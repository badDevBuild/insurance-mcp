from pathlib import Path
from typing import List, Any
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.document import DocItem, SectionHeaderItem, TableItem, TextItem, PictureItem
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableStructureOptions

from .base import BaseParser, ParsedDocument, DocElement, DocTable

class DoclingParser(BaseParser):
    """
    High-fidelity PDF parser using Docling (v2.0+)
    
    优化配置:
    - mode=accurate: 使用精确模式识别表格
    - min_confidence=0.4: 降低阈值以识别更多表格
    """
    
    def __init__(self):
        # 优化表格识别配置
        pipeline_options = PdfPipelineOptions(
            do_table_structure=True,
            do_ocr=False,
            images_scale=1.0,
            table_structure_options=TableStructureOptions(
                mode="accurate",       # 精确模式（比fast慢但更准确）
            )
        )
        
        self.converter = DocumentConverter(
            allowed_formats=[InputFormat.PDF],
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options
                )
            }
        )

    def parse(self, pdf_path: Path) -> ParsedDocument:
        """Parse PDF to structured document using Docling"""
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
            
        # 1. Call Docling API
        conv_result = self.converter.convert(pdf_path)
        doc = conv_result.document
        
        # 2. Convert to internal ParsedDocument format
        elements: List[DocElement] = []
        
        # Iterate through document elements in reading order
        # Docling's export_to_dict or iterating main_text usually follows reading order
        # We'll iterate through body elements
        
        # Flatten the structure if needed or iterate via doc.iterate_items()
        # Depending on docling version, access patterns might vary.
        # Assuming docling 2.x provides an iterator or list of items.
        
        # We can use doc.texts, doc.tables etc but we want interleaved reading order.
        # Usually doc.body.children or similar.
        # Let's use doc.iterate_items() which usually yields in reading order.
        
        for item, level in doc.iterate_items():
            page_no = item.prov[0].page_no if item.prov else 1
            bbox = item.prov[0].bbox if item.prov else None
            bbox_list = [bbox.l, bbox.t, bbox.r, bbox.b] if bbox else None
            
            if isinstance(item, SectionHeaderItem):
                elements.append(DocElement(
                    type="heading",
                    content=item.text,
                    page_number=page_no,
                    bbox=bbox_list,
                    level=level + 1 # Docling root might be 0 or 1, we want 1-based
                ))
            elif isinstance(item, TableItem):
                # Convert Docling table to DocTable
                # item.data is usually a pandas DF or list of lists
                # Docling TableItem has export_to_dataframe() or data field
                
                # Depending on docling version, we might need to handle grid table
                # Assuming simple conversion for now
                df = item.export_to_dataframe()
                headers = df.columns.tolist()
                rows = df.values.tolist()
                # Convert all to string
                rows = [[str(cell) for cell in row] for row in rows]
                headers = [str(h) for h in headers]
                
                elements.append(DocTable(
                    type="table",
                    content="[TABLE]", # Placeholder for text representation
                    page_number=page_no,
                    bbox=bbox_list,
                    rows=rows,
                    headers=headers
                ))
            elif isinstance(item, TextItem):
                # Standard text paragraph
                if item.text.strip():
                    elements.append(DocElement(
                        type="text",
                        content=item.text,
                        page_number=page_no,
                        bbox=bbox_list
                    ))
            # Ignore images for now unless needed
            
        return ParsedDocument(elements=elements)
