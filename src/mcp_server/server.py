"""MCP服务器入口点

提供保险条款检索的MCP服务，包括4个工具：
1. lookup_product：产品查询（模糊匹配）
2. search_policy_clause：语义条款检索
3. check_exclusion_risk：免责条款核查
4. calculate_surrender_value_logic：退保/减额交清逻辑提取

根据 tasks.md §T027, T037 实施。
"""
import asyncio
from typing import Any, Sequence
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from src.mcp_server.tools.search_clause import create_search_clause_tool
from src.mcp_server.tools.check_exclusion import create_check_exclusion_tool
from src.mcp_server.tools.surrender_logic import create_surrender_logic_tool
from src.mcp_server.tools.get_rate_table import tool as get_rate_table_tool
from src.mcp_server.product_lookup import lookup_product  # T037: 产品查询工具
from src.common.logging import setup_logging

# 设置日志
setup_logging()
logger = logging.getLogger(__name__)

# 创建MCP服务器实例
app = Server("insurance-mcp-server")

# 初始化工具实例
try:
    search_clause_tool = create_search_clause_tool()
    check_exclusion_tool = create_check_exclusion_tool()
    surrender_logic_tool = create_surrender_logic_tool()
    
    logger.info("所有MCP工具初始化完成")
except Exception as e:
    logger.error(f"工具初始化失败: {e}")
    raise


@app.list_tools()
async def list_tools() -> list[Tool]:
    """列出所有可用的MCP工具
    
    Returns:
        Tool列表
    """
    tools = [
        Tool(
            name="lookup_product",
            description="根据模糊的产品名称（可选公司名）查询精确的产品信息，支持部分匹配，返回Top-5最相关产品",
            inputSchema={
                "type": "object",
                "properties": {
                    "product_name": {
                        "type": "string",
                        "description": "产品名称（支持模糊匹配，如'盈添悦'可匹配'平安盈添悦两全保险'）"
                    },
                    "company": {
                        "type": "string",
                        "description": "可选：保险公司名称（如'平安人寿'）用于过滤"
                    }
                },
                "required": ["product_name"]
            }
        ),
        Tool(
            name=search_clause_tool.NAME,
            description=search_clause_tool.DESCRIPTION,
            inputSchema=search_clause_tool.get_schema()["inputSchema"]
        ),
        Tool(
            name=check_exclusion_tool.NAME,
            description=check_exclusion_tool.DESCRIPTION,
            inputSchema=check_exclusion_tool.get_schema()["inputSchema"]
        ),
        Tool(
            name=surrender_logic_tool.NAME,
            description=surrender_logic_tool.DESCRIPTION,
            inputSchema=surrender_logic_tool.get_schema()["inputSchema"]
        ),
        Tool(
            name=get_rate_table_tool.NAME,
            description=get_rate_table_tool.DESCRIPTION,
            inputSchema=get_rate_table_tool.get_schema()["inputSchema"]
        )
    ]
    
    logger.debug(f"列出 {len(tools)} 个MCP工具")
    
    return tools


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> Sequence[TextContent]:
    """调用指定的MCP工具
    
    Args:
        name: 工具名称
        arguments: 工具参数（dict）
    
    Returns:
        TextContent列表
    
    Raises:
        ValueError: 工具不存在
        Exception: 工具执行失败
    """
    logger.info(f"调用工具: {name}, 参数: {arguments}")
    
    try:
        # 路由到对应的工具
        if name == "lookup_product":
            # T037: 产品查询工具
            product_name = arguments.get("product_name")
            company = arguments.get("company")
            results = lookup_product(product_name, company=company)
            
            if not results:
                response_text = f"未找到匹配产品：{product_name}"
            else:
                response_text = _format_product_results(results)
        
        elif name == search_clause_tool.NAME:
            result = search_clause_tool.execute(**arguments)
            # 将ClauseResult列表转换为文本
            if not result:
                response_text = "未找到匹配的条款。"
            else:
                response_text = _format_clause_results(result)
        
        elif name == check_exclusion_tool.NAME:
            result = check_exclusion_tool.execute(**arguments)
            # 将ExclusionCheckResult转换为文本
            response_text = _format_exclusion_result(result)
        
        elif name == surrender_logic_tool.NAME:
            result = surrender_logic_tool.execute(**arguments)
            # 将SurrenderLogicResult转换为文本
            response_text = _format_surrender_result(result)
            
        elif name == get_rate_table_tool.NAME:
            result = get_rate_table_tool.execute(**arguments)
            # 将RateTableData转换为文本
            response_text = _format_rate_table_result(result)
        
        else:
            raise ValueError(f"未知的工具: {name}")
        
        logger.info(f"工具 {name} 执行成功")
        
        return [TextContent(type="text", text=response_text)]
    
    except Exception as e:
        error_msg = f"工具 {name} 执行失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return [TextContent(type="text", text=f"错误: {error_msg}")]


def _format_product_results(results) -> str:
    """格式化ProductInfo列表为可读文本
    
    Args:
        results: ProductInfo列表
    
    Returns:
        格式化的文本
    """
    lines = [f"找到 {len(results)} 个匹配产品：\n"]
    
    for i, product_info in enumerate(results, 1):
        lines.append(f"【产品 {i}】")
        lines.append(f"产品名称: {product_info.product_name}")
        lines.append(f"产品代码: {product_info.product_code}")
        lines.append(f"保险公司: {product_info.company}")
        
        if product_info.category:
            lines.append(f"产品类别: {product_info.category}")
        
        if product_info.publish_time:
            lines.append(f"发布时间: {product_info.publish_time}")
        
        lines.append(f"产品ID: {product_info.product_id}")
        lines.append("-" * 60)
    
    return "\n".join(lines)


def _format_clause_results(results) -> str:
    """格式化ClauseResult列表为可读文本
    
    Args:
        results: ClauseResult列表
    
    Returns:
        格式化的文本
    """
    lines = [f"找到 {len(results)} 个相关条款：\n"]
    
    for i, clause in enumerate(results, 1):
        lines.append(f"【条款 {i}】")
        lines.append(f"相似度: {clause.similarity_score:.4f}")
        lines.append(f"类别: {clause.category}")
        
        if clause.source.section_title:
            lines.append(f"章节: {clause.source.section_title}")
        
        if clause.source.section_id:
            lines.append(f"编号: {clause.source.section_id}")
        
        lines.append(f"\n内容:\n{clause.content}\n")
        lines.append("-" * 60)
    
    return "\n".join(lines)


def _format_exclusion_result(result) -> str:
    """格式化ExclusionCheckResult为可读文本
    
    Args:
        result: ExclusionCheckResult对象
    
    Returns:
        格式化的文本
    """
    lines = [f"【免责条款核查结果】\n"]
    lines.append(f"场景: {result.scenario}")
    lines.append(f"可能免责: {'是' if result.is_likely_excluded else '否'}")
    lines.append(f"置信度: {result.confidence_level}\n")
    
    if result.exclusion_clauses:
        lines.append(f"找到 {len(result.exclusion_clauses)} 个相关免责条款：\n")
        
        for i, clause in enumerate(result.exclusion_clauses, 1):
            lines.append(f"【免责条款 {i}】")
            lines.append(f"相似度: {clause.similarity_score:.4f}")
            
            if clause.source.section_title:
                lines.append(f"章节: {clause.source.section_title}")
            
            lines.append(f"\n内容:\n{clause.content}\n")
            lines.append("-" * 60)
    else:
        lines.append("未找到相关免责条款。\n")
    
    lines.append(f"\n{result.disclaimer}")
    
    return "\n".join(lines)


def _format_surrender_result(result) -> str:
    """格式化SurrenderLogicResult为可读文本
    
    Args:
        result: SurrenderLogicResult对象
    
    Returns:
        格式化的文本
    """
    lines = [f"【退保/减额交清逻辑】\n"]
    lines.append(f"产品: {result.product_name}\n")
    
    # 退保条款
    if result.surrender_clauses:
        lines.append(f"=== 退保条款 ({len(result.surrender_clauses)}个) ===\n")
        for i, clause in enumerate(result.surrender_clauses, 1):
            lines.append(f"【退保条款 {i}】")
            if clause.source.section_title:
                lines.append(f"章节: {clause.source.section_title}")
            lines.append(f"\n{clause.content}\n")
            lines.append("-" * 60)
    
    # 减额交清条款
    if result.paid_up_clauses:
        lines.append(f"\n=== 减额交清条款 ({len(result.paid_up_clauses)}个) ===\n")
        for i, clause in enumerate(result.paid_up_clauses, 1):
            lines.append(f"【减额交清条款 {i}】")
            if clause.source.section_title:
                lines.append(f"章节: {clause.source.section_title}")
            lines.append(f"\n{clause.content}\n")
            lines.append("-" * 60)
    
    # 相关表格
    if result.related_tables:
        lines.append(f"\n=== 相关表格 ({len(result.related_tables)}个) ===\n")
        for i, table in enumerate(result.related_tables, 1):
            lines.append(f"【表格 {i}】")
            if table.source.section_title:
                lines.append(f"标题: {table.source.section_title}")
            lines.append(f"\n{table.content}\n")
            lines.append("-" * 60)
    
    # 对比说明
    lines.append(f"\n{result.comparison_notes}")
    
    return "\n".join(lines)


def _format_rate_table_result(result) -> str:
    """格式化RateTableData为可读文本"""
    lines = [f"【费率表数据】\n"]
    lines.append(f"表ID: {result.get('table_id')}")
    lines.append(f"产品: {result.get('product_name')} ({result.get('product_code')})")
    lines.append(f"类型: {result.get('table_type')}")
    lines.append(f"来源: 第 {result.get('page_number')} 页")
    
    lines.append("\n数据预览:")
    headers = result.get('headers', [])
    rows = result.get('rows', [])
    
    # 使用Markdown表格格式
    if headers:
        lines.append("| " + " | ".join(headers) + " |")
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
        
        # 限制显示行数，避免太长
        display_rows = rows[:20]
        for row in display_rows:
            lines.append("| " + " | ".join(row) + " |")
            
        if len(rows) > 20:
            lines.append(f"\n... (共 {len(rows)} 行，仅显示前20行)")
    
    return "\n".join(lines)


async def main():
    """主函数：启动MCP服务器"""
    logger.info("启动Insurance MCP Server...")
    
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
