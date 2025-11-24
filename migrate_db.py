"""
数据库迁移脚本
从旧schema迁移到新schema
"""
import sqlite3
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.common.config import config
from src.common.logging import logger

def migrate():
    """执行数据库迁移"""
    
    db_path = config.DB_PATH
    
    if not Path(db_path).exists():
        print(f"数据库不存在: {db_path}")
        print("请运行: python -m src.cli.manage init")
        return
    
    print("=" * 80)
    print("数据库迁移")
    print("=" * 80)
    print(f"数据库: {db_path}\n")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # 1. 检查 products 表是否需要迁移
        print("检查 products 表...")
        
        # 获取当前列
        cursor.execute("PRAGMA table_info(products)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"  当前列: {', '.join(columns)}")
        
        if 'product_code' not in columns:
            print("  ✓ 需要添加 product_code 列")
            
            # 备份表
            cursor.execute("ALTER TABLE products RENAME TO products_old")
            
            # 创建新表
            cursor.execute("""
            CREATE TABLE products (
                id TEXT PRIMARY KEY,
                product_code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                company TEXT NOT NULL DEFAULT '平安人寿',
                category TEXT,
                publish_time TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # 迁移数据（生成默认的product_code）
            cursor.execute("""
            INSERT INTO products (id, product_code, name, company, category, created_at)
            SELECT 
                id,
                COALESCE(substr(name, 1, 10), id) as product_code,  -- 使用产品名前10字符作为临时code
                name,
                company,
                category,
                created_at
            FROM products_old
            """)
            
            # 删除旧表
            cursor.execute("DROP TABLE products_old")
            
            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_code ON products(product_code)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_company ON products(company)")
            
            print("  ✓ products 表已迁移")
        else:
            print("  - products 表已是最新版本")
        
        # 2. 检查 policy_documents 表
        print("\n检查 policy_documents 表...")
        
        cursor.execute("PRAGMA table_info(policy_documents)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"  当前列: {', '.join(columns)}")
        
        if 'doc_type' not in columns:
            print("  ✓ 需要添加 doc_type 和 file_size 列")
            
            # 备份表
            cursor.execute("ALTER TABLE policy_documents RENAME TO policy_documents_old")
            
            # 创建新表
            cursor.execute("""
            CREATE TABLE policy_documents (
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
                FOREIGN KEY(product_id) REFERENCES products(id)
            )
            """)
            
            # 迁移数据
            cursor.execute("""
            INSERT INTO policy_documents (
                id, product_id, doc_type, filename, local_path, url, file_hash, 
                downloaded_at, verification_status, auditor_notes, markdown_content
            )
            SELECT 
                id,
                product_id,
                '未分类' as doc_type,  -- 旧数据没有doc_type，设为默认值
                filename,
                local_path,
                url,
                file_hash,
                downloaded_at,
                verification_status,
                auditor_notes,
                markdown_content
            FROM policy_documents_old
            """)
            
            # 删除旧表
            cursor.execute("DROP TABLE policy_documents_old")
            
            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_product ON policy_documents(product_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_status ON policy_documents(verification_status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_hash ON policy_documents(file_hash)")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_doc_unique ON policy_documents(product_id, doc_type, url)")
            
            print("  ✓ policy_documents 表已迁移")
        else:
            print("  - policy_documents 表已是最新版本")
        
        # 提交更改
        conn.commit()
        
        print("\n" + "=" * 80)
        print("✅ 迁移完成！")
        print("=" * 80)
        
        # 显示统计
        cursor.execute("SELECT COUNT(*) FROM products")
        product_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM policy_documents")
        doc_count = cursor.fetchone()[0]
        
        print(f"\n数据统计:")
        print(f"  - 产品: {product_count} 条")
        print(f"  - 文档: {doc_count} 条")
        
        print(f"\n⚠️  注意: 旧数据的 product_code 是自动生成的，建议重新爬取数据")
        
    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()

