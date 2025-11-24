"""
保险公司爬虫基类
定义了通用的爬虫接口和流程框架
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright, Page, Browser
from src.common.logging import logger
from src.common.config import config
import asyncio


class BaseInsuranceSpider(ABC):
    """
    保险公司爬虫基类
    
    子类需要实现:
    - BASE_URL: 目标网站URL
    - COMPANY_NAME: 保险公司名称
    - parse_product_list(): 解析产品列表
    - extract_pdf_links(): 提取PDF链接
    """
    
    BASE_URL: str = ""
    COMPANY_NAME: str = ""
    
    def __init__(self, headless: bool = True):
        """
        初始化爬虫
        
        Args:
            headless: 是否无头模式运行浏览器
        """
        self.headless = headless
        if not self.BASE_URL:
            raise ValueError(f"{self.__class__.__name__} must define BASE_URL")
        if not self.COMPANY_NAME:
            raise ValueError(f"{self.__class__.__name__} must define COMPANY_NAME")
    
    async def discover_products(self, 
                                limit: int = 100,
                                fetch_details: bool = True) -> List[Dict[str, Any]]:
        """
        发现产品（通用流程）
        
        Args:
            limit: 最大爬取数量
            fetch_details: 是否获取详细信息（PDF链接）
            
        Returns:
            产品列表
        """
        results = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent=config.USER_AGENT,
                viewport={'width': 1920, 'height': 1080}
            )
            page = await context.new_page()
            
            try:
                logger.info(f"[{self.COMPANY_NAME}] Navigating to {self.BASE_URL}")
                
                # 导航到目标页面
                await self.navigate_to_page(page)
                
                # 等待页面加载
                await self.wait_for_page_load(page)
                
                # 解析产品列表（子类实现）
                results = await self.parse_product_list(page, limit, fetch_details)
                
                logger.info(f"[{self.COMPANY_NAME}] ✅ Discovered {len(results)} products")
                
            except Exception as e:
                logger.error(f"[{self.COMPANY_NAME}] Error during discovery: {e}")
                import traceback
                logger.error(traceback.format_exc())
                
                try:
                    screenshot_path = f"debug_{self.COMPANY_NAME.lower()}_error.png"
                    await page.screenshot(path=screenshot_path, full_page=True)
                    logger.info(f"Saved error screenshot to {screenshot_path}")
                except Exception as ss_err:
                    logger.warning(f"Could not save screenshot: {ss_err}")
            finally:
                await browser.close()
        
        return results[:limit]
    
    async def navigate_to_page(self, page: Page):
        """
        导航到目标页面（可被子类覆盖）
        
        Args:
            page: Playwright页面对象
        """
        try:
            await page.goto(self.BASE_URL, wait_until='domcontentloaded', timeout=60000)
        except Exception as nav_err:
            logger.warning(f"Initial navigation issue: {nav_err}, retrying...")
            await asyncio.sleep(2)
            await page.goto(self.BASE_URL, wait_until='domcontentloaded', timeout=60000)
        
        await asyncio.sleep(3)  # 等待JavaScript执行
    
    @abstractmethod
    async def wait_for_page_load(self, page: Page):
        """
        等待页面关键元素加载（子类必须实现）
        
        Args:
            page: Playwright页面对象
        """
        pass
    
    @abstractmethod
    async def parse_product_list(self, 
                                  page: Page, 
                                  limit: int,
                                  fetch_details: bool) -> List[Dict[str, Any]]:
        """
        解析产品列表（子类必须实现）
        
        Args:
            page: Playwright页面对象
            limit: 最大爬取数量
            fetch_details: 是否获取详细信息
            
        Returns:
            产品列表，每个产品包含:
            - product_code: 产品代码
            - name: 产品名称
            - company: 保险公司名称
            - publish_time: 发布时间
            - source_url: 主PDF链接
            - pdf_links: 所有PDF链接字典
            - filename: 建议的文件名
        """
        pass
    
    @abstractmethod
    async def extract_pdf_links(self, element) -> Dict[str, str]:
        """
        从页面元素中提取PDF链接（子类必须实现）
        
        Args:
            element: 页面元素（具体类型由子类定义）
            
        Returns:
            PDF链接字典 {文档类型: URL}
        """
        pass
    
    def normalize_product_data(self, **kwargs) -> Dict[str, Any]:
        """
        标准化产品数据格式（辅助方法）
        
        Args:
            **kwargs: 产品字段
            
        Returns:
            标准化的产品数据字典
        """
        product_code = kwargs.get('product_code', '')
        product_name = kwargs.get('name', '')
        
        return {
            "product_code": product_code,
            "name": product_name,
            "company": self.COMPANY_NAME,
            "publish_time": kwargs.get('publish_time', ''),
            "source_url": kwargs.get('source_url', ''),
            "pdf_links": kwargs.get('pdf_links', {}),
            "filename": f"{product_code}_{product_name}.pdf" if product_code else f"{product_name}.pdf",
            # 可以添加额外字段
            "category": kwargs.get('category', ''),
            "status": kwargs.get('status', ''),
        }

