import os
from langchain_chroma import Chroma

def create_vector_store(docs, embedding_function, persist_directory: str):
    """
    Creates and persists a Chroma vector store.
    """
    return Chroma.from_documents(
        documents=docs,
        embedding=embedding_function,
        persist_directory=persist_directory
    )

def get_retriever(persist_directory: str, embedding_function, k: int = 3):
    """
    Returns a retriever from an existing Chroma vector store.
    """
    if not os.path.exists(persist_directory):
        return None
        
    db = Chroma(persist_directory=persist_directory, embedding_function=embedding_function)
    return db.as_retriever(search_kwargs={"k": k})
