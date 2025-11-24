# 爬虫架构说明

## 📚 当前代码逻辑详解

### 1. **PingAnLifeSpider 类结构**

```python
class PingAnLifeSpider:
    BASE_URL = "https://life.pingan.com/gongkaixinxipilu/..."
    
    def __init__(self, headless=True):
        # 初始化：设置浏览器模式
    
    async def discover_products(self, limit, fetch_details):
        # 主流程：爬取产品列表
```

### 2. **执行流程图**

```
┌─────────────────────────────────────────────┐
│ 1. 启动浏览器 (Chromium)                    │
│    - 设置User-Agent                         │
│    - 设置视口大小                           │
└─────────────┬───────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ 2. 导航到目标网页                           │
│    await page.goto(BASE_URL)                │
└─────────────┬───────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ 3. 等待表格加载                             │
│    await page.wait_for_selector("table")    │
└─────────────┬───────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ 4. 循环处理每一页                           │
│    while len(results) < limit:              │
└─────────────┬───────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ 5. 获取当前页的所有行                        │
│    rows = await page.locator("tr").all()    │
└─────────────┬───────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ 6. 逐行提取数据                             │
│    for row in rows:                         │
│      - 产品代码 (tds[0])                    │
│      - 产品名称 (tds[1])                    │
│      - 下拉菜单 (tds[2]) ← PDF链接          │
│      - 发布时间 (tds[3])                    │
└─────────────┬───────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ 7. 提取PDF链接 (核心逻辑)                   │
│    ul_element = tds[2].locator("ul")        │
│    links = ul_element.locator("a").all()    │
│                                             │
│    关键：不需要点击展开下拉菜单！           │
│    原因：所有链接已在DOM中，只是CSS隐藏     │
└─────────────┬───────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ 8. 构建返回数据                             │
│    item = {                                 │
│      "product_code": "2124",                │
│      "name": "平安福耀年金保险",             │
│      "pdf_links": {                         │
│        "产品条款": "https://...",           │
│        "备案产品清单表": "https://...",     │
│        ...                                  │
│      }                                      │
│    }                                        │
└─────────────┬───────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ 9. 翻页处理                                 │
│    next_btn = page.locator("a:下一页")     │
│    await next_btn.click()                   │
└─────────────┬───────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ 10. 返回结果                                │
│     return results                          │
└─────────────────────────────────────────────┘
```

### 3. **核心技巧：直接读取隐藏的DOM元素**

```python
# ❌ 错误方式：尝试点击展开下拉菜单
await dropdown.click()
await asyncio.sleep(1)
links = await page.locator("ul a").all()

# ✅ 正确方式：直接读取DOM中的链接
ul_element = dropdown_cell.locator("ul").first  # <ul> 在DOM中存在
links = await ul_element.locator("a").all()     # 直接获取所有 <a>

# 原因：HTML结构如下
# <td class="dropdown">
#   <a>请选择</a>
#   <ul style="display: none;">  ← CSS隐藏，但DOM中存在
#     <a href="...">产品条款</a>
#     <a href="...">备案产品清单表</a>
#   </ul>
# </td>
```

---

## 🔧 如何添加其他保险公司

### 方案概览

我已经为您创建了完整的可扩展架构：

```
架构组件:
├── base_spider.py              ← 基类（定义通用接口）
├── pingan_life_spider.py       ← 平安人寿实现（您当前使用的）
├── pingan_life_spider_v2.py    ← 重构版（继承基类）
├── chinalifeinsurance_spider.py ← 其他公司模板
├── spider_factory.py           ← 工厂类（统一管理）
└── [新公司]_spider.py          ← 您要添加的新爬虫
```

### 添加新公司的5步流程

#### **步骤1: 创建爬虫文件**

```bash
cd src/crawler/discovery/
cp chinalifeinsurance_spider.py taikang_life_spider.py  # 复制模板
```

#### **步骤2: 修改类定义**

```python
class TaikangLifeSpider(BaseInsuranceSpider):
    """泰康人寿爬虫"""
    
    # 1️⃣ 设置目标网站URL
    BASE_URL = "https://www.taikanglife.com/products/list"
    
    # 2️⃣ 设置公司名称
    COMPANY_NAME = "泰康人寿"
```

#### **步骤3: 分析目标网站**

使用浏览器开发者工具 (F12) 分析页面结构：

```python
# 示例：假设泰康人寿的HTML结构是
# <div class="product-list">
#   <div class="product-item">
#     <span class="code">产品代码</span>
#     <h3 class="name">产品名称</h3>
#     <span class="date">发布时间</span>
#     <div class="files">
#       <a href="...">条款</a>
#       <a href="...">费率表</a>
#     </div>
#   </div>
# </div>
```

#### **步骤4: 实现4个核心方法**

```python
class TaikangLifeSpider(BaseInsuranceSpider):
    
    # 方法1: 等待页面加载
    async def wait_for_page_load(self, page: Page):
        await page.wait_for_selector(".product-list", timeout=10000)
    
    # 方法2: 解析产品列表 ⭐ 核心方法
    async def parse_product_list(self, page, limit, fetch_details):
        results = []
        
        # 获取所有产品项
        items = await page.locator(".product-item").all()
        
        for item in items:
            # 提取字段（根据实际HTML调整选择器）
            code = await item.locator(".code").text_content()
            name = await item.locator(".name").text_content()
            date = await item.locator(".date").text_content()
            
            # 提取PDF链接
            files_div = item.locator(".files")
            pdf_links = await self.extract_pdf_links(files_div)
            
            # 构建数据
            results.append(self.normalize_product_data(
                product_code=code,
                name=name,
                publish_time=date,
                pdf_links=pdf_links,
                source_url=pdf_links.get("条款", "")
            ))
        
        return results
    
    # 方法3: 提取PDF链接
    async def extract_pdf_links(self, element):
        pdf_links = {}
        links = await element.locator("a").all()
        
        for link in links:
            text = await link.text_content()
            url = await link.get_attribute("href")
            if text and url:
                pdf_links[text.strip()] = url
        
        return pdf_links
    
    # 方法4: 翻页 (如果需要)
    async def go_to_next_page(self, page: Page) -> bool:
        next_btn = page.locator(".pagination .next")
        if await next_btn.count() > 0:
            await next_btn.click()
            return True
        return False
```

#### **步骤5: 注册到工厂**

在 `spider_factory.py` 中注册：

```python
from src.crawler.discovery.taikang_life_spider import TaikangLifeSpider

# 在文件末尾添加
SpiderFactory.register("taikang-life", TaikangLifeSpider)
```

### 使用新爬虫

```python
from src.crawler.discovery.spider_factory import SpiderFactory

# 方式1: 通过工厂创建
spider = SpiderFactory.create("taikang-life", headless=True)
products = await spider.discover_products(limit=50)

# 方式2: 直接实例化
from src.crawler.discovery.taikang_life_spider import TaikangLifeSpider
spider = TaikangLifeSpider(headless=True)
products = await spider.discover_products(limit=50)
```

---

## 📊 对比：当前实现 vs 重构版

| 特性 | 当前 pingan_life_spider.py | 重构版 (基于BaseSpider) |
|------|---------------------------|------------------------|
| **代码复用** | ❌ 每个公司独立实现 | ✅ 继承基类，复用通用逻辑 |
| **可维护性** | ⚠️  修改需同步多处 | ✅ 修改基类即可影响所有子类 |
| **统一管理** | ❌ 需要手动导入各个爬虫 | ✅ 工厂类统一管理 |
| **扩展性** | ⚠️  添加新公司需要大量代码 | ✅ 只需实现4个核心方法 |
| **测试覆盖** | ⚠️  每个爬虫单独测试 | ✅ 基类测试 + 子类特定测试 |

### 建议：逐步迁移

```python
# 当前使用：
from src.crawler.discovery.pingan_life_spider import PingAnLifeSpider

# 未来迁移到：
from src.crawler.discovery.spider_factory import SpiderFactory
spider = SpiderFactory.create("pingan-life")
```

---

## 🎯 快速参考

### 常用选择器

| 元素类型 | Playwright选择器示例 |
|---------|---------------------|
| 表格行 | `table tbody tr` |
| 表格单元格 | `td:nth-child(1)` |
| 类名 | `.product-item` |
| ID | `#product-list` |
| 文本内容 | `a:has-text('下一页')` |
| 属性 | `a[href$='.pdf']` |
| 后代元素 | `.dropdown ul a` |

### 常用方法

```python
# 获取元素
element = await page.locator("selector").first
elements = await page.locator("selector").all()

# 提取数据
text = await element.text_content()      # 文本内容
html = await element.inner_html()        # HTML内容
attr = await element.get_attribute("href") # 属性值

# 交互
await element.click()                    # 点击
await element.fill("text")               # 输入文本
await element.check()                    # 勾选复选框

# 等待
await page.wait_for_selector("selector") # 等待元素
await page.wait_for_timeout(2000)        # 等待时间
```

---

## 📁 完整文档

- **详细扩展指南**: `docs/ADD_NEW_INSURANCE_COMPANY.md`
- **基类代码**: `src/crawler/discovery/base_spider.py`
- **工厂类代码**: `src/crawler/discovery/spider_factory.py`
- **示例实现**: `src/crawler/discovery/chinalifeinsurance_spider.py`

---

**总结**：您当前的 `pingan_life_spider.py` 是一个完整、可工作的爬虫实现。要添加其他保险公司，建议使用我创建的基类架构，通过继承 `BaseInsuranceSpider` 来快速实现新公司的爬虫，代码更清晰、更易维护。

