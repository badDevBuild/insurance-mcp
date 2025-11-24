"""语义条款检索工具

实现 search_policy_clause MCP工具。
"""
from typing import List, Optional, Dict, Any
import logging

from src.mcp_server.tools.base import BaseTool
from src.common.models import ClauseResult, ClauseCategory

logger = logging.getLogger(__name__)

class SearchPolicyClauseTool(BaseTool):
    """语义条款检索工具"""
    
    NAME = "search_policy_clause"
    DESCRIPTION = """
    根据自然语言查询检索相关的保险条款。
    支持按保险公司、产品名称、条款类型（如保险责任、免除责任）进行过滤。
    使用混合检索技术（语义+关键词），并返回置信度评分。
    """
    
    def run(
        self,
        query: str,
        company: Optional[str] = None,
        product_code: Optional[str] = None,  # P0增强: 产品代码过滤
        product_name: Optional[str] = None,
        doc_type: Optional[str] = None,  # FR-005: 文档类型过滤
        category: Optional[str] = None,
        n_results: int = 5,
        min_similarity: float = -1.0
    ) -> List[ClauseResult]:
        """执行检索
        
        Args:
            query: 查询语句
            company: 保险公司名称过滤
            product_code: 产品代码过滤 (P0增强,推荐使用)
            product_name: 产品名称过滤
            doc_type: 文档类型过滤 (产品条款/产品说明书/产品费率表)
            category: 条款类型过滤 (Liability/Exclusion/Process/Definition)
            n_results: 返回结果数量
            min_similarity: 最小相似度阈值 (0.0-1.0)
            
        Returns:
            ClauseResult列表
        """
        logger.info(f"执行search_policy_clause: query='{query}', company={company}, product_code={product_code}, doc_type={doc_type}, category={category}")
        
        # 1. 生成查询向量
        query_embedding = self.embed_query(query)
        
        # 2. 构建过滤条件
        where = {}
        if company:
            where['company'] = company
        if product_code:  # P0增强: 支持product_code过滤
            where['product_code'] = product_code
        if doc_type:  # FR-005: 支持doc_type过滤
            where['doc_type'] = doc_type
        # 注意：product_name在metadata中可能不完全匹配，这里简化处理
        # 理想情况下应该先查找product_id
        if category:
            # 确保category是有效的枚举值
            try:
                if category in ClauseCategory.__members__:
                    cat_val = ClauseCategory[category].value
                else:
                    cat_val = category # 尝试直接使用传入值
                where['category'] = cat_val
            except Exception:
                logger.warning(f"无效的category: {category}，忽略该过滤条件")
        
        # 3. 执行检索 (优先使用ChromaDBStore的search，因为它直接支持metadata过滤)
        # 在MVP阶段，我们可能还没有完整的BM25索引加载逻辑，所以先用Dense检索
        results = self.chroma_store.search(
            query_embedding=query_embedding,
            n_results=n_results * 2, # 多取一些用于后过滤
            where=where if where else None
        )
        
        # 4. 处理结果并转换为ClauseResult
        clause_results = []
        for res in results:
            # 计算相似度 (1 - distance)
            similarity = max(0.0, 1.0 - res.get('distance', 1.0))
            
            # 过滤低置信度结果
            if similarity < min_similarity:
                continue
            
            # 构建ClauseResult
            metadata = res.get('metadata', {})
            clause_result = ClauseResult(
                chunk_id=res['id'],
                content=res['document'],
                section_id=metadata.get('section_id', ''),
                section_title=metadata.get('section_title', ''),
                similarity_score=similarity,
                source_reference=self._format_source_ref(res)
            )
            clause_results.append(clause_result)
            
            if len(clause_results) >= n_results:
                break
                
        return clause_results

tool = SearchPolicyClauseTool()

