import hashlib
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from src.common.config import config
from src.common.logging import logger
from src.common.models import Product, PolicyDocument, VerificationStatus
from src.common.repository import repository
from src.crawler.acquisition.downloader import PDFDownloader

class SavePipeline:
    def __init__(self):
        self.downloader = PDFDownloader()

    async def process_item(self, item: Dict[str, Any]):
        """
        Process a discovered item: ensure product exists, download doc, save to DB.
        
        Args:
            item: Dictionary containing product and document metadata from spider.
                  Expected keys: name, company, category, source_url, filename
        """
        # 1. Create or Get Product
        product = repository.get_product_by_name(item["name"], item["company"])
        if not product:
            product = Product(
                name=item["name"],
                company=item["company"],
                category=item.get("category")
            )
            repository.add_product(product)
            logger.info(f"Created new product: {product.name}")
        else:
            logger.debug(f"Product exists: {product.name}")

        # 2. Prepare Document Path
        # Structure: data/raw/{company}/{filename} (Flattish for now or by year if available)
        # Using company folder to avoid name collisions
        safe_company = item["company"].replace("/", "_").replace("\\", "_")
        safe_filename = item["filename"].replace("/", "_").replace("\\", "_")
        
        target_dir = config.RAW_DATA_DIR / safe_company
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / safe_filename
        
        # 3. Download File (if not exists or force update logic - for now skip if exists)
        # But we need to hash it to check duplicates in DB effectively. 
        # If file exists locally, we might want to re-verify or skip.
        # Let's try to download to a temp location first if we want to be safe, 
        # or download directly and hash.
        
        download_success = False
        if not target_path.exists():
            download_success = await self.downloader.download(item["source_url"], target_path)
        else:
            logger.info(f"File already exists locally: {target_path}")
            download_success = True

        if download_success and target_path.exists():
            # 4. Calculate Hash
            file_hash = self._calculate_file_hash(target_path)
            
            # 5. Check if Document exists in DB
            existing_doc = repository.get_document_by_hash(file_hash)
            if existing_doc:
                logger.info(f"Document already exists in DB (ID: {existing_doc.id})")
                # Optional: Update URL or association if needed
                return

            # 6. Save Document to DB
            doc = PolicyDocument(
                product_id=product.id,
                filename=safe_filename,
                local_path=str(target_path),
                url=item["source_url"],
                file_hash=file_hash,
                verification_status=VerificationStatus.PENDING
            )
            repository.add_document(doc)
            logger.info(f"Saved document {doc.filename} (ID: {doc.id})")
            
        else:
            logger.error(f"Failed to process document for {item['name']}")

    def _calculate_file_hash(self, file_path: Path) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

save_pipeline = SavePipeline()

