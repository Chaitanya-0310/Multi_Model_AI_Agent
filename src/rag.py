import os
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# Directory where the vector store will be persisted
PERSIST_DIRECTORY = "./chroma_db"

def ingest_docs(data_dir: str = "./data"):
    """
    Ingests text files from the data directory into a local Chroma vector store.
    """
    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"Data directory '{data_dir}' not found.")

    # Load documents
    loader = DirectoryLoader(data_dir, glob="**/*.txt", loader_cls=TextLoader)
    documents = loader.load()

    if not documents:
        print("No documents found to ingest.")
        return

    # Split documents into chunks
    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
    docs = text_splitter.split_documents(documents)

    # Initialize Embeddings
    embedding_function = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    # Create and persist vector store
    # Note: Chroma will automatically persist if persist_directory is set
    Chroma.from_documents(
        documents=docs,
        embedding=embedding_function,
        persist_directory=PERSIST_DIRECTORY
    )
    print(f"Ingested {len(docs)} document chunks into {PERSIST_DIRECTORY}.")

def retrieve_context(query: str, k: int = 3) -> str:
    """
    Retrieves relevant context from the vector store based on the query.
    """
    if not os.path.exists(PERSIST_DIRECTORY):
        return "No knowledge base found. Please run ingestion."

    embedding_function = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    db = Chroma(persist_directory=PERSIST_DIRECTORY, embedding_function=embedding_function)
    
    retriever = db.as_retriever(search_kwargs={"k": k})
    docs = retriever.invoke(query)
    
    return "\n\n".join([doc.page_content for doc in docs])

if __name__ == "__main__":
    # If run as a script, perform ingestion
    try:
        ingest_docs()
    except Exception as e:
        print(f"Error during ingestion: {e}")
