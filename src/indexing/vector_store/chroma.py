"""ChromaDB向量存储包装器

提供ChromaDB的封装，支持：
- Collection初始化和管理
- 向量存储和检索
- Metadata过滤查询
- 批量操作

根据 tasks.md §T022 和 data-model.md §ChromaDB Collection设计 实施。
"""
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from src.common.config import config
from src.common.models import PolicyChunk

logger = logging.getLogger(__name__)


class ChromaDBStore:
    """ChromaDB向量存储
    
    管理insurance_policy_chunks collection，支持：
    - PolicyChunk的CRUD操作
    - 语义相似度检索
    - Metadata过滤查询
    - 批量插入和更新
    
    Collection Schema:
    负责PolicyChunk的持久化存储和检索。
    
    特性：
    - 本地持久化
    - 元数据过滤
    - 批量添加
    """
    
    # Collection配置
    COLLECTION_NAME = "insurance_policy_chunks"
    VECTOR_DIMENSION = 512  # BAAI/bge-small-zh-v1.5
    DISTANCE_METRIC = "cosine"  # 余弦相似度
    
    def __init__(self, persist_directory: Optional[str] = None):
        """初始化ChromaDB客户端
        
        Args:
            persist_directory: 持久化目录（可选，从配置读取）
        """
        self.persist_dir = Path(persist_directory or config.VECTOR_STORE_DIR)
        
        # 确保目录存在
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化ChromaDB客户端（持久化模式）
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # 获取或创建collection
        self.collection = self._get_or_create_collection()
        
        logger.info(f"初始化ChromaDB存储，持久化目录={self.persist_dir}")
        logger.info(f"Collection '{self.COLLECTION_NAME}' 包含 {self.collection.count()} 个文档")
    
    def _get_or_create_collection(self):
        """获取或创建collection"""
        try:
            # 尝试获取现有collection
            collection = self.client.get_collection(
                name=self.COLLECTION_NAME,
                embedding_function=None  # 我们使用预先生成的embeddings
            )
            logger.debug(f"使用现有Collection '{self.COLLECTION_NAME}'")
        except Exception:
            # 创建新collection
            collection = self.client.create_collection(
                name=self.COLLECTION_NAME,
                embedding_function=None,
                metadata={
                    "description": "保险条款向量索引",
                    "dimension": self.VECTOR_DIMENSION,
                    "distance_metric": self.DISTANCE_METRIC
                }
            )
            logger.info(f"创建新Collection '{self.COLLECTION_NAME}'")
        
        return collection
    
    def add_chunk(self, chunk: PolicyChunk) -> str:
        """添加单个PolicyChunk
        
        Args:
            chunk: PolicyChunk对象
        
        Returns:
            chunk_id
        
        Raises:
            ValueError: embedding_vector为空
        """
        if not chunk.embedding_vector:
            raise ValueError(f"Chunk {chunk.id} 缺少embedding_vector")
        
        self.collection.add(
            ids=[chunk.id],
            documents=[chunk.content],
            embeddings=[chunk.embedding_vector],
            metadatas=[chunk.to_chroma_metadata()]
        )
        
        logger.debug(f"添加chunk {chunk.id[:8]}...")
        return chunk.id
    
    def add_chunks(self, chunks: List[PolicyChunk]) -> List[str]:
        """批量添加PolicyChunks
        
        Args:
            chunks: PolicyChunk列表
        
        Returns:
            chunk_id列表
        
        Raises:
            ValueError: 任何chunk缺少embedding_vector
        """
        if not chunks:
            return []
        
        # 验证所有chunks都有embedding
        for chunk in chunks:
            if not chunk.embedding_vector:
                raise ValueError(f"Chunk {chunk.id} 缺少embedding_vector")
        
        # 提取数据
        ids = [chunk.id for chunk in chunks]
        documents = [chunk.content for chunk in chunks]
        embeddings = [chunk.embedding_vector for chunk in chunks]
        metadatas = [chunk.to_chroma_metadata() for chunk in chunks]
        
        # 批量插入
        import json
        try:
            with open("debug_log.txt", "w") as f:
                f.write(f"Total chunks: {len(metadatas)}\n\n")
                for idx, meta in enumerate(metadatas):
                    f.write(f"=== Chunk {idx} ===\n")
                    f.write(f"Metadata: {json.dumps(meta, ensure_ascii=False)}\n")
                    for k, v in meta.items():
                        f.write(f"  Key: {k}, Type: {type(v)}, Value: {v}\n")
                    f.write("\n")
        except Exception as e:
            with open("debug_log.txt", "a") as f:
                f.write(f"DEBUG: Failed to log metadata: {e}\n")

        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas
        )
        
        logger.info(f"批量添加 {len(chunks)} 个chunks")
        return ids
    
    def update_chunk(self, chunk: PolicyChunk) -> str:
        """更新PolicyChunk
        
        Args:
            chunk: PolicyChunk对象
        
        Returns:
            chunk_id
        """
        if not chunk.embedding_vector:
            raise ValueError(f"Chunk {chunk.id} 缺少embedding_vector")
        
        self.collection.update(
            ids=[chunk.id],
            documents=[chunk.content],
            embeddings=[chunk.embedding_vector],
            metadatas=[chunk.to_chroma_metadata()]
        )
        
        logger.debug(f"更新chunk {chunk.id[:8]}...")
        return chunk.id
    
    def delete_chunk(self, chunk_id: str):
        """删除单个chunk
        
        Args:
            chunk_id: chunk ID
        """
        self.collection.delete(ids=[chunk_id])
        logger.debug(f"删除chunk {chunk_id[:8]}...")
    
    def delete_by_document(self, document_id: str) -> int:
        """删除指定文档的所有chunks
        
        Args:
            document_id: document ID
        
        Returns:
            删除的chunk数量
        """
        # 查询该文档的所有chunks
        results = self.collection.get(
            where={"document_id": document_id}
        )
        
        if results['ids']:
            self.collection.delete(ids=results['ids'])
            logger.info(f"删除文档 {document_id} 的 {len(results['ids'])} 个chunks")
            return len(results['ids'])
        
        return 0
    
    def get_chunk(self, chunk_id: str) -> Optional[PolicyChunk]:
        """获取单个chunk
        
        Args:
            chunk_id: chunk ID
        
        Returns:
            PolicyChunk对象，不存在则返回None
        """
        results = self.collection.get(
            ids=[chunk_id],
            include=["documents", "metadatas", "embeddings"]
        )
        
        if not results['ids']:
            return None
        
        # 构建PolicyChunk - from_chroma_result期望列表格式
        chunk_data = {
            'ids': [results['ids'][0]],
            'documents': [results['documents'][0]],
            'metadatas': [results['metadatas'][0]],
            'embeddings': [results['embeddings'][0]] if results['embeddings'] is not None and len(results['embeddings']) > 0 else None
        }
        
        return PolicyChunk.from_chroma_result(chunk_data)
    
    def search(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """语义相似度检索
        
        Args:
            query_embedding: 查询向量（1536维）
            n_results: 返回结果数量
            where: metadata过滤条件
            where_document: document内容过滤条件
        
        Returns:
            结果列表，每个结果包含：
            - id: chunk ID
            - document: chunk内容
            - metadata: chunk元数据
            - distance: 相似度距离
        
        Example:
            >>> # 基础查询
            >>> results = store.search(query_embedding, n_results=10)
            
            >>> # 按公司过滤
            >>> results = store.search(
            ...     query_embedding,
            ...     where={"company": "平安人寿"}
            ... )
            
            >>> # 按类别过滤
            >>> results = store.search(
            ...     query_embedding,
            ...     where={"category": "Exclusion"}
            ... )
            
            >>> # 组合过滤
            >>> results = store.search(
            ...     query_embedding,
            ...     where={
            ...         "$and": [
            ...             {"company": "平安人寿"},
            ...             {"category": "Exclusion"}
            ...         ]
            ...     }
            ... )
        """
        query_params = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"]
        }
        
        if where:
            query_params["where"] = where
        
        if where_document:
            query_params["where_document"] = where_document
        
        results = self.collection.query(**query_params)
        
        # 转换结果格式
        formatted_results = []
        for i in range(len(results['ids'][0])):
            formatted_results.append({
                'id': results['ids'][0][i],
                'document': results['documents'][0][i],
                'metadata': results['metadatas'][0][i],
                'distance': results['distances'][0][i]
            })
        
        logger.debug(f"检索到 {len(formatted_results)} 个结果")
        
        return formatted_results
    
    def count(self) -> int:
        """获取collection中的chunk数量
        
        Returns:
            chunk数量
        """
        return self.collection.count()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取存储统计信息
        
        Returns:
            统计信息字典
        """
        return {
            'collection_name': self.COLLECTION_NAME,
            'total_chunks': self.count(),
            'persist_directory': str(self.persist_dir),
            'vector_dimension': self.VECTOR_DIMENSION,
            'distance_metric': self.DISTANCE_METRIC
        }
    
    def reset(self):
        """重置collection（删除所有数据）
        
        警告：此操作不可逆！
        """
        logger.warning(f"重置Collection '{self.COLLECTION_NAME}'...")
        self.client.delete_collection(name=self.COLLECTION_NAME)
        self.collection = self._get_or_create_collection()
        logger.info("Collection已重置")


def get_chroma_store(persist_directory: Optional[str] = None) -> ChromaDBStore:
    """工厂函数：获取ChromaDB存储实例
    
    Args:
        persist_directory: 持久化目录
    
    Returns:
        ChromaDBStore实例
    """
    return ChromaDBStore(persist_directory=persist_directory)

