# 第五阶段优化方案 - 需求质量检查清单

**目的**: 验证第五阶段（向量化索引）优化方案的需求质量，确保所有新增需求清晰、完整、可测试且数据模型一致

**创建日期**: 2025-11-21  
**检查类型**: 轻量级作者自检  
**关注重点**: 可测试性、数据模型一致性  
**覆盖范围**: FR-009/010/011, FR-001/002/002a, T020a/022a/023a/025a/028a

---

## 需求完整性 (Requirement Completeness)

### 切片策略 (FR-009)

- [ ] CHK001 - 是否明确定义了各级标题（L1/L2/L3/L4）对应的语义单元类型？[Completeness, Spec §FR-009]
- [ ] CHK002 - "逻辑完整性"原则是否提供了可验证的标准（如何判断一个条款是否完整）？[Clarity, Spec §FR-009]
- [ ] CHK003 - chunk大小目标（512-1024 tokens）是否定义了超出范围时的处理策略？[Gap, Spec §FR-009]
- [ ] CHK004 - "20%重叠"是否明确了重叠内容的选择规则（重叠哪些内容）？[Ambiguity, Spec §FR-009]

### 表格保护 (FR-009a)

- [ ] CHK005 - 是否定义了"表格"的识别标准（如何区分表格与非表格内容）？[Clarity, Spec §FR-009a]
- [ ] CHK006 - 表格JSON结构的"完整性标记"是否有验证方法？[Measurability, Spec §FR-009a]
- [ ] CHK007 - 是否定义了表格解析失败时的降级策略？[Exception Flow, Gap]
- [ ] CHK008 - "合并单元格"等复杂表格场景是否在需求中明确排除或包含？[Scope, Spec §FR-009a]

### 元数据增强 (FR-010)

- [ ] CHK009 - 11个元数据字段中，哪些是"必需"哪些是"可选"是否已明确定义？[Completeness, Spec §FR-010]
- [ ] CHK010 - category的4种分类规则是否覆盖所有可能的条款类型（无兜底分类时如何处理）？[Coverage, Spec §FR-010]
- [ ] CHK011 - entity_role的识别规则是否处理了多主体同时出现的情况？[Edge Case, Spec §FR-010]
- [ ] CHK012 - keywords提取方法（"规则引擎 + NLP"）是否定义了具体的技术选型或算法？[Ambiguity, Spec §FR-010]

### 混合检索 (FR-011)

- [ ] CHK013 - 权重配置（语义60% + BM25 40%）是否定义了调整权重的触发条件和决策逻辑？[Clarity, Spec §FR-011]
- [ ] CHK014 - "包含数字的查询"的判断规则是否明确（正则表达式或具体示例）？[Ambiguity, Spec §FR-011]
- [ ] CHK015 - 是否定义了BM25和语义检索结果数量不一致时的处理策略？[Exception Flow, Gap]
- [ ] CHK016 - RRF算法的参数k（默认60）是否有调优空间的说明？[Clarity, Spec §FR-011]

---

## 需求可测试性 (Testability & Acceptance Criteria)

### MCP工具 - search_policy_clause (FR-001)

- [ ] CHK017 - 验收标准"查询'这个保险保多久？'能返回'1.4 保险期间'条款"是否可以自动化测试？[Measurability, Spec §FR-001]
- [ ] CHK018 - "相似度阈值 > 0.7"的验收标准是否明确了如何构建测试用例（覆盖边界值0.69, 0.7, 0.71）？[Testability, Spec §FR-001]
- [ ] CHK019 - "必须包含完整的 source_reference"是否定义了"完整"的标准（哪些字段非空）？[Clarity, Spec §FR-001]
- [ ] CHK020 - 是否定义了当没有满足阈值的结果时的返回行为（空列表还是错误）？[Gap, Spec §FR-001]

### MCP工具 - check_exclusion_risk (FR-002)

- [ ] CHK021 - "免责条款召回率 > 95%"是否定义了如何计算召回率的分母（总免责条款数）？[Measurability, Spec §FR-002]
- [ ] CHK022 - "不返回非免责类条款"是否等同于精确率 = 100%？如果不是，精确率要求是多少？[Ambiguity, Spec §FR-002]
- [ ] CHK023 - 关键词扩展规则（"酒驾" → ["酒后驾驶", "饮酒", "醉酒", "酒精"]）是否有完整的映射表或生成算法？[Completeness, Spec §FR-002]
- [ ] CHK024 - 是否定义了安全免责声明的具体文本（是否可变）？[Clarity, Spec §FR-002]

### MCP工具 - calculate_surrender_value_logic (FR-002a)

- [ ] CHK025 - 验收标准"同时返回退保和减额交清条款"是否明确了"同时"的优先级（如果只找到一个怎么办）？[Clarity, Spec §FR-002a]
- [ ] CHK026 - "具体金额需查阅保单"的提示是否有标准化的文本模板？[Clarity, Spec §FR-002a]
- [ ] CHK027 - related_tables的关联逻辑是否有明确的匹配规则（如何判断表格"相关"）？[Ambiguity, Spec §FR-002a]

### 分层测试标准 (SC-003)

- [ ] CHK028 - 50个问题的黄金测试集是否定义了具体的问题分布（各保险产品、条款类型的覆盖率）？[Completeness, Spec §SC-003]
- [ ] CHK029 - "Top-1准确率 ≥ 90%"是否定义了当多个条款同样相关时的判定标准？[Ambiguity, Spec §SC-003]
- [ ] CHK030 - 是否定义了测试失败后的改进流程（重新标注、优化策略的迭代周期）？[Process, Gap]

---

## 数据模型一致性 (Data Model Consistency)

### PolicyChunk字段一致性

- [ ] CHK031 - spec.md §FR-010中定义的11个元数据字段是否与data-model.md中PolicyChunk的字段列表完全一致？[Consistency, Spec §FR-010 vs Data-Model]
- [ ] CHK032 - data-model.md中PolicyChunk的字段是否与models.py中PolicyChunk类的属性完全一致（字段名、类型、必需性）？[Consistency, Data-Model vs Code]
- [ ] CHK033 - category枚举的4个值（Liability/Exclusion/Process/Definition）在spec.md、data-model.md、models.py三处是否完全一致？[Consistency]
- [ ] CHK034 - entity_role枚举的3个值（Insurer/Insured/Beneficiary）在三处是否完全一致？[Consistency]

### 类型定义一致性

- [ ] CHK035 - spec.md中定义的ClauseResult结构是否在models.py中有对应的Pydantic模型？[Completeness, Gap]
- [ ] CHK036 - spec.md中定义的SourceRef结构是否在models.py中有对应的Pydantic模型？[Completeness, Gap]
- [ ] CHK037 - spec.md中定义的TableData结构（JSON格式）是否与models.py中的TableData类匹配？[Consistency, Spec §FR-009a vs Code]

### ChromaDB Schema一致性

- [ ] CHK038 - data-model.md中ChromaDB Metadata Schema是否包含了PolicyChunk的所有需要存储的字段？[Completeness, Data-Model]
- [ ] CHK039 - models.py中PolicyChunk.to_chroma_metadata()方法返回的字段是否与ChromaDB Schema定义一致？[Consistency, Code vs Data-Model]
- [ ] CHK040 - ChromaDB metadata中的字段限制（不支持嵌套对象）是否在所有序列化逻辑中都被考虑？[Consistency, Data-Model]

---

## 任务需求完整性 (Task Requirements Completeness)

### T020a - Markdown后处理

- [ ] CHK041 - 脚注内联、噪音去除、格式标准化、表格验证4个子任务是否都有明确的输入输出定义？[Completeness, Tasks §T020a]
- [ ] CHK042 - 是否定义了Markdown增强模块（4个子模块）与后处理模块的集成接口？[Gap, Tasks §T020a]
- [ ] CHK043 - "提升50%检索效果"的声明是否有验证方法（如何测量提升幅度）？[Measurability, Tasks §T020a]

### T022a - 混合检索

- [ ] CHK044 - BM25Index和HybridRetriever的接口定义是否与FR-011中的需求一致？[Consistency, Tasks §T022a vs Spec §FR-011]
- [ ] CHK045 - 是否定义了BM25索引的更新策略（增量更新 vs 全量重建）？[Gap, Tasks §T022a]

### T023a - 表格独立Chunk

- [ ] CHK046 - SemanticChunker的表格识别逻辑是否与FR-009a中的要求一致？[Consistency, Tasks §T023a vs Spec §FR-009a]
- [ ] CHK047 - 表格与文本chunk的合并排序逻辑是否有明确的算法描述？[Clarity, Tasks §T023a]

### T025a - MCP工具重设计

- [ ] CHK048 - 3个MCP工具的实现是否与FR-001/002/002a中的工具签名和返回结构完全一致？[Consistency, Tasks §T025a vs Spec]
- [ ] CHK049 - 是否定义了MCP工具的错误处理和超时策略？[Gap, Tasks §T025a]

### T028a - 黄金测试集

- [ ] CHK050 - 黄金测试集的50个问题是否与SC-003中定义的分层标准（20/15/15）一致？[Consistency, Tasks §T028a vs Spec §SC-003]
- [ ] CHK051 - 是否定义了黄金测试集的维护流程（如何添加新问题、更新Ground Truth）？[Process, Gap]

---

## 边缘情况与异常流 (Edge Cases & Exception Flows)

### 数据质量问题

- [ ] CHK052 - 是否定义了Markdown文件包含乱码或格式错误时的处理策略？[Exception Flow, Gap]
- [ ] CHK053 - 是否定义了无法提取section_id时的降级方案（如何生成替代ID）？[Exception Flow, Gap]
- [ ] CHK054 - 是否定义了category分类规则无法匹配任何类型时的兜底策略？[Edge Case, Gap]

### 检索失败场景

- [ ] CHK055 - 是否定义了BM25索引为空或损坏时的混合检索降级方案？[Exception Flow, Gap]
- [ ] CHK056 - 是否定义了OpenAI embedding API失败时的重试和回退策略？[Exception Flow, Gap]
- [ ] CHK057 - 是否定义了ChromaDB查询超时时的错误处理？[Exception Flow, Gap]

### 性能边界

- [ ] CHK058 - 是否定义了单个chunk的最大大小限制（防止超过embedding API限制）？[Edge Case, Gap]
- [ ] CHK059 - 是否定义了混合检索的最大返回结果数限制？[Edge Case, Spec §FR-011]
- [ ] CHK060 - 是否定义了黄金测试集执行时间的合理范围（防止测试超时）？[Non-Functional, Gap]

---

## 总结

**检查项总数**: 60  
**重点关注**: 可测试性（17项）、数据模型一致性（10项）  
**覆盖范围**: 
- 新增功能需求: FR-009/010/011, FR-001/002/002a (27项)
- 新增任务: T020a/022a/023a/025a/028a (11项)
- 数据模型一致性: spec.md ↔ data-model.md ↔ models.py (10项)
- 边缘情况与异常流: (12项)

**下一步行动**: 
1. 逐项检查并标记完成状态
2. 对发现的gap和ambiguity，在spec.md或data-model.md中补充说明
3. 对consistency问题，修正不一致的定义
4. 完成所有检查后，方可进入第五阶段代码实施

