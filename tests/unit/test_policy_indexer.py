import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.indexing.indexer import PolicyIndexer
from src.common.models import PolicyDocument, PolicyChunk


@pytest.fixture
def mock_components():
    """模拟所有依赖组件"""
    embedder = MagicMock()
    embedder.embed_batch.return_value = [[0.1] * 768 for _ in range(3)]  # BGE-M3维度
    embedder.get_stats.return_value = {
        'total_tokens': 100,
        'estimated_cost_usd': 0.0001
    }
    
    chroma_store = MagicMock()
    metadata_extractor = MagicMock()
    metadata_extractor.extract_all.return_value = {
        'category': '保障责任',
        'entity_role': '保险人',
        'keywords': ['重疾', '给付'],
        'section_id': '1.2.3',
        'parent_section': '保险责任'
    }
    
    bm25_index = MagicMock()
    
    repo = MagicMock()
    product = MagicMock()
    product.company = "测试保险公司"
    product.product_code = "TEST001"
    product.name = "测试产品"
    repo.get_product.return_value = product
    
    return {
        'embedder': embedder,
        'chroma_store': chroma_store,
        'metadata_extractor': metadata_extractor,
        'bm25_index': bm25_index,
        'repo': repo,
        'product': product
    }


@pytest.fixture
def sample_document():
    """示例PolicyDocument"""
    return PolicyDocument(
        id="test-doc-id",
        product_id="test-product-id",
        filename="test.pdf",
        local_path="data/test.pdf",
        doc_type="产品条款",  # 修正为正确的枚举值
        verification_status="VERIFIED",
        created_at=datetime.now()
    )


@pytest.fixture
def sample_markdown():
    """示例Markdown内容"""
    return """# 测试保险产品

## 保险责任

### 重大疾病保险金

被保险人在合同生效后确诊重大疾病，按基本保额给付。

### 身故保险金

被保险人身故，按基本保额给付。

## 责任免除

因下列情形之一导致被保险人身故或重大疾病的，本公司不承担给付保险金的责任：
1. 投保人对被保险人的故意杀害
2. 被保险人故意犯罪或抗拒依法采取的刑事强制措施
"""


class TestPolicyIndexerDocling:
    """测试 Docling 模式的 PolicyIndexer"""
    
    def test_init_docling_mode(self, mock_components):
        """测试 Docling 模式初始化"""
        indexer = PolicyIndexer(
            embedder=mock_components['embedder'],
            chroma_store=mock_components['chroma_store'],
            metadata_extractor=mock_components['metadata_extractor'],
            bm25_index=mock_components['bm25_index'],
            use_docling=True,
            repo=mock_components['repo']
        )
        
        assert indexer.use_docling is True
        assert hasattr(indexer, 'docling_parser')
        assert hasattr(indexer, 'table_classifier')
        assert hasattr(indexer, 'table_serializer')
        assert hasattr(indexer, 'md_chunker')
    
    @patch('src.indexing.indexer.Path')
    def test_index_with_docling_no_tables(self, mock_path, mock_components, sample_document):
        """测试 Docling 模式索引（无费率表场景）"""
        # 模拟 PDF 存在
        mock_pdf_path = MagicMock(spec=Path)
        mock_pdf_path.exists.return_value = True
        mock_path.return_value = mock_pdf_path
        
        # 模拟 DoclingParser 返回
        mock_parsed_doc = MagicMock()
        mock_parsed_doc.elements = [
            MagicMock(type='heading', content='保险责任', page_number=1, bbox=None, level=2),
            MagicMock(type='text', content='被保险人确诊重疾，按基本保额给付。', page_number=1, bbox=None)
        ]
        
        indexer = PolicyIndexer(
            embedder=mock_components['embedder'],
            chroma_store=mock_components['chroma_store'],
            metadata_extractor=mock_components['metadata_extractor'],
            bm25_index=mock_components['bm25_index'],
            use_docling=True,
            repo=mock_components['repo']
        )
        
        indexer.docling_parser.parse = MagicMock(return_value=mock_parsed_doc)
        
        chunks = indexer.index_document(sample_document, "data/test.pdf", update_bm25=False)
        
        # 验证
        assert len(chunks) > 0
        assert all(isinstance(c, PolicyChunk) for c in chunks)
        assert all(c.document_id == sample_document.id for c in chunks)
        assert all(c.company == "测试保险公司" for c in chunks)
        assert all(c.product_code == "TEST001" for c in chunks)
        # Phase 6 新增字段验证
        assert all(hasattr(c, 'section_path') for c in chunks)
        assert all(hasattr(c, 'table_refs') for c in chunks)


class TestPolicyIndexerLegacy:
    """测试 Legacy 模式的 PolicyIndexer"""
    
    def test_init_legacy_mode(self, mock_components):
        """测试 Legacy 模式初始化"""
        indexer = PolicyIndexer(
            embedder=mock_components['embedder'],
            chroma_store=mock_components['chroma_store'],
            metadata_extractor=mock_components['metadata_extractor'],
            bm25_index=mock_components['bm25_index'],
            use_docling=False,
            repo=mock_components['repo']
        )
        
        assert indexer.use_docling is False
        assert not hasattr(indexer, 'docling_parser')
        assert hasattr(indexer, 'md_chunker')  # 仍需要 MarkdownChunker
    
    @patch('builtins.open')
    @patch('src.indexing.indexer.Path')
    def test_index_legacy_markdown(self, mock_path, mock_open, mock_components, sample_document, sample_markdown):
        """测试 Legacy 模式索引 Markdown"""
        # 模拟文件存在
        mock_md_path = MagicMock(spec=Path)
        mock_md_path.exists.return_value = True
        mock_path.return_value = mock_md_path
        
        # 模拟文件读取
        mock_open.return_value.__enter__.return_value.read.return_value = sample_markdown
        
        indexer = PolicyIndexer(
            embedder=mock_components['embedder'],
            chroma_store=mock_components['chroma_store'],
            metadata_extractor=mock_components['metadata_extractor'],
            bm25_index=mock_components['bm25_index'],
            use_docling=False,
            repo=mock_components['repo']
        )
        
        chunks = indexer.index_document(sample_document, "data/processed/test.md", update_bm25=False)
        
        # 验证
        assert len(chunks) > 0
        assert all(isinstance(c, PolicyChunk) for c in chunks)
        # Legacy 模式也应支持 section_path（通过 MarkdownChunker）
        assert all(hasattr(c, 'section_path') for c in chunks)
        # Legacy 模式 table_refs 应为空
        assert all(c.table_refs == [] for c in chunks)


class TestMarkdownConversion:
    """测试 Markdown 转换辅助方法"""
    
    def test_element_to_markdown_heading(self, mock_components):
        """测试标题转 Markdown"""
        indexer = PolicyIndexer(use_docling=True, repo=mock_components['repo'])
        
        elem = MagicMock(type='heading', content='保险责任', level=2)
        result = indexer._element_to_markdown(elem)
        
        assert result == '\n## 保险责任\n'
    
    def test_element_to_markdown_text(self, mock_components):
        """测试文本转 Markdown"""
        indexer = PolicyIndexer(use_docling=True, repo=mock_components['repo'])
        
        elem = MagicMock(type='text', content='这是一段文本内容')
        result = indexer._element_to_markdown(elem)
        
        assert result == '这是一段文本内容'
    
    def test_table_to_markdown(self, mock_components):
        """测试表格转 Markdown"""
        from src.indexing.parsers.base import DocTable
        
        indexer = PolicyIndexer(use_docling=True, repo=mock_components['repo'])
        
        table = DocTable(
            type='table',
            content='[TABLE]',
            page_number=1,
            headers=['年龄', '保费'],
            rows=[['30', '1000'], ['40', '1500']]
        )
        
        result = indexer._table_to_markdown(table)
        
        assert '| 年龄 | 保费 |' in result
        assert '| --- | --- |' in result
        assert '| 30 | 1000 |' in result
        assert '| 40 | 1500 |' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
