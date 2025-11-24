# 快速开始：保险 MCP 核心平台

**功能分支**: `001-insurance-mcp-core`
**最后更新**: 2025-11-21
**第一期范围**: 仅支持平安人寿公司数据采集

## 先决条件

- Python 3.10+
- OpenAI API Key (设置为 `OPENAI_API_KEY`)
- Docker (可选，用于容器化运行)

## 安装

1. **克隆并安装依赖**:
   ```bash
   git clone <repo>
   cd insurance-mcp
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **设置环境变量**:
   ```bash
   # 创建 .env 文件
   echo "OPENAI_API_KEY=sk-..." > .env
   ```

3. **初始化数据库**:
   ```bash
   # 创建 data/db/metadata.sqlite 和数据目录
   python -m src.cli.manage init
   ```

## 使用流程

### 1. 数据采集 (一键运行)

**推荐方式**：使用统一的 `run` 命令完成发现、下载、入库全流程：

```bash
# 采集平安人寿产品（限制10个用于快速测试）
python -m src.cli.manage crawl run --company pingan-life --limit 10

# 采集更多产品（如100个）
python -m src.cli.manage crawl run --company pingan-life --limit 100
```

**分步运行**（高级用法）：

```bash
# 步骤1: 发现产品并保存到JSON
python -m src.cli.manage crawl discover --company pingan-life --limit 10 --output products.json

# 步骤2: 从JSON下载PDF
python -m src.cli.manage crawl acquire --input products.json
```

**说明**：
- 第一期仅支持 `--company pingan-life`，爬取平安人寿官网 (https://life.pingan.com/gongkaixinxipilu/baoxianchanpinmulujitiaokuan.jsp)
- 系统自动去重：已下载的PDF和已存在的产品会被跳过
- 每个产品的所有文档（条款、费率表、说明书等）都会被下载
- 所有元数据（包括PDF链接）都保存到SQLite数据库

### 2. 处理与核验 (待实施)

转换 PDF 并打开核验 CLI：

```bash
# 解析待处理的 PDF
python -m src.cli.manage process --all

# 启动审核员 CLI 以审查文档
python -m src.cli.verify review
# > [?] 显示文档 1: 平安福耀年金保险... (y/n/skip)
# > ... (显示 Markdown 预览) ...
# > [?] 标记为已核验？ (y/n)
```

### 3. PDF 处理与审核

将下载的 PDF 转换为 Markdown：

```bash
# 转换所有产品条款（限制数量）
python -m src.cli.manage process convert --doc-type 产品条款 --limit 10

# 转换所有产品说明书
python -m src.cli.manage process convert --doc-type 产品说明书 --limit 10

# 转换所有待处理文档（不限制）
python -m src.cli.manage process convert --all

# 分析特定产品的PDF版面结构
python -m src.cli.manage process analyze 2124
```

**审核转换结果**（审核员工作流）：

```bash
# 查看待审核文档列表
python -m src.cli.verify list

# 预览特定文档的转换结果
python -m src.cli.verify preview 067afcfc

# 批准文档
python -m src.cli.verify approve 067afcfc --notes "格式完整，内容准确"

# 驳回文档
python -m src.cli.verify reject 067afcfc -r "表格格式错误"

# 查看审核统计
python -m src.cli.verify stats
```

**处理结果**：
- Markdown 文件保存在 `data/processed/` 目录
- 每个文档以其 UUID 命名（如 `067afcfc-e8eb-43d2-994a-66474dcd65e5.md`）
- 数据库中保存前 5000 字符的预览
- 文档状态：PENDING（待审核）→ VERIFIED（已通过）或 REJECTED（已驳回）

### 4. 索引 (待实施)

将已核验的文档索引到 ChromaDB：

```bash
python -m src.cli.manage index --rebuild
```

### 5. 运行 MCP 服务器 (待实施)

启动服务器以供 Claude Desktop 或其他客户端使用：

```bash
# 标准 Stdio 模式
python -m src.mcp_server.server
```

---

## 查看采集结果

### 查看数据库

```bash
sqlite3 data/db/metadata.sqlite

# 查看所有产品
SELECT product_code, name, company, publish_time FROM products LIMIT 10;

# 查看所有文档
SELECT doc_type, filename, file_size/1024.0 as size_kb FROM policy_documents LIMIT 10;

# 查看某个产品的所有文档
SELECT doc_type, filename, url 
FROM policy_documents 
WHERE product_id = (SELECT id FROM products WHERE product_code = '2124');
```

### 查看下载的文件

```bash
# 查看目录结构
tree data/raw/平安人寿/ -L 2

# 查看某个产品的文件
ls -lh data/raw/平安人寿/2124/
```

## 配置

创建 `.env` 文件：

```ini
OPENAI_API_KEY=sk-...
CHROMA_DB_PATH=./data/vector_store
SQLITE_DB_PATH=./data/db/metadata.sqlite
LOG_LEVEL=INFO
```
