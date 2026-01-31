from langchain_text_splitters import CharacterTextSplitter

def split_documents(documents, chunk_size: int = 1000, chunk_overlap: int = 200):
    """
    Splits documents into chunks.
    """
    text_splitter = CharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return text_splitter.split_documents(documents)
