# 质量核对清单：保险数据准确性与合规性 (Data Accuracy & Compliance)

**目的**: 验证需求是否确保了保险数据的绝对准确性、来源可追溯性及爬虫操作的法律合规性。
**创建时间**: 2025-11-20
**功能**: [specs/001-insurance-mcp-core/spec.md](../spec.md)

## 1. 数据准确性需求 (Requirement Quality: Accuracy)

- [ ] 是否明确定义了"准确性"的可衡量标准（例如：SC-004 中的 100% 表格还原率）？ [Clarity, Spec §SC-004]
- [ ] 是否规定了 OCR 置信度低时的具体处理流程？ [Completeness, Spec §EC-002]
- [ ] 是否对双栏排版解析的阅读顺序还原提出了明确要求？ [Clarity, Spec §FR-004]
- [ ] 是否定义了人工审核员"核验 (Verified)"操作的具体验收标准？ [Clarity, Spec §FR-005]
- [ ] 是否明确要求 MCP 返回结果必须包含精确到章节的来源引用？ [Completeness, Spec §User Story 1]

## 2. 合规性与风控需求 (Requirement Quality: Compliance)

- [x] 是否明确禁止爬取特定的隐私敏感路径（如保单查询、用户中心）？ [Coverage, Spec §EC-004] - 已在EC-004中明确
- [x] 是否对爬虫的 QPS (每秒请求数) 设定了具体的全局上限？ [Clarity, Spec §FR-008] - 已实现：全局QPS=0.8 < 1，可通过环境变量配置
- [x] 是否明确了 Robots 协议的遵守原则及例外情况（如果存在）？ [Completeness, Spec §FR-008] - 已在FR-008中规定
- [x] 是否定义了触发反爬封锁时的熔断与退避机制？ [Completeness, Spec §EC-003] - 已实现：429/403触发熔断，5分钟冷却
- [x] 是否规定了数据源（PDF 原文件）的持久化存储与哈希校验要求？ [Traceability, Spec §FR-007] - 已实现：所有PDF保存并计算SHA-256

## 3. 系统行为与流程 (Requirement Quality: Workflow)

- [ ] 是否完整定义了"发现层"与"采集层"在分层爬虫架构中的职责边界？ [Clarity, Spec §FR-003]
- [ ] 是否明确了从 IAC 失败回退到官网的自动重试逻辑？ [Coverage, Spec §User Story 3]
- [ ] 是否定义了加密 PDF 无法解密时的异常处理流程？ [Edge Case, Spec §EC-001]
- [ ] 是否规定了仅索引"已核验"文档的强制性约束？ [Consistency, Spec §FR-006]

## 4. 验收标准质量 (Acceptance Criteria Quality)

- [ ] "100% 来源核验"的成功标准是否具备可验证的技术手段？ [Measurability, Spec §SC-001]
- [ ] "90% 检索准确率"的测试集（50 个黄金问题）是否已定义或有计划定义？ [Measurability, Spec §SC-003]
- [ ] 爬虫"24小时内发现新文件"的时效性指标是否在当前架构下可实现？ [Feasibility, Spec §SC-002]

## 备注

- 此清单用于验证需求规格书本身的质量，而非测试系统实现。
- 重点关注：**准确性**（Accuracy Over Everything）与 **合规性**（Legal Compliance）。

