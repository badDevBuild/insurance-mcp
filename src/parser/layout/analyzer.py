"""
PDF版面分析器

简化版本：使用pdfplumber进行基础的版面分析
检测单栏/双栏布局、表格、图像等元素
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import pdfplumber

from src.common.logging import logger


class LayoutAnalyzer:
    """
    PDF版面分析器
    
    功能：
    - 检测单栏/双栏布局
    - 识别页面元素（文本、表格、图像）
    - 提供版面统计信息
    
    注意：markitdown已自动处理大部分版面问题，
    此分析器主要用于质量检查和统计
    """
    
    def __init__(self):
        logger.info("LayoutAnalyzer initialized")
    
    def analyze_pdf(self, pdf_path: Path) -> Dict[str, Any]:
        """
        分析PDF文件的版面结构
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            版面分析结果
        """
        result = {
            "success": False,
            "total_pages": 0,
            "layout_type": "unknown",  # single_column, double_column, mixed
            "has_tables": False,
            "has_images": False,
            "avg_text_width": 0,
            "pages_analyzed": [],
            "error": None
        }
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                result["total_pages"] = len(pdf.pages)
                
                # 分析前3页来判断版面类型（采样分析）
                sample_pages = min(3, len(pdf.pages))
                
                for i in range(sample_pages):
                    page = pdf.pages[i]
                    page_info = self._analyze_page(page, i + 1)
                    result["pages_analyzed"].append(page_info)
                
                # 汇总分析结果
                if result["pages_analyzed"]:
                    # 判断是否有表格
                    result["has_tables"] = any(p["table_count"] > 0 for p in result["pages_analyzed"])
                    
                    # 判断是否有图像
                    result["has_images"] = any(p["image_count"] > 0 for p in result["pages_analyzed"])
                    
                    # 计算平均文本宽度比例
                    avg_width_ratio = sum(p["text_width_ratio"] for p in result["pages_analyzed"]) / len(result["pages_analyzed"])
                    
                    # 根据文本宽度比例判断单栏/双栏
                    # 单栏通常占页面宽度的70%以上
                    # 双栏通常每栏占40-50%
                    if avg_width_ratio > 0.65:
                        result["layout_type"] = "single_column"
                    elif avg_width_ratio > 0.35:
                        result["layout_type"] = "double_column"
                    else:
                        result["layout_type"] = "mixed"
                    
                    result["avg_text_width"] = avg_width_ratio
                
                result["success"] = True
                logger.info(f"分析完成: {pdf_path.name} - {result['layout_type']}, {result['total_pages']}页")
                
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"分析失败: {pdf_path.name} - {e}")
        
        return result
    
    def _analyze_page(self, page, page_num: int) -> Dict[str, Any]:
        """
        分析单个页面
        
        Args:
            page: pdfplumber页面对象
            page_num: 页码
            
        Returns:
            页面分析结果
        """
        page_info = {
            "page_num": page_num,
            "width": page.width,
            "height": page.height,
            "table_count": 0,
            "image_count": 0,
            "text_width_ratio": 0,
            "char_count": 0
        }
        
        try:
            # 检测表格
            tables = page.find_tables()
            page_info["table_count"] = len(tables)
            
            # 检测图像（简化）
            if hasattr(page, 'images'):
                page_info["image_count"] = len(page.images)
            
            # 提取文本分析宽度
            text = page.extract_text()
            if text:
                page_info["char_count"] = len(text)
                
                # 获取文本框
                words = page.extract_words()
                if words:
                    # 计算文本区域的宽度
                    min_x = min(w['x0'] for w in words)
                    max_x = max(w['x1'] for w in words)
                    text_width = max_x - min_x
                    page_info["text_width_ratio"] = text_width / page.width
                
        except Exception as e:
            logger.warning(f"页面{page_num}分析出错: {e}")
        
        return page_info
    
    def get_quality_score(self, analysis_result: Dict[str, Any]) -> float:
        """
        根据版面分析结果计算质量分数
        
        Args:
            analysis_result: analyze_pdf()的返回结果
            
        Returns:
            质量分数 (0-1)
        """
        if not analysis_result["success"]:
            return 0.0
        
        score = 1.0
        
        # 双栏布局可能导致文字跨栏混乱，降低分数
        if analysis_result["layout_type"] == "double_column":
            score *= 0.8
            logger.warning("检测到双栏布局，建议人工复核")
        
        # 混合布局更复杂，进一步降低分数
        if analysis_result["layout_type"] == "mixed":
            score *= 0.7
            logger.warning("检测到混合布局，建议人工复核")
        
        # 包含表格，需要确认表格还原质量
        if analysis_result["has_tables"]:
            score *= 0.9
            logger.info("检测到表格，建议检查表格还原质量")
        
        return score


# 全局实例
_analyzer: Optional[LayoutAnalyzer] = None


def get_analyzer() -> LayoutAnalyzer:
    """获取全局分析器实例"""
    global _analyzer
    if _analyzer is None:
        _analyzer = LayoutAnalyzer()
    return _analyzer

