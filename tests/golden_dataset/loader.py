"""黄金测试集加载工具

用于加载和管理保险MCP黄金测试集
"""
import json
import sys
from pathlib import Path
from typing import List

# 添加项目根目录到路径
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.common.models import GoldenTestSet, GoldenTestCase


def load_test_set(file_path: str = None) -> GoldenTestSet:
    """
    加载黄金测试集
    
    Args:
        file_path: 测试集JSON文件路径，默认为当前目录下的phase5_test_set_v1.json
    
    Returns:
        GoldenTestSet对象
    """
    if file_path is None:
        file_path = Path(__file__).parent / "phase5_test_set_v1.json"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    return GoldenTestSet(**data)


def get_test_cases_by_tier(tier: int, file_path: str = None) -> List[GoldenTestCase]:
    """
    按层级获取测试用例
    
    Args:
        tier: 测试层级（1=基础, 2=对比, 3=专项）
        file_path: 测试集文件路径（可选）
    
    Returns:
        符合条件的测试用例列表
    """
    test_set = load_test_set(file_path)
    return [tc for tc in test_set.test_cases if tc.tier == tier]


def get_test_cases_by_type(query_type: str, file_path: str = None) -> List[GoldenTestCase]:
    """
    按查询类型获取测试用例
    
    Args:
        query_type: 查询类型（basic/comparison/exclusion）
        file_path: 测试集文件路径（可选）
    
    Returns:
        符合条件的测试用例列表
    """
    test_set = load_test_set(file_path)
    return [tc for tc in test_set.test_cases if tc.query_type == query_type]


def get_test_cases_by_category(category: str, file_path: str = None) -> List[GoldenTestCase]:
    """
    按条款类别获取测试用例
    
    Args:
        category: 条款类别（Liability/Exclusion/Process/Definition）
        file_path: 测试集文件路径（可选）
    
    Returns:
        符合条件的测试用例列表
    """
    test_set = load_test_set(file_path)
    return [
        tc for tc in test_set.test_cases 
        if tc.expected_category and tc.expected_category.value == category
    ]


if __name__ == "__main__":
    # 测试加载
    try:
        test_set = load_test_set()
        print(f"✅ 加载测试集成功: {test_set.name} v{test_set.version}")
        print(f"   描述: {test_set.description}")
        print(f"   总测试用例: {test_set.total_count}")
        print(f"   层级分布: {test_set.tier_distribution}")
        print(f"   类别分布: {test_set.category_distribution}")
        print()
        
        # 测试按层级筛选
        for tier in [1, 2, 3]:
            tier_cases = get_test_cases_by_tier(tier)
            print(f"   Tier {tier} 用例数: {len(tier_cases)}")
            if tier_cases:
                print(f"     示例问题: {tier_cases[0].question}")
        
        print()
        print("✅ 所有测试通过！")
        
    except Exception as e:
        print(f"❌ 加载失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

