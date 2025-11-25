"""费率表访问工具单元测试"""
import pytest
import json
import csv
from pathlib import Path
from unittest.mock import patch, mock_open
from src.mcp_server.tools.get_rate_table import GetRateTableTool

@pytest.fixture
def tool():
    return GetRateTableTool()

@pytest.fixture
def mock_metadata():
    return [
        {
            "id": "table_123",
            "product_code": "P001",
            "product_name": "测试产品",
            "table_type": "现金价值表",
            "source_pdf": "test.pdf",
            "page_number": 5
        }
    ]

@pytest.fixture
def mock_csv_content():
    return "保单年度,现金价值\n1,100\n2,200\n3,300"

def test_get_rate_table_success(tool, mock_metadata, mock_csv_content):
    """测试成功获取费率表"""
    with patch("builtins.open", mock_open(read_data=json.dumps(mock_metadata))) as m:
        # 模拟第二次open读取CSV
        m.side_effect = [
            mock_open(read_data=json.dumps(mock_metadata)).return_value,
            mock_open(read_data=mock_csv_content).return_value
        ]
        
        with patch("pathlib.Path.exists", return_value=True):
            result = tool.run("table_123")
            
            assert result["table_id"] == "table_123"
            assert result["headers"] == ["保单年度", "现金价值"]
            assert len(result["rows"]) == 3
            assert result["rows"][0] == ["1", "100"]

def test_get_rate_table_with_filter(tool, mock_metadata, mock_csv_content):
    """测试带过滤条件的获取"""
    with patch("builtins.open", mock_open()) as m:
        m.side_effect = [
            mock_open(read_data=json.dumps(mock_metadata)).return_value,
            mock_open(read_data=mock_csv_content).return_value
        ]
        
        with patch("pathlib.Path.exists", return_value=True):
            # 过滤: 保单年度=2
            result = tool.run("table_123", filter_conditions={"保单年度": "2"})
            
            assert len(result["rows"]) == 1
            assert result["rows"][0] == ["2", "200"]

def test_get_rate_table_not_found(tool):
    """测试表格不存在"""
    with patch("builtins.open", mock_open(read_data="[]")):
        with patch("pathlib.Path.exists", return_value=True):
            with pytest.raises(ValueError, match="未找到ID为 table_999 的费率表"):
                tool.run("table_999")
