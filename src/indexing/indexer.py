"""索引器：Markdown → PolicyChunk → ChromaDB

负责将VERIFIED的Markdown文档切分、向量化、索引到ChromaDB。

核心流程：
1. 使用MarkdownHeaderTextSplitter按标题层级切分
2. 使用MetadataExtractor提取元数据
3. 使用OpenAI Embedder生成向量
4. 保存到ChromaDB和BM25索引

根据 spec.md §FR-009 和 tasks.md §T023 实施。
"""
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from langchain_text_splitters import MarkdownHeaderTextSplitter

from src.common.models import PolicyChunk, PolicyDocument
from src.common.repository import SQLiteRepository
from src.indexing.embedding.bge import BGEEmbedder
from src.indexing.vector_store.chroma import ChromaDBStore
from src.indexing.vector_store.hybrid_retriever import BM25Index
from src.indexing.metadata_extractor import MetadataExtractor
from src.indexing.chunker import SemanticChunker

logger = logging.getLogger(__name__)


class PolicyIndexer:
    """保险条款索引器
    
    将Markdown文档转换为可检索的PolicyChunk向量。
    
    特性：
    - 语义感知切分（按标题层级）
    - 自动元数据提取
    - 批量向量化
    - 20%重叠上下文
    - 表格完整性保护
    """
    
    # 切分配置
    CHUNK_SIZE = 750  # 目标chunk大小（tokens）
    CHUNK_OVERLAP = 150  # 20% 重叠（约150 tokens）
    
    # 标题层级配置（用于MarkdownHeaderTextSplitter）
    HEADERS_TO_SPLIT_ON = [
        ("#", "L1"),      # 产品名称
        ("##", "L2"),     # 章节标题
        ("###", "L3"),    # 条款标题
    ]
    
    def __init__(
        self,
        embedder: Optional[BGEEmbedder] = None,
        chroma_store: Optional[ChromaDBStore] = None,
        metadata_extractor: Optional[MetadataExtractor] = None,
        bm25_index: Optional[BM25Index] = None,
        semantic_chunker: Optional[SemanticChunker] = None,
        repo=None  # P0增强
    ):
        """初始化索引器
        
        Args:
            embedder: OpenAI Embedder实例
            chroma_store: ChromaDB存储实例
            metadata_extractor: 元数据提取器实例
            bm25_index: BM25索引实例（可选）
            semantic_chunker: 语义切分器实例（可选，用于表格处理）
            repo: Repository实例（可选，P0增强）
        """
        # 初始化组件
        self.repo = repo or SQLiteRepository()
        self.md_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=self.HEADERS_TO_SPLIT_ON,
            strip_headers=False  # 保留标题
        )
        self.metadata_extractor = metadata_extractor or MetadataExtractor()
        self.embedder = embedder or BGEEmbedder()  # Use BGEEmbedder
        self.chroma_store = chroma_store or ChromaDBStore()
        self.bm25_index = bm25_index or BM25Index()
        self.semantic_chunker = semantic_chunker or SemanticChunker()
        
        # P0增强: 保存repository引用
        if repo is None:
            from src.common.repository import repository
            repo = repository
        self.repo = repo
        
        # 初始化Markdown切分器
        self.md_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=self.HEADERS_TO_SPLIT_ON,
            strip_headers=False  # 保留标题
        )
        
        logger.info("初始化PolicyIndexer")
    
    def index_document(
        self,
        document: PolicyDocument,
        markdown_path: str,
        update_bm25: bool = True
    ) -> List[PolicyChunk]:
        """索引单个文档
        
        Args:
            document: PolicyDocument对象
            markdown_path: Markdown文件路径
            update_bm25: 是否更新BM25索引
        
        Returns:
            生成的PolicyChunk列表
        
        Raises:
            FileNotFoundError: Markdown文件不存在
            ValueError: 文档未VERIFIED
        """
        if document.verification_status != 'VERIFIED':
            raise ValueError(f"文档 {document.id} 未通过审核，状态={document.verification_status}")
        
        markdown_path = Path(markdown_path)
        if not markdown_path.exists():
            raise FileNotFoundError(f"Markdown文件不存在: {markdown_path}")
        
        logger.info(f"开始索引文档: {document.filename} (ID: {document.id[:8]}...)")
        
        # 0. 获取产品信息 (P0增强)
        product = self.repo.get_product(document.product_id)
        if not product:
            raise ValueError(f"未找到产品: {document.product_id}")
        
        logger.info(f"产品信息: {product.company} - {product.name} ({product.product_code})")
        
        # 1. 读取Markdown内容
        with open(markdown_path, 'r', encoding='utf-8') as f:
            markdown_content = f.read()
        
        # 2. 切分文档
        chunks = self._split_markdown(markdown_content, document, product)
        
        logger.info(f"切分为 {len(chunks)} 个chunks")
        
        # 2.5. 处理表格（提取为独立chunks）
        chunks = self.semantic_chunker.process_chunks(chunks, document.id)
        
        logger.info(f"表格处理后共 {len(chunks)} 个chunks")
        
        # 3. 提取元数据
        chunks = self._enrich_metadata(chunks)
        
        # 4. 生成embeddings
        chunks = self._generate_embeddings(chunks)
        
        # 5. 保存到ChromaDB
        self.chroma_store.add_chunks(chunks)
        
        logger.info(f"已保存 {len(chunks)} 个chunks到ChromaDB")
        
        # 6. 更新BM25索引
        if update_bm25 and self.bm25_index:
            for chunk in chunks:
                self.bm25_index.add_chunk(chunk)
            logger.info(f"已更新BM25索引")
        
        return chunks
    
    def _split_markdown(
        self,
        markdown_content: str,
        document: PolicyDocument,
        product
    ) -> List[PolicyChunk]:
        """切分Markdown文档
        
        使用MarkdownHeaderTextSplitter按标题层级切分。
        
        Args:
            markdown_content: Markdown内容
            document: PolicyDocument对象
            product: Product对象
        
        Returns:
            PolicyChunk列表（未填充embedding）
        """
        # 使用langchain的MarkdownHeaderTextSplitter
        splits = self.md_splitter.split_text(markdown_content)
        
        chunks = []
        for i, split in enumerate(splits):
            # 提取内容和标题信息
            content = split.page_content
            metadata = split.metadata
            
            # 提取层级信息
            level = self._determine_level(metadata)
            section_title = self._extract_section_title(metadata)
            
            # 创建PolicyChunk
            chunk = PolicyChunk(
                id=str(uuid.uuid4()),
                document_id=document.id,
                company=product.company,
                product_code=product.product_code,
                product_name=product.name,
                doc_type=document.doc_type,  # 传递文档类型
                content=content,
                section_id="",  # 暂时为空，稍后由enrich_metadata填充
                section_title=section_title or "",
                level=level,
                chunk_index=i,
                created_at=datetime.now()
            )
            
            chunks.append(chunk)
        
        logger.info(f"MarkdownHeaderTextSplitter生成 {len(chunks)} 个chunks")
        if chunks:
            logger.info(f"DEBUG: Created chunk[0] with doc_type='{chunks[0].doc_type}' (type: {type(chunks[0].doc_type)})")
        
        return chunks
    
    def _determine_level(self, metadata: Dict[str, str]) -> int:
        """确定标题层级
        
        Args:
            metadata: split的metadata字典
        
        Returns:
            标题层级（1-3）
        """
        if 'L3' in metadata:
            return 3
        elif 'L2' in metadata:
            return 2
        elif 'L1' in metadata:
            return 1
        return 1
    
    def _extract_section_title(self, metadata: Dict[str, str]) -> Optional[str]:
        """提取章节标题
        
        Args:
            metadata: split的metadata字典
        
        Returns:
            章节标题
        """
        # 优先使用最深层级的标题
        for level in ['L3', 'L2', 'L1']:
            if level in metadata:
                return metadata[level]
        return None
    
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
                # 构建Markdown路径
                md_path = Path(f"data/processed/{doc.id}.md")
                
                if not md_path.exists():
                    logger.warning(f"Markdown文件不存在: {md_path}，跳过")
                    stats['failed'] += 1
                    continue
                
                # 索引文档
                chunks = self.index_document(doc, str(md_path), update_bm25=update_bm25)
                
                stats['total_chunks'] += len(chunks)
                stats['success'] += 1
                
                logger.info(f"✅ {doc.filename}: {len(chunks)} chunks")
                
            except Exception as e:
                logger.error(f"索引文档 {doc.filename} 失败: {e}")
                stats['failed'] += 1
                stats['errors'].append(f"{doc.filename}: {str(e)}")
        
        logger.info(f"索引重建完成！成功: {stats['success']}, 失败: {stats['failed']}, "
                   f"总chunks: {stats['total_chunks']}")
        
        return stats


def create_indexer(
    embedder: Optional[BGEEmbedder] = None,
    chroma_store: Optional[ChromaDBStore] = None,
    metadata_extractor: Optional[MetadataExtractor] = None,
    bm25_index: Optional[BM25Index] = None,
    semantic_chunker: Optional[SemanticChunker] = None
) -> PolicyIndexer:
    """工厂函数：创建PolicyIndexer实例
    
    Args:
        embedder: OpenAI Embedder实例（可选，自动创建）
        chroma_store: ChromaDB存储实例（可选，自动创建）
        metadata_extractor: 元数据提取器实例（可选，自动创建）
        bm25_index: BM25索引实例（可选）
        semantic_chunker: 语义切分器实例（可选，自动创建）
    
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
    
    if semantic_chunker is None:
        from src.indexing.chunker import get_semantic_chunker
        semantic_chunker = get_semantic_chunker()
    
    return PolicyIndexer(
        embedder=embedder,
        chroma_store=chroma_store,
        metadata_extractor=metadata_extractor,
        bm25_index=bm25_index,
        semantic_chunker=semantic_chunker
    )

