import sys
from pathlib import Path
import uuid

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.common.models import PolicyChunk, DocumentType

def test_chunk_serialization():
    print("Testing PolicyChunk serialization...")
    
    # Test 1: Pass Enum to doc_type (which is str)
    try:
        chunk = PolicyChunk(
            document_id="doc_123",
            company="TestCompany",
            product_code="P123",
            product_name="TestProduct",
            doc_type=DocumentType.MANUAL, # Pass Enum
            content="Test content",
            section_id="1.1",
            section_title="Test Title",
            level=1,
            chunk_index=0
        )
        print(f"Chunk created. doc_type type: {type(chunk.doc_type)}")
        print(f"Chunk doc_type value: {chunk.doc_type}")
        
        metadata = chunk.to_chroma_metadata()
        print(f"Metadata doc_type: {metadata.get('doc_type')}")
        
        if 'doc_type' not in metadata:
            print("❌ doc_type MISSING in metadata!")
        else:
            print("✅ doc_type present in metadata")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_chunk_serialization()
