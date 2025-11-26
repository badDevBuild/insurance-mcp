"""产品级别端到端测试运行器

执行product-level测试集，支持product_lookup和search_policy_clause测试。
"""
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

# 添加项目根目录到sys.path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.mcp_server.tools.search_policy_clause import SearchPolicyClauseTool
from src.mcp_server.product_lookup import lookup_product
from src.common.logging import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

class ProductLevelTestResult:
    """测试结果"""
    def __init__(self, test_case: Dict[str, Any]):
        self.test_id = test_case['id']
        self.category = test_case['category']
        self.question = test_case['question']
        self.product_name = test_case.get('product_name')
        self.company = test_case.get('company')
        self.expected_doc_type = test_case.get('expected_doc_type')
        
        # 结果
        self.status = "未执行"
        self.response = []
        self.error = None
        self.execution_time = 0.0
        self.doc_type_correct = None  # 仅用于rate_table测试
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        # 格式化响应内容
        formatted_responses = []
        for resp in self.response:
            if hasattr(resp, 'model_dump'):
                # ClauseResult对象
                formatted_responses.append({
                    "content": resp.content[:500] if hasattr(resp, 'content') else '',
                    "section_title": getattr(resp, 'section_title', ''),
                    "section_id": getattr(resp, 'section_id', ''),
                    "similarity_score": getattr(resp, 'similarity_score', 0),
                    "doc_type": getattr(resp, 'doc_type', ''),
                })
            elif isinstance(resp, dict):
                # 产品查询结果
                formatted_responses.append({
                    "product_name": resp.get('product_name', ''),
                    "company": resp.get('company', ''),
                    "similarity": resp.get('similarity', 0)
                })
        
        return {
            "test_id": self.test_id,
            "category": self.category,
            "question": self.question,
            "product_name": self.product_name,
            "status": self.status,
            "response_count": len(self.response),
            "responses": formatted_responses,
            "execution_time_ms": round(self.execution_time * 1000, 2),
            "doc_type_correct": self.doc_type_correct,
            "error": self.error
        }

class ProductLevelTestRunner:
    """产品级别测试运行器"""
    
    def __init__(self, test_set_path: str):
        self.test_set_path = Path(test_set_path)
        self.test_data = self._load_test_set()
        self.results: List[ProductLevelTestResult] = []
        self.search_tool = SearchPolicyClauseTool()
        
    def _load_test_set(self) -> Dict[str, Any]:
        """加载测试集"""
        with open(self.test_set_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def run_all_tests(self):
        """运行所有测试"""
        total = len(self.test_data['test_cases'])
        logger.info(f"开始执行{total}个产品级别测试用例...")
        
        for i, test_case in enumerate(self.test_data['test_cases'], 1):
            logger.info(f"[{i}/{total}] 执行: {test_case['id']} - {test_case['question']}")
            result = self._run_single_test(test_case)
            self.results.append(result)
            
        logger.info("所有测试用例执行完成")
    
    def _run_single_test(self, test_case: Dict[str, Any]) -> ProductLevelTestResult:
        """运行单个测试"""
        result = ProductLevelTestResult(test_case)
        category = test_case['category']
        
        try:
            import time
            start_time = time.time()
            
            if category == 'product_lookup':
                # 产品查询测试
                response = lookup_product(
                    product_name=test_case['question'],
                    company=test_case.get('company')
                )
                result.response = response if isinstance(response, list) else [response]
                result.status = "通过" if len(result.response) > 0 else "失败"
                
            else:
                # 条款查询测试 - 必须提供product_name
                if not test_case.get('product_name'):
                    raise ValueError(f"测试用例{test_case['id']}缺少product_name参数")
                
                response = self.search_tool.run(
                    query=test_case['question'],
                    product_name=test_case['product_name'],
                    company=test_case.get('company'),
                    n_results=5,
                    min_similarity=test_case.get('min_similarity', 0.3)
                )
                result.response = response
                
                # 判断成功/失败
                if not response:
                    result.status = "失败"
                    result.error = "未返回结果"
                else:
                    # 特殊判断: 费率表测试必须检查doc_type
                    if category == 'rate_table_query':
                        top1_doc_type = response[0].doc_type if hasattr(response[0], 'doc_type') else None
                        result.doc_type_correct = (top1_doc_type == test_case['expected_doc_type'])
                        result.status = "通过" if result.doc_type_correct else "失败"
                    else:
                        # 其他测试: 只要有结果且相似度>=阈值就算通过
                        top1_similarity = response[0].similarity_score if response else 0
                        result.status = "通过" if top1_similarity >= test_case.get('min_similarity', 0.3) else "失败"
            
            result.execution_time = time.time() - start_time
            
        except Exception as e:
            result.status = "错误"
            result.error = str(e)
            logger.error(f"测试用例 {test_case['id']} 执行失败: {e}", exc_info=True)
        
        return result
    
    def generate_detailed_report(self, output_path: str):
        """生成详细JSON报告"""
        # 按类别统计
        stats_by_category = {}
        for result in self.results:
            cat = result.category
            if cat not in stats_by_category:
                stats_by_category[cat] = {"total": 0, "passed": 0, "failed": 0, "error": 0}
            stats_by_category[cat]["total"] += 1
            if result.status == "通过":
                stats_by_category[cat]["passed"] += 1
            elif result.status == "失败":
                stats_by_category[cat]["failed"] += 1
            else:
                stats_by_category[cat]["error"] += 1
        
        # 计算通过率
        for stats in stats_by_category.values():
            stats['pass_rate'] = (stats['passed'] / stats['total'] * 100) if stats['total'] > 0 else 0
        
        report = {
            "test_set_name": self.test_data['name'],
            "test_set_version": self.test_data['version'],
            "total_count": len(self.results),
            "execution_time": datetime.now().isoformat(),
            "summary": {
                "total": len(self.results),
                "passed": sum(1 for r in self.results if r.status == "通过"),
                "failed": sum(1 for r in self.results if r.status == "失败"),
                "error": sum(1 for r in self.results if r.status == "错误"),
                "pass_rate": 0,
                "by_category": stats_by_category
            },
            "detailed_results": [r.to_dict() for r in self.results]
        }
        
        # 计算总通过率
        report["summary"]["pass_rate"] = (
            report["summary"]["passed"] / report["summary"]["total"] * 100
            if report["summary"]["total"] > 0 else 0
        )
        
        # 保存
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"详细报告已保存到: {output_path}")
        return report
    
    def generate_markdown_report(self, output_path: str):
        """生成Markdown报告"""
        lines = ["# 产品级别端到端测试报告\n"]
        lines.append(f"**测试集**: {self.test_data['name']}\n")
        lines.append(f"**执行时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"**测试用例总数**: {len(self.results)}\n")
        
        # 总体统计
        passed = sum(1 for r in self.results if r.status == "通过")
        failed = sum(1 for r in self.results if r.status == "失败")
        error = sum(1 for r in self.results if r.status == "错误")
        pass_rate = (passed / len(self.results) * 100) if self.results else 0
        
        lines.append("\n## 测试摘要\n")
        lines.append(f"- ✅ **通过**: {passed}")
        lines.append(f"- ❌ **失败**: {failed}")
        lines.append(f"- ⚠️ **错误**: {error}")
        lines.append(f"- 📊 **通过率**: {pass_rate:.2f}%\n")
        
        # 按类别统计
        lines.append("\n## 按类别统计\n")
        for category in ["product_lookup", "basic_query", "comparison_query", "rate_table_query", "exclusion_query"]:
            cat_results = [r for r in self.results if r.category == category]
            if not cat_results:
                continue
            
            cat_passed = sum(1 for r in cat_results if r.status == "通过")
            cat_failed = sum(1 for r in cat_results if r.status == "失败")
            cat_total = len(cat_results)
            cat_pass_rate = (cat_passed / cat_total * 100) if cat_total > 0 else 0
            
            lines.append(f"\n### {category.upper()}\n")
            lines.append(f"- 总数: {cat_total}")
            lines.append(f"- 通过: {cat_passed}")
            lines.append(f"- 失败: {cat_failed}")
            lines.append(f"- 通过率: {cat_pass_rate:.2f}%\n")
        
        # 详细结果（仅显示失败和错误的）
        lines.append("\n## 失败和错误案例\n")
        failed_cases = [r for r in self.results if r.status in ["失败", "错误"]]
        
        if not failed_cases:
            lines.append("✅ 所有测试通过!\n")
        else:
            for result in failed_cases:
                status_icon = "❌" if result.status == "失败" else "⚠️"
                lines.append(f"\n### {status_icon} {result.test_id}\n")
                lines.append(f"**类别**: {result.category}\n")
                lines.append(f"**问题**: {result.question}\n")
                lines.append(f"**产品**: {result.product_name or 'N/A'}\n")
                lines.append(f"**状态**: {result.status}\n")
                if result.error:
                    lines.append(f"**错误**: {result.error}\n")
                if result.doc_type_correct is not None:
                    lines.append(f"**doc_type正确**: {result.doc_type_correct}\n")
    
    def generate_qa_review_report(self, output_path: str):
        """生成包含所有问题和答案的审阅报告"""
        lines = ["# 测试问答详细审阅报告\n"]
        lines.append(f"**测试集**: {self.test_data['name']}\n")
        lines.append(f"**执行时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"**测试用例总数**: {len(self.results)}\n")
        lines.append(f"**通过**: {sum(1 for r in self.results if r.status == '通过')} | **失败**: {sum(1 for r in self.results if r.status == '失败')}\n")
        
        lines.append("\n---\n")
        
        # 按类别组织
        categories = {
            "product_lookup": "产品查询",
            "basic_query": "基础查询", 
            "comparison_query": "对比查询",
            "rate_table_query": "费率表查询",
            "exclusion_query": "免责查询"
        }
        
        for cat_key, cat_name in categories.items():
            cat_results = [r for r in self.results if r.category == cat_key]
            if not cat_results:
                continue
            
            lines.append(f"\n## {cat_name}\n")
            
            for i, result in enumerate(cat_results, 1):
                status_icon = "✅" if result.status == "通过" else ("❌" if result.status == "失败" else "⚠️")
                lines.append(f"\n### {i}. {status_icon} {result.test_id}\n")
                lines.append(f"**问题**: {result.question}\n")
                if result.product_name:
                    lines.append(f"**产品**: {result.product_name}\n")
                lines.append(f"**状态**: {result.status}\n")
                
                # 显示答案
                if result.response:
                    lines.append(f"\n**答案** ({len(result.response)}条结果):\n")
                    
                    for j, resp in enumerate(result.response[:5], 1):  # 最多显示前5条
                        if hasattr(resp, 'section_title'):
                            # 条款查询结果
                            sim_score = getattr(resp, 'similarity_score', 0)
                            lines.append(f"\n{j}. **{resp.section_title}** (相似度: {sim_score:.4f})\n")
                            if hasattr(resp, 'section_id') and resp.section_id:
                                lines.append(f"   - 章节ID: {resp.section_id}\n")
                            if hasattr(resp, 'doc_type'):
                                lines.append(f"   - 文档类型: {resp.doc_type}\n")
                            if hasattr(resp, 'content'):
                                content_preview = resp.content[:300].replace('\n', ' ')
                                lines.append(f"   - 内容: {content_preview}...\n")
                        elif isinstance(resp, dict) and 'product_name' in resp:
                            # 产品查询结果
                            lines.append(f"\n{j}. **{resp['product_name']}**\n")
                            lines.append(f"   - 公司: {resp.get('company', 'N/A')}\n")
                            lines.append(f"   - 相似度: {resp.get('similarity', 0):.4f}\n")
                else:
                    lines.append(f"\n**答案**: 无结果返回\n")
                
                if result.error:
                    lines.append(f"\n**错误**: {result.error}\n")
                
                lines.append("\n---\n")
        
        # 保存
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        logger.info(f"问答审阅报告已保存到: {output_path}")
        
        # 保存
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        logger.info(f"Markdown报告已保存到: {output_path}")

if __name__ == "__main__":
    # 测试集路径
    test_set_path = project_root / "tests/golden_dataset/phase5_test_set_product_level.json"
    
    # 创建运行器
    runner = ProductLevelTestRunner(str(test_set_path))
    
    # 运行测试
    runner.run_all_tests()
    
    # 生成报告
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_report_path = project_root / f"test_report_product_level_{timestamp}.json"
    md_report_path = project_root / f"test_report_product_level_{timestamp}.md"
    
    runner.generate_detailed_report(str(json_report_path))
    runner.generate_markdown_report(str(md_report_path))
    
    # 生成问答审阅报告
    qa_report_path = project_root / f"test_qa_review_{timestamp}.md"
    runner.generate_qa_review_report(str(qa_report_path))
    
    print(f"\n✅ 测试完成!")
    print(f"📄 详细报告(JSON): {json_report_path}")
    print(f"📄 可读报告(Markdown): {md_report_path}")
    print(f"📋 问答审阅报告: {qa_report_path}")
