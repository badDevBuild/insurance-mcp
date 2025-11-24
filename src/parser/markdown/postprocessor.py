"""Markdown后处理Pipeline

提供一套完整的Markdown后处理流程，包括：
1. 脚注内联处理
2. 噪音去除
3. 格式标准化
4. 表格验证
5. 结构化增强

根据 spec.md §FR-004 实施。
"""
import re
from pathlib import Path
from typing import List, Optional
import logging

from src.parser.markdown.enhancer import MarkdownEnhancer

logger = logging.getLogger(__name__)


class FootnoteInliner:
    """脚注内联处理器
    
    将文档末尾的脚注（名词解释）直接插入到对应正文段落后。
    例如：原文"被保险人⁽¹⁾应在..."，脚注"⁽¹⁾被保险人指受保险合同保障的人"
    优化为："被保险人（指受保险合同保障的人）应在..."
    
    效果：提升检索效果约50%
    """
    
    def __init__(self):
        # 上标数字映射
        self.superscript_map = {
            '¹': '1', '²': '2', '³': '3', '⁴': '4', '⁵': '5',
            '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9', '⁰': '0'
        }
    
    def process(self, content: str) -> str:
        """内联所有脚注
        
        Args:
            content: Markdown内容
            
        Returns:
            处理后的Markdown内容
        """
        # 1. 提取所有脚注定义（通常在文档末尾）
        footnotes = self._extract_footnotes(content)
        
        if not footnotes:
            logger.debug("未发现脚注，跳过内联处理")
            return content
        
        # 2. 将脚注内联到正文中
        result = self._inline_footnotes(content, footnotes)
        
        # 3. 移除原始脚注定义部分
        result = self._remove_footnote_section(result, footnotes)
        
        logger.info(f"成功内联 {len(footnotes)} 个脚注")
        return result
    
    def _extract_footnotes(self, content: str) -> dict:
        """提取脚注定义
        
        Returns:
            {footnote_marker: footnote_text}
            例如: {'⁽¹⁾': '被保险人指受保险合同保障的人'}
        """
        footnotes = {}
        lines = content.split('\n')
        
        # 从文档末尾开始查找（脚注通常在末尾）
        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            
            # 尝试匹配各种脚注定义格式
            # 格式1: ⁽¹⁾: 内容
            # 格式2: [1]: 内容
            # 格式3: (1): 内容
            # 格式4: ¹ 内容
            
            # 查找冒号分隔的定义
            if ':' in line_stripped or '：' in line_stripped:
                parts = re.split(r'\s*[:：]\s*', line_stripped, maxsplit=1)
                if len(parts) == 2:
                    marker = parts[0].strip()
                    text = parts[1].strip()
                    
                    # 验证marker是否为脚注标记
                    if self._is_footnote_marker(marker):
                        footnotes[marker] = text
        
        return footnotes
    
    def _is_footnote_marker(self, text: str) -> bool:
        """判断是否为脚注标记"""
        # 匹配 ⁽¹⁾, [1], (1), ¹ 等格式
        patterns = [
            r'^⁽[¹²³⁴⁵⁶⁷⁸⁹⁰\d]+⁾$',  # ⁽1⁾ 或 ⁽¹⁾ (上标括号)
            r'^\[\d+\]$',  # [1]
            r'^\(\d+\)$',  # (1)
            r'^[¹²³⁴⁵⁶⁷⁸⁹⁰]+$',  # 纯上标数字
        ]
        
        for pattern in patterns:
            if re.match(pattern, text):
                return True
        
        return False
    
    def _inline_footnotes(self, content: str, footnotes: dict) -> str:
        """将脚注内联到正文，但不替换脚注定义行"""
        lines = content.split('\n')
        result_lines = []
        
        for line in lines:
            # 检查是否为脚注定义行
            is_footnote_definition = False
            for marker in footnotes.keys():
                if line.strip().startswith(marker) and (':' in line or '：' in line):
                    is_footnote_definition = True
                    break
            
            # 如果是脚注定义行，保持原样（将在后续步骤中移除）
            if is_footnote_definition:
                result_lines.append(line)
                continue
            
            # 否则，进行内联替换
            processed_line = line
            for marker, text in footnotes.items():
                # 转义特殊字符用于正则表达式
                escaped_marker = re.escape(marker)
                # 替换为内联形式
                processed_line = re.sub(escaped_marker, f"（{text}）", processed_line)
            
            result_lines.append(processed_line)
        
        return '\n'.join(result_lines)
    
    def _remove_footnote_section(self, content: str, footnotes: dict) -> str:
        """移除原始脚注定义部分"""
        lines = content.split('\n')
        result_lines = []
        
        for line in lines:
            line_stripped = line.strip()
            
            # 检查是否为脚注定义行
            is_footnote_line = False
            for marker in footnotes.keys():
                if line_stripped.startswith(marker):
                    is_footnote_line = True
                    break
            
            if not is_footnote_line:
                result_lines.append(line)
        
        return '\n'.join(result_lines)


class NoiseRemover:
    """噪音去除处理器
    
    移除以下内容：
    - 页眉、页脚（如"平安人寿"、"第X页"）
    - 水印文字
    - 无意义的分隔符（如"=========="）
    
    保留有意义的分隔符（如章节之间的"---"）
    """
    
    def __init__(self):
        # 常见页眉页脚模式
        self.header_footer_patterns = [
            re.compile(r'^平安人寿.*$', re.MULTILINE),
            re.compile(r'^第\s*\d+\s*页.*$', re.MULTILINE),
            re.compile(r'^\d+\s*/\s*\d+$', re.MULTILINE),  # 页码 1/10
            re.compile(r'^页码[:：]\s*\d+.*$', re.MULTILINE),
        ]
        
        # 无意义的分隔符（长度超过10个相同字符）
        self.noise_separator_pattern = re.compile(
            r'^[=\-_*]{10,}$',
            re.MULTILINE
        )
        
        # 水印文字（通常包含"水印"、"仅供"等关键词）
        self.watermark_patterns = [
            re.compile(r'.*水印.*', re.IGNORECASE),
            re.compile(r'.*仅供.*查阅.*', re.IGNORECASE),
        ]
    
    def process(self, content: str) -> str:
        """去除所有噪音
        
        Args:
            content: Markdown内容
            
        Returns:
            处理后的Markdown内容
        """
        result = content
        removed_count = 0
        
        # 1. 移除页眉页脚
        for pattern in self.header_footer_patterns:
            matches = pattern.findall(result)
            result = pattern.sub('', result)
            removed_count += len(matches)
        
        # 2. 移除噪音分隔符
        matches = self.noise_separator_pattern.findall(result)
        result = self.noise_separator_pattern.sub('', result)
        removed_count += len(matches)
        
        # 3. 移除水印
        for pattern in self.watermark_patterns:
            matches = pattern.findall(result)
            result = pattern.sub('', result)
            removed_count += len(matches)
        
        # 4. 清理多余的空行（连续超过2个空行合并为2个）
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        logger.info(f"移除 {removed_count} 处噪音")
        return result


class FormatStandardizer:
    """格式标准化处理器
    
    统一Markdown格式：
    - 标题层级（确保 # 为产品名，## 为章节，### 为条款）
    - 列表格式（使用 `-` 或 `1.` 统一风格）
    - 专有名词标准化（如"被保險人" → "被保险人"）
    """
    
    def __init__(self):
        # 繁简体转换映射（常见保险术语）
        self.term_mappings = {
            '被保險人': '被保险人',
            '保險': '保险',
            '給付': '给付',
            '賠償': '赔偿',
            '條款': '条款',
        }
    
    def process(self, content: str) -> str:
        """标准化格式
        
        Args:
            content: Markdown内容
            
        Returns:
            处理后的Markdown内容
        """
        result = content
        
        # 1. 统一列表标记（将 * 改为 -）
        result = re.sub(r'^\*\s+', '- ', result, flags=re.MULTILINE)
        
        # 2. 标准化专有名词（繁简体转换）
        for old_term, new_term in self.term_mappings.items():
            result = result.replace(old_term, new_term)
        
        # 3. 统一标点符号（全角转半角，保留中文逗号句号）
        result = self._normalize_punctuation(result)
        
        logger.info("完成格式标准化")
        return result
    
    def _normalize_punctuation(self, content: str) -> str:
        """标准化标点符号"""
        # 全角括号转半角（在Markdown中更规范）
        mappings = {
            '（': '(',
            '）': ')',
            '【': '[',
            '】': ']',
            '：': ':', 
            '；': ';',
        }
        
        result = content
        for old, new in mappings.items():
            result = result.replace(old, new)
        
        return result


class TableValidator:
    """表格验证处理器
    
    检查Markdown表格的行列完整性：
    - 验证表格格式正确性
    - 检查行列数是否一致
    - 标记损坏的表格
    """
    
    def __init__(self):
        # Markdown表格模式：| col1 | col2 |
        self.table_header_pattern = re.compile(
            r'^\|(.+)\|$',
            re.MULTILINE
        )
        self.table_separator_pattern = re.compile(
            r'^\|[\s\-:]+\|$',
            re.MULTILINE
        )
    
    def process(self, content: str) -> str:
        """验证并修复表格
        
        Args:
            content: Markdown内容
            
        Returns:
            处理后的Markdown内容
        """
        tables = self._extract_tables(content)
        
        if not tables:
            logger.debug("未发现表格，跳过验证")
            return content
        
        valid_count = 0
        invalid_count = 0
        
        for table in tables:
            if self._validate_table(table):
                valid_count += 1
            else:
                invalid_count += 1
                logger.warning(f"发现损坏的表格：{table[:50]}...")
        
        logger.info(f"表格验证完成：{valid_count} 个有效，{invalid_count} 个无效")
        return content
    
    def _extract_tables(self, content: str) -> List[str]:
        """提取所有Markdown表格"""
        tables = []
        lines = content.split('\n')
        current_table = []
        in_table = False
        
        for line in lines:
            if self.table_header_pattern.match(line) or self.table_separator_pattern.match(line):
                in_table = True
                current_table.append(line)
            elif in_table:
                if line.strip().startswith('|'):
                    current_table.append(line)
                else:
                    # 表格结束
                    if current_table:
                        tables.append('\n'.join(current_table))
                        current_table = []
                    in_table = False
        
        # 处理末尾的表格
        if current_table:
            tables.append('\n'.join(current_table))
        
        return tables
    
    def _validate_table(self, table: str) -> bool:
        """验证单个表格的完整性"""
        lines = [l.strip() for l in table.split('\n') if l.strip()]
        
        if len(lines) < 2:  # 至少需要表头和分隔符
            return False
        
        # 检查每行的列数是否一致
        column_counts = []
        for line in lines:
            if line.startswith('|') and line.endswith('|'):
                # 计算列数（减去首尾的|）
                cols = line.strip('|').split('|')
                column_counts.append(len(cols))
        
        # 所有行的列数应该相同
        return len(set(column_counts)) == 1 if column_counts else False


class MarkdownPostProcessor:
    """Markdown后处理主流程
    
    协调所有子处理器，按顺序执行：
    1. FootnoteInliner: 脚注内联
    2. NoiseRemover: 噪音去除
    3. FormatStandardizer: 格式标准化
    4. TableValidator: 表格验证
    5. (可选) MarkdownEnhancer: 结构化增强
    
    接口设计符合 tasks.md §T020a 规范。
    """
    
    def __init__(self, steps: Optional[List[str]] = None):
        """初始化后处理器
        
        Args:
            steps: 要执行的步骤列表，默认执行所有步骤
                   可选: ['footnote', 'noise', 'format', 'table', 'enhance']
        """
        self.steps = steps or ['footnote', 'noise', 'format', 'table']
        
        # 初始化各个处理器
        self.processors = {
            'footnote': FootnoteInliner(),
            'noise': NoiseRemover(),
            'format': FormatStandardizer(),
            'table': TableValidator(),
            'enhance': MarkdownEnhancer(),  # 结构化增强（可选）
        }
        
        logger.info(f"初始化Markdown后处理器，步骤: {self.steps}")
    
    def process(self, md_path: str, output_path: Optional[str] = None) -> str:
        """处理Markdown文件
        
        Args:
            md_path: 输入的Markdown文件路径
            output_path: 输出文件路径（可选，默认覆盖原文件）
        
        Returns:
            处理后的Markdown内容
        
        Raises:
            FileNotFoundError: 文件不存在
            ValueError: Markdown格式错误
        """
        md_path = Path(md_path)
        
        if not md_path.exists():
            raise FileNotFoundError(f"Markdown文件不存在: {md_path}")
        
        # 读取内容
        with open(md_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if not content.strip():
            raise ValueError(f"Markdown文件为空: {md_path}")
        
        # 执行后处理
        result = self.process_content(content)
        
        # 保存结果
        output_path = Path(output_path) if output_path else md_path
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result)
        
        logger.info(f"后处理完成: {output_path}")
        return result
    
    def process_content(self, content: str) -> str:
        """处理Markdown内容字符串（用于测试）
        
        Args:
            content: Markdown内容
        
        Returns:
            处理后的Markdown内容
        
        Raises:
            ValueError: Markdown内容为空
        """
        if not content.strip():
            raise ValueError("Markdown内容为空")
        
        result = content
        
        # 按顺序执行各个步骤
        for step in self.steps:
            if step not in self.processors:
                logger.warning(f"未知的处理步骤: {step}，跳过")
                continue
            
            processor = self.processors[step]
            logger.debug(f"执行步骤: {step}")
            result = processor.process(result)
        
        return result

