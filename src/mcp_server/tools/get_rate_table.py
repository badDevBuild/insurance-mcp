"""费率表访问工具

实现 get_rate_table MCP工具。
"""
import os
import csv
import json
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

from src.mcp_server.tools.base import BaseTool
from src.common.config import settings
from src.common.models import TableData

logger = logging.getLogger(__name__)

class RateTableData(TableData):
    """费率表数据返回结构 (扩展TableData)"""
    table_id: str
    product_code: str
    product_name: str
    source_pdf: str
    page_number: int
    csv_path: str

class GetRateTableTool(BaseTool):
    """费率表访问工具"""
    
    NAME = "get_rate_table"
    DESCRIPTION = """
    根据费率表UUID获取详细的表格数据（CSV格式）。
    支持简单的行过滤条件（如年龄=30）。
    """
    
    def run(
        self,
        table_id: str,
        filter_conditions: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """执行获取费率表
        
        Args:
            table_id: 费率表UUID
            filter_conditions: 过滤条件字典，key为列名，value为匹配值
            
        Returns:
            RateTableData字典
        """
        logger.info(f"执行get_rate_table: table_id={table_id}, filter={filter_conditions}")
        
        # 1. 加载元数据
        metadata_path = Path(settings.TABLE_EXPORT_DIR) / "metadata.json"
        if not metadata_path.exists():
            raise FileNotFoundError(f"元数据文件不存在: {metadata_path}")
            
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata_list = json.load(f)
            
        # 2. 查找表格元数据
        table_meta = next((item for item in metadata_list if item['id'] == table_id), None)
        if not table_meta:
            raise ValueError(f"未找到ID为 {table_id} 的费率表")
            
        # 3. 读取CSV文件
        csv_path = Path(settings.TABLE_EXPORT_DIR) / f"{table_id}.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV文件不存在: {csv_path}")
            
        rows = []
        headers = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            try:
                headers = next(reader)
            except StopIteration:
                headers = []
                
            for row in reader:
                # 4. 应用过滤条件
                if filter_conditions:
                    match = True
                    for col, val in filter_conditions.items():
                        # 找到列索引
                        try:
                            col_idx = headers.index(col)
                            if row[col_idx] != str(val):
                                match = False
                                break
                        except ValueError:
                            # 列名不存在，忽略该条件或视为不匹配？
                            # 这里选择忽略不存在的列名，避免报错
                            logger.warning(f"过滤列 '{col}' 不存在于表头中: {headers}")
                            pass
                    if not match:
                        continue
                
                rows.append(row)
        
        # 5. 构建返回结果
        result = RateTableData(
            table_id=table_id,
            product_code=table_meta.get('product_code', ''),
            product_name=table_meta.get('product_name', ''),
            table_type=table_meta.get('table_type', 'RATE_TABLE'),
            headers=headers,
            rows=rows,
            row_count=len(rows),
            column_count=len(headers),
            source_pdf=table_meta.get('source_pdf', ''),
            page_number=table_meta.get('page_number', 0),
            csv_path=str(csv_path)
        )
        
        return result.model_dump()

tool = GetRateTableTool()
