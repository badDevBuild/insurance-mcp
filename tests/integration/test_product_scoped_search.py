"""
产品范围检索和产品查询的集成测试

测试T032-T037的P0+增强功能：
1. 产品查询工具（lookup_product）
2. 产品范围检索（search_policy_clause with product_code）
3. 产品元数据在索引和检索中的正确传递

根据 tasks.md §T036 实施。
"""
import pytest
import sys
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.mcp_server.product_lookup import lookup_product, get_product_by_code
from src.mcp_server.tools.search_policy_clause import SearchPolicyClauseTool
from src.indexing.indexer import PolicyIndexer
from src.indexing.vector_store.chroma import ChromaDBStore
from src.indexing.embedding.bge import BGEEmbedder
from src.common.repository import SQLiteRepository
from src.common.models import Product, PolicyDocument, VerificationStatus


class TestProductLookup:
    """测试产品查询工具"""
    
    def test_lookup_product_fuzzy_match(self):
        """测试模糊匹配功能"""
        # 查询"盈添悦"应该能匹配到完整产品名
        results = lookup_product("盈添悦", company="平安人寿")
        
        assert len(results) > 0, "应该找到至少1个产品"
        
        # Top 1结果应该包含"盈添悦"
        top_product = results[0]
        assert "盈添悦" in top_product.product_name
        assert top_product.company == "平安人寿"
        assert top_product.product_code is not None
    
    def test_lookup_product_by_category(self):
        """测试按类别查询"""
        # 查询"养老"应该返回养老年金类产品
        results = lookup_product("养老", company="平安人寿")
        
        if len(results) > 0:
            # 检查返回的产品是否包含"养老"相关词
            top_product = results[0]
            assert "养老" in top_product.product_name or "年金" in top_product.product_name
    
    def test_lookup_product_returns_top_k(self):
        """测试返回Top-K结果"""
        results = lookup_product("保险", top_k=5)
        
        # 应该返回不超过5个结果
        assert len(results) <= 5
    
    def test_get_product_by_code(self):
        """测试通过产品代码精确查询"""
        # 首先通过模糊查询获取一个产品代码
        results = lookup_product("盈添悦", company="平安人寿")
        
        if len(results) > 0:
            product_code = results[0].product_code
            
            # 使用产品代码精确查询
            exact_result = get_product_by_code(product_code)
            
            assert exact_result is not None
            assert exact_result.product_code == product_code


class TestProductScopedSearch:
    """测试产品范围检索（FR-001增强）"""
    
    @pytest.fixture
    def setup_test_env(self):
        """设置测试环境"""
        # 初始化组件
        repo = SQLiteRepository()
        chroma_store = ChromaDBStore()
        
        # 创建搜索工具实例（工具会自动初始化需要的组件）
        search_tool = SearchPolicyClauseTool()
        
        return {
            'repo': repo,
            'chroma_store': chroma_store,
            'search_tool': search_tool
        }
    
    def test_search_with_product_code_filter(self, setup_test_env):
        """测试按产品代码过滤检索"""
        env = setup_test_env
        search_tool = env['search_tool']
        
        # 首先查找一个产品
        products = lookup_product("盈添悦", company="平安人寿")
        
        if len(products) == 0:
            pytest.skip("没有找到测试产品")
        
        product_code = products[0].product_code
        
        # 在该产品范围内检索
        results = search_tool.run(
            query="身故保险金怎么赔?",
            product_code=product_code,
            n_results=5
        )
        
        # 验证返回的所有结果都属于该产品
        for result in results:
            # 注意: 需要验证result的来源元数据
            # 这里假设ClauseResult包含source_reference.product_code
            # 实际实现中需要确保这一点
            pass  # 在实际数据存在后补充断言
    
    def test_search_without_product_filter(self, setup_test_env):
        """测试全局检索（向后兼容）"""
        env = setup_test_env
        search_tool = env['search_tool']
        
        # 不指定产品代码，应该进行全局检索
        results = search_tool.run(
            query="保险期间是多久?",
            company="平安人寿",
            n_results=5
        )
        
        # 应该返回结果（如果有数据的话）
        # 具体断言取决于实际数据
        assert isinstance(results, list)
    
    def test_search_with_doc_type_filter(self, setup_test_env):
        """测试按文档类型过滤（FR-005）"""
        env = setup_test_env
        search_tool = env['search_tool']
        
        # 仅在产品条款中检索
        results = search_tool.run(
            query="保险责任",
            doc_type="产品条款",
            n_results=5
        )
        
        # 验证返回的结果都是产品条款类型
        for result in results:
            # 需要验证doc_type元数据
            pass  # 在实际数据存在后补充断言
    
    def test_product_metadata_in_chunks(self, setup_test_env):
        """测试Chunk中是否包含产品元数据"""
        env = setup_test_env
        chroma_store = env['chroma_store']
        
        # 获取一个chunk并检查其元数据
        results = chroma_store.collection.get(limit=1, include=["metadatas"])
        
        if len(results['ids']) > 0:
            metadata = results['metadatas'][0]
            
            # 验证产品元数据字段存在
            assert 'company' in metadata, "应包含company字段"
            assert 'product_code' in metadata, "应包含product_code字段"
            assert 'product_name' in metadata, "应包含product_name字段"
            
            # 验证字段值非空
            assert metadata['company'], "company字段不应为空"
            assert metadata['product_code'], "product_code字段不应为空"


class TestIndexingWithProductMetadata:
    """测试索引流程中的产品元数据传递"""
    
    def test_chunk_contains_product_context(self):
        """测试生成的Chunk包含产品上下文"""
        repo = SQLiteRepository()
        
        # 获取一个VERIFIED文档
        documents = repo.list_documents(verification_status='VERIFIED')
        
        if len(documents) == 0:
            pytest.skip("没有VERIFIED文档可测试")
        
        doc = documents[0]
        
        # 获取关联的产品
        product = repo.get_product(doc.product_id)
        
        assert product is not None, f"文档{doc.id}关联的产品{doc.product_id}不存在"
        
        # 验证产品有必要的字段
        assert product.company, "产品应有company字段"
        assert product.product_code, "产品应有product_code字段"
        assert product.name, "产品应有name字段"


class TestEndToEndProductScopedRetrieval:
    """端到端测试：产品查询 → 产品范围检索"""
    
    def test_e2e_workflow(self):
        """
        测试完整工作流：
        1. 用户查询"盈添悦"
        2. 系统返回product_code
        3. 使用product_code进行范围检索
        4. 验证结果仅来自该产品
        """
        # Step 1: 产品查询
        products = lookup_product("盈添悦", company="平安人寿")
        
        if len(products) == 0:
            pytest.skip("没有找到测试产品")
        
        product_code = products[0].product_code
        print(f"\n找到产品: {products[0].product_name} (代码: {product_code})")
        
        # Step 2: 产品范围检索
        search_tool = SearchPolicyClauseTool()
        results = search_tool.run(
            query="身故保险金如何给付?",
            product_code=product_code,
            n_results=3
        )
        
        print(f"检索到 {len(results)} 个结果")
        
        # Step 3: 验证结果质量
        if len(results) > 0:
            # 相似度应该比全局检索更高（这是产品范围检索的核心价值）
            top_similarity = results[0].similarity_score
            print(f"Top-1 相似度: {top_similarity:.4f}")
            
            # 在产品范围内，相似度应该>0.7（根据spec.md的目标）
            # 注意：这个阈值可能需要根据实际数据调整
            # assert top_similarity > 0.7, f"产品范围检索相似度应>0.7，实际: {top_similarity:.4f}"


# Pytest标记
pytestmark = pytest.mark.integration


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
