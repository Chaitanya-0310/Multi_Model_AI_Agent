import os
from langchain_community.document_loaders import DirectoryLoader, TextLoader

def load_documents(data_dir: str):
    """
    Loads text files from the specified directory.
    """
    if not os.path.exists(data_dir):
        raise FileNotFoundError(f"Data directory '{data_dir}' not found.")

    loader = DirectoryLoader(data_dir, glob="**/*.txt", loader_cls=TextLoader)
    documents = loader.load()
    return documents
