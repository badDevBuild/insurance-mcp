# Markdown结构化增强补丁

## 🎯 目标

将markitdown生成的"纯文本式Markdown"转换为**真正结构化的Markdown**，提升：
1. 向量检索效果（标题层级 → 更准确的section_id）
2. 人工阅读体验（格式化 → 更易读）
3. 切片质量（结构化 → 更精准的chunk边界）

---

## 问题根源

**markitdown的输出特点**：
- ✅ 能提取完整文本内容
- ✅ 能识别表格结构
- ❌ 不进行语义层级分析（不知道哪些是标题）
- ❌ 不处理格式细节（列表、强调、脚注）

**需要补充**：基于保险条款的**领域知识**进行结构化。

---

## 解决方案：MarkdownEnhancer

### 架构设计

```python
# src/parser/markdown/enhancer.py

class MarkdownEnhancer:
    """
    Markdown结构化增强器
    
    在markitdown的基础上，根据保险条款的特征进行结构化处理
    """
    
    def __init__(self):
        self.title_detector = TitleDetector()
        self.list_formatter = ListFormatter()
        self.footnote_processor = FootnoteProcessor()
        self.paragraph_merger = ParagraphMerger()
        self.emphasis_marker = EmphasisMarker()
    
    def enhance(self, raw_markdown: str) -> str:
        """
        增强Markdown结构
        
        处理顺序很重要！
        """
        text = raw_markdown
        
        # 1. 合并断行段落（必须最先做）
        text = self.paragraph_merger.merge(text)
        
        # 2. 识别并格式化标题
        text = self.title_detector.detect_and_format(text)
        
        # 3. 格式化列表
        text = self.list_formatter.format(text)
        
        # 4. 处理脚注
        text = self.footnote_processor.inline(text)
        
        # 5. 添加强调标记
        text = self.emphasis_marker.mark(text)
        
        return text
```

---

## 模块1: TitleDetector（标题检测器）

### 核心逻辑

保险条款的标题有明确的模式：

```python
class TitleDetector:
    """
    基于规则的标题检测器
    
    规则：
    1. 章节编号（如"1. 我们保什么"）→ # 一级标题
    2. 条款编号（如"1.1 保险金额"）→ ## 二级标题
    3. 子条款（如"1.2.1 首个养老保险金"）→ ### 三级标题
    4. 特殊标题（如"阅读指引"、"条款目录"）→ ## 二级标题
    """
    
    # 标题模式
    PATTERNS = {
        'chapter': r'^(\d+)\.\s*(.+)$',              # 1. 我们保什么
        'clause': r'^(\d+\.\d+)\s+(.+)$',            # 1.1 保险金额
        'subclause': r'^(\d+\.\d+\.\d+)\s+(.+)$',    # 1.2.1 首个养老保险金
        'special': r'^(阅读指引|条款目录|险种简称|险种代码|您拥有的重要权益|您应当特别注意的事项)$'
    }
    
    def detect_and_format(self, text: str) -> str:
        """检测标题并格式化"""
        lines = text.split('\n')
        result = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # 跳过空行
            if not stripped:
                result.append(line)
                continue
            
            # 检测各类标题
            formatted = self._try_format_title(stripped, i, lines)
            result.append(formatted if formatted else line)
        
        return '\n'.join(result)
    
    def _try_format_title(self, line: str, index: int, all_lines: list) -> Optional[str]:
        """尝试将行格式化为标题"""
        
        # 1. 三级条款（最具体，先匹配）
        match = re.match(self.PATTERNS['subclause'], line)
        if match:
            number, title = match.groups()
            return f"### {number} {title}"
        
        # 2. 二级条款
        match = re.match(self.PATTERNS['clause'], line)
        if match:
            number, title = match.groups()
            # 排除表格中的数字（如"1.2 万元"）
            if not self._is_in_table(index, all_lines):
                return f"## {number} {title}"
        
        # 3. 一级章节
        match = re.match(self.PATTERNS['chapter'], line)
        if match:
            number, title = match.groups()
            # 必须是完整的章节标题（如"我们保什么、保多久"）
            if len(title) > 5 and not title.replace('.', '').isdigit():
                return f"# {number}. {title}"
        
        # 4. 特殊标题
        match = re.match(self.PATTERNS['special'], line)
        if match:
            return f"## {line}"
        
        return None
    
    def _is_in_table(self, line_index: int, all_lines: list) -> bool:
        """判断是否在表格中"""
        # 向上和向下各看3行
        start = max(0, line_index - 3)
        end = min(len(all_lines), line_index + 4)
        
        for i in range(start, end):
            if '|' in all_lines[i]:  # Markdown表格标记
                return True
        
        return False


# 测试用例
def test_title_detector():
    detector = TitleDetector()
    
    input_text = """
阅读指引

平安颐享天年养老年金保险（分红型）产品...

 我们保什么、保多久

这部分讲的是我们提供的保障...

1.1 保险金额

本合同基本保险金额...

1.2.1 首个养老保险金

领取日
"""
    
    expected = """
## 阅读指引

平安颐享天年养老年金保险（分红型）产品...

# 1. 我们保什么、保多久

这部分讲的是我们提供的保障...

## 1.1 保险金额

本合同基本保险金额...

### 1.2.1 首个养老保险金

领取日
"""
    
    result = detector.detect_and_format(input_text)
    assert result.strip() == expected.strip()
```

---

## 模块2: ParagraphMerger（段落合并器）

### 核心逻辑

解决不必要的断行问题：

```python
class ParagraphMerger:
    """
    段落合并器
    
    问题：
    本合同基本保险金额由您和我们在投保时约定并在保险单上载明。若该金额发生

    变更，则以变更后的金额为基本保险金额。
    
    应该是：
    本合同基本保险金额由您和我们在投保时约定并在保险单上载明。若该金额发生变更，则以变更后的金额为基本保险金额。
    """
    
    def merge(self, text: str) -> str:
        """合并不必要的断行"""
        lines = text.split('\n')
        result = []
        buffer = []
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # 空行：输出buffer并重置
            if not stripped:
                if buffer:
                    result.append(' '.join(buffer))
                    buffer = []
                result.append('')
                continue
            
            # 判断是否应该合并
            if self._should_merge(stripped, buffer, i, lines):
                buffer.append(stripped)
            else:
                # 输出之前的buffer
                if buffer:
                    result.append(' '.join(buffer))
                    buffer = []
                # 开始新的buffer
                buffer.append(stripped)
        
        # 输出最后的buffer
        if buffer:
            result.append(' '.join(buffer))
        
        return '\n'.join(result)
    
    def _should_merge(self, line: str, buffer: list, index: int, all_lines: list) -> bool:
        """判断是否应该与前一行合并"""
        
        # 没有buffer，不合并
        if not buffer:
            return False
        
        # 如果是标题（数字开头），不合并
        if re.match(r'^\d+\.', line):
            return False
        
        # 如果是列表项（• 或 - 开头），不合并
        if re.match(r'^[•\-\*]\s', line):
            return False
        
        # 如果是表格行（包含|），不合并
        if '|' in line:
            return False
        
        # 如果buffer的最后一行是完整句子（以。！？结尾），不合并
        last_line = buffer[-1]
        if last_line.endswith(('。', '！', '？', '：')):
            return False
        
        # 否则，合并
        return True


# 测试用例
def test_paragraph_merger():
    merger = ParagraphMerger()
    
    input_text = """
本合同基本保险金额由您和我们在投保时约定并在保险单上载明。若该金额发生

变更，则以变更后的金额为基本保险金额。

在本合同保险期间内，您可以向我们申请减少基本保险金额。
"""
    
    expected = """
本合同基本保险金额由您和我们在投保时约定并在保险单上载明。若该金额发生变更，则以变更后的金额为基本保险金额。

在本合同保险期间内，您可以向我们申请减少基本保险金额。
"""
    
    result = merger.merge(input_text)
    assert result == expected
```

---

## 模块3: ListFormatter（列表格式化器）

### 核心逻辑

识别列表项并格式化：

```python
class ListFormatter:
    """
    列表格式化器
    
    识别模式：
    1. "被保险人就是..."、"投保人就是..." → 定义列表
    2. "（1）..."、"（2）..." → 编号列表
    3. "条件："后跟多行 → 无序列表
    """
    
    def format(self, text: str) -> str:
        """格式化列表"""
        lines = text.split('\n')
        result = []
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # 检测定义列表（如"被保险人就是..."）
            if self._is_definition_item(line):
                formatted = self._format_definition(line)
                result.append(formatted)
                i += 1
                continue
            
            # 检测编号列表（如"（1）..."）
            if self._is_numbered_item(line):
                # 收集连续的编号项
                numbered_items = []
                while i < len(lines) and self._is_numbered_item(lines[i].strip()):
                    numbered_items.append(lines[i].strip())
                    i += 1
                # 格式化为Markdown列表
                for item in numbered_items:
                    formatted = self._format_numbered_item(item)
                    result.append(formatted)
                continue
            
            # 检测条件列表（"需要同时满足如下条件："）
            if '满足如下条件' in line or '需要满足' in line:
                result.append(line)
                result.append('')  # 空行
                i += 1
                # 下面的项应该是列表
                while i < len(lines) and self._is_condition_item(lines[i]):
                    item = lines[i].strip()
                    result.append(f"- {item}")
                    i += 1
                continue
            
            # 普通行
            result.append(lines[i])
            i += 1
        
        return '\n'.join(result)
    
    def _is_definition_item(self, line: str) -> bool:
        """是否为定义项"""
        patterns = [
            r'^(\s+)?被保险人就是',
            r'^(\s+)?投保人就是',
            r'^(\s+)?受益人就是',
            r'^(\s+)?保险人就是',
        ]
        return any(re.match(p, line) for p in patterns)
    
    def _format_definition(self, line: str) -> str:
        """格式化定义项"""
        # "被保险人就是受保险合同保障的人。"
        # → "- **被保险人**：受保险合同保障的人"
        match = re.match(r'^\s*(.+?)就是(.+?)。?$', line)
        if match:
            term, definition = match.groups()
            return f"- **{term.strip()}**：{definition.strip()}"
        return f"- {line}"
    
    def _is_numbered_item(self, line: str) -> bool:
        """是否为编号列表项（如"（1）..."）"""
        return bool(re.match(r'^（\d+）', line))
    
    def _format_numbered_item(self, line: str) -> str:
        """格式化编号项"""
        # "（1）在本合同生效后..." → "1. 在本合同生效后..."
        match = re.match(r'^（(\d+)）\s*(.+)$', line)
        if match:
            number, content = match.groups()
            return f"{number}. {content}"
        return line
    
    def _is_condition_item(self, line: str) -> bool:
        """是否为条件项（通常以"（1）"开头或缩进）"""
        return self._is_numbered_item(line.strip()) or line.startswith('  ')


# 测试用例
def test_list_formatter():
    formatter = ListFormatter()
    
    input_text = """
 被保险人就是受保险合同保障的人。
 投保人就是购买保险并交纳保险费的人。
 受益人就是发生保险事故后享有保险金请求权的人。

需要同时满足如下条件：
（1）在本合同生效后的首个保单周年日当日被保险人的年龄不小于...
（2）在本合同生效后的首个保单周年日当日，男性被保险人不小于 60 周岁...
"""
    
    expected = """
- **被保险人**：受保险合同保障的人
- **投保人**：购买保险并交纳保险费的人
- **受益人**：发生保险事故后享有保险金请求权的人

需要同时满足如下条件：

- 1. 在本合同生效后的首个保单周年日当日被保险人的年龄不小于...
- 2. 在本合同生效后的首个保单周年日当日，男性被保险人不小于 60 周岁...
"""
    
    result = formatter.format(input_text)
    # 验证列表项存在
    assert '- **被保险人**：' in result
    assert '1. 在本合同生效后' in result
```

---

## 模块4: EmphasisMarker（强调标记器）

### 核心逻辑

为重要内容添加强调：

```python
class EmphasisMarker:
    """
    强调标记器
    
    规则：
    1. "免除保险人责任" → **免除保险人责任**
    2. "请您务必" → **请您务必**
    3. 金额数字 → 加粗
    """
    
    IMPORTANT_PHRASES = [
        '免除保险人责任',
        '责任免除',
        '请您务必',
        '特别注意',
        '不承担',
        '我们不',
        '犹豫期',
        '现金价值',
        '基本保险金额',
    ]
    
    def mark(self, text: str) -> str:
        """添加强调标记"""
        result = text
        
        # 1. 重要短语加粗
        for phrase in self.IMPORTANT_PHRASES:
            # 避免重复加粗
            pattern = f'(?<!\\*){re.escape(phrase)}(?!\\*)'
            result = re.sub(pattern, f'**{phrase}**', result)
        
        # 2. 金额数字加粗（如"20%"、"60周岁"）
        # 注意：不要在已加粗的文本中再加粗
        result = re.sub(
            r'(?<!\*)\b(\d+(?:\.\d+)?%)\b(?!\*)',
            r'**\1**',
            result
        )
        
        result = re.sub(
            r'(?<!\*)\b(\d+(?:\.\d+)?\s*(?:周岁|万元|元|年|月|日))\b(?!\*)',
            r'**\1**',
            result
        )
        
        return result


# 测试用例
def test_emphasis_marker():
    marker = EmphasisMarker()
    
    input_text = """
本保险条款中背景突出的内容属于免除保险人责任的条款。

犹豫期为20日，犹豫期内您可以要求全额退还保险费。

基本保险金额减少后，本合同保险费不低于我们规定的最低标准。
"""
    
    result = marker.mark(input_text)
    
    assert '**免除保险人责任**' in result
    assert '**犹豫期**' in result
    assert '**20日**' in result
    assert '**基本保险金额**' in result
```

---

## 集成到T020a

### 更新后的处理流程

```python
# src/parser/markdown/postprocessor.py (更新)

from src.parser.markdown.enhancer import MarkdownEnhancer

class MarkdownPostProcessor:
    def __init__(self):
        self.footnote_inliner = FootnoteInliner()
        self.noise_remover = NoiseRemover()
        self.format_standardizer = FormatStandardizer()
        self.table_validator = TableValidator()
        
        # 新增：结构化增强器（放在最后）
        self.enhancer = MarkdownEnhancer()
    
    def process(self, markdown_path: Path) -> ProcessedMarkdown:
        """执行完整的后处理流程"""
        text = markdown_path.read_text(encoding='utf-8')
        
        # 阶段1: 清洗
        text = self.footnote_inliner.inline_footnotes(text)
        text = self.noise_remover.remove_noise(text)
        text = self.format_standardizer.standardize(text)
        text, table_metadata = self.table_validator.validate_tables(text)
        
        # 阶段2: 结构化增强（新增）
        text = self.enhancer.enhance(text)
        
        return ProcessedMarkdown(
            content=text,
            tables=table_metadata,
            processed_at=datetime.now()
        )
```

---

## CLI命令扩展

```bash
# 增强单个文档
python -m src.cli.manage process enhance --doc-id 067afcfc

# 批量增强所有已转换的文档
python -m src.cli.manage process enhance --all

# 对比增强前后（调试用）
python -m src.cli.manage process enhance --doc-id 067afcfc --show-diff
```

---

## 预期效果对比

### 增强前

```markdown
阅读指引

平安颐享天年养老年金保险（分红型）产品提供养老、生存、身故保障及保单红利
为了帮助您更好地了解产品，我们先介绍几个保险条款中常用的术语

 被保险人就是受保险合同保障的人。
 投保人就是购买保险并交纳保险费的人。

与您有重大利害关系的条款事关您的切身利益，请您务必仔细、认真阅读

 本保险条款中背景突出的内容属于免除保险人责任的条款。

 我们保什么、保多久

1.1 保险金额

本合同基本保险金额由您和我们在投保时约定并在保险单上载明。若该金额发生

变更，则以变更后的金额为基本保险金额。

1.2.1 首个养老保险金

领取日

在符合约定条件的情况下，您可在投保时与我们约定...

1.若您选择以本合同生效后的首个保单周年日作为首个养老保险金领取日，则需

要同时满足如下条件：

（1）在本合同生效后的首个保单周年日当日被保险人的年龄不小于...

（2）在本合同生效后的首个保单周年日当日，男性被保险人不小于 60 周岁...
```

### 增强后

```markdown
## 阅读指引

平安颐享天年养老年金保险（分红型）产品提供养老、生存、身故保障及保单红利。为了帮助您更好地了解产品，我们先介绍几个保险条款中常用的术语：

- **被保险人**：受保险合同保障的人
- **投保人**：购买保险并交纳保险费的人
- **受益人**：发生保险事故后享有保险金请求权的人
- **保险人**：保险公司

与您有重大利害关系的条款事关您的切身利益，**请您务必**仔细、认真阅读。

> **重要提示**：本保险条款中背景突出的内容属于**免除保险人责任**的条款。

# 1. 我们保什么、保多久

## 1.1 保险金额

本合同**基本保险金额**由您和我们在投保时约定并在保险单上载明。若该金额发生变更，则以变更后的金额为基本保险金额。

### 1.2.1 首个养老保险金领取日

在符合约定条件的情况下，您可在投保时与我们约定...

**情况1**：若您选择以本合同生效后的首个保单周年日作为首个养老保险金领取日，则需要同时满足如下条件：

1. 在本合同生效后的首个保单周年日当日被保险人的年龄不小于国家法律、行政法规或其他相关规定、政策规定的被保险人退休年龄
2. 在本合同生效后的首个保单周年日当日，男性被保险人不小于 **60周岁**，女性被保险人不小于 **55周岁**

> **周岁定义**：按有效身份证件中记载的出生日期计算的年龄，自出生之日起为0周岁，每经过一年增加一岁，不足一年的不计。
```

---

## 验收标准

### 自动化测试

```python
def test_markdown_enhancement():
    """测试Markdown增强效果"""
    
    # 读取原始文档
    raw_doc = Path("data/processed/02d8c86f-d84e-4058-a2ee-9617e135ef44.md")
    raw_text = raw_doc.read_text()
    
    # 应用增强
    enhancer = MarkdownEnhancer()
    enhanced_text = enhancer.enhance(raw_text)
    
    # 验证标题层级
    assert '# 1. 我们保什么、保多久' in enhanced_text
    assert '## 1.1 保险金额' in enhanced_text
    assert '### 1.2.1 首个养老保险金' in enhanced_text
    
    # 验证列表格式
    assert '- **被保险人**：' in enhanced_text
    assert '1. 在本合同生效后' in enhanced_text
    
    # 验证强调标记
    assert '**免除保险人责任**' in enhanced_text
    assert '**犹豫期**' in enhanced_text
    
    # 验证段落合并（无不必要的断行）
    assert '\n\n变更' not in enhanced_text
```

### 人工检查

- [ ] 标题层级正确（#, ##, ###）
- [ ] 列表结构清晰（-, 1.）
- [ ] 重要内容加粗
- [ ] 段落连贯（无不必要断行）
- [ ] 脚注内联或格式化
- [ ] 阅读体验提升

---

## 优先级建议

### 方案A：立即实施（推荐）

**理由**：
- Markdown质量直接影响切片效果（T023）
- 影响section_id提取准确性（T020a中的元数据提取）
- 影响用户阅读体验（审核员CLI）

**实施顺序**：
1. 先实施ParagraphMerger（最简单，效果明显）
2. 再实施TitleDetector（最重要，影响section_id）
3. 然后ListFormatter（提升可读性）
4. 最后EmphasisMarker（锦上添花）

### 方案B：延后实施

**理由**：
- 当前Markdown虽然不美观，但内容完整
- 可以先完成第五阶段核心功能
- 后续作为优化项迭代

---

## 工作量估算

| 模块 | 代码量 | 测试 | 总计 |
|-----|-------|------|------|
| ParagraphMerger | 0.5天 | 0.5天 | 1天 |
| TitleDetector | 1天 | 0.5天 | 1.5天 |
| ListFormatter | 1天 | 0.5天 | 1.5天 |
| EmphasisMarker | 0.5天 | 0.5天 | 1天 |
| 集成测试 | - | 1天 | 1天 |
| **总计** | - | - | **6天** |

---

## 与已有方案的关系

这个增强模块是对**已生成的T020a（Markdown后处理）**的扩展：

```
T020a原方案:
├── FootnoteInliner      (脚注内联)
├── NoiseRemover         (噪音去除)
├── FormatStandardizer   (格式标准化)
└── TableValidator       (表格验证)

T020a扩展:
└── MarkdownEnhancer     ← 新增（本补丁）
    ├── ParagraphMerger
    ├── TitleDetector
    ├── ListFormatter
    └── EmphasisMarker
```

两者是**串行关系**：
1. 先执行清洗（T020a原方案）
2. 再执行增强（本补丁）

---

## 建议

### 立即行动

✅ **推荐将此补丁集成到优化包中**

理由：
1. **成本低**：只需6天，相对20天的第五阶段开发，占比30%
2. **收益高**：
   - 提升section_id提取准确性 → 影响混合检索效果
   - 提升阅读体验 → 审核员工作效率
   - 提升切片质量 → 向量检索准确率
3. **风险低**：
   - 不影响现有功能
   - 可以增量rollout（先测试ParagraphMerger）
   - 如有问题可以回退到原始Markdown

### 分阶段实施

**Phase 1**（2天）：
- ParagraphMerger + TitleDetector
- 验证效果后决定是否继续

**Phase 2**（2天）：
- ListFormatter + EmphasisMarker

**Phase 3**（2天）：
- 集成测试 + 批量处理现有文档

---

**本补丁完成。建议将其作为T020a的扩展模块。** 🎯

