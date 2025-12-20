# 🤖 AI Agents Documentation
This document explicitly details the AI agents orchestrating the **Marketing Campaign** workflow.
## 1. Planner Agent (Strategist)
*   **Role:** Senior Marketing Strategist
*   **Responsibility:** Analyzes the user's high-level campaign goal and determines the optimal mix of marketing assets to produce.
*   **Input:** User-provided campaign goal (e.g., "Launch a Q3 awareness campaign...").
*   **Output:** A structured list of 3-5 specific marketing assets (e.g., "Email Sequence", "LinkedIn Post", "Landing Page Copy").
*   **Mechanism:** Uses `gpt-3.5-turbo` with structured output to ensure a valid JSON list of steps.
## 2. Writer Agent (Copywriter)
*   **Role:** Marketing Copywriter
*   **Responsibility:** Drafts the actual content for each asset identified by the Planner.
*   **Tool Usage:**
    *   **RAG (Retrieval-Augmented Generation):** Queries the knowledge base for context relevant to the specific asset and goal (e.g., product specs, past successful campaigns).
*   **Input:** Campaign Goal, Specific Asset Type, Retrieved Context.
*   **Output:** A complete draft of the marketing asset.
*   **Mechanism:** Iterates through the plan (sequentially for this MVP) and generates content for each item using `gpt-3.5-turbo`.
## 3. Reviewer Agent (Compliance)
*   **Role:** Brand Compliance Officer
*   **Responsibility:** Critiques the generated drafts to ensure they align with the company's brand voice and avoid forbidden terms.
*   **Tool Usage:**
    *   **RAG:** Specifically retrieves "Brand Tone and Forbidden Words" from the knowledge base.
*   **Input:** Generated Drafts, Retrieved Brand Guidelines.
*   **Output:** A pass/fail assessment and specific feedback for each asset.
*   **Mechanism:** Uses `gpt-3.5-turbo` to compare the content against strict brand guidelines.
## 🕸️ Agentic Workflow (LangGraph)
The agents are connected via a `StateGraph`:
1.  **Entry Point:** `Planner` receives the goal.
2.  **Planner -> Writer:** The plan is passed to the writer.
3.  **Writer -> Reviewer:** Drafts are passed to the reviewer.
4.  **Reviewer -> End:** The final critique is generated and the flow terminates.