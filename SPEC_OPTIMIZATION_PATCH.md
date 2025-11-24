# spec.md 优化补丁

## 🎯 使用说明

本文件包含需要添加或修改到 `specs/001-insurance-mcp-core/spec.md` 中的内容片段。
请根据标记的位置，将对应内容合并到spec.md中。

---

## 补丁 1: 新增 FR-009 - 语义感知切片策略

**位置**: 在 `FR-008` 之后插入

```markdown
### FR-009: 语义感知切片策略 (Semantic-Aware Chunking)

系统必须实现基于保险条款语义结构的切片策略，确保逻辑完整性：

- **切片方法**: 使用 Markdown 标题层级进行语义切分（MarkdownHeaderSplitter 或等价实现）：
  - **Level 1 (#)**: 保险产品名称（作为根节点）
  - **Level 2 (##)**: 大章节（如"1. 我们保什么、保多久"、"2. 我们不保什么"）
  - **Level 3 (###)**: 具体条款（如"1.2 保险责任"、"2.1 责任免除"）
  - **Level 4以下**: 子条款细节

- **切片原则**:
  1. **逻辑完整性**: 一个完整的条款（如"1.2.6 身故保险金"）不得跨多个chunk切分
  2. **上下文保留**: 每个chunk包含其父级标题作为上下文（如chunk包含"1.2.6"时，也应包含"1.2"和"1"的标题）
  3. **大小控制**: 目标chunk大小为 512-1024 tokens，允许20%重叠以保留边界上下文
  4. **表格保护**: 表格必须作为独立chunk存储，或转换为JSON结构保存在metadata中（详见FR-009a）

- **实施要求**:
  - 使用 LangChain 的 `MarkdownHeaderTextSplitter` 或自实现等价逻辑
  - 保留原始Markdown的标题层级结构
  - 为每个chunk生成唯一的 `section_id`（如"1.2.6"）
```

---

## 补丁 2: 新增 FR-009a - 表格完整性保护

**位置**: 在 `FR-009` 之后插入

```markdown
### FR-009a: 表格完整性保护 (Table Integrity Protection)

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
    ]
  }
  ```

- **检索优化**: 表格chunk的语义检索应同时考虑：
  - 表格标题（如"减额交清对比表"）
  - 表格内的数值和关键词（如"减额"、"年金"）
  - 表格的上下文说明（表格前后的段落）

**合规性**: 此规则直接响应 Constitution 3.2 ("表格必须转换为标准的 Markdown 表格或保留语义的结构化文本，严禁破坏表格的行列对应关系")。
```

---

## 补丁 3: 新增 FR-010 - 元数据增强策略

**位置**: 在 `FR-009a` 之后插入

```markdown
### FR-010: 元数据增强策略 (Metadata Enrichment)

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
```

---

## 补丁 4: 新增 FR-011 - 混合检索机制

**位置**: 在 `FR-010` 之后插入

```markdown
### FR-011: 混合检索机制 (Hybrid Search)

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
  - 对于问句类型查询（如"如何退保？"），提升语义检索权重至80%

**合规性**: 此功能直接响应 Constitution 4.1 ("混合检索：支持语义检索（Vector Search）与关键词检索（Keyword Search）的混合模式")。
```

---

## 补丁 5: 重新设计 MCP 工具定义

**位置**: 替换 `spec.md` 中的 `FR-001` 和 `FR-002`

```markdown
### FR-001: MCP工具 - 语义条款检索 (search_policy_clause)

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

---

### FR-002: MCP工具 - 免责条款核查 (check_exclusion_risk)

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
    is_excluded: bool                    # 是否明确免责
    confidence: float                    # 置信度（0-1）
    matched_clauses: List[ClauseResult]  # 匹配的免责条款
    risk_summary: str                    # 风险总结
    disclaimer: str                      # 免责声明（必需）
```

**特殊处理**:
- **强制过滤**: 只在 `category="Exclusion"` 的chunk中检索
- **关键词增强**: 自动扩展查询（如"酒驾" → ["酒后驾驶", "饮酒", "醉酒", "酒精"]）
- **安全免责声明**: 必须返回"本结果仅供参考，实际理赔以保险合同和公司审核为准"

**验收标准**:
- 查询"酒驾出事赔吗？"能准确返回酒驾相关免责条款
- 免责条款召回率 > 95%
- 不返回非免责类条款

---

### FR-002a: MCP工具 - 退保/减额交清逻辑提取 (calculate_surrender_value_logic)

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

**用户场景示例**:
```
用户: "我想把这个保险做减额交清，具体怎么算？"

Agent调用: calculate_surrender_value_logic(
    product_id="平安福耀年金保险",
    operation="reduced_paid_up"
)

返回:
- 定义: "减额交清是指..."（6.4条款原文）
- 计算规则: ["在扣除所有未交保费和债务后，以当时的现金价值作为一次性趸交保费..."]
- 后果: ["保额相应减少", "合同继续有效", "无需继续交费"]
- 相关表格: [减额交清对比表的JSON数据]
- 对比说明: "退保是一次性拿回现金价值但失去保障；减额交清是不拿钱、不交钱，但保障缩水。"
```
```

---

## 补丁 6: 扩展成功标准 (Success Criteria)

**位置**: 替换 `spec.md` 中的 `SC-003`

```markdown
### SC-003: 检索准确性（分层测试）

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
```

---

## 补丁 7: 新增数据清洗要求

**位置**: 在 `FR-004` 的"PDF转Markdown转换管道"部分添加

```markdown
### FR-004: PDF 转 Markdown 转换管道（扩展）

（保留原有内容，并在最后添加以下段落）

**数据清洗与优化**（后处理步骤）:

在将Markdown文件索引到向量数据库之前，必须执行以下清洗步骤：

1. **脚注内联处理**:
   - **目标**: 将文档末尾的"脚注"（名词解释）直接插入到对应正文段落后
   - **示例**: 原文"被保险人⁽¹⁾应在..."，脚注"⁽¹⁾被保险人指受保险合同保障的人"
     → 优化为"被保险人（指受保险合同保障的人）应在..."
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
```

---

## 补丁应用检查清单

使用以下清单确保补丁正确应用：

- [ ] FR-009 已添加到 spec.md
- [ ] FR-009a 已添加到 spec.md
- [ ] FR-010 已添加到 spec.md
- [ ] FR-011 已添加到 spec.md
- [ ] FR-001 已替换为新的工具定义
- [ ] FR-002 已替换为新的工具定义
- [ ] FR-002a 已添加（新工具）
- [ ] SC-003 已替换为分层测试标准
- [ ] FR-004 已添加数据清洗要求
- [ ] 所有补丁与 Constitution 原则一致性已验证

---

**应用后验证步骤**:

1. 运行 `/speckit.analyze` 确认CRITICAL问题已解决
2. 检查是否有新的不一致性引入
3. 更新 quickstart.md 以反映新的MCP工具用法

