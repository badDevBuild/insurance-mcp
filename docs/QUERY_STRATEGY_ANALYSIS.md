# 查询策略分析报告

**生成时间**: 2025-11-25  
**分析范围**: 测试用例、检索逻辑、数据索引情况

---

## 📊 数据索引情况

### 数据库中的文档类型分布

| 文档类型 | VERIFIED | PENDING | 总计 |
|---------|----------|---------|------|
| **产品条款** | 5 | 16 | 21 |
| **产品说明书** | 20 | 0 | 20 |
| **产品费率表** | 20 | 0 | 20 |
| **总计** | 45 | 16 | 61 |

### ChromaDB中已索引的文档类型分布

| 文档类型 | Chunk数量 | 占比 |
|---------|-----------|------|
| **产品条款** | 108 | 13.6% |
| **产品说明书** | 601 | 75.6% |
| **产品费率表** | 86 | 10.8% |
| **总计** | 795 | 100% |

**结论**: ✅ 三种文档类型都已成功索引到ChromaDB

---

## 🔍 当前查询策略

### 1. 测试用例的查询策略

**当前状态**: ❌ **测试用例中没有指定`doc_type`过滤**

**影响**:
- ✅ **优点**: 查询会覆盖所有文档类型（产品条款、产品说明书、产品费率表），更全面
- ⚠️ **缺点**: 可能返回不相关的文档类型（如查询"保险期间"可能返回说明书而非条款）

**测试用例字段分析**:
```json
{
  "id": "test_basic_001",
  "question": "身故保险金怎么赔付?",
  "query_type": "basic",
  "expected_category": "Liability",  // ✅ 有category过滤
  "company": "平安人寿",              // ✅ 有company过滤
  // ❌ 缺少 doc_type 字段
}
```

### 2. MCP工具的查询策略

**`search_policy_clause`工具支持**:
```python
def run(
    self,
    query: str,
    company: Optional[str] = None,
    product_code: Optional[str] = None,
    product_name: Optional[str] = None,
    doc_type: Optional[str] = None,  # ✅ 支持doc_type过滤
    category: Optional[str] = None,
    n_results: int = 5,
    min_similarity: float = -1.0
) -> List[ClauseResult]:
```

**默认行为**:
- 如果**不指定`doc_type`**: 查询所有类型的文档
- 如果**指定`doc_type`**: 仅查询指定类型的文档

### 3. 检索器的查询策略

**HybridRetriever的查询流程**:
1. **Dense Vector检索** (语义检索)
   - 使用BGE-small-zh-v1.5生成查询向量
   - 在ChromaDB中执行相似度搜索
   - **支持metadata过滤**（包括`doc_type`）

2. **BM25检索** (关键词检索)
   - 使用BM25算法进行精确词汇匹配
   - **不支持metadata过滤**（仅基于文本内容）

3. **RRF融合** (Reciprocal Rank Fusion)
   - 合并两种检索结果
   - 自动权重调整：
     - 数字查询：80% BM25 + 20% Vector
     - 自然语言查询：20% BM25 + 80% Vector

---

## 🎯 查询策略设计原则

### 设计理念

**客户端视角**:
- ✅ AI客户端（用户）只提供查询内容，不知道文档类型
- ✅ 测试用例应该模拟真实客户端行为，**不指定`doc_type`**
- ✅ `doc_type`的选择应该是MCP服务器端的智能逻辑

**服务器端职责**:
- ✅ 根据查询内容智能推断合适的文档类型
- ✅ 如果无法确定，则查询所有类型，让混合检索自动选择最相关的结果
- ✅ 提供`doc_type`参数作为可选的高级过滤选项（供特殊场景使用）

### 当前实现状态

**现状**: ⚠️ **MCP服务器端尚未实现智能推断逻辑**

当前行为：
- 如果客户端传入`doc_type`：使用该值进行过滤
- 如果客户端不传`doc_type`：查询所有文档类型（默认行为）

**这是正确的默认行为**，但缺少智能推断优化。

### 推荐的智能推断策略

#### 场景1: 查询保险条款（如"身故保险金怎么赔付"）

**查询特征**:
- 包含"保险金"、"保险责任"、"免责"、"条款"等关键词
- 查询的是法律条款内容

**推断逻辑**:
```python
if any(keyword in query for keyword in ["保险金", "保险责任", "免责", "条款", "赔付", "理赔"]):
    inferred_doc_type = "产品条款"
```

#### 场景2: 查询产品说明（如"这个产品怎么买"）

**查询特征**:
- 包含"购买"、"投保"、"怎么买"、"如何投保"等关键词
- 查询的是操作流程

**推断逻辑**:
```python
if any(keyword in query for keyword in ["购买", "投保", "怎么买", "如何投保", "申请", "办理"]):
    inferred_doc_type = "产品说明书"
```

#### 场景3: 查询费率信息（如"30岁保费多少"）

**查询特征**:
- 包含数字+年龄、"保费"、"费率"、"多少钱"等关键词
- 查询的是具体金额

**推断逻辑**:
```python
if any(keyword in query for keyword in ["保费", "费率", "多少钱", "价格"]) and any(char.isdigit() for char in query):
    inferred_doc_type = "产品费率表"
```

#### 场景4: 通用查询（不确定文档类型）

**推断逻辑**:
```python
# 如果无法明确推断，则不指定doc_type
# 让混合检索在所有类型中自动选择最相关的结果
inferred_doc_type = None
```

---

## 📝 改进建议

### 建议1: 在MCP服务器端实现智能`doc_type`推断（高优先级）

**实现位置**: `src/mcp_server/tools/search_policy_clause.py`

**实现方案**:
```python
def _infer_doc_type(self, query: str) -> Optional[str]:
    """根据查询内容智能推断文档类型
    
    Args:
        query: 用户查询内容
        
    Returns:
        推断的文档类型，如果无法确定则返回None
    """
    query_lower = query.lower()
    
    # 费率表关键词
    rate_keywords = ["保费", "费率", "多少钱", "价格", "费用", "成本"]
    if any(kw in query for kw in rate_keywords) and any(c.isdigit() for c in query):
        return "产品费率表"
    
    # 说明书关键词（购买流程、操作说明）
    manual_keywords = ["购买", "投保", "怎么买", "如何投保", "申请", "办理", "操作"]
    if any(kw in query for kw in manual_keywords):
        return "产品说明书"
    
    # 条款关键词（默认）
    clause_keywords = ["保险金", "保险责任", "免责", "条款", "赔付", "理赔", "保障"]
    if any(kw in query for kw in clause_keywords):
        return "产品条款"
    
    # 无法确定，返回None（查询所有类型）
    return None

def run(self, query: str, doc_type: Optional[str] = None, ...):
    # 如果客户端未指定doc_type，则智能推断
    if doc_type is None:
        doc_type = self._infer_doc_type(query)
        logger.info(f"智能推断doc_type: {doc_type}")
    
    # 后续逻辑保持不变
    ...
```

**优势**:
- ✅ 客户端无需关心文档类型
- ✅ 提高检索准确性
- ✅ 保持向后兼容（客户端仍可手动指定）

### 建议2: 测试用例保持不变（正确）

**当前设计**: ✅ **正确**
- 测试用例不指定`doc_type`，模拟真实客户端行为
- 测试MCP服务器的智能推断能力

**无需修改**: 测试用例应该保持当前状态，不添加`doc_type`字段。

### 建议3: 更新测试评估逻辑（中优先级）

**当前评估逻辑**:
- 检查关键词匹配、标题匹配、ID匹配
- **可以添加**: 检查返回结果的`doc_type`分布，验证智能推断是否合理

**改进方案**:
```python
# 在_evaluate_case中添加doc_type分布统计
doc_type_distribution = {}
for r in results:
    metadata = r.get('metadata', {})
    doc_type = metadata.get('doc_type', 'N/A')
    doc_type_distribution[doc_type] = doc_type_distribution.get(doc_type, 0) + 1

result.doc_type_distribution = doc_type_distribution
# 在报告中显示doc_type分布，帮助分析智能推断效果
```

---

## 🔧 实施建议

### 优先级1: 在MCP服务器端实现智能`doc_type`推断（高优先级）

**目标**: 让MCP服务器根据查询内容自动推断合适的文档类型

**实施步骤**:
1. 在`SearchPolicyClauseTool`中添加`_infer_doc_type()`方法
2. 在`run()`方法中，如果`doc_type`为None，则调用推断方法
3. 添加日志记录推断结果，便于调试和优化
4. 编写单元测试验证推断逻辑

**预期效果**:
- 提高检索准确性（特别是对比查询，从67%提升到80%+）
- 改善用户体验（自动选择最相关的文档类型）
- 保持向后兼容（客户端仍可手动指定）

### 优先级2: 更新测试评估逻辑（中优先级）

**目标**: 在测试报告中显示`doc_type`分布，验证智能推断效果

**实施步骤**:
1. 在`TestCaseResult`中添加`doc_type_distribution`字段
2. 在`_evaluate_case()`中统计返回结果的`doc_type`分布
3. 在测试报告中显示分布情况

**预期效果**:
- 可视化智能推断的效果
- 发现需要优化的查询模式

### 优先级3: 测试用例保持不变（正确）

**当前设计**: ✅ **无需修改**
- 测试用例不指定`doc_type`是正确的设计
- 模拟真实客户端行为
- 测试MCP服务器的智能推断能力

---

## 📈 当前测试结果分析

### 测试结果回顾

- **总体准确率**: 84.0% (42/50)
- **基础查询**: 85% (17/20)
- **对比查询**: 67% (10/15)
- **免责查询**: 100% (15/15)

### 可能的问题

1. **对比查询准确率较低（67%）**
   - **可能原因**: 返回了说明书而非条款
   - **解决方案**: 为对比查询用例添加`doc_type="产品条款"`过滤

2. **部分基础查询返回0结果**
   - **可能原因**: category过滤过严，且未考虑文档类型
   - **解决方案**: 放宽过滤条件或添加`doc_type`过滤

---

## ✅ 总结

### 当前状态

1. ✅ **数据索引**: 三种文档类型都已成功索引（产品条款13.6%，产品说明书75.6%，产品费率表10.8%）
2. ✅ **工具支持**: MCP工具支持`doc_type`过滤（作为可选参数）
3. ✅ **测试用例设计**: **正确** - 不指定`doc_type`，模拟真实客户端行为
4. ⚠️ **智能推断**: MCP服务器端尚未实现智能`doc_type`推断逻辑
5. ⚠️ **测试评估**: 未统计返回结果的`doc_type`分布

### 设计原则确认

**✅ 正确的设计思路**:
- **客户端**: 只提供查询内容，不关心`doc_type`
- **服务器端**: 应该智能推断`doc_type`，如果无法确定则查询所有类型
- **测试用例**: 应该模拟真实客户端行为，不指定`doc_type`

### 推荐行动

1. **高优先级**: 在MCP服务器端实现智能`doc_type`推断逻辑
2. **中优先级**: 更新测试评估逻辑，统计`doc_type`分布
3. **无需修改**: 测试用例保持当前状态（不添加`doc_type`字段）

---

**报告生成时间**: 2025-11-25

