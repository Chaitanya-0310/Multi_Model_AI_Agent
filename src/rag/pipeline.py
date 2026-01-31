from .loader import load_documents
from .splitter import split_documents
from .embeddings import get_embedding_function
from .vector_store import create_vector_store, get_retriever

# Directory where the vector store will be persisted
PERSIST_DIRECTORY = "./chroma_db"

def ingest_docs(data_dir: str = "./data"):
    """
    Ingests text files from the data directory into a local Chroma vector store.
    """
    # 1. Load documents
    documents = load_documents(data_dir)
    
    if not documents:
        print("No documents found to ingest.")
        return

    # 2. Split documents
    docs = split_documents(documents)

    # 3. Initialize Embeddings
    embedding_function = get_embedding_function()

    # 4. Create and persist vector store
    create_vector_store(docs, embedding_function, PERSIST_DIRECTORY)
    print(f"Ingested {len(docs)} document chunks into {PERSIST_DIRECTORY}.")

def retrieve_context(query: str, k: int = 3) -> str:
    """
    Retrieves relevant context from the vector store based on the query.
    """
    embedding_function = get_embedding_function()
    retriever = get_retriever(PERSIST_DIRECTORY, embedding_function, k)
    
    if retriever is None:
        return "No knowledge base found. Please run ingestion."

    docs = retriever.invoke(query)
    
    return "\n\n".join([doc.page_content for doc in docs])
