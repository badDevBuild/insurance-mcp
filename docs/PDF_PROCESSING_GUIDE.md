# PDF处理功能使用指南

## 概述

PDF处理模块负责将保险产品的PDF文档（条款、说明书）转换为高质量的Markdown格式，以便后续的向量化索引和检索。

**支持的文档类型**：
- 产品条款
- 产品说明书

**核心技术栈**：
- **markitdown**: Microsoft开发的文档转换工具，提供高保真的PDF→Markdown转换
- **pdfplumber**: 用于PDF版面分析和质量检查

---

## 工作流程

```
┌─────────────────┐
│  PDF文件 (raw)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  版面分析       │ (可选)
│  analyzer.py    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  PDF转Markdown  │
│  converter.py   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Markdown (proc) │
│  + DB metadata  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  人工审核       │
│  verify.py      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ VERIFIED 文档   │
│  → 进入索引     │
└─────────────────┘
```

---

## 命令参考

### 1. PDF转Markdown

**转换指定类型的文档**：

```bash
# 转换产品条款（限制10份）
python -m src.cli.manage process convert --doc-type 产品条款 --limit 10

# 转换产品说明书（限制10份）
python -m src.cli.manage process convert --doc-type 产品说明书 --limit 10
```

**转换所有文档**：

```bash
# 转换所有PENDING状态的条款和说明书
python -m src.cli.manage process convert --all
```

**输出示例**：

```
🔄 开始PDF转Markdown转换...
文档类型过滤: 产品条款
限制数量: 10

[1/10] 处理: 产品条款.pdf (产品条款)
✅ [产品条款.pdf] 转换成功，输出 11,053 字符
💾 [产品条款.pdf] Markdown已保存到: data/processed/067afcfc-...md
✅ [产品条款.pdf] 数据库已更新，状态: PENDING

...

============================================================
✅ 转换完成
============================================================
总计: 10
成功: 10
失败: 0
============================================================
```

### 2. PDF版面分析

分析特定产品的PDF版面结构（用于质量检查）：

```bash
python -m src.cli.manage process analyze 2124
```

**输出示例**：

```
🔍 分析产品 2124 的PDF文档版面...

📄 产品条款: 产品条款.pdf
   ✅ 分析成功
   页数: 21
   布局类型: single_column
   包含表格: 是
   包含图像: 否
   质量评分: 0.90

📄 产品说明书: 产品说明书.pdf
   ✅ 分析成功
   页数: 8
   布局类型: mixed
   包含表格: 是
   包含图像: 是
   质量评分: 0.70
   ⚠️  建议人工复核
```

**质量评分规则**：
- `1.0`: 单栏布局，无复杂元素
- `0.9`: 单栏布局，包含表格
- `0.8`: 双栏布局
- `0.7`: 混合布局
- `< 0.7`: 复杂版面，建议人工复核

### 3. 审核管理

#### 3.1 列出待审核文档

```bash
# 列出所有待审核文档
python -m src.cli.verify list

# 只看产品条款
python -m src.cli.verify list --doc-type 产品条款

# 限制显示数量
python -m src.cli.verify list --limit 50
```

**输出示例**：

```
待审核文档列表 (5份)
┏━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━┓
┃ ID       ┃ 文档类型 ┃ 文件名       ┃ 产品ID   ┃ 下载时间   ┃ Markdown长度 ┃
┡━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━┩
│ 067afcfc │ 产品条款 │ 产品条款.pdf │ a099cc08 │ 2025-11-21 │       11,053 │
│ 56a86f5d │ 产品条款 │ 产品条款.pdf │ ca12573b │ 2025-11-21 │       10,266 │
...
└──────────┴──────────┴──────────────┴──────────┴────────────┴──────────────┘
```

#### 3.2 预览文档

```bash
# 使用完整ID或前8位
python -m src.cli.verify preview 067afcfc

# 指定预览行数
python -m src.cli.verify preview 067afcfc --lines 100
```

**输出示例**：

```
╭─────────────────── 📄 Document Info ────────────────────╮
│ ID: 067afcfc-e8eb-43d2-994a-66474dcd65e5                │
│ 文档类型: 产品条款                                      │
│ 文件名: 产品条款.pdf                                    │
│ Markdown长度: 11,053 字符 (774 行)                      │
│ 状态: PENDING                                           │
╰─────────────────────────────────────────────────────────╯

Markdown预览（前30行）:

────────────────────────────────────────────────────────
平安人寿〔2025〕年金保险 163 号

平安福耀年金保险（分红型）

阅读指引
...
────────────────────────────────────────────────────────

... 还有 744 行未显示

💡 完整文件: data/processed/067afcfc-e8eb-43d2-994a-66474dcd65e5.md
```

#### 3.3 批准文档

```bash
# 批准文档
python -m src.cli.verify approve 067afcfc

# 带备注
python -m src.cli.verify approve 067afcfc --notes "格式完整，内容准确"
```

**输出**：

```
✅ 文档已批准: 产品条款.pdf
   ID: 067afcfc-e8eb-43d2-994a-66474dcd65e5
   备注: 格式完整，内容准确
```

#### 3.4 驳回文档

```bash
# 驳回文档（必须提供原因）
python -m src.cli.verify reject 067afcfc -r "表格格式错误，需要重新处理"
```

**输出**：

```
❌ 文档已驳回: 产品条款.pdf
   ID: 067afcfc-e8eb-43d2-994a-66474dcd65e5
   原因: 表格格式错误，需要重新处理
```

#### 3.5 查看统计

```bash
python -m src.cli.verify stats
```

**输出示例**：

```
           文档审核统计           
┏━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━┓
┃ 状态        ┃  数量 ┃     占比 ┃
┡━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━┩
│ ⏳ PENDING  │    85 │    70.8% │
│ ✅ VERIFIED │    30 │    25.0% │
│ ❌ REJECTED │     5 │     4.2% │
│ ━━━━━━━━━━  │ ━━━━━ │ ━━━━━━━━ │
│ 总计        │   120 │   100.0% │
└─────────────┴───────┴──────────┘

         按文档类型统计         
┏━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━┓
┃ 文档类型   ┃ 状态     ┃ 数量 ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━┩
│ 产品条款   │ PENDING  │   10 │
│ 产品条款   │ VERIFIED │   10 │
│ 产品说明书 │ PENDING  │   20 │
└────────────┴──────────┴──────┘
```

---

## 典型工作流

### 场景1: 批量处理新采集的PDF

```bash
# 1. 先转换一小批样本检查质量
python -m src.cli.manage process convert --doc-type 产品条款 --limit 5

# 2. 审核转换结果
python -m src.cli.verify list
python -m src.cli.verify preview 067afcfc

# 3. 如果质量满意，批量转换
python -m src.cli.manage process convert --all

# 4. 批量审核（人工）
python -m src.cli.verify list
# ... 逐个preview和approve/reject ...

# 5. 查看进度
python -m src.cli.verify stats
```

### 场景2: 处理转换失败的文档

```bash
# 1. 查看失败原因（检查日志）
tail -f logs/crawler.log

# 2. 对于特定问题文档，先分析版面
python -m src.cli.manage process analyze 2124

# 3. 如果版面复杂，可能需要：
#    - 调整转换参数（未来实现）
#    - 使用OCR回退（未来实现）
#    - 人工处理
```

### 场景3: 质量抽检

```bash
# 1. 按类型分别抽检
python -m src.cli.verify list --doc-type 产品条款 --limit 10
python -m src.cli.verify list --doc-type 产品说明书 --limit 10

# 2. 对每种类型随机抽取几份预览
python -m src.cli.verify preview <random_id>

# 3. 根据抽检结果决定是否批量approve
for id in $(python -m src.cli.verify list | awk '{print $1}'); do
    python -m src.cli.verify approve $id --notes "批量审核通过"
done
```

---

## 文件组织

```
insurance-mcp/
├── data/
│   ├── raw/                    # 原始PDF文件
│   │   └── 平安人寿/
│   │       └── 2124/
│   │           ├── 产品条款.pdf
│   │           └── 产品说明书.pdf
│   │
│   ├── processed/              # 转换后的Markdown
│   │   ├── 067afcfc-e8eb-43d2-994a-66474dcd65e5.md
│   │   └── 56a86f5d-5ae0-4e1e-90bb-e7018a0e415d.md
│   │
│   └── db/
│       └── metadata.sqlite     # 元数据数据库
│
├── src/
│   ├── parser/
│   │   ├── markdown/
│   │   │   └── converter.py    # PDF→Markdown转换器
│   │   ├── layout/
│   │   │   └── analyzer.py     # 版面分析器
│   │   └── ocr/
│   │       └── paddle.py       # OCR回退（待实施）
│   │
│   └── cli/
│       ├── manage.py           # process命令
│       └── verify.py           # 审核员CLI
│
└── logs/
    └── crawler.log             # 处理日志
```

---

## 数据库字段

### `policy_documents` 表

| 字段 | 类型 | 说明 |
|-----|-----|-----|
| `id` | TEXT | 文档UUID |
| `product_id` | TEXT | 关联的产品ID |
| `doc_type` | TEXT | 文档类型（产品条款/产品说明书） |
| `filename` | TEXT | 原始文件名 |
| `local_path` | TEXT | PDF文件路径 |
| `url` | TEXT | 原始下载URL |
| `file_hash` | TEXT | SHA-256哈希 |
| `file_size` | INTEGER | 文件大小（字节） |
| `downloaded_at` | TIMESTAMP | 下载时间 |
| `verification_status` | TEXT | 审核状态（PENDING/VERIFIED/REJECTED） |
| `auditor_notes` | TEXT | 审核备注 |
| `markdown_content` | TEXT | Markdown内容预览（前5000字符） |
| `pdf_links` | JSON | 所有PDF链接字典 |

---

## 常见问题

### Q1: 为什么选择markitdown而不是pdfplumber？

**A**: 测试对比显示：
- markitdown输出更完整（1063行 vs 159行）
- 自动处理排版、表格、列表
- Microsoft官方维护，质量更高
- pdfplumber更适合用于版面分析和质量检查

### Q2: 转换后的Markdown为什么不在数据库中存储完整内容？

**A**: 
- 保险条款文档通常较大（10-30KB）
- 数据库只存储前5000字符作为预览
- 完整内容保存在`data/processed/`目录
- 减少数据库体积，提高查询性能

### Q3: 如何处理双栏或复杂布局的PDF？

**A**:
1. 先用`process analyze`检查版面
2. 质量评分<0.8的建议人工复核
3. markitdown通常能自动处理大部分双栏布局
4. 特殊情况可能需要OCR回退（待实施）

### Q4: 审核流程可以自动化吗？

**A**:
- 当前版本需要人工审核
- 未来可以基于质量评分实现自动approve
- 建议至少人工抽检10%

### Q5: 转换失败的文档如何处理？

**A**:
1. 检查日志文件`logs/crawler.log`
2. 确认PDF文件是否损坏
3. 如果是版面问题，等待OCR功能实施
4. 可以手动编辑转换后的Markdown

---

## 性能数据

基于实际测试（平安人寿产品条款）：

| 指标 | 数值 |
|-----|-----|
| 平均转换速度 | ~1秒/文档 |
| 输出质量 | 10-12KB Markdown（对应20页PDF） |
| 支持PDF大小 | 最大测试50MB |
| 并发处理 | 单进程顺序处理 |
| 成功率 | >98%（常规PDF） |

---

## 下一步

完成PDF处理后，文档将进入**第五阶段：向量化索引**：

1. 使用已VERIFIED的Markdown文档
2. 切分为语义chunk
3. 生成embedding向量
4. 存储到ChromaDB
5. 通过MCP服务器提供检索能力

详见后续指南。

