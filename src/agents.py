from typing import TypedDict, List, Annotated, Dict, Optional, Literal
import os
import operator
import logging
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
import guardrails as gd
from guardrails.validators import Validator, register_validator, PassResult, FailResult

from src.config import (
    DEFAULT_MODEL,
    get_llm,
    COMPETITORS,
    ROUTER_PROMPT,
    PLANNER_PROMPT,
    WRITER_PROMPT,
    WRITER_FEEDBACK_PROMPT,
    WRITER_VARIANT_PROMPT,
    REVIEWER_PROMPT,
    RETRIEVAL_GRADER_PROMPT,
    HALLUCINATION_GRADER_PROMPT,
    QUERY_REWRITER_PROMPT,
    COMPLIANCE_CHECKER_PROMPT,
    PERFORMANCE_ESTIMATOR_PROMPT,
)
from src.tools import get_tools
from src.langfuse_integration import (
    get_langfuse_handler,
    get_langfuse_client,
    track_user_feedback,
    track_guardrails_validation,
    track_retrieval_metrics,
    is_langfuse_enabled
)

load_dotenv()

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MarketingAgent")

# --- State Definition ---

class AgentState(TypedDict):
    goal: str
    plan: List[str]
    drafts: Dict[str, str]
    critique: str
    messages: Annotated[List[BaseMessage], operator.add]
    intent: str
    retrieved_docs: str
    retry_count: int
    reasoning_trace: str
    current_asset: Optional[str]
    errors: List[str]
    publish_results: Dict[str, str]
    user_feedback: Dict[str, str]        # Stores user feedback for each asset
    draft_status: Dict[str, str]         # Tracks approval: "approved", "needs_revision", "pending"
    feedback_iteration: int              # Counts regeneration attempts
    langfuse_trace_id: Optional[str]     # Langfuse trace ID for observability
    # --- Quality & routing fields ---
    retrieved_docs_relevant: bool        # Whether the last retrieved docs are relevant
    generation_grounded: bool            # Whether the last generation is grounded in docs
    rewritten_query: Optional[str]       # Query rewriter output (not the original goal)
    confidence_scores: Dict[str, float]  # Per-asset quality confidence 0.0–1.0
    # --- Feature: Compliance Checker ---
    compliance_flags: Dict[str, List[Dict]]   # Per asset: [{severity, issue, suggestion}]
    compliance_summary: Dict[str, str]         # Per asset: "PASS" / "WARN" / "BLOCK"
    compliance_acknowledged: bool              # Whether user acknowledged HIGH flags
    # --- Feature: Audience Variant Generator ---
    draft_variants: Dict[str, str]             # Per asset: variant draft text
    # --- Feature: Performance Estimator ---
    performance_estimates: Dict[str, Dict]     # Per asset: {metric: value}
    # --- Feature: Brand Review Gate ---
    compliance_revision_requested: Optional[bool]   # None=not decided, False=accept, True=revise
    compliance_revision_notes: Dict[str, str]        # Per-asset revision notes from brand review

# --- Structured Outputs ---

class RouterOutput(BaseModel):
    """Result of query classification."""
    intent: Literal["Factual", "Analytical", "ChitChat", "ClarificationNeeded"] = Field(
        description="The classified intent of the user query."
    )
    reasoning: str = Field(description="Brief reasoning for the classification.")

class Plan(BaseModel):
    """List of assets to create."""
    steps: List[str] = Field(description="List of marketing assets to generate.")
    reasoning: str = Field(description="Reasoning for choosing these assets.")

class GradeRetrieval(BaseModel):
    """Binary score for relevance check."""
    binary_score: Literal["yes", "no"] = Field(description="Relevance score 'yes' or 'no'")

class GradeHallucination(BaseModel):
    """Binary score for hallucination check."""
    binary_score: Literal["yes", "no"] = Field(description="Hallucination score 'yes' or 'no'")

# --- Router Node ---

def router_node(state: AgentState) -> Dict:
    """Classifies the user query intent."""
    logger.info("--- ROUTER ---")
    goal = state.get("goal", "")
    
    # Get Langfuse callback handler
    langfuse_handler = get_langfuse_handler()
    callbacks = [langfuse_handler] if langfuse_handler else []
    
    llm = get_llm(temperature=0)
    structured_llm = llm.with_structured_output(RouterOutput)
    
    prompt = ChatPromptTemplate.from_template(ROUTER_PROMPT)
    chain = prompt | structured_llm
    
    logger.info(f"Input Goal: {goal}")
    result = chain.invoke({"goal": goal}, config={"callbacks": callbacks})
    logger.info(f"Detected Intent: {result.intent}")
    
    return {
        "intent": result.intent,
        "reasoning_trace": f"Router Reasoning: {result.reasoning}"
    }

# --- Grader Nodes ---

def retrieval_grader(state: AgentState) -> Dict:
    """Grades if the retrieved documents are relevant to the question."""
    logger.info("--- RETRIEVAL GRADER ---")
    question = state.get("rewritten_query") or state.get("goal")
    docs = state.get("retrieved_docs")

    # Get Langfuse callback handler
    langfuse_handler = get_langfuse_handler()
    callbacks = [langfuse_handler] if langfuse_handler else []

    llm = get_llm(temperature=0)
    structured_llm = llm.with_structured_output(GradeRetrieval)

    prompt = ChatPromptTemplate.from_template(RETRIEVAL_GRADER_PROMPT)
    chain = prompt | structured_llm

    result = chain.invoke({"question": question, "document": docs}, config={"callbacks": callbacks})
    is_relevant = result.binary_score == "yes"
    logger.info(f"Retrieval Relevance: {result.binary_score} → retrieved_docs_relevant={is_relevant}")

    # Track relevance score with Langfuse
    trace_id = state.get("langfuse_trace_id")
    if trace_id:
        track_retrieval_metrics(trace_id, question, 0, result.binary_score)

    return {
        "retrieved_docs_relevant": is_relevant,
        "reasoning_trace": state.get("reasoning_trace", "") + f"\nRetrieval Grade: {result.binary_score}",
    }

def hallucination_grader(state: AgentState) -> Dict:
    """Grades if the generated answer is grounded in the retrieved documents."""
    logger.info("--- HALLUCINATION GRADER ---")
    docs = state.get("retrieved_docs")
    current_asset = state.get("current_asset")
    generation = state.get("drafts", {}).get(current_asset, "")

    # Get Langfuse callback handler
    langfuse_handler = get_langfuse_handler()
    callbacks = [langfuse_handler] if langfuse_handler else []

    llm = get_llm(temperature=0)
    structured_llm = llm.with_structured_output(GradeHallucination)

    prompt = ChatPromptTemplate.from_template(HALLUCINATION_GRADER_PROMPT)
    chain = prompt | structured_llm

    result = chain.invoke({"documents": docs, "generation": generation}, config={"callbacks": callbacks})
    is_grounded = result.binary_score == "yes"
    logger.info(f"Hallucination Grade: {result.binary_score} → generation_grounded={is_grounded}")

    # Compute per-asset confidence score from retrieval + hallucination signals
    retrieved_relevant = state.get("retrieved_docs_relevant", False)
    if retrieved_relevant and is_grounded:
        confidence = 1.0
    elif retrieved_relevant and not is_grounded:
        confidence = 0.5
    elif not retrieved_relevant and is_grounded:
        confidence = 0.6
    else:
        confidence = 0.2

    new_confidence_scores = (state.get("confidence_scores") or {}).copy()
    if current_asset:
        new_confidence_scores[current_asset] = confidence
    logger.info(f"Confidence score for '{current_asset}': {confidence:.0%}")

    return {
        "generation_grounded": is_grounded,
        "confidence_scores": new_confidence_scores,
        "reasoning_trace": state.get("reasoning_trace", "") + f"\nHallucination Grade: {result.binary_score}",
    }

@register_validator(name="competitor_check", data_type="string")
class CompetitorCheck(Validator):
    def __init__(self, competitors: List[str], on_fail: str = "fix"):
        super().__init__(on_fail=on_fail, competitors=competitors)
        self.competitors = competitors

    def validate(self, value: str, metadata: Dict = {}) -> gd.validators.ValidationResult:
        for competitor in self.competitors:
            if competitor.lower() in value.lower():
                return FailResult(
                    error_message=f"Value contains competitor: {competitor}",
                    fix_value=value.replace(competitor, "[REDACTED]")
                )
        return PassResult()

# --- Agent Nodes ---

def planner_node(state: AgentState) -> Dict:
    """
    Generates a marketing plan (Pass 1) then estimates KPIs per asset (Pass 2).
    Pass 2 uses function calling to fetch industry benchmarks via CampaignPerformanceEstimatorTool.
    """
    logger.info("--- PLANNER ---")
    goal = state.get("goal")

    langfuse_handler = get_langfuse_handler()
    callbacks = [langfuse_handler] if langfuse_handler else []

    llm = get_llm(temperature=0)
    structured_llm = llm.with_structured_output(Plan)

    prompt = ChatPromptTemplate.from_template(PLANNER_PROMPT)
    chain = prompt | structured_llm

    logger.info(f"LLM Input: {goal}")
    result = chain.invoke({"goal": goal}, config={"callbacks": callbacks})
    logger.info(f"LLM Output (Plan): {result.steps}")

    # ── Pass 2: Performance Estimator ────────────────────────────────────────
    from src.tools import CampaignPerformanceEstimatorTool
    estimator_tool = CampaignPerformanceEstimatorTool()
    performance_estimates: Dict[str, Dict] = {}

    for asset in result.steps:
        try:
            raw = estimator_tool.run(asset)
            # Parse the markdown-formatted benchmarks into a simple dict
            estimates: Dict[str, str] = {}
            for line in raw.split("\n"):
                if line.strip().startswith("•"):
                    parts = line.strip("• ").split(": ", 1)
                    if len(parts) == 2:
                        estimates[parts[0].strip()] = parts[1].strip()
                elif "Source:" in line:
                    estimates["Source"] = line.split("Source:", 1)[1].strip(" *()")
            performance_estimates[asset] = estimates
            logger.info(f"Performance estimates for '{asset}': {estimates}")
        except Exception as e:
            logger.warning(f"Performance estimator failed for '{asset}': {e}")
            performance_estimates[asset] = {}

    return {
        "plan": result.steps,
        "performance_estimates": performance_estimates,
        "reasoning_trace": state.get("reasoning_trace", "") + f"\nPlanner Reasoning: {result.reasoning}",
    }

def retriever_node(state: AgentState) -> Dict:
    """Retrieves context using the retriever tool."""
    logger.info("--- RETRIEVER ---")
    goal = state.get("goal")
    rewritten_query = state.get("rewritten_query")

    # Determine which asset to retrieve for next
    plan = state.get("plan", [])
    drafts = state.get("drafts", {})
    current_asset = None
    for asset in plan:
        if asset not in drafts:
            current_asset = asset
            break

    if not current_asset:
        current_asset = "general marketing assets"

    # Reset retry count and rewritten query when switching to a new asset
    retry_count = state.get("retry_count", 0)
    if state.get("current_asset") != current_asset:
        retry_count = 0
        rewritten_query = None  # Fresh start for each new asset

    tools = get_tools()
    retriever_tool = next(t for t in tools if t.name == "knowledge_base_retriever")

    # Prefer rewritten query over raw goal for better recall
    query = rewritten_query if rewritten_query else f"{current_asset} related to {goal}"
    logger.info(f"Tool Call (Retriever) — query: {query}")

    context = retriever_tool.run(query)
    logger.info(f"Tool Output (Retriever): {context[:200]}...")

    # Track retrieval metrics with Langfuse
    trace_id = state.get("langfuse_trace_id")
    if trace_id:
        doc_count = len(context.split("\n\n")) if context else 0
        track_retrieval_metrics(trace_id, query, doc_count)

    return {
        "retrieved_docs": context,
        "current_asset": current_asset,
        "retry_count": retry_count,
        "rewritten_query": rewritten_query,
    }

def writer_node(state: AgentState) -> Dict:
    """Generates content for a specific asset."""
    logger.info("--- WRITER ---")
    goal = state.get("goal")
    plan = state.get("plan", [])
    drafts = state.get("drafts", {})
    context = state.get("retrieved_docs", "")
    user_feedback = state.get("user_feedback", {})
    
    # Use asset from state if set, otherwise find next
    current_asset = state.get("current_asset")
    if not current_asset or current_asset in drafts:
        for asset in plan:
            if asset not in drafts:
                current_asset = asset
                break
    
    if not current_asset:
        return {}

    # Get Langfuse callback handler
    langfuse_handler = get_langfuse_handler()
    callbacks = [langfuse_handler] if langfuse_handler else []

    # Use higher temperature for creative writing
    llm = get_llm(temperature=0.7)

    # Check if there's user feedback for this asset (regeneration case)
    feedback_text = user_feedback.get(current_asset, "")
    if feedback_text:
        logger.info(f"Regenerating {current_asset} with user feedback: {feedback_text}")
        prompt = ChatPromptTemplate.from_template(WRITER_FEEDBACK_PROMPT)
        chain = prompt | llm
        result = chain.invoke({
            "asset_type": current_asset,
            "context": context,
            "goal": goal,
            "feedback": feedback_text
        }, config={"callbacks": callbacks})
    else:
        prompt = ChatPromptTemplate.from_template(WRITER_PROMPT)
        chain = prompt | llm
        logger.info(f"Writing asset: {current_asset}")
        logger.info(f"LLM Input (Writer): Goal={goal}, Asset={current_asset}, Context Length={len(context)}")
        result = chain.invoke({"asset_type": current_asset, "context": context, "goal": goal}, config={"callbacks": callbacks})
    logger.info(f"LLM Output (Writer): {result.content[:200]}...")
    
    # --- Guardrails Integration ---
    logger.info(f"--- GUARDRAILS CHECK for {current_asset} ---")
    
    # Initialize Guard with validators — competitor list loaded from config
    guard = gd.Guard().use(
        CompetitorCheck(competitors=COMPETITORS, on_fail="fix")
    )
    
    try:
        # Validate the generated content
        raw_content = result.content
        validation_result = guard.parse(raw_content)
        validated_content = validation_result.validated_output
        
        # Track guardrails validation with Langfuse
        trace_id = state.get("langfuse_trace_id")
        if trace_id:
            passed = (validated_content == raw_content)
            details = "Content validated successfully" if passed else "Content modified by guardrails"
            track_guardrails_validation(trace_id, current_asset, passed, details)
        
        if validated_content != raw_content:
            logger.info(f"Guardrails modified the content for {current_asset}")
            reasoning_addition = f"\nWriter: Generated {current_asset} (Guardrails applied fixes)"
        else:
            logger.info(f"Guardrails passed for {current_asset}")
            reasoning_addition = f"\nWriter: Generated {current_asset}"
            
    except Exception as e:
        logger.error(f"Guardrails error: {e}")
        validated_content = result.content # Fallback to original content
        reasoning_addition = f"\nWriter: Generated {current_asset} (Guardrails check failed: {str(e)})"

    new_drafts = drafts.copy()
    new_drafts[current_asset] = validated_content

    # ── Audience Variant Generation ───────────────────────────────────────────
    variant_drafts = (state.get("draft_variants") or {}).copy()
    primary_audience, variant_audience = _detect_audiences(current_asset, goal)
    try:
        variant_prompt = ChatPromptTemplate.from_template(WRITER_VARIANT_PROMPT)
        variant_chain = variant_prompt | get_llm(temperature=0.7)
        variant_result = variant_chain.invoke(
            {
                "asset_type": current_asset,
                "primary_audience": primary_audience,
                "variant_audience": variant_audience,
                "goal": goal,
                "primary_draft": validated_content,
            },
            config={"callbacks": callbacks},
        )
        variant_drafts[current_asset] = variant_result.content
        logger.info(f"Variant draft generated for '{current_asset}' → audience: {variant_audience}")
        reasoning_addition += f" + variant ({variant_audience})"
    except Exception as e:
        logger.warning(f"Variant generation failed for '{current_asset}': {e}")
        variant_drafts[current_asset] = ""

    return {
        "drafts": new_drafts,
        "draft_variants": variant_drafts,
        "current_asset": current_asset,
        "reasoning_trace": state.get("reasoning_trace", "") + reasoning_addition,
    }

def _detect_audiences(asset_name: str, goal: str) -> tuple[str, str]:
    """
    Infers primary and variant audience segments from the asset name / goal.
    Returns (primary_audience, variant_audience).
    """
    asset_lower = asset_name.lower()
    goal_lower = goal.lower()

    audience_map = [
        (["invest", "tfsa", "rrsp", "fhsa", "portfolio", "robo", "wealth builder"],
         "First-Time Investors & Canadians Aged 25–40", "Experienced Investors Optimising Returns"),
        (["trade", "commission", "stock", "etf", "self-directed", "brokerage", "tsx", "nyse"],
         "Self-Directed Investors & Active Traders", "First-Time Investors Exploring DIY Investing"),
        (["cash", "savings", "interest", "e-transfer", "chequing", "high-interest", "emergency fund"],
         "Everyday Canadians & Young Savers", "Millennials Building an Emergency Fund"),
        (["tax", "netfile", "cra", "t4", "t1", "filing", "return", "rrsp receipt"],
         "Canadians Filing Personal Tax Returns", "First-Time Filers & New Graduates"),
        (["first-time", "beginner", "new investor", "just starting", "no experience"],
         "First-Time Investors & Financial Newcomers", "Mid-Career Canadians Restarting Their Finances"),
        (["premium", "generation", "100k", "500k", "high net worth", "wealth management"],
         "Premium & Generation Tier Investors ($100k+)", "Aspiring Premium Investors Growing Wealth"),
        (["millennial", "gen z", "young professional", "25", "30", "35"],
         "Millennial & Gen Z Canadians", "Mid-Career Professionals Optimising Savings"),
        (["small business", "sole proprietor", "freelance", "self-employed", "corporate"],
         "Canadian Small Business Owners & Freelancers", "Salaried Professionals Seeking Tax Simplicity"),
    ]

    combined = asset_lower + " " + goal_lower
    for keywords, primary, variant in audience_map:
        if any(kw in combined for kw in keywords):
            return primary, variant

    return "Canadians Seeking Financial Freedom", "Young Professionals Planning for the Future"


def compliance_checker_node(state: AgentState) -> Dict:
    """
    Runs deterministic compliance checks on all current drafts.
    Sets compliance_flags and compliance_summary per asset.
    HIGH flags → summary = "BLOCK"; any flag → "WARN"; clean → "PASS".
    """
    logger.info("--- COMPLIANCE CHECKER ---")
    from src.tools import ComplianceCheckerTool
    import json as _json

    checker = ComplianceCheckerTool()
    drafts = state.get("drafts", {})

    all_flags: Dict[str, List[Dict]] = (state.get("compliance_flags") or {}).copy()
    all_summary: Dict[str, str] = (state.get("compliance_summary") or {}).copy()

    for asset, content in drafts.items():
        try:
            raw = checker.run({"asset_type": asset, "content": content})
            result = _json.loads(raw)
            flags = result.get("flags", [])
            has_high = any(f["severity"] == "HIGH" for f in flags)
            has_any = len(flags) > 0
            all_flags[asset] = flags
            all_summary[asset] = "BLOCK" if has_high else ("WARN" if has_any else "PASS")
            logger.info(f"Compliance [{asset}]: {all_summary[asset]} — {len(flags)} flag(s)")
        except Exception as e:
            logger.warning(f"Compliance check failed for '{asset}': {e}")
            all_flags[asset] = []
            all_summary[asset] = "PASS"

    return {
        "compliance_flags": all_flags,
        "compliance_summary": all_summary,
    }


def reviewer_node(state: AgentState) -> Dict:
    """
    Reviews drafts using LLM function calling.
    The LLM autonomously calls ContentQualityTool for each asset to get objective
    quality metrics, then issues a structured brand compliance verdict.
    """
    logger.info("--- REVIEWER (Function Calling) ---")
    drafts = state.get("drafts", {})
    guidelines = state.get("retrieved_docs", "Use standard professional tone.")

    langfuse_handler = get_langfuse_handler()
    callbacks = [langfuse_handler] if langfuse_handler else []

    from src.tools import ContentQualityTool
    quality_tool = ContentQualityTool()

    llm = get_llm(temperature=0)
    llm_with_tools = llm.bind_tools([quality_tool])

    critique_parts = []

    for asset, content in drafts.items():
        logger.info(f"Reviewing (function calling): {asset}")

        review_prompt = (
            f"You are a brand compliance officer for Wealthsimple.\n\n"
            f"Brand Guidelines (excerpt):\n{guidelines[:600]}\n\n"
            f"Asset Type: {asset}\n"
            f"Content:\n{content[:1500]}\n\n"
            f"Step 1: Call the content_quality_analyzer tool to get an objective quality report.\n"
            f"Step 2: Use the tool results + brand guidelines to write your final compliance verdict."
        )

        messages = [HumanMessage(content=review_prompt)]

        # Round 1 — LLM decides to call the tool
        ai_response = llm_with_tools.invoke(messages, config={"callbacks": callbacks})
        messages.append(ai_response)

        quality_report = ""
        if hasattr(ai_response, "tool_calls") and ai_response.tool_calls:
            for tool_call in ai_response.tool_calls:
                logger.info(f"LLM invoked function: {tool_call['name']} for '{asset}'")
                try:
                    tool_result = quality_tool.run(tool_call["args"])
                    quality_report = tool_result
                    messages.append(
                        ToolMessage(content=tool_result, tool_call_id=tool_call["id"])
                    )
                except Exception as e:
                    err_msg = f"Tool error: {e}"
                    messages.append(
                        ToolMessage(content=err_msg, tool_call_id=tool_call["id"])
                    )

            # Round 2 — LLM writes verdict using tool results
            final_response = llm.invoke(messages, config={"callbacks": callbacks})
            critique_parts.append(
                f"**{asset}**\n\n"
                f"*Quality Report (automated):*\n```\n{quality_report}\n```\n\n"
                f"*Brand Compliance Verdict:*\n{final_response.content}\n\n"
                f"{'─'*40}\n\n"
            )
        else:
            # LLM skipped the tool — fall back to direct prompt
            logger.warning(f"LLM did not call tool for '{asset}', using direct review.")
            prompt = ChatPromptTemplate.from_template(REVIEWER_PROMPT)
            chain = prompt | llm
            result = chain.invoke(
                {"guidelines": guidelines, "asset": asset, "content": content},
                config={"callbacks": callbacks},
            )
            critique_parts.append(f"**{asset} Review:**\n{result.content}\n\n{'─'*40}\n\n")

    return {"critique": "".join(critique_parts)}

def chitchat_node(state: AgentState) -> Dict:
    """Handles chitchat."""
    logger.info("--- CHITCHAT ---")
    llm = get_llm(temperature=0)
    result = llm.invoke(f"The user said: {state['goal']}. Respond politely.")
    return {"critique": result.content}

def clarification_node(state: AgentState) -> Dict:
    """Asks for clarification."""
    logger.info("--- CLARIFICATION ---")
    return {"critique": "Your request is a bit ambiguous. Could you please provide more details about your campaign goal?"}

def increment_retry_node(state: AgentState) -> Dict:
    """Increments the retry count."""
    return {"retry_count": state.get("retry_count", 0) + 1}

def query_rewriter_node(state: AgentState) -> Dict:
    """Rewrites the query to improve retrieval — stores in rewritten_query, not goal."""
    logger.info("--- QUERY REWRITER ---")
    goal = state.get("goal")
    current_asset = state.get("current_asset", "marketing assets")

    llm = get_llm(temperature=0)
    prompt = ChatPromptTemplate.from_template(QUERY_REWRITER_PROMPT)
    chain = prompt | llm

    result = chain.invoke({"goal": goal, "asset_type": current_asset})
    rewritten = result.content.strip()
    logger.info(f"Rewritten query: {rewritten}")

    return {
        "rewritten_query": rewritten,  # Preserve original goal; use this for next retrieval
        "retry_count": state.get("retry_count", 0) + 1,
    }

def feedback_processor_node(state: AgentState) -> Dict:
    """Processes user feedback and prepares for regeneration."""
    logger.info("--- FEEDBACK PROCESSOR ---")
    
    draft_status = state.get("draft_status", {})
    user_feedback = state.get("user_feedback", {})
    drafts = state.get("drafts", {})
    trace_id = state.get("langfuse_trace_id")
    
    # Track user feedback with Langfuse
    if trace_id:
        for asset, status in draft_status.items():
            feedback_text = user_feedback.get(asset, "")
            track_user_feedback(trace_id, asset, feedback_text, status)
    
    # Find assets that need revision
    assets_to_revise = [asset for asset, status in draft_status.items() if status == "needs_revision"]
    
    if assets_to_revise:
        logger.info(f"Assets requiring revision: {assets_to_revise}")
        # Remove drafts that need revision so they get regenerated
        new_drafts = drafts.copy()
        for asset in assets_to_revise:
            if asset in new_drafts:
                del new_drafts[asset]
        
        return {
            "drafts": new_drafts,
            "feedback_iteration": state.get("feedback_iteration", 0) + 1,
            "current_asset": assets_to_revise[0] if assets_to_revise else None
        }
    
    return {"feedback_iteration": state.get("feedback_iteration", 0)}


def publisher_node(state: AgentState) -> Dict:
    """Publishes drafts to Google Docs and schedules in Calendar."""
    logger.info("--- PUBLISHER ---")
    drafts = state.get("drafts", {})
    goal = state.get("goal")
    
    from src.google_utils import create_doc, add_calendar_event
    from datetime import datetime, timedelta
    
    results = {}
    for i, (asset, content) in enumerate(drafts.items()):
        logger.info(f"Publishing {asset}...")
        # 1. Create Google Doc
        doc_id, doc_url = create_doc(f"{asset} - {goal[:30]}", content)
        
        # 2. Schedule in Calendar (e.g., publish in i+1 days)
        publish_date = (datetime.now() + timedelta(days=i+1)).isoformat() + "Z"
        event_id = add_calendar_event(f"Publish {asset}", publish_date, f"Draft URL: {doc_url}")
        
        results[asset] = f"Doc: {doc_url} | Scheduled: {publish_date}"
        
    return {"publish_results": results}

# --- Routing Logic ---

def route_after_router(state: AgentState) -> str:
    intent = state.get("intent")
    if intent == "ChitChat":
        return "chitchat"
    elif intent == "ClarificationNeeded":
        return "clarification"
    else:
        return "planner"

def route_after_planner(state: AgentState) -> str:
    return "retriever"

def route_after_retriever(state: AgentState) -> str:
    return "retrieval_grader"

def route_after_retrieval_grade(state: AgentState) -> str:
    """Decides whether to proceed to writing or retry retrieval."""
    if state.get("retrieved_docs_relevant", False):
        return "writer"

    # Docs not relevant — try rewriting the query once before giving up
    if state.get("retry_count", 0) < 1:
        return "query_rewriter"
    return "writer"  # Proceed anyway after one retry

def route_after_writer(state: AgentState) -> str:
    return "compliance_checker"

def route_after_hallucination_grade(state: AgentState) -> str:
    """Decides whether to retry generation or move to the next asset/reviewer."""
    if not state.get("generation_grounded", True):
        # Generation hallucinated — retry retrieval once with query rewriting
        if state.get("retry_count", 0) < 1:
            return "query_rewriter"

    # Check if all assets in the plan have been drafted
    plan = state.get("plan", [])
    drafts = state.get("drafts", {})
    if len(drafts) < len(plan):
        return "retriever"  # More assets to draft
    return "feedback_processor"

def route_after_feedback(state: AgentState) -> str:
    """Decides whether to regenerate drafts based on feedback or proceed to reviewer."""
    draft_status = state.get("draft_status", {})
    
    # Check if any drafts need revision
    needs_revision = any(status == "needs_revision" for status in draft_status.values())
    
    if needs_revision:
        logger.info("User requested revisions, regenerating drafts...")
        return "retriever"  # Start regeneration from retrieval
    
    # All drafts approved, proceed to reviewer
    logger.info("All drafts approved, proceeding to review...")
    return "reviewer"

def brand_review_gate_node(state: AgentState) -> Dict:
    """
    HITL gate after brand compliance reviewer.
    The graph pauses BEFORE this node so the UI can show the brand review critique
    and collect the user's decision (accept or revise).
    Routing is determined by compliance_revision_requested set via update_state from the UI.
    """
    logger.info("--- BRAND REVIEW GATE ---")
    return {}  # Pure pass-through; routing reads state set by the UI


def route_after_brand_review_gate(state: AgentState) -> str:
    """Routes to feedback loop if user requested revisions, otherwise proceeds to publisher."""
    if state.get("compliance_revision_requested", False):
        logger.info("Brand review: revision requested → routing to feedback_processor")
        return "feedback_processor"
    logger.info("Brand review: accepted → routing to publisher")
    return "publisher"


# --- Graph Construction ---

def create_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("router", router_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("compliance_checker", compliance_checker_node)
    workflow.add_node("retrieval_grader", retrieval_grader)
    workflow.add_node("hallucination_grader", hallucination_grader)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("brand_review_gate", brand_review_gate_node)
    workflow.add_node("publisher", publisher_node)
    workflow.add_node("chitchat", chitchat_node)
    workflow.add_node("clarification", clarification_node)
    workflow.add_node("query_rewriter", query_rewriter_node)
    workflow.add_node("feedback_processor", feedback_processor_node)
    
    workflow.set_entry_point("router")
    
    workflow.add_conditional_edges(
        "router",
        route_after_router,
        {
            "planner": "planner",
            "chitchat": "chitchat",
            "clarification": "clarification"
        }
    )
    
    workflow.add_edge("planner", "retriever")
    workflow.add_edge("retriever", "retrieval_grader")
    
    workflow.add_conditional_edges(
        "retrieval_grader",
        route_after_retrieval_grade,
        {
            "query_rewriter": "query_rewriter",
            "writer": "writer"
        }
    )
    
    workflow.add_edge("query_rewriter", "retriever")
    workflow.add_edge("writer", "compliance_checker")
    workflow.add_edge("compliance_checker", "hallucination_grader")
    
    workflow.add_conditional_edges(
        "hallucination_grader",
        route_after_hallucination_grade,
        {
            "query_rewriter": "query_rewriter",
            "retriever": "retriever",
            "feedback_processor": "feedback_processor"
        }
    )
    
    # Feedback loop edges
    workflow.add_conditional_edges(
        "feedback_processor",
        route_after_feedback,
        {
            "retriever": "retriever",
            "reviewer": "reviewer"
        }
    )
    
    workflow.add_edge("reviewer", "brand_review_gate")
    workflow.add_conditional_edges(
        "brand_review_gate",
        route_after_brand_review_gate,
        {
            "feedback_processor": "feedback_processor",
            "publisher": "publisher",
        }
    )
    workflow.add_edge("publisher", END)
    workflow.add_edge("chitchat", END)
    workflow.add_edge("clarification", END)
    
    memory = MemorySaver()
    return workflow.compile(
        checkpointer=memory,
        interrupt_after=["planner"],                                          # Pause after planner → plan approval
        interrupt_before=["feedback_processor", "brand_review_gate", "publisher"],  # Draft review, compliance review, publish auth
    )
