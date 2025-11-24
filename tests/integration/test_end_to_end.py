"""端到端集成测试

验证从Markdown处理到检索的完整链路：
1. Markdown后处理 (Post-processing)
2. 索引构建 (Indexing)
3. 混合检索 (Hybrid Retrieval)
4. MCP工具调用 (Tool Execution)

根据 tasks.md §T031 实施。
"""
import asyncio
import os
import shutil
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.common.logging import setup_logging
from src.common.models import PolicyDocument, Product
from src.common.repository import PolicyRepository  # P0增强
from src.parser.markdown.postprocessor import MarkdownPostProcessor
from src.indexing.indexer import PolicyIndexer, create_indexer
from src.indexing.vector_store.chroma import ChromaDBStore
from src.indexing.vector_store.hybrid_retriever import BM25Index, create_hybrid_retriever
from src.mcp_server.tools.search_policy_clause import tool as search_tool

setup_logging()

# 测试数据目录
TEST_DATA_DIR = Path("tests/data/e2e_test")
TEST_DB_PATH = TEST_DATA_DIR / "chroma_db"
TEST_REPO_DB_PATH = TEST_DATA_DIR / "policy_repo.db" # P0增强

@pytest.fixture(scope="module")
def setup_test_env():
    """设置测试环境"""
    # 清理并创建测试目录
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR)
    TEST_DATA_DIR.mkdir(parents=True)
    
    yield
    
    # 清理
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR)

@pytest.fixture(scope="module")
def sample_markdown():
    """创建样本Markdown文件"""
    content = """
# 平安人寿测试保险

## 1. 保险责任

### 1.1 身故保险金

被保险人⁽¹⁾于等待期后身故，我们按基本保险金额给付身故保险金。

⁽¹⁾: 被保险人指受保险合同保障的人

### 1.2 满期生存保险金

保险期间届满时，被保险人仍生存，我们给付满期生存保险金。

## 2. 责任免除

### 2.1 责任免除事项

因下列情形之一导致被保险人身故的，我们不承担给付保险金的责任：

1) 投保人对被保险人的故意杀害、故意伤害；
2) 被保险人酒后驾驶⁽²⁾；

⁽²⁾: 酒后驾驶指车辆驾驶人员血液中的酒精含量大于或者等于20mg/100ml的驾驶行为。

## 3. 现金价值表

| 年度 | 现金价值 |
|---|---|
| 1 | 100 |
| 2 | 200 |
"""
    md_path = TEST_DATA_DIR / "test_doc.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)
    return str(md_path)

@pytest.fixture(scope="module")
def mock_document(sample_markdown): # 接收 sample_markdown fixture
    """Mock PolicyDocument"""
    # 1. 创建测试产品 (P0增强: 需要先创建产品)
    repo = PolicyRepository(db_path=TEST_REPO_DB_PATH)
    
    test_product = Product(
        id="prod_e2e_test",
        product_code="TEST001",
        name="测试保险产品",
        company="测试保险公司",
        category="两全保险",
        publish_time="2025-01-01",
        created_at=datetime.now()
    )
    repo.add_product(test_product)
    
    # 2. 创建测试文档
    test_doc_path = Path(sample_markdown) # 使用 sample_markdown 的路径
    test_doc = PolicyDocument(
        id="doc_e2e_test",
        product_id="prod_e2e_test",
        doc_type="产品条款",
        filename="test_doc.md",
        local_path=str(test_doc_path),
        url="http://example.com",
        verification_status="VERIFIED"
    )
    repo.add_document(test_doc)
    
    return test_doc # 返回创建的文档对象

@pytest.mark.asyncio
async def test_e2e_workflow(setup_test_env, sample_markdown, mock_document):
    """执行端到端工作流"""
    
    # 1. 后处理 (Post-processing)
    print("\nStep 1: Markdown后处理...")
    postprocessor = MarkdownPostProcessor()
    processed_content = postprocessor.process(sample_markdown)
    
    # 验证脚注内联
    assert "被保险人(被保险人指受保险合同保障的人)" in processed_content
    assert "酒后驾驶(酒后驾驶指" in processed_content
    
    # 2. 索引构建 (Indexing)
    print("\nStep 2: 索引构建...")
    
    # 使用本地ChromaDB进行测试
    chroma_store = ChromaDBStore(persist_directory=str(TEST_DB_PATH))
    bm25_index = BM25Index()
    
    # Mock embedder以避免API调用
    mock_embedder = MagicMock()
    # 返回随机向量
    mock_embedder.embed_batch.side_effect = lambda texts: [[0.1] * 1536 for _ in texts]
    mock_embedder.embed_single.side_effect = lambda text: [0.1] * 1536
    mock_embedder.get_stats.return_value = {"total_tokens": 100, "estimated_cost_usd": 0.0001}
    
    indexer = create_indexer(
        embedder=mock_embedder,
        chroma_store=chroma_store,
        bm25_index=bm25_index
    )
    
    chunks = indexer.index_document(mock_document, sample_markdown)
    
    assert len(chunks) > 0
    # 验证表格chunk
    table_chunks = [c for c in chunks if c.is_table]
    assert len(table_chunks) == 1
    assert table_chunks[0].table_data.row_count == 2
    
    # 3. 混合检索 (Retrieval)
    print("\nStep 3: 混合检索...")
    retriever = create_hybrid_retriever(
        chroma_store=chroma_store,
        bm25_index=bm25_index
    )
    
    # 测试数字查询（应该触发高BM25权重）
    results_numeric = retriever.search(
        query="现金价值 200",
        query_embedding=[0.1]*1536,
        auto_weight=True
    )
    
    # 验证是否找回表格chunk
    found_table = any(res['metadata'].get('is_table') for res in results_numeric)
    assert found_table, "未能检索到表格数据"
    
    # 4. MCP工具调用 (Tool Execution)
    print("\nStep 4: MCP工具调用...")
    
    # Patch工具中的组件
    with patch.object(search_tool, '_chroma_store', chroma_store), \
         patch.object(search_tool, '_embedder', mock_embedder), \
         patch.object(search_tool, '_retriever', retriever):
        
        # 执行search_policy_clause
        tool_results = search_tool.run(
            query="酒后驾驶赔吗",
            min_similarity=0.0 # Mock向量相似度可能很低
        )
        
        assert len(tool_results) > 0
        # 验证结果结构 (Mock embedder返回相同向量,无法保证检索顺序)
        assert tool_results[0].chunk_id
        assert tool_results[0].content
        assert tool_results[0].section_id
        assert tool_results[0].similarity_score >= 0.0

    print("\n✅ 端到端测试通过！")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

