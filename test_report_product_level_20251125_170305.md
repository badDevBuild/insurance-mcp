# 产品级别端到端测试报告

**测试集**: Phase5_Product_Level_Test_Set

**执行时间**: 2025-11-25 17:03:05

**测试用例总数**: 50


## 测试摘要

- ✅ **通过**: 46
- ❌ **失败**: 1
- ⚠️ **错误**: 3
- 📊 **通过率**: 92.00%


## 按类别统计


### PRODUCT_LOOKUP

- 总数: 10
- 通过: 10
- 失败: 0
- 通过率: 100.00%


### BASIC_QUERY

- 总数: 20
- 通过: 20
- 失败: 0
- 通过率: 100.00%


### COMPARISON_QUERY

- 总数: 10
- 通过: 10
- 失败: 0
- 通过率: 100.00%


### RATE_TABLE_QUERY

- 总数: 5
- 通过: 2
- 失败: 0
- 通过率: 40.00%


### EXCLUSION_QUERY

- 总数: 5
- 通过: 4
- 失败: 1
- 通过率: 80.00%


## 失败和错误案例


### ⚠️ rate_table_001

**类别**: rate_table_query

**问题**: 平安福耀年金保险30岁男性保费多少？

**产品**: 平安福耀年金保险（分红型）

**状态**: 错误

**错误**: Expected where to have exactly one operator, got {'company': '平安人寿', 'doc_type': '产品费率表'} in query.


### ⚠️ rate_table_004

**类别**: rate_table_query

**问题**: 平安御享金越终身寿险40岁女性投保费用？

**产品**: 平安御享金越（2026）终身寿险（分红型）

**状态**: 错误

**错误**: Expected where to have exactly one operator, got {'company': '平安人寿', 'doc_type': '产品费率表'} in query.


### ⚠️ rate_table_005

**类别**: rate_table_query

**问题**: 平安盈尊优享B款终身寿险50岁保费价格表？

**产品**: 平安盈尊优享（B款）终身寿险（分红型）

**状态**: 错误

**错误**: Expected where to have exactly one operator, got {'company': '平安人寿', 'doc_type': '产品费率表'} in query.


### ❌ exclusion_001

**类别**: exclusion_query

**问题**: 平安福耀年金保险酒后驾驶会赔吗？

**产品**: 平安福耀年金保险（分红型）

**状态**: 失败

**错误**: 未返回结果
