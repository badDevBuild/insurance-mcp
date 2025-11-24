"""
Docling Integration Test - 端到端索引流程验证

验证从PDF解析到向量索引的完整流程:
1. DoclingParser解析PDF
2. TableClassifier识别费率表
3. TableSerializer导出CSV
4. MarkdownChunker智能分块
5. PolicyIndexer生成chunks并索引到ChromaDB

依赖: 需要真实的PDF文件和运行中的ChromaDB实例
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.indexing.parsers.docling_parser import DoclingParser
from src.indexing.analyzers.table_classifier import TableClassifier
from src.indexing.analyzers.table_serializer import TableSerializer
from src.indexing.chunkers.markdown_chunker import MarkdownChunker
from src.indexing.indexer import PolicyIndexer, create_indexer
from src.common.models import PolicyDocument, Product
from src.common.config import config


@pytest.fixture
def sample_product():
    """示例Product对象"""
    return Product(
        id="test-product-id",
        company="测试保险公司",
        name="测试重疾险",
        product_code="TEST001",
        category="人身险",
        status="在售",
        created_at=datetime.now()
    )


@pytest.fixture
def sample_document():
    """示例PolicyDocument对象"""
    return PolicyDocument(
        id="test-doc-id",
        product_id="test-product-id",
        filename="test_policy.pdf",
        local_path="data/raw/test_policy.pdf",
        doc_type="产品条款",
        verification_status="VERIFIED",
        created_at=datetime.now()
    )


class TestDoclingParserIntegration:
    """DoclingParser 集成测试"""
    
    @pytest.mark.skipif(
        not Path("data/raw/sample_policy.pdf").exists(),
        reason="需要示例PDF文件"
    )
    def test_parse_real_pdf(self):
        """测试解析真实PDF文件"""
        parser = DoclingParser()
        pdf_path = Path("data/raw/sample_policy.pdf")
        
        result = parser.parse(pdf_path)
        
        # 验证解析结果
        assert len(result.elements) > 0
        
        # 检查元素类型
        element_types = {elem.type for elem in result.elements}
        assert 'text' in element_types or 'heading' in element_types
        
        # 检查是否有标题层级
        headings = [e for e in result.elements if e.type == 'heading']
        if headings:
            assert all(h.level >= 1 for h in headings)
        
        print(f"\n✓ 解析完成: {len(result.elements)} 个元素")
        print(f"  - 标题: {len([e for e in result.elements if e.type == 'heading'])}")
        print(f"  - 文本: {len([e for e in result.elements if e.type == 'text'])}")
        print(f"  - 表格: {len([e for e in result.elements if e.type == 'table'])}")


class TestTableWorkflow:
    """费率表识别和导出流程测试"""
    
    def test_table_classification_and_serialization(self):
        """测试表格分类和序列化流程"""
        from src.indexing.parsers.base import DocTable
        
        classifier = TableClassifier()
        serializer = TableSerializer()
        
        # 创建测试表格（费率表）
        rate_table = DocTable(
            type='table',
            content='[TABLE]',
            page_number=10,
            headers=['年龄', '保费', '保额'],
            rows=[
                ['30', '1000', '100000'],
                ['35', '1200', '100000'],
                ['40', '1500', '100000'],
                ['45', '1800', '100000'],
                ['50', '2200', '100000']
            ]
        )
        
        # 创建普通表格
        normal_table = DocTable(
            type='table',
            content='[TABLE]',
            page_number=5,
            headers=['条款编号', '条款名称'],
            rows=[
                ['1.1', '保险责任'],
                ['1.2', '责任免除']
            ]
        )
        
        # 测试分类
        assert classifier.is_rate_table(rate_table) is True
        assert classifier.is_rate_table(normal_table) is False
        
        # 测试序列化
        if config.ENABLE_TABLE_SEPARATION:
            table_id = serializer.serialize_rate_table(
                table=rate_table,
                product_code="TEST001",
                source_pdf="test.pdf"
            )
            
            assert table_id is not None
            assert len(table_id) == 36  # UUID长度
            
            # 验证CSV文件存在
            csv_path = serializer.export_dir / f"{table_id}.csv"
            assert csv_path.exists()
            
            # 验证metadata.json更新
            metadata = serializer._load_metadata()
            assert table_id in metadata
            assert metadata[table_id]['product_code'] == "TEST001"
            assert metadata[table_id]['row_count'] == 5
            
            print(f"\n✓ 费率表导出成功: {table_id}")
            print(f"  CSV路径: {csv_path}")


class TestMarkdownChunkerIntegration:
    """MarkdownChunker 集成测试"""
    
    def test_chunk_with_complex_hierarchy(self):
        """测试复杂层级结构的Markdown分块"""
        markdown = """# 测试保险产品条款

## 第一章 保险责任

### 1.1 重大疾病保险金

被保险人在合同生效后确诊重大疾病，按基本保额给付。

重大疾病包括但不限于：
1. 恶性肿瘤
2. 急性心肌梗塞
3. 脑中风后遗症

### 1.2 身故保险金

被保险人身故，按基本保额给付。

## 第二章 责任免除

### 2.1 一般免责

因下列情形之一导致被保险人身故或重大疾病的，本公司不承担给付保险金的责任：

1. 投保人对被保险人的故意杀害
2. 被保险人故意犯罪或抗拒依法采取的刑事强制措施
3. 被保险人主动吸食或注射毒品

### 2.2 特殊免责

酒后驾驶、无合法有效驾驶证驾驶机动车造成的损失不予赔付。
"""
        
        chunker = MarkdownChunker(chunk_size=200, chunk_overlap=50)
        
        chunks = chunker.chunk_with_hierarchy(markdown, doc_id="test-doc")
        
        # 验证
        assert len(chunks) > 0
        
        # 检查所有chunks都有breadcrumb
        for chunk in chunks:
            assert 'section_path' in chunk
            assert 'content' in chunk
            assert 'section_title' in chunk
            assert 'level' in chunk
            
            # Breadcrumb应该包含在content中
            if chunk['section_title']:
                assert '[章节:' in chunk['content']
        
        # 验证层级结构
        section_paths = [c['section_path'] for c in chunks if c['section_path']]
        assert any('>' in path for path in section_paths)  # 应该有多级路径
        
        print(f"\n✓ Markdown分块完成: {len(chunks)} 个chunks")
        print(f"  示例路径: {section_paths[0]}")


class TestEndToEndIndexing:
    """端到端索引流程测试"""
    
    @pytest.mark.integration
    def test_docling_mode_indexing(self, sample_product, sample_document):
        """测试Docling模式端到端索引（mock版本）"""
        # Mock所有依赖
        mock_embedder = MagicMock()
        mock_embedder.embed_batch.return_value = [[0.1] * 768] * 5
        mock_embedder.get_stats.return_value = {'total_tokens': 100, 'estimated_cost_usd': 0.0}
        
        mock_chroma = MagicMock()
        mock_metadata_extractor = MagicMock()
        mock_metadata_extractor.extract_all.return_value = {
            'category': '保障责任',
            'entity_role': '保险人',
            'keywords': ['重疾', '给付'],
            'section_id': '1.1',
            'parent_section': '保险责任'
        }
        
        mock_repo = MagicMock()
        mock_repo.get_product.return_value = sample_product
        
        # 创建Docling模式索引器
        indexer = PolicyIndexer(
            embedder=mock_embedder,
            chroma_store=mock_chroma,
            metadata_extractor=mock_metadata_extractor,
            use_docling=True,
            repo=mock_repo
        )
        
        # Mock DoclingParser
        from src.indexing.parsers.base import DocElement, DocTable
        mock_parsed = MagicMock()
        mock_parsed.elements = [
            DocElement(type='heading', content='保险责任', page_number=1, level=2),
            DocElement(type='text', content='被保险人确诊重疾，按基本保额给付。', page_number=1),
            DocTable(
                type='table',
                content='[TABLE]',
                page_number=10,
                headers=['年龄', '保费'],
                rows=[['30', '1000'], ['40', '1500']]
            )
        ]
        indexer.docling_parser.parse = MagicMock(return_value=mock_parsed)
        
        # Mock PDF存在
        with patch('pathlib.Path.exists', return_value=True):
            chunks = indexer.index_document(
                sample_document,
                "data/raw/test.pdf",
                update_bm25=False
            )
        
        # 验证
        assert len(chunks) > 0
        assert all(c.document_id == sample_document.id for c in chunks)
        assert all(c.company == sample_product.company for c in chunks)
        
        # 验证新字段存在
        for chunk in chunks:
            assert hasattr(chunk, 'section_path')
            assert hasattr(chunk, 'table_refs')
            assert isinstance(chunk.table_refs, list)
        
        # 验证ChromaDB调用
        mock_chroma.add_chunks.assert_called_once_with(chunks)
        
        print(f"\n✓ 端到端索引测试通过: {len(chunks)} chunks")
    
    @pytest.mark.integration
    def test_legacy_mode_indexing(self, sample_product, sample_document):
        """测试Legacy模式端到端索引（mock版本）"""
        # Mock所有依赖
        mock_embedder = MagicMock()
        mock_embedder.embed_batch.return_value = [[0.1] * 768] * 3
        mock_embedder.get_stats.return_value = {'total_tokens': 50, 'estimated_cost_usd': 0.0}
        
        mock_chroma = MagicMock()
        mock_metadata_extractor = MagicMock()
        mock_metadata_extractor.extract_all.return_value = {
            'category': '保障责任',
            'entity_role': '保险人',
            'keywords': ['重疾'],
            'section_id': '1.1',
            'parent_section': '保险责任'
        }
        
        mock_repo = MagicMock()
        mock_repo.get_product.return_value = sample_product
        
        # 创建Legacy模式索引器
        indexer = PolicyIndexer(
            embedder=mock_embedder,
            chroma_store=mock_chroma,
            metadata_extractor=mock_metadata_extractor,
            use_docling=False,
            repo=mock_repo
        )
        
        # Mock Markdown文件
        sample_markdown = """# 测试保险产品

## 保险责任

被保险人确诊重疾，按基本保额给付。
"""
        
        with patch('pathlib.Path.exists', return_value=True):
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = sample_markdown
                
                chunks = indexer.index_document(
                    sample_document,
                    "data/processed/test.md",
                    update_bm25=False
                )
        
        # 验证
        assert len(chunks) > 0
        
        # Legacy模式也应该有section_path（通过MarkdownChunker）
        for chunk in chunks:
            assert hasattr(chunk, 'section_path')
            assert hasattr(chunk, 'table_refs')
            assert chunk.table_refs == []  # Legacy模式无费率表
        
        print(f"\n✓ Legacy模式索引测试通过: {len(chunks)} chunks")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
