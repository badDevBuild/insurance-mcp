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
    
    def _infer_doc_type(self, query: str) -> Optional[str]:
        """根据查询内容智能推断文档类型
        
        Args:
            query: 用户查询内容
            
        Returns:
            推断的文档类型（"产品条款"/"产品说明书"/"产品费率表"），
            如果无法确定则返回None
        """
        query_lower = query.lower()
        
        # 1. 费率表推断
        # 触发条件: 包含费率关键词 且 包含数字
        rate_keywords = ["保费", "费率", "多少钱", "价格", "费用", "成本", "交多少"]
        has_digit = any(char.isdigit() for char in query)
        if any(kw in query_lower for kw in rate_keywords) and has_digit:
            logger.info(f"推断文档类型: 产品费率表 (query='{query}')")
            return "产品费率表"
            
        # 2. 其他情况
        # 不进行显式推断，完全依赖语义检索的相似度排序
        # 产品条款和产品说明书的内容在语义上有自然区分
        return None
    
    def run(
        self,
        query: str,
        product_code: Optional[str] = None,
        product_name: Optional[str] = None,
        company: Optional[str] = None,
        doc_type: Optional[str] = None,
        category: Optional[str] = None,
        n_results: int = 5,
        min_similarity: float = 0.5,
        auto_fetch_rate_tables: bool = False
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
            auto_fetch_rate_tables: 是否自动获取费率表完整数据(默认False)
            
        Returns:
            ClauseResult列表
        """
        # 0. 参数验证: product_code 或 product_name 必须提供一个
        if not product_code and not product_name:
            raise ValueError(
                "product_code 或 product_name 必须提供一个。\n"
                "用户查询始终针对具体产品，请指定 product_code 或 product_name 参数。\n"
                "例如: product_name='平安福耀年金保险（分红型）'"
            )
        
        logger.info(f"执行search_policy_clause: query='{query}', product_code={product_code}, product_name={product_name}, company={company}, doc_type={doc_type}, category={category}")
        
        # 1. 智能文档类型推断 (FR-012)
        if not doc_type:
            doc_type = self._infer_doc_type(query)
            if doc_type:
                logger.info(f"应用推断的文档类型: {doc_type}")
        
        # 1. 生成查询向量
        query_embedding = self.embed_query(query)
        
        # 2. 构建过滤条件 (修复ChromaDB多条件过滤)
        conditions = []
        
        if company:
            conditions.append({"company": company})
        if product_code:
            conditions.append({"product_code": product_code})
        if product_name:
            conditions.append({"product_name": product_name})
        if doc_type:
            conditions.append({"doc_type": doc_type})
        if category:
            # 确保category是有效的枚举值
            try:
                if category in ClauseCategory.__members__:
                    cat_val = ClauseCategory[category].value
                else:
                    cat_val = category # 尝试直接使用传入值
                conditions.append({"category": cat_val})
            except Exception:
                logger.warning(f"无效的category: {category}，忽略该过滤条件")
        
        # 根据条件数量决定where格式
        if len(conditions) == 0:
            where = None
        elif len(conditions) == 1:
            where = conditions[0]  # 单条件: 直接使用
        else:
            where = {"$and": conditions}  # 多条件: 用$and包装
        
        logger.info(f"构建过滤条件: {where}")
        
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
                source_reference=self._format_source_ref(res),
                table_refs=metadata.get('table_refs', '').split(',') if metadata.get('table_refs') else [],
                doc_type=metadata.get('doc_type', '产品条款')
            )
            clause_results.append(clause_result)
            
            if len(clause_results) >= n_results:
                break
        
        # 5. 自动获取费率表数据(如果需要)
        if auto_fetch_rate_tables:
            from src.mcp_server.tools.get_rate_table import get_rate_table
            
            for result in clause_results:
                if result.table_refs:
                    try:
                        # 获取第一个费率表的数据
                        table_id = result.table_refs[0]
                        rate_table = get_rate_table(table_id)
                        
                        # 转换为Markdown格式
                        if rate_table and rate_table.table_data:
                            md_lines = ["## 费率表数据\n"]
                            
                            # 表头
                            headers = rate_table.table_data.headers
                            md_lines.append("| " + " | ".join(headers) + " |")
                            md_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
                            
                            # 表格数据
                            for row in rate_table.table_data.rows[:20]:  # 最多显示20行
                                md_lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
                            
                            if len(rate_table.table_data.rows) > 20:
                                md_lines.append(f"\n*(...还有{len(rate_table.table_data.rows) - 20}行数据)*")
                            
                            result.rate_table_content = "\n".join(md_lines)
                            logger.info(f"已为chunk {result.chunk_id[:8]}自动获取费率表数据")
                    except Exception as e:
                        logger.warning(f"获取费率表{table_id}数据失败: {e}")
                        # 失败不影响整体结果,继续
                
        return clause_results

tool = SearchPolicyClauseTool()

