# 如何添加新的保险公司爬虫

本指南详细说明如何为新的保险公司创建爬虫，以扩展系统的覆盖范围。

## 📋 目录

1. [架构概览](#架构概览)
2. [快速开始](#快速开始)
3. [详细步骤](#详细步骤)
4. [常见问题](#常见问题)
5. [最佳实践](#最佳实践)

---

## 架构概览

### 核心组件

```
src/crawler/discovery/
├── base_spider.py              # 基类（所有爬虫继承）
├── pingan_life_spider.py       # 平安人寿爬虫（参考实现）
├── chinalifeinsurance_spider.py # 中国人寿爬虫（模板示例）
├── spider_factory.py           # 爬虫工厂（统一管理）
└── [新公司]_spider.py          # 新增的爬虫文件
```

### 继承关系

```
BaseInsuranceSpider (抽象基类)
    ├── PingAnLifeSpider
    ├── ChinaLifeInsuranceSpider
    └── [您的新爬虫]Spider
```

---

## 快速开始

### 步骤1: 创建爬虫文件

```bash
cd /Users/shushu/insurance-mcp/src/crawler/discovery/
cp chinalifeinsurance_spider.py [新公司]_spider.py
```

### 步骤2: 修改基本信息

打开 `[新公司]_spider.py`，修改以下内容：

```python
class NewCompanySpider(BaseInsuranceSpider):
    """新公司爬虫"""
    
    # 1. 设置公司基本信息
    BASE_URL = "https://新公司官网产品列表URL"
    COMPANY_NAME = "新公司名称"
```

### 步骤3: 分析目标网站

1. 访问目标网站
2. 按 `F12` 打开浏览器开发者工具
3. 分析HTML结构，记录关键元素的CSS选择器

### 步骤4: 实现必需方法

根据网站结构实现以下方法：

- `wait_for_page_load()` - 等待页面加载
- `parse_product_list()` - 解析产品列表
- `extract_pdf_links()` - 提取PDF链接
- `go_to_next_page()` (可选) - 翻页逻辑

### 步骤5: 注册爬虫

在 `spider_factory.py` 中注册新爬虫：

```python
from src.crawler.discovery.[新公司]_spider import NewCompanySpider

SpiderFactory.register("new-company", NewCompanySpider)
```

### 步骤6: 测试运行

```bash
python src/crawler/discovery/[新公司]_spider.py
```

---

## 详细步骤

### 1. 分析目标网站结构

#### 1.1 找到产品列表页面

访问保险公司官网，找到"公开信息披露" > "产品信息"等相关页面。

**关键URL模式：**
- `/gongkaixinxipilu/` (公开信息披露)
- `/product/` (产品)
- `/disclosure/` (披露)

#### 1.2 分析HTML结构

使用开发者工具查看页面结构，记录以下信息：

| 信息 | CSS选择器示例 | 说明 |
|------|---------------|------|
| 产品列表容器 | `table tbody tr` 或 `.product-list` | 包含所有产品的容器 |
| 产品代码 | `td:nth-child(1)` 或 `.product-code` | 产品唯一标识 |
| 产品名称 | `td:nth-child(2)` 或 `.product-name` | 产品全称 |
| 发布时间 | `td:nth-child(4)` 或 `.publish-date` | 发布/更新时间 |
| PDF链接 | `a[href$='.pdf']` 或 `.download-link` | 下载链接 |
| 下一页按钮 | `.pagination .next` 或 `a:has-text('下一页')` | 翻页按钮 |

**提示：** 使用Playwright的选择器工具快速定位元素

```bash
playwright codegen https://目标网站URL
```

#### 1.3 识别数据结构模式

常见的产品列表结构：

**模式1: 表格结构**
```html
<table>
  <tbody>
    <tr>
      <td>产品代码</td>
      <td>产品名称</td>
      <td><a href="...">条款下载</a></td>
      <td>发布时间</td>
    </tr>
  </tbody>
</table>
```

**模式2: 卡片结构**
```html
<div class="product-list">
  <div class="product-item">
    <h3 class="name">产品名称</h3>
    <span class="code">产品代码</span>
    <div class="downloads">
      <a href="...">条款</a>
      <a href="...">费率表</a>
    </div>
  </div>
</div>
```

---

### 2. 实现爬虫类

#### 2.1 创建类骨架

```python
from src.crawler.discovery.base_spider import BaseInsuranceSpider
from playwright.async_api import Page
from typing import List, Dict, Any
import asyncio

class NewCompanySpider(BaseInsuranceSpider):
    """
    [新公司名称]爬虫
    
    目标网站: [URL]
    """
    
    BASE_URL = "https://..."
    COMPANY_NAME = "[新公司名称]"
```

#### 2.2 实现 `wait_for_page_load()`

等待关键元素加载完成：

```python
async def wait_for_page_load(self, page: Page):
    """等待页面关键元素加载"""
    try:
        # 等待产品列表容器
        await page.wait_for_selector("[您的选择器]", timeout=10000)
        logger.info(f"[{self.COMPANY_NAME}] Page loaded")
    except Exception as e:
        logger.error(f"[{self.COMPANY_NAME}] Load failed: {e}")
        await page.screenshot(path=f"debug_{self.COMPANY_NAME}_error.png")
        raise
```

#### 2.3 实现 `parse_product_list()`

解析产品列表的核心逻辑：

```python
async def parse_product_list(self, page: Page, limit: int, fetch_details: bool) -> List[Dict[str, Any]]:
    """解析产品列表"""
    results = []
    page_count = 0
    
    while len(results) < limit:
        page_count += 1
        await asyncio.sleep(2)
        
        # 1. 获取产品元素列表
        items = await page.locator("[您的选择器]").all()
        
        if not items:
            break
        
        # 2. 逐个解析产品
        for item in items:
            if len(results) >= limit:
                break
            
            try:
                # 提取字段
                product_code = await item.locator("[代码选择器]").text_content()
                product_name = await item.locator("[名称选择器]").text_content()
                publish_time = await item.locator("[时间选择器]").text_content()
                
                # 清理数据
                product_code = product_code.strip() if product_code else ""
                product_name = product_name.strip() if product_name else ""
                
                if not product_name:
                    continue
                
                # 提取PDF链接
                pdf_links = {}
                if fetch_details:
                    pdf_element = item.locator("[PDF容器选择器]")
                    pdf_links = await self.extract_pdf_links(pdf_element)
                
                # 构建标准化数据
                source_url = pdf_links.get("产品条款", "")
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
                logger.info(f"[{self.COMPANY_NAME}] ✓ {product_name}")
                
            except Exception as e:
                logger.warning(f"[{self.COMPANY_NAME}] Parse error: {e}")
                continue
        
        # 3. 翻页
        if len(results) >= limit:
            break
        if not await self.go_to_next_page(page):
            break
    
    return results
```

#### 2.4 实现 `extract_pdf_links()`

提取PDF下载链接：

```python
async def extract_pdf_links(self, element) -> Dict[str, str]:
    """提取PDF链接"""
    pdf_links = {}
    
    try:
        # 获取所有链接
        links = await element.locator("a").all()
        
        for link in links:
            link_text = await link.text_content()
            link_url = await link.get_attribute("href")
            
            # 处理相对URL
            if link_url and not link_url.startswith("http"):
                link_url = f"{self.BASE_URL的域名部分}{link_url}"
            
            if link_url and link_text:
                pdf_links[link_text.strip()] = link_url
        
        logger.info(f"[{self.COMPANY_NAME}] ✓ {len(pdf_links)} PDFs")
    
    except Exception as e:
        logger.warning(f"[{self.COMPANY_NAME}] Extract error: {e}")
    
    return pdf_links
```

#### 2.5 实现 `go_to_next_page()` (可选)

如果网站有分页：

```python
async def go_to_next_page(self, page: Page) -> bool:
    """翻到下一页"""
    try:
        next_btn = page.locator("[下一页按钮选择器]").first
        
        if await next_btn.count() > 0:
            # 检查是否可点击（未禁用）
            is_disabled = await next_btn.get_attribute("disabled")
            if not is_disabled:
                await next_btn.click()
                await asyncio.sleep(2)
                return True
        
        return False
    except Exception as e:
        logger.info(f"[{self.COMPANY_NAME}] No more pages: {e}")
        return False
```

---

### 3. 测试爬虫

#### 3.1 单元测试

在文件末尾添加测试代码：

```python
if __name__ == "__main__":
    spider = NewCompanySpider(headless=False)
    products = asyncio.run(spider.discover_products(
        limit=5, 
        fetch_details=True
    ))
    
    import json
    print(json.dumps(products, ensure_ascii=False, indent=2))
```

运行测试：

```bash
python src/crawler/discovery/[新公司]_spider.py
```

#### 3.2 验证数据完整性

检查返回的数据是否包含所有必需字段：

```python
for product in products:
    assert "product_code" in product
    assert "name" in product
    assert "company" in product
    assert "publish_time" in product
    assert "source_url" in product
    assert "pdf_links" in product
    assert "filename" in product
```

---

### 4. 注册到工厂

在 `spider_factory.py` 中注册：

```python
from src.crawler.discovery.[新公司]_spider import NewCompanySpider

SpiderFactory.register("new-company-code", NewCompanySpider)
```

**公司代码命名规范：**
- 使用小写字母和连字符
- 格式：`公司简称-life` 或 `公司简称-property`
- 示例：`pingan-life`, `china-life`, `picc-property`

---

### 5. 集成到CLI

更新 `src/cli/manage.py` 中的爬虫命令：

```python
@crawl.command()
@click.option('--company', type=click.Choice([
    'pingan-life',
    'china-life',
    'new-company',  # 添加新公司
]), required=True)
def discover(company: str):
    """发现产品"""
    spider = SpiderFactory.create(company, headless=True)
    if spider:
        products = asyncio.run(spider.discover_products(limit=100))
        # 保存到数据库...
```

---

## 常见问题

### Q1: 如何处理需要登录的网站？

在 `navigate_to_page()` 方法中实现登录逻辑：

```python
async def navigate_to_page(self, page: Page):
    await super().navigate_to_page(page)
    
    # 如果检测到登录页面
    if "login" in page.url:
        await page.fill("#username", "your_username")
        await page.fill("#password", "your_password")
        await page.click("button[type='submit']")
        await page.wait_for_url("**/products/**")
```

### Q2: 如何处理动态加载的内容（AJAX）？

使用 `page.wait_for_response()` 等待API请求完成：

```python
async with page.expect_response(
    lambda response: "/api/products" in response.url
) as response_info:
    await page.click(".load-more")

response = await response_info.value
data = await response.json()
```

### Q3: 如何处理验证码？

1. **简单图片验证码**: 使用OCR库识别
2. **滑动验证码**: 模拟人类滑动行为
3. **复杂验证码**: 建议联系网站管理员获取API接口

### Q4: PDF链接是JavaScript生成的怎么办？

使用 `evaluate()` 执行JavaScript：

```python
pdf_url = await page.evaluate("""
    () => {
        return document.querySelector('.download-btn').onclick.toString();
    }
""")
```

---

## 最佳实践

### 1. 合规性

- ✅ 遵守 `robots.txt`
- ✅ 设置合理的请求延迟（2-3秒）
- ✅ 使用真实的User-Agent
- ✅ 只爬取公开披露的信息
- ❌ 不要爬取用户隐私数据

### 2. 稳定性

- ✅ 使用多层try-except捕获异常
- ✅ 保存错误截图便于调试
- ✅ 添加详细的日志记录
- ✅ 实现指数退避重试机制

### 3. 可维护性

- ✅ 使用有意义的变量名
- ✅ 添加详细的注释
- ✅ 将选择器定义为类常量
- ✅ 编写单元测试

### 4. 性能

- ✅ 复用浏览器实例
- ✅ 并行处理多个页面（如果合适）
- ✅ 只在需要时加载图片/视频
- ✅ 使用 `headless=True` 提升速度

---

## 完整示例

参考现有实现：

1. **平安人寿爬虫**: `src/crawler/discovery/pingan_life_spider.py`
   - 表格结构
   - 隐藏下拉菜单
   - 分页处理

2. **中国人寿爬虫(模板)**: `src/crawler/discovery/chinalifeinsurance_spider.py`
   - 卡片结构
   - 完整的实现模板

---

## 需要帮助？

遇到问题时：

1. 查看现有爬虫代码作为参考
2. 使用 `headless=False` 观察浏览器行为
3. 添加 `logger.debug()` 输出调试信息
4. 保存HTML源码分析结构
5. 查阅Playwright文档: https://playwright.dev/python/

---

**祝您顺利完成新爬虫的开发！** 🎉

