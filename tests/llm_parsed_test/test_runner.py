"""
LLM解析文档端到端测试执行器

运行20个测试问题，调用MCP服务，生成测试报告
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
from datetime import datetime
from typing import List, Dict, Any

from tests.llm_parsed_test.config import (
    TEST_QUESTIONS_PATH,
    TEST_REPORT_PATH,
    TEST_VECTOR_STORE_DIR,
    TEST_BM25_INDEX_PATH,
    CHROMA_COLLECTION_NAME
)
from src.indexing.embedding.bge import BGEEmbedder
from src.indexing.vector_store.chroma import ChromaDBStore
from src.indexing.vector_store.hybrid_retriever import BM25Index, create_hybrid_retriever
from src.common.logging import logger


class LLMTestRunner:
    """LLM解析文档端到端测试执行器"""
    
    def __init__(self):
        # 初始化检索组件（指向测试环境）
        self.embedder = BGEEmbedder()
        self.chroma_store = ChromaDBStore(
            persist_directory=str(TEST_VECTOR_STORE_DIR)
        )
        
        # 加载BM25索引
        try:
            self.bm25_index = BM25Index()
            self.bm25_index.load(str(TEST_BM25_INDEX_PATH))
            self.hybrid_retriever = create_hybrid_retriever(
                chroma_store=self.chroma_store,
                bm25_index=self.bm25_index
            )
            logger.info("BM25索引加载成功，将使用混合检索")
        except FileNotFoundError:
            logger.warning("BM25索引未找到，将使用纯向量检索")
            self.bm25_index = None
            self.hybrid_retriever = None
        
        logger.info(f"TestRunner initialized")
    
    def load_questions(self) -> List[Dict]:
        """加载测试问题"""
        with open(TEST_QUESTIONS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        questions = data['questions']
        logger.info(f"加载了 {len(questions)} 个测试问题")
        return questions
    
    def run_single_query(self, question: str, top_k: int = 3) -> List[Dict]:
        """
        执行单个查询
        
        Returns:
            List of results with similarity scores and metadata
        """
        # 生成query embedding
        query_embedding = self.embedder.embed_single(question)
        
        # 执行检索
        if self.hybrid_retriever:
            # 混合检索
            results = self.hybrid_retriever.search(
                query=question,
                query_embedding=query_embedding,
                n_results=top_k,
                auto_weight=True
            )
        else:
            # 纯向量检索
            results = self.chroma_store.search(
                query_embedding=query_embedding,
                n_results=top_k
            )
        
        return results
    
    def evaluate_result(self, results: List[Dict], expected_answer: Dict) -> Dict[str, Any]:
        """
        评估检索结果是否包含正确答案
        
        Returns:
            evaluation dict with hit@1, hit@3, scores
        """
        evaluation = {
            'hit_at_1': False,
            'hit_at_3': False,
            'top1_score': 0.0,
            'top3_scores': [],
            'reasoning': ''
        }
        
        if not results:
            evaluation['reasoning'] = "无检索结果"
            return evaluation
        
        # 提取预期的关键信息
        expected_key_phrase = expected_answer.get('key_phrase', '')
        expected_section_id = expected_answer.get('section_id', '')
        expected_doc_type = expected_answer.get('doc_type', '')
        
        # 评估Top-1
        top1_result = results[0]
        top1_metadata = top1_result.get('metadata', {})
        top1_content = top1_result.get('document', '')
        
        # 处理distance或rrf_score
        distance = top1_result.get('distance')
        if distance is not None:
            evaluation['top1_score'] = 1 - distance
        else:
            # 混合检索返回rrf_score
            evaluation['top1_score'] = top1_result.get('rrf_score', 0.0)
        
        # 检查Top-1是否匹配
        if self._is_match(top1_metadata, top1_content, expected_section_id, expected_key_phrase, expected_doc_type):
            evaluation['hit_at_1'] = True
            evaluation['hit_at_3'] = True
            evaluation['reasoning'] = f"Top-1命中: 相似度{evaluation['top1_score']:.3f}"
        else:
            # 检查Top-3
            for i, result in enumerate(results[:3], 1):
                metadata = result.get('metadata', {})
                content = result.get('document', '')
                
                # 处理distance或rrf_score
                distance = result.get('distance')
                if distance is not None:
                    score = 1 - distance
                else:
                    score = result.get('rrf_score', 0.0)
                
                evaluation['top3_scores'].append(score)
                
                if self._is_match(metadata, content, expected_section_id, expected_key_phrase, expected_doc_type):
                    evaluation['hit_at_3'] = True
                    evaluation['reasoning'] = f"Top-{i}命中: 相似度{score:.3f}"
                    break
            
            if not evaluation['hit_at_3']:
                evaluation['reasoning'] = f"Top-3未命中（最高相似度: {evaluation['top1_score']:.3f}）"
        
        return evaluation
    
    def _is_match(self, metadata: Dict, content: str, expected_section_id: str, 
                  expected_key_phrase: str, expected_doc_type: str) -> bool:
        """判断结果是否匹配预期答案"""
        # 检查文档类型
        if expected_doc_type and metadata.get('doc_type') != expected_doc_type:
            # 如果预期多个doc_type（用逗号分隔）
            if ',' in expected_doc_type:
                doc_types = [dt.strip() for dt in expected_doc_type.split(',')]
                if metadata.get('doc_type') not in doc_types:
                    return False
            else:
                return False
        
        # 检查section_id（如果提供）
        if expected_section_id:
            # 可能有多个section_id（逗号分隔）
            if ',' in expected_section_id:
                section_ids = [sid.strip() for sid in expected_section_id.split(',')]
                if metadata.get('section_id') not in section_ids:
                    return False
            else:
                if metadata.get('section_id') != expected_section_id:
                    return False
        
        # 检查关键短语
        if expected_key_phrase and expected_key_phrase in content:
            return True
        
        # 宽松匹配：section_id正确即可
        if expected_section_id and metadata.get('section_id') == expected_section_id:
            return True
        
        return False
    
    def run_all_tests(self) -> Dict[str, Any]:
        """运行所有测试问题"""
        logger.info("=" * 80)
        logger.info("开始执行测试")
        logger.info("=" * 80)
        
        questions = self.load_questions()
        
        results = {
            'metadata': {
                'total_questions': len(questions),
                'test_time': datetime.now().isoformat(),
                'retrieval_method': 'hybrid' if self.hybrid_retriever else 'semantic'
            },
            'category_stats': {},
            'question_results': []
        }
        
        hit_at_1_count = 0
        hit_at_3_count = 0
        
        for i, question_item in enumerate(questions, 1):
            question = question_item['question']
            category = question_item['category']
            expected_answer = question_item['expected_answer']
            
            logger.info(f"\n[{i}/{len(questions)}] {question}")
            
            # 执行查询
            search_results = self.run_single_query(question, top_k=3)
            
            # 评估结果
            evaluation = self.evaluate_result(search_results, expected_answer)
            
            # 记录结果
            question_result = {
                'id': question_item['id'],
                'question': question,
                'category': category,
                'expected_answer': expected_answer,
                'search_results': search_results,
                'evaluation': evaluation
            }
            results['question_results'].append(question_result)
            
            # 更新统计
            if evaluation['hit_at_1']:
                hit_at_1_count += 1
            if evaluation['hit_at_3']:
                hit_at_3_count += 1
            
            # 打印评估结果
            status = "✅" if evaluation['hit_at_1'] else ("🔶" if evaluation['hit_at_3'] else "❌")
            logger.info(f"  {status} {evaluation['reasoning']}")
        
        # 计算总体统计
        results['overall_stats'] = {
            'hit_at_1_count': hit_at_1_count,
            'hit_at_3_count': hit_at_3_count,
            'hit_at_1_rate': hit_at_1_count / len(questions),
            'hit_at_3_rate': hit_at_3_count / len(questions)
        }
        
        # 按类别统计
        for category in set(q['category'] for q in questions):
            category_questions = [r for r in results['question_results'] if r['category'] == category]
            category_hit_1 = sum(1 for r in category_questions if r['evaluation']['hit_at_1'])
            category_hit_3 = sum(1 for r in category_questions if r['evaluation']['hit_at_3'])
            
            results['category_stats'][category] = {
                'total': len(category_questions),
                'hit_at_1': category_hit_1,
                'hit_at_3': category_hit_3,
                'hit_at_1_rate': category_hit_1 / len(category_questions) if category_questions else 0,
                'hit_at_3_rate': category_hit_3 / len(category_questions) if category_questions else 0
            }
        
        logger.info("\n" + "=" * 80)
        logger.info("测试完成!")
        logger.info("=" * 80)
        logger.info(f"Hit@1: {hit_at_1_count}/{len(questions)} ({results['overall_stats']['hit_at_1_rate']:.1%})")
        logger.info(f"Hit@3: {hit_at_3_count}/{len(questions)} ({results['overall_stats']['hit_at_3_rate']:.1%})")
        
        return results
    
    def generate_report(self, test_results: Dict[str, Any]):
        """生成Markdown测试报告"""
        logger.info(f"\n生成测试报告: {TEST_REPORT_PATH}")
        
        TEST_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        lines = []
        
        # 标题
        lines.extend([
            f"# LLM解析文档测试报告",
            f"",
            f"**测试时间**: {test_results['metadata']['test_time']}",
            f"**检索方法**: {test_results['metadata']['retrieval_method']}",
            f"**问题总数**: {test_results['metadata']['total_questions']}",
            f"",
            f"---",
            f""
        ])
        
        # 执行摘要
        overall = test_results['overall_stats']
        lines.extend([
            f"## 📊 执行摘要",
            f"",
            f"| 指标 | 数值 |",
            f"|------|------|",
            f"| Hit@1准确率 | {overall['hit_at_1_count']}/{test_results['metadata']['total_questions']} ({overall['hit_at_1_rate']:.1%}) |",
            f"| Hit@3准确率 | {overall['hit_at_3_count']}/{test_results['metadata']['total_questions']} ({overall['hit_at_3_rate']:.1%}) |",
            f"",
        ])
        
        # 分类统计
        lines.extend([
            f"## 📈 分类统计",
            f"",
            f"| 类别 | 总数 | Hit@1 | Hit@3 |",
            f"|------|------|-------|-------|",
        ])
        
        category_names = {
            'basic': '基础查询',
            'comparison': '对比查询',
            'rate': '费率查询',
            'exclusion': '免责查询'
        }
        
        for category, stats in test_results['category_stats'].items():
            category_cn = category_names.get(category, category)
            lines.append(
                f"| {category_cn} | {stats['total']} | "
                f"{stats['hit_at_1']}/{stats['total']} ({stats['hit_at_1_rate']:.1%}) | "
                f"{stats['hit_at_3']}/{stats['total']} ({stats['hit_at_3_rate']:.1%}) |"
            )
        
        lines.append("")
        
        # 详细结果
        lines.extend([
            f"## 📝 详细结果",
            f""
        ])
        
        for result in test_results['question_results']:
            q_id = result['id']
            question = result['question']
            category = category_names.get(result['category'], result['category'])
            evaluation = result['evaluation']
            
            # 问题标题
            status_emoji = "✅" if evaluation['hit_at_1'] else ("🔶" if evaluation['hit_at_3'] else "❌")
            lines.extend([
                f"### {status_emoji} 问题 #{q_id}: {question}",
                f"",
                f"**类别**: {category}  ",
                f"**评估**: {evaluation['reasoning']}",
                f"",
            ])
            
            # Top-3结果
            lines.append(f"**检索结果**:")
            lines.append(f"")
            
            for i, search_result in enumerate(result['search_results'][:3], 1):
                metadata = search_result.get('metadata', {})
                content = search_result.get('document', '')
                
                # 处理distance或rrf_score  
                distance = search_result.get('distance')
                if distance is not None:
                    score = 1 - distance
                else:
                    score = search_result.get('rrf_score', 0.0)
                
                lines.extend([
                    f"{i}. **相似度**: {score:.3f} | **文档**: {metadata.get('doc_type', 'N/A')} | "
                    f"**章节**: {metadata.get('section_title', 'N/A')} ({metadata.get('section_id', '')})",
                    f"   ```",
                    f"   {content[:200]}...",
                    f"   ```",
                    f""
                ])
            
            lines.append("---")
            lines.append("")
        
        # 写入文件
        with open(TEST_REPORT_PATH, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        
        logger.info(f"✅ 测试报告已生成: {TEST_REPORT_PATH}")


def main():
    """主函数"""
    import argparse
    from src.common.logging import setup_logging
    
    parser = argparse.ArgumentParser(description="LLM解析文档端到端测试")
    parser.add_argument('--output', default=str(TEST_REPORT_PATH), help="测试报告输出路径")
    
    args = parser.parse_args()
    
    setup_logging()
    
    runner = LLMTestRunner()
    test_results = runner.run_all_tests()
    runner.generate_report(test_results)
    
    # 打印总结
    overall = test_results['overall_stats']
    print(f"\n" + "=" * 80)
    print(f"测试完成! 报告已保存: {TEST_REPORT_PATH}")
    print(f"=" * 80)
    print(f"Hit@1准确率: {overall['hit_at_1_rate']:.1%} ({overall['hit_at_1_count']}/{test_results['metadata']['total_questions']})")
    print(f"Hit@3准确率: {overall['hit_at_3_rate']:.1%} ({overall['hit_at_3_count']}/{test_results['metadata']['total_questions']})")
    print(f"=" * 80)
    
    # 建议
    if overall['hit_at_1_rate'] >= 0.75:
        print(f"✅ 达到目标标准 (Hit@1 ≥ 75%)")
    elif overall['hit_at_3_rate'] >= 0.70:
        print(f"🔶 达到最低标准 (Hit@3 ≥ 70%)")
    else:
        print(f"❌ 未达到最低标准，建议优化chunking策略或embedding模型")


if __name__ == "__main__":
    main()
