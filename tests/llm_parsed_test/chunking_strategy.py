"""
表格感知的Chunking策略

核心逻辑：
1. 检测Markdown表格（以|开头的连续行）
2. 将表格与前后说明文字作为一个完整chunk
3. 不受chunk_size限制
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import re
from typing import List, Dict
from src.indexing.chunkers.markdown_chunker import MarkdownChunker


class TableAwareChunker(MarkdownChunker):
    """
    表格感知Chunker - 专门用于LLM解析文档
    
    特性：
    1. 检测所有Markdown表格
    2. 将表格与前后说明合并为单个chunk
    3. 特殊章节分类（阅读指引、术语、免责等）
    """
    
    def __init__(self, chunk_size: int = 600, chunk_overlap: int = 100):
        super().__init__(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        
        # 特殊章节识别模式
        self.guide_patterns = [r'阅读指引', r'常用术语', r'产品特色']
        self.exclusion_patterns = [r'责任免除', r'不保什么', r'免责']
        self.liability_patterns = [r'保险责任', r'我们保什么', r'保障范围']
    
    def chunk_with_hierarchy(self, markdown: str, doc_id: str = None, doc_type: str = None) -> List[Dict]:
        """
        表格感知的hierarchical chunking
        
        Args:
            markdown: Markdown内容
            doc_id: 文档ID
            doc_type: 文档类型
        
        Returns:
            List of chunk dicts with enhanced metadata
        """
        lines = markdown.split('\n')
        
        # 解析章节结构（继承自父类）
        sections = self._parse_sections(lines)
        
        # 使用表格感知的chunking
        chunks = []
        chunk_idx = 0
        
        for section in sections:
            section_chunks = self._chunk_section_with_table_awareness(section, chunk_idx)
            chunks.extend(section_chunks)
            chunk_idx += len(section_chunks)
        
        # 增强metadata
        for chunk in chunks:
            chunk['doc_type'] = doc_type or "产品条款"
            chunk['category'] = self._classify_chunk(chunk)
        
        return chunks
    
    def _chunk_section_with_table_awareness(self, section: Dict, start_idx: int) -> List[Dict]:
        """
        表格感知的section chunking
        
        核心逻辑：
        1. 检测section中是否包含表格
        2. 如果包含表格，将整个section作为一个chunk（不切分）
        3. 如果不包含表格，按正常逻辑chunking
        """
        content_text = '\n'.join(section['content']).strip()
        
        if not content_text:
            return []
        
        # 构建section path
        path_parts = section['parent_path'] + [section['title']]
        section_path = ' > '.join(path_parts)
        
        # 检测是否包含Markdown表格
        has_table = self._contains_markdown_table(content_text)
        
        if has_table:
            # 包含表格：整个section作为一个chunk，不受chunk_size限制
            return [{
                'content': self._add_parent_context(content_text, section_path),
                'section_path': section_path,
                'section_id': section['section_id'],
                'section_title': section['title'],
                'level': section['level'],
                'chunk_index': start_idx,
                'contains_table': True,
                'table_aware': True  # 标记为表格感知chunk
            }]
        
        # 不包含表格：调用父类的正常chunking逻辑
        return self._chunk_section(section, start_idx)
    
    def _contains_markdown_table(self, text: str) -> bool:
        """
        检测文本中是否包含Markdown表格
        
        Markdown表格特征：
        - 至少2行以|开头和结尾
        - 通常包含分隔行（如 | :---: | :---: |）
        
        Args:
            text: 文本内容
        
        Returns:
            是否包含表格
        """
        lines = text.split('\n')
        table_lines = [line for line in lines if line.strip().startswith('|') and line.strip().endswith('|')]
        
        # 至少需要3行才能构成表格（标题行 + 分隔行 + 至少1行数据）
        if len(table_lines) < 3:
            return False
        
        # 检查是否存在分隔行（包含'-'和':'）
        has_separator = any(
            '-' in line and '|' in line 
            for line in table_lines
        )
        
        return has_separator
    
    def _classify_chunk(self, chunk: Dict) -> str:
        """
        分类chunk到不同的category
        
        Returns:
            category: Liability / Exclusion / Process / Definition / General
        """
        section_title = chunk.get('section_title', '')
        content = chunk.get('content', '')
        
        # 阅读指引和术语定义
        if any(re.search(pattern, section_title) for pattern in self.guide_patterns):
            return "Definition"
        
        # 术语定义
        if '术语' in section_title or '被保险人' in content or '投保人' in content:
            return "Definition"
        
        # 责任免除
        if any(re.search(pattern, section_title) for pattern in self.exclusion_patterns):
            return "Exclusion"
        
        # 保险责任
        if any(re.search(pattern, section_title) for pattern in self.liability_patterns):
            return "Liability"
        
        # 流程相关
        if any(keyword in section_title for keyword in ['如何', '申请', '给付', '支付']):
            return "Process"
        
        return "General"


def create_table_aware_chunker(chunk_size: int = 600, chunk_overlap: int = 100) -> TableAwareChunker:
    """工厂函数"""
    return TableAwareChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
