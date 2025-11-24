# 研究报告：保险 MCP 核心平台

**功能分支**: `001-insurance-mcp-core`
**状态**: 阶段 0 完成

## 决策与理由

### 1. PDF 解析与版面分析
**决策**: 使用 **Microsoft MarkItDown** (或 `pdfplumber` + 自定义启发式算法作为后备)，并结合 **PaddleOCR** 处理扫描内容。
**理由**:
- MarkItDown 是 Microsoft 最近开源的专门用于将各种格式（包括 PDF）转换为 Markdown 的工具，比原始提取能更好地处理版面分析。
- PaddleOCR 提供最佳的开源中文识别准确率，这对扫描版保单文档至关重要。
**考虑过的替代方案**:
- `Unstructured`: 功能强大但沉重，开源版本有限制。
- `Azure Document Intelligence`: 成本高，不适合本地优先的 MVP。

### 2. 爬虫架构
**决策**: **Playwright** 用于发现层 (IAC) + **Scrapy/Aiohttp** 用于采集层。
**理由**:
- IAC (中国保险行业协会) 网站严重依赖动态渲染和复杂的表单提交，Playwright 能可靠处理。
- 文件下载需要并发控制和健壮性，Scrapy/Aiohttp 在这方面表现优异。
**考虑过的替代方案**:
- Selenium: 较慢，资源占用重。
- 纯 Requests/BeautifulSoup: 无法处理 IAC 的 JS 渲染分页。

### 3. 向量数据库
**决策**: **ChromaDB** (本地持久化模式)。
**理由**:
- 无需部署基础设施（保存为本地文件）。
- 原生 Python API 集成。
- 性能足以应对 <1M 向量（MVP 规模）。
**考虑过的替代方案**:
- Pinecone: 需要云端设置，增加延迟。
- pgvector: 需要运行 PostgreSQL 容器，增加 MVP 复杂度。

### 4. Embedding 模型
**决策**: **OpenAI `text-embedding-3-small`**。
**理由**:
- 行业标准性能。
- 成本极低（$0.02 / 1M tokens）。
- 1536 维度提供出色的语义检索质量。
**考虑过的替代方案**:
- `sentence-transformers` (本地): 增加 CPU/内存开销、部署复杂度和模型管理负担。

### 5. MCP SDK
**决策**: **官方 `mcp` Python SDK**。
**理由**:
- 原生支持协议。
- 简化工具注册和服务器管理。

## 已解决的疑问

- **Q: 如何处理双栏 PDF？**
  - **A**: 使用版面感知解析（通过 `pdfplumber` 坐标或 MarkItDown 的启发式算法检测栏间距），按左栏向下然后右栏向下的顺序读取。
- **Q: 元数据存储在哪里？**
  - **A**: 对于 MVP，元数据（文件名、URL、核验状态）将存储在原始数据目录旁的轻量级 **SQLite** 数据库文件中。这为 CLI 提供了 SQL 查询能力，而无需繁重的服务器设置。
