"""Markdown后处理器单元测试

测试 src/parser/markdown/postprocessor.py 的各个组件
"""
import pytest
from src.parser.markdown.postprocessor import (
    FootnoteInliner,
    NoiseRemover,
    FormatStandardizer,
    TableValidator,
    MarkdownPostProcessor
)


class TestFootnoteInliner:
    """测试脚注内联功能"""
    
    def test_inline_simple_footnote(self):
        """测试简单脚注内联"""
        inliner = FootnoteInliner()
        
        content = """
被保险人⁽¹⁾应在保险期间内提交申请。

⁽¹⁾: 被保险人指受保险合同保障的人
"""
        
        result = inliner.process(content)
        
        # 应该包含内联后的内容
        assert "被保险人（被保险人指受保险合同保障的人）" in result
        # 原始脚注定义应该被移除
        assert "⁽¹⁾: 被保险人指" not in result
    
    def test_no_footnotes(self):
        """测试没有脚注的情况"""
        inliner = FootnoteInliner()
        
        content = "这是一段没有脚注的正常文本。"
        result = inliner.process(content)
        
        # 内容应该保持不变
        assert result == content


class TestNoiseRemover:
    """测试噪音去除功能"""
    
    def test_remove_header_footer(self):
        """测试移除页眉页脚"""
        remover = NoiseRemover()
        
        content = """
平安人寿保险公司

这是正文内容。

第 10 页
"""
        
        result = remover.process(content)
        
        # 页眉页脚应该被移除
        assert "平安人寿保险公司" not in result
        assert "第 10 页" not in result
        # 正文应该保留
        assert "这是正文内容" in result
    
    def test_remove_noise_separator(self):
        """测试移除无意义分隔符"""
        remover = NoiseRemover()
        
        content = """
正文内容1

====================

正文内容2
"""
        
        result = remover.process(content)
        
        # 长分隔符应该被移除
        assert "====================" not in result
        # 正文应该保留
        assert "正文内容1" in result
        assert "正文内容2" in result
    
    def test_clean_extra_newlines(self):
        """测试清理多余空行"""
        remover = NoiseRemover()
        
        content = "行1\n\n\n\n\n行2"
        result = remover.process(content)
        
        # 多个空行应该合并为两个
        assert "\n\n\n" not in result
        assert "行1\n\n行2" in result


class TestFormatStandardizer:
    """测试格式标准化功能"""
    
    def test_normalize_list_markers(self):
        """测试统一列表标记"""
        standardizer = FormatStandardizer()
        
        content = """
* 项目1
* 项目2
- 项目3
"""
        
        result = standardizer.process(content)
        
        # 所有 * 应该被转换为 -
        assert "* 项目" not in result
        assert "- 项目1" in result
        assert "- 项目2" in result
    
    def test_normalize_terms(self):
        """测试专有名词标准化"""
        standardizer = FormatStandardizer()
        
        content = "被保險人應當提交資料。"
        result = standardizer.process(content)
        
        # 繁体应该转换为简体
        assert "被保险人" in result
        assert "被保險人" not in result
    
    def test_normalize_punctuation(self):
        """测试标点符号标准化"""
        standardizer = FormatStandardizer()
        
        content = "如下（示例）：内容；说明【注释】"
        result = standardizer.process(content)
        
        # 全角标点应该转换为半角
        assert "(示例)" in result
        assert ":内容" in result
        assert ";说明" in result


class TestTableValidator:
    """测试表格验证功能"""
    
    def test_valid_table(self):
        """测试有效表格"""
        validator = TableValidator()
        
        content = """
| 列1 | 列2 | 列3 |
|-----|-----|-----|
| A   | B   | C   |
| D   | E   | F   |
"""
        
        result = validator.process(content)
        
        # 有效表格应该保持不变
        assert "| 列1 | 列2 | 列3 |" in result
    
    def test_extract_multiple_tables(self):
        """测试提取多个表格"""
        validator = TableValidator()
        
        content = """
表格1:
| A | B |
|---|---|
| 1 | 2 |

正文

表格2:
| X | Y | Z |
|---|---|---|
| 3 | 4 | 5 |
"""
        
        tables = validator._extract_tables(content)
        
        # 应该提取到2个表格
        assert len(tables) == 2


class TestMarkdownPostProcessor:
    """测试主后处理流程"""
    
    def test_init_default_steps(self):
        """测试默认步骤初始化"""
        processor = MarkdownPostProcessor()
        
        # 默认应该包含4个基础步骤
        assert 'footnote' in processor.steps
        assert 'noise' in processor.steps
        assert 'format' in processor.steps
        assert 'table' in processor.steps
    
    def test_init_custom_steps(self):
        """测试自定义步骤"""
        processor = MarkdownPostProcessor(steps=['footnote', 'noise'])
        
        # 应该只包含指定的步骤
        assert processor.steps == ['footnote', 'noise']
    
    def test_process_content(self):
        """测试处理内容"""
        processor = MarkdownPostProcessor(steps=['noise', 'format'])
        
        content = """
平安人寿

* 列表项

第 5 页
"""
        
        result = processor.process_content(content)
        
        # 噪音应该被移除
        assert "平安人寿" not in result
        assert "第 5 页" not in result
        
        # 列表标记应该被统一
        assert "- 列表项" in result
    
    def test_process_empty_content(self):
        """测试处理空内容"""
        processor = MarkdownPostProcessor()
        
        with pytest.raises(ValueError):
            processor.process_content("")
    
    def test_sequential_processing(self):
        """测试顺序处理"""
        processor = MarkdownPostProcessor(steps=['footnote', 'noise', 'format'])
        
        content = """
平安人寿

被保险人⁽¹⁾的权利

⁽¹⁾: 被保险人指受保险合同保障的人

* 列表1
"""
        
        result = processor.process_content(content)
        
        # 所有步骤应该被依次执行
        # 1. 脚注内联 (注意：format步骤会将全角括号转半角)
        assert "被保险人(被保险人指受保险合同保障的人)" in result
        # 2. 噪音去除
        assert "平安人寿" not in result
        # 3. 格式标准化
        assert "- 列表1" in result
        assert "* 列表1" not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

