"""
PDF转Markdown转换器

使用markitdown实现高保真PDF转Markdown转换
重点支持：产品条款、产品说明书
"""

from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import hashlib

from markitdown import MarkItDown

from src.common.logging import logger
from src.common.models import PolicyDocument, VerificationStatus, DocumentType
from src.common.repository import SQLiteRepository


class PDFConverter:
    """
    PDF到Markdown转换器
    
    特性：
    - 使用markitdown实现高保真转换
    - 自动处理排版、表格、列表
    - 支持条款和说明书文档
    - 转换结果保存到processed目录
    """
    
    def __init__(self):
        self.converter = MarkItDown()
        self.repo = SQLiteRepository()
        
        # 支持的文档类型（聚焦条款和说明书）
        # 支持的文档类型
        self.supported_doc_types = {
            DocumentType.CLAUSE.value,
            DocumentType.MANUAL.value,
            DocumentType.RATE_TABLE.value
        }
        
        logger.info(f"PDFConverter initialized. Supported types: {', '.join(self.supported_doc_types)}")
    
    def is_supported(self, doc_type: str) -> bool:
        """检查文档类型是否支持"""
        return doc_type in self.supported_doc_types
    
    def convert_document(self, doc: PolicyDocument) -> Dict[str, Any]:
        """
        转换单个PDF文档
        
        Args:
            doc: PolicyDocument对象
            
        Returns:
            转换结果字典
        """
        result = {
            "success": False,
            "document_id": doc.id,
            "doc_type": doc.doc_type,
            "error": None,
            "markdown_length": 0,
            "output_path": None
        }
        
        try:
            # 检查文档类型
            if not self.is_supported(doc.doc_type):
                result["error"] = f"不支持的文档类型: {doc.doc_type}"
                logger.warning(f"[{doc.filename}] {result['error']}")
                return result
            
            # 检查PDF文件是否存在
            pdf_path = Path(doc.local_path)
            if not pdf_path.exists():
                result["error"] = f"PDF文件不存在: {pdf_path}"
                logger.error(f"[{doc.filename}] {result['error']}")
                return result
            
            logger.info(f"[{doc.filename}] 开始转换PDF → Markdown")
            
            # 根据文档类型选择转换策略
            if doc.doc_type == DocumentType.CLAUSE:
                markdown_text = self._convert_clause(pdf_path)
            elif doc.doc_type == DocumentType.MANUAL:
                markdown_text = self._convert_manual(pdf_path)
            elif doc.doc_type == DocumentType.RATE_TABLE:
                markdown_text = self._convert_rate_table(pdf_path)
            else:
                # 默认策略
                convert_result = self.converter.convert(str(pdf_path))
                markdown_text = convert_result.text_content
            
            if not markdown_text or len(markdown_text) < 100:
                result["error"] = "转换结果为空或内容过少"
                logger.error(f"[{doc.filename}] {result['error']}")
                return result
            
            result["markdown_length"] = len(markdown_text)
            logger.info(f"[{doc.filename}] 转换成功，输出 {result['markdown_length']} 字符")
            
            # 保存Markdown文件到processed目录
            processed_dir = Path("data/processed")
            processed_dir.mkdir(parents=True, exist_ok=True)
            
            # 使用文档ID作为文件名
            output_path = processed_dir / f"{doc.id}.md"
            output_path.write_text(markdown_text, encoding='utf-8')
            
            result["output_path"] = str(output_path)
            logger.info(f"[{doc.filename}] Markdown已保存到: {output_path}")
            
            # 更新数据库中的markdown_content字段
            # 注意：对于大文件，我们只保存文件路径而不是全文本
            # 这里我们保存前5000字符作为预览
            preview = markdown_text[:5000] if len(markdown_text) > 5000 else markdown_text
            
            # 通过repository更新文档
            with self.repo.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE policy_documents 
                    SET markdown_content = ?,
                        verification_status = ?
                    WHERE id = ?
                    """,
                    (preview, VerificationStatus.PENDING.value, doc.id)
                )
                conn.commit()
            
            logger.info(f"[{doc.filename}] 数据库已更新，状态: {VerificationStatus.PENDING.value}")
            
            result["success"] = True
            
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"[{doc.filename}] 转换失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        return result
    
    def _convert_clause(self, pdf_path: Path) -> str:
        """
        产品条款解析策略
        
        特点:
        - 章节结构清晰
        - 条款编号重要
        - 需要保留层级关系
        """
        logger.info(f"Using CLAUSE strategy for {pdf_path.name}")
        # 目前使用通用策略，后续可针对条款结构优化
        result = self.converter.convert(str(pdf_path))
        return result.text_content

    def _convert_manual(self, pdf_path: Path) -> str:
        """
        产品说明书解析策略
        
        特点:
        - 图文并茂
        - 包含案例和示例
        - Q&A格式常见
        """
        logger.info(f"Using MANUAL strategy for {pdf_path.name}")
        # 目前使用通用策略，后续可针对图文混排优化
        result = self.converter.convert(str(pdf_path))
        return result.text_content

    def _convert_rate_table(self, pdf_path: Path) -> str:
        """
        产品费率表解析策略
        
        特点:
        - 大量表格
        - 数值精度重要
        - 多维表格常见
        """
        logger.info(f"Using RATE_TABLE strategy for {pdf_path.name}")
        # 目前使用通用策略，后续可针对表格提取优化
        # MarkItDown对表格支持较好，但可能需要后处理
        result = self.converter.convert(str(pdf_path))
        return result.text_content

    def convert_batch(self, doc_type_filter: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        """
        批量转换PENDING状态的文档
        
        Args:
            doc_type_filter: 文档类型过滤（如"产品条款"）
            limit: 最多转换文档数
            
        Returns:
            批量转换结果统计
        """
        stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "results": []
        }
        
        logger.info(f"开始批量转换，类型过滤: {doc_type_filter or '全部'}, 限制: {limit}")
        
        # 获取所有PENDING状态的文档
        pending_docs = self.repo.get_pending_documents()
        
        # 过滤文档类型
        if doc_type_filter:
            pending_docs = [doc for doc in pending_docs if doc.doc_type == doc_type_filter]
        
        # 只处理支持的文档类型
        pending_docs = [doc for doc in pending_docs if self.is_supported(doc.doc_type)]
        
        # 限制数量
        pending_docs = pending_docs[:limit]
        
        stats["total"] = len(pending_docs)
        
        logger.info(f"找到 {stats['total']} 个待转换文档")
        
        if stats["total"] == 0:
            logger.warning("没有找到待转换的文档")
            return stats
        
        # 逐个转换
        for i, doc in enumerate(pending_docs, 1):
            logger.info(f"\n[{i}/{stats['total']}] 处理: {doc.filename} ({doc.doc_type})")
            
            result = self.convert_document(doc)
            stats["results"].append(result)
            
            if result["success"]:
                stats["success"] += 1
            else:
                stats["failed"] += 1
        
        # 打印总结
        logger.info("\n" + "="*80)
        logger.info("批量转换完成")
        logger.info("="*80)
        logger.info(f"总计: {stats['total']}")
        logger.info(f"成功: {stats['success']}")
        logger.info(f"失败: {stats['failed']}")
        logger.info(f"跳过: {stats['skipped']}")
        logger.info("="*80)
        
        return stats


# 全局实例（单例模式）
_converter: Optional[PDFConverter] = None


def get_converter() -> PDFConverter:
    """获取全局转换器实例"""
    global _converter
    if _converter is None:
        _converter = PDFConverter()
    return _converter

