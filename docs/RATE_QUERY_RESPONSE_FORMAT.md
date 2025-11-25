# 费率查询返回内容格式文档

**创建时间**: 2025-11-25  
**相关需求**: FR-001, FR-009

---

## 📋 概述

本文档说明当客户端询问费率相关问题时，MCP服务器返回的内容格式和结构。

---

## 🔍 实际测试结果

### 测试场景1: 查询"30岁保费多少"

**查询**: `search_policy_clause(query="30岁保费多少", company="平安人寿")`

**返回结果**:

```json
{
  "chunk_id": "596fd0a4-9b26-445e-8ed8-61b176910980",
  "content": "[章节: 投保举例]\n\n王女士（ 40 周岁）为自己投保平安福耀年金保险（分红型）...",
  "section_id": "",
  "section_title": "投保举例",
  "similarity_score": 0.3566,
  "source_reference": {
    "product_name": "平安福耀年金保险（分红型）",
    "document_type": "产品条款",
    "pdf_path": "未知文件",
    "page_number": 0,
    "download_url": ""
  }
}
```

**问题**:
- ⚠️ 返回的是"投保举例"章节，而非费率表
- ⚠️ 内容包含数值但格式混乱（可能是PDF解析问题）
- ⚠️ `document_type`显示为"产品条款"而非"产品费率表"

---

### 测试场景2: 查询"基本保险金额表"

**查询**: `search_policy_clause(query="基本保险金额表", company="平安人寿", doc_type="产品费率表")`

**返回结果**:

```json
{
  "chunk_id": "...",
  "content": "[章节: 《平安安盈年金保险（分红型）》基本保险金额表 （每份）]\n\n单位：人民币元\n\n[费率表: e4f73d3b-6a1b-4662-9410-41fa421b27c2]\n",
  "section_id": "",
  "section_title": "《平安安盈年金保险（分红型）》基本保险金额表 （每份）",
  "similarity_score": 0.4996,
  "source_reference": {
    "product_name": "平安安盈年金保险（分红型）",
    "document_type": "产品费率表",
    "pdf_path": "未知文件",
    "page_number": 0,
    "download_url": ""
  }
}
```

**关键发现**:
- ✅ 返回了费率表chunk
- ✅ `content`字段包含费率表引用标记：`[费率表: e4f73d3b-6a1b-4662-9410-41fa421b27c2]`
- ⚠️ **ClauseResult没有`table_refs`字段**，客户端无法直接获取费率表UUID
- ⚠️ 客户端只能看到引用标记，无法访问CSV文件

---

### 测试场景3: 查询费率表（包含完整Markdown表格）

**部分费率表chunk包含完整Markdown表格**（未被正确分类为费率表）：

```markdown
[章节: 《平安颐享天年养老年金保险（分红型）》基本保险金额表 （每万元趸交或年交保费）]

男性

| 开始领取时间.交费期间 投保年龄 | 首个保单周年日.趸交 | 首个保单周年日.3 年交 | ... |
| --- | --- | --- | --- |
| 50 |  |  | 176 | 156 | ... |
| 51 |  |  | 170 | 147 | ... |
...
```

**说明**: 这些chunk的`table_refs`为`N/A`，说明表格没有被分离，而是直接包含在chunk中。

---

## 📊 ClauseResult结构分析

### 当前ClauseResult字段

```python
class ClauseResult(BaseModel):
    chunk_id: str                    # Chunk唯一ID
    content: str                     # 条款原文（包含费率表引用标记）
    section_id: str                  # 条款编号
    section_title: str               # 条款标题
    similarity_score: float          # 相似度分数（0-1）
    source_reference: SourceRef      # 来源引用
```

### 缺失的字段

- ❌ **`table_refs`**: 费率表UUID列表（在PolicyChunk中存在，但ClauseResult中没有）
- ❌ **`doc_type`**: 文档类型（在metadata中存在，但ClauseResult中没有）

---

## 🔄 当前返回流程

### 1. 检索阶段

```
用户查询 "30岁保费多少"
    ↓
MCP服务器执行检索（不指定doc_type）
    ↓
ChromaDB返回chunks（可能包含条款、说明书、费率表）
    ↓
按相似度排序
```

### 2. 结果转换阶段

```
ChromaDB结果
    ↓
提取metadata（包含table_refs）
    ↓
构建ClauseResult
    ⚠️ table_refs信息丢失！
    ↓
返回给客户端
```

### 3. 客户端接收

```json
{
  "content": "[费率表: e4f73d3b-6a1b-4662-9410-41fa421b27c2]",
  // ⚠️ 客户端无法直接获取table_refs列表
  // ⚠️ 只能从content中解析UUID（不可靠）
}
```

---

## ⚠️ 当前问题

### 问题1: table_refs信息丢失

**现状**:
- PolicyChunk的metadata中包含`table_refs`字段
- 但ClauseResult中没有`table_refs`字段
- 客户端无法直接获取费率表UUID列表

**影响**:
- 客户端无法直接访问CSV文件
- 只能从`content`中解析`[费率表: UUID]`标记（不可靠）

### 问题2: doc_type信息缺失

**现状**:
- ChromaDB metadata中包含`doc_type`
- 但ClauseResult中没有`doc_type`字段
- 客户端无法知道返回的是哪种文档类型

**影响**:
- 客户端无法判断结果是否来自费率表
- 无法根据文档类型调整展示方式

### 问题3: 费率表查询不准确

**现状**:
- 查询"30岁保费多少"返回的是"投保举例"而非费率表
- 相似度较低（0.35），说明检索不够精准

**原因**:
- 费率表数据不向量化，只有说明文字被索引
- 查询关键词与费率表chunk的语义匹配度低

---

## 💡 改进建议

### 建议1: 扩展ClauseResult结构（高优先级）

**添加字段**:
```python
class ClauseResult(BaseModel):
    # ... 现有字段 ...
    table_refs: List[str] = Field(default_factory=list, description="关联的费率表UUID列表")
    doc_type: str = Field(default="产品条款", description="文档类型")
```

**实施位置**: `src/common/models.py`

### 建议2: 更新MCP工具返回逻辑

**修改位置**: `src/mcp_server/tools/search_policy_clause.py`

```python
clause_result = ClauseResult(
    chunk_id=res['id'],
    content=res['document'],
    section_id=metadata.get('section_id', ''),
    section_title=metadata.get('section_title', ''),
    similarity_score=similarity,
    source_reference=self._format_source_ref(res),
    # ✅ 新增字段
    table_refs=metadata.get('table_refs', '').split(',') if metadata.get('table_refs') else [],
    doc_type=metadata.get('doc_type', '产品条款')
)
```

### 建议3: 提供费率表访问工具（中优先级）

**新增MCP工具**: `get_rate_table(table_id: str) -> RateTableData`

**功能**:
- 根据table_id读取CSV文件
- 返回结构化数据（JSON格式）
- 支持简单的过滤和查询

---

## 📝 当前返回内容示例

### 示例1: 费率表chunk（已分离）

**ClauseResult**:
```json
{
  "chunk_id": "abc123",
  "content": "[章节: 基本保险金额表]\n\n单位：人民币元\n\n[费率表: e4f73d3b-6a1b-4662-9410-41fa421b27c2]\n\n注：本产品交费方式为趸交或年交，每份趸交或年交保费 1000 元。",
  "section_title": "基本保险金额表",
  "similarity_score": 0.4996,
  "source_reference": {
    "product_name": "平安安盈年金保险（分红型）",
    "document_type": "产品费率表"
  }
}
```

**客户端看到的内容**:
- ✅ 章节标题和说明文字
- ✅ 费率表引用标记（但无法直接访问CSV）
- ⚠️ 无法获取table_refs列表

### 示例2: 费率表chunk（未分离，包含完整表格）

**ClauseResult**:
```json
{
  "chunk_id": "def456",
  "content": "[章节: 基本保险金额表]\n\n| 年龄 | 保费 | 费率 |\n| --- | --- | --- |\n| 30 | 1000 | 0.01 |\n| 31 | 1050 | 0.0105 |\n...",
  "section_title": "基本保险金额表",
  "similarity_score": 0.4690,
  "source_reference": {
    "product_name": "平安颐享天年养老年金保险（分红型）",
    "document_type": "产品费率表"
  }
}
```

**客户端看到的内容**:
- ✅ 完整的Markdown表格
- ✅ 可以直接展示表格数据
- ⚠️ 表格数据已向量化（可能影响检索质量）

---

## ✅ 总结

### 当前状态

1. **返回格式**: ClauseResult包含`content`、`section_title`、`similarity_score`、`source_reference`
2. **费率表引用**: 在`content`中以`[费率表: UUID]`标记形式存在
3. **缺失信息**: `table_refs`和`doc_type`字段未包含在ClauseResult中

### 客户端可获取的信息

- ✅ 章节标题和说明文字
- ✅ 费率表引用标记（需解析）
- ✅ 产品名称和文档类型（通过source_reference）
- ❌ 费率表UUID列表（无法直接获取）
- ❌ CSV文件路径（无法直接访问）

### 改进方向

1. **扩展ClauseResult**: 添加`table_refs`和`doc_type`字段
2. **提供费率表工具**: 新增`get_rate_table`工具供客户端查询CSV数据
3. **优化检索**: 改进费率表查询的准确性

---

**文档维护者**: Insurance MCP Team  
**最后更新**: 2025-11-25

