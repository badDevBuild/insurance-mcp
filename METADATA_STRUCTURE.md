# 元数据结构文档

**生成时间**: 2025-11-24  
**数据来源**: ChromaDB `insurance_policy_chunks` Collection

---

## 📋 元数据字段说明

当前系统从PDF解析后存储在ChromaDB中的元数据包含 **12个字段**：

### 1. 产品相关字段 (P0+增强)

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `company` | string | 保险公司名称 | "平安人寿" |
| `product_code` | string | 产品代码 | "2124" |
| `product_name` | string | 产品完整名称 | "平安福耀年金保险（分红型）" |
| `doc_type` | string | 文档类型 | "产品条款", "产品费率表", "产品说明书" |

**作用**: 支持产品范围检索（T035）和产品查询工具（T037）

---

### 2. 文档结构字段

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `document_id` | string | 文档唯一标识符 (UUID) | "067afcfc-e8eb-43d2-994a-66474dcd65e5" |
| `chunk_index` | integer | 当前chunk在文档中的序号 | 0, 1, 2, ... |
| `section_title` | string | 章节标题 | "保险责任", "责任免除" (可能为空) |
| `level` | integer | 章节层级 | 1, 2, 3 |

**作用**: 
- `document_id`: 关联同一文档的所有chunks
- `chunk_index`: 确定chunks在原文中的顺序
- `section_title`: 提供上下文信息，帮助用户理解结果来源
- `level`: 表示章节的层级结构

---

### 3. 语义分析字段

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `category` | string | 条款类别 | "Liability" (保险责任), "Process" (流程), "Definition" (定义), "Exclusion" (免责) |
| `entity_role` | string | 涉及的实体角色 | "Insured" (被保险人), "Insurer" (保险人), "Beneficiary" (受益人) |
| `keywords` | string | 关键词（逗号分隔） | "红,利,,,合,同,,,保,单,,,被,保,险,人,,,保,险" |

**作用**:
- `category`: 帮助用户过滤特定类型的条款
- `entity_role`: 识别条款涉及的主体
- `keywords`: 辅助关键词搜索和分析

**注意**: 元数据提取器的准确率约79%（见VALIDATION_REPORT.md），后续可优化

---

### 4. 内容特征字段

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `is_table` | boolean | 是否为表格内容 | true, false |

**作用**: 区分表格和文本内容，便于不同的展示逻辑

---

## 📊 实际数据示例

### 示例 1: 产品条款Chunk

```json
{
  "category": "Process",
  "chunk_index": 0,
  "company": "平安人寿",
  "doc_type": "产品条款",
  "document_id": "067afcfc-e8eb-43d2-994a-66474dcd65e5",
  "entity_role": "Insured",
  "is_table": false,
  "keywords": "本,合,同,,,保,险,费,,,被,保,险,人,,,保,险,金,,,保,险",
  "level": 1,
  "product_code": "2124",
  "product_name": "平安福耀年金保险（分红型）",
  "section_title": ""
}
```

**文档内容**:
> 平安人寿〔2025〕年金保险 163 号  
> 平安福耀年金保险（分红型）  
> 阅读指引...

---

### 示例 2: 产品费率表Chunk

```json
{
  "category": "Liability",
  "chunk_index": 0,
  "company": "平安人寿",
  "doc_type": "产品费率表",
  "document_id": "ef1d300f-c098-47f7-a869-72a2be42e6c3",
  "is_table": false,
  "keywords": "2,8,,,2,7,,,2,6,,,2,5,,,7,6",
  "level": 1,
  "product_code": "2124",
  "product_name": "平安福耀年金保险（分红型）",
  "section_title": ""
}
```

**文档内容**:
> 《平安福耀年金保险（分红型）》基本保险金额表...

**注意**: 费率表chunk没有 `entity_role` 字段（因为表格通常不涉及特定角色）

---

### 示例 3: 产品说明书Chunk

```json
{
  "category": "Liability",
  "chunk_index": 0,
  "company": "平安人寿",
  "doc_type": "产品说明书",
  "document_id": "024f311e-451c-4e0e-89cb-8a3995186231",
  "entity_role": "Insured",
  "is_table": false,
  "keywords": "红,利,,,合,同,,,保,单,,,被,保,险,人,,,保,险",
  "level": 1,
  "product_code": "2124",
  "product_name": "平安福耀年金保险（分红型）",
  "section_title": ""
}
```

**文档内容**:
> 平安福耀年金保险（分红型）产品说明书  
> 在本说明书中，"您"指投保人...

---

## 🔍 元数据使用场景

### 1. 产品范围检索 (FR-001, T035)

```python
# 搜索特定产品的条款
results = store.search(
    query_vector=embedding,
    n_results=5,
    where={"product_code": "2124"}
)
```

### 2. 文档类型过滤

```python
# 只搜索产品条款，不包括费率表
results = store.search(
    query_vector=embedding,
    n_results=5,
    where={"doc_type": "产品条款"}
)
```

### 3. 条款类别过滤

```python
# 只查找免责条款
results = store.search(
    query_vector=embedding,
    n_results=5,
    where={"category": "Exclusion"}
)
```

### 4. 组合过滤

```python
# 查找特定产品的保险责任条款
results = store.search(
    query_vector=embedding,
    n_results=5,
    where={
        "product_code": "2124",
        "category": "Liability"
    }
)
```

---

## 📐 数据模型定义

元数据结构在代码中的定义位置：

### PolicyChunk 模型
**文件**: `src/common/models.py` (L152-207)

```python
class PolicyChunk(BaseModel):
    """保险条款chunk（语义单元）"""
    
    # 基本字段
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    content: str
    chunk_index: int
    
    # 产品上下文（P0+增强）
    company: str
    product_code: str
    product_name: str
    doc_type: str
    
    # 文档结构
    section_title: Optional[str] = None
    level: int = 1
    
    # 语义元数据
    category: Optional[str] = None
    entity_role: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    
    # 内容特征
    is_table: bool = False
    
    # 向量
    embedding_vector: Optional[List[float]] = None
    
    def to_chroma_metadata(self) -> Dict[str, Any]:
        """转换为ChromaDB元数据格式"""
        # ChromaDB要求所有值为基本类型
        return {
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "company": self.company,
            "product_code": self.product_code,
            "product_name": self.product_name,
            "doc_type": self.doc_type,
            "section_title": self.section_title or "",
            "level": self.level,
            "category": self.category or "",
            "entity_role": self.entity_role or "",
            "keywords": ",".join(self.keywords),
            "is_table": self.is_table
        }
```

---

## 📈 当前统计信息

- **总Chunks数**: 8
- **元数据字段数**: 12
- **产品数**: 1 (平安福耀年金保险)
- **文档类型数**: 3 (产品条款、产品费率表、产品说明书)

---

## 🔄 元数据生成流程

```
PDF文件
  ↓
[PolicyDocumentExtractor]  → 解析PDF结构
  ↓
[MetadataExtractor]        → 提取语义元数据 (category, entity_role, keywords)
  ↓
[BGEEmbedder]              → 生成embedding向量
  ↓
[PolicyIndexer]            → 组装完整的PolicyChunk对象
  ↓
[ChromaDBStore]            → 存储到向量数据库
```

**关键文件**:
1. `src/indexing/metadata_extractor.py` - 语义元数据提取
2. `src/indexing/indexer.py` - 索引协调器
3. `src/indexing/vector_store/chroma.py` - ChromaDB存储

---

## ⚠️ 已知限制

1. **元数据提取准确率**: 约79% (见VALIDATION_REPORT.md)
   - `category` 分类可能不完全准确
   - `entity_role` 识别有时会遗漏
   - 这不影响检索核心功能，只是辅助过滤

2. **keywords格式**: 使用逗号分隔的字符串，不是数组
   - 原因: ChromaDB要求元数据值为基本类型

3. **section_title缺失**: 部分chunk的 `section_title` 为空
   - 原因: 某些文档（如封面页）没有明确的章节标题

---

## 🚀 未来优化方向

1. **提升元数据提取准确率**
   - 优化关键词权重
   - 引入更多训练数据
   - 考虑使用LLM辅助分类

2. **增加更多元数据字段**
   - `effective_date`: 生效日期
   - `clause_number`: 条款编号 (如"第3.1条")
   - `importance_score`: 重要性评分

3. **支持更复杂的查询**
   - 日期范围查询
   - 正则表达式匹配
   - 全文检索集成

---

**文档维护**: 每次元数据结构变更时应更新此文档
