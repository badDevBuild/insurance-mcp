"""端到端测试运行器 - 50问题黄金测试集

执行完整的50个测试用例,生成详细的测试报告。
"""
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any
import logging

# 添加项目根目录到sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.mcp_server.tools.search_policy_clause import SearchPolicyClauseTool
from src.common.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

class TestCaseResult:
    """测试用例结果"""
    def __init__(self, test_case: Dict[str, Any]):
        self.test_id = test_case['id']
        self.question = test_case['question']
        self.query_type = test_case['query_type']
        self.expected_section_ids = test_case.get('expected_section_ids', [])
        self.expected_category = test_case.get('expected_category')
        self.min_similarity = test_case.get('min_similarity_score', 0.5)
        self.top_k = test_case.get('top_k', 5)
        
        # 结果字段
        self.status = "未执行"
        self.mcp_response = []  # List[ClauseResult]
        self.top_1_similarity = 0.0
        self.section_ids_matched = []
        self.category_distribution = {}
        self.error = None
        self.execution_time = 0.0
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "test_id": self.test_id,
            "question": self.question,
            "query_type": self.query_type,
            "expected_section_ids": self.expected_section_ids,
            "status": self.status,
            "top_1_similarity": self.top_1_similarity,
            "section_ids_matched": self.section_ids_matched,
            "category_distribution": self.category_distribution,
            "mcp_response_count": len(self.mcp_response),
            "execution_time_ms": round(self.execution_time * 1000, 2),
            "error": self.error
        }

class EndToEndTestRunner:
    """端到端测试运行器"""
    
    def __init__(self, test_set_path: str):
        self.test_set_path = Path(test_set_path)
        self.test_data = self._load_test_set()
        self.results: List[TestCaseResult] = []
        self.search_tool = SearchPolicyClauseTool()
        
    def _load_test_set(self) -> Dict[str, Any]:
        """加载测试集"""
        with open(self.test_set_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def run_all_tests(self):
        """运行所有测试用例"""
        logger.info(f"开始执行{len(self.test_data['test_cases'])}个测试用例...")
        
        for i, test_case in enumerate(self.test_data['test_cases'], 1):
            logger.info(f"[{i}/{len(self.test_data['test_cases'])}] 执行: {test_case['id']} - {test_case['question']}")
            result = self._run_single_test(test_case)
            self.results.append(result)
            
        logger.info("所有测试用例执行完成")
    
    def _run_single_test(self, test_case: Dict[str, Any]) -> TestCaseResult:
        """运行单个测试用例"""
        result = TestCaseResult(test_case)
        
        try:
            import time
            start_time = time.time()
            
            # 调用MCP工具
            # 如果测试用例未指定产品，默认使用"平安福耀年金保险（分红型）"
            product_name = test_case.get('product_name') or "平安福耀年金保险（分红型）"
            
            mcp_response = self.search_tool.run(
                query=test_case['question'],
                company=test_case.get('company', '平安人寿'),
                product_name=product_name,
                n_results=result.top_k,
                min_similarity=result.min_similarity,
                auto_fetch_rate_tables=True
            )
            
            result.execution_time = time.time() - start_time
            result.mcp_response = mcp_response
            
            # 分析结果
            if mcp_response:
                result.top_1_similarity = mcp_response[0].similarity_score
                
                # 提取匹配的section_ids
                result.section_ids_matched = [
                    r.section_id for r in mcp_response if r.section_id
                ]
                
                # 统计category分布
                category_counts = {}
                for r in mcp_response:
                    cat = getattr(r, 'category', 'Unknown')
                    category_counts[cat] = category_counts.get(cat, 0) + 1
                result.category_distribution = category_counts
                
                # 判断成功/失败
                if result.expected_section_ids:
                    # 检查期望的section_id是否在结果中
                    matched = any(
                        exp_id in result.section_ids_matched 
                        for exp_id in result.expected_section_ids
                    )
                    result.status = "通过" if matched else "失败"
                else:
                    # 无Ground Truth时,根据相似度判断
                    result.status = "通过" if result.top_1_similarity >= result.min_similarity else "失败"
            else:
                result.status = "失败"
                result.error = "未返回结果"
                
        except Exception as e:
            result.status = "错误"
            result.error = str(e)
            logger.error(f"测试用例 {test_case['id']} 执行失败: {e}", exc_info=True)
        
        return result
    
    def generate_detailed_report(self, output_path: str):
        """生成详细报告(JSON)"""
        report = {
            "test_set_name": self.test_data['name'],
            "test_set_version": self.test_data['version'],
            "total_count": len(self.results),
            "execution_time": datetime.now().isoformat(),
            "summary": self._generate_summary(),
            "detailed_results": []
        }
        
        for result in self.results:
            detailed = result.to_dict()
            # 添加MCP响应详情
            detailed['mcp_responses'] = [
                {
                    "rank": i + 1,
                    "chunk_id": r.chunk_id,
                    "content_preview": r.content[:200] + "..." if len(r.content) > 200 else r.content,
                    "section_id": r.section_id,
                    "section_title": r.section_title,
                    "similarity_score": round(r.similarity_score, 4),
                    "category": getattr(r, 'category', 'Unknown'),
                    "doc_type": r.doc_type if hasattr(r, 'doc_type') else '产品条款',
                    "product_name": r.source_reference.product_name,
                    "rate_table_content": r.rate_table_content  # 添加表格内容
                }
                for i, r in enumerate(result.mcp_response)
            ]
            report['detailed_results'].append(detailed)
        
        # 保存JSON报告
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"详细报告已保存到: {output_path}")
        return report
    
    def generate_markdown_report(self, output_path: str):
        """生成Markdown格式报告"""
        lines = ["# 端到端测试报告 - 50问题黄金测试集\n"]
        lines.append(f"**测试集**: {self.test_data['name']}\n")
        lines.append(f"**执行时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"**测试用例总数**: {len(self.results)}\n")
        
        # 汇总统计
        summary = self._generate_summary()
        lines.append("\n## 测试摘要\n")
        lines.append(f"- ✅ **通过**: {summary['passed']}")
        lines.append(f"- ❌ **失败**: {summary['failed']}")
        lines.append(f"- ⚠️ **错误**: {summary['error']}")
        lines.append(f"- 📊 **通过率**: {summary['pass_rate']:.2f}%\n")
        
        # 按类型统计
        lines.append("\n## 按查询类型统计\n")
        for qtype, stats in summary['by_type'].items():
            lines.append(f"\n### {qtype.upper()}\n")
            lines.append(f"- 总数: {stats['total']}")
            lines.append(f"- 通过: {stats['passed']}")
            lines.append(f"- 失败: {stats['failed']}")
            lines.append(f"- 通过率: {stats['pass_rate']:.2f}%\n")
        
        # 详细结果
        lines.append("\n## 详细测试结果\n")
        
        for i, result in enumerate(self.results, 1):
            status_icon = "✅" if result.status == "通过" else "❌" if result.status == "失败" else "⚠️"
            lines.append(f"\n### {i}. {status_icon} {result.test_id}\n")
            lines.append(f"**问题**: {result.question}\n")
            lines.append(f"**类型**: {result.query_type} | **状态**: {result.status}\n")
            
            if result.error:
                lines.append(f"**错误**: {result.error}\n")
                continue
            
            if result.mcp_response:
                lines.append(f"\n**Top-1相似度**: {result.top_1_similarity:.4f}\n")
                lines.append(f"**期望章节**: {', '.join(result.expected_section_ids) if result.expected_section_ids else 'N/A'}\n")
                lines.append(f"**匹配章节**: {', '.join(result.section_ids_matched[:3])}\n")
                
                lines.append("\n**MCP返回结果**:\n")
                for j, r in enumerate(result.mcp_response, 1):
                    lines.append(f"\n{j}. **{r.section_title}** (章节: {r.section_id}, 相似度: {r.similarity_score:.4f})")
                    
                    # 展示内容预览
                    content_preview = r.content[:300].replace('\n', ' ') + "..."
                    lines.append(f"   > {content_preview}\n")
                    
                    # 如果有表格内容，展示出来
                    if r.rate_table_content:
                        lines.append("\n   **📊 附带表格数据**:\n")
                        # 缩进表格内容以便阅读
                        table_lines = r.rate_table_content.split('\n')
                        for tl in table_lines:
                            lines.append(f"   {tl}")
                        lines.append("\n")
            
            lines.append("\n" + "-" * 80 + "\n")
        
        # 保存Markdown报告
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        logger.info(f"Markdown报告已保存到: {output_path}")
    
    def _generate_summary(self) -> Dict[str, Any]:
        """生成摘要统计"""
        passed = sum(1 for r in self.results if r.status == "通过")
        failed = sum(1 for r in self.results if r.status == "失败")
        error = sum(1 for r in self.results if r.status == "错误")
        
        # 按类型统计
        by_type = {}
        for result in self.results:
            qtype = result.query_type
            if qtype not in by_type:
                by_type[qtype] = {"total": 0, "passed": 0, "failed": 0, "error": 0}
            by_type[qtype]["total"] += 1
            if result.status == "通过":
                by_type[qtype]["passed"] += 1
            elif result.status == "失败":
                by_type[qtype]["failed"] += 1
            else:
                by_type[qtype]["error"] += 1
        
        # 计算通过率
        for stats in by_type.values():
            stats['pass_rate'] = (stats['passed'] / stats['total'] * 100) if stats['total'] > 0 else 0
        
        return {
            "total": len(self.results),
            "passed": passed,
            "failed": failed,
            "error": error,
            "pass_rate": (passed / len(self.results) * 100) if self.results else 0,
            "by_type": by_type
        }

if __name__ == "__main__":
    # 测试集路径
    test_set_path = project_root / "tests/golden_dataset/phase5_test_set_labeled.json"
    
    # 创建运行器
    runner = EndToEndTestRunner(str(test_set_path))
    
    # 运行测试
    runner.run_all_tests()
    
    # 生成报告
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_report_path = project_root / f"test_report_{timestamp}.json"
    md_report_path = project_root / f"test_report_{timestamp}.md"
    
    runner.generate_detailed_report(str(json_report_path))
    runner.generate_markdown_report(str(md_report_path))
    
    print(f"\n✅ 测试完成!")
    print(f"📄 详细报告(JSON): {json_report_path}")
    print(f"📄 可读报告(Markdown): {md_report_path}")
