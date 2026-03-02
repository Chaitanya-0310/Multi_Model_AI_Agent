# src/tools.py
import re
import json
from typing import Type, List, Dict, Any
from pydantic import BaseModel, Field
from langchain.tools import BaseTool
from src.rag import retrieve_context
from src.config import RETRIEVER_TOOL_DESCRIPTION, COMPETITORS
from src.google_utils import create_doc, add_calendar_event


# ─── Retriever Tool ───────────────────────────────────────────────────────────

class RetrieverInput(BaseModel):
    """Input for the retriever tool."""
    query: str = Field(description="The search query to look up in the knowledge base.")

class RetrieverTool(BaseTool):
    name: str = "knowledge_base_retriever"
    description: str = RETRIEVER_TOOL_DESCRIPTION
    args_schema: Type[BaseModel] = RetrieverInput

    def _run(self, query: str) -> str:
        try:
            context = retrieve_context(query)
            if not context or context.strip() == "No knowledge base found. Please run ingestion.":
                return "Error: Knowledge base empty. Please run ingestion first."
            return context
        except Exception as e:
            return f"Error retrieving context: {str(e)}"

    async def _arun(self, query: str) -> str:
        return self._run(query)


# ─── Content Quality Analyzer Tool (Function Calling) ────────────────────────

class ContentQualityInput(BaseModel):
    """Input for the content quality analyzer."""
    asset_type: str = Field(
        description="The type/name of the marketing asset being analyzed (e.g., 'Email Campaign', 'LinkedIn Post')."
    )
    content: str = Field(
        description="The full text content of the marketing asset to analyze."
    )

class ContentQualityTool(BaseTool):
    """
    Deterministic quality checker the LLM calls via function calling.
    Checks word count, CTA presence, prohibited terms, platform character limits,
    and measurable benefits — things LLMs are unreliable at computing themselves.
    """
    name: str = "content_quality_analyzer"
    description: str = (
        "Analyze the quality of a marketing asset. "
        "Checks word count, CTA presence, prohibited terms, platform character limits, "
        "and presence of measurable benefits (numbers/stats). "
        "Call this tool for EVERY asset before writing your compliance verdict."
    )
    args_schema: Type[BaseModel] = ContentQualityInput

    # Platform character/word limits — sourced from industry standards
    PLATFORM_LIMITS: dict = {
        "email subject": 50,
        "email": 2000,
        "linkedin": 3000,
        "twitter": 280,
        "x post": 280,
        "blog": 2500,
        "press release": 1200,
        "social media": 300,
    }

    # Must include at least one of these to qualify as having a CTA
    CTA_KEYWORDS: list = [
        "contact us", "learn more", "get started", "try", "schedule a demo",
        "download", "sign up", "register", "free trial", "visit", "call us",
        "request a quote", "book a call", "see how", "find out",
    ]

    def _run(self, asset_type: str, content: str) -> str:
        issues = []
        passes = []

        word_count = len(content.split())
        char_count = len(content)

        # ── Platform character limit check ────────────────────────────────────
        asset_lower = asset_type.lower()
        limit_hit = False
        for platform, limit in self.PLATFORM_LIMITS.items():
            if platform in asset_lower:
                if char_count > limit:
                    issues.append(
                        f"Exceeds {platform} character limit "
                        f"({char_count:,} / {limit:,} chars — {char_count - limit:,} over)"
                    )
                    limit_hit = True
                else:
                    passes.append(f"Within {platform} character limit ({char_count:,}/{limit:,})")
                break
        if not limit_hit and not passes:
            passes.append(f"No strict platform limit — {char_count:,} chars, {word_count} words")

        # ── CTA check ─────────────────────────────────────────────────────────
        content_lower = content.lower()
        found_cta = next((kw for kw in self.CTA_KEYWORDS if kw in content_lower), None)
        if found_cta:
            passes.append(f"CTA present ('{found_cta}')")
        else:
            issues.append(
                "No clear call-to-action detected. "
                "Brand guidelines require a CTA — add one of: "
                "get started, schedule a demo, learn more, free trial, etc."
            )

        # ── Prohibited terms check ────────────────────────────────────────────
        brand_prohibited = ["revolutionary", "game-changer", "game changer", "best", "perfect"]
        found_prohibited = [t for t in brand_prohibited + COMPETITORS if t.lower() in content_lower]
        if found_prohibited:
            issues.append(f"Prohibited terms found: {', '.join(found_prohibited)}")
        else:
            passes.append("No prohibited terms or competitor names detected")

        # ── Measurable benefits check ─────────────────────────────────────────
        has_numbers = bool(re.search(r'\d+', content))
        if has_numbers:
            passes.append("Measurable benefits present (numbers/stats found)")
        else:
            issues.append(
                "No measurable benefits (numbers/stats). "
                "Brand guidelines require quantifiable results — "
                "e.g., '48-hour migration', '99.7% success rate', '40% cost reduction'."
            )

        # ── Sentence length check (brand guideline: under 25 words) ──────────
        sentences = re.split(r'[.!?]+', content)
        long_sentences = [s.strip() for s in sentences if len(s.split()) > 25 and s.strip()]
        if long_sentences:
            issues.append(
                f"{len(long_sentences)} sentence(s) exceed 25-word limit "
                f"(Wealthsimple brand guideline: keep sentences concise)"
            )
        else:
            passes.append("All sentences within 25-word brand guideline")

        # ── Score ─────────────────────────────────────────────────────────────
        score = max(0, 100 - (len(issues) * 20))

        # ── Format report ─────────────────────────────────────────────────────
        lines = [
            f"Content Quality Report — {asset_type}",
            f"{'─' * 50}",
            f"Score     : {score}/100",
            f"Words     : {word_count}  |  Characters: {char_count:,}",
            "",
        ]
        if passes:
            lines.append("✅ Checks Passed:")
            for p in passes:
                lines.append(f"   • {p}")
        if issues:
            lines.append("")
            lines.append(f"⚠️  Issues ({len(issues)}):")
            for i in issues:
                lines.append(f"   • {i}")
        if not issues:
            lines.append("")
            lines.append("All quality checks passed — content meets Wealthsimple brand standards.")

        return "\n".join(lines)

    async def _arun(self, asset_type: str, content: str) -> str:
        return self._run(asset_type, content)


# ─── Google Doc & Calendar Tools ──────────────────────────────────────────────

class GoogleDocInput(BaseModel):
    title: str = Field(description="Document title.")
    content: str = Field(description="Content to write in the document.")

class GoogleDocTool(BaseTool):
    name: str = "google_doc_creator"
    description: str = "Create a Google Doc with the specified title and content."
    args_schema: Type[BaseModel] = GoogleDocInput

    def _run(self, title: str, content: str) -> str:
        try:
            doc_id, url = create_doc(title, content)
            return f"Successfully created document. ID: {doc_id}, URL: {url}"
        except Exception as e:
            return f"Error creating Google Doc: {str(e)}"

class GoogleCalendarInput(BaseModel):
    summary: str = Field(description="Event title.")
    start_time: str = Field(description="Start time in ISO format (e.g., 2025-09-01T09:00:00Z).")
    description: str = Field(default="", description="Event description.")

class GoogleCalendarTool(BaseTool):
    name: str = "google_calendar_scheduler"
    description: str = "Schedule a publishing date in Google Calendar."
    args_schema: Type[BaseModel] = GoogleCalendarInput

    def _run(self, summary: str, start_time: str, description: str = "") -> str:
        try:
            event_id = add_calendar_event(summary, start_time, description)
            return f"Successfully scheduled event. ID: {event_id}"
        except Exception as e:
            return f"Error scheduling event: {str(e)}"


# ─── Compliance Checker Tool ──────────────────────────────────────────────────

class ComplianceCheckerInput(BaseModel):
    asset_type: str = Field(description="The type of marketing asset (e.g., 'Email Campaign', 'LinkedIn Post').")
    content: str = Field(description="The full text content of the marketing asset to check.")

class ComplianceCheckerTool(BaseTool):
    """
    Deterministic regex-based compliance checker.
    Scans content for prohibited phrases, missing disclaimers, and unsubstantiated stats.
    Returns structured JSON with flags and a pass/fail verdict.
    """
    name: str = "compliance_checker"
    description: str = (
        "Check a marketing asset for regulatory and brand compliance issues. "
        "Detects absolute guarantee language, missing disclaimers, competitor disparagement, "
        "and unsubstantiated statistics. Returns structured JSON with severity-rated flags."
    )
    args_schema: Type[BaseModel] = ComplianceCheckerInput

    # HIGH severity patterns — block publication
    HIGH_PATTERNS: List[Dict[str, str]] = [
        {"pattern": r"\bguaranteed?\s+(returns?|results?|savings?|profits?|success)\b",
         "issue": "Absolute guarantee language: 'guaranteed [returns/results/savings]'",
         "suggestion": "Replace with hedged language: 'designed to help achieve', 'customers report', 'can support'"},
        {"pattern": r"\brisk[- ]free\b",
         "issue": "Prohibited phrase: 'risk-free'",
         "suggestion": "Remove entirely or replace with specific risk mitigation features"},
        {"pattern": r"\b100\s*%\s*(certain|guaranteed?|sure|accurate)\b",
         "issue": "Absolute certainty claim: '100% certain/guaranteed'",
         "suggestion": "Replace with a specific, substantiated metric or remove"},
        {"pattern": r"\balways\s+(profitable|works?|succeeds?|deliver[s]?)\b",
         "issue": "Absolute performance claim: 'always [profitable/works]'",
         "suggestion": "Replace with 'consistently', 'in most cases', or cite a specific success rate"},
        {"pattern": r"\bnever\s+(lose[s]?|fail[s]?|miss[es]?)\b",
         "issue": "Absolute negative claim: 'never lose/fail'",
         "suggestion": "Remove or replace with 'industry-low failure rate' citing a source"},
        {"pattern": r"\bfail[- ]?proof\b|\bfool[- ]?proof\b|\binfallible\b",
         "issue": "Prohibited absolute reliability claim: 'fail-proof / fool-proof / infallible'",
         "suggestion": "Remove entirely; use specific reliability metrics instead"},
        {"pattern": r"\byou\s+will\s+definitely\b|\bwe\s+guarantee\s+you\s+will\b",
         "issue": "Personal guarantee language",
         "suggestion": "Replace with 'customers typically report' or 'designed to help you'"},
    ]

    # MEDIUM severity patterns — should fix before publishing
    MEDIUM_PATTERNS: List[Dict[str, str]] = [
        {"pattern": r"\b\d+\s*%(?!\s*(uptime|success\s+rate|of\s+customers))",
         "issue": "Unsubstantiated statistic: percentage claim without a cited source",
         "suggestion": "Add source citation in parentheses: '(Source: [Report Name], [Year])'"},
        {"pattern": r"\b(the\s+)?(#1|number\s+one|market\s+leader|best\s+in\s+(the\s+)?market|most\s+advanced|most\s+powerful|most\s+secure)\b",
         "issue": "Unverified superlative claim without substantiation",
         "suggestion": "Remove or add an independent benchmark/analyst citation"},
        {"pattern": r"\bcompetitor[s]?\s+(don'?t|can'?t|won'?t|fail[s]?|lack[s]?)\b",
         "issue": "Potential competitor disparagement language",
         "suggestion": "Reframe as a positive Wealthsimple differentiator without referencing competitors"},
    ]

    # Financial metrics requiring disclaimers
    FINANCIAL_DISCLAIMER_PATTERNS: List[str] = [
        r"\bROI\b", r"\breturn\s+on\s+investment\b",
        r"\bcost\s+(savings?|reduction)\b", r"\bsave[s]?\s+\$?\d+",
        r"\bpay[s]?\s+for\s+itself\b", r"\bprofitability\b",
    ]

    REQUIRED_DISCLAIMER_SNIPPET: str = "results may vary"

    def _run(self, asset_type: str, content: str) -> str:
        flags = []
        content_lower = content.lower()

        # Check HIGH severity patterns
        for rule in self.HIGH_PATTERNS:
            if re.search(rule["pattern"], content_lower):
                flags.append({
                    "severity": "HIGH",
                    "issue": rule["issue"],
                    "suggestion": rule["suggestion"],
                })

        # Check MEDIUM severity patterns
        for rule in self.MEDIUM_PATTERNS:
            if re.search(rule["pattern"], content_lower):
                flags.append({
                    "severity": "MEDIUM",
                    "issue": rule["issue"],
                    "suggestion": rule["suggestion"],
                })

        # Check for financial claims without disclaimer
        has_financial_claim = any(
            re.search(p, content_lower) for p in self.FINANCIAL_DISCLAIMER_PATTERNS
        )
        has_disclaimer = self.REQUIRED_DISCLAIMER_SNIPPET in content_lower
        if has_financial_claim and not has_disclaimer:
            flags.append({
                "severity": "HIGH",
                "issue": "Financial performance metric cited without required disclaimer",
                "suggestion": (
                    "Add disclaimer: 'Results based on [customer/source]. "
                    "Individual results may vary based on implementation specifics.'"
                ),
            })

        has_high = any(f["severity"] == "HIGH" for f in flags)
        result = {"flags": flags, "passed": not has_high}
        return json.dumps(result)

    async def _arun(self, asset_type: str, content: str) -> str:
        return self._run(asset_type, content)


# ─── Campaign Performance Estimator Tool ─────────────────────────────────────

class PerformanceEstimatorInput(BaseModel):
    asset_type: str = Field(
        description=(
            "The marketing asset type to estimate performance for. "
            "Supported: email, linkedin, blog, twitter, press release, social media, paid ads."
        )
    )

class CampaignPerformanceEstimatorTool(BaseTool):
    """
    Returns industry-standard KPI benchmarks for a given marketing asset type.
    Data sourced from HubSpot 2025 Marketing Report, Mailchimp Email Benchmarks,
    LinkedIn Marketing Solutions, Content Marketing Institute 2025.
    """
    name: str = "campaign_performance_estimator"
    description: str = (
        "Get projected performance benchmarks for a marketing asset type. "
        "Returns estimated KPIs (open rates, CTR, engagement, reach, conversion) "
        "based on industry benchmarks. Call once per planned asset."
    )
    args_schema: Type[BaseModel] = PerformanceEstimatorInput

    # Industry benchmarks — sourced from HubSpot 2025, Mailchimp, LinkedIn, CMI 2025
    BENCHMARKS: Dict[str, Dict[str, str]] = {
        "email": {
            "Open Rate": "21.3%",
            "Click-Through Rate": "2.3%",
            "Conversion Rate": "1.8%",
            "Unsubscribe Rate": "0.2%",
            "Source": "HubSpot Email Marketing Report 2025 / Mailchimp Benchmarks",
        },
        "linkedin": {
            "Organic Reach": "5–10% of followers",
            "Engagement Rate": "0.5–1.0%",
            "Lead Gen Form CVR": "2.7%",
            "Sponsored Content CTR": "0.44%",
            "Source": "LinkedIn Marketing Solutions Benchmarks 2025",
        },
        "blog": {
            "Organic Traffic Lift": "+15% over 90 days (SEO-optimised post)",
            "Avg. Time on Page": "3.5 minutes",
            "Bounce Rate": "65–75%",
            "Lead Generation Rate": "0.5–1.0% of readers",
            "Source": "HubSpot State of Marketing 2025 / CMI B2B Report 2025",
        },
        "twitter": {
            "Engagement Rate": "0.045%",
            "Click Rate": "0.86%",
            "Impressions per Post": "1,000–5,000 (10k followers)",
            "Retweet Rate": "0.03%",
            "Source": "Rival IQ Social Media Industry Report 2025",
        },
        "press release": {
            "Media Pickup Rate": "5–15 journalists",
            "Earned Media Value": "$500–$2,000 avg per placement",
            "Online Syndications": "25–100 outlets",
            "Backlinks Generated": "3–8 high-DA links",
            "Source": "Cision State of the Media Report 2025",
        },
        "social media": {
            "Organic Reach": "2–5% of followers",
            "Engagement Rate": "1–3% (B2B average)",
            "CTR on Posts with Links": "1.1%",
            "Story View Rate": "5–7% of followers",
            "Source": "Sprout Social Index 2025",
        },
        "paid ads": {
            "Average CTR": "2.0–5.0% (B2B SaaS)",
            "Cost Per Click": "$3.50–$8.00",
            "Conversion Rate": "2.4–5.0%",
            "Cost Per Lead": "$40–$120",
            "Source": "WordStream Google Ads Benchmarks 2025",
        },
        "video": {
            "Average View-Through Rate": "45% (first 30 seconds)",
            "Engagement Rate": "6–8% on LinkedIn",
            "CTR from Video": "1.84% (highest of any digital format)",
            "Source": "Wistia State of Video Report 2025",
        },
    }

    def _run(self, asset_type: str) -> str:
        key = asset_type.lower().strip()
        # Fuzzy match
        for benchmark_key in self.BENCHMARKS:
            if benchmark_key in key or key in benchmark_key:
                data = self.BENCHMARKS[benchmark_key]
                lines = [f"**{benchmark_key.title()} Benchmarks:**"]
                for metric, value in data.items():
                    if metric != "Source":
                        lines.append(f"  • {metric}: {value}")
                lines.append(f"  *(Source: {data['Source']})*")
                return "\n".join(lines)

        # Default fallback
        return (
            f"No specific benchmarks found for '{asset_type}'. "
            "General B2B marketing benchmark: 1–3% engagement rate, 2–5% conversion rate. "
            "(Source: HubSpot State of Marketing 2025)"
        )

    async def _arun(self, asset_type: str) -> str:
        return self._run(asset_type)


def get_tools() -> List[BaseTool]:
    """Returns retriever, Google Doc, and Calendar tools."""
    return [RetrieverTool(), GoogleDocTool(), GoogleCalendarTool()]
