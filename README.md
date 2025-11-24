# Speckit - Insurance MCP Server

> **打造高准确度、可信赖的保险领域垂直信息 MCP 服务器。**

本项目旨在解决通用 AI 在处理严肃保险决策时存在的幻觉和细节混淆问题，通过 Model Context Protocol (MCP) 为 AI 客户端提供准确的保险条款信息。

## 📜 项目宪章

请参阅 [speckit.constitution.md](./speckit.constitution.md) 了解本项目的核心愿景、原则及架构设计。

## 🏗️ 系统架构

根据宪章，本项目包含以下模块：

1.  **Crawler (爬虫)**: 获取官方保险条款 PDF。
2.  **ETL (转换)**: PDF 转 Markdown (高保真解析)。
3.  **Review (审核)**: 人工/自动化质量控制。
4.  **RAG (检索)**: 向量化存储与语义检索。
5.  **MCP Server**: 提供标准 MCP 接口。

## 🚀 快速开始

### 环境配置

```bash
# 1. 克隆项目
git clone <repository-url>
cd insurance-mcp

# 2. 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt
playwright install

# 4. 初始化数据库
python -m src.cli.manage init
```

### 核心功能

#### 1. 自动化采集（已实现 ✅）

采集平安人寿官网的保险产品PDF文档：

```bash
# 完整采集流程：发现产品 → 下载PDF → 保存到数据库
python -m src.cli.manage crawl run --company pingan-life --limit 20
```

**特性**：
- 🚀 Playwright动态网页爬取
- 🔒 QPS限流（0.8 QPS）+ 熔断机制
- 📦 自动去重（基于产品代码）
- 💾 元数据入库 + PDF本地存储

#### 2. PDF处理（已实现 ✅）

将PDF文档转换为高质量Markdown：

```bash
# 转换产品条款
python -m src.cli.manage process convert --doc-type 产品条款 --limit 10

# 分析PDF版面
python -m src.cli.manage process analyze 2124
```

**特性**：
- 📄 基于markitdown高保真转换
- 🎯 支持产品条款、产品说明书
- 📊 版面分析和质量评分
- 💾 Markdown存储 + 数据库索引

#### 3. 人工审核（已实现 ✅）

审核员工作流：

```bash
# 查看待审核文档
python -m src.cli.verify list

# 预览转换结果
python -m src.cli.verify preview 067afcfc

# 批准/驳回
python -m src.cli.verify approve 067afcfc --notes "格式完整"
python -m src.cli.verify reject 067afcfc -r "表格错误"

# 查看统计
python -m src.cli.verify stats
```

#### 4. 向量检索（已实现 ✅）

索引VERIFIED文档并提供语义检索：

```bash
# 索引已审核文档（Docling模式）
python -m src.cli.manage index rebuild --use-docling

# Legacy模式（使用Markdown）
python -m src.cli.manage index rebuild --no-docling

# 测试检索
python -m src.cli.manage index test-search "保险期间多久"

# 查看索引统计
python -m src.cli.manage index stats

# 查看导出的费率表
python -m src.cli.manage index tables --list
```

**特性**：
- 🧠 BGE-M3 中文嵌入（768维）
- 🔍 混合检索（Dense Vector + BM25）
- 📊 Docling 高精度PDF解析
- 📄 费码表自动分离导出CSV
- 🧵 章节面包屑路径

#### 5. MCP 服务（已实现 ✅）

启动MCP服务器为AI客户端提供服务：

```bash
# 启动MCP服务器
python -m src.mcp_server.server
```

**可用工具**：
- `search_policy_clause`: 语义条款检索
- `check_exclusion_risk`: 免责条款核查
- `calculate_surrender_value_logic`: 退保/减额交清逻辑提取
- `lookup_product`: 产品查询

### 详细文档

- 📖 [快速入门指南](./specs/001-insurance-mcp-core/quickstart.md)
- 📖 [PDF处理指南](./docs/PDF_PROCESSING_GUIDE.md)
- 📖 [QPS限流指南](./docs/QPS_RATE_LIMITER_GUIDE.md)

## 📝 开发日志

### 第一阶段：项目初始化 ✅
- 初始化项目结构
- 确立 [项目宪法](./speckit.constitution.md)
- 定义数据模型和技术栈

### 第二阶段：数据模型 ✅
- 实现 `Product` 和 `PolicyDocument` Pydantic模型
- 设计SQLite数据库schema
- 实现Repository模式的数据访问层

### 第三阶段：自动化采集 ✅
- 实现平安人寿爬虫（Playwright）
- 实现PDF下载器（异步 + 指数退避）
- 实现QPS限流器（Token Bucket + Circuit Breaker）
- 实现完整采集pipeline

### 第四阶段：PDF处理 ✅
- 实现PDF→Markdown转换器（markitdown）
- 实现PDF版面分析器（pdfplumber）
- 实现审核员CLI工具
- 完成人工审核工作流

### 第五阶段：向量检索 ✅
- BGE-M3 中文嵌入（768维）
- 混合检索（Dense Vector + BM25 + RRF）
- 智能元数据提取（category, keywords）
- ChromaDB 向量存储
- Markdown 后处理 Pipeline

### 第六阶段：Docling 集成 ✅ ← **最新**
- Docling 高精度PDF解析（多栏识别）
- 费率表自动分离导出CSV
- 章节面包屑路径（breadcrumb）
- 双模式架构（Docling/Legacy）
- 单元测试 + 集成测试全部通过

### 第七阶段：MCP服务 ✅
- MCP服务器实现
- 4个专业工具（search_clause, check_exclusion, surrender_logic, lookup_product）
- 支持产品范围过滤
- Claude Desktop 可集成

---

## 🚀 改进计划

基于深度研究报告《保险文档智能处理全流程架构》，我们制定了四阶段改进路线图：

### 🏆 已完成：Phase 6 - Docling 集成与结构化解析重构

**目标**: 将现有的"文本流提取"升级为"文档对象模型（DOM）提取"

**核心技术**: Docling v2.63.0 (IBM开源)

**实际效果** ✅:
- ✅ 表格结构完整保留
- ✅ 阅读顺序自动修复（多栏支持）
- ✅ 费率表自动识别并导出 CSV
- ✅ 章节面包屑路径注入
- ✅ 单元测试 + 集成测试 100% 通过

**完成时间**: 2025-11-24

### 🗺️ 完整路线图

```
Phase 1 (当前)         Phase 2             Phase 3              Phase 4
高保真解析重构    →   领域知识增强    →   图谱与推理      →   多模态智能体
[3周]                 [3周]               [4周]               [6周]
```

**详细信息**: 请查看 [docs/IMPROVEMENT_ROADMAP.md](./docs/IMPROVEMENT_ROADMAP.md)

**执行计划**: Plan ID `4ba969fd-cc33-428d-bb9a-e49b8c42c3da`

