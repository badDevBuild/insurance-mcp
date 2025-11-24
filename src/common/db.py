import sqlite3
from contextlib import contextmanager
from src.common.config import config
from src.common.logging import logger

@contextmanager
def get_db_connection():
    """Context manager for SQLite database connection."""
    conn = None
    try:
        conn = sqlite3.connect(config.DB_PATH)
        conn.row_factory = sqlite3.Row
        yield conn
    except sqlite3.Error as e:
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()

def init_db():
    """Initialize database schema."""
    schema_script = """
    CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        product_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        company TEXT NOT NULL DEFAULT '平安人寿',
        category TEXT,
        publish_time TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE INDEX IF NOT EXISTS idx_product_code ON products(product_code);
    CREATE INDEX IF NOT EXISTS idx_product_company ON products(company);

    CREATE TABLE IF NOT EXISTS policy_documents (
        id TEXT PRIMARY KEY,
        product_id TEXT,
        doc_type TEXT NOT NULL,
        filename TEXT NOT NULL,
        local_path TEXT NOT NULL,
        url TEXT,
        file_hash TEXT,
        file_size INTEGER,
        downloaded_at TIMESTAMP,
        verification_status TEXT DEFAULT 'PENDING',
        auditor_notes TEXT,
        markdown_content TEXT,
        pdf_links TEXT,  -- JSON格式存储所有PDF链接 {"产品条款": "url1", "费率表": "url2"}
        FOREIGN KEY(product_id) REFERENCES products(id)
    );
    
    CREATE INDEX IF NOT EXISTS idx_doc_product ON policy_documents(product_id);
    CREATE INDEX IF NOT EXISTS idx_doc_status ON policy_documents(verification_status);
    CREATE INDEX IF NOT EXISTS idx_doc_hash ON policy_documents(file_hash);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_doc_unique ON policy_documents(product_id, doc_type, url);
    """
    
    try:
        # Ensure directory exists
        config.ensure_dirs()
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.executescript(schema_script)
            conn.commit()
            logger.info(f"Database initialized at {config.DB_PATH}")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

