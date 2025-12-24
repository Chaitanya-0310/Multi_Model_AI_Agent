# RAG Architecture & Flow

This document details the architecture of the Retrieval-Augmented Generation (RAG) system used in the Marketing Campaign Orchestrator.

## 1. High-Level System Architecture

The system consists of three main layers:
1.  **Frontend**: Streamlit UI for user interaction.
2.  **Orchestration**: LangGraph managing the state and agent workflow.
3.  **RAG Engine**: Handles document ingestion, embedding, and retrieval.

```mermaid
graph TD
    subgraph Frontend
        UI[Streamlit UI]
    end

    subgraph Agents [LangGraph Agents]
        Planner[Planner Agent]
        Writer[Writer Agent]
        Reviewer[Reviewer Agent]
    end

    subgraph RAG [RAG Engine]
        Ingest[Ingestion Pipeline]
        VectorDB[(Chroma Vector Store)]
        Retriever[Retriever]
    end

    subgraph External
        Google[Google Gemini 1.5 Flash]
        HF[HuggingFace Embeddings]
    end

    UI -->|Campaign Goal| Planner
    UI -->|Trigger Re-ingest| Ingest
    
    Planner -->|Plan| Writer
    Writer -->|Drafts| Reviewer
    Reviewer -->|Critique| UI

    Writer <-->|Query/Context| Retriever
    Reviewer <-->|Query/Context| Retriever
    
    Ingest -->|Text Chunks| VectorDB
    Retriever <-->|Similarity Search| VectorDB
    
    Agents -.->|Generation| Google
    RAG -.->|Embeddings| HF
```

## 2. RAG Data Flow

The RAG process is split into two distinct flows: Ingestion (Offline/Setup) and Inference (Runtime).

### A. Ingestion Flow (Knowledge Base Creation)
This process loads raw text data and converts it into a machine-searchable vector format.

1.  **Load**: `DirectoryLoader` reads `*.txt` files from `./data`.
2.  **Split**: `CharacterTextSplitter` chunks text (size: 1000, overlap: 0).
3.  **Embed**: `all-MiniLM-L6-v2` converts chunks into vector embeddings.
4.  **Store**: Vectors are saved locally to `./chroma_db`.

```mermaid
flowchart LR
    Docs[Text Files ./data] -->|DirectoryLoader| RawText
    RawText -->|CharacterTextSplitter| Chunks[Text Chunks]
    Chunks -->|HuggingFace Embeddings| Vectors
    Vectors -->|Persist| DB[(Chroma DB ./chroma_db)]
```

### B. Inference Flow (Agentic Execution)
How agents use the RAG system to generate content.

```mermaid
sequenceDiagram
    participant Agent as Writer/Reviewer Agent
    participant Rag as RAG Module
    participant DB as Chroma DB
    participant LLM as Gemini 1.5 Flash

    Note over Agent: Need context for "Email"
    Agent->>Rag: retrieve_context("Email related to [Goal]")
    Rag->>DB: Similarity Search (Top 3)
    DB-->>Rag: Relevant Document Chunks
    Rag-->>Agent: Concatenated Text Context
    
    Note over Agent: Construct Prompt
    Agent->>Agent: Prompt = Context + Goal + Instructions
    
    Agent->>LLM: Generate Content
    LLM-->>Agent: Draft Content
```

## 3. Technology Stack

| Component | Technology | Implementation |
| :--- | :--- | :--- |
| **LLM** | Google Gemini | `gemini-1.5-flash` |
| **Embeddings** | Hugging Face | `all-MiniLM-L6-v2` |
| **Vector Store** | ChromaDB | Local Persistence (`./chroma_db`) |
| **Orchestrator** | LangGraph | StateGraph with Checkpointing |
| **Framework** | LangChain | `langchain_google_genai`, `langchain_chroma` |
