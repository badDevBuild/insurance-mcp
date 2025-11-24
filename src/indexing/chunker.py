"""语义感知切分器：支持表格独立处理

扩展基础的Markdown切分器，支持：
- 表格识别和独立提取
- 表格JSON转换（headers + rows）
- 表格上下文保留
- 与文本chunk按顺序合并

根据 spec.md §FR-009a 和 tasks.md §T023a 实施。
"""
import re
import uuid
from typing import List, Dict, Any, Optional, Tuple
import logging
from datetime import datetime

from src.common.models import PolicyChunk, TableData

logger = logging.getLogger(__name__)


class SemanticChunker:
    """语义感知切分器
    
    在标准Markdown切分基础上，增加表格独立处理能力。
    
    特性：
    - 识别Markdown表格
    - 表格作为独立chunk
    - 表格JSON结构化存储
    - 表格上下文保留（前后文本）
    """
    
    # 表格相关正则
    TABLE_ROW_PATTERN = re.compile(r'^\|(.+)\|$', re.MULTILINE)
    TABLE_SEPARATOR_PATTERN = re.compile(r'^\|[\s\-:]+\|$', re.MULTILINE)
    
    def __init__(self):
        """初始化语义切分器"""
        logger.info("初始化SemanticChunker")
    
    def process_chunks(
        self,
        chunks: List[PolicyChunk],
        document_id: str
    ) -> List[PolicyChunk]:
        """处理chunks，提取表格为独立chunk
        
        Args:
            chunks: 原始PolicyChunk列表
            document_id: 文档ID
        
        Returns:
            处理后的PolicyChunk列表（包含表格chunks）
        """
        logger.info(f"开始处理 {len(chunks)} 个chunks，提取表格...")
        
        processed_chunks = []
        
        for chunk in chunks:
            # 检查是否包含表格
            if self._contains_table(chunk.content):
                # 提取表格并分离
                new_chunks = self._extract_and_split_tables(chunk, document_id)
                processed_chunks.extend(new_chunks)
            else:
                # 普通chunk，直接添加
                processed_chunks.append(chunk)
        
        logger.info(f"处理完成，生成 {len(processed_chunks)} 个chunks（包含表格）")
        
        return processed_chunks
    
    def _contains_table(self, content: str) -> bool:
        """检查内容是否包含Markdown表格
        
        Args:
            content: Markdown内容
        
        Returns:
            是否包含表格
        """
        # 简单检测：至少包含两行以|开头和结尾的行
        lines = content.split('\n')
        table_lines = [l for l in lines if l.strip().startswith('|') and l.strip().endswith('|')]
        
        return len(table_lines) >= 2
    
    def _extract_and_split_tables(
        self,
        chunk: PolicyChunk,
        document_id: str
    ) -> List[PolicyChunk]:
        """从chunk中提取表格，分离为多个chunks
        
        策略：
        1. 识别所有表格
        2. 为每个表格创建独立chunk
        3. 剩余文本作为普通chunk
        4. 按原始顺序排列
        
        Args:
            chunk: 原始PolicyChunk
            document_id: 文档ID
        
        Returns:
            分离后的PolicyChunk列表
        """
        lines = chunk.content.split('\n')
        result_chunks = []
        
        current_text = []
        current_table = []
        in_table = False
        
        for line in lines:
            stripped = line.strip()
            
            # 判断是否为表格行
            is_table_line = (
                stripped.startswith('|') and
                stripped.endswith('|') and
                len(stripped) > 2
            )
            
            if is_table_line:
                if not in_table:
                    # 表格开始，先保存之前的文本
                    if current_text:
                        text_chunk = self._create_text_chunk(
                            '\n'.join(current_text),
                            chunk,
                            document_id
                        )
                        result_chunks.append(text_chunk)
                        current_text = []
                    
                    in_table = True
                
                current_table.append(line)
            
            else:
                if in_table:
                    # 表格结束，保存表格chunk
                    if current_table:
                        table_chunk = self._create_table_chunk(
                            '\n'.join(current_table),
                            chunk,
                            document_id
                        )
                        result_chunks.append(table_chunk)
                        current_table = []
                    
                    in_table = False
                
                current_text.append(line)
        
        # 处理末尾的内容
        if current_table:
            table_chunk = self._create_table_chunk(
                '\n'.join(current_table),
                chunk,
                document_id
            )
            result_chunks.append(table_chunk)
        
        if current_text:
            text_chunk = self._create_text_chunk(
                '\n'.join(current_text),
                chunk,
                document_id
            )
            result_chunks.append(text_chunk)
        
        return result_chunks
    
    def _create_text_chunk(
        self,
        text: str,
        original_chunk: PolicyChunk,
        document_id: str
    ) -> PolicyChunk:
        """创建文本chunk（从原始chunk继承元数据）
        
        Args:
            text: 文本内容
            original_chunk: 原始PolicyChunk
            document_id: 文档ID
        
        Returns:
            新的PolicyChunk
        """
        return PolicyChunk(
            id=str(uuid.uuid4()),
            document_id=document_id,
            content=text.strip(),
            section_id=original_chunk.section_id,
            section_title=original_chunk.section_title,
            category=original_chunk.category,
            entity_role=original_chunk.entity_role,
            parent_section=original_chunk.parent_section,
            level=original_chunk.level,
            page_number=original_chunk.page_number,
            chunk_index=original_chunk.chunk_index,
            keywords=original_chunk.keywords,
            is_table=False,
            created_at=datetime.now()
        )
    
    def _create_table_chunk(
        self,
        table_markdown: str,
        original_chunk: PolicyChunk,
        document_id: str
    ) -> PolicyChunk:
        """创建表格chunk
        
        Args:
            table_markdown: 表格Markdown文本
            original_chunk: 原始PolicyChunk
            document_id: 文档ID
        
        Returns:
            表格PolicyChunk（is_table=True，包含table_data）
        """
        # 解析表格为JSON
        table_data = self._parse_table_to_json(table_markdown)
        
        # 生成表格摘要作为content（用于检索）
        table_summary = self._generate_table_summary(table_data, table_markdown)
        
        return PolicyChunk(
            id=str(uuid.uuid4()),
            document_id=document_id,
            content=table_summary,
            section_id=original_chunk.section_id,
            section_title=original_chunk.section_title,
            category=original_chunk.category,
            entity_role=original_chunk.entity_role,
            parent_section=original_chunk.parent_section,
            level=original_chunk.level,
            page_number=original_chunk.page_number,
            chunk_index=original_chunk.chunk_index,
            keywords=original_chunk.keywords,
            is_table=True,
            table_data=table_data,
            created_at=datetime.now()
        )
    
    def _parse_table_to_json(self, table_markdown: str) -> Dict[str, Any]:
        """将Markdown表格解析为JSON结构
        
        Args:
            table_markdown: 表格Markdown文本
        
        Returns:
            TableData格式的字典
        """
        lines = [l.strip() for l in table_markdown.split('\n') if l.strip()]
        
        if len(lines) < 2:
            return {"table_type": "invalid", "headers": [], "rows": [], "row_count": 0, "column_count": 0}
        
        # 第一行是表头
        header_line = lines[0]
        headers = [cell.strip() for cell in header_line.strip('|').split('|')]
        
        # 跳过分隔符行（第二行）
        # 从第三行开始是数据行
        rows = []
        for line in lines[2:]:
            if line.startswith('|') and line.endswith('|'):
                cells = [cell.strip() for cell in line.strip('|').split('|')]
                rows.append(cells)
        
        return {
            "table_type": "table",
            "headers": headers,
            "rows": rows,
            "row_count": len(rows),
            "column_count": len(headers)
        }
    
    def _generate_table_summary(
        self,
        table_data: Dict[str, Any],
        table_markdown: str
    ) -> str:
        """生成表格摘要（用于向量检索）
        
        策略：
        - 包含表头
        - 包含前3行数据（示例）
        - 包含统计信息
        
        Args:
            table_data: 表格JSON数据
            table_markdown: 原始Markdown表格
        
        Returns:
            表格摘要文本
        """
        headers = table_data.get('headers', [])
        rows = table_data.get('rows', [])
        row_count = table_data.get('row_count', 0)
        column_count = table_data.get('column_count', 0)
        
        summary_parts = []
        
        # 1. 表格描述
        summary_parts.append(f"表格：{column_count}列 × {row_count}行")
        
        # 2. 表头
        if headers:
            summary_parts.append(f"表头：{' | '.join(headers)}")
        
        # 3. 示例数据（前3行）
        if rows:
            sample_rows = rows[:3]
            summary_parts.append("示例数据：")
            for i, row in enumerate(sample_rows, 1):
                summary_parts.append(f"  行{i}: {' | '.join(row)}")
        
        # 4. 原始Markdown（部分，用于关键词匹配）
        summary_parts.append("\n原始表格：")
        summary_parts.append(table_markdown[:500])  # 截断过长内容
        
        return '\n'.join(summary_parts)


def get_semantic_chunker() -> SemanticChunker:
    """工厂函数：获取SemanticChunker实例
    
    Returns:
        SemanticChunker实例
    """
    return SemanticChunker()

