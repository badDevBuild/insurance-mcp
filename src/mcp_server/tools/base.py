"""MCP工具基类和通用功能

提供MCP工具的基础结构和共享逻辑。
"""
from typing import Dict, Any, List, Optional
import logging
from pydantic import BaseModel

from src.indexing.vector_store.chroma import ChromaDBStore, get_chroma_store
from src.indexing.vector_store.hybrid_retriever import HybridRetriever, create_hybrid_retriever, BM25Index
from src.indexing.vector_store.chroma import ChromaDBStore, get_chroma_store
from src.indexing.vector_store.hybrid_retriever import HybridRetriever, create_hybrid_retriever, BM25Index
from src.indexing.embedding.bge import BGEEmbedder, get_embedder
from src.common.models import PolicyChunk, ClauseCategory, SourceRef

logger = logging.getLogger(__name__)

class BaseTool:
    """MCP工具基类"""
    
    def __init__(self):
        """初始化工具，加载检索器等资源"""
        # 懒加载资源，避免启动过慢
        self._chroma_store = None
        self._embedder = None
        self._retriever = None
        self._bm25_index = None
    
    @property
    def chroma_store(self) -> ChromaDBStore:
        if not self._chroma_store:
            self._chroma_store = get_chroma_store()
        return self._chroma_store
    
    @property
    def embedder(self) -> BGEEmbedder:
        if not self._embedder:
            self._embedder = get_embedder()
        return self._embedder
    
    @property
    def retriever(self) -> HybridRetriever:
        """获取混合检索器实例（单例模式）"""
        if not self._retriever:
            # 加载BM25索引（如果存在）
            # 注意：这里简化处理，假设索引已构建。生产环境应更健壮地处理。
            # BM25索引通常较大，考虑内存占用。
            try:
                # 临时：这里简化为只使用Dense检索，后续集成BM25加载逻辑
                # 真正的混合检索需要先加载预构建的BM25索引
                self._retriever = create_hybrid_retriever(
                    chroma_store=self.chroma_store,
                    # bm25_index=... # TODO: 实现BM25索引加载
                    chunks=[] # 避免重新构建
                )
                # 临时Hack：手动禁用BM25部分，或者需要实现加载逻辑
            except Exception as e:
                logger.warning(f"初始化混合检索器失败: {e}，回退到基础ChromaStore")
                # 在实际工具实现中处理回退
        return self._retriever

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
