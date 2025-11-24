import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.mcp_server.tools.search_policy_clause import SearchPolicyClauseTool
from src.common.logging import setup_logging
from src.common.models import DocumentType

def test_search():
    setup_logging()
    print("Starting multi-doc search verification...")
    
    tool = SearchPolicyClauseTool()
    
    # Test 1: General search (no filter)
    print("\n--- Test 1: General Search (Query: '现金价值') ---")
    
    # Debug: Check embedding
    emb = tool.embedder.embed_single("现金价值")
    print(f"Embedding length: {len(emb)}")
    print(f"Embedding sample: {emb[:5]}")
    
    # Debug: Direct search
    print("Direct ChromaDB search:")
    raw_results = tool.chroma_store.search(query_embedding=emb, n_results=5)
    print(f"Raw results count: {len(raw_results)}")
    if raw_results:
        print(f"First raw result distance: {raw_results[0].get('distance')}")
        print(f"First raw result metadata: {raw_results[0].get('metadata')}")

    results = tool.run(query="现金价值", n_results=5)
    print(f"Tool results: {len(results)}")
        
    # Test 2: Filter by Clause
    print(f"\n--- Test 2: Filter by {DocumentType.CLAUSE.value} ---")
    results = tool.run(query="现金价值", doc_type=DocumentType.CLAUSE.value, n_results=5)
    print(f"Found {len(results)} results")
    for r in results:
        print(f"  - [{r.source_reference.doc_type}] {r.section_title}")
        if r.source_reference.doc_type != DocumentType.CLAUSE.value:
            print("  ❌ ERROR: Wrong doc type!")
            
    # Test 3: Filter by Manual
    print(f"\n--- Test 3: Filter by {DocumentType.MANUAL.value} ---")
    results = tool.run(query="现金价值", doc_type=DocumentType.MANUAL.value, n_results=5)
    print(f"Found {len(results)} results")
    for r in results:
        print(f"  - [{r.source_reference.doc_type}] {r.section_title}")
        if r.source_reference.doc_type != DocumentType.MANUAL.value:
            print("  ❌ ERROR: Wrong doc type!")

    # Test 4: Filter by Rate Table
    print(f"\n--- Test 4: Filter by {DocumentType.RATE_TABLE.value} ---")
    results = tool.run(query="费率", doc_type=DocumentType.RATE_TABLE.value, n_results=5)
    print(f"Found {len(results)} results")
    for r in results:
        print(f"  - [{r.source_reference.doc_type}] {r.section_title}")
        if r.source_reference.doc_type != DocumentType.RATE_TABLE.value:
            print("  ❌ ERROR: Wrong doc type!")

if __name__ == "__main__":
    test_search()
