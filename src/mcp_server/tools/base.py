"""MCP工具基类和通用功能

提供MCP工具的基础结构和共享逻辑。
"""
from typing import Dict, Any, List, Optional
import logging
from pathlib import Path
from pydantic import BaseModel

from src.indexing.vector_store.chroma import ChromaDBStore, get_chroma_store
from src.indexing.vector_store.hybrid_retriever import HybridRetriever, create_hybrid_retriever, BM25Index
from src.indexing.embedding.bge import BGEEmbedder, get_embedder
from src.common.models import PolicyChunk, ClauseCategory, SourceRef
from src.common.config import config

logger = logging.getLogger(__name__)


def _load_bm25_index() -> Optional[BM25Index]:
    """加载BM25索引（如果存在）
    
    Returns:
        BM25Index实例，如果索引文件不存在则返回None
    """
    bm25_path = config.BM25_INDEX_PATH
    
    if not bm25_path.exists():
        logger.warning(f"BM25索引文件不存在: {bm25_path}，回退到纯语义检索")
        return None
    
    try:
        bm25_index = BM25Index()
        bm25_index.load(str(bm25_path))
        logger.info(f"成功加载BM25索引: {bm25_path}")
        return bm25_index
    except Exception as e:
        logger.error(f"加载BM25索引失败: {e}")
        return None


class BaseTool:
    """MCP工具基类
    
    提供懒加载的检索器、嵌入器等资源。
    支持混合检索（BM25 + Dense），当BM25索引不存在时优雅降级。
    """
    
    def __init__(self):
        """初始化工具，加载检索器等资源"""
        # 懒加载资源，避免启动过慢
        self._chroma_store = None
        self._embedder = None
        self._retriever = None
        self._bm25_index = None
        self._bm25_loaded = False  # 标记是否已尝试加载BM25
    
    @property
    def chroma_store(self) -> ChromaDBStore:
        """ChromaDB存储实例（懒加载）"""
        if not self._chroma_store:
            self._chroma_store = get_chroma_store()
        return self._chroma_store
    
    @property
    def embedder(self) -> BGEEmbedder:
        """BGE嵌入器实例（懒加载）"""
        if not self._embedder:
            self._embedder = get_embedder()
        return self._embedder
    
    @property
    def bm25_index(self) -> Optional[BM25Index]:
        """BM25索引实例（懒加载，可能为None）"""
        if not self._bm25_loaded:
            self._bm25_index = _load_bm25_index()
            self._bm25_loaded = True
        return self._bm25_index
    
    @property
    def retriever(self) -> HybridRetriever:
        """获取混合检索器实例（单例模式）
        
        支持混合检索（BM25 + Dense），当BM25索引不存在时优雅降级到纯语义检索。
        """
        if not self._retriever:
            try:
                # 加载BM25索引
                bm25 = self.bm25_index
                
                # 创建混合检索器
                self._retriever = create_hybrid_retriever(
                    chroma_store=self.chroma_store,
                    bm25_index=bm25,  # 可能为None，这时只使用语义检索
                    chunks=[]  # 不重新构建索引，使用已加载的
                )
                
                if bm25:
                    logger.info("混合检索器初始化成功（BM25 + Dense）")
                else:
                    logger.info("混合检索器初始化成功（仅Dense模式）")
                    
            except Exception as e:
                logger.warning(f"初始化混合检索器失败: {e}，回退到基础ChromaStore")
                # 创建一个最小化的检索器作为回退
                self._retriever = create_hybrid_retriever(
                    chroma_store=self.chroma_store,
                    bm25_index=None,
                    chunks=[]
                )
        return self._retriever
    
    @property
    def has_bm25(self) -> bool:
        """检查是否有BM25索引可用"""
        return self.bm25_index is not None

    def _format_source_ref(self, chunk_data: Dict[str, Any]) -> SourceRef:
        """从Chunk数据构建SourceRef"""
        metadata = chunk_data.get('metadata', {})
        return SourceRef(
            product_name=metadata.get('product_name', '未知产品'),
            document_type=metadata.get('document_type', '产品条款'),
            pdf_path=metadata.get('pdf_path', metadata.get('filename', '未知文件')),
            page_number=metadata.get('page_number', 0),
            download_url=metadata.get('download_url', metadata.get('source_url', ''))
        )

    def embed_query(self, query: str) -> List[float]:
        """生成查询向量"""
        return self.embedder.embed_single(query)
