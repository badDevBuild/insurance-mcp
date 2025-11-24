import csv
import json
import uuid
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from ..parsers.base import DocTable
from ...common.config import config

class TableSerializer:
    """
    Serializes rate tables to CSV and updates metadata registry.
    """
    
    def __init__(self, export_dir: Path = None):
        self.export_dir = export_dir or config.TABLE_EXPORT_DIR
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_path = self.export_dir / "metadata.json"
        self._ensure_metadata_file()
        
    def _ensure_metadata_file(self):
        if not self.metadata_path.exists():
            with open(self.metadata_path, "w", encoding="utf-8") as f:
                json.dump({}, f)

    def _load_metadata(self) -> Dict:
        try:
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

    def _save_metadata(self, metadata: Dict):
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def serialize_rate_table(self, table: DocTable, product_code: str = None, source_pdf: str = None) -> str:
        """
        Serialize table to CSV and return the Table UUID.
        """
        table_id = str(uuid.uuid4())
        filename = f"{table_id}.csv"
        file_path = self.export_dir / filename
        
        # Write CSV
        with open(file_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            if table.headers:
                writer.writerow(table.headers)
            writer.writerows(table.rows)
            
        # Update Metadata
        metadata = self._load_metadata()
        metadata[table_id] = {
            "source_pdf": source_pdf,
            "product_code": product_code,
            "table_type": "RATE_TABLE",
            "csv_path": filename,
            "headers": table.headers,
            "row_count": len(table.rows),
            "col_count": len(table.headers) if table.headers else (len(table.rows[0]) if table.rows else 0),
            "page_number": table.page_number,
            "created_at": datetime.now().isoformat()
        }
        self._save_metadata(metadata)
        
        table.csv_path = str(file_path)
        return table_id
