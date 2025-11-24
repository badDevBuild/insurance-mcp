
import chromadb
from chromadb.config import Settings
import uuid
from enum import Enum

def debug():
    print(f"ChromaDB version: {chromadb.__version__}")
    
    try:
        client = chromadb.PersistentClient(path="./test_db_debug", settings=Settings(allow_reset=True))
        client.reset()
        
        collection = client.create_collection(name="test_collection")
        
        # Test case 1: All fields
        metadata_full = {
            "document_id": "doc_test",
            "section_id": "1.1",
            "section_title": "Test Title",
            "category": "Liability",
            "level": 3,
            "chunk_index": 0,
            "is_table": False,
            "entity_role": "Insurer",
            "parent_section": "1",
            "keywords": "key,word"
        }
        
        print("\nTest 1: Full metadata")
        try:
            collection.add(
                ids=[str(uuid.uuid4())],
                documents=["test content"],
                embeddings=[[0.1]*1536],
                metadatas=[metadata_full]
            )
            print("SUCCESS")
        except Exception as e:
            print(f"FAILURE: {e}")

        # Test case 2: Only strings
        metadata_str = {
            "document_id": "doc_test",
            "category": "Liability"
        }
        print("\nTest 2: Only strings")
        try:
            collection.add(
                ids=[str(uuid.uuid4())],
                documents=["test content"],
                embeddings=[[0.1]*1536],
                metadatas=[metadata_str]
            )
            print("SUCCESS")
        except Exception as e:
            print(f"FAILURE: {e}")

        # Test case 3: With Int
        metadata_int = {
            "level": 3
        }
        print("\nTest 3: With Int")
        try:
            collection.add(
                ids=[str(uuid.uuid4())],
                documents=["test content"],
                embeddings=[[0.1]*1536],
                metadatas=[metadata_int]
            )
            print("SUCCESS")
        except Exception as e:
            print(f"FAILURE: {e}")

        # Test case 4: With Bool
        metadata_bool = {
            "is_table": False
        }
        print("\nTest 4: With Bool")
        try:
            collection.add(
                ids=[str(uuid.uuid4())],
                documents=["test content"],
                embeddings=[[0.1]*1536],
                metadatas=[metadata_bool]
            )
            print("SUCCESS")
        except Exception as e:
            print(f"FAILURE: {e}")

        # Test case 5: With Enum object (should fail)
        class MyEnum(str, Enum):
            VAL = "val"
            
        metadata_enum = {
            "category": MyEnum.VAL
        }
        print("\nTest 5: With Enum object")
        try:
            collection.add(
                ids=[str(uuid.uuid4())],
                documents=["test content"],
                embeddings=[[0.1]*1536],
                metadatas=[metadata_enum]
            )
            print("SUCCESS")
        except Exception as e:
            print(f"FAILURE: {e}")
            # import traceback
            # traceback.print_exc()

    except Exception as e:
        print(f"Global Error: {e}")

if __name__ == "__main__":
    debug()
