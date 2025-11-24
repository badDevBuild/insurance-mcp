import pytest
from pathlib import Path
from src.indexing.parsers.docling_parser import DoclingParser
from src.indexing.parsers.base import DocTable

@pytest.fixture
def sample_pdf_path():
    # Try to find a real PDF in data/raw, otherwise use a mock or skip
    raw_dir = Path("data/raw")
    pdfs = list(raw_dir.glob("**/*.pdf"))
    if pdfs:
        return pdfs[0]
    pytest.skip("No PDF found for testing")

def test_docling_parser_init():
    parser = DoclingParser()
    assert parser is not None

def test_docling_parser_parse(sample_pdf_path):
    parser = DoclingParser()
    doc = parser.parse(sample_pdf_path)
    
    assert doc is not None
    assert len(doc.elements) > 0
    
    # Check elements structure
    has_heading = False
    has_text = False
    
    for element in doc.elements:
        if element.type == "heading":
            has_heading = True
        elif element.type == "text":
            has_text = True
            
    assert has_heading or has_text
    
    # Check markdown export
    md = doc.to_markdown()
    assert len(md) > 0
    
    # Check tables if any
    tables = doc.get_tables()
    for table in tables:
        assert isinstance(table, DocTable)
        assert table.type == "table"
        assert len(table.headers) > 0 or len(table.rows) > 0

if __name__ == "__main__":
    # Manual run for debugging
    import sys
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
        parser = DoclingParser()
        doc = parser.parse(path)
        print(f"Parsed {len(doc.elements)} elements")
        print(doc.to_markdown()[:1000])
    else:
        pytest.main([__file__])
