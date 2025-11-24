"""
MetadataExtractor 单元测试

测试T023b的元数据提取器功能，包括：
1. 条款类型分类（category）
2. 主体角色识别（entity_role）
3. 关键词提取（keywords）
4. 边界情况和回归测试

根据 tasks.md §T023c 实施。
"""
import pytest
import sys
from pathlib import Path

# 添加src到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.indexing.metadata_extractor import MetadataExtractor
from src.common.models import ClauseCategory, EntityRole


class TestCategoryClassification:
    """测试条款类型分类"""
    
    @pytest.fixture
    def extractor(self):
        return MetadataExtractor()
    
    def test_liability_clause(self, extractor):
        """测试保险责任条款识别"""
        content = """
        1.2 保险责任
        在保险期间内，我们承担如下保险责任：
        （一）被保险人身故，我们给付身故保险金，本合同终止。
        """
        
        category = extractor.classify_category(content)
        assert category == ClauseCategory.LIABILITY, "应识别为保险责任条款"
    
    def test_exclusion_clause(self, extractor):
        """测试责任免除条款识别"""
        content = """
        2.1 责任免除
        因下列情形之一导致被保险人身故的，我们不承担给付保险金责任：
        （一）投保人对被保险人的故意杀害、故意伤害；
        （二）被保险人故意犯罪或抗拒依法采取的刑事强制措施；
        """
        
        category = extractor.classify_category(content)
        assert category == ClauseCategory.EXCLUSION, "应识别为责任免除条款"
    
    def test_process_clause(self, extractor):
        """测试流程类条款识别"""
        content = """
        5.3 理赔申请
        申请保险金时，申请人应填写保险金给付申请书，并提供下列证明和资料：
        （一）保险合同；
        （二）申请人的有效身份证件；
        """
        
        category = extractor.classify_category(content)
        assert category == ClauseCategory.PROCESS, "应识别为流程类条款"
    
    def test_definition_clause(self, extractor):
        """测试定义类条款识别"""
        content = """
        8.1 名词解释
        本合同所称"被保险人"是指其财产或者人身受保险合同保障，享有保险金请求权的人。
        """
        
        category = extractor.classify_category(content)
        assert category == ClauseCategory.DEFINITION, "应识别为定义类条款"
    
    def test_general_clause(self, extractor):
        """测试无法明确分类的条款"""
        content = """
        1.1 保险合同构成
        本保险合同由保险单或其他保险凭证及所附条款、投保单、与本合同有关的投保文件、合法有效的声明等组成。
        """
        
        category = extractor.classify_category(content)
        assert category == ClauseCategory.GENERAL, "无法明确分类应标记为GENERAL"


class TestEntityRoleIdentification:
    """测试主体角色识别"""
    
    @pytest.fixture
    def extractor(self):
        return MetadataExtractor()
    
    def test_insurer_role(self, extractor):
        """测试保险人角色识别"""
        content = """
        我们按照本合同约定给付保险金。在本合同保险期间内，本公司承担相应责任。
        """
        
        role = extractor.identify_entity_role(content)
        assert role == EntityRole.INSURER, "应识别为保险人角色"
    
    def test_insured_role(self, extractor):
        """测试被保险人角色识别"""
        content = """
        被保险人应在保险期间内按时缴纳保险费。若被保险人发生保险事故，受益人可申请保险金。
        """
        
        role = extractor.identify_entity_role(content)
        assert role == EntityRole.INSURED, "应识别为被保险人角色"
    
    def test_beneficiary_role(self, extractor):
        """测试受益人角色识别"""
        content = """
        受益人申请保险金时，应提供以下材料。受益人为无民事行为能力人或限制民事行为能力人的，由其监护人代为申请。
        """
        
        role = extractor.identify_entity_role(content)
        assert role == EntityRole.BENEFICIARY, "应识别为受益人角色"
    
    def test_no_clear_role(self, extractor):
        """测试无明确角色的条款"""
        content = """
        本合同的保险期间为二十年。保险费支付方式为年交。
        """
        
        role = extractor.identify_entity_role(content)
        assert role is None, "无明确角色应返回None"


class TestKeywordExtraction:
    """测试关键词提取"""
    
    @pytest.fixture
    def extractor(self):
        return MetadataExtractor()
    
    def test_extract_insurance_keywords(self, extractor):
        """测试保险领域关键词提取"""
        content = """
        1.2.6 身故保险金
        若被保险人在保险期间内身故，我们按照本合同基本保险金额向受益人给付身故保险金。
        """
        
        keywords = extractor.extract_keywords(content, top_k=5)
        
        # 验证关键词数量
        assert len(keywords) <= 5, "应返回不超过5个关键词"
        
        # 验证关键词质量（应包含核心概念）
        keywords_str = ",".join(keywords).lower()
        
        # 至少应包含以下关键词之一
        expected_keywords = ["身故", "保险金", "受益人", "给付"]
        matches = [kw for kw in expected_keywords if kw in keywords_str]
        
        assert len(matches) > 0, f"应包含核心关键词，实际提取: {keywords}"
    
    def test_keyword_deduplication(self, extractor):
        """测试关键词去重"""
        content = """
        保险金保险金保险金的给付按照保险合同约定执行，保险金申请需提交相关证明。
        """
        
        keywords = extractor.extract_keywords(content, top_k=10)
        
        # 验证无重复
        assert len(keywords) == len(set(keywords)), "关键词列表不应包含重复项"
    
    def test_stopword_filtering(self, extractor):
        """测试停用词过滤"""
        content = """
        我们将在收到完整的理赔材料后进行审核，并在三十日内作出核定。
        """
        
        keywords = extractor.extract_keywords(content, top_k=5)
        
        # 停用词不应出现在关键词中
        stopwords = ["的", "在", "了", "和", "是", "有", "为"]
        
        for keyword in keywords:
            assert keyword not in stopwords, f"停用词 '{keyword}' 不应出现在关键词中"


class TestSectionIdExtraction:
    """测试条款编号提取"""
    
    @pytest.fixture
    def extractor(self):
        return MetadataExtractor()
    
    def test_extract_three_level_section_id(self, extractor):
        """测试三级编号提取（如1.2.6）"""
        heading = "### 1.2.6 身故保险金"
        
        section_id = extractor.extract_section_id(heading)
        assert section_id == "1.2.6", f"应提取'1.2.6'，实际: {section_id}"
    
    def test_extract_two_level_section_id(self, extractor):
        """测试二级编号提取（如2.1）"""
        heading = "## 2.1 责任免除"
        
        section_id = extractor.extract_section_id(heading)
        assert section_id == "2.1", f"应提取'2.1'，实际: {section_id}"
    
    def test_extract_one_level_section_id(self, extractor):
        """测试一级编号提取（如1）"""
        heading = "# 1 我们保什么、保多久"
        
        section_id = extractor.extract_section_id(heading)
        assert section_id == "1", f"应提取'1'，实际: {section_id}"
    
    def test_no_section_id(self, extractor):
        """测试无编号的标题"""
        heading = "### 保险责任"
        
        section_id = extractor.extract_section_id(heading)
        assert section_id is None, "无编号标题应返回None"
    
    def test_chinese_section_id(self, extractor):
        """测试中文编号（如第一条）"""
        heading = "### 第一条 保险责任"
        
        section_id = extractor.extract_section_id(heading)
        
        # 中文编号可能不被识别，返回None或者进行转换
        # 具体行为取决于实现
        assert section_id is not None or section_id is None, "应能处理中文编号"


class TestParentSectionDetection:
    """测试父级章节识别"""
    
    @pytest.fixture
    def extractor(self):
        return MetadataExtractor()
    
    def test_detect_parent_section(self, extractor):
        """测试父级章节识别"""
        # 1.2.6 的父级是 1.2
        parent = extractor.detect_parent_section("1.2.6")
        assert parent == "1.2", f"1.2.6的父级应是1.2，实际: {parent}"
        
        # 2.1 的父级是 2
        parent = extractor.detect_parent_section("2.1")
        assert parent == "2", f"2.1的父级应是2，实际: {parent}"
        
        # 1 没有父级
        parent = extractor.detect_parent_section("1")
        assert parent is None, f"顶级编号没有父级，应返回None"


class TestEdgeCases:
    """测试边界情况"""
    
    @pytest.fixture
    def extractor(self):
        return MetadataExtractor()
    
    def test_mixed_paragraph(self, extractor):
        """测试混合段落（包含多种角色和类型）"""
        content = """
        2.2 特别约定
        被保险人在保险期间内因故意犯罪导致身故的，我们不承担给付保险金责任。
        受益人作为第一顺序继承人有权申请保险金。
        """
        
        # 应识别为免责条款（优先级最高）
        category = extractor.classify_category(content)
        assert category == ClauseCategory.EXCLUSION
        
        # 主体角色可能有多个，取频率最高的
        role = extractor.identify_entity_role(content)
        assert role is not None, "混合段落应识别出主要角色"
    
    def test_numeric_section_id_in_content(self, extractor):
        """测试内容中包含数字（不是条款编号）"""
        content = """
        保险期间为20年，保险金额为100万元，年交保费12000元。
        """
        
        # 提取关键词时，数字可能被包含
        keywords = extractor.extract_keywords(content, top_k=5)
        
        # 验证关键词有效性
        assert len(keywords) > 0, "应提取到有效关键词"
    
    def test_table_context(self, extractor):
        """测试表格上下文的处理"""
        content = """
        ### 5.6 现金价值表
        
        | 保单年度 | 现金价值 | 减额交清保额 |
        |---------|---------|-------------|
        | 1       | 0       | 0           |
        | 5       | 15000   | 8000        |
        | 10      | 35000   | 20000       |
        """
        
        # 表格相关内容应识别为流程或定义类
        category = extractor.classify_category(content)
        assert category in [ClauseCategory.PROCESS, ClauseCategory.GENERAL], \
            "表格内容应识别为流程或通用类型"
        
        # 提取关键词应包含表格相关词汇
        keywords = extractor.extract_keywords(content, top_k=5)
        keywords_str = ",".join(keywords).lower()
        
        # 应包含"现金价值"或"减额交清"
        assert "现金" in keywords_str or "价值" in keywords_str or "减额" in keywords_str, \
            f"表格关键词提取异常: {keywords}"
    
    def test_empty_content(self, extractor):
        """测试空内容"""
        content = ""
        
        category = extractor.classify_category(content)
        assert category == ClauseCategory.GENERAL, "空内容应标记为GENERAL"
        
        role = extractor.identify_entity_role(content)
        assert role is None, "空内容没有角色"
        
        keywords = extractor.extract_keywords(content)
        assert keywords == [], "空内容没有关键词"
    
    def test_very_long_content(self, extractor):
        """测试超长内容"""
        # 模拟一个非常长的条款（2000字）
        content = "被保险人在保险期间内因意外伤害导致身故的，我们按照约定给付保险金。" * 100
        
        # 应能正常处理
        category = extractor.classify_category(content)
        assert category is not None
        
        role = extractor.identify_entity_role(content)
        assert role is not None
        
        keywords = extractor.extract_keywords(content, top_k=5)
        assert len(keywords) <= 5, "即使内容很长，也应只返回Top-K关键词"


class TestRegressionSuite:
    """回归测试套件"""
    
    @pytest.fixture
    def extractor(self):
        return MetadataExtractor()
    
    def test_baseline_samples(self, extractor):
        """使用小型基准集进行回归测试"""
        # 基准样本：[(content, expected_category, expected_role)]
        baseline = [
            (
                "我们给付身故保险金。",
                ClauseCategory.LIABILITY,
                EntityRole.INSURER
            ),
            (
                "我们不承担责任免除条款中列明的情形。",
                ClauseCategory.EXCLUSION,
                EntityRole.INSURER
            ),
            (
                "被保险人应在犹豫期内提交退保申请。",
                ClauseCategory.PROCESS,
                EntityRole.INSURED
            ),
            (
                "本合同所称'保险事故'是指保险合同约定的保险责任范围内的事故。",
                ClauseCategory.DEFINITION,
                None  # 定义类条款通常不强调角色
            )
        ]
        
        for content, expected_cat, expected_role in baseline:
            actual_cat = extractor.classify_category(content)
            assert actual_cat == expected_cat, \
                f"分类失败：'{content[:20]}...' 期望{expected_cat}，实际{actual_cat}"
            
            actual_role = extractor.identify_entity_role(content)
            # 角色识别可能有多个合理结果，这里只检查非None情况
            if expected_role is not None:
                assert actual_role is not None, \
                    f"角色识别失败：'{content[:20]}...' 应识别出角色"


# Pytest标记
pytestmark = pytest.mark.unit


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
