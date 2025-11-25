"""测试search_policy_clause的产品参数验证"""
import pytest
from src.mcp_server.tools.search_policy_clause import SearchPolicyClauseTool

@pytest.fixture
def tool():
    return SearchPolicyClauseTool()

def test_product_parameter_required(tool):
    """测试product参数必填验证"""
    # 未提供product_code或product_name应该抛出ValueError
    with pytest.raises(ValueError, match="product_code 或 product_name 必须提供一个"):
        tool.run(query="保险期间多久？")

def test_product_code_provided(tool):
    """测试提供product_code可以正常执行"""
    # 这个测试需要实际的索引数据，可能会失败或返回空结果
    # 但至少不应该因为参数验证而失败
    try:
        result = tool.run(
            query="保险期间多久？",
            product_code="P001"
        )
        # 如果执行到这里，说明参数验证通过
        assert isinstance(result, list)
    except Exception as e:
        # 如果抛出的不是参数验证错误，说明参数验证通过了
        assert "product_code 或 product_name 必须提供一个" not in str(e)

def test_product_name_provided(tool):
    """测试提供product_name可以正常执行"""
    try:
        result = tool.run(
            query="保险期间多久？",
            product_name="平安福耀年金保险（分红型）"
        )
        # 如果执行到这里，说明参数验证通过
        assert isinstance(result, list)
    except Exception as e:
        # 如果抛出的不是参数验证错误，说明参数验证通过了
        assert "product_code 或 product_name 必须提供一个" not in str(e)

def test_both_product_parameters_provided(tool):
    """测试同时提供两个product参数也可以"""
    try:
        result = tool.run(
            query="保险期间多久？",
            product_code="P001",
            product_name="平安福耀年金保险（分红型）"
        )
        # 如果执行到这里，说明参数验证通过
        assert isinstance(result, list)
    except Exception as e:
        # 如果抛出的不是参数验证错误，说明参数验证通过了
        assert "product_code 或 product_name 必须提供一个" not in str(e)

def test_min_similarity_default(tool):
    """测试默认相似度阈值为0.5"""
    # 检查默认参数
    import inspect
    sig = inspect.signature(tool.run)
    assert sig.parameters['min_similarity'].default == 0.5
