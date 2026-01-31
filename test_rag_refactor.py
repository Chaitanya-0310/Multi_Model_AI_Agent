import sys
import os

# Ensure we can import from src
sys.path.append(os.getcwd())

try:
    from src.rag import ingest_docs, retrieve_context
    print("SUCCESS: Successfully imported 'ingest_docs' and 'retrieve_context' from 'src.rag'")
    print(f"ingest_docs location: {ingest_docs}")
    print(f"retrieve_context location: {retrieve_context}")
except Exception as e:
    print(f"FAILURE: Could not import from 'src.rag': {e}")
