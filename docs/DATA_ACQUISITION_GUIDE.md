# 数据采集完整流程指南

本文档说明如何使用完整的数据采集管道，从爬取产品列表到下载PDF并保存到数据库。

## 📋 目录

1. [流程概览](#流程概览)
2. [快速开始](#快速开始)
3. [详细说明](#详细说明)
4. [数据结构](#数据结构)
5. [故障排查](#故障排查)

---

## 流程概览

### 完整流程图

```
┌─────────────────────────────────────────┐
│  1. 爬取产品列表                        │
│     - 访问平安人寿官网                   │
│     - 提取产品元数据                     │
│     - 获取所有PDF链接                    │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  2. 保存产品信息到数据库                 │
│     - 检查产品是否已存在（去重）          │
│     - 插入新产品记录                     │
│     - 返回产品ID                         │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  3. 下载PDF文件                         │
│     - 遍历所有PDF链接                    │
│     - 检查是否已下载（去重）              │
│     - 下载到本地目录                     │
│     - 计算文件哈希和大小                 │
└──────────────┬──────────────────────────┘
               ↓
┌─────────────────────────────────────────┐
│  4. 保存文档记录到数据库                 │
│     - 创建PolicyDocument记录            │
│     - 关联到Product                     │
│     - 状态设为PENDING（待审核）          │
└─────────────────────────────────────────┘
```

### 核心组件

| 组件 | 文件 | 职责 |
|------|------|------|
| **爬虫** | `pingan_life_spider.py` | 爬取产品列表和PDF链接 |
| **下载器** | `downloader.py` | 下载PDF文件（带重试） |
| **数据模型** | `models.py` | Product和PolicyDocument |
| **数据库** | `repository.py` | 数据持久化 |
| **采集管道** | `acquisition_pipeline.py` | 整合所有组件 |
| **CLI命令** | `manage.py` | 用户接口 |

---

## 快速开始

### 1. 初始化数据库

首次使用前，需要初始化数据库和目录结构：

```bash
cd /Users/shushu/insurance-mcp
source .venv/bin/activate

# 初始化
python -m src.cli.manage init
```

**输出示例：**
```
Initializing Insurance MCP...
Database initialized at data/db/metadata.sqlite
Initialization complete.
```

### 2. 运行完整采集流程

**一站式命令**（推荐）：

```bash
python -m src.cli.manage crawl run --company pingan-life --limit 10
```

**参数说明：**
- `--company`: 公司代码（目前只支持 `pingan-life`）
- `--limit`: 最大爬取产品数量（默认100）

### 3. 查看结果

**数据库：**
```bash
sqlite3 data/db/metadata.sqlite

# 查看产品
SELECT * FROM products;

# 查看文档
SELECT * FROM policy_documents;
```

**PDF文件：**
```bash
ls -lh data/raw/平安人寿/
```

**目录结构示例：**
```
data/raw/平安人寿/
├── 2124/
│   ├── 产品条款.pdf
│   ├── 备案产品清单表.pdf
│   ├── 产品费率表.pdf
│   ├── 总精算师声明书.pdf
│   ├── 法律责任人声明书.pdf
│   └── 产品说明书.pdf
├── 2123/
│   └── ...
```

---

## 详细说明

### 数据去重策略

系统在多个层面进行去重：

#### 1. 产品去重

通过 `product_code` + `company` 组合判断：

```python
# 如果产品已存在，直接返回现有记录
existing = repo.get_product_by_code(product_code, company)
```

#### 2. PDF去重

通过 `product_id` + `doc_type` + `url` 组合判断：

```python
# 如果PDF已下载，跳过
if document_exists(product_id, doc_type, url):
    skip_download()
```

### 错误处理

#### 1. 下载失败重试

下载器自动进行指数退避重试：

```python
PDFDownloader(
    max_retries=3,      # 最多重试3次
    initial_delay=1.0   # 初始延迟1秒
)
```

**重试策略：**
- 第1次失败：等待 1秒
- 第2次失败：等待 2秒
- 第3次失败：等待 4秒
- 加入随机抖动避免请求冲突

#### 2. 部分失败继续执行

某个产品处理失败不会影响其他产品：

```python
for product in products:
    try:
        process(product)
    except Exception as e:
        log_error(e)
        continue  # 继续处理下一个
```

### 文件命名规范

**产品目录：**
```
data/raw/{公司名}/{产品代码}/
```

**PDF文件：**
```
{文档类型}.pdf
```

**非法字符处理：**

以下字符会被替换为下划线：
```
/ \ : * ? " < > |
```

例如：`产品条款(2024版)` → `产品条款_2024版_.pdf`

### 哈希计算

使用SHA-256算法计算文件哈希，用于：
1. 检测文件是否被篡改
2. 文件去重
3. 数据完整性验证

```python
# 8KB块读取，节省内存
while chunk := f.read(8192):
    sha256.update(chunk)
```

---

## 数据结构

### Product表

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| id | TEXT | UUID主键 | "a1b2c3d4..." |
| product_code | TEXT | 产品代码（唯一） | "2124" |
| name | TEXT | 产品名称 | "平安福耀年金保险（分红型）" |
| company | TEXT | 保险公司 | "平安人寿" |
| category | TEXT | 产品类别 | NULL（未实现） |
| publish_time | TEXT | 发布时间 | "2025-11-18" |
| created_at | TIMESTAMP | 创建时间 | "2025-11-21 10:30:00" |

**索引：**
- `idx_product_code`: product_code（唯一性检查）
- `idx_product_company`: company（按公司查询）

### PolicyDocument表

| 字段 | 类型 | 说明 | 示例 |
|------|------|------|------|
| id | TEXT | UUID主键 | "x1y2z3..." |
| product_id | TEXT | 关联产品ID（外键） | "a1b2c3d4..." |
| doc_type | TEXT | 文档类型 | "产品条款" |
| filename | TEXT | 文件名 | "产品条款.pdf" |
| local_path | TEXT | 本地路径 | "data/raw/平安人寿/2124/产品条款.pdf" |
| url | TEXT | 源URL | "https://life.pingan.com/..." |
| file_hash | TEXT | SHA-256哈希 | "a3f8d9..." |
| file_size | INTEGER | 文件大小（字节） | 1048576 |
| downloaded_at | TIMESTAMP | 下载时间 | "2025-11-21 10:32:15" |
| verification_status | TEXT | 审核状态 | "PENDING" |
| auditor_notes | TEXT | 审核备注 | NULL |
| markdown_content | TEXT | Markdown内容 | NULL（未解析） |

**索引：**
- `idx_doc_product`: product_id（查询产品的所有文档）
- `idx_doc_status`: verification_status（查询待审核文档）
- `idx_doc_hash`: file_hash（哈希查重）
- `idx_doc_unique`: (product_id, doc_type, url)（防重复下载）

---

## 故障排查

### 问题1: 导入模块失败

**错误：**
```
ModuleNotFoundError: No module named 'src'
```

**解决：**
```bash
# 方法1: 使用 -m 参数
python -m src.cli.manage crawl run

# 方法2: 设置PYTHONPATH
export PYTHONPATH=/Users/shushu/insurance-mcp:$PYTHONPATH
python src/cli/manage.py crawl run
```

### 问题2: 数据库表不存在

**错误：**
```
sqlite3.OperationalError: no such table: products
```

**解决：**
```bash
# 重新初始化数据库
python -m src.cli.manage init
```

### 问题3: PDF下载失败

**原因：**
- 网络连接问题
- 目标网站限流
- URL已失效

**查看日志：**
```bash
# 日志中会显示详细的失败原因
2025-11-21 | WARNING | Failed to download https://... : Status 403
2025-11-21 | INFO | Retrying in 2.5s...
```

**手动重试：**

如果部分PDF下载失败，可以再次运行命令：
```bash
python -m src.cli.manage crawl run --company pingan-life --limit 100
```

系统会自动跳过已下载的文件。

### 问题4: 磁盘空间不足

**检查空间：**
```bash
df -h data/raw/
```

**清理旧文件：**
```bash
# 删除某个产品的PDF
rm -rf data/raw/平安人寿/2124/

# 数据库会保留记录，下次运行会重新下载
```

### 问题5: 字符编码问题

如果文件名包含特殊字符导致保存失败，系统会自动清理非法字符。

查看日志：
```
WARNING | Sanitized filename: 产品条款（2024版） -> 产品条款_2024版_
```

---

## 高级用法

### 1. 自定义爬取范围

```bash
# 只爬取5个产品（快速测试）
python -m src.cli.manage crawl run --limit 5

# 爬取所有产品（可能需要较长时间）
python -m src.cli.manage crawl run --limit 1000
```

### 2. 查询数据库

```sql
-- 统计各状态的文档数量
SELECT verification_status, COUNT(*) as count 
FROM policy_documents 
GROUP BY verification_status;

-- 查看某个产品的所有文档
SELECT doc_type, filename, file_size/1024.0 as size_kb 
FROM policy_documents 
WHERE product_id = 'xxx';

-- 查找下载失败的记录（file_hash为NULL）
SELECT p.name, pd.doc_type, pd.url 
FROM policy_documents pd
JOIN products p ON pd.product_id = p.id
WHERE pd.file_hash IS NULL;
```

### 3. 导出数据

```bash
# 导出产品列表为JSON
sqlite3 data/db/metadata.sqlite <<EOF
.mode json
.output products.json
SELECT * FROM products;
.quit
EOF

# 导出为CSV
sqlite3 data/db/metadata.sqlite <<EOF
.mode csv
.headers on
.output products.csv
SELECT * FROM products;
.quit
EOF
```

---

## 性能优化

### 并发下载（未来改进）

当前是串行下载，未来可以改为并发：

```python
# 当前: 逐个下载（安全但慢）
for url in urls:
    await download(url)

# 未来: 并发下载（快但需要限流）
await asyncio.gather(*[download(url) for url in urls])
```

### 增量更新

系统已支持增量更新：
- 已存在的产品不会重复插入
- 已下载的PDF不会重复下载

**建议：**
- 每天运行一次采集所有产品
- 系统自动跳过已有数据，只下载新增内容

---

## 下一步

数据采集完成后，可以进行：

1. **数据审核** (T019)
   ```bash
   python -m src.cli.verify review
   ```

2. **PDF解析** (T016)
   ```bash
   python -m src.cli.manage process --all
   ```

3. **向量索引** (T024)
   ```bash
   python -m src.cli.manage index --rebuild
   ```

---

## 联系与支持

如有问题，请查看：
- 爬虫架构文档：`docs/CRAWLER_ARCHITECTURE.md`
- 添加新公司指南：`docs/ADD_NEW_INSURANCE_COMPANY.md`
- 任务清单：`specs/001-insurance-mcp-core/tasks.md`

**Happy Crawling!** 🎉

