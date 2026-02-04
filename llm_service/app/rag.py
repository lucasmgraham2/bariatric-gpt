import chromadb
import os
import glob
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Initialize persistent client in the llm_service directory
DB_DIR = os.path.join(os.path.dirname(__file__), "../chroma_db")
KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "../knowledge")

_client = None
_collection = None

def get_collection():
    global _client, _collection
    if _collection:
        return _collection
    
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
        
    _client = chromadb.PersistentClient(path=DB_DIR)
    
    # Get or create collection
    _collection = _client.get_or_create_collection(name="bariatric_knowledge")
    
    # Warn if empty but don't auto-ingest (handled by build_knowledge.py now)
    if _collection.count() == 0:
        print("--- RAG WARNING: Database is empty. Run 'python app/build_knowledge.py' to populate. ---")
        
    return _collection

def query_knowledge(text: str, n_results: int = 5) -> str:
    """Retreives top N relevant context strings."""
    try:
        col = get_collection()
        results = col.query(query_texts=[text], n_results=n_results)
        
        if not results['documents']:
            return ""

        print(f"--- RAG RETRIEVED: {len(results['documents'][0])} chunks for query '{text}' ---")
        
        if not results['documents']:
            return ""
            
        # Flatten list of lists
        docs = results['documents'][0]
        return "\n\n".join(docs)
    except Exception as e:
        print(f"--- RAG Query Failed: {e} ---")
        return ""
