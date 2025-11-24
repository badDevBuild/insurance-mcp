from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field

class DocElement(BaseModel):
    """Base class for document elements"""
    type: str
    content: str
    page_number: int
    bbox: Optional[List[float]] = None  # [x0, y0, x1, y1]
    level: int = 0  # For headings
    metadata: Dict[str, Any] = Field(default_factory=dict)

class DocTable(DocElement):
    """Table element"""
    type: str = "table"
    rows: List[List[str]]
    headers: List[str]
    is_rate_table: bool = False
    csv_path: Optional[str] = None

class ParsedDocument(BaseModel):
    """Intermediate representation of a parsed document"""
    elements: List[DocElement]
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def get_tables(self) -> List[DocTable]:
        return [e for e in self.elements if isinstance(e, DocTable)]

    def to_markdown(self, exclude_rate_tables: bool = False) -> str:
        """Convert to Markdown"""
        md_lines = []
        for element in self.elements:
            if isinstance(element, DocTable):
                if exclude_rate_tables and element.is_rate_table:
                    continue
                # Convert table to markdown
                md_lines.append(self._table_to_markdown(element))
            else:
                # Headings and text
                if element.type == "heading":
                    md_lines.append(f"{'#' * element.level} {element.content}")
                else:
                    md_lines.append(element.content)
            md_lines.append("") # Empty line after each element
        return "\n".join(md_lines)

    def _table_to_markdown(self, table: DocTable) -> str:
        """Simple markdown table generator"""
        if not table.headers and not table.rows:
            return ""
        
        lines = []
        # Headers
        if table.headers:
            lines.append("| " + " | ".join(table.headers) + " |")
            lines.append("| " + " | ".join(["---"] * len(table.headers)) + " |")
        
        # Rows
        for row in table.rows:
            lines.append("| " + " | ".join(row) + " |")
            
        return "\n".join(lines)

class BaseParser(ABC):
    """Abstract base parser"""
    
    @abstractmethod
    def parse(self, pdf_path: Path) -> ParsedDocument:
        """Parse PDF to structured document"""
        pass
