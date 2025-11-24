from typing import List, Dict, Optional, Tuple
from pathlib import Path
import re

class MarkdownChunker:
    """
    Markdown-aware chunker that preserves heading hierarchy and injects breadcrumb paths.
    
    Based on FR-009 requirements:
    - Respects heading boundaries (doesn't split mid-section)
    - Injects complete section path for each chunk
    - Target size: 512-1024 tokens with 128 token overlap
    """
    
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 128):
        self.chunk_size = chunk_size  # Target tokens
        self.chunk_overlap = chunk_overlap
        
    def chunk_with_hierarchy(self, markdown: str, doc_id: str = None) -> List[Dict]:
        """
        Chunk markdown while preserving hierarchy and adding breadcrumb paths.
        
        Returns:
            List of chunk dicts with:
            - content: str
            - section_path: str (breadcrumb like "保险责任 > 重疾 > 给付条件")
            - section_id: str
            - section_title: str
            - level: int
            - chunk_index: int
        """
        lines = markdown.split('\n')
        
        # Parse heading structure
        sections = self._parse_sections(lines)
        
        # Generate chunks with context
        chunks = []
        chunk_idx = 0
        
        for section in sections:
            section_chunks = self._chunk_section(section, chunk_idx)
            chunks.extend(section_chunks)
            chunk_idx += len(section_chunks)
            
        return chunks
        
    def _parse_sections(self, lines: List[str]) -> List[Dict]:
        """
        Parse markdown into hierarchical sections.
        
        Returns list of section dicts with:
        - level: int (1-5)
        - title: str
        - section_id: str (extracted from title)
        - content: List[str] (lines)
        - parent_path: List[str] (titles of ancestors)
        """
        sections = []
        current_section = None
        heading_stack = []  # Stack to track parent headings
        
        for line in lines:
            heading_match = re.match(r'^(#{1,5})\s+(.+)$', line)
            
            if heading_match:
                # Save previous section
                if current_section:
                    sections.append(current_section)
                    
                # Parse new heading
                hashes, title = heading_match.groups()
                level = len(hashes)
                section_id = self._extract_section_id(title)
                
                # Update heading stack (pop deeper levels)
                while heading_stack and heading_stack[-1]['level'] >= level:
                    heading_stack.pop()
                    
                # Build parent path
                parent_path = [h['title'] for h in heading_stack]
                
                # Create new section
                current_section = {
                    'level': level,
                    'title': title,
                    'section_id': section_id,
                    'content': [],
                    'parent_path': parent_path
                }
                
                # Push to stack
                heading_stack.append({
                    'level': level,
                    'title': title
                })
            else:
                # Accumulate content
                if current_section is not None:
                    current_section['content'].append(line)
                else:
                    # Content before first heading - create default section with level=1
                    if not sections or sections[-1].get('level') != 1 or sections[-1].get('title') != '文档开头':
                        sections.append({
                            'level': 1,  # 修正: 使用 level=1 符合 PolicyChunk 验证规则
                            'title': '文档开头',
                            'section_id': '',
                            'content': [line],
                            'parent_path': []
                        })
                    else:
                        sections[-1]['content'].append(line)
                        
        # Save last section
        if current_section:
            sections.append(current_section)
            
        return sections
        
    def _extract_section_id(self, title: str) -> str:
        """
        Extract section ID from title like "1.2.6 身故保险金" -> "1.2.6"
        """
        match = re.match(r'^([\d\.]+)\s+', title)
        if match:
            return match.group(1)
        return ""
        
    def _chunk_section(self, section: Dict, start_idx: int) -> List[Dict]:
        """
        Split a section into chunks if needed, preserving logical boundaries.
        """
        content_text = '\n'.join(section['content']).strip()
        
        if not content_text:
            return []
            
        # Build section path breadcrumb
        path_parts = section['parent_path'] + [section['title']]
        section_path = ' > '.join(path_parts)
        
        # Simple token estimate (rough: 1 token ≈ 1.5 chars for Chinese)
        estimated_tokens = len(content_text) / 1.5
        
        # If section fits in one chunk, return as-is
        if estimated_tokens <= self.chunk_size:
            return [{
                'content': self._add_parent_context(content_text, section_path),
                'section_path': section_path,
                'section_id': section['section_id'],
                'section_title': section['title'],
                'level': section['level'],
                'chunk_index': start_idx
            }]
            
        # Otherwise, split by paragraphs with overlap
        paragraphs = [p.strip() for p in content_text.split('\n\n') if p.strip()]
        
        chunks = []
        current_chunk = []
        current_size = 0
        
        for para in paragraphs:
            para_size = len(para) / 1.5
            
            if current_size + para_size > self.chunk_size and current_chunk:
                # Finalize current chunk
                chunk_text = '\n\n'.join(current_chunk)
                chunks.append({
                    'content': self._add_parent_context(chunk_text, section_path),
                    'section_path': section_path,
                    'section_id': section['section_id'],
                    'section_title': section['title'],
                    'level': section['level'],
                    'chunk_index': start_idx + len(chunks)
                })
                
                # Start new chunk with overlap (keep last paragraph)
                if len(current_chunk) > 0:
                    current_chunk = [current_chunk[-1], para]
                    current_size = len(current_chunk[-2]) / 1.5 + para_size
                else:
                    current_chunk = [para]
                    current_size = para_size
            else:
                current_chunk.append(para)
                current_size += para_size
                
        # Add final chunk
        if current_chunk:
            chunk_text = '\n\n'.join(current_chunk)
            chunks.append({
                'content': self._add_parent_context(chunk_text, section_path),
                'section_path': section_path,
                'section_id': section['section_id'],
                'section_title': section['title'],
                'level': section['level'],
                'chunk_index': start_idx + len(chunks)
            })
            
        return chunks
        
    def _add_parent_context(self, content: str, section_path: str) -> str:
        """
        Prepend breadcrumb path to chunk content.
        """
        return f"[章节: {section_path}]\n\n{content}"
