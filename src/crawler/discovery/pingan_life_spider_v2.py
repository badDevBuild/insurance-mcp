"""
平安人寿爬虫 (重构版 - 继承BaseInsuranceSpider)
"""
import asyncio
from typing import List, Dict, Any
from playwright.async_api import Page
from src.crawler.discovery.base_spider import BaseInsuranceSpider
from src.common.logging import logger


class PingAnLifeSpiderV2(BaseInsuranceSpider):
    """
    平安人寿保险公司爬虫
    
    目标网站: https://life.pingan.com/gongkaixinxipilu/baoxianchanpinmulujitiaokuan.jsp
    """
    
    BASE_URL = "https://life.pingan.com/gongkaixinxipilu/baoxianchanpinmulujitiaokuan.jsp"
    COMPANY_NAME = "平安人寿"
    
    async def wait_for_page_load(self, page: Page):
        """等待产品表格加载"""
        try:
            await page.wait_for_selector("table tbody tr", timeout=10000)
            logger.info(f"[{self.COMPANY_NAME}] Product table loaded")
        except Exception as e:
            logger.error(f"[{self.COMPANY_NAME}] Could not find product table: {e}")
            await page.screenshot(path="debug_pingan_no_table.png", full_page=True)
            raise
    
    async def parse_product_list(self, 
                                  page: Page, 
                                  limit: int,
                                  fetch_details: bool) -> List[Dict[str, Any]]:
        """
        解析平安人寿产品列表
        
        表格结构: 产品代码 | 产品名称 | 产品报备材料 | 发布时间 | 历史版本 | 现金价值
        """
        results = []
        page_count = 0
        
        while len(results) < limit:
            page_count += 1
            logger.info(f"[{self.COMPANY_NAME}] Processing page {page_count}")
            
            await asyncio.sleep(2)
            
            # 获取所有行
            try:
                rows = await page.locator("table tbody tr").all()
            except:
                logger.warning(f"[{self.COMPANY_NAME}] No table rows found")
                break
            
            if not rows:
                logger.warning(f"[{self.COMPANY_NAME}] No result rows on page {page_count}")
                break
            
            logger.info(f"[{self.COMPANY_NAME}] Found {len(rows)} rows on page {page_count}")
            
            # 逐行解析
            for row in rows:
                if len(results) >= limit:
                    break
                
                try:
                    tds = await row.locator("td").all()
                    if len(tds) < 6:
                        continue
                    
                    # 提取基本字段
                    product_code = (await tds[0].inner_text()).strip()
                    product_name = (await tds[1].inner_text()).strip()
                    publish_time = (await tds[3].inner_text()).strip()
                    
                    # 跳过表头
                    if not product_name or product_name == "产品名称":
                        continue
                    
                    # 提取PDF链接
                    pdf_links = {}
                    if fetch_details:
                        pdf_links = await self.extract_pdf_links(tds[2])
                    
                    # 构建标准化数据
                    source_url = pdf_links.get("产品条款", "")
                    if not source_url and pdf_links:
                        source_url = list(pdf_links.values())[0]
                    
                    item = self.normalize_product_data(
                        product_code=product_code,
                        name=product_name,
                        publish_time=publish_time,
                        source_url=source_url,
                        pdf_links=pdf_links
                    )
                    
                    results.append(item)
                    logger.info(f"[{self.COMPANY_NAME}] ✓ Extracted: {product_name} (Code: {product_code})")
                    
                except Exception as row_err:
                    logger.warning(f"[{self.COMPANY_NAME}] Failed to extract row: {row_err}")
                    continue
            
            if len(results) >= limit:
                break
            
            # 翻页
            if not await self.go_to_next_page(page):
                break
        
        return results
    
    async def extract_pdf_links(self, dropdown_cell) -> Dict[str, str]:
        """
        从下拉菜单单元格中提取PDF链接
        
        Args:
            dropdown_cell: <td class="dropdown"> 元素
            
        Returns:
            PDF链接字典 {文档类型: URL}
        """
        pdf_links = {}
        
        try:
            # 定位隐藏的 <ul> 元素
            ul_element = dropdown_cell.locator("ul").first
            
            if await ul_element.count() > 0:
                # 提取所有 <a> 标签
                links = await ul_element.locator("a").all()
                
                logger.debug(f"[{self.COMPANY_NAME}] Found {len(links)} PDF link elements")
                
                for idx, link in enumerate(links):
                    try:
                        link_text = await link.text_content()
                        if link_text:
                            link_text = link_text.strip()
                        link_url = await link.get_attribute("href")
                        
                        if link_url and link_text:
                            pdf_links[link_text] = link_url
                            logger.debug(f"  - {link_text}: {link_url[:60]}...")
                        elif not link_url:
                            logger.warning(f"  Link '{link_text}' has no href")
                    except Exception as link_err:
                        logger.warning(f"Failed to extract link {idx}: {link_err}")
                
                logger.info(f"[{self.COMPANY_NAME}] ✓ Extracted {len(pdf_links)} PDFs: {list(pdf_links.keys())}")
            else:
                logger.warning(f"[{self.COMPANY_NAME}] No <ul> element found in dropdown")
        
        except Exception as e:
            logger.warning(f"[{self.COMPANY_NAME}] Failed to extract PDF links: {e}")
        
        return pdf_links
    
    async def go_to_next_page(self, page: Page) -> bool:
        """
        翻到下一页
        
        Args:
            page: Playwright页面对象
            
        Returns:
            是否成功翻页
        """
        try:
            next_btn = page.locator("a:has-text('下一页')").first
            
            if await next_btn.count() > 0:
                # 检查按钮是否可点击
                parent = page.locator("li.next")
                if await parent.count() > 0:
                    await next_btn.click()
                    logger.info(f"[{self.COMPANY_NAME}] Clicked next page")
                    await asyncio.sleep(2)
                    return True
                else:
                    logger.info(f"[{self.COMPANY_NAME}] No more pages (button disabled)")
                    return False
            else:
                logger.info(f"[{self.COMPANY_NAME}] No next page button found")
                return False
        except Exception as e:
            logger.info(f"[{self.COMPANY_NAME}] Pagination ended: {e}")
            return False


if __name__ == "__main__":
    # 测试
    spider = PingAnLifeSpiderV2(headless=False)
    products = asyncio.run(spider.discover_products(limit=5, fetch_details=True))
    
    import json
    print(json.dumps(products, ensure_ascii=False, indent=2))

