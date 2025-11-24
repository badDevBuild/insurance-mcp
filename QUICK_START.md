# 🚀 快速开始 - 数据采集流程

## ✅ 已完成的功能

我已经为您创建了一个**完整、健壮的数据采集管道**，包括：

### 核心功能
- ✅ 爬取产品列表和PDF链接
- ✅ 自动下载所有PDF文件
- ✅ 保存元数据到SQLite数据库
- ✅ 智能去重（产品和PDF文件）
- ✅ 错误处理和自动重试
- ✅ 完整的日志记录

### 数据流程

```
爬取产品 → 保存到数据库 → 下载PDF → 计算哈希 → 保存文档记录
```

---

## 🎯 三种使用方式

### 方式1: 快速测试（推荐新手）

```bash
cd /Users/shushu/insurance-mcp
source .venv/bin/activate
python test_acquisition.py
```

这会：
- 爬取5个产品（测试用）
- 下载PDF文件到 `data/raw/平安人寿/`
- 保存元数据到数据库

### 方式2: 使用CLI命令（推荐）

```bash
# 初始化数据库（首次使用）
python -m src.cli.manage init

# 运行完整采集流程
python -m src.cli.manage crawl run --company pingan-life --limit 100
```

### 方式3: 编程方式

```python
import asyncio
from src.common.db import init_db
from src.crawler.pipelines.acquisition_pipeline import run_acquisition

# 初始化
init_db()

# 运行采集
stats = asyncio.run(run_acquisition(company="平安人寿", limit=50))
print(f"采集了 {stats['pdfs_downloaded']} 个PDF文件")
```

---

## 📊 数据结构

### 数据库表

**products表（产品信息）：**
```sql
- id: 主键
- product_code: 产品代码（唯一，用于去重）
- name: 产品名称
- company: 保险公司
- publish_time: 发布时间
- created_at: 创建时间
```

**policy_documents表（文档信息）：**
```sql
- id: 主键
- product_id: 关联产品（外键）
- doc_type: 文档类型（如"产品条款"）
- filename: 文件名
- local_path: 本地路径
- url: 源URL
- file_hash: SHA-256哈希
- file_size: 文件大小
- downloaded_at: 下载时间
- verification_status: 审核状态（PENDING/VERIFIED/REJECTED）
```

### 文件目录结构

```
data/
├── db/
│   └── metadata.sqlite         # 数据库
└── raw/
    └── 平安人寿/                 # 按公司分类
        ├── 2124/                # 按产品代码分类
        │   ├── 产品条款.pdf
        │   ├── 备案产品清单表.pdf
        │   ├── 产品费率表.pdf
        │   ├── 总精算师声明书.pdf
        │   ├── 法律责任人声明书.pdf
        │   └── 产品说明书.pdf
        ├── 2123/
        │   └── ...
        └── ...
```

---

## 🔍 查看结果

### 查看数据库

```bash
sqlite3 data/db/metadata.sqlite

# 查看所有产品
SELECT * FROM products;

# 查看所有文档
SELECT * FROM policy_documents;

# 统计下载情况
SELECT 
  COUNT(*) as total,
  SUM(CASE WHEN file_hash IS NOT NULL THEN 1 ELSE 0 END) as downloaded
FROM policy_documents;

# 查看某个产品的所有PDF
SELECT doc_type, filename, file_size/1024.0 as size_kb
FROM policy_documents
WHERE product_id = (
  SELECT id FROM products WHERE product_code = '2124'
);
```

### 查看文件

```bash
# 查看下载的PDF
ls -lh data/raw/平安人寿/

# 查看某个产品的PDF
ls -lh data/raw/平安人寿/2124/

# 统计文件数量和大小
du -sh data/raw/平安人寿/
```

---

## 🎨 核心特性

### 1. 智能去重

**产品去重：**
- 通过 `product_code` + `company` 判断
- 已存在的产品不会重复插入

**PDF去重：**
- 通过 `product_id` + `doc_type` + `url` 判断
- 已下载的PDF不会重复下载

### 2. 自动重试

下载失败会自动重试（最多3次）：
```
第1次失败 → 等待1秒 → 重试
第2次失败 → 等待2秒 → 重试
第3次失败 → 等待4秒 → 重试
仍然失败 → 记录错误，继续下一个
```

### 3. 部分失败处理

- 某个产品处理失败不影响其他产品
- 某个PDF下载失败不影响其他PDF
- 所有错误都会记录到日志

### 4. 增量更新

可以多次运行采集命令：
```bash
# 第一次运行：下载50个产品
python -m src.cli.manage crawl run --limit 50

# 第二次运行：只会下载新增的产品和PDF
python -m src.cli.manage crawl run --limit 100
```

---

## 📝 实际案例

### 案例1: 首次采集

```bash
$ python -m src.cli.manage crawl run --limit 10

🚀 开始采集 平安人寿 的产品数据...
配置: limit=10, fetch_details=True

================================================================================
步骤 1/3: 爬取产品列表
================================================================================
✓ 发现 10 个产品

================================================================================
步骤 2/3: 保存产品元数据
================================================================================

[1/10] 处理产品: 平安福耀年金保险（分红型） (2124)
  ✓ 新产品已保存: a1b2c3d4...
  📄 下载PDF文件: 6 个文档
    ↓ 下载 [产品条款]...
    ✓ 已保存 [产品条款]: 245.3 KB
    ↓ 下载 [备案产品清单表]...
    ✓ 已保存 [备案产品清单表]: 125.7 KB
    ...

================================================================================
步骤 3/3: 采集完成
================================================================================
📊 采集统计
================================================================================
产品:
  - 发现: 10 个
  - 新增: 10 个
  - 已存在: 0 个

PDF文档:
  - 总计: 60 个
  - 已下载: 58 个
  - 已跳过: 0 个
  - 失败: 2 个
================================================================================

✅ 采集完成!
产品: 发现 10, 新增 10, 已存在 0
PDF: 下载 58, 跳过 0, 失败 2
```

### 案例2: 增量更新

```bash
$ python -m src.cli.manage crawl run --limit 10

# 第二次运行相同命令

[1/10] 处理产品: 平安福耀年金保险（分红型） (2124)
  ✓ 产品已存在: a1b2c3d4...
  📄 下载PDF文件: 6 个文档
    ⊙ 跳过 [产品条款]: 已存在
    ⊙ 跳过 [备案产品清单表]: 已存在
    ...

产品:
  - 发现: 10 个
  - 新增: 0 个
  - 已存在: 10 个

PDF文档:
  - 总计: 60 个
  - 已下载: 0 个
  - 已跳过: 60 个
  - 失败: 0 个
```

---

## 🛠️ 故障排查

### 问题1: 导入错误

```bash
ModuleNotFoundError: No module named 'src'
```

**解决：**
```bash
# 使用 -m 参数
python -m src.cli.manage crawl run

# 或使用测试脚本
python test_acquisition.py
```

### 问题2: 数据库未初始化

```bash
sqlite3.OperationalError: no such table: products
```

**解决：**
```bash
python -m src.cli.manage init
```

### 问题3: 部分PDF下载失败

**原因：** 网络问题或网站限流

**解决：** 重新运行命令，系统会自动重试失败的文件
```bash
python -m src.cli.manage crawl run --limit 100
```

---

## 📚 详细文档

- **完整使用指南：** `docs/DATA_ACQUISITION_GUIDE.md`
- **爬虫架构说明：** `docs/CRAWLER_ARCHITECTURE.md`
- **添加新公司指南：** `docs/ADD_NEW_INSURANCE_COMPANY.md`

---

## 🎉 下一步

数据采集完成后，可以进行：

1. **数据审核** - 人工核验PDF质量
2. **PDF解析** - 转换为Markdown
3. **向量索引** - 索引到ChromaDB
4. **MCP服务** - 提供检索接口

---

**现在就开始吧！**

```bash
python test_acquisition.py
```

