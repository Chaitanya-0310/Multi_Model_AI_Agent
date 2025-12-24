from typing import TypedDict, List, Annotated
import os
import operator
import time
from langchain_core.messages import BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from src.rag import retrieve_context
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

load_dotenv() 


# --- State Definition ---

# 2. Now initialize the model

class AgentState(TypedDict):
    goal: str
    plan: List[str]
    drafts: dict
    critique: str
    messages: Annotated[List[BaseMessage], operator.add]

# --- Planner Node ---
class Plan(BaseModel):
    """List of assets to create."""
    steps: List[str] = Field(description="List of marketing assets to generate (e.g., 'Email', 'LinkedIn Post').")

def planner(state: AgentState):
    """
    Decides what marketing assets to create based on the goal.
    """
    print("--- PLANNER ---")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)
    goal = state['goal']
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a senior marketing strategist. Given a campaign goal, list the key 3-5 assets needed."),
        ("user", "{goal}")
    ])
    
    planner_llm = llm.with_structured_output(Plan)
    chain = prompt | planner_llm
    
    result = chain.invoke({"goal": goal})
    
    return {"plan": result.steps}

# --- Writer Node ---
def writer(state: AgentState):
    """
    Generates content for each step in the plan using RAG.
    """
    print("--- WRITER ---")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)
    plan = state['plan']
    goal = state['goal']
    drafts = {}
    
    for step in plan:
        context = retrieve_context(f"{step} related to {goal}")
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a marketing copywriter. Write a {asset_type} for this goal. Use the following context/guidelines:\n\n{context}"),
            ("user", "Goal: {goal}\nAsset Type: {asset_type}")
        ])
        
        chain = prompt | llm
        result = chain.invoke({"asset_type": step, "context": context, "goal": goal})
        drafts[step] = result.content
        
    return {"drafts": drafts}

# --- Reviewer Node ---
def reviewer(state: AgentState):
    """
    Reviews the drafts against brand guidelines.
    """
    print("--- REVIEWER ---")
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)
    drafts = state['drafts']
    critique = ""
    
    guidelines = retrieve_context("Brand Tone and Forbidden Words")
    
    for asset, content in drafts.items():
        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a brand compliance officer. Review the text below against these guidelines:\n\n{guidelines}\n\nProvide a brief pass/fail and feedback."),
            ("user", "Asset: {asset}\nContent:\n{content}")
        ])
        
        chain = prompt | llm
        result = chain.invoke({"guidelines": guidelines, "asset": asset, "content": content})
        critique += f"**{asset} Review:**\n{result.content}\n\n"
        
    return {"critique": critique}

# --- Graph Construction ---
def create_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("planner", planner)
    workflow.add_node("writer", writer)
    workflow.add_node("reviewer", reviewer)
    
    workflow.set_entry_point("planner")
    
    workflow.add_edge("planner", "writer")
    workflow.add_edge("writer", "reviewer")
    workflow.add_edge("reviewer", END)
    
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory, interrupt_before=["reviewer"])