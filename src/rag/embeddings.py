from langchain_huggingface import HuggingFaceEmbeddings

def get_embedding_function(model_name: str = "all-MiniLM-L6-v2"):
    """
    Returns the embedding function.
    """
    return HuggingFaceEmbeddings(model_name=model_name)
