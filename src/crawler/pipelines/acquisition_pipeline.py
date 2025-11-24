"""
完整的数据采集管道
包括：产品发现 -> PDF下载 -> 元数据保存到数据库
"""
import asyncio
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.crawler.discovery.pingan_life_spider import PingAnLifeSpider
from src.crawler.acquisition.downloader import PDFDownloader
from src.common.models import Product, PolicyDocument, VerificationStatus
from src.common.repository import SQLiteRepository
from src.common.logging import logger
from src.common.config import config


class AcquisitionPipeline:
    """
    完整的数据采集管道
    
    流程:
    1. 爬取产品列表和PDF链接
    2. 保存产品元数据到数据库
    3. 下载PDF文件到本地
    4. 计算文件哈希并更新数据库
    5. 去重和错误处理
    """
    
    def __init__(self, company: str = "平安人寿"):
        self.company = company
        self.spider = PingAnLifeSpider(headless=True)
        self.downloader = PDFDownloader(max_retries=3, initial_delay=1.0)
        self.repo = SQLiteRepository()
        
        # 统计信息
        self.stats = {
            "products_discovered": 0,
            "products_new": 0,
            "products_existing": 0,
            "pdfs_total": 0,
            "pdfs_downloaded": 0,
            "pdfs_skipped": 0,
            "pdfs_failed": 0,
        }
    
    async def run(self, limit: int = 100, fetch_details: bool = True) -> Dict[str, Any]:
        """
        运行完整的采集流程
        
        Args:
            limit: 最大爬取产品数量
            fetch_details: 是否获取PDF链接
            
        Returns:
            统计信息字典
        """
        logger.info(f"🚀 开始采集 {self.company} 的产品数据...")
        logger.info(f"配置: limit={limit}, fetch_details={fetch_details}")
        
        # 步骤1: 爬取产品列表
        logger.info("=" * 80)
        logger.info("步骤 1/3: 爬取产品列表")
        logger.info("=" * 80)
        products_data = await self.spider.discover_products(
            limit=limit,
            fetch_details=fetch_details
        )
        self.stats["products_discovered"] = len(products_data)
        logger.info(f"✓ 发现 {len(products_data)} 个产品")
        
        if not products_data:
            logger.warning("未发现任何产品，流程终止")
            return self.stats
        
        # 步骤2: 保存产品元数据并下载PDF
        logger.info("=" * 80)
        logger.info("步骤 2/3: 保存产品元数据")
        logger.info("=" * 80)
        
        for idx, product_data in enumerate(products_data, 1):
            logger.info(f"\n[{idx}/{len(products_data)}] 处理产品: {product_data['name']} ({product_data['product_code']})")
            
            try:
                # 2.1 保存或更新产品信息
                product = await self._save_product(product_data)
                
                # 2.2 下载PDF文件
                if fetch_details and product_data.get('pdf_links'):
                    await self._download_pdfs(product, product_data['pdf_links'])
                
            except Exception as e:
                logger.error(f"❌ 处理产品失败: {product_data['name']}: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                continue
        
        # 步骤3: 输出统计信息
        logger.info("=" * 80)
        logger.info("步骤 3/3: 采集完成")
        logger.info("=" * 80)
        self._print_stats()
        
        return self.stats
    
    async def _save_product(self, product_data: Dict[str, Any]) -> Product:
        """
        保存或更新产品信息
        
        Args:
            product_data: 爬取到的产品数据
            
        Returns:
            Product实例
        """
        product_code = product_data['product_code']
        
        # 检查产品是否已存在
        existing_product = self.repo.get_product_by_code(product_code, self.company)
        
        if existing_product:
            logger.info(f"  ✓ 产品已存在: {existing_product.id}")
            self.stats["products_existing"] += 1
            return existing_product
        
        # 创建新产品
        product = Product(
            product_code=product_code,
            name=product_data['name'],
            company=self.company,
            publish_time=product_data.get('publish_time'),
            category=None  # 可以从产品名称推断
        )
        
        self.repo.add_product(product)
        logger.info(f"  ✓ 新产品已保存: {product.id}")
        self.stats["products_new"] += 1
        
        return product
    
    async def _download_pdfs(self, product: Product, pdf_links: Dict[str, str]):
        """
        下载产品的所有PDF文件
        
        Args:
            product: Product实例
            pdf_links: PDF链接字典 {文档类型: URL}
        """
        logger.info(f"  📄 下载PDF文件: {len(pdf_links)} 个文档")
        
        for doc_type, url in pdf_links.items():
            # Filter for supported document types only
            # This ensures we only save documents that match our DocumentType enum
            if doc_type not in ["产品条款", "产品说明书", "产品费率表"]:
                logger.debug(f"    ⊙ 跳过不支持的文档类型: {doc_type}")
                continue
                
            self.stats["pdfs_total"] += 1
            
            try:
                # 检查是否已下载过（根据URL去重）
                if self._is_document_exists(product.id, doc_type, url):
                    logger.info(f"    ⊙ 跳过 [{doc_type}]: 已存在")
                    self.stats["pdfs_skipped"] += 1
                    continue
                
                # 构建保存路径
                save_path = self._get_save_path(product, doc_type, url)
                
                # 下载PDF
                logger.info(f"    ↓ 下载 [{doc_type}]...")
                success = await self.downloader.download(url, save_path)
                
                if success:
                    # 计算文件哈希
                    file_hash = self._calculate_file_hash(save_path)
                    file_size = save_path.stat().st_size
                    
                    # 保存文档记录
                    doc = PolicyDocument(
                        product_id=product.id,
                        doc_type=doc_type,
                        filename=save_path.name,
                        local_path=str(save_path),
                        url=url,
                        file_hash=file_hash,
                        file_size=file_size,
                        downloaded_at=datetime.now(),
                        verification_status=VerificationStatus.PENDING,
                        pdf_links=pdf_links  # 保存所有PDF链接以实现可追溯性
                    )
                    
                    self.repo.add_document(doc)
                    logger.info(f"    ✓ 已保存 [{doc_type}]: {file_size / 1024:.1f} KB")
                    self.stats["pdfs_downloaded"] += 1
                else:
                    logger.warning(f"    ✗ 下载失败 [{doc_type}]")
                    self.stats["pdfs_failed"] += 1
                    
            except Exception as e:
                logger.error(f"    ✗ 处理文档失败 [{doc_type}]: {e}")
                self.stats["pdfs_failed"] += 1
    
    def _is_document_exists(self, product_id: str, doc_type: str, url: str) -> bool:
        """
        检查文档是否已存在
        
        Args:
            product_id: 产品ID
            doc_type: 文档类型
            url: 文档URL
            
        Returns:
            是否已存在
        """
        # 通过product_id + doc_type + url组合判断
        # 这里简化处理，实际可以查询数据库
        try:
            with self.repo.get_db_connection() as conn:
                cursor = conn.cursor()
                result = cursor.execute(
                    "SELECT id FROM policy_documents WHERE product_id = ? AND doc_type = ? AND url = ?",
                    (product_id, doc_type, url)
                ).fetchone()
                return result is not None
        except:
            return False
    
    def _get_save_path(self, product: Product, doc_type: str, url: str) -> Path:
        """
        生成PDF保存路径
        
        路径结构: data/raw/{company}/{product_code}/{doc_type}.pdf
        
        Args:
            product: Product实例
            doc_type: 文档类型
            url: 文档URL
            
        Returns:
            保存路径
        """
        # 确保目录存在
        company_dir = config.RAW_DATA_DIR / self._sanitize_filename(self.company)
        product_dir = company_dir / self._sanitize_filename(product.product_code)
        product_dir.mkdir(parents=True, exist_ok=True)
        
        # 文件名：文档类型.pdf
        filename = f"{self._sanitize_filename(doc_type)}.pdf"
        
        return product_dir / filename
    
    def _sanitize_filename(self, name: str) -> str:
        """
        清理文件名，移除非法字符
        
        Args:
            name: 原始名称
            
        Returns:
            清理后的名称
        """
        # 替换非法字符
        illegal_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in illegal_chars:
            name = name.replace(char, '_')
        return name.strip()
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """
        计算文件的SHA-256哈希值
        
        Args:
            file_path: 文件路径
            
        Returns:
            哈希值（十六进制字符串）
        """
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    def _print_stats(self):
        """打印统计信息"""
        logger.info("\n" + "=" * 80)
        logger.info("📊 采集统计")
        logger.info("=" * 80)
        logger.info(f"产品:")
        logger.info(f"  - 发现: {self.stats['products_discovered']} 个")
        logger.info(f"  - 新增: {self.stats['products_new']} 个")
        logger.info(f"  - 已存在: {self.stats['products_existing']} 个")
        logger.info(f"\nPDF文档:")
        logger.info(f"  - 总计: {self.stats['pdfs_total']} 个")
        logger.info(f"  - 已下载: {self.stats['pdfs_downloaded']} 个")
        logger.info(f"  - 已跳过: {self.stats['pdfs_skipped']} 个")
        logger.info(f"  - 失败: {self.stats['pdfs_failed']} 个")
        logger.info("=" * 80)
        
        if self.stats['pdfs_failed'] > 0:
            logger.warning(f"⚠️  有 {self.stats['pdfs_failed']} 个PDF下载失败，请检查日志")


# 便捷函数
async def run_acquisition(company: str = "平安人寿", limit: int = 100) -> Dict[str, Any]:
    """
    运行数据采集流程（便捷函数）
    
    Args:
        company: 保险公司名称
        limit: 最大爬取产品数量
        
    Returns:
        统计信息字典
    """
    pipeline = AcquisitionPipeline(company=company)
    stats = await pipeline.run(limit=limit, fetch_details=True)
    return stats


if __name__ == "__main__":
    # 测试运行
    async def test():
        # 初始化数据库
        from src.common.db import init_db
        init_db()
        
        # 运行采集（只采集5个产品用于测试）
        stats = await run_acquisition(company="平安人寿", limit=5)
        
        print("\n✅ 测试完成！")
        print(f"请检查: data/raw/平安人寿/ 目录下的PDF文件")
    
    asyncio.run(test())

