# Phase 1: 高保真结构化解析重构 - Docling集成计划
## 📋 项目背景
### 当前痛点
基于深度研究报告的差距分析，我们的现有系统存在以下严重问题：
1. **解析引擎缺陷**: 无法正确处理多栏排版，表格结构丢失，阅读顺序可能错乱
2. **费率表处理失败**: 数字密集型数据被向量化后，无法精确回答数值查询
3. **上下文丢失**: 单个Chunk缺乏父级章节约束信息
### 核心目标
将当前的"文本流提取"升级为"文档对象模型（DOM）提取"，彻底解决表格错乱和排版问题，并为费率表查询做准备。
### 设计原则
* **数据质量优先**: RAG质量上限由解析质量决定
* **结构化优先**: 从像素到语义的完整转换
* **向后兼容**: 保留现有元数据体系
## 🎯 成功标准 (Success Criteria)
### 定量指标
1. **表格还原准确率**: ≥95% (通过人工抽样验证)
2. **阅读顺序准确率**: ≥98% (多栏文档测试)
3. **费率查询准确率**: 100% (数值型问题零幻觉)
4. **处理速度**: 单页PDF ≤2秒
### 定性指标
1. LLM能正确理解Markdown表格的行列关系
2. 每个Chunk自动附带完整的章节路径
3. 费率表与文本Chunk完全隔离
## 📐 技术架构
### 核心技术选型
* **解析引擎**: Docling (IBM开源)
    * 理由: 输出结构化Markdown，保留标题层级，表格还原能力卓越
    * 版本: >=2.0.0
    * License: MIT (商业友好)
* **表格识别**: Docling内置TSR (Table Structure Recognition)
    * 无需额外依赖
    * 支持无线表格
### 数据流架构
```warp-runnable-command
PDF文件
  ↓
[Docling Parser] → 解析为DoclingDocument对象
  ↓
[Document Analyzer] → 识别表格类型(费率表 vs 普通表)
  ↓
  ├─→ [费率表] → 序列化为CSV/JSON → 存储到assets/tables/
  │                                      └→ 元数据记录路径
  ↓
  └─→ [文本+普通表] → Markdown-Aware Chunking
                        ↓
                   [MetadataExtractor] → 保留现有元数据提取
                        ↓
                   [BGEEmbedder] → 向量化
                        ↓
                   [ChromaDBStore] → 存储
```
## 📦 实施阶段
### Stage 1: 环境准备与依赖安装 (1天)
#### 任务清单
1. **安装Docling及依赖**
    * `pip install docling>=2.0.0`
    * 验证CUDA支持(如有GPU)
    * 测试示例PDF解析
2. **创建新目录结构**
```warp-runnable-command
   src/indexing/
     ├── parsers/
     │   ├── __init__.py
     │   ├── base.py          # 抽象解析器接口
     │   ├── docling_parser.py  # Docling实现
     │   └── legacy_parser.py   # 保留旧解析器作为备用
     ├── analyzers/
     │   ├── __init__.py
     │   └── table_classifier.py  # 费率表识别器
     └── chunkers/
         ├── __init__.py
         ├── base.py
         └── markdown_chunker.py  # Markdown感知切片器
   
   assets/
     └── tables/              # 存储提取的费率表
         ├── rate_tables/
         └── metadata.json    # 表格索引
   
```
3. **配置更新**
    * 在`src/common/config.py`添加:
        * `DOCLING_MODEL_PATH`
        * `TABLE_EXPORT_DIR`
        * `ENABLE_TABLE_SEPARATION`
#### 验收标准
* Docling成功解析一个测试PDF
* 目录结构创建完成
* 配置项可正常读取
***
### Stage 2: Docling解析器集成 (2-3天)
#### 任务2.1: 实现DoclingParser类
**文件**: `src/indexing/parsers/docling_parser.py`
**核心功能**:
```python
class DoclingParser(BaseParser):
    def parse(self, pdf_path: Path) -> ParsedDocument:
        """解析PDF为结构化对象"""
        # 1. 调用Docling API
        # 2. 提取文档结构树 (headings, paragraphs, tables, images)
        # 3. 转换为内部ParsedDocument格式
        pass
    
    def export_markdown(self, doc: ParsedDocument) -> str:
        """导出为层级化Markdown"""
        # 保留标题层级: #, ##, ###
        # 表格转为GitHub风格Markdown
        pass
```
**关键点**:
* 保留Docling的`DocElement`对象，不立即扁平化
* 记录每个元素的页码和坐标（用于调试）
* 正确处理跨页表格的合并
#### 任务2.2: 阅读顺序修复
**问题**: 多栏排版的阅读顺序
**解决方案**:
* 利用Docling的版面分析结果
* 按`reading_order`属性排序元素
* 单元测试: 准备2-3个多栏PDF样本，验证输出顺序
#### 验收标准
* 单栏PDF解析100%准确
* 双栏PDF阅读顺序正确率≥98%
* 输出的Markdown标题层级完整
***
### Stage 3: 费率表分离与序列化 (2天)
#### 任务3.1: 表格分类器
**文件**: `src/indexing/analyzers/table_classifier.py`
**分类逻辑**:
```python
class TableClassifier:
    def is_rate_table(self, table: DocTable) -> bool:
        """
        识别费率表的启发式规则:
        1. 列名包含: 年龄/Age, 保费/Premium, 费率/Rate
        2. 数值单元格占比 >70%
        3. 行数 ≥10 (排除小表)
        """
        pass
    
    def get_table_type(self, table: DocTable) -> TableType:
        # Enum: RATE_TABLE, BENEFIT_TABLE, ORDINARY_TABLE
        pass
```
#### 任务3.2: 表格序列化
**策略选择** (参考报告5.2):
1. **费率表** → CSV格式 (便于后续Text-to-SQL)
2. **普通表** → Markdown表格 (便于LLM阅读)
**实现**:
```python
class TableSerializer:
    def serialize_rate_table(self, table: DocTable) -> Path:
        """导出为CSV，返回文件路径"""
        # 1. 提取表头（处理多层嵌套）
        # 2. 展平为单层表头（用下划线连接父级）
        # 3. 写入CSV
        # 4. 在metadata.json中记录元信息
        pass
```
**元数据记录**:
在`assets/tables/metadata.json`中:
```json
{
  "table_uuid": {
    "source_pdf": "平安福耀费率表.pdf",
    "page_range": [5, 8],
    "product_code": "2124",
    "table_type": "RATE_TABLE",
    "csv_path": "rate_tables/2124_male_rates.csv",
    "columns": ["Age", "Premium_10Y", "Premium_20Y"],
    "row_count": 56
  }
}
```
#### 验收标准
* 费率表识别准确率≥95%
* CSV表头正确展平（无信息丢失）
* 元数据JSON格式正确
***
### Stage 4: Markdown感知切片器 (2天)
#### 任务4.1: 实现层级化切片
**文件**: `src/indexing/chunkers/markdown_chunker.py`
**核心逻辑** (参考报告5.1):
```python
class MarkdownChunker:
    def chunk_with_hierarchy(self, markdown: str) -> List[Chunk]:
        """
        基于Markdown标题进行切片
        
        策略:
        1. 解析Markdown的标题树 (# -> ## -> ###)
        2. 按章节切分
        3. 为每个chunk附加"面包屑"路径
        """
        # 示例输出:
        # Chunk 1:
        #   path: "保险责任 > 重大疾病保险金"
        #   content: "被保险人首次确诊重疾..."
        pass
    
    def add_parent_context(self, chunk: Chunk, parent_path: str):
        """在chunk开头添加父级路径"""
        chunk.content = f"[章节: {parent_path}]\n\n{chunk.content}"
```
**参数配置**:
* `max_chunk_size`: 1024 tokens (适配BGE-M3)
* `chunk_overlap`: 128 tokens
* `respect_heading_boundaries`: True (不在标题中间切断)
#### 任务4.2: 更新PolicyChunk模型
**文件**: `src/common/models.py`
**新增字段**:
```python
class PolicyChunk(BaseModel):
    # ... 现有字段 ...
    
    # 新增:
    section_path: Optional[str] = None  # 例: "保险责任 > 重疾 > 给付条件"
    heading_level: int = 1  # 该chunk对应的最高标题级别
    contains_table: bool = False  # 是否包含表格
    table_refs: List[str] = []  # 如果费率表被分离，记录其UUID引用
```
#### 验收标准
* 所有chunk都有`section_path`
* 长章节被正确切分，边界在段落而非句中
* 包含表格的chunk正确标记
***
### Stage 5: 索引流程重构 (1-2天)
#### 任务5.1: 更新PolicyIndexer
**文件**: `src/indexing/indexer.py`
**修改要点**:
```python
class PolicyIndexer:
    def index_document(self, pdf_path: Path) -> IndexResult:
        # 1. 使用DoclingParser解析
        parsed_doc = self.parser.parse(pdf_path)
        
        # 2. 提取表格并分类
        tables = parsed_doc.get_tables()
        for table in tables:
            if self.classifier.is_rate_table(table):
                # 序列化为CSV，跳过向量化
                csv_path = self.serializer.serialize_rate_table(table)
                # 仅在元数据中记录
            else:
                # 普通表格转Markdown，继续向量化
                pass
        
        # 3. Markdown感知切片
        markdown = parsed_doc.to_markdown(exclude_rate_tables=True)
        chunks = self.chunker.chunk_with_hierarchy(markdown)
        
        # 4. 元数据提取（保留原有逻辑）
        for chunk in chunks:
            chunk.category = self.metadata_extractor.extract_category(chunk.content)
            # ...
        
        # 5. 向量化与存储
        # ...
```
#### 任务5.2: CLI命令更新
**文件**: `src/cli/manage.py`
**新增命令**:
```warp-runnable-command
# 查看已分离的表格
python -m src.cli.manage tables list
# 导出特定表格
python -m src.cli.manage tables export --table-id <uuid> --format csv
# 重新索引（使用新解析器）
python -m src.cli.manage index rebuild --use-docling
```
#### 验收标准
* 完整的PDF能成功索引
* ChromaDB中的chunk包含新字段
* 费率表不在向量库中，但可通过metadata查询
***
### Stage 6: 测试与验证 (2天)
#### 任务6.1: 单元测试
**文件**: `tests/unit/test_docling_parser.py`
**测试用例**:
1. 单栏PDF解析
2. 双栏PDF阅读顺序
3. 费率表识别
4. 表格序列化（CSV格式验证）
5. Markdown切片边界
#### 任务6.2: 集成测试
**文件**: `tests/integration/test_docling_indexing.py`
**端到端测试**:
1. 索引包含费率表的完整PDF
2. 验证ChromaDB中的chunk质量
3. 验证费率表CSV的可读性
4. 对比新旧解析器的输出差异
#### 任务6.3: 回归测试
**目标**: 确保不破坏现有功能
**验证**:
* 运行所有现有测试套件
* P0+增强功能仍正常工作
* MCP工具调用无影响
#### 验收标准
* 单元测试覆盖率≥80%
* 集成测试全部通过
* 回归测试零失败
***
### Stage 7: 文档与交付 (1天)
#### 任务7.1: 更新技术文档
**更新文件**:
1. `METADATA_STRUCTURE.md`
    * 新增`section_path`字段说明
    * 新增`table_refs`字段说明
2. 创建`DOCLING_INTEGRATION.md`
    * 解析流程图
    * 表格分离策略说明
    * 故障排查指南
3. 更新`README.md`
    * 安装依赖更新
    * 新增CLI命令说明
#### 任务7.2: 性能基准测试
**创建**: `benchmarks/docling_performance.py`
**测试指标**:
* 单页解析时间
* 内存占用
* 与旧解析器的对比
#### 交付物清单
- [ ] 完整的代码实现
- [ ] 测试覆盖报告
- [ ] 性能基准报告
- [ ] 更新的技术文档
- [ ] 迁移指南（从旧解析器切换）
## 🚨 风险与缓解
### 风险1: Docling模型下载失败
* **概率**: 中
* **影响**: 高
* **缓解**: 提前下载模型到本地，配置离线路径
### 风险2: 费率表识别准确率不足
* **概率**: 中
* **影响**: 高
* **缓解**: 实现"人工标注模式"，允许用户手动标记表格类型
### 风险3: 性能下降
* **概率**: 低
* **影响**: 中
* **缓解**: 实现批处理和缓存机制，增加GPU加速
### 风险4: 与现有系统不兼容
* **概率**: 低
* **影响**: 高
* **缓解**: 保留旧解析器作为fallback，通过配置切换
## 📊 时间估算
| 阶段 | 工作量 | 依赖 |
|------|--------|------|
| Stage 1: 环境准备 | 1天 | 无 |
| Stage 2: 解析器集成 | 2-3天 | Stage 1 |
| Stage 3: 表格分离 | 2天 | Stage 2 |
| Stage 4: 切片器 | 2天 | Stage 2 |
| Stage 5: 流程重构 | 1-2天 | Stage 3, 4 |
| Stage 6: 测试 | 2天 | Stage 5 |
| Stage 7: 文档 | 1天 | Stage 6 |
**总计**: 11-14个工作日
**关键路径**: Stage 1 → Stage 2 → Stage 3 → Stage 5 → Stage 6
## ✅ 验收标准总结
### Must Have (P0)
1. Docling成功解析测试PDF
2. 费率表正确分离并导出为CSV
3. Markdown切片包含完整章节路径
4. 所有集成测试通过
### Should Have (P1)
5. 多栏PDF阅读顺序准确率≥98%
6. 费率表识别准确率≥95%
7. 单元测试覆盖率≥80%
### Nice to Have (P2)
8. 性能优于旧解析器
9. 支持GPU加速
10. 完整的调试日志
## 📝 后续阶段预告
本Phase完成后，将具备以下能力基础:
* **Phase 2**: Text-to-SQL费率查询工具
* **Phase 3**: 混合检索（Dense + Sparse/BM25）
* **Phase 4**: GraphRAG跨文档推理
***
**计划创建时间**: 2025-11-24
**预计开始时间**: 2025-11-25
**预计完成时间**: 2025-12-13