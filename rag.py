import os
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Define paths relative to the execution root (usually where app.py is run)
DATA_PATH = os.path.join(os.getcwd(), "data")
DB_PATH = os.path.join(os.getcwd(), "chroma_db")

def ingest_docs():
    """
    Loads text files from data/, splits them, and stores embeddings in ChromaDB.
    """
    if not os.path.exists(DATA_PATH):
        os.makedirs(DATA_PATH)
        print(f"Created data directory at {DATA_PATH}. Please add .txt files.")
        return

    # 1. Load Documents
    loader = DirectoryLoader(DATA_PATH, glob="*.txt", loader_cls=TextLoader)
    docs = loader.load()
    
    if not docs:
        print("No documents found to ingest.")
        return

    # 2. Split Text
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    splits = text_splitter.split_documents(docs)
    
    # 3. Store in Vector DB
    # persist_directory ensures data is saved to disk
    Chroma.from_documents(
        documents=splits, 
        embedding=GoogleGenerativeAIEmbeddings(model="embedding-001"), 
        persist_directory=DB_PATH
    )
    print(f"Successfully ingested {len(splits)} chunks into {DB_PATH}.")

def retrieve_context(query: str) -> str:
    """
    Retrieves the top 3 most relevant document chunks for a given query.
    """
    embedding_function = GoogleGenerativeAIEmbeddings(model="embedding-001")
    vectorstore = Chroma(persist_directory=DB_PATH, embedding_function=embedding_function)
    
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    docs = retriever.invoke(query)
    
    # Combine content into a single string
    return "\n\n".join([d.page_content for d in docs])