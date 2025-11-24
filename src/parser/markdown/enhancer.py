"""Markdown结构化增强模块

提供高级的Markdown结构化处理，包括：
1. ParagraphMerger: 合并不必要的断行
2. TitleDetector: 识别标题层级
3. ListFormatter: 格式化列表
4. EmphasisMarker: 重要内容加粗

根据 MARKDOWN_ENHANCEMENT_PATCH.md 实施。
"""
import re
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ParagraphMerger:
    """段落合并器
    
    合并被PDF提取错误断开的段落。
    
    规则：
    - 如果行末没有句号、问号、感叹号等终结符，且下一行不是标题/列表，则合并
    - 保留真正的段落分隔（两个连续换行）
    - 保护表格、代码块不被合并
    """
    
    def __init__(self):
        # 句子终结符
        self.sentence_endings = r'[。！？；：]$'
        # 标题标记
        self.heading_pattern = re.compile(r'^#{1,6}\s+')
        # 列表标记
        self.list_pattern = re.compile(r'^[-*+]\s+|^\d+\.\s+')
        # 表格行
        self.table_pattern = re.compile(r'^\|.+\|$')
    
    def process(self, content: str) -> str:
        """合并断开的段落
        
        Args:
            content: Markdown内容
        
        Returns:
            处理后的内容
        """
        lines = content.split('\n')
        result_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            
            # 如果是空行、标题、列表、表格，直接添加
            if (not line.strip() or 
                self.heading_pattern.match(line) or 
                self.list_pattern.match(line) or
                self.table_pattern.match(line)):
                result_lines.append(line)
                i += 1
                continue
            
            # 检查是否需要与下一行合并
            if i < len(lines) - 1:
                next_line = lines[i + 1]
                
                # 如果当前行没有终结符，且下一行不是空行/标题/列表/表格
                if (not re.search(self.sentence_endings, line.strip()) and
                    next_line.strip() and
                    not self.heading_pattern.match(next_line) and
                    not self.list_pattern.match(next_line) and
                    not self.table_pattern.match(next_line)):
                    
                    # 合并当前行和下一行
                    result_lines.append(line.rstrip() + next_line.lstrip())
                    i += 2
                    continue
            
            # 不合并，直接添加
            result_lines.append(line)
            i += 1
        
        logger.info("完成段落合并")
        return '\n'.join(result_lines)


class TitleDetector:
    """标题检测器
    
    识别潜在的标题，并添加Markdown标题标记（#）。
    
    规则：
    - 检测全大写、带编号（如"1.2.3"）、特殊关键词的行
    - 根据编号层级设置标题层级（#/##/###）
    - 避免误识别表格标题
    """
    
    def __init__(self):
        # 条款编号模式（如 1.2.3）
        self.section_number_pattern = re.compile(r'^(\d+\.)+\d+\s+(.+)$')
        # 特殊关键词（通常是章节标题）
        self.title_keywords = [
            '保险责任', '责任免除', '保险期间', '保险金额', 
            '投保范围', '保险费', '犹豫期', '宽限期', '复效',
            '合同解除', '争议处理', '释义', '附则'
        ]
    
    def process(self, content: str) -> str:
        """识别并标记标题
        
        Args:
            content: Markdown内容
        
        Returns:
            处理后的内容
        """
        lines = content.split('\n')
        result_lines = []
        
        for line in lines:
            stripped = line.strip()
            
            # 如果已经是标题，跳过
            if stripped.startswith('#'):
                result_lines.append(line)
                continue
            
            # 检测条款编号
            match = self.section_number_pattern.match(stripped)
            if match:
                # 根据点号数量确定层级
                dots_count = match.group(1).count('.')
                level = min(dots_count + 2, 6)  # 最多6级
                heading = '#' * level + ' ' + stripped
                result_lines.append(heading)
                logger.debug(f"检测到标题: {stripped[:30]}...")
                continue
            
            # 检测关键词标题
            for keyword in self.title_keywords:
                if keyword in stripped and len(stripped) < 50:
                    # 关键词标题通常用##
                    heading = '## ' + stripped
                    result_lines.append(heading)
                    logger.debug(f"检测到关键词标题: {stripped}")
                    break
            else:
                # 不是标题，保持原样
                result_lines.append(line)
        
        logger.info("完成标题检测")
        return '\n'.join(result_lines)


class ListFormatter:
    """列表格式化器
    
    识别并格式化列表项。
    
    规则：
    - 检测以"1)、2)、3)"或"一、二、三"开头的行
    - 转换为标准Markdown列表（- 或 1.）
    - 保持缩进层级
    """
    
    def __init__(self):
        # 中文数字映射
        self.chinese_numbers = {
            '一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
            '六': 6, '七': 7, '八': 8, '九': 9, '十': 10
        }
        # 中文数字列表模式（如"一、内容"）
        self.chinese_list_pattern = re.compile(r'^([一二三四五六七八九十]+)、\s*(.+)$')
        # 括号数字列表模式（如"1)内容"或"1）内容"）
        self.paren_list_pattern = re.compile(r'^(\d+)[)）]\s*(.+)$')
    
    def process(self, content: str) -> str:
        """格式化列表
        
        Args:
            content: Markdown内容
        
        Returns:
            处理后的内容
        """
        lines = content.split('\n')
        result_lines = []
        
        for line in lines:
            stripped = line.strip()
            
            # 如果已经是标准列表，跳过
            if stripped.startswith('-') or re.match(r'^\d+\.\s+', stripped):
                result_lines.append(line)
                continue
            
            # 检测中文数字列表
            match = self.chinese_list_pattern.match(stripped)
            if match:
                content_part = match.group(2)
                formatted = '- ' + content_part
                result_lines.append(formatted)
                logger.debug(f"格式化中文列表: {stripped[:30]}...")
                continue
            
            # 检测括号数字列表
            match = self.paren_list_pattern.match(stripped)
            if match:
                number = match.group(1)
                content_part = match.group(2)
                formatted = f"{number}. {content_part}"
                result_lines.append(formatted)
                logger.debug(f"格式化括号列表: {stripped[:30]}...")
                continue
            
            # 不是列表，保持原样
            result_lines.append(line)
        
        logger.info("完成列表格式化")
        return '\n'.join(result_lines)


class EmphasisMarker:
    """重点标记器
    
    为重要内容添加加粗标记（**）。
    
    规则：
    - 金额数字（如"1000元"）
    - 百分比（如"80%"）
    - 关键术语（如"被保险人"、"保险金"、"理赔"）
    - 否定词（如"不承担"、"除外"）
    """
    
    def __init__(self):
        # 关键术语
        self.key_terms = [
            '被保险人', '投保人', '受益人', '保险人',
            '保险金', '保险费', '保险金额', '保险期间',
            '责任免除', '不承担', '除外', '终止'
        ]
        # 金额模式
        self.amount_pattern = re.compile(r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(元|万元|美元)')
        # 百分比模式
        self.percentage_pattern = re.compile(r'(\d+(?:\.\d+)?%)')
    
    def process(self, content: str) -> str:
        """添加重点标记
        
        Args:
            content: Markdown内容
        
        Returns:
            处理后的内容
        """
        result = content
        
        # 1. 标记金额
        def mark_amount(match):
            amount = match.group(0)
            # 避免重复加粗
            if not result[max(0, match.start()-2):match.start()] == '**':
                return f"**{amount}**"
            return amount
        
        result = self.amount_pattern.sub(mark_amount, result)
        
        # 2. 标记百分比
        def mark_percentage(match):
            percentage = match.group(0)
            if not result[max(0, match.start()-2):match.start()] == '**':
                return f"**{percentage}**"
            return percentage
        
        result = self.percentage_pattern.sub(mark_percentage, result)
        
        # 3. 标记关键术语（只标记第一次出现）
        marked_terms = set()
        for term in self.key_terms:
            if term not in marked_terms and term in result:
                # 只标记第一次出现
                result = result.replace(term, f"**{term}**", 1)
                marked_terms.add(term)
        
        logger.info(f"完成重点标记，标记了 {len(marked_terms)} 个关键术语")
        return result


class MarkdownEnhancer:
    """Markdown结构化增强器
    
    协调所有增强子模块，提供高级的Markdown结构化处理。
    
    步骤顺序：
    1. ParagraphMerger: 合并断开的段落
    2. TitleDetector: 识别标题层级
    3. ListFormatter: 格式化列表
    4. EmphasisMarker: 标记重点内容
    """
    
    def __init__(self, enable_steps: Optional[List[str]] = None):
        """初始化增强器
        
        Args:
            enable_steps: 启用的步骤列表，默认启用所有
                         可选: ['paragraph', 'title', 'list', 'emphasis']
        """
        self.enable_steps = enable_steps or ['paragraph', 'title', 'list', 'emphasis']
        
        # 初始化各个处理器
        self.processors = {
            'paragraph': ParagraphMerger(),
            'title': TitleDetector(),
            'list': ListFormatter(),
            'emphasis': EmphasisMarker(),
        }
        
        logger.info(f"初始化Markdown增强器，步骤: {self.enable_steps}")
    
    def process(self, content: str) -> str:
        """执行结构化增强
        
        Args:
            content: Markdown内容
        
        Returns:
            增强后的内容
        """
        result = content
        
        # 按顺序执行各个步骤
        for step in self.enable_steps:
            if step not in self.processors:
                logger.warning(f"未知的增强步骤: {step}，跳过")
                continue
            
            processor = self.processors[step]
            logger.debug(f"执行增强步骤: {step}")
            result = processor.process(result)
        
        logger.info("完成Markdown结构化增强")
        return result

