import asyncio
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
from playwright.async_api import async_playwright, Page, Browser

# 添加项目根目录到Python路径
# __file__ = .../src/crawler/discovery/pingan_life_spider.py
# 需要往上3层: discovery -> crawler -> src -> 项目根目录
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.common.logging import logger
from src.common.config import config

class PingAnLifeSpider:
    """
    Spider for Ping An Life Insurance official website.
    Target: https://life.pingan.com/gongkaixinxipilu/baoxianchanpinmulujitiaokuan.jsp
    
    This spider extracts product information from Ping An Life's public disclosure page.
    """
    
    BASE_URL = "https://life.pingan.com/gongkaixinxipilu/baoxianchanpinmulujitiaokuan.jsp"
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        
    async def discover_products(self, 
                                limit: int = 100,
                                fetch_details: bool = True) -> List[Dict[str, Any]]:
        """
        Discover products from Ping An Life website.
        
        Args:
            limit: Max number of products to discover.
            fetch_details: Whether to fetch detailed PDF links by expanding the dropdown menu.
            
        Returns:
            List of product metadata dictionaries with fields:
            - product_code: 产品代码
            - name: 产品名称
            - company: 保险公司名称 (固定为"平安人寿")
            - publish_time: 发布时间
            - source_url: 主要PDF下载链接 (产品条款)
            - pdf_links: 所有PDF链接的字典 {文档类型: URL}
            - filename: 建议的文件名
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
                logger.info(f"Navigating to {self.BASE_URL}")
                
                try:
                    await page.goto(self.BASE_URL, wait_until='domcontentloaded', timeout=60000)
                except Exception as nav_err:
                    logger.warning(f"Initial navigation issue: {nav_err}, retrying...")
                    await asyncio.sleep(2)
                    await page.goto(self.BASE_URL, wait_until='domcontentloaded', timeout=60000)
                
                # Wait for page to load
                await asyncio.sleep(3)
                
                logger.info("Waiting for product table to load...")
                
                # 1. Wait for product table to load
                try:
                    await page.wait_for_selector("table tbody tr", timeout=10000)
                    logger.info("Product table found")
                except Exception as e:
                    logger.error(f"Could not find product table: {e}")
                    await page.screenshot(path="debug_pingan_no_table.png", full_page=True)
                    return []
                
                # 2. Extract product information from table
                # Table columns: 产品代码, 产品名称, 产品报备材料, 发布时间, 历史版本, 现金价值
                
                page_count = 0
                while len(results) < limit:
                    page_count += 1
                    logger.info(f"Processing page {page_count}")
                    
                    await asyncio.sleep(2)
                    
                    try:
                        rows = await page.locator("table tbody tr").all()
                    except:
                        logger.warning("No table rows found")
                        break
                    
                    if not rows:
                        logger.warning("No result rows found on this page")
                        break
                    
                    logger.info(f"Found {len(rows)} rows on page {page_count}")
                    
                    for row_idx, row in enumerate(rows):
                        if len(results) >= limit:
                            break
                            
                        try:
                            tds = await row.locator("td").all()
                            if len(tds) < 6:  # Expected: 6 columns including 现金价值
                                logger.debug(f"Skipping row with only {len(tds)} columns")
                                continue
                            
                            # Extract basic data
                            product_code = (await tds[0].inner_text()).strip()
                            product_name = (await tds[1].inner_text()).strip()
                            publish_time = (await tds[3].inner_text()).strip()
                            
                            # Skip empty or header rows
                            if not product_name or product_name == "产品名称":
                                continue
                            
                            # Extract PDF links from the dropdown menu
                            # Note: The links are already in HTML (just CSS hidden), so we can extract directly
                            pdf_links = {}
                            if fetch_details:
                                try:
                                    # Find the dropdown cell (class="dropdown")
                                    dropdown_cell = tds[2]
                                    
                                    # The structure is: <td class="dropdown"><a>请选择</a><ul><a>...</a>...</ul></td>
                                    # All links are in the <ul>, we just need to extract them
                                    
                                    # Find the <ul> element (it exists in DOM even if CSS hidden)
                                    ul_element = dropdown_cell.locator("ul").first
                                    
                                    if await ul_element.count() > 0:
                                        # Get all <a> tags inside <ul>
                                        # These are the PDF links (not the trigger button)
                                        links = await ul_element.locator("a").all()
                                        
                                        logger.debug(f"Found {len(links)} link elements for {product_name}")
                                        
                                        for idx, link in enumerate(links):
                                            try:
                                                # Get link text and URL
                                                link_text = await link.text_content()
                                                if link_text:
                                                    link_text = link_text.strip()
                                                link_url = await link.get_attribute("href")
                                                
                                                logger.debug(f"  Link {idx+1}: '{link_text}' -> {link_url[:60] if link_url else 'None'}...")
                                                
                                                if link_url and link_text:
                                                    pdf_links[link_text] = link_url
                                                elif not link_url:
                                                    logger.warning(f"  Link {idx+1} '{link_text}' has no href attribute")
                                            except Exception as link_err:
                                                logger.warning(f"Failed to extract link {idx}: {link_err}")
                                        
                                        logger.info(f"✓ Successfully extracted {len(pdf_links)} PDF links for {product_name}: {list(pdf_links.keys())}")
                                    else:
                                        logger.warning(f"No <ul> element found in dropdown for {product_name}")
                                        
                                except Exception as dropdown_err:
                                    logger.warning(f"Failed to extract PDF links for {product_name}: {dropdown_err}")
                                    import traceback
                                    logger.debug(traceback.format_exc())
                            
                            # Use the first PDF link (产品条款) as the primary source_url
                            source_url = pdf_links.get("产品条款", "")
                            if not source_url and pdf_links:
                                # Fallback to any available PDF
                                source_url = list(pdf_links.values())[0]
                            
                            item = {
                                "product_code": product_code,
                                "name": product_name,
                                "company": "平安人寿",
                                "publish_time": publish_time,
                                "source_url": source_url,
                                "pdf_links": pdf_links,  # Store all PDF links
                                "filename": f"{product_code}_{product_name}.pdf" if product_code else f"{product_name}.pdf"
                            }
                            
                            results.append(item)
                            logger.info(f"✓ Extracted: {product_name} (Code: {product_code})")
                                
                        except Exception as row_err:
                            logger.warning(f"Failed to extract row data: {row_err}")
                            continue
                    
                    if len(results) >= limit:
                        break
                    
                    # 3. Handle pagination
                    try:
                        # Look for next page button in the pagination
                        next_btn = page.locator("a:has-text('下一页')").first
                        
                        # Check if next button exists and is not disabled
                        if await next_btn.count() > 0:
                            # Check if parent listitem has cursor pointer (indicates it's clickable)
                            parent = page.locator("listitem:has(a:has-text('下一页'))")
                            if await parent.count() > 0:
                                await next_btn.click()
                                logger.info("Clicked next page button")
                                await asyncio.sleep(2)
                            else:
                                logger.info("No more pages available (next button disabled)")
                                break
                        else:
                            logger.info("No more pages available")
                            break
                    except Exception as page_err:
                        logger.info(f"Pagination ended: {page_err}")
                        break

                logger.info(f"✅ Discovered {len(results)} products in total")
                
            except Exception as e:
                logger.error(f"Error during discovery: {e}")
                import traceback
                logger.error(traceback.format_exc())
                try:
                    await page.screenshot(path="debug_pingan_error.png", full_page=True)
                    logger.info("Saved error screenshot to debug_pingan_error.png")
                except Exception as ss_err:
                    logger.warning(f"Could not save screenshot: {ss_err}")
            finally:
                await browser.close()
                
        return results[:limit]
    

if __name__ == "__main__":
    # Test run
    spider = PingAnLifeSpider(headless=False)
    products = asyncio.run(spider.discover_products(
        limit=10,
        fetch_details=True
    ))
    import json
    print(json.dumps(products, ensure_ascii=False, indent=2))

