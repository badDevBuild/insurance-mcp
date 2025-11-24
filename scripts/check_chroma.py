import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.indexing.vector_store.chroma import get_chroma_store
from src.common.logging import setup_logging

def check_chroma():
    setup_logging()
    store = get_chroma_store()
    count = store.collection.count()
    print(f"ChromaDB Collection Count: {count}")
    
    if count > 0:
        print("Sample item:")
        print(store.collection.peek(limit=1))

if __name__ == "__main__":
    check_chroma()
