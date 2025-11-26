"""
LLM解析文档测试配置

独立的测试环境配置，与主系统分离
"""
from pathlib import Path

# 测试数据路径
TEST_DATA_DIR = Path("data/llm_test")
TEST_VECTOR_STORE_DIR = TEST_DATA_DIR / "vector_store"
TEST_BM25_INDEX_PATH = TEST_DATA_DIR / "bm25_index.pkl"

# LLM解析的Markdown文件
LLM_PARSED_DOCS = {
    "产品条款": Path("data/processed/2124条款.md"),
    "产品说明书": Path("data/processed/2124产品说明书.md"),
    "产品费率表": Path("data/processed/2124费率表.md")
}

# 产品信息（硬编码用于测试）
TEST_PRODUCT = {
    "id": "test-llm-2124",
    "product_code": "2124",
    "name": "平安福耀年金保险（分红型）",
    "company": "平安人寿",
    "category": "年金保险"
}

# Chunking 配置（针对LLM解析文档优化）
CHUNK_SIZE = 600  # tokens（比现有系统更小，更精准）
CHUNK_OVERLAP = 100  # tokens

# ChromaDB 配置
CHROMA_COLLECTION_NAME = "llm_test_insurance_clauses"

# 测试报告路径
TEST_REPORT_PATH = Path("tests/llm_parsed_test/test_report.md")

# 测试问题文件
TEST_QUESTIONS_PATH = Path("tests/llm_parsed_test/test_questions.json")

# 确保测试目录存在
def ensure_test_dirs():
    TEST_DATA_DIR.mkdir(parents=True, exist_ok=True)
    TEST_VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
    TEST_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
