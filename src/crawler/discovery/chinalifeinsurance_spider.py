"""
中国人寿爬虫示例
展示如何为新的保险公司创建爬虫
"""
import asyncio
from typing import List, Dict, Any
from playwright.async_api import Page
from src.crawler.discovery.base_spider import BaseInsuranceSpider
from src.common.logging import logger


class ChinaLifeInsuranceSpider(BaseInsuranceSpider):
    """
    中国人寿保险公司爬虫
    
    目标网站: http://www.e-chinalife.com/... (示例URL，需要替换为实际URL)
    
    注意: 这是一个模板示例，实际实现需要根据中国人寿官网的真实结构调整
    """
    
    # 1. 定义公司基本信息
    BASE_URL = "http://www.e-chinalife.com/web/xxx/product_list.html"  # 替换为实际URL
    COMPANY_NAME = "中国人寿"
    
    async def wait_for_page_load(self, page: Page):
        """
        2. 实现页面加载等待逻辑
        
        根据中国人寿官网的实际结构，等待关键元素加载
        """
        try:
            # 示例：等待产品列表容器加载
            # 实际选择器需要根据网站HTML结构调整
            await page.wait_for_selector(".product-list", timeout=10000)
            logger.info(f"[{self.COMPANY_NAME}] Product list loaded")
        except Exception as e:
            logger.error(f"[{self.COMPANY_NAME}] Could not find product list: {e}")
            await page.screenshot(path="debug_chinalife_no_list.png", full_page=True)
            raise
    
    async def parse_product_list(self, 
                                  page: Page, 
                                  limit: int,
                                  fetch_details: bool) -> List[Dict[str, Any]]:
        """
        3. 实现产品列表解析逻辑
        
        根据中国人寿官网的实际HTML结构解析产品数据
        """
        results = []
        page_count = 0
        
        while len(results) < limit:
            page_count += 1
            logger.info(f"[{self.COMPANY_NAME}] Processing page {page_count}")
            
            await asyncio.sleep(2)
            
            # 示例：获取产品列表项
            # 实际选择器需要根据网站HTML结构调整
            try:
                # 假设产品列表是 <div class="product-item">
                items = await page.locator(".product-item").all()
            except:
                logger.warning(f"[{self.COMPANY_NAME}] No product items found")
                break
            
            if not items:
                logger.warning(f"[{self.COMPANY_NAME}] No results on page {page_count}")
                break
            
            logger.info(f"[{self.COMPANY_NAME}] Found {len(items)} items on page {page_count}")
            
            # 逐个解析产品
            for item in items:
                if len(results) >= limit:
                    break
                
                try:
                    # 示例：提取产品信息
                    # 实际选择器需要根据网站HTML结构调整
                    
                    # 假设结构是：
                    # <div class="product-item">
                    #   <span class="code">产品代码</span>
                    #   <h3 class="name">产品名称</h3>
                    #   <span class="date">发布时间</span>
                    #   <div class="downloads">
                    #     <a href="...">条款</a>
                    #     <a href="...">费率表</a>
                    #   </div>
                    # </div>
                    
                    product_code = await item.locator(".code").text_content()
                    product_code = product_code.strip() if product_code else ""
                    
                    product_name = await item.locator(".name").text_content()
                    product_name = product_name.strip() if product_name else ""
                    
                    publish_time = await item.locator(".date").text_content()
                    publish_time = publish_time.strip() if publish_time else ""
                    
                    # 跳过空数据
                    if not product_name:
                        continue
                    
                    # 提取PDF链接
                    pdf_links = {}
                    if fetch_details:
                        downloads_div = item.locator(".downloads").first
                        if await downloads_div.count() > 0:
                            pdf_links = await self.extract_pdf_links(downloads_div)
                    
                    # 构建标准化数据
                    source_url = pdf_links.get("产品条款", "") or pdf_links.get("条款", "")
                    if not source_url and pdf_links:
                        source_url = list(pdf_links.values())[0]
                    
                    item_data = self.normalize_product_data(
                        product_code=product_code,
                        name=product_name,
                        publish_time=publish_time,
                        source_url=source_url,
                        pdf_links=pdf_links
                    )
                    
                    results.append(item_data)
                    logger.info(f"[{self.COMPANY_NAME}] ✓ Extracted: {product_name} (Code: {product_code})")
                    
                except Exception as item_err:
                    logger.warning(f"[{self.COMPANY_NAME}] Failed to extract item: {item_err}")
                    continue
            
            if len(results) >= limit:
                break
            
            # 翻页
            if not await self.go_to_next_page(page):
                break
        
        return results
    
    async def extract_pdf_links(self, element) -> Dict[str, str]:
        """
        4. 实现PDF链接提取逻辑
        
        Args:
            element: 包含PDF链接的页面元素
            
        Returns:
            PDF链接字典 {文档类型: URL}
        """
        pdf_links = {}
        
        try:
            # 示例：提取所有 <a> 标签
            links = await element.locator("a").all()
            
            logger.debug(f"[{self.COMPANY_NAME}] Found {len(links)} PDF link elements")
            
            for link in links:
                try:
                    link_text = await link.text_content()
                    if link_text:
                        link_text = link_text.strip()
                    link_url = await link.get_attribute("href")
                    
                    # 处理相对URL
                    if link_url and not link_url.startswith("http"):
                        # 假设需要拼接基础URL
                        link_url = f"http://www.e-chinalife.com{link_url}"
                    
                    if link_url and link_text:
                        pdf_links[link_text] = link_url
                        logger.debug(f"  - {link_text}: {link_url[:60]}...")
                    
                except Exception as link_err:
                    logger.warning(f"Failed to extract link: {link_err}")
            
            logger.info(f"[{self.COMPANY_NAME}] ✓ Extracted {len(pdf_links)} PDFs")
        
        except Exception as e:
            logger.warning(f"[{self.COMPANY_NAME}] Failed to extract PDF links: {e}")
        
        return pdf_links
    
    async def go_to_next_page(self, page: Page) -> bool:
        """
        5. 实现翻页逻辑
        
        Args:
            page: Playwright页面对象
            
        Returns:
            是否成功翻页
        """
        try:
            # 示例：查找"下一页"按钮
            # 实际选择器需要根据网站分页结构调整
            next_btn = page.locator(".pagination .next:not(.disabled)").first
            
            if await next_btn.count() > 0:
                await next_btn.click()
                logger.info(f"[{self.COMPANY_NAME}] Clicked next page")
                await asyncio.sleep(2)
                return True
            else:
                logger.info(f"[{self.COMPANY_NAME}] No more pages")
                return False
        except Exception as e:
            logger.info(f"[{self.COMPANY_NAME}] Pagination ended: {e}")
            return False


if __name__ == "__main__":
    """
    使用说明:
    
    1. 将 BASE_URL 替换为中国人寿官网的实际产品列表页URL
    2. 使用浏览器开发者工具分析页面结构
    3. 更新各个方法中的CSS选择器
    4. 运行测试
    """
    print("⚠️  这是一个模板示例，需要根据中国人寿官网的实际结构调整")
    print("请按照以下步骤操作：")
    print("1. 访问中国人寿官网产品披露页面")
    print("2. 使用开发者工具(F12)分析HTML结构")
    print("3. 更新代码中的CSS选择器")
    print("4. 测试运行")
    
    # spider = ChinaLifeInsuranceSpider(headless=False)
    # products = asyncio.run(spider.discover_products(limit=5, fetch_details=True))
    # import json
    # print(json.dumps(products, ensure_ascii=False, indent=2))

