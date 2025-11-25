"""生成详细的问答报告

从测试runner的结果生成包含每个问题和完整答案的详细报告。
"""
import json
import sys
from pathlib import Path
from datetime import datetime

# 添加项目根目录到sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tests.test_runner_product_level import ProductLevelTestRunner

def generate_detailed_qa_report(runner: ProductLevelTestRunner, output_path: str):
    """生成包含完整问答对的详细报告"""
    lines = ["# 产品级别测试 - 详细问答报告\n"]
    lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    lines.append(f"**测试总数**: {len(runner.results)}\n")
    
    # 按类别组织
    categories = {
        "product_lookup": "产品查询测试",
        "basic_query": "基础查询测试",
        "comparison_query": "对比查询测试",
        "rate_table_query": "费率表查询测试",
        "exclusion_query": "免责条款查询测试"
    }
    
    for cat_key, cat_name in categories.items():
        cat_results = [r for r in runner.results if r.category == cat_key]
        if not cat_results:
            continue
        
        lines.append(f"\n---\n\n## {cat_name}\n")
        
        for i, result in enumerate(cat_results, 1):
            status_icon = "✅" if result.status == "通过" else "❌" if result.status == "失败" else "⚠️"
            
            lines.append(f"\n### {i}. {status_icon} {result.test_id}\n")
            lines.append(f"**问题**: {result.question}\n")
            
            if result.product_name:
                lines.append(f"**产品**: {result.product_name}\n")
            if result.company:
                lines.append(f"**公司**: {result.company}\n")
            
            lines.append(f"**状态**: {result.status}\n")
            
            if result.error:
                lines.append(f"**错误**: {result.error}\n")
                lines.append("\n---\n")
                continue
            
            # 显示MCP响应
            if result.response:
                lines.append(f"\n**MCP返回** ({len(result.response)}条结果):\n")
                
                for j, resp in enumerate(result.response[:5], 1):  # 最多显示Top-5
                    content_preview = ""  # 初始化
                    
                    # 判断响应类型: ProductInfo 或 ClauseResult
                    if hasattr(resp, 'product_name') and hasattr(resp, 'product_code'):
                        # ProductInfo (来自lookup_product)
                        lines.append(f"\n{j}. **{resp.product_name}**\n")
                        lines.append(f"   *产品代码: {resp.product_code} | 公司: {resp.company}*\n")
                        if hasattr(resp, 'category'):
                            lines.append(f"   *类别: {resp.category}*\n")
                        content_preview = f"产品类型: {getattr(resp, 'category', 'N/A')}"
                    else:
                        # ClauseResult (来自search_policy_clause)
                        section_title = getattr(resp, 'section_title', '未知标题')
                        lines.append(f"\n{j}. **{section_title}**\n")
                        
                        # 元数据
                        metadata_parts = []
                        if hasattr(resp, 'similarity_score'):
                            metadata_parts.append(f"相似度: {resp.similarity_score:.4f}")
                        if hasattr(resp, 'doc_type'):
                            metadata_parts.append(f"类型: {resp.doc_type}")
                        if hasattr(resp, 'source_reference') and resp.source_reference:
                            metadata_parts.append(f"产品: {resp.source_reference.product_name}")
                        
                        if metadata_parts:
                            lines.append(f"   *{' | '.join(metadata_parts)}*\n")
                        
                        # 内容预览
                        content = getattr(resp, 'content', str(resp))
                        # 清理换行和多余空格
                        content_clean = ' '.join(content.split())
                        content_preview = content_clean[:300] + "..." if len(content_clean) > 300 else content_clean
                    
                    if content_preview:
                        lines.append(f"\n   > {content_preview}\n")
            else:
                lines.append("\n**MCP返回**: 无结果\n")
            
            lines.append("\n---\n")
    
    # 保存
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"✅ 详细问答报告已保存到: {output_path}")

if __name__ == "__main__":
    # 加载测试集
    test_set_path = project_root / "tests/golden_dataset/phase5_test_set_product_level.json"
    
    print("正在重新运行测试以获取完整响应...")
    runner = ProductLevelTestRunner(str(test_set_path))
    runner.run_all_tests()
    
    # 生成详细报告
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    qa_report_path = project_root / f"test_qa_report_{timestamp}.md"
    
    generate_detailed_qa_report(runner, str(qa_report_path))
    
    print(f"\n📄 详细问答报告: {qa_report_path}")
