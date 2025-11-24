from typing import List
import re
from ..parsers.base import DocTable

class TableClassifier:
    """
    Classifies tables into Rate Tables (for separation) or Ordinary Tables (for vectorization).
    """
    
    RATE_KEYWORDS = ["年龄", "age", "保费", "premium", "费率", "rate", "金额", "amount", "利益", "benefit", "现金价值", "cash value"]
    
    def is_rate_table(self, table: DocTable) -> bool:
        """
        Determine if a table is a rate table based on heuristics.
        """
        if not table.rows:
            return False
            
        # Rule 3: Row count check (skip very small tables)
        if len(table.rows) < 5: # Relaxed from 10 to 5 for smaller rate tables
            return False
            
        # Rule 1: Header keyword check
        header_text = " ".join(table.headers).lower()
        has_rate_keyword = any(kw in header_text for kw in self.RATE_KEYWORDS)
        
        # Check first row if headers are empty (sometimes headers are in first row)
        if not has_rate_keyword and table.rows:
            first_row_text = " ".join(table.rows[0]).lower()
            has_rate_keyword = any(kw in first_row_text for kw in self.RATE_KEYWORDS)
            
        if not has_rate_keyword:
            # If strict keyword matching fails, we rely heavily on numeric density
            pass
            
        # Rule 2: Numeric cell ratio
        numeric_cells = 0
        total_cells = 0
        
        for row in table.rows:
            for cell in row:
                total_cells += 1
                # Check if cell contains digit
                if any(c.isdigit() for c in cell):
                    numeric_cells += 1
                    
        if total_cells == 0:
            return False
            
        numeric_ratio = numeric_cells / total_cells
        
        # Decision Logic
        if has_rate_keyword and numeric_ratio > 0.5:
            return True
        
        if numeric_ratio > 0.8: # High numeric density even without obvious keywords
            return True
            
        return False
