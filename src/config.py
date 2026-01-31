# src/config.py

# Model Configurations
DEFAULT_MODEL = "gemini-2.5-flash"
EMBEDDING_MODEL = "embedding-001"

# Intent Classification Categories
INTENT_CATEGORIES = ["Factual", "Analytical", "ChitChat", "ClarificationNeeded"]

# Prompts
ROUTER_PROMPT = """You are an expert router. Classify the user query into one of the following categories:
- Factual: Queries that require specific facts or data retrieval.
- Analytical: Queries that require analysis, comparisons, or strategic thinking.
- ChitChat: General conversation, greetings, or non-business related queries.
- ClarificationNeeded: Queries that are ambiguous or lack enough information to proceed.

User Query: {goal}
"""

PLANNER_PROMPT = """You are a senior marketing strategist. Given a campaign goal, list the key 3-5 assets needed.
Your output should include your reasoning in the scratchpad before providing the structured plan.

Scratchpad: (Think about the target audience, channels, and objective)

Goal: {goal}
"""

WRITER_PROMPT = """You are a marketing copywriter. Write a {asset_type} for this goal.
Use the following context/guidelines:
{context}

Reasoning Trace: (Think about the tone, key message, and call to action based on the context)

Goal: {goal}
Asset Type: {asset_type}
"""

REVIEWER_PROMPT = """You are a brand compliance officer. Review the text below against these guidelines:
{guidelines}

Reasoning Trace: (Analyze the text for tone, forbidden words, and alignment with guidelines)

Asset: {asset}
Content: {content}
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

# Tool Docstrings
RETRIEVER_TOOL_DESCRIPTION = "Use this tool ONLY to retrieve marketing guidelines, product information, and brand history from the knowledge base."
