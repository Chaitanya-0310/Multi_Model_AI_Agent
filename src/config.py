# src/config.py

# Model Configurations
DEFAULT_MODEL = "gemini-2.5-flash"
EMBEDDING_MODEL = "embedding-001"

# Intent Classification Categories
INTENT_CATEGORIES = ["Factual", "Analytical", "ChitChat", "ClarificationNeeded"]

# Competitor list — sourced from brand_guidelines.txt "Prohibited Terms"
# The guardrails validator will redact any of these if they appear in generated content
COMPETITORS = [
    "Questrade", "TD Direct Investing", "RBC Direct Investing",
    "Nest Wealth", "Betterment",
]

# Prompts
ROUTER_PROMPT = """You are an expert router. Classify the user query into one of the following categories:
- Factual: Queries that require specific facts or data retrieval.
- Analytical: Queries that require analysis, comparisons, or strategic thinking.
- ChitChat: General conversation, greetings, or non-business related queries.
- ClarificationNeeded: Queries that are ambiguous or lack enough information to proceed.

User Query: {goal}
"""

PLANNER_PROMPT = """You are a senior marketing strategist at Wealthsimple.
Given a campaign goal, produce a precise list of 3–5 marketing assets to create.

NAMING RULES (strictly follow these):
- Each asset name MUST follow the format: "[Channel]: [Specific description]"
- The description must mention the product AND the target audience.
- Examples of good names:
    "Email Campaign: Wealthsimple Invest TFSA Guide for First-Time Investors"
    "LinkedIn Post: Wealthsimple Trade Commission-Free Story for Millennial Professionals"
    "Blog Post: How Canadians Are Building Wealth with Wealthsimple Invest"
    "Social Media Post: Wealthsimple Cash 4.5% High-Interest Savings for Young Savers"
- Match asset types to the channels explicitly stated in the goal.
- If no channels are mentioned, choose the 3 highest-impact assets for the stated objective.
- Do NOT create generic names like "Email Campaign" or "Blog Post" without a specific description.

Campaign Goal: {goal}
"""

WRITER_PROMPT = """You are a marketing copywriter. Write a {asset_type} for this goal.
Use the following context/guidelines:
{context}

Reasoning Trace: (Think about the tone, key message, and call to action based on the context)

Goal: {goal}
Asset Type: {asset_type}
"""

REVIEWER_PROMPT = """You are a brand compliance officer for Wealthsimple.
Review the marketing asset below against the brand guidelines.

Brand Guidelines:
{guidelines}

Asset Type: {asset}
Content:
{content}

Provide a structured review with:
1. VERDICT: PASS or FAIL
2. TONE CHECK: Does it match the brand voice (simple and human, honest, encouraging, proudly Canadian)?
3. PROHIBITED TERMS: List any found (revolutionary, game-changer, guaranteed returns, risk-free, competitor names)
4. MEASURABLE BENEFITS: Are stats or specific numbers included?
5. SUGGESTIONS: Up to 3 specific, actionable improvements (if any)

Be concise. Each section should be 1–2 sentences.
"""

RETRIEVAL_GRADER_PROMPT = """You are a grader assessing relevance of a retrieved document to a user question. 
If the document contains keyword(s) or semantic meaning related to the user question, grade it as relevant. 
It does not need to be a perfect answer; the goal is to filter out clearly irrelevant documents.

Give a binary score 'yes' or 'no' score to indicate whether the document is relevant to the question.

Retrieved Document: 
{document}

User Question: {question}
"""

HALLUCINATION_GRADER_PROMPT = """You are a grader assessing whether an LLM generation is grounded in / supported by a set of retrieved facts.
Give a binary score 'yes' or 'no'. 'yes' means that the answer is grounded in / supported by the set of facts.

Set of Facts:
{documents}

LLM Generation: {generation}
"""

WRITER_FEEDBACK_PROMPT = """You are a marketing copywriter. Write a {asset_type} for this goal.
Use the following context/guidelines:
{context}

Reasoning Trace: (Think about the tone, key message, and call to action based on the context)

Goal: {goal}
Asset Type: {asset_type}

IMPORTANT: The user reviewed the previous draft and provided this feedback. You MUST incorporate it:
{feedback}
"""

QUERY_REWRITER_PROMPT = """You are an expert at optimizing search queries for semantic vector database retrieval.
Rewrite the following marketing goal into a precise, focused search query.
Extract the most important terms: product names, target audience, marketing channel, and specific features.
Return ONLY the rewritten query string — no explanation, no preamble.

Original Goal: {goal}
Asset Type: {asset_type}
"""

COMPLIANCE_CHECKER_PROMPT = """You are a senior marketing compliance officer at Wealthsimple.
Review the following marketing asset for regulatory and brand compliance issues.

Asset Type: {asset_type}
Content:
{content}

Flag any of the following issues with their severity:

HIGH SEVERITY (blocks publication):
- Absolute guarantee language: "guaranteed", "risk-free", "100% certain", "always profitable", "never lose", "fail-proof"
- Missing financial disclaimer when ROI%, cost savings, or performance metrics are cited
- Direct competitor disparagement (naming competitors negatively)
- Unverified superlative claims ("the best", "#1", "most advanced") without a cited source

MEDIUM SEVERITY (should fix before publish):
- Unsubstantiated statistics (numbers with % not backed by a cited source)
- Missing call to action in promotional materials
- Overly absolute language that stops short of a guarantee

LOW SEVERITY (best practice improvement):
- Passive voice overuse
- Missing testimonial attribution
- Informal language in formal channel

Respond ONLY with a JSON object in this exact format (no markdown, no explanation):
{{
  "flags": [
    {{"severity": "HIGH", "issue": "exact phrase or description", "suggestion": "how to fix it"}},
    {{"severity": "MEDIUM", "issue": "...", "suggestion": "..."}},
    {{"severity": "LOW", "issue": "...", "suggestion": "..."}}
  ],
  "passed": true
}}

If there are no issues, return: {{"flags": [], "passed": true}}
The "passed" field must be false if there is at least one HIGH severity flag.
"""

WRITER_VARIANT_PROMPT = """You are a marketing copywriter specialising in audience personalisation.
Below is a primary marketing draft written for a specific audience segment.
Your task is to rewrite it for a COMPLEMENTARY audience segment — same campaign, different angle.

Asset Type: {asset_type}
Original Audience: {primary_audience}
Variant Audience: {variant_audience}
Campaign Goal: {goal}

Primary Draft (for reference — do NOT copy, only adapt):
{primary_draft}

Write the variant draft now. Keep the same asset type and length, but adjust:
- Tone and vocabulary to match the variant audience's priorities
- Pain points and motivators specific to {variant_audience}
- Any metrics or examples that are more relevant to {variant_audience}
"""

PERFORMANCE_ESTIMATOR_PROMPT = """You are a marketing analytics expert. Given the list of planned campaign assets below,
call the campaign_performance_estimator tool for each asset type to retrieve industry benchmark KPIs.
Then summarise the projected performance in 1-2 sentences per asset.

Campaign Goal: {goal}
Planned Assets:
{assets_list}

For each asset, call the tool with the appropriate asset_type parameter.
After collecting all estimates, provide a brief written summary.
"""

# Tool Docstrings
RETRIEVER_TOOL_DESCRIPTION = "Use this tool ONLY to retrieve marketing guidelines, product information, and brand history from the knowledge base."

# LLM Provider Factory
import os
from dotenv import load_dotenv

load_dotenv()

def get_llm(temperature: float = 0):
    """
    Returns an LLM instance based on LLM_PROVIDER env var.
    Set LLM_PROVIDER=groq in .env to use Groq (Llama 3.3 70B) — much higher free-tier rate limits.
    Defaults to Google Gemini if not set.
    """
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    if provider == "groq":
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            api_key=os.getenv("GROQ_API_KEY"),
            temperature=temperature,
        )
    # Default: Google Gemini
    from langchain_google_genai import ChatGoogleGenerativeAI
    return ChatGoogleGenerativeAI(model=DEFAULT_MODEL, temperature=temperature)


# Langfuse Configuration

LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

def is_langfuse_enabled() -> bool:
    """Check if Langfuse is properly configured."""
    return bool(LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY)

def get_langfuse_config() -> dict:
    """Get Langfuse configuration as a dictionary."""
    return {
        "public_key": LANGFUSE_PUBLIC_KEY,
        "secret_key": LANGFUSE_SECRET_KEY,
        "host": LANGFUSE_HOST,
        "enabled": is_langfuse_enabled()
    }
