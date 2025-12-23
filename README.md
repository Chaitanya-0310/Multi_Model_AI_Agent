# 🚀 Marketing Campaign Orchestrator
An intelligent, agentic AI application that automates the creation of marketing campaigns. It uses **LangGraph** to orchestrate a team of AI agents that plan, write, and review marketing assets, grounded in your company's knowledge base using **RAG** (Retrieval-Augmented Generation).
## ✨ Features
*   **Strategic Planning:** Automatically determines the best assets (emails, posts, blogs) for your campaign goal.
*   **RAG-Powered Drafting:** Writes content using your actual product documentation and brand history.
*   **Brand Compliance:** A dedicated agent reviews all content against your brand guidelines to ensure consistency.
*   **Interactive UI:** Built with **Streamlit** for easy interaction and configuration.
## 🛠️ Architecture
The system is built on a **StateGraph** workflow:
1.  **User Input:** Defines the campaign goal.
2.  **Planner Agent:** Decides what to build.
3.  **Writer Agent:** Generates drafts using RAG.
4.  **Reviewer Agent:** Critiques drafts against brand rules.
See [agents.md](./agents.md) for detailed agent specifications.
## 📂 Project Structure
*   `app.py`: Main Streamlit application entry point.
*   `src/agents.py`: Definitions of the Planner, Writer, and Reviewer agents and the LangGraph workflow.
*   `src/rag.py`: RAG implementation (Ingestion and Retrieval) using ChromaDB and OpenAI Embeddings.
*   `data/`: Directory for knowledge base text files (brand guidelines, product docs).
*   `requirements.txt`: Python dependencies.
## 🚀 Getting Started
### Prerequisites
*   Python 3.10+
*   OpenAI API Key
### Installation
1.  **Clone the repository** (if applicable).
2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Set up Knowledge Base:**
    *   Place your text documents (e.g., `brand_guidelines.txt`, `product_info.txt`) inside the `data/` folder.
### Running the App
1.  **Start the Streamlit server:**
    ```bash
    streamlit run app.py
    ```
2.  **Configure:**
    *   Enter your OpenAI API Key in the sidebar.
    *   Click **"Re-ingest Knowledge Base"** to load your documents into the vector store.
3.  **Run a Campaign:**
    *   Enter a goal (e.g., *"Promote our new eco-friendly sneaker launch on Instagram"*).
    *   Click **"Run Campaign"**.
## 🧩 Technologies
*   **LangChain & LangGraph**: Agent orchestration.
*   **Streamlit**: User Interface.
*   **ChromaDB**: Vector Database for RAG.

*   **OpenAI**: LLM (GPT-3.5) and Embeddings.

## Screenshots
<img width="1893" height="869" alt="Screenshot 2025-12-23 143253" src="https://github.com/user-attachments/assets/d34ec154-3437-4079-a46d-e4dc85fdc782" />
<img width="1864" height="838" alt="Screenshot 2025-12-23 143300" src="https://github.com/user-attachments/assets/8d6a8bf8-08c9-46d7-8238-02043cea7a26" />
<img width="1868" height="876" alt="Screenshot 2025-12-23 143449" src="https://github.com/user-attachments/assets/49a12976-5e9c-4882-a710-1c7bc354c835" />
<img width="1883" height="868" alt="Screenshot 2025-12-23 143458" src="https://github.com/user-attachments/assets/b45b89f5-1aa1-4de0-ba5f-9af9b5e8f16d" />
<img width="1488" height="448" alt="Screenshot 2025-12-23 143634" src="https://github.com/user-attachments/assets/8e5ca0d2-f3bd-4f4e-bba8-81a4e5da7f46" />
