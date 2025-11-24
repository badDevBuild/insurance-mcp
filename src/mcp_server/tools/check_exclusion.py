"""MCP工具：免责条款核查 (check_exclusion_risk)

提供免责条款的专项核查功能，支持：
- 强制过滤category="Exclusion"
- 关键词扩展（如"酒驾" → ["酒后驾驶", "饮酒", "醉酒"]）
- 高召回率（≥95%）
- 安全免责声明

根据 spec.md §FR-002 实施。
"""
from typing import List, Dict, Any, Optional
import logging

from src.common.models import ExclusionCheckResult, SourceRef, ClauseResult
from src.indexing.embedding.openai import get_embedder
from src.indexing.vector_store.chroma import get_chroma_store

logger = logging.getLogger(__name__)


class CheckExclusionRiskTool:
    """免责条款核查工具
    
    专门用于检索免责条款，提供高召回率和关键词扩展。
    """
    
    # 工具元数据
    NAME = "check_exclusion_risk"
    DESCRIPTION = """
    免责条款核查工具。根据场景描述，检索相关的免责条款。
    
    自动过滤category="Exclusion"，提供高召回率检索。
    返回结果包含免责声明，仅供参考，不构成法律意见。
    """
    
    # 关键词扩展映射（针对常见场景）
    KEYWORD_EXPANSIONS = {
        '酒驾': ['酒后驾驶', '饮酒', '醉酒', '酒精', '酒后'],
        '毒驾': ['毒品', '吸毒', '毒驾', '麻醉药品', '精神药品'],
        '自杀': ['自杀', '自残', '自伤', '故意自伤'],
        '战争': ['战争', '军事行动', '暴乱', '武装冲突', '恐怖活动'],
        '既往症': ['既往症', '既往病史', '已有疾病', '先天性疾病'],
        '犯罪': ['犯罪', '违法', '故意犯罪', '刑事责任'],
    }
    
    # 安全免责声明
    DISCLAIMER = """
    【重要提示】
    本工具检索结果仅供参考，不构成法律意见或理赔决定。
    具体理赔情况请以保险合同条款和保险公司最终审核为准。
    如有疑问，请联系保险公司客服或专业律师。
    """
    
    def __init__(self, embedder=None, chroma_store=None):
        """初始化工具
        
        Args:
            embedder: OpenAI Embedder实例
            chroma_store: ChromaDB存储实例
        """
        self.embedder = embedder or get_embedder()
        self.chroma_store = chroma_store or get_chroma_store()
        
        logger.info(f"初始化 {self.NAME} 工具")
    
    def _expand_keywords(self, query: str) -> List[str]:
        """扩展关键词
        
        根据预定义的映射扩展查询关键词，提升召回率。
        
        Args:
            query: 原始查询
        
        Returns:
            扩展后的关键词列表
        """
        expanded = [query]
        
        for key, expansions in self.KEYWORD_EXPANSIONS.items():
            if key in query:
                expanded.extend(expansions)
                logger.debug(f"关键词扩展: {key} → {expansions}")
        
        return list(set(expanded))  # 去重
    
    def execute(
        self,
        scenario: str,
        company: Optional[str] = None,
        product: Optional[str] = None,
        top_k: int = 10
    ) -> ExclusionCheckResult:
        """执行免责条款核查
        
        Args:
            scenario: 场景描述（如："被保险人酒后驾驶发生事故"）
            company: 保险公司名称过滤（可选）
            product: 产品名称过滤（可选）
            top_k: 返回结果数量（默认10，比普通检索更多）
        
        Returns:
            ExclusionCheckResult对象
        
        Example:
            >>> tool.execute("被保险人酒后驾驶发生事故", company="平安人寿")
            >>> tool.execute("投保前已有高血压病史", product="平安福2023")
        """
        logger.info(f"执行免责条款核查: scenario='{scenario}', "
                   f"company={company}, product={product}")
        
        # 1. 关键词扩展
        expanded_queries = self._expand_keywords(scenario)
        logger.debug(f"扩展查询: {expanded_queries}")
        
        # 2. 为每个扩展查询生成embedding并检索
        all_results = {}  # {chunk_id: result}
        
        for query in expanded_queries:
            try:
                # 生成查询向量
                query_embedding = self.embedder.embed_single(query)
                
                # 构建过滤条件（强制category="Exclusion"）
                where = {"category": "Exclusion"}
                if company:
                    where['company'] = company
                if product:
                    where['product_name'] = product
                
                # 执行检索
                results = self.chroma_store.search(
                    query_embedding=query_embedding,
                    n_results=top_k,
                    where=where
                )
                
                # 合并结果（避免重复）
                for result in results:
                    chunk_id = result.get('id')
                    if chunk_id not in all_results:
                        all_results[chunk_id] = result
                
            except Exception as e:
                logger.error(f"查询 '{query}' 检索失败: {e}")
                continue
        
        # 3. 转换为ClauseResult
        exclusion_clauses = []
        for result in all_results.values():
            metadata = result.get('metadata', {})
            distance = result.get('distance', 1.0)
            similarity = 1 - distance
            
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
            
            exclusion_clauses.append(clause_result)
        
        # 4. 按相似度排序
        exclusion_clauses.sort(key=lambda x: x.similarity_score, reverse=True)
        
        # 5. 限制返回数量
        exclusion_clauses = exclusion_clauses[:top_k]
        
        # 6. 构建ExclusionCheckResult
        result = ExclusionCheckResult(
            scenario=scenario,
            is_likely_excluded=(len(exclusion_clauses) > 0),
            exclusion_clauses=exclusion_clauses,
            confidence_level="high" if len(exclusion_clauses) >= 3 else "medium" if len(exclusion_clauses) >= 1 else "low",
            disclaimer=self.DISCLAIMER
        )
        
        logger.info(f"免责核查完成，找到 {len(exclusion_clauses)} 个相关条款，"
                   f"可能免责: {result.is_likely_excluded}")
        
        return result
    
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
                    "scenario": {
                        "type": "string",
                        "description": "场景描述，如：'被保险人酒后驾驶发生事故'、'投保前已有高血压'"
                    },
                    "company": {
                        "type": "string",
                        "description": "保险公司名称过滤（可选），如：'平安人寿'"
                    },
                    "product": {
                        "type": "string",
                        "description": "产品名称过滤（可选），如：'平安福2023'"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "返回结果数量（默认10）",
                        "default": 10
                    }
                },
                "required": ["scenario"]
            }
        }


def create_check_exclusion_tool(**kwargs) -> CheckExclusionRiskTool:
    """工厂函数：创建check_exclusion_risk工具
    
    Returns:
        CheckExclusionRiskTool实例
    """
    return CheckExclusionRiskTool(**kwargs)

