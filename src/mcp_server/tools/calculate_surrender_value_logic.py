"""退保/减额交清逻辑提取工具

实现 calculate_surrender_value_logic MCP工具。
"""
from typing import List, Optional, Dict, Any
import logging

from src.mcp_server.tools.base import BaseTool
from src.common.models import SurrenderLogicResult, SourceRef

logger = logging.getLogger(__name__)

class CalculateSurrenderValueLogicTool(BaseTool):
    """退保/减额交清逻辑提取工具"""
    
    NAME = "calculate_surrender_value_logic"
    DESCRIPTION = """
    提取保险产品的退保（解除合同）和减额交清计算逻辑。
    返回相关的条款文本以及关联的现金价值表或减额交清表（如果存在）。
    不进行具体的金额计算，而是提供计算依据。
    """
    
    def run(
        self,
        product_name: str, # 必须指定产品
        product_code: Optional[str] = None,  # P0增强
        year: Optional[int] = None, # 保单年度（辅助信息）
        company: Optional[str] = None,
        doc_type: Optional[str] = None  # FR-005: 文档类型过滤
    ) -> SurrenderLogicResult:
        """提取计算逻辑
        
        Args:
            product_name: 产品名称
            product_code: 产品代码 (P0增强,推荐使用)
            year: 保单年度（可选）
            product_code: 产品代码 (P0增强,推荐使用)
            year: 保单年度（可选）
            company: 保险公司
            doc_type: 文档类型过滤
            
        Returns:
            SurrenderLogicResult对象
        """
        logger.info(f"执行calculate_surrender_value_logic: product='{product_name}', product_code={product_code}, doc_type={doc_type}")
        
        # 构建通用过滤条件
        where = {}
        if product_code:  # P0增强: 优先使用product_code
            where['product_code'] = product_code
        elif company:
            where['company'] = company
            
        if doc_type:  # FR-005
            where['doc_type'] = doc_type
        
        # 1. 检索退保条款
        surrender_query = f"{product_name} 解除合同 退保 现金价值"
        surrender_emb = self.embed_query(surrender_query)
        
        surrender_results = self.chroma_store.search(
            query_embedding=surrender_emb,
            n_results=3,
            where=where if where else None
        )
        
        surrender_clauses = [self._format_source_ref(res) for res in surrender_results]
        surrender_text = "\n\n".join([res['document'] for res in surrender_results])
        
        # 2. 检索减额交清条款
        reduced_paid_up_query = f"{product_name} 减额交清"
        rpu_emb = self.embed_query(reduced_paid_up_query)
        
        rpu_results = self.chroma_store.search(
            query_embedding=rpu_emb,
            n_results=3,
            where=where if where else None
        )
        
        reduced_paid_up_clauses = [self._format_source_ref(res) for res in rpu_results]
        rpu_text = "\n\n".join([res['document'] for res in rpu_results])
        
        # 3. 检索相关表格 (is_table=True)
        table_query = f"{product_name} 现金价值表 减额交清表"
        table_emb = self.embed_query(table_query)
        
        # 构建表格查询条件
        table_where = {"is_table": True}
        if where:  # P0增强: 使用统一的过滤条件
            table_where.update(where)
            
        table_results = self.chroma_store.search(
            query_embedding=table_emb,
            n_results=3,
            where=table_where
        )
        
        related_tables = []
        for res in table_results:
            metadata = res.get('metadata', {})
            table_data = metadata.get('table_data')
            
            # 如果metadata中没有直接存储table_data（可能因为太长），则需要从其他地方获取
            # 这里假设indexer已经将table_data放入metadata
            # 或者我们可以从chunk content中解析摘要
            
            # 修正：ChromaDB metadata不支持复杂嵌套JSON，通常存储为字符串
            # 这里我们直接使用SourceRef指向表格位置
            related_tables.append(self._format_source_ref(res))
            
        # 4. 构建结果
        explanation = f"关于【{product_name}】的退保与减额交清逻辑：\n\n"
        explanation += "1. **退保（解除合同）**：\n"
        explanation += "   通常按保单现金价值退还。相关条款指出：" + surrender_text[:200] + "...\n\n"
        
        if rpu_text:
            explanation += "2. **减额交清**：\n"
            explanation += "   可选择将现金价值作为一次交清的保险费，减少保额但合同继续有效。条款摘要：" + rpu_text[:200] + "...\n"
        else:
            explanation += "2. **减额交清**：\n   未检索到明确的减额交清条款，该产品可能不支持此功能。\n"
            
        if related_tables:
            explanation += "\n3. **关联表格**：\n"
            explanation += f"   发现 {len(related_tables)} 个相关表格（现金价值表/减额交清表），请查阅附件。"
            
        return SurrenderLogicResult(
            surrender_clauses=surrender_clauses,
            reduced_paid_up_clauses=reduced_paid_up_clauses,
            related_tables=related_tables,
            calculation_logic_summary=explanation
        )

tool = CalculateSurrenderValueLogicTool()

