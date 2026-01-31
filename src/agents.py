from typing import TypedDict, List, Annotated, Dict, Optional, Literal
import os
import operator
import logging
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
import guardrails as gd
from guardrails.validators import Validator, register_validator, PassResult, FailResult

from src.config import (
    DEFAULT_MODEL,
    ROUTER_PROMPT,
    PLANNER_PROMPT,
    WRITER_PROMPT,
    REVIEWER_PROMPT,
    RETRIEVAL_GRADER_PROMPT,
    HALLUCINATION_GRADER_PROMPT
)
from src.tools import get_tools

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
    user_feedback: Dict[str, str]  # Stores user feedback for each asset
    draft_status: Dict[str, str]  # Tracks approval: "approved", "needs_revision", "pending"
    feedback_iteration: int  # Counts regeneration attempts

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
    
    llm = ChatGoogleGenerativeAI(model=DEFAULT_MODEL, temperature=0)
    structured_llm = llm.with_structured_output(RouterOutput)
    
    prompt = ChatPromptTemplate.from_template(ROUTER_PROMPT)
    chain = prompt | structured_llm
    
    logger.info(f"Input Goal: {goal}")
    result = chain.invoke({"goal": goal})
    logger.info(f"Detected Intent: {result.intent}")
    
    return {
        "intent": result.intent,
        "reasoning_trace": f"Router Reasoning: {result.reasoning}"
    }

# --- Grader Nodes ---

def retrieval_grader(state: AgentState) -> Dict:
    """Grades if the retrieved documents are relevant to the question."""
    logger.info("--- RETRIEVAL GRADER ---")
    question = state.get("goal")
    docs = state.get("retrieved_docs")
    
    llm = ChatGoogleGenerativeAI(model=DEFAULT_MODEL, temperature=0)
    structured_llm = llm.with_structured_output(GradeRetrieval)
    
    prompt = ChatPromptTemplate.from_template(RETRIEVAL_GRADER_PROMPT)
    chain = prompt | structured_llm
    
    result = chain.invoke({"question": question, "document": docs})
    logger.info(f"Retrieval Relevance: {result.binary_score}")
    
    return {"reasoning_trace": state.get("reasoning_trace", "") + f"\nRetrieval Grade: {result.binary_score}"}

def hallucination_grader(state: AgentState) -> Dict:
    """Grades if the generated answer is grounded in the retrieved documents."""
    logger.info("--- HALLUCINATION GRADER ---")
    docs = state.get("retrieved_docs")
    # In this simplified version, we grade the most recently added draft
    current_asset = state.get("current_asset")
    generation = state.get("drafts", {}).get(current_asset, "")
    
    llm = ChatGoogleGenerativeAI(model=DEFAULT_MODEL, temperature=0)
    structured_llm = llm.with_structured_output(GradeHallucination)
    
    prompt = ChatPromptTemplate.from_template(HALLUCINATION_GRADER_PROMPT)
    chain = prompt | structured_llm
    
    result = chain.invoke({"documents": docs, "generation": generation})
    logger.info(f"Hallucination Grade: {result.binary_score}")
    
    return {"reasoning_trace": state.get("reasoning_trace", "") + f"\nHallucination Grade: {result.binary_score}"}

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
    """Generates a marketing plan."""
    logger.info("--- PLANNER ---")
    goal = state.get("goal")
    
    llm = ChatGoogleGenerativeAI(model=DEFAULT_MODEL, temperature=0)
    structured_llm = llm.with_structured_output(Plan)
    
    prompt = ChatPromptTemplate.from_template(PLANNER_PROMPT)
    chain = prompt | structured_llm
    
    logger.info(f"LLM Input: {goal}")
    result = chain.invoke({"goal": goal})
    logger.info(f"LLM Output (Plan): {result.steps}")
    
    return {
        "plan": result.steps,
        "reasoning_trace": state.get("reasoning_trace", "") + f"\nPlanner Reasoning: {result.reasoning}"
    }

def retriever_node(state: AgentState) -> Dict:
    """Retrieves context using the retriever tool."""
    logger.info("--- RETRIEVER ---")
    goal = state.get("goal")
    
    # Decide which asset we are retrieving for if not set
    plan = state.get("plan", [])
    drafts = state.get("drafts", {})
    current_asset = None
    for asset in plan:
        if asset not in drafts:
            current_asset = asset
            break
    
    if not current_asset:
        current_asset = "general marketing assets"

    # Reset retry count if we are on a new asset
    retry_count = state.get("retry_count", 0)
    if state.get("current_asset") != current_asset:
        retry_count = 0

    tools = get_tools()
    retriever_tool = next(t for t in tools if t.name == "knowledge_base_retriever")
    
    query = f"{current_asset} related to {goal}"
    logger.info(f"Tool Call (Retriever) Arguments: {query}")
    
    context = retriever_tool.run(query)
    logger.info(f"Tool Output (Retriever): {context[:200]}...") # Log first 200 chars
    
    return {
        "retrieved_docs": context, 
        "current_asset": current_asset,
        "retry_count": retry_count
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

    llm = ChatGoogleGenerativeAI(model=DEFAULT_MODEL, temperature=0)
    
    # Check if there's user feedback for this asset (regeneration case)
    feedback_text = user_feedback.get(current_asset, "")
    if feedback_text:
        logger.info(f"Regenerating {current_asset} with user feedback: {feedback_text}")
        enhanced_prompt = WRITER_PROMPT + "\n\nIMPORTANT: The user provided the following feedback on the previous draft. Please incorporate this feedback:\n{feedback}"
        prompt = ChatPromptTemplate.from_template(enhanced_prompt)
        chain = prompt | llm
        result = chain.invoke({
            "asset_type": current_asset, 
            "context": context, 
            "goal": goal,
            "feedback": feedback_text
        })
    else:
        prompt = ChatPromptTemplate.from_template(WRITER_PROMPT)
        chain = prompt | llm
        logger.info(f"Writing asset: {current_asset}")
        logger.info(f"LLM Input (Writer): Goal={goal}, Asset={current_asset}, Context Length={len(context)}")
        result = chain.invoke({"asset_type": current_asset, "context": context, "goal": goal})
    logger.info(f"LLM Output (Writer): {result.content[:200]}...")
    
    # --- Guardrails Integration ---
    logger.info(f"--- GUARDRAILS CHECK for {current_asset} ---")
    
    # Initialize Guard with validators
    # For demonstration, we use our custom CompetitorCheck
    guard = gd.Guard().use(
        CompetitorCheck(competitors=["CompetitorX", "OtherBrand"], on_fail="fix")
    )
    
    try:
        # Validate the generated content
        raw_content = result.content
        validation_result = guard.parse(raw_content)
        validated_content = validation_result.validated_output
        
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
    
    return {
        "drafts": new_drafts,
        "current_asset": current_asset,
        "reasoning_trace": state.get("reasoning_trace", "") + reasoning_addition
    }

def reviewer_node(state: AgentState) -> Dict:
    """Reviews drafts against brand guidelines."""
    logger.info("--- REVIEWER ---")
    drafts = state.get("drafts", {})
    guidelines = state.get("retrieved_docs", "Use standard professional tone.")
    
    llm = ChatGoogleGenerativeAI(model=DEFAULT_MODEL, temperature=0)
    prompt = ChatPromptTemplate.from_template(REVIEWER_PROMPT)
    chain = prompt | llm
    
    critique = ""
    for asset, content in drafts.items():
        logger.info(f"Reviewing asset: {asset}")
        result = chain.invoke({"guidelines": guidelines, "asset": asset, "content": content})
        critique += f"**{asset} Review:**\n{result.content}\n\n"
        
    return {"critique": critique}

def chitchat_node(state: AgentState) -> Dict:
    """Handles chitchat."""
    logger.info("--- CHITCHAT ---")
    llm = ChatGoogleGenerativeAI(model=DEFAULT_MODEL, temperature=0)
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
    """Rewrites the query to improve retrieval."""
    logger.info("--- QUERY REWRITER ---")
    goal = state.get("goal")
    current_asset = state.get("current_asset", "marketing assets")
    
    llm = ChatGoogleGenerativeAI(model=DEFAULT_MODEL, temperature=0)
    result = llm.invoke(f"Rewrite the following marketing goal into a better search query for a vector database. Goal: {goal}, Asset: {current_asset}")
    
    return {
        "goal": result.content, # Update goal with rewritten query for next retrieval
        "retry_count": state.get("retry_count", 0) + 1
    }

def feedback_processor_node(state: AgentState) -> Dict:
    """Processes user feedback and prepares for regeneration."""
    logger.info("--- FEEDBACK PROCESSOR ---")
    
    draft_status = state.get("draft_status", {})
    user_feedback = state.get("user_feedback", {})
    drafts = state.get("drafts", {})
    
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
    if "Retrieval Grade: yes" in state.get("reasoning_trace", ""):
        return "writer"
    
    if state.get("retry_count", 0) < 1:
        return "query_rewriter"
    return "writer"

def route_after_writer(state: AgentState) -> str:
    return "hallucination_grader"

def route_after_hallucination_grade(state: AgentState) -> str:
    """Decides whether to retry generation or move to the next asset/reviewer."""
    if "Hallucination Grade: no" in state.get("reasoning_trace", ""):
        if state.get("retry_count", 0) < 1:
            return "query_rewriter" # Retry from retrieval/rewriting
    
    # Check if all assets are done
    plan = state.get("plan", [])
    drafts = state.get("drafts", {})
    if len(drafts) < len(plan):
        return "retriever" # Go back to retrieve for next asset
    return "feedback_processor"  # Changed from "reviewer" to include feedback loop

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

# --- Graph Construction ---

def create_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("router", router_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("retriever", retriever_node)
    workflow.add_node("writer", writer_node)
    workflow.add_node("retrieval_grader", retrieval_grader)
    workflow.add_node("hallucination_grader", hallucination_grader)
    workflow.add_node("reviewer", reviewer_node)
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
    workflow.add_edge("writer", "hallucination_grader")
    
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
    
    workflow.add_edge("reviewer", "publisher")
    workflow.add_edge("publisher", END)
    workflow.add_edge("chitchat", END)
    workflow.add_edge("clarification", END)
    
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory, interrupt_before=["retriever", "feedback_processor", "publisher"])
