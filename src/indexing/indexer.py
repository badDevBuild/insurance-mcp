"""索引器:PDF/Markdown → PolicyChunk → ChromaDB

负责将VERIFIED的文档切分、向量化、索引到ChromaDB。

核心流程（Phase 6 - Docling Integration）：
1. 使用DoclingParser解析PDF → 结构化元素
2. 使用TableClassifier识别费率表 → 导出CSV
3. 使用MarkdownChunker智能分块（含breadcrumb路径）
4. 使用MetadataExtractor提取元数据
5. 使用BGE Embedder生成向量
6. 保存到ChromaDB和BM25索引

根据 spec.md §FR-004, FR-009, FR-009a 和 tasks.md §T052 实施。
"""
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from src.common.models import PolicyChunk, PolicyDocument
from src.common.repository import SQLiteRepository
from src.common.config import config
from src.indexing.embedding.bge import BGEEmbedder
from src.indexing.vector_store.chroma import ChromaDBStore
from src.indexing.vector_store.hybrid_retriever import BM25Index
from src.indexing.metadata_extractor import MetadataExtractor
from src.indexing.parsers.docling_parser import DoclingParser
from src.indexing.parsers.base import DocTable
from src.indexing.analyzers.table_classifier import TableClassifier
from src.indexing.analyzers.table_serializer import TableSerializer
from src.indexing.chunkers.markdown_chunker import MarkdownChunker

logger = logging.getLogger(__name__)


class PolicyIndexer:
    """保险条款索引器（Phase 6: Docling Integration）
    
    将PDF文档转换为可检索的PolicyChunk向量。
    
    特性（Phase 6增强）：
    - Docling高精度PDF解析（多栏识别）
    - 费率表自动分离导出（CSV + metadata.json）
    - 智能Markdown分块（含章节路径breadcrumb）
    - 自动元数据提取
    - 批量向量化
    - 表格引用跟踪
    """
    
    # 切分配置（FR-009）
    CHUNK_SIZE = 800  # 目标chunk大小（tokens）512-1024范围
    CHUNK_OVERLAP = 128  # 重叠（tokens）
    
    def __init__(
        self,
        embedder: Optional[BGEEmbedder] = None,
        chroma_store: Optional[ChromaDBStore] = None,
        metadata_extractor: Optional[MetadataExtractor] = None,
        bm25_index: Optional[BM25Index] = None,
        use_docling: bool = True,  # Phase 6: 启用Docling解析
        repo=None
    ):
        """初始化索引器
        
        Args:
            embedder: BGE Embedder实例
            chroma_store: ChromaDB存储实例
            metadata_extractor: 元数据提取器实例
            bm25_index: BM25索引实例（可选）
            use_docling: 是否使用Docling解析PDF（Phase 6）
            repo: Repository实例（可选）
        """
        # 初始化核心组件
        self.repo = repo or SQLiteRepository()
        self.metadata_extractor = metadata_extractor or MetadataExtractor()
        self.embedder = embedder or BGEEmbedder()
        self.chroma_store = chroma_store or ChromaDBStore()
        self.bm25_index = bm25_index or BM25Index()
        
        # Phase 6: 通用组件（两种模式都需要）
        self.md_chunker = MarkdownChunker(
            chunk_size=self.CHUNK_SIZE,
            chunk_overlap=self.CHUNK_OVERLAP
        )
        
        # Phase 6: Docling专用组件
        self.use_docling = use_docling
        if use_docling:
            self.docling_parser = DoclingParser()
            self.table_classifier = TableClassifier()
            self.table_serializer = TableSerializer()
            logger.info("初始化PolicyIndexer (Docling模式启用)")
        else:
            logger.info("初始化PolicyIndexer (Legacy模式)")
    
    def index_document(
        self,
        document: PolicyDocument,
        source_path: str,
        update_bm25: bool = True
    ) -> List[PolicyChunk]:
        """索引单个文档
        
        Phase 6增强：支持PDF直接解析（use_docling=True）或Markdown（Legacy）
        
        Args:
            document: PolicyDocument对象
            source_path: 源文件路径（PDF或Markdown，根据use_docling自动判断）
            update_bm25: 是否更新BM25索引
        
        Returns:
            生成的PolicyChunk列表
        
        Raises:
            FileNotFoundError: 源文件不存在
            ValueError: 文档未VERIFIED
        """
        if document.verification_status != 'VERIFIED':
            raise ValueError(f"文档 {document.id} 未通过审核，状态={document.verification_status}")
        
        source_path = Path(source_path)
        if not source_path.exists():
            raise FileNotFoundError(f"源文件不存在: {source_path}")
        
        logger.info(f"开始索引文档: {document.filename} (ID: {document.id[:8]}...)")
        
        # 0. 获取产品信息
        product = self.repo.get_product(document.product_id)
        if not product:
            raise ValueError(f"未找到产品: {document.product_id}")
        
        logger.info(f"产品信息: {product.company} - {product.name} ({product.product_code})")
        
        # Phase 6: 分支处理
        if self.use_docling:
            chunks = self._index_with_docling(source_path, document, product)
        else:
            chunks = self._index_legacy(source_path, document, product)
        
        logger.info(f"最终生成 {len(chunks)} 个chunks")
        
        # 3. 生成embeddings
        chunks = self._generate_embeddings(chunks)
        
        # 4. 保存到ChromaDB
        self.chroma_store.add_chunks(chunks)
        
        logger.info(f"已保存 {len(chunks)} 个chunks到ChromaDB")
        
        # 5. 更新BM25索引
        if update_bm25 and self.bm25_index:
            for chunk in chunks:
                self.bm25_index.add_chunk(chunk)
            logger.info(f"已更新BM25索引")
        
        return chunks
    
    def _index_with_docling(
        self,
        pdf_path: Path,
        document: PolicyDocument,
        product
    ) -> List[PolicyChunk]:
        """Phase 6: 使用Docling解析PDF并生成chunks
        
        流程：
        1. DoclingParser解析PDF → ParsedDocument
        2. TableClassifier识别费率表 → TableSerializer导出CSV
        3. 转换为Markdown（保留普通表格）
        4. MarkdownChunker智能分块（含breadcrumb）
        5. 填充metadata（含section_path, table_refs）
        
        Args:
            pdf_path: PDF文件路径
            document: PolicyDocument对象
            product: Product对象
        
        Returns:
            PolicyChunk列表（未填充embedding）
        """
        logger.info("[Docling] 开始解析PDF...")
        
        # Step 1: 解析PDF
        parsed_doc = self.docling_parser.parse(pdf_path)
        logger.info(f"[Docling] 解析完成，共 {len(parsed_doc.elements)} 个元素")
        
        # Step 2: 分离费率表
        rate_table_refs = []  # 存储费率表UUID
        markdown_elements = []  # 用于构建Markdown的元素
        
        for elem in parsed_doc.elements:
            if isinstance(elem, DocTable):
                is_rate = self.table_classifier.is_rate_table(elem)
                
                if is_rate and config.ENABLE_TABLE_SEPARATION:
                    # 导出费率表到CSV
                    table_id = self.table_serializer.serialize_rate_table(
                        table=elem,
                        product_code=product.product_code,
                        source_pdf=str(pdf_path)
                    )
                    rate_table_refs.append(table_id)
                    logger.info(f"[Docling] 导出费率表: {table_id} (page {elem.page_number})")
                    
                    # 在markdown中插入引用标记
                    markdown_elements.append(f"\n[费率表: {table_id}]\n")
                else:
                    # 普通表格：转为Markdown表格
                    markdown_elements.append(self._table_to_markdown(elem))
            else:
                # 文本或标题
                markdown_elements.append(self._element_to_markdown(elem))
        
        # Step 3: 合并为Markdown
        markdown_content = '\n'.join(markdown_elements)
        
        logger.info(f"[Docling] 费率表分离完成: {len(rate_table_refs)} 张")
        
        # Step 4: MarkdownChunker智能分块
        chunk_dicts = self.md_chunker.chunk_with_hierarchy(
            markdown=markdown_content,
            doc_id=document.id
        )
        
        logger.info(f"[Docling] 智能分块完成: {len(chunk_dicts)} 个chunks")
        
        # Step 5: 转换为PolicyChunk对象
        chunks = []
        for chunk_dict in chunk_dicts:
            chunk = PolicyChunk(
                id=str(uuid.uuid4()),
                document_id=document.id,
                company=product.company,
                product_code=product.product_code,
                product_name=product.name,
                doc_type=document.doc_type,
                content=chunk_dict['content'],
                section_id=chunk_dict['section_id'],
                section_title=chunk_dict['section_title'],
                section_path=chunk_dict['section_path'],  # Phase 6新增
                level=chunk_dict['level'],
                chunk_index=chunk_dict['chunk_index'],
                table_refs=rate_table_refs,  # Phase 6新增：所有费率表引用
                created_at=datetime.now()
            )
            chunks.append(chunk)
        
        # Step 6: 使用MetadataExtractor补充元数据
        chunks = self._enrich_metadata(chunks)
        
        return chunks
    
    def _index_legacy(
        self,
        markdown_path: Path,
        document: PolicyDocument,
        product
    ) -> List[PolicyChunk]:
        """Legacy模式：直接处理Markdown文件（兼容旧流程）
        
        注意：此模式不支持section_path和table_refs字段
        """
        logger.info("[Legacy] 使用传统Markdown切分...")
        
        # 读取Markdown
        with open(markdown_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
        
        # 使用MarkdownChunker（不需要Docling解析）
        chunk_dicts = self.md_chunker.chunk_with_hierarchy(
            markdown=markdown_content,
            doc_id=document.id
        )
        
        logger.info(f"[Legacy] 切分完成: {len(chunk_dicts)} 个chunks")
        
        # 转换为PolicyChunk
        chunks = []
        for chunk_dict in chunk_dicts:
            chunk = PolicyChunk(
                id=str(uuid.uuid4()),
                document_id=document.id,
                company=product.company,
                product_code=product.product_code,
                product_name=product.name,
                doc_type=document.doc_type,
                content=chunk_dict['content'],
                section_id=chunk_dict['section_id'],
                section_title=chunk_dict['section_title'],
                section_path=chunk_dict['section_path'],
                level=chunk_dict['level'],
                chunk_index=chunk_dict['chunk_index'],
                table_refs=[],  # Legacy模式无表格引用
                created_at=datetime.now()
            )
            chunks.append(chunk)
        
        # 补充元数据
        chunks = self._enrich_metadata(chunks)
        
        return chunks
    
    def _element_to_markdown(self, elem) -> str:
        """将DocElement转为Markdown格式"""
        if elem.type == 'heading':
            prefix = '#' * elem.level
            return f"\n{prefix} {elem.content}\n"
        else:
            return elem.content
    
    def _table_to_markdown(self, table: DocTable) -> str:
        """将普通表格转为Markdown表格格式"""
        lines = []
        
        # 表头
        if table.headers:
            lines.append('| ' + ' | '.join(table.headers) + ' |')
            lines.append('| ' + ' | '.join(['---'] * len(table.headers)) + ' |')
        
        # 表格行
        for row in table.rows:
            lines.append('| ' + ' | '.join(row) + ' |')
        
        return '\n' + '\n'.join(lines) + '\n'
    
    
    def _enrich_metadata(self, chunks: List[PolicyChunk]) -> List[PolicyChunk]:
        """使用MetadataExtractor填充元数据
        
        Args:
            chunks: PolicyChunk列表
        
        Returns:
            填充了元数据的PolicyChunk列表
        """
        logger.info("提取元数据...")
        
        for chunk in chunks:
            # 提取所有元数据
            metadata = self.metadata_extractor.extract_all(
                content=chunk.content,
                section_title=chunk.section_title
            )
            
            # 填充到chunk
            chunk.category = metadata['category']
            chunk.entity_role = metadata['entity_role']
            chunk.keywords = ','.join(metadata['keywords'])  # 转换为逗号分隔字符串
            chunk.section_id = metadata['section_id']
            chunk.parent_section = metadata['parent_section']
            # DEBUG LOG
            # logger.debug(f"Enriched chunk {chunk.id[:8]}: doc_type={chunk.doc_type}")
        
        logger.info("元数据提取完成")
        
        return chunks
    
    def _generate_embeddings(self, chunks: List[PolicyChunk]) -> List[PolicyChunk]:
        """批量生成embeddings
        
        Args:
            chunks: PolicyChunk列表
        
        Returns:
            填充了embedding_vector的PolicyChunk列表
        """
        logger.info("生成embeddings...")
        
        # 提取所有内容
        contents = [chunk.content for chunk in chunks]
        
        # 批量生成embeddings
        embeddings = self.embedder.embed_batch(contents)
        
        # 填充到chunks
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding_vector = embedding
        
        # 打印统计信息
        stats = self.embedder.get_stats()
        logger.info(f"Embeddings生成完成，使用 {stats['total_tokens']} tokens，"
                   f"成本约 ${stats['estimated_cost_usd']:.6f}")
        
        return chunks
    
    def rebuild_index(
        self,
        reset: bool = False,
        update_bm25: bool = True
    ) -> Dict[str, Any]:
        """重建整个索引
        
        从数据库读取所有VERIFIED文档，重新索引。
        
        Args:
            reset: 是否先清空现有索引
            update_bm25: 是否同时重建BM25索引
        
        Returns:
            统计信息字典
        """
        logger.info("开始重建索引...")
        
        if reset:
            logger.warning("清空现有索引...")
            self.chroma_store.reset()
            if self.bm25_index:
                self.bm25_index = BM25Index()
        
        # 获取所有VERIFIED文档
        repo = SQLiteRepository()
        documents = repo.list_documents(verification_status='VERIFIED')
        
        if not documents:
            logger.warning("没有VERIFIED文档可索引")
            return {
                'total_documents': 0,
                'total_chunks': 0,
                'success': 0,
                'failed': 0
            }
        
        logger.info(f"找到 {len(documents)} 个VERIFIED文档")
        
        # 逐个索引
        stats = {
            'total_documents': len(documents),
            'total_chunks': 0,
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        for doc in documents:
            try:
                # 根据模式选择源文件
                if self.use_docling:
                    # Docling模式：使用原始PDF
                    source_path = Path(doc.local_path)
                else:
                    # Legacy模式：使用Markdown
                    source_path = Path(f"data/processed/{doc.id}.md")
                
                if not source_path.exists():
                    logger.warning(f"源文件不存在: {source_path}，跳过")
                    stats['failed'] += 1
                    continue
                
                # 索引文档
                chunks = self.index_document(doc, str(source_path), update_bm25=update_bm25)
                
                stats['total_chunks'] += len(chunks)
                stats['success'] += 1
                
                logger.info(f"✅ {doc.filename}: {len(chunks)} chunks")
                
            except Exception as e:
                logger.error(f"索引文档 {doc.filename} 失败: {e}")
                stats['failed'] += 1
                stats['errors'].append(f"{doc.filename}: {str(e)}")
        
        logger.info(f"索引重建完成！成功: {stats['success']}, 失败: {stats['failed']}, "
                   f"总chunks: {stats['total_chunks']}")
        
        # 保存BM25索引
        if update_bm25 and self.bm25_index:
            try:
                from src.common.config import config
                self.bm25_index.save(str(config.BM25_INDEX_PATH))
                logger.info(f"BM25索引已保存到 {config.BM25_INDEX_PATH}")
            except Exception as e:
                logger.error(f"保存BM25索引失败: {e}")
        
        return stats


def create_indexer(
    embedder: Optional[BGEEmbedder] = None,
    chroma_store: Optional[ChromaDBStore] = None,
    metadata_extractor: Optional[MetadataExtractor] = None,
    bm25_index: Optional[BM25Index] = None,
    use_docling: bool = True
) -> PolicyIndexer:
    """工厂函数：创建PolicyIndexer实例
    
    Args:
        embedder: BGE Embedder实例（可选，自动创建）
        chroma_store: ChromaDB存储实例（可选，自动创建）
        metadata_extractor: 元数据提取器实例（可选，自动创建）
        bm25_index: BM25索引实例（可选）
        use_docling: 是否启用Docling模式（Phase 6）
    
    Returns:
        PolicyIndexer实例
    """
    if embedder is None:
        from src.indexing.embedding.bge import get_embedder
        embedder = get_embedder()
    
    if chroma_store is None:
        from src.indexing.vector_store.chroma import get_chroma_store
        chroma_store = get_chroma_store()
    
    if metadata_extractor is None:
        from src.indexing.metadata_extractor import get_metadata_extractor
        metadata_extractor = get_metadata_extractor()
    
    return PolicyIndexer(
        embedder=embedder,
        chroma_store=chroma_store,
        metadata_extractor=metadata_extractor,
        bm25_index=bm25_index,
        use_docling=use_docling
    )

