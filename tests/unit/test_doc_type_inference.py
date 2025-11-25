"""智能文档类型推断单元测试"""
import pytest
from src.mcp_server.tools.search_policy_clause import SearchPolicyClauseTool

@pytest.fixture
def tool():
    return SearchPolicyClauseTool()

def test_infer_rate_table(tool):
    """测试费率表推断"""
    # 包含关键词 + 数字
    assert tool._infer_doc_type("30岁保费多少") == "产品费率表"
    assert tool._infer_doc_type("费率表查询 10年") == "产品费率表"
    assert tool._infer_doc_type("一年交多少钱 5000") == "产品费率表"
    
    # 包含关键词但无数字 -> 不推断
    assert tool._infer_doc_type("保费怎么算") is None
    
    # 不包含关键词 -> 不推断
    assert tool._infer_doc_type("30岁买什么保险") is None

def test_infer_other_types(tool):
    """测试其他类型（不应推断）"""
    # 产品说明书关键词 -> 不推断
    assert tool._infer_doc_type("如何购买这个产品") is None
    assert tool._infer_doc_type("投保流程") is None
    
    # 产品条款关键词 -> 不推断
    assert tool._infer_doc_type("身故保险金怎么赔") is None
    assert tool._infer_doc_type("免责条款有哪些") is None

def test_infer_none(tool):
    """测试无法推断的情况"""
    assert tool._infer_doc_type("保险期间多久") is None
    assert tool._infer_doc_type("你好") is None
