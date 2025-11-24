# 第五阶段实施检查清单

## 🎯 总览

本清单用于确保第五阶段（向量化索引）实施过程中正确应用所有优化建议。

**使用方法**：
1. 在开始每个任务前，阅读对应的"任务前检查"
2. 实施过程中，参考"实施要点"
3. 完成后，执行"验收测试"并勾选完成状态

---

## 📋 第一步：准备阶段

### 1.1 文档更新检查

- [ ] **spec.md 已更新**
  - [ ] 已添加 FR-009（语义感知切片策略）
  - [ ] 已添加 FR-009a（表格完整性保护）
  - [ ] 已添加 FR-010（元数据增强策略）
  - [ ] 已添加 FR-011（混合检索机制）
  - [ ] 已重新设计 FR-001, FR-002（MCP工具）
  - [ ] 已添加 FR-002a（退保逻辑工具）
  - [ ] 已更新 SC-003（分层测试标准）
  - [ ] 已扩展 FR-004（数据清洗要求）
  - [ ] 所有补丁已正确合并，无语法错误

- [ ] **tasks.md 已扩展**
  - [ ] 已添加 T020a（Markdown后处理）
  - [ ] 已添加 T022a（混合检索）
  - [ ] 已添加 T023a（表格独立chunk）
  - [ ] 已添加 T025a（MCP工具重设计）
  - [ ] 已添加 T028a（黄金测试集）
  - [ ] 依赖关系图已更新

- [ ] **data-model.md 已更新**
  - [ ] PolicyChunk实体已扩展（新增8个字段）
  - [ ] ER图已更新
  - [ ] ChromaDB schema已定义
  - [ ] 已添加表格数据结构定义

- [ ] **models.py 已更新**
  - [ ] PolicyChunk类已重构
  - [ ] 已添加ClauseCategory枚举
  - [ ] 已添加EntityRole枚举
  - [ ] 已添加TableData模型
  - [ ] 已实现to_chroma_metadata()方法
  - [ ] 已实现from_chroma_result()方法
  - [ ] 已添加classify_category()辅助函数
  - [ ] 已添加identify_entity_role()辅助函数

### 1.2 环境准备检查

- [ ] **Python依赖已安装**
  ```bash
  pip install rank-bm25 jieba langchain
  pip list | grep -E "rank-bm25|jieba|langchain"
  ```

- [ ] **测试环境已验证**
  ```bash
  # 确认pytest可用
  pytest --version
  
  # 确认ChromaDB可访问
  python -c "import chromadb; print(chromadb.__version__)"
  
  # 确认OpenAI API Key已配置
  python -c "from src.common.config import config; print('OpenAI Key:', bool(config.OPENAI_API_KEY))"
  ```

- [ ] **数据准备已完成**
  - [ ] 至少有20份VERIFIED状态的PDF文档
  - [ ] Markdown文件已生成并保存在data/processed/
  - [ ] 数据库中的verification_status字段准确
  
  ```bash
  # 检查VERIFIED文档数量
  sqlite3 data/db/metadata.sqlite \
    "SELECT COUNT(*) FROM policy_documents WHERE verification_status='VERIFIED';"
  ```

### 1.3 团队对齐检查

- [ ] **技术方案已确认**
  - [ ] 团队已理解"第一性原理"设计理念
  - [ ] 已讨论并认同混合检索的必要性
  - [ ] 已理解表格独立chunk的重要性
  - [ ] 已明确MCP工具的新设计

- [ ] **工作量估算已完成**
  - [ ] T020a: 3天（后处理pipeline）
  - [ ] T022a: 5天（混合检索）
  - [ ] T023a: 4天（表格处理）
  - [ ] T025a: 5天（MCP工具重设计）
  - [ ] T028a: 3天（黄金测试集）
  - [ ] **总计**: 15-20工作日

---

## 📋 第二步：T020a - Markdown后处理

### 任务前检查

- [ ] 已完成T019（审核员CLI）
- [ ] 至少有10份VERIFIED文档可用于测试
- [ ] 已阅读用户建议："脚注处理提升50%效果"

### 实施要点

- [ ] **FootnoteInliner实现**
  - [ ] 正则表达式正确匹配脚注标记（⁽数字⁾ 或 [数字]）
  - [ ] 能提取脚注内容
  - [ ] 能找到正文中的脚注引用
  - [ ] 正确插入定义到正文
  - [ ] 删除原脚注部分
  
  ```python
  # 测试用例
  def test_footnote_inliner():
      input_text = "被保险人⁽¹⁾应在...\n\n⁽¹⁾被保险人指受保险合同保障的人"
      expected = "被保险人（指受保险合同保障的人）应在..."
      result = FootnoteInliner().inline_footnotes(input_text)
      assert result == expected
  ```

- [ ] **NoiseRemover实现**
  - [ ] 噪音模式列表完整（页眉、页脚、水印）
  - [ ] 正则表达式准确（不误杀正文）
  - [ ] 保留有意义的分隔符
  
  ```python
  # 测试用例
  def test_noise_remover():
      input_text = "平安人寿 第12页\n\n1.2.6 身故保险金\n若被保险人..."
      expected = "1.2.6 身故保险金\n若被保险人..."
      result = NoiseRemover().remove_noise(input_text)
      assert "第12页" not in result
      assert "身故保险金" in result
  ```

- [ ] **FormatStandardizer实现**
  - [ ] 统一标题层级
  - [ ] 统一列表格式
  - [ ] 修正繁简混用
  - [ ] 规范化空白行

- [ ] **TableValidator实现**
  - [ ] 检测Markdown表格
  - [ ] 验证行列完整性
  - [ ] 生成JSON结构
  - [ ] 返回表格元数据

- [ ] **Pipeline集成**
  - [ ] MarkdownPostProcessor类正确编排流程
  - [ ] 错误处理完善
  - [ ] 日志记录详细

- [ ] **CLI命令实现**
  ```bash
  python -m src.cli.manage process postprocess --doc-id 067afcfc
  python -m src.cli.manage process postprocess --all
  ```

### 验收测试

- [ ] **功能测试**
  - [ ] 手动测试10份文档，脚注内联成功率 > 95%
  - [ ] 噪音去除不影响正文（零误杀）
  - [ ] 表格完整性验证通过率 100%
  - [ ] 处理后的Markdown仍符合规范

- [ ] **性能测试**
  - [ ] 单文档处理时间 < 5秒
  - [ ] 批量处理100份文档无内存溢出

- [ ] **回归测试**
  - [ ] 原有的T018 process convert命令仍可用
  - [ ] 原有的T019 verify命令仍可用

- [ ] **更新tasks.md**
  - [ ] 将T020a标记为 `[x]`
  - [ ] 记录实施要点和注意事项

---

## 📋 第三步：T022a - 混合检索

### 任务前检查

- [ ] 已完成T020a（后处理）
- [ ] 已完成T021（OpenAI Embedding）
- [ ] 已完成T022（ChromaDB实现）
- [ ] 理解Reciprocal Rank Fusion算法

### 实施要点

- [ ] **BM25Index实现**
  - [ ] 使用rank-bm25库
  - [ ] 中文分词使用jieba
  - [ ] 索引持久化到磁盘
  - [ ] 支持增量更新
  
  ```python
  # 测试用例
  def test_bm25_search():
      index = BM25Index(Path("test_bm25.pkl"))
      docs = [
          Document(id="1", content="1.2.1 保险责任"),
          Document(id="2", content="2.1 责任免除")
      ]
      index.build(docs)
      
      results = index.search("1.2.1条款", top_k=1)
      assert results[0].doc_id == "1"
      assert results[0].score > 0
  ```

- [ ] **HybridRetriever实现**
  - [ ] 正确调用ChromaDB和BM25
  - [ ] RRF算法实现准确
  - [ ] 权重自动调整逻辑合理
  - [ ] 支持metadata过滤
  
  ```python
  # 测试用例
  @pytest.mark.asyncio
  async def test_hybrid_search_numbers():
      retriever = HybridRetriever(chroma, bm25)
      results = retriever.search("1.2.1条款")
      
      # 应该自动提升BM25权重
      assert "1.2.1" in results[0].content
  ```

- [ ] **权重启发式规则**
  - [ ] 数字查询：BM25权重提升至80%
  - [ ] 问句查询：语义权重提升至80%
  - [ ] 默认配置：语义60% + BM25 40%

- [ ] **集成到索引流程**
  - [ ] 在T023（索引器）中同步构建BM25索引
  - [ ] 提供统一的search接口

### 验收测试

- [ ] **功能测试**
  - [ ] 专有名词查询准确（如"189号"、"减额交清"）
  - [ ] 问句查询准确（如"如何退保？"）
  - [ ] metadata过滤正确（如category="Exclusion"）

- [ ] **对比测试**
  - [ ] 准备10个测试查询
  - [ ] 对比纯语义 vs 混合检索的准确率
  - [ ] 混合检索准确率提升 > 15%

- [ ] **性能测试**
  - [ ] 查询响应时间 < 2秒
  - [ ] 并发10个查询无性能下降

- [ ] **更新tasks.md**
  - [ ] 将T022a标记为 `[x]`
  - [ ] 记录混合检索效果提升数据

---

## 📋 第四步：T023a - 表格独立Chunk

### 任务前检查

- [ ] 已完成T020a（后处理）
- [ ] 理解Constitution 3.2关于表格的要求
- [ ] 已阅读用户建议："不要拆散表格"

### 实施要点

- [ ] **SemanticChunker实现**
  - [ ] 使用MarkdownHeaderTextSplitter按层级切分
  - [ ] 表格识别正则表达式准确
  - [ ] 表格作为独立chunk提取
  - [ ] 表格JSON转换正确
  
  ```python
  # 测试用例
  def test_table_extraction():
      markdown = """
      ### 6.4 减额交清对比表
      
      | 保单年度 | 减额后年金 |
      |---------|-----------|
      | 第5年   | 1000元/年 |
      """
      
      chunker = SemanticChunker(enable_table_protection=True)
      chunks = chunker.chunk_document(markdown, "test_doc")
      
      table_chunks = [c for c in chunks if c.is_table]
      assert len(table_chunks) == 1
      assert table_chunks[0].table_data["row_count"] == 1
  ```

- [ ] **表格上下文提取**
  - [ ] 获取表格前3行作为上下文
  - [ ] 上下文包含在chunk的content中
  - [ ] 表格类型推断准确

- [ ] **表格JSON结构**
  - [ ] headers正确解析
  - [ ] rows正确解析
  - [ ] row_count和column_count准确
  - [ ] 复杂表格（合并单元格）处理

- [ ] **与文本chunk合并**
  - [ ] 按chunk_index排序
  - [ ] 保持原文顺序
  - [ ] 表格占位符正确移除

### 验收测试

- [ ] **功能测试**
  - [ ] 表格chunk的is_table标记100%准确
  - [ ] 表格JSON完整性100%
  - [ ] 复杂表格（减额交清表）正确解析
  - [ ] 表格上下文正确提取

- [ ] **对比测试**
  - [ ] 对比启用vs未启用表格保护
  - [ ] 验证表格信息不丢失

- [ ] **集成测试**
  - [ ] 与T023（索引器）集成
  - [ ] 表格chunk能正确存入ChromaDB
  - [ ] 表格metadata能正确过滤

- [ ] **更新tasks.md**
  - [ ] 将T023a标记为 `[x]`
  - [ ] 记录表格处理的特殊案例

---

## 📋 第五步：T025a - MCP工具重设计

### 任务前检查

- [ ] 已完成T022a（混合检索）
- [ ] 已完成T023a（表格处理）
- [ ] 已完成T023（ChromaDB索引）
- [ ] 已阅读用户建议的工具设计

### 实施要点

- [ ] **Tool 1: search_policy_clause**
  - [ ] SearchPolicyClauseInput模型定义
  - [ ] ClauseResult模型定义
  - [ ] SourceRef结构完整
  - [ ] 支持company/product/category过滤
  - [ ] 相似度阈值 > 0.7
  
  ```python
  # 测试用例
  @pytest.mark.asyncio
  async def test_search_policy_clause():
      result = await search_policy_clause(SearchPolicyClauseInput(
          query="保险期间多久？",
          company="平安人寿",
          top_k=5
      ))
      
      assert len(result) > 0
      assert result[0].similarity_score > 0.7
      assert result[0].source_reference is not None
  ```

- [ ] **Tool 2: check_exclusion_risk**
  - [ ] 强制过滤category="Exclusion"
  - [ ] 关键词扩展功能
  - [ ] LLM二次判断（可选）
  - [ ] 风险总结生成
  - [ ] 免责声明必须返回
  
  ```python
  # 测试用例
  @pytest.mark.asyncio
  async def test_check_exclusion():
      result = await check_exclusion_risk(CheckExclusionRiskInput(
          scenario_description="酒后骑摩托车出事"
      ))
      
      assert all(c.metadata["category"] == "Exclusion" for c in result.matched_clauses)
      assert "仅供参考" in result.disclaimer
  ```

- [ ] **Tool 3: calculate_surrender_value_logic**
  - [ ] 同时返回退保和减额交清条款
  - [ ] 提取计算规则
  - [ ] 提取条件和后果
  - [ ] 关联相关表格
  - [ ] 生成对比说明
  - [ ] 缺失提示清晰
  
  ```python
  # 测试用例
  @pytest.mark.asyncio
  async def test_surrender_logic():
      result = await calculate_surrender_value_logic(
          CalculateSurrenderValueLogicInput(
              product_id="平安福耀年金保险",
              operation="reduced_paid_up"
          )
      )
      
      assert "减额交清" in result.operation_name
      assert len(result.calculation_rules) > 0
      assert result.comparison_note is not None
  ```

- [ ] **MCP Server集成**
  - [ ] list_tools()返回3个工具
  - [ ] call_tool()正确路由
  - [ ] 错误处理完善
  - [ ] 日志记录详细

### 验收测试

- [ ] **功能测试**
  - [ ] 3个工具都能响应
  - [ ] 返回结构符合定义
  - [ ] source_reference完整

- [ ] **场景测试**
  - [ ] 基础查询："保险期间多久？"
  - [ ] 免责查询："酒驾赔吗？"
  - [ ] 对比查询："退保vs减额交清？"

- [ ] **Claude Desktop测试**（如可用）
  - [ ] MCP服务器能连接
  - [ ] Claude能调用工具
  - [ ] 返回结果Claude能理解

- [ ] **更新contracts/**
  - [ ] 补充OpenAPI规范
  - [ ] 更新工具文档

- [ ] **更新tasks.md**
  - [ ] 将T025a标记为 `[x]`
  - [ ] 记录工具使用示例

---

## 📋 第六步：T028a - 黄金测试集

### 任务前检查

- [ ] 已完成T025a（MCP工具）
- [ ] 已完成所有前置索引任务
- [ ] 理解分层测试标准（SC-003）

### 实施要点

- [ ] **数据集构建**
  - [ ] 至少50个问题
  - [ ] 基础查询20个
  - [ ] 对比查询15个
  - [ ] 免责查询15个
  - [ ] 每个问题有ground truth标注
  - [ ] JSON格式规范

- [ ] **测试脚本实现**
  - [ ] test_basic_queries()
  - [ ] test_comparison_queries()
  - [ ] test_exclusion_queries()
  - [ ] 使用MRR和NDCG@k指标
  - [ ] 生成测试报告

- [ ] **持续评估机制**
  - [ ] 每月运行一次
  - [ ] 记录趋势数据
  - [ ] 失败案例分析

### 验收测试

- [ ] **数据质量检查**
  - [ ] 所有问题都有完整的ground truth
  - [ ] 问题覆盖主要使用场景
  - [ ] 标注准确性人工复核

- [ ] **测试执行**
  ```bash
  pytest tests/golden_dataset/test_retrieval_quality.py -v
  ```
  - [ ] 基础查询准确率 ≥ 90%
  - [ ] 对比查询准确率 ≥ 85%
  - [ ] 免责查询召回率 ≥ 95%

- [ ] **报告生成**
  - [ ] 测试报告清晰
  - [ ] 失败案例有详细说明
  - [ ] 改进建议明确

- [ ] **更新tasks.md**
  - [ ] 将T028a标记为 `[x]`
  - [ ] 记录测试结果和趋势

---

## 📋 第七步：端到端集成测试

### 集成测试场景

- [ ] **场景1：完整流程测试**
  ```bash
  # 1. 采集新产品
  python -m src.cli.manage crawl run --company pingan-life --limit 1
  
  # 2. 转换PDF
  python -m src.cli.manage process convert --all
  
  # 3. 审核
  python -m src.cli.verify approve <doc_id> --notes "测试"
  
  # 4. 后处理
  python -m src.cli.manage process postprocess --all
  
  # 5. 索引
  python -m src.cli.manage index --rebuild --enable-bm25
  
  # 6. 测试检索
  python -m src.cli.manage index test-search "保险期间" --method hybrid
  
  # 7. 启动MCP服务器
  python -m src.mcp_server.server
  ```

- [ ] **场景2：用户提供的CFO Agent场景**
  - [ ] 用户问："我想把这个保险做减额交清，划算吗？"
  - [ ] Agent调用calculate_surrender_value_logic
  - [ ] 返回减额交清定义、计算规则、对比说明
  - [ ] 用户能理解并做出决策

- [ ] **场景3：免责核查场景**
  - [ ] 用户问："酒驾出事赔吗？"
  - [ ] Agent调用check_exclusion_risk
  - [ ] 强制检索免责条款
  - [ ] 返回明确的免责判断

### 性能测试

- [ ] **索引性能**
  - [ ] 100份文档索引时间 < 30分钟
  - [ ] ChromaDB大小合理（< 500MB）
  - [ ] BM25索引大小合理（< 100MB）

- [ ] **检索性能**
  - [ ] 单次查询响应 < 2秒
  - [ ] 并发10个查询无性能下降
  - [ ] 内存占用稳定（< 1GB）

- [ ] **准确性验证**
  - [ ] 黄金测试集全部通过
  - [ ] 真实用户查询测试（如可用）

### 回归测试

- [ ] **前期功能不受影响**
  - [ ] T001-T019所有功能仍可用
  - [ ] 数据库schema兼容
  - [ ] 文件结构未破坏

- [ ] **文档一致性**
  - [ ] README.md准确反映新功能
  - [ ] quickstart.md步骤可执行
  - [ ] 所有API文档与实现一致

---

## 📋 第八步：上线前检查

### 代码质量

- [ ] **测试覆盖率**
  ```bash
  pytest --cov=src tests/ --cov-report=html
  ```
  - [ ] 核心模块覆盖率 > 80%
  - [ ] 关键路径覆盖率 = 100%

- [ ] **代码review**
  - [ ] 所有CRITICAL问题已修复
  - [ ] 所有HIGH问题已修复
  - [ ] MEDIUM问题已有跟踪Issue

- [ ] **Linting**
  ```bash
  ruff check src/ tests/
  mypy src/
  ```
  - [ ] 无错误
  - [ ] 警告已处理

### 文档完整性

- [ ] **用户文档**
  - [ ] README.md更新
  - [ ] quickstart.md更新
  - [ ] 新增MCP工具使用指南
  - [ ] 新增混合检索说明

- [ ] **开发文档**
  - [ ] spec.md已更新
  - [ ] tasks.md已更新
  - [ ] data-model.md已更新
  - [ ] 架构图已更新

- [ ] **运维文档**
  - [ ] 部署指南
  - [ ] 监控方案
  - [ ] 故障排查手册

### 部署准备

- [ ] **环境配置**
  - [ ] .env.example已更新
  - [ ] requirements.txt已更新
  - [ ] Docker镜像已构建（如需要）

- [ ] **数据备份**
  - [ ] SQLite数据库已备份
  - [ ] ChromaDB已备份
  - [ ] 原始PDF已备份

- [ ] **监控就绪**
  - [ ] 日志级别配置合理
  - [ ] 关键指标已定义
  - [ ] 告警规则已设置

---

## 📋 总结报告模板

完成所有步骤后，生成实施报告：

```markdown
# 第五阶段实施报告

## 实施时间
- 开始时间: YYYY-MM-DD
- 结束时间: YYYY-MM-DD
- 总耗时: X工作日

## 完成任务
- [x] T020a - Markdown后处理
- [x] T022a - 混合检索
- [x] T023a - 表格独立Chunk
- [x] T025a - MCP工具重设计
- [x] T028a - 黄金测试集

## 关键指标
- 检索准确率提升: +X%
- 响应时间: X秒
- 黄金测试集通过率: X%

## 已修复CRITICAL问题
- C1: 切片策略明确（MarkdownHeaderSplitter）
- C2: 元数据字段扩充（8个新字段）
- C3: 表格完整性保护（独立chunk）
- C4: 混合检索实现（BM25 + Vector）

## 遗留问题
- （列出MEDIUM和LOW问题）

## 下一步建议
- （后续优化方向）
```

---

**检查清单完成。祝实施顺利！🚀**

