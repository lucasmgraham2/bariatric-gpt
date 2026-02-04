
import os
import glob
import shutil
import chromadb
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE_DIR = os.path.join(BASE_DIR, "../knowledge")
DB_DIR = os.path.join(BASE_DIR, "../chroma_db")

def rebuild_database():
    print("="*50)
    print("      BUILDING KNOWLEDGE BASE (Offline Mode)")
    print("="*50)

    # 1. Cleaner: Wipe existing DB
    if os.path.exists(DB_DIR):
        print(f"🧹 Removing old database at {DB_DIR}...")
        shutil.rmtree(DB_DIR)
    
    os.makedirs(DB_DIR, exist_ok=True)

    # 2. Loader: Read files
    docs = []
    print(f"📂 Scanning {KNOWLEDGE_DIR}...")
    
    # Text files
    txt_files = glob.glob(os.path.join(KNOWLEDGE_DIR, "*.txt"))
    for f in txt_files:
        try:
            print(f"   - Loading text: {os.path.basename(f)}")
            loader = TextLoader(f)
            docs.extend(loader.load())
        except Exception as e:
            print(f"   ❌ Error loading {f}: {e}")

    # PDF files
    pdf_files = glob.glob(os.path.join(KNOWLEDGE_DIR, "*.pdf"))
    for f in pdf_files:
        try:
            print(f"   - Loading PDF: {os.path.basename(f)}")
            loader = PyPDFLoader(f)
            docs.extend(loader.load())
        except Exception as e:
            print(f"   ❌ Error loading {f}: {e}")

    if not docs:
        print("\n⚠️  No documents found! Database will be empty.")
        return

    # 3. Splitter: Chunking
    # Using slightly larger chunks for medical context, with overlap to capture cross-boundary info
    print(f"\n✂️  Splitting {len(docs)} documents...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150,
        length_function=len,
        is_separator_regex=False,
    )
    splits = text_splitter.split_documents(docs)
    print(f"   -> Generated {len(splits)} chunks of knowledge.")

    # 4. Ingest: ChromaDB
    print("\n💾 Ingesting into Vector Database...")
    client = chromadb.PersistentClient(path=DB_DIR)
    collection = client.get_or_create_collection(name="bariatric_knowledge")

    ids = [str(i) for i in range(len(splits))]
    documents = [d.page_content for d in splits]
    metadatas = [d.metadata for d in splits]

    # Batch add (Chroma matches batch size automatically, but good to be safe if huge)
    batch_size = 100
    total_batches = (len(documents) + batch_size - 1) // batch_size
    
    for i in range(0, len(documents), batch_size):
        end = min(i + batch_size, len(documents))
        print(f"   - Batch {i//batch_size + 1}/{total_batches}...")
        collection.add(
            ids=ids[i:end],
            documents=documents[i:end],
            metadatas=metadatas[i:end]
        )

    print("\n✅ Knowledge Base Build Complete.")
    print(f"   Total Chunks: {collection.count()}")
    print("="*50)

if __name__ == "__main__":
    rebuild_database()
