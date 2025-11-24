import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.crawler.discovery.pingan_life_spider import PingAnLifeSpider
from src.common.logging import setup_logging

async def verify_crawler():
    setup_logging()
    print("Starting crawler verification...")
    
    spider = PingAnLifeSpider(headless=True)
    # Fetch just a few products to verify
    products = await spider.discover_products(limit=5, fetch_details=True)
    
    print(f"\nDiscovered {len(products)} products.")
    
    for p in products:
        print(f"\nProduct: {p['name']} ({p['product_code']})")
        print("PDF Links:")
        if p['pdf_links']:
            for doc_type, url in p['pdf_links'].items():
                print(f"  - {doc_type}: {url}")
        else:
            print("  No PDF links found.")
            
    # Check if we found different types
    doc_types_found = set()
    for p in products:
        if p['pdf_links']:
            doc_types_found.update(p['pdf_links'].keys())
            
    print(f"\nDocument types found: {doc_types_found}")
    
    required_types = {"产品条款", "产品说明书", "产品费率表"}
    missing_types = required_types - doc_types_found
    
    if not missing_types:
        print("\n✅ SUCCESS: All required document types found!")
    else:
        print(f"\n⚠️ WARNING: Missing document types: {missing_types}")
        print("Note: This might be because the sampled products don't have these documents, or the crawler failed to extract them.")

if __name__ == "__main__":
    asyncio.run(verify_crawler())
