"""免责条款核查工具

实现 check_exclusion_risk MCP工具。
"""
from typing import List, Optional, Dict, Any
import logging

from src.mcp_server.tools.base import BaseTool
from src.common.models import ExclusionCheckResult, ClauseCategory

logger = logging.getLogger(__name__)

class CheckExclusionRiskTool(BaseTool):
    """免责条款核查工具"""
    
    NAME = "check_exclusion_risk"
    DESCRIPTION = """
    针对特定场景（如"酒驾"、"既往症"）查询保险产品的免责条款（责任免除）。
    强制聚焦于Exclusion类型的条款，并自动扩展风险关键词。
    返回相关的免责条款列表及风险提示。
    """
    
    # 关键词扩展映射
    KEYWORD_EXPANSION = {
        "酒驾": ["酒后驾驶", "饮酒", "醉酒", "酒精"],
        "吸毒": ["毒品", "注射毒品", "管制药物"],
        "犯罪": ["违法", "犯罪行为", "被逮捕", "刑事"],
        "自杀": ["自致伤害", "自杀", "故意自伤"],
        "既往症": ["从前", "曾经", "过去", "病史", "先天性"],
        "无证驾驶": ["无合法有效驾驶证", "无有效驾驶证", "驾驶证有效期已届满"],
        "战争": ["战争", "军事冲突", "暴乱", "武装叛乱"],
        "核": ["核爆炸", "核辐射", "核污染"]
    }
    
    def run(
        self,
        query: str,
        product_name: Optional[str] = None, # 暂未强依赖
        product_code: Optional[str] = None,  # P0增强
        product_code: Optional[str] = None,  # P0增强
        company: Optional[str] = None,
        doc_type: Optional[str] = None,  # FR-005: 文档类型过滤
    ) -> ExclusionCheckResult:
        """执行免责核查
        
        Args:
            query: 风险场景描述（如"酒后驾车撞树了赔吗"）
            product_name: 产品名称
            product_code: 产品代码 (P0增强,推荐使用)
            product_code: 产品代码 (P0增强,推荐使用)
            company: 保险公司
            doc_type: 文档类型过滤
            
        Returns:
            ExclusionCheckResult对象
        """
        logger.info(f"执行check_exclusion_risk: query='{query}', product_code={product_code}, doc_type={doc_type}")
        
        # 1. 关键词扩展
        expanded_query = query
        risk_keywords = []
        for key, expansions in self.KEYWORD_EXPANSION.items():
            if key in query:
                expanded_query += " " + " ".join(expansions)
                risk_keywords.append(key)
        
        # 2. 强制过滤 Exclusion 类别
        where = {"category": ClauseCategory.EXCLUSION.value}
        if product_code:  # P0增强
            where['product_code'] = product_code
        if company:
            where['company'] = company
        if doc_type:  # FR-005
            where['doc_type'] = doc_type
            
        # 3. 执行检索 (降低阈值以提高召回率)
        query_embedding = self.embed_query(expanded_query)
        results = self.chroma_store.search(
            query_embedding=query_embedding,
            n_results=10, # 获取更多候选
            where=where
        )
        
        # 4. 处理结果
        relevant_clauses = []
        risk_detected = False
        
        for res in results:
            similarity = 1.0 - res.get('distance', 1.0)
            
            # 免责条款阈值可以稍低，宁可误报不可漏报
            if similarity < 0.65: 
                continue
            
            relevant_clauses.append(self._format_source_ref(res))
            
            # 简单判断：如果相似度够高，认为检测到风险
            if similarity > 0.75:
                risk_detected = True
                
        # 5. 构建总结
        summary = "未发现直接相关的免责条款。"
        if relevant_clauses:
            if risk_detected:
                summary = f"检测到高风险免责条款。该场景可能触及以下 {len(relevant_clauses)} 条免责内容，请仔细核对。"
            else:
                summary = f"发现 {len(relevant_clauses)} 条可能相关的免责条款，建议人工核实。"
                
        return ExclusionCheckResult(
            risk_detected=risk_detected,
            relevant_clauses=relevant_clauses,
            summary=summary,
            disclaimer="本工具仅提供条款检索辅助，不构成理赔承诺。具体理赔结论以保险公司审核为准。"
        )

tool = CheckExclusionRiskTool()

