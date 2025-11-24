# 实施计划：保险 MCP 核心平台

**分支**: `001-insurance-mcp-core` | **日期**: 2025-11-20 | **规格书**: [specs/001-insurance-mcp-core/spec.md](../spec.md)
**输入**: 来自 `/specs/001-insurance-mcp-core/spec.md` 的功能规格
**最后更新**: 2025-11-23 - P0+增强: 实现产品范围检索和产品查询工具,集成BGE embedding模型

**注意**: 此模板由 `/speckit.plan` 命令填写。请参阅 `.specify/templates/commands/plan.md` 了解执行工作流。

## 摘要

构建保险领域垂直信息 MCP 服务器核心平台。技术路径包括：使用 Playwright 构建按保险公司维度的分层爬虫（发现层+采集层），从保险公司官网获取保险条款 PDF；利用 OCR 和版面分析技术将 PDF 转换为高保真 Markdown；使用 ChromaDB 存储向量化数据；基于 Model Context Protocol (MCP) 提供语义检索服务。第一期聚焦平安人寿公司，实现 MVP，专注于端到端流程跑通和准确性验证。P0+增强实现了产品范围检索(支持按产品过滤查询)和智能产品查询工具(模糊匹配产品名称),显著提升检索准确性。

## 技术背景

**语言/版本**: Python 3.10+
**主要依赖**:
- `mcp`: Model Context Protocol SDK
- `playwright`: 动态网页爬虫 (发现层)
- `scrapy`: 高并发下载 (采集层)
- `docling`: **[New]** 高保真 PDF 解析引擎 (v2.0+)
- `pdfplumber` / `paddleocr`: PDF 解析与 OCR (Legacy)
- `chromadb`: 向量数据库
- `FlagEmbedding`: BGE中文Embedding模型 (BAAI/bge-small-zh-v1.5)
- `typer`: CLI 工具
**存储**:
- 本地文件系统 (PDF 原件, Markdown 结果)
- ChromaDB (向量索引)
- SQLite (元数据管理 - 可选，视 MVP 复杂度而定，暂定文件系统+内存或简单 JSONL)
**测试**: `pytest` (单元测试), `pytest-asyncio` (异步测试)
**目标平台**: 本地运行 (macOS/Linux), Docker 容器化部署
**项目类型**: 后端服务 + CLI 工具
**性能目标**: 爬虫 QPS < 1 (合规限制), 检索响应 < 2s
**约束**: 必须严格遵守 Robots 协议，隐私数据避让，数据源可追溯
**规模/范围**: 第一期仅覆盖平安人寿一家险企，支持该公司数百份 PDF 文档索引，验证端到端流程可行性

## 宪法检查 (Constitution Check)

*关卡: 必须在阶段 0 研究之前通过。在阶段 1 设计之后重新检查。*

- [x] **Library-First**: 核心功能（爬虫、解析、检索）应模块化为独立库/包，便于复用和测试。
- [x] **CLI Interface**: 提供 CLI 工具用于手动触发爬虫、审核数据和测试检索，符合 MVP 快速验证需求。
- [x] **Test-First**: 核心解析逻辑和检索算法需有单元测试覆盖。
- [x] **Simplicity**: MVP 阶段使用本地 ChromaDB 和文件系统存储，避免过度工程。

## 项目结构

### 文档 (本功能)

```text
specs/001-insurance-mcp-core/
├── plan.md              # 本文件
├── research.md          # 阶段 0 输出
├── data-model.md        # 阶段 1 输出
├── quickstart.md        # 阶段 1 输出
├── contracts/           # 阶段 1 输出
└── tasks.md             # 阶段 2 输出
```

### 源代码 (仓库根目录)

```text
src/
├── common/                 # 共享工具 (Logging, Config, Utils)
├── crawler/                # 爬虫模块
│   ├── discovery/          # 发现层 (Playwright)
│   ├── acquisition/        # 采集层 (Scrapy/Aiohttp)
│   └── pipelines/          # 数据管道
├── parser/                 # 解析模块
│   ├── layout/             # 版面分析 (Legacy)
│   ├── ocr/                # OCR 集成 (Legacy)
│   └── markdown/           # Markdown 生成 (Legacy)
├── indexing/               # 索引模块
│   ├── parsers/            # **[New]** 结构化解析器 (Docling)
│   ├── analyzers/          # **[New]** 文档分析器 (费率表分类)
│   ├── chunkers/           # **[New]** 智能切片器 (Markdown感知)
│   ├── vector_store/       # ChromaDB 适配
│   └── embedding/          # BGE Embedding (本地模型)
├── mcp_server/             # MCP 服务端
│   ├── tools/              # MCP 工具实现
│   ├── product_lookup.py   # 产品查询工具 (P0+)
│   └── server.py           # 入口
└── cli/                    # 命令行工具
    ├── verify.py           # 数据审核 CLI
    └── manage.py           # 系统管理 CLI

tests/
├── unit/
│   ├── test_parser.py
│   └── test_crawler_rules.py
├── integration/
│   └── test_mcp_server.py
└── data/                   # 测试数据样本
```

**结构决策**: 采用单一仓库多模块结构 (`src/` 内的 Monorepo 风格)。将爬虫、解析、索引和 MCP 服务解耦，通过清晰的接口交互，便于未来独立拆分或扩展。CLI 工具作为入口调用各模块功能。

## 复杂度追踪 (Complexity Tracking)

| 违规项 | 为什么需要 | 拒绝更简单替代方案的原因 |
|--------|------------|-------------------------|
| (无) | | |
