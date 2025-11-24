# 功能规格书：保险 MCP 核心平台 (Insurance MCP Core Platform)

**功能分支**: `001-insurance-mcp-core`
**创建日期**: 2025-11-20
**最后更新**: 2025-11-21
**状态**: 草稿 (Draft)
**输入来源**: 用户描述："构建一个高准确度、可信赖的保险领域垂直信息 MCP 服务器..."
**最新变更**: 2025-11-21 - 调整爬虫策略为按保险公司维度采集，第一期聚焦平安人寿

## 澄清 (Clarifications)

### 会话 2025-11-20
- Q: 选择哪种向量数据库方案？ → A: **ChromaDB (Local)** - 轻量级、开源、支持进程内运行或 Docker，适合第一阶段开发，零成本且易于本地调试。

### 会话 2025-11-23
- Q: Embedding 模型选择方案？ → A: **BGE-small-zh-v1.5 (本地部署)** - BAAI开源模型,中文性能优秀(C-MTEB 68分),配置要求低(102MB,CPU可运行),完全免费,推理速度快,适合本地部署和隐私保护。

## 用户场景与测试 (User Scenarios & Testing)

### 用户故事 1 - AI 客户端获取精准信息 (AI Client Accurate Information Retrieval) (优先级: P1)

作为 AI 客户端（通过 LLM），我希望能够检索到基于语义搜索的准确保险条款，从而能够在不产生幻觉的情况下回答用户问题。

**优先级理由**: 这是核心价值主张——消除保险咨询中的幻觉问题。

**独立测试**: 通过发送针对特定保险责任细节的 MCP 请求，验证返回内容是否包含条款原文的精确文本。

**验收场景 (Acceptance Scenarios)**:

1. **Given (已知)** 数据库中存在已核验的保险条款，**When (当)** AI 客户端调用 `search_products` 进行模糊查询时（例如："产品 X 承保攀岩吗？"），**Then (那么)** 系统返回具有高语义相似度的相关条款。
2. **Given (已知)** 查询的产品存在，但没有与查询相关的条款，**When (当)** 进行搜索时，**Then (那么)** 系统返回空结果或"未找到相关条款"，而不是编造答案。
3. **Given (已知)** 发起查询，**When (当)** 返回结果时，**Then (那么)** 每个结果都包含指向具体文件和章节的 `source_reference`（来源引用）。

---

### 用户故事 2 - 数据审核员核验 (Data Auditor Verification) (优先级: P1)

作为数据审核员，我希望能够将转换后的 Markdown 文本与原始 PDF 进行对比审核，从而确保上线数据的 100% 准确性。

**优先级理由**: 为了满足"准确性高于一切"的原则，必须有"人机协同 (Human-in-the-Loop)"环节。

**独立测试**: 运行审核工具/脚本，查看差异对比界面，并批准一个文档。

**验收场景 (Acceptance Scenarios)**:

1. **Given (已知)** 一个新爬取并转换完成的保单文档，**When (当)** 审核员打开审核界面 (CLI/Web) 时，**Then (那么)** 看到状态为"未核验 (Unverified)"。
2. **Given (已知)** 一个未核验的文档，**When (当)** 审核员将其标记为"已核验 (Verified)"，**Then (那么)** 该文档即可进入向量索引流程。
3. **Given (已知)** 一个存在转换错误的文档，**When (当)** 审核员标记报错，**Then (那么)** 该文档在修复前会被排除在索引之外。

---

### 用户故事 3 - 自动化条款采集 (Automated Policy Acquisition) (优先级: P2)

作为系统运维人员，我希望系统能按保险公司维度自动发现并获取该公司的最新保险条款，从而建立精准的公司产品数据库。

**优先级理由**: 确保"单一事实来源"的覆盖率和时效性。第一期聚焦平安人寿，从该公司官网公开信息披露栏目直接采集，验证端到端流程可行性。

**独立测试**: 针对平安人寿官网 (https://life.pingan.com/gongkaixinxipilu/baoxianchanpinmulujitiaokuan.jsp)，验证爬虫能正确解析产品目录并下载对应的 PDF 文件。

**验收场景 (Acceptance Scenarios)**:

1. **Given (已知)** 平安人寿官网更新了产品目录，**When (当)** "发现层"任务运行时，**Then (那么)** 系统能提取产品元数据（产品代码、产品名称、报备材料链接、发布时间）并建立索引条目。
2. **Given (已知)** 建立了新的索引条目，**When (当)** "采集层"任务运行时，**Then (那么)** 系统从平安人寿官网下载 PDF 文件，按产品代码去重存储。
3. **Given (已知)** 目标网站有反爬机制（如 WAF），**When (当)** 爬虫遇到 403/429 错误时，**Then (那么)** 系统自动执行指数退避 (exponential backoff) 并记录日志，而不是持续请求导致 IP 被封。

### 边界情况 (Edge Cases)

- **EC-001 - 加密/受保护的 PDF**: 如果下载的 PDF 有密码保护，系统尝试使用通用策略（如空密码）解密；若失败，标记为"处理失败"并告警。
- **EC-002 - 低质量/双栏扫描件**: 对于 OCR 置信度低或双栏排版的扫描件，系统必须使用支持版面分析 (Layout Analysis) 的解析引擎，防止文字跨栏乱序拼接；若无法处理，标记为需要人工审核。
- **EC-003 - 爬虫被封锁**: 严格遵守 QPS 限制。如果目标网站拦截，系统执行熔断机制，暂停该域名的采集任务 5 分钟以上。
- **EC-004 - 隐私数据避让**: 爬虫必须配置 URL 过滤器，**严禁**访问包含 `policy` (保单查询)、`user` (用户信息) 等路径的接口，防止触碰合规红线。

---

## 需求 (Requirements)

### 功能性需求 (Functional Requirements)

- **FR-001**: MCP工具 - 语义条款检索 (`search_policy_clause`)

系统必须提供 `search_policy_clause` MCP 工具，用于基于自然语言查询检索保险条款：

**工具签名**:
```python
def search_policy_clause(
    query: str,              # 自然语言查询
    company: Optional[str],  # 保险公司过滤（如"平安人寿"）
    product: Optional[str],  # 产品名称过滤（如"平安福耀年金保险"）
    category: Optional[str], # 条款类型过滤（Liability/Exclusion/Process/Definition）
    top_k: int = 5          # 返回结果数量
) -> List[ClauseResult]
```

**返回结构**:
```python
class ClauseResult:
    chunk_id: str                    # Chunk唯一ID
    content: str                     # 条款原文
    section_id: str                  # 条款编号（如"1.2.6"）
    section_title: str               # 条款标题
    similarity_score: float          # 相似度分数（0-1）
    source_reference: SourceRef      # 来源引用
    
class SourceRef:
    product_name: str                # 产品名称
    document_type: str               # 文档类型（产品条款/说明书）
    pdf_path: str                    # 原始PDF路径
    page_number: int                 # 页码
    download_url: str                # 原始下载链接
```

**验收标准**:
- 查询"这个保险保多久？"能返回"1.4 保险期间"条款
- 相似度阈值 > 0.7 的结果才返回
- 必须包含完整的 source_reference

**产品范围检索增强 (合并自原 FR-002a)**:
- 在 `search_policy_clause` 中新增可选参数 `product_code: Optional[str]`，并明确：
  - 指定 `product_code` 时，仅在该产品条款范围内检索
  - 指定 `company` 时，仅在该公司的产品中检索
  - 未指定时执行全局检索（向后兼容）
- 数据模型补充：PolicyChunk 必须包含 `company`, `product_code`, `product_name` 元数据字段
- 目标效果：在指定产品范围内的查询，Top-K 结果相似度显著提升（基线 0.26 → 0.7+）

---

- **FR-001a**: MCP工具 - 产品查询 (`lookup_product`)

系统必须提供 `lookup_product` MCP 工具,用于根据模糊的产品名称和公司名称查询精确的产品信息:

**工具签名**:
```python
def lookup_product(
    product_name: str,      # 产品名称(支持模糊匹配)
    company: Optional[str] = None  # 保险公司(可选)
) -> List[ProductInfo]
```

**返回结构**:
```python
class ProductInfo:
    product_id: str          # 产品ID
    product_code: str        # 产品代码
    product_name: str        # 完整产品名称
    company: str             # 保险公司名称
    category: str            # 产品类别
    publish_time: str        # 发布时间
```

**匹配规则**:
- 支持部分匹配: "盈添悦" → "平安盈添悦两全保险（分红型）"
- 支持公司过滤: company="平安人寿" 只返回平安的产品
- 返回Top-5最相关的产品

**验收标准**:
- 查询"盈添悦"能返回"平安盈添悦两全保险（分红型）"及其product_code
- 查询"平安 养老"能返回平安的所有养老年金产品
- 模糊匹配准确率 > 90%

---


- **FR-002**: MCP工具 - 免责条款核查 (`check_exclusion_risk`)

系统必须提供 `check_exclusion_risk` MCP 工具，专门用于核查特定场景是否属于保险免责范围：

**工具签名**:
```python
def check_exclusion_risk(
    scenario_description: str,   # 场景描述（如"酒后骑摩托车出事"）
    product_id: Optional[str],   # 产品ID（可选）
    strict_mode: bool = True     # 严格模式：仅返回明确的免责条款
) -> ExclusionCheckResult
```

**返回结构**:
```python
class ExclusionCheckResult:
    risk_detected: bool              # 是否检测到风险
    relevant_clauses: List[SourceRef] # 相关免责条款列表
    summary: str                     # 总结说明
    disclaimer: str                  # 免责声明
```

**特殊处理**:
- **强制过滤**: 只在 `category="Exclusion"` 的chunk中检索
- **关键词增强**: 自动扩展查询（如"酒驾" → ["酒后驾驶", "饮酒", "醉酒", "酒精"]）
- **安全免责声明**: 必须返回"本结果仅供参考，实际理赔以保险合同和公司审核为准"

**验收标准**:
  - **计算方法**: 召回率 = (返回的相关免责条款数) / (人工标注的所有相关免责条款数)
  - **Ground Truth来源**: 黄金测试集
    - **MVP阶段**: 使用6个代表性测试用例验证测试框架和核心功能
      - 基础查询: 3个 (身故、满期、现金价值)
      - 对比查询: 1个 (身故vs满期)
      - 免责查询: 2个 (酒驾、免责条款总览)
    - **完整版**: 后续扩展到50个标准问题 (基础20 + 对比15 + 专项15)
  - **相关性判断**: 人工标注每个问题对应的所有相关免责条款的section_id
  - **示例**: 问题"酒驾赔吗？"，Ground Truth为["2.1.3", "2.1.5"]，如果系统返回Top-5中包含这两个，则召回2/2=100%
- **不返回非免责类条款**:
  - **精确率要求**: 返回的Top-5结果中，category="Exclusion"的比例 ≥ 90%
  - **验证方法**: 自动化测试检查返回结果的category字段

---

- **FR-002a**: MCP工具 - 退保/减额交清逻辑提取 (`calculate_surrender_value_logic`)

系统必须提供 `calculate_surrender_value_logic` MCP 工具，用于提取退保或减额交清的计算逻辑和相关条款：

**工具签名**:
```python
def calculate_surrender_value_logic(
    product_id: str,             # 产品ID
    policy_year: Optional[int],  # 保单年度（可选）
    operation: str               # "surrender" (退保) 或 "reduced_paid_up" (减额交清)
) -> SurrenderLogicResult
```

**返回结构**:
```python
class SurrenderLogicResult:
    operation_name: str                  # 操作名称（中文）
    definition: str                      # 定义条款原文
    calculation_rules: List[str]         # 计算规则列表
    conditions: List[str]                # 前置条件
    consequences: List[str]              # 后果说明
    related_tables: List[TableChunk]     # 相关表格（如现金价值表）
    comparison_note: str                 # 对比说明（退保 vs 减额交清）
    source_references: List[SourceRef]   # 来源引用
```

**特殊处理**:
- **表格关联**: 自动关联相关的现金价值表、减额交清表
- **条款串联**: 同时返回"退保"和"减额交清"条款，便于对比
- **缺失提示**: 如果缺少具体金额表，明确提示"具体金额需查阅保单现金价值表"

**验收标准**:
- 查询"退保损失多少"能返回退保条款 + 现金价值计算规则
- 对比查询"退保和减额交清哪个划算"能同时返回两者条款
- 必须标注"本工具只提供计算逻辑，具体金额请参考保单"

---

- **FR-003**: 系统必须实现**分层爬虫架构**：
    - **发现层 (Discovery)**: 按保险公司维度，从目标保险公司官网"公开信息披露"栏目定期抓取产品元数据（产品代码、产品名称、报备材料链接）。第一期仅实现平安人寿官网 (https://life.pingan.com/gongkaixinxipilu/baoxianchanpinmulujitiaokuan.jsp)，IAC 与其他来源将于后续阶段实现。
    - **采集层 (Acquisition)**: 基于元数据，从保险公司官网下载 PDF 实体文件。
    
- **FR-004**: 系统必须实现高保真 **PDF 转 Markdown** 转换管道：
    - 支持**版面分析 (Layout Analysis)**，正确还原双栏排版文档的阅读顺序。
    - 具备**表格还原能力**，能将简单的费率表、利益演示表转换为 Markdown 表格，保持行列结构不崩坏。
    
**数据清洗与优化**（后处理步骤）:

在将Markdown文件索引到向量数据库之前，必须执行以下清洗步骤：

1. **脚注内联处理**:
   - **目标**: 将文档末尾的"脚注"（名词解释）直接插入到对应正文段落后
   - **示例**: 原文"被保险人⁽¹⁾应在..."，脚注"⁽¹⁾被保险人指受保险合同保障的人" → 优化为"被保险人（指受保险合同保障的人）应在..."
   - **效果**: 提升检索效果约50%（用户建议）
   - **实施**: 使用正则表达式匹配脚注标记，将定义插入主体段落

2. **噪音去除**:
   - 移除页眉、页脚（如"平安人寿"、"第X页"）
   - 移除水印文字
   - 移除无意义的分隔符（如"=========="）
   - 保留有意义的分隔符（如章节之间的"---"）

3. **格式标准化**:
   - 统一标题层级（确保 # 为产品名，## 为章节，### 为条款）
   - 统一列表格式（使用 `-` 或 `1.` 统一风格）
   - 标准化专有名词（如"被保險人" → "被保险人"）

4. **表格验证**:
   - 检查Markdown表格的行列完整性
   - 对于复杂表格，自动转换为JSON并保存在metadata
   - 标记表格所在的chunk（`is_table: true`）

**实施优先级**: 此步骤为 **P0 (最高优先级)**，因为：
- 直接影响检索质量（提升50%）
- 影响用户体验（答案的可读性）
- 符合Constitution 2.1（准确性高于一切）

---

- **FR-005**: 系统必须提供机制（CLI 或简易 UI），供人工审核员将文档转换质量标记为"已核验 (Verified)"或"已驳回 (Rejected)"。

- **FR-006**: 系统必须**仅**将标记为"已核验"的文档索引到向量数据库中。

- **FR-007**: 系统必须持久化存储原始 PDF 文件，并将解析后的文本块与原始文件关联，以确可追溯性。

- **FR-008**: 爬虫必须内置**合规限制**：全局QPS ≤ 0.8 req/s（每域名独立限制），并强制遵守目标站点的 Robots 协议（针对非强制披露目录）；当遇到 403/429 时，必须触发熔断并暂停该域名采集 ≥ 5 分钟。

- **FR-009**: 语义感知切片策略 (Semantic-Aware Chunking)

系统必须实现基于保险条款语义结构的切片策略，确保逻辑完整性：

- **切片方法**: 使用 Markdown 标题层级进行语义切分（MarkdownHeaderSplitter 或等价实现）：
  - **Level 1 (#)**: 保险产品名称（作为根节点）
  - **Level 2 (##)**: 大章节（如"1. 我们保什么、保多久"、"2. 我们不保什么"）
  - **Level 3 (###)**: 具体条款（如"1.2 保险责任"、"2.1 责任免除"）
  - **Level 4以下**: 子条款细节

- **切片原则**:
  1. **逻辑完整性**: 一个完整的条款（如"1.2.6 身故保险金"）不得跨多个chunk切分
  2. **上下文保留**: 每个chunk包含其父级标题作为上下文（如chunk包含"1.2.6"时，也应包含"1.2"和"1"的标题）
  3. **大小控制**: 
     - 目标chunk大小为 512-1024 tokens
     - **重叠策略**: 相邻chunk间保留20%重叠区域，具体规则：
       - 从前一个chunk的末尾取最后 100-200 tokens
       - 将这些tokens作为下一个chunk的开头上下文
       - 示例：Chunk A末尾为"...保险金给付条件为..."，Chunk B开头应包含"保险金给付条件为..."
     - 重叠的目的是保留上下文连贯性，防止关键信息在边界处断裂
     - **超出范围时**: 优先保持逻辑完整性，允许chunk最大扩展到2048 tokens；超过则在子条款层级强制切分
  4. **表格保护**: 表格必须作为独立chunk存储，或转换为JSON结构保存在metadata中（详见FR-009a）

- **实施要求**:
  - 使用 LangChain 的 `MarkdownHeaderTextSplitter` 或自实现等价逻辑
  - 保留原始Markdown的标题层级结构
  - 为每个chunk生成唯一的 `section_id`（如"1.2.6"）

---

- **FR-009a**: 表格完整性保护 (Table Integrity Protection)

系统必须严格保护保险条款中的表格结构（如减额交清表、费率表、利益演示表），防止行列关系崩坏：

- **强制规则**:
  1. **独立chunk存储**: 任何表格必须作为独立的chunk存储，不得与表格前后的文本合并切分
  2. **JSON备份**: 除Markdown表格格式外，同时将表格转换为JSON结构存储在chunk的 `table_data` metadata中
  3. **完整性标记**: 使用 `is_table: true` 标记表格chunk，便于检索时特殊处理

- **JSON结构示例**:
  ```json
  {
    "table_type": "减额交清对比表",
    "headers": ["保单年度", "减额后年金领取金额", "备注"],
    "rows": [
      ["第5年", "1000元/年", "从第6年开始领取"],
      ["第10年", "1500元/年", "终身领取"]
    ],
    "row_count": 2,
    "column_count": 3
  }
  ```
  
  **字段说明**:
  - `table_type`: 表格类型/标题（用于语义检索）
  - `headers`: 表头列表
  - `rows`: 数据行列表（每行为一个数组）
  - `row_count`: 行数（自动计算，用于完整性验证）
  - `column_count`: 列数（自动计算，用于完整性验证）

- **检索优化**: 表格chunk的语义检索应同时考虑：
  - 表格标题（如"减额交清对比表"）
  - 表格内的数值和关键词（如"减额"、"年金"）
  - 表格的上下文说明（表格前后的段落）

**合规性**: 此规则直接响应 Constitution 3.2 ("表格必须转换为标准的 Markdown 表格或保留语义的结构化文本，严禁破坏表格的行列对应关系")。

---

- **FR-010**: 元数据增强策略 (Metadata Enrichment)

系统必须为每个PolicyChunk提供丰富的元数据，以支持精准过滤和上下文重建：

- **必需元数据字段**:
  
  | 字段名 | 类型 | 说明 | 示例 |
  |--------|-----|------|------|
  | `section_id` | string | 条款编号 | "1.2.6" |
  | `section_title` | string | 条款标题 | "身故保险金" |
  | `category` | enum | 条款类型 | "Liability", "Exclusion", "Process", "Definition" |
  | `entity_role` | string | 主体角色 | "Insurer"（我们）, "Insured"（被保险人）, "Beneficiary"（受益人） |
  | `parent_section` | string | 父级章节 | "1.2" |
  | `level` | int | 标题层级 | 3 (对应 ###) |
  | `page_number` | int | 原PDF页码 | 12 |
  | `chunk_index` | int | 文档内顺序 | 15 |
  | `keywords` | list[string] | 关键词提取 | ["身故", "保险金", "受益人"] |
  | `is_table` | bool | 是否为表格 | true/false |
  | `table_data` | dict | 表格JSON | (见FR-009a) |

- **元数据提取规则**:
  - `category` 分类规则：
    - **Liability**: 包含"保险责任"、"我们给付"、"保险金"等关键词
    - **Exclusion**: 包含"责任免除"、"我们不承担"、"除外"等关键词
    - **Process**: 包含"申请"、"理赔"、"手续"、"流程"等关键词
    - **Definition**: 包含"本合同所称"、"定义"、"指"等关键词
  
  - `entity_role` 识别规则：
    - 段落中出现"我们"、"本公司"、"保险人" → Insurer
    - 段落中出现"被保险人"、"您的孩子" → Insured
    - 段落中出现"受益人"、"继承人" → Beneficiary

- **实施方式**:
  - 使用规则引擎 + NLP关键词提取
  - 在chunk生成时自动填充这些字段
  - 存储在ChromaDB的metadata中，支持过滤查询

---

- **FR-011**: 混合检索机制 (Hybrid Search)

系统必须实现语义检索与关键词检索的混合模式，以应对保险条款中的专有名词和精确匹配需求：

- **检索模式**:
  1. **Dense Vector Search (语义检索)**:
     - 使用 OpenAI text-embedding-3-small 生成向量
     - 基于 ChromaDB 的相似度搜索
     - 适用场景：模糊查询（如"不交钱了怎么办" → 匹配"效力中止"）
  
  2. **Sparse Vector Search (关键词检索)**:
     - 使用 BM25 算法进行精确词汇匹配
     - 适用场景：专有名词（如"189号"、"减额交清"、"犹豫期"）
  
  3. **Hybrid Fusion (混合融合)**:
     - 使用 Reciprocal Rank Fusion (RRF) 算法合并两种检索结果
     - 权重配置：语义检索 60%，关键词检索 40%（可调）

- **实施选项**:
  - **方案A**: 使用支持混合检索的向量数据库（Qdrant, Weaviate）
  - **方案B**: ChromaDB (语义) + 自实现BM25索引（如使用 `rank_bm25` 库）
  - **推荐**: 方案B（保持ChromaDB的简单性，独立管理BM25索引）

- **查询处理流程**:
  ```python
  def hybrid_search(query: str, top_k: int = 10) -> List[Chunk]:
      # 1. 语义检索
      semantic_results = chroma_db.similarity_search(query, k=top_k)
      
      # 2. 关键词检索
      bm25_results = bm25_index.search(query, k=top_k)
      
      # 3. 混合融合 (RRF)
      fused_results = reciprocal_rank_fusion(
          semantic_results, 
          bm25_results, 
          weights=[0.6, 0.4]
      )
      
      return fused_results[:top_k]
  ```

- **特殊优化**:
  - 对于包含数字的查询（如"1.2.1条款"），自动提升关键词检索权重至80%
    - **数字查询判断规则**: `\d+\.\d+\.\d+`（条款编号格式）或包含2个以上数字的查询
  - 对于问句类型查询（如"如何退保？"），提升语义检索权重至80%

- **索引管理策略**:
  1. **初始构建**: 首次索引时，遍历所有VERIFIED文档构建BM25索引
  2. **更新模式**:
     - **MVP阶段**: 批量全量重建（每次运行`index --rebuild`时）
     - **未来优化**: 增量更新（仅索引新增/更新的chunk）
  3. **持久化**: BM25索引保存为pickle文件（`data/vector_store/bm25_index.pkl`）
  4. **同步保证**: ChromaDB和BM25索引必须同步更新，防止不一致

**合规性**: 此功能直接响应 Constitution 4.1 ("混合检索：支持语义检索（Vector Search）与关键词检索（Keyword Search）的混合模式")。

### 关键实体 (Key Entities)

- **Product (产品)**: 代表逻辑上的保险产品（如："平安福耀年金保险"）。
  - 属性：`id`, `product_code` (产品代码，用于去重), `name`, `company`, `category`, `publish_time`, `created_at`。
  
- **PolicyDocument (条款文档)**: 代表单个 PDF 文件（如产品条款、费率表、说明书）。
  - 属性：`id`, `product_id`, `doc_type` (文档类型), `filename`, `local_path`, `url`, `file_hash`, `file_size`, `downloaded_at`, `verification_status` (PENDING, VERIFIED, REJECTED), `pdf_links` (所有PDF链接，用于来源追溯)。
  - **可追溯性**: `pdf_links` 字段以JSON格式保存产品的所有文档链接（如 `{"产品条款": "url1", "费率表": "url2"}`），确保符合Constitution 2.2原则。
  
- **PolicyChunk (条款切片)**: 用于向量索引的文本段，每个chunk代表一个逻辑完整的语义单元。
  - 核心属性：`id`, `document_id`, `content`, `embedding_vector`
  - 结构化元数据（新增/增强）：
    - `section_id`: 条款编号（如"1.2.6"）
    - `section_title`: 条款标题（如"身故保险金"）
    - `category`: 条款类型（Liability/Exclusion/Process/Definition）
    - `entity_role`: 主体角色（Insurer/Insured/Beneficiary）
    - `parent_section`: 父级章节编号（如"1.2"）
    - `level`: 标题层级（1-5）
    - `page_number`: 原PDF页码
    - `chunk_index`: 文档内顺序
    - `keywords`: 关键词提取
    - `is_table`: 是否为表格
    - `table_data`: 表格JSON结构（仅表格chunk）

## 成功标准 (Success Criteria)

### 可衡量的结果 (Measurable Outcomes)

- **SC-001**: MCP API 返回的数据 **100%** 关联至"已核验"的源文档。
- **SC-002**: 爬虫能在发布后 **24小时** 内成功识别并下载目标站点的新 PDF（取决于运行频率）。
- **SC-003**: 检索准确性（分层测试）

系统的检索能力必须通过以下分层测试：

**测试集**: "保险问答黄金数据集" (共50个问题，覆盖多种场景)

**分层标准**:

1. **基础查询测试** (20个问题):
   - **场景**: 单一明确的条款查询（如"保险期间多久？"、"如何申请理赔？"）
   - **标准**: Top-1 准确率 ≥ 90%
   - **示例问题**: "犹豫期是多少天？" → 应返回"5.1 犹豫期"条款

2. **对比查询测试** (15个问题):
   - **场景**: 需要同时检索多个相关条款进行对比（如"退保和减额交清的区别？"）
   - **标准**: Top-3 结果中包含所有相关条款的比例 ≥ 85%
   - **示例问题**: "减额交清和退保哪个划算？" → 应同时返回"6.4 减额交清"和"5.2 退保"

3. **专项检索测试** (15个问题):
   - **场景**: 针对特定类型条款的精确检索（主要是免责条款）
   - **标准**: 免责条款召回率 ≥ 95%，精确率 ≥ 90%
   - **示例问题**: "吸毒导致的意外赔吗？" → 必须返回免责条款，且不能返回非免责条款

**评估方法**:
- 人工标注正确答案（Ground Truth）
- 使用 MRR (Mean Reciprocal Rank) 和 NDCG@k 指标
- 每月重新评估，确保持续准确性

**失败处理**:
- 如果任一层级测试未达标，禁止上线
- 分析失败案例，优化切片策略或元数据
- **SC-004**: 系统能将已核验文档中的标准保单表格（如利益演示表）解析为可读 Markdown 表格，行列完整性达到 **100%**。

## 假设与依赖 (Assumptions & Dependencies)

- **假设**: 平安人寿官网"公开信息披露"栏目允许爬取，通过标准 HTTP 请求可访问公开文档库（无阻挡基本访问的复杂验证码）。
- **假设**: 保险条款主要是基于文本的 PDF，而非扫描图片（虽然提到了 OCR，但为了第一阶段效率，优先处理原生数字 PDF）。
- **假设**: 第一期仅实现平安人寿公司的爬虫，架构设计需考虑未来扩展到其他保险公司的可扩展性。
- **依赖**: 访问 **OpenAI API** (用于 `text-embedding-3-small` 模型) 进行向量化。
- **依赖**: **ChromaDB (Local)** 作为向量数据库，运行于本地环境或 Docker 中。
