import sqlite3
import json
from typing import Optional, List
from datetime import datetime
from src.common.db import get_db_connection
from src.common.models import Product, PolicyDocument, VerificationStatus
from src.common.logging import logger

class SQLiteRepository:
    def add_product(self, product: Product) -> Product:
        query = """
        INSERT OR REPLACE INTO products (id, product_code, name, company, category, publish_time, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                product.id,
                product.product_code,
                product.name,
                product.company,
                product.category,
                product.publish_time,
                product.created_at.isoformat() if product.created_at else None
            ))
            conn.commit()
        return product
    
    def get_product_by_code(self, product_code: str, company: str) -> Optional[Product]:
        """根据产品代码和公司查询产品"""
        query = "SELECT * FROM products WHERE product_code = ? AND company = ?"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute(query, (product_code, company)).fetchone()
            if row:
                return Product(
                    id=row["id"],
                    product_code=row["product_code"],
                    name=row["name"],
                    company=row["company"],
                    category=row["category"],
                    publish_time=row["publish_time"],
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
                )
        return None

    def get_product(self, product_id: str) -> Optional[Product]:
        query = "SELECT * FROM products WHERE id = ?"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute(query, (product_id,)).fetchone()
            if row:
                return Product(
                    id=row["id"],
                    product_code=row["product_code"],
                    name=row["name"],
                    company=row["company"],
                    category=row["category"],
                    publish_time=row["publish_time"],
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
                )
        return None
        
    def get_product_by_name(self, name: str, company: str) -> Optional[Product]:
        query = "SELECT * FROM products WHERE name = ? AND company = ?"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute(query, (name, company)).fetchone()
            if row:
                return Product(
                    id=row["id"],
                    name=row["name"],
                    company=row["company"],
                    category=row["category"],
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
                )
        return None

    def add_document(self, doc: PolicyDocument) -> PolicyDocument:
        query = """
        INSERT OR IGNORE INTO policy_documents (
            id, product_id, doc_type, filename, local_path, url, file_hash, file_size,
            downloaded_at, verification_status, auditor_notes, markdown_content, pdf_links
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (
                doc.id,
                doc.product_id,
                doc.doc_type,
                doc.filename,
                doc.local_path,
                doc.url,
                doc.file_hash,
                doc.file_size,
                doc.downloaded_at.isoformat() if doc.downloaded_at else None,
                doc.verification_status.value,
                doc.auditor_notes,
                doc.markdown_content,
                json.dumps(doc.pdf_links, ensure_ascii=False) if doc.pdf_links else None
            ))
            conn.commit()
        return doc
    
    def get_db_connection(self):
        """返回数据库连接上下文管理器"""
        return get_db_connection()

    def get_document(self, doc_id: str) -> Optional[PolicyDocument]:
        query = "SELECT * FROM policy_documents WHERE id = ?"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute(query, (doc_id,)).fetchone()
            if row:
                return self._row_to_doc(row)
        return None
        
    def get_document_by_hash(self, file_hash: str) -> Optional[PolicyDocument]:
        query = "SELECT * FROM policy_documents WHERE file_hash = ?"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            row = cursor.execute(query, (file_hash,)).fetchone()
            if row:
                return self._row_to_doc(row)
        return None

    def get_pending_documents(self) -> List[PolicyDocument]:
        query = "SELECT * FROM policy_documents WHERE verification_status = ?"
        with get_db_connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute(query, (VerificationStatus.PENDING.value,)).fetchall()
            return [self._row_to_doc(row) for row in rows]
    
    def list_documents(self, verification_status: str = None) -> List[PolicyDocument]:
        """
        列出文档
        
        Args:
            verification_status: 过滤状态 (PENDING/VERIFIED/REJECTED)
            
        Returns:
            文档列表
        """
        if verification_status:
            query = "SELECT * FROM policy_documents WHERE verification_status = ?"
            with get_db_connection() as conn:
                cursor = conn.cursor()
                rows = cursor.execute(query, (verification_status,)).fetchall()
                return [self._row_to_doc(row) for row in rows]
        else:
            query = "SELECT * FROM policy_documents"
            with get_db_connection() as conn:
                cursor = conn.cursor()
                rows = cursor.execute(query).fetchall()
                return [self._row_to_doc(row) for row in rows]
            
    def update_document_status(self, doc_id: str, status: VerificationStatus, notes: Optional[str] = None):
        query = """
        UPDATE policy_documents 
        SET verification_status = ?, auditor_notes = ?
        WHERE id = ?
        """
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (status.value, notes, doc_id))
            conn.commit()

    def _row_to_doc(self, row) -> PolicyDocument:
        # Helper function to safely get row value
        def safe_get(row, key, default=None):
            try:
                return row[key]
            except (KeyError, IndexError):
                return default
        
        return PolicyDocument(
            id=row["id"],
            product_id=row["product_id"],
            doc_type=row["doc_type"],
            filename=row["filename"],
            local_path=row["local_path"],
            url=row["url"],
            file_hash=row["file_hash"],
            file_size=safe_get(row, "file_size"),
            downloaded_at=datetime.fromisoformat(row["downloaded_at"]) if row["downloaded_at"] else None,
            verification_status=VerificationStatus(row["verification_status"]),
            auditor_notes=row["auditor_notes"],
            markdown_content=row["markdown_content"],
            pdf_links=json.loads(safe_get(row, "pdf_links", "{}")) if safe_get(row, "pdf_links") else {}
        )

repository = SQLiteRepository()

