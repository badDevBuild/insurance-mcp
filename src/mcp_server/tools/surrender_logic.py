"""MCP工具：退保/减额交清逻辑提取 (calculate_surrender_value_logic)

提供退保和减额交清逻辑的提取功能，支持：
- 同时返回退保和减额交清条款
- 关联相关表格（现金价值表、减额交清表）
- 生成对比说明
- 提供计算逻辑和注意事项

根据 spec.md §FR-002a 实施。
"""
from typing import List, Dict, Any, Optional
import logging

from src.common.models import SurrenderLogicResult, ClauseResult, SourceRef
from src.indexing.embedding.openai import get_embedder
from src.indexing.vector_store.chroma import get_chroma_store

logger = logging.getLogger(__name__)


class CalculateSurrenderValueLogicTool:
    """退保/减额交清逻辑提取工具
    
    提取退保和减额交清的相关条款和表格数据。
    """
    
    # 工具元数据
    NAME = "calculate_surrender_value_logic"
    DESCRIPTION = """
    退保/减额交清逻辑提取工具。
    
    提取保险合同中关于退保、减额交清的条款和计算规则。
    同时返回相关表格（现金价值表、减额交清表）。
    """
    
    # 退保相关关键词
    SURRENDER_KEYWORDS = [
        '退保', '现金价值', '解除合同', '退还保费',
        '退保金', '解约', '保单现金价值'
    ]
    
    # 减额交清相关关键词
    PAID_UP_KEYWORDS = [
        '减额交清', '减额缴清', '减保', '保额调整',
        '减额交清保险金额', '缴清保额'
    ]
    
    def __init__(self, embedder=None, chroma_store=None):
        """初始化工具
        
        Args:
            embedder: OpenAI Embedder实例
            chroma_store: ChromaDB存储实例
        """
        self.embedder = embedder or get_embedder()
        self.chroma_store = chroma_store or get_chroma_store()
        
        logger.info(f"初始化 {self.NAME} 工具")
    
    def execute(
        self,
        product: str,
        company: Optional[str] = None,
        policy_year: Optional[int] = None
    ) -> SurrenderLogicResult:
        """执行退保/减额交清逻辑提取
        
        Args:
            product: 产品名称
            company: 保险公司名称（可选）
            policy_year: 保单年度（可选，用于表格查询）
        
        Returns:
            SurrenderLogicResult对象
        
        Example:
            >>> tool.execute("平安福2023", company="平安人寿", policy_year=5)
        """
        logger.info(f"执行退保/减额交清逻辑提取: product='{product}', "
                   f"company={company}, policy_year={policy_year}")
        
        # 1. 检索退保条款
        surrender_clauses = self._search_surrender_clauses(product, company)
        
        # 2. 检索减额交清条款
        paid_up_clauses = self._search_paid_up_clauses(product, company)
        
        # 3. 检索相关表格
        tables = self._search_related_tables(product, company)
        
        # 4. 生成对比说明
        comparison = self._generate_comparison(surrender_clauses, paid_up_clauses)
        
        # 5. 构建SurrenderLogicResult
        result = SurrenderLogicResult(
            product_name=product,
            surrender_clauses=surrender_clauses,
            paid_up_clauses=paid_up_clauses,
            related_tables=tables,
            comparison_notes=comparison
        )
        
        logger.info(f"逻辑提取完成：退保条款{len(surrender_clauses)}个，"
                   f"减额交清条款{len(paid_up_clauses)}个，表格{len(tables)}个")
        
        return result
    
    def _search_surrender_clauses(
        self,
        product: str,
        company: Optional[str]
    ) -> List[ClauseResult]:
        """检索退保条款
        
        Args:
            product: 产品名称
            company: 公司名称
        
        Returns:
            ClauseResult列表
        """
        # 构建查询（综合多个关键词）
        query = "退保 现金价值 解除合同"
        
        try:
            query_embedding = self.embedder.embed_single(query)
            
            # 构建过滤条件
            where = {"product_name": product}
            if company:
                where['company'] = company
            
            # 执行检索
            results = self.chroma_store.search(
                query_embedding=query_embedding,
                n_results=5,
                where=where
            )
            
            # 转换为ClauseResult
            clauses = []
            for result in results:
                metadata = result.get('metadata', {})
                distance = result.get('distance', 1.0)
                similarity = 1 - distance
                
                source_ref = SourceRef(
                    document_id=metadata.get('document_id', ''),
                    section_id=metadata.get('section_id'),
                    section_title=metadata.get('section_title'),
                    page_number=metadata.get('page_number'),
                    chunk_id=result.get('id', '')
                )
                
                clause_result = ClauseResult(
                    content=result.get('document', ''),
                    similarity_score=similarity,
                    category=metadata.get('category'),
                    entity_role=metadata.get('entity_role'),
                    keywords=metadata.get('keywords', '').split(',') if metadata.get('keywords') else [],
                    source=source_ref
                )
                
                clauses.append(clause_result)
            
            logger.debug(f"检索到 {len(clauses)} 个退保条款")
            return clauses
            
        except Exception as e:
            logger.error(f"检索退保条款失败: {e}")
            return []
    
    def _search_paid_up_clauses(
        self,
        product: str,
        company: Optional[str]
    ) -> List[ClauseResult]:
        """检索减额交清条款
        
        Args:
            product: 产品名称
            company: 公司名称
        
        Returns:
            ClauseResult列表
        """
        query = "减额交清 减额缴清 保额调整"
        
        try:
            query_embedding = self.embedder.embed_single(query)
            
            where = {"product_name": product}
            if company:
                where['company'] = company
            
            results = self.chroma_store.search(
                query_embedding=query_embedding,
                n_results=5,
                where=where
            )
            
            clauses = []
            for result in results:
                metadata = result.get('metadata', {})
                distance = result.get('distance', 1.0)
                similarity = 1 - distance
                
                source_ref = SourceRef(
                    document_id=metadata.get('document_id', ''),
                    section_id=metadata.get('section_id'),
                    section_title=metadata.get('section_title'),
                    page_number=metadata.get('page_number'),
                    chunk_id=result.get('id', '')
                )
                
                clause_result = ClauseResult(
                    content=result.get('document', ''),
                    similarity_score=similarity,
                    category=metadata.get('category'),
                    entity_role=metadata.get('entity_role'),
                    keywords=metadata.get('keywords', '').split(',') if metadata.get('keywords') else [],
                    source=source_ref
                )
                
                clauses.append(clause_result)
            
            logger.debug(f"检索到 {len(clauses)} 个减额交清条款")
            return clauses
            
        except Exception as e:
            logger.error(f"检索减额交清条款失败: {e}")
            return []
    
    def _search_related_tables(
        self,
        product: str,
        company: Optional[str]
    ) -> List[ClauseResult]:
        """检索相关表格（现金价值表、减额交清表）
        
        Args:
            product: 产品名称
            company: 公司名称
        
        Returns:
            ClauseResult列表（is_table=True）
        """
        query = "现金价值表 减额交清表"
        
        try:
            query_embedding = self.embedder.embed_single(query)
            
            # 构建过滤条件（必须是表格）
            where = {
                "product_name": product,
                "is_table": True
            }
            if company:
                where['company'] = company
            
            results = self.chroma_store.search(
                query_embedding=query_embedding,
                n_results=5,
                where=where
            )
            
            tables = []
            for result in results:
                metadata = result.get('metadata', {})
                distance = result.get('distance', 1.0)
                similarity = 1 - distance
                
                source_ref = SourceRef(
                    document_id=metadata.get('document_id', ''),
                    section_id=metadata.get('section_id'),
                    section_title=metadata.get('section_title'),
                    page_number=metadata.get('page_number'),
                    chunk_id=result.get('id', '')
                )
                
                clause_result = ClauseResult(
                    content=result.get('document', ''),
                    similarity_score=similarity,
                    category=metadata.get('category'),
                    entity_role=metadata.get('entity_role'),
                    keywords=metadata.get('keywords', '').split(',') if metadata.get('keywords') else [],
                    source=source_ref
                )
                
                tables.append(clause_result)
            
            logger.debug(f"检索到 {len(tables)} 个相关表格")
            return tables
            
        except Exception as e:
            logger.error(f"检索相关表格失败: {e}")
            return []
    
    def _generate_comparison(
        self,
        surrender_clauses: List[ClauseResult],
        paid_up_clauses: List[ClauseResult]
    ) -> str:
        """生成退保与减额交清的对比说明
        
        Args:
            surrender_clauses: 退保条款列表
            paid_up_clauses: 减额交清条款列表
        
        Returns:
            对比说明文本
        """
        comparison = """
【退保 vs 减额交清对比】

1. **退保**：
   - 终止保险合同
   - 退还现金价值
   - 保障完全终止
   - 适用场景：不再需要保障，或急需资金

2. **减额交清**：
   - 保险合同继续有效
   - 不再缴纳保费
   - 保额相应减少
   - 适用场景：暂时无法缴费，但仍需保障

3. **注意事项**：
   - 退保可能产生损失（尤其是前几年）
   - 减额交清保额会显著降低
   - 具体计算需参考现金价值表和减额交清表
   - 建议咨询保险公司客服了解详细计算方法

【重要提示】
以上信息仅供参考，具体操作请以保险合同条款和保险公司规定为准。
"""
        return comparison.strip()
    
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
                    "product": {
                        "type": "string",
                        "description": "产品名称，如：'平安福2023'"
                    },
                    "company": {
                        "type": "string",
                        "description": "保险公司名称（可选），如：'平安人寿'"
                    },
                    "policy_year": {
                        "type": "integer",
                        "description": "保单年度（可选），用于查询特定年度的现金价值"
                    }
                },
                "required": ["product"]
            }
        }


def create_surrender_logic_tool(**kwargs) -> CalculateSurrenderValueLogicTool:
    """工厂函数：创建calculate_surrender_value_logic工具
    
    Returns:
        CalculateSurrenderValueLogicTool实例
    """
    return CalculateSurrenderValueLogicTool(**kwargs)

