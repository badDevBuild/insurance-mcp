"""MCP工具：语义条款检索 (search_policy_clause)

提供保险条款的语义检索功能，支持：
- 自然语言查询
- 公司/产品/类别过滤
- 相似度阈值过滤
- 结构化返回（包含来源引用）

根据 spec.md §FR-001 实施。
"""
from typing import List, Dict, Any, Optional
import logging

from src.common.models import ClauseResult, SourceRef, ClauseCategory
from src.indexing.embedding.openai import get_embedder
from src.indexing.vector_store.chroma import get_chroma_store
from src.indexing.vector_store.hybrid_retriever import create_hybrid_retriever, BM25Index

logger = logging.getLogger(__name__)


class SearchPolicyClauseTool:
    """语义条款检索工具
    
    使用混合检索（Dense Vector + BM25）进行条款检索。
    """
    
    # 工具元数据
    NAME = "search_policy_clause"
    DESCRIPTION = """
    语义条款检索工具。根据自然语言查询，检索相关的保险条款。
    
    支持按公司、产品、类别过滤，返回相似度高于阈值的条款。
    """
    
    # 默认相似度阈值
    DEFAULT_SIMILARITY_THRESHOLD = 0.7
    
    def __init__(
        self,
        embedder=None,
        chroma_store=None,
        use_hybrid: bool = True
    ):
        """初始化工具
        
        Args:
            embedder: OpenAI Embedder实例
            chroma_store: ChromaDB存储实例
            use_hybrid: 是否使用混合检索
        """
        self.embedder = embedder or get_embedder()
        self.chroma_store = chroma_store or get_chroma_store()
        self.use_hybrid = use_hybrid
        
        # 如果使用混合检索，需要BM25索引
        self.hybrid_retriever = None
        if use_hybrid:
            logger.info("混合检索模式（需要BM25索引）")
        
        logger.info(f"初始化 {self.NAME} 工具")
    
    def execute(
        self,
        query: str,
        company: Optional[str] = None,
        product: Optional[str] = None,
        category: Optional[str] = None,
        top_k: int = 5,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD
    ) -> List[ClauseResult]:
        """执行条款检索
        
        Args:
            query: 查询字符串（自然语言）
            company: 保险公司名称过滤
            product: 产品名称过滤
            category: 条款类别过滤（Liability/Exclusion/Process/Definition）
            top_k: 返回结果数量
            similarity_threshold: 相似度阈值（0-1）
        
        Returns:
            ClauseResult列表
        
        Example:
            >>> tool.execute("保险期间多久", company="平安人寿")
            >>> tool.execute("什么情况不赔", category="Exclusion")
        """
        logger.info(f"执行条款检索: query='{query}', company={company}, "
                   f"product={product}, category={category}")
        
        # 1. 生成查询向量
        try:
            query_embedding = self.embedder.embed_single(query)
        except Exception as e:
            logger.error(f"生成embedding失败: {e}")
            return []
        
        # 2. 构建过滤条件
        where = {}
        if company:
            where['company'] = company
        if product:
            where['product_name'] = product
        if category:
            # 验证category是否有效
            try:
                ClauseCategory(category)
                where['category'] = category
            except ValueError:
                logger.warning(f"无效的category: {category}，忽略此过滤条件")
        
        # 3. 执行检索
        try:
            if self.use_hybrid and self.hybrid_retriever:
                # 混合检索
                results = self.hybrid_retriever.search(
                    query=query,
                    query_embedding=query_embedding,
                    n_results=top_k * 2,  # 多检索一些，用于阈值过滤
                    where=where if where else None,
                    auto_weight=True
                )
            else:
                # 纯向量检索
                results = self.chroma_store.search(
                    query_embedding=query_embedding,
                    n_results=top_k * 2,
                    where=where if where else None
                )
        except Exception as e:
            logger.error(f"检索失败: {e}")
            return []
        
        # 4. 过滤低相似度结果并转换为ClauseResult
        clause_results = []
        for result in results:
            # 计算相似度（从distance转换）
            distance = result.get('distance', 1.0)
            similarity = 1 - distance  # 余弦相似度
            
            # 应用阈值
            if similarity < similarity_threshold:
                continue
            
            metadata = result.get('metadata', {})
            
            # 构建SourceRef
            source_ref = SourceRef(
                document_id=metadata.get('document_id', ''),
                section_id=metadata.get('section_id'),
                section_title=metadata.get('section_title'),
                page_number=metadata.get('page_number'),
                chunk_id=result.get('id', '')
            )
            
            # 构建ClauseResult
            clause_result = ClauseResult(
                content=result.get('document', ''),
                similarity_score=similarity,
                category=metadata.get('category'),
                entity_role=metadata.get('entity_role'),
                keywords=metadata.get('keywords', '').split(',') if metadata.get('keywords') else [],
                source=source_ref
            )
            
            clause_results.append(clause_result)
            
            # 限制返回数量
            if len(clause_results) >= top_k:
                break
        
        logger.info(f"检索完成，返回 {len(clause_results)} 个结果")
        
        return clause_results
    
    def get_schema(self) -> Dict[str, Any]:
        """获取工具的JSON Schema
        
        Returns:
            MCP工具schema
        """
        return {
            "name": self.NAME,
            "description": self.DESCRIPTION,
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "查询字符串（自然语言），如：'保险期间多久'、'什么情况下理赔'"
                    },
                    "company": {
                        "type": "string",
                        "description": "保险公司名称过滤（可选），如：'平安人寿'"
                    },
                    "product": {
                        "type": "string",
                        "description": "产品名称过滤（可选），如：'平安福2023'"
                    },
                    "category": {
                        "type": "string",
                        "enum": ["Liability", "Exclusion", "Process", "Definition"],
                        "description": "条款类别过滤（可选）"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回结果数量（默认5）",
                        "default": 5
                    },
                    "similarity_threshold": {
                        "type": "number",
                        "description": "相似度阈值（0-1，默认0.7）",
                        "default": 0.7
                    }
                },
                "required": ["query"]
            }
        }


def create_search_clause_tool(**kwargs) -> SearchPolicyClauseTool:
    """工厂函数：创建search_policy_clause工具
    
    Returns:
        SearchPolicyClauseTool实例
    """
    return SearchPolicyClauseTool(**kwargs)

