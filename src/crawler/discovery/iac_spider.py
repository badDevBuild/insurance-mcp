import asyncio
from typing import List, Optional, Dict, Any
from playwright.async_api import async_playwright, Page, Browser, Frame
from src.common.logging import logger
from src.common.config import config

class IACSpider:
    """
    Spider for Insurance Association of China (IAC) product library.
    Target: https://www.iachina.cn/art/2017/6/29/art_71_45682.html (Contains iframe to query system)
    Actual System URL (inside iframe): https://tiaokuan.iachina.cn/
    
    Form Structure: Element UI based form with el-input and el-select components
    """
    
    BASE_URL = "https://www.iachina.cn/art/2017/6/29/art_71_45682.html"
    
    # 产品类别选项
    CATEGORIES = ["人寿保险", "年金保险", "健康保险", "意外伤害保险", "委托管理业务"]
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        
    async def discover_products(self, 
                                company_filter: Optional[str] = None, 
                                category: Optional[str] = None,
                                limit: int = 100,
                                fetch_details: bool = True) -> List[Dict[str, Any]]:
        """
        Discover products from IAC.
        
        Args:
            company_filter: Optional company name to filter by (e.g., "平安人寿").
            category: Optional product category (e.g., "人寿保险", "年金保险").
            limit: Max number of products to discover.
            fetch_details: Whether to fetch detailed information by clicking "详细信息".
            
        Returns:
            List of product metadata dictionaries.
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
                    await page.goto(self.BASE_URL, wait_until='domcontentloaded', timeout=90000)
                except Exception as nav_err:
                    logger.warning(f"Initial navigation issue: {nav_err}, retrying...")
                    await asyncio.sleep(2)
                    await page.goto(self.BASE_URL, wait_until='domcontentloaded', timeout=90000)
                
                await asyncio.sleep(3)
                
                # 1. Locate and switch to iframe
                logger.info("Waiting for iframe to load...")
                try:
                    frame_element = await page.wait_for_selector(
                        "iframe[src*='tiaokuan.iachina.cn']", 
                        timeout=30000,
                        state='attached'
                    )
                except Exception as iframe_err:
                    logger.error(f"Could not find iframe: {iframe_err}")
                    await page.screenshot(path="debug_no_iframe.png", full_page=True)
                    return []
                
                if not frame_element:
                    logger.error("Could not find the product query iframe.")
                    return []
                
                frame = await frame_element.content_frame()
                if not frame:
                    logger.error("Could not access iframe content.")
                    return []

                logger.info("Switched to query iframe context")
                
                try:
                    await frame.wait_for_load_state("domcontentloaded", timeout=30000)
                except:
                    logger.warning("Iframe load state timeout, continuing anyway...")
                
                await asyncio.sleep(3)

                # 2. Fill Search Form
                logger.info("Attempting to fill search form...")
                
                if company_filter:
                    logger.info(f"Filling company name: {company_filter}")
                    try:
                        await frame.wait_for_selector("input.el-input__inner", timeout=10000)
                        
                        company_inputs = await frame.locator("input.el-input__inner[type='text']:not([readonly])").all()
                        logger.info(f"Found {len(company_inputs)} text input fields")
                        
                        if len(company_inputs) >= 2:
                            await company_inputs[1].fill(company_filter)
                            logger.info(f"Filled company filter: {company_filter}")
                        else:
                            logger.warning(f"Expected at least 2 input fields, found {len(company_inputs)}")
                    except Exception as input_err:
                        logger.error(f"Failed to fill company input: {input_err}")
                
                # 3. Select Product Category
                if category and category in self.CATEGORIES:
                    logger.info(f"Selecting product category: {category}")
                    try:
                        all_selects = await frame.locator(".el-select").all()
                        logger.info(f"Found {len(all_selects)} total select dropdowns")
                        
                        category_selected = False
                        
                        for idx in range(len(all_selects) - 1, max(len(all_selects) - 4, -1), -1):
                            if category_selected:
                                break
                                
                            try:
                                logger.info(f"Trying select dropdown at index {idx}")
                                select = all_selects[idx]
                                
                                await select.click(timeout=3000)
                                await asyncio.sleep(0.8)
                                
                                dropdown_visible = await frame.locator("ul.el-select-dropdown__list:visible").count()
                                
                                if dropdown_visible > 0:
                                    visible_options = await frame.locator("li.el-select-dropdown__item:visible span").all()
                                    option_texts = [await opt.inner_text() for opt in visible_options]
                                    logger.info(f"Dropdown {idx} options: {option_texts}")
                                    
                                    if category in option_texts or "人寿保险" in option_texts:
                                        logger.info(f"✓ Found category dropdown at index {idx}")
                                        
                                        option = frame.locator(f"li.el-select-dropdown__item:visible span:text-is('{category}')").first
                                        if await option.count() > 0:
                                            await option.click()
                                            logger.info(f"✓ Selected category: {category}")
                                            category_selected = True
                                            await asyncio.sleep(0.5)
                                        else:
                                            logger.warning(f"Option '{category}' not found in dropdown")
                                            await page.keyboard.press("Escape")
                                    else:
                                        logger.debug(f"Dropdown {idx} is not the category dropdown, closing...")
                                        await page.keyboard.press("Escape")
                                        await asyncio.sleep(0.3)
                                else:
                                    logger.debug(f"Dropdown {idx} did not open")
                                    
                            except Exception as select_err:
                                logger.debug(f"Select {idx} failed: {select_err}")
                                continue
                        
                        if not category_selected:
                            logger.warning("Could not select category, continuing without it")
                        
                    except Exception as cat_err:
                        logger.warning(f"Failed to select category: {cat_err}")
                        try:
                            await page.keyboard.press("Escape")
                        except:
                            pass

                # 4. Click Search/Query Button
                await asyncio.sleep(1)
                
                try:
                    try:
                        await page.keyboard.press("Escape")
                        await asyncio.sleep(0.5)
                    except:
                        pass
                    
                    search_button = frame.locator("button:has-text('查询')").first
                    if await search_button.count() > 0:
                        await search_button.click(force=True)
                        logger.info("Clicked search button")
                        await asyncio.sleep(3)
                    else:
                        logger.warning("Search button not found")
                except Exception as btn_err:
                    logger.warning(f"Failed to click search button: {btn_err}")

                # 5. Extract Results Table
                page_count = 0
                while len(results) < limit:
                    page_count += 1
                    logger.info(f"Processing page {page_count}")
                    
                    await asyncio.sleep(2)
                    
                    try:
                        await frame.wait_for_selector("table tbody tr", timeout=10000)
                    except:
                        logger.warning("No table found or timeout")
                        break
                    
                    rows = await frame.locator("table tbody tr").all()
                    
                    if not rows:
                        logger.warning("No result rows found on this page")
                        break
                    
                    logger.info(f"Found {len(rows)} rows on page {page_count}")
                    
                    for row_idx, row in enumerate(rows):
                        if len(results) >= limit:
                            break
                            
                        try:
                            tds = await row.locator("td").all()
                            if len(tds) < 5:
                                logger.debug(f"Skipping row with only {len(tds)} columns")
                                continue
                            
                            # Extract basic data
                            seq_num = (await tds[0].inner_text()).strip()
                            company_name = (await tds[1].inner_text()).strip()
                            product_name = (await tds[2].inner_text()).strip()
                            sale_time = (await tds[3].inner_text()).strip()
                            sale_status = (await tds[4].inner_text()).strip()
                            
                            # Skip empty or header rows
                            if not product_name or product_name == "产品名称":
                                continue
                            
                            item = {
                                "name": product_name,
                                "company": company_name,
                                "category": category or "Unknown",
                                "sale_time": sale_time,
                                "status": sale_status,
                                "source_url": "",  # Will be filled from detail page
                                "filename": f"{product_name}.pdf"
                            }
                            
                            # 6. Fetch Details if requested
                            if fetch_details and len(tds) > 5:
                                try:
                                    logger.info(f"Fetching details for: {product_name}")
                                    
                                    # Find and click "详细信息" button
                                    detail_button = tds[5].locator("button:has-text('详细信息')").first
                                    
                                    if await detail_button.count() > 0:
                                        await detail_button.click()
                                        logger.info("Clicked '详细信息' button")
                                        await asyncio.sleep(2)
                                        
                                        # Extract detail page information
                                        detail_info = await self._extract_detail_info(frame)
                                        
                                        # Merge detail info into item
                                        item.update(detail_info)
                                        
                                        # Go back to list
                                        back_button = frame.locator("button:has-text('返回')").first
                                        if await back_button.count() > 0:
                                            await back_button.click()
                                            logger.info("Clicked '返回' button")
                                            await asyncio.sleep(1)
                                        else:
                                            logger.warning("'返回' button not found, using browser back")
                                            await page.go_back()
                                            await asyncio.sleep(2)
                                    else:
                                        logger.warning(f"'详细信息' button not found for {product_name}")
                                        
                                except Exception as detail_err:
                                    logger.warning(f"Failed to fetch details for {product_name}: {detail_err}")
                            
                            results.append(item)
                            logger.info(f"✓ Extracted: {product_name} ({company_name})")
                                
                        except Exception as row_err:
                            logger.warning(f"Failed to extract row data: {row_err}")
                            continue
                    
                    if len(results) >= limit:
                        break
                    
                    # 7. Pagination
                    try:
                        next_btn = frame.locator(".el-pagination button.btn-next:not([disabled])")
                        if await next_btn.count() == 0:
                            next_btn = frame.locator("button:has-text('下一页'):not([disabled])")
                        
                        if await next_btn.count() > 0:
                            await next_btn.click()
                            logger.info("Clicked next page button")
                            await asyncio.sleep(2)
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
                    await page.screenshot(path="debug_iac_error.png", full_page=True)
                    logger.info("Saved error screenshot to debug_iac_error.png")
                except Exception as ss_err:
                    logger.warning(f"Could not save screenshot: {ss_err}")
            finally:
                await browser.close()
                
        return results[:limit]
    
    async def _extract_detail_info(self, frame: Frame) -> Dict[str, Any]:
        """
        Extract information from the detail page.
        
        Args:
            frame: The iframe containing the detail page
            
        Returns:
            Dictionary with detail information
        """
        detail_info = {}
        
        try:
            # Wait for detail page to load
            await asyncio.sleep(1)
            
            # NOTE: IAC爬虫已暂缓，优先使用平安人寿官网爬虫
            # 详情页提取功能待后续有实际需求时再完善
            # 可提取字段: PDF链接、产品代码、登记日期等
            
            # Try to find PDF download link
            # Look for links ending with .pdf
            pdf_links = await frame.locator("a[href$='.pdf']").all()
            if pdf_links:
                pdf_url = await pdf_links[0].get_attribute("href")
                detail_info["source_url"] = pdf_url
                logger.info(f"Found PDF link: {pdf_url}")
            
            # Example: Extract from description table if exists
            # detail_rows = await frame.locator(".el-descriptions-item").all()
            # for row in detail_rows:
            #     label = await row.locator(".el-descriptions-item__label").inner_text()
            #     content = await row.locator(".el-descriptions-item__content").inner_text()
            #     detail_info[label] = content
            
        except Exception as e:
            logger.warning(f"Error extracting detail info: {e}")
        
        return detail_info

if __name__ == "__main__":
    # Test run
    spider = IACSpider(headless=False)
    products = asyncio.run(spider.discover_products(
        company_filter="平安人寿", 
        category="人寿保险",
        limit=2,  # Test with just 2 products
        fetch_details=True
    ))
    import json
    print(json.dumps(products, ensure_ascii=False, indent=2))
