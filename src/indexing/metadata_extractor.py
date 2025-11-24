"""元数据提取器

从PolicyChunk内容中自动提取元数据，包括：
- classify_category: 条款类型分类（Liability/Exclusion/Process/Definition）
- identify_entity_role: 主体角色识别（Insurer/Insured/Beneficiary）
- extract_keywords: 关键词提取（Top-K）
- extract_section_id: 从标题提取条款编号（如"1.2.3"）
- detect_parent_section: 计算父级章节

根据 spec.md §FR-010 和 tasks.md §T023b 实施。
"""
import re
from typing import List, Optional, Set
import logging

import jieba
import jieba.analyse

from src.common.models import ClauseCategory, EntityRole

logger = logging.getLogger(__name__)


class MetadataExtractor:
    """元数据提取器
    
    使用规则引擎 + NLP关键词提取，自动填充PolicyChunk的metadata字段。
    
    方法：
    - 基于规则的分类（关键词匹配）
    - TF-IDF关键词提取（jieba.analyse）
    - 正则表达式（条款编号提取）
    """
    
    def __init__(self):
        """初始化元数据提取器"""
        # 条款类型关键词
        self.category_keywords = {
            ClauseCategory.LIABILITY: [
                '保险责任', '我们给付', '我们支付', '我们承担',
                '保险金', '理赔', '赔偿', '给付', '保障'
            ],
            ClauseCategory.EXCLUSION: [
                '责任免除', '我们不承担', '不在保障范围', '除外责任',
                '不负责', '不予', '不赔', '免责', '除外'
            ],
            ClauseCategory.PROCESS: [
                '申请', '理赔', '手续', '流程', '办理', '提交',
                '材料', '文件', '证明', '报案', '通知'
            ],
            ClauseCategory.DEFINITION: [
                '本合同所称', '定义', '释义', '指', '包括',
                '是指', '系指', '本条款所称'
            ]
        }
        
        # 主体角色关键词
        self.entity_role_keywords = {
            EntityRole.INSURER: [
                '保险人', '我们', '本公司', '承保人'
            ],
            EntityRole.INSURED: [
                '被保险人', '您', '投保人', '被保人'
            ],
            EntityRole.BENEFICIARY: [
                '受益人', '身故受益人', '生存受益人'
            ]
        }
        
        # 停用词（扩展jieba默认停用词）
        self.stopwords = set([
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人',
            '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去',
            '你', '会', '着', '没有', '看', '好', '自己', '这', '为',
            '与', '或', '及', '等', '其', '中', '由', '以', '如', '但'
        ])
        
        # 条款编号模式（如"1.2.3"）
        self.section_id_pattern = re.compile(r'^(\d+(?:\.\d+)*)\s+')
        
        logger.info("初始化元数据提取器")
    
    def classify_category(self, content: str) -> ClauseCategory:
        """分类条款类型
        
        基于关键词匹配，返回最匹配的类别。
        
        Args:
            content: 条款内容
        
        Returns:
            ClauseCategory枚举值
        """
        # 计算每个类别的匹配分数
        scores = {}
        
        for category, keywords in self.category_keywords.items():
            score = sum(1 for keyword in keywords if keyword in content)
            scores[category] = score
        
        # 返回得分最高的类别
        if not scores or max(scores.values()) == 0:
            return ClauseCategory.GENERAL
        
        best_category = max(scores.keys(), key=lambda k: scores[k])
        
        logger.debug(f"分类结果: {best_category.value}，得分={scores[best_category]}")
        
        return best_category
    
    def identify_entity_role(self, content: str) -> Optional[EntityRole]:
        """识别主体角色
        
        识别条款中的主要主体（保险人/被保险人/受益人）。
        
        Args:
            content: 条款内容
        
        Returns:
            EntityRole枚举值，无法识别则返回None
        """
        # 计算每个角色的出现次数
        role_counts = {}
        
        for role, keywords in self.entity_role_keywords.items():
            count = sum(content.count(keyword) for keyword in keywords)
            role_counts[role] = count
        
        # 返回出现次数最多的角色
        if not role_counts or max(role_counts.values()) == 0:
            return None
        
        primary_role = max(role_counts.keys(), key=lambda k: role_counts[k])
        
        logger.debug(f"识别到主体角色: {primary_role.value}")
        
        return primary_role
    
    def extract_keywords(self, content: str, top_k: int = 5) -> List[str]:
        """提取关键词
        
        使用jieba TF-IDF算法提取Top-K关键词。
        
        Args:
            content: 条款内容
            top_k: 返回前K个关键词
        
        Returns:
            关键词列表
        """
        # 使用jieba TF-IDF提取关键词
        keywords = jieba.analyse.extract_tags(
            content,
            topK=top_k * 2,  # 提取2倍数量，用于过滤
            withWeight=False
        )
        
        # 过滤停用词和单字符
        filtered_keywords = [
            kw for kw in keywords
            if len(kw) > 1 and kw not in self.stopwords
        ][:top_k]
        
        logger.debug(f"提取关键词: {filtered_keywords}")
        
        return filtered_keywords
    
    def extract_section_id(self, heading: str) -> Optional[str]:
        """从标题提取条款编号
        
        从Markdown标题中提取条款编号（如"### 1.2.3 身故保险金" → "1.2.3"）。
        
        Args:
            heading: 标题文本
        
        Returns:
            条款编号，无法提取则返回None
        """
        # 移除Markdown标题标记
        heading = heading.lstrip('#').strip()
        
        # 匹配条款编号
        match = self.section_id_pattern.match(heading)
        
        if match:
            section_id = match.group(1)
            logger.debug(f"提取条款编号: {section_id}")
            return section_id
        
        return None
    
    def detect_parent_section(self, section_id: str) -> Optional[str]:
        """计算父级章节
        
        从条款编号推断父级章节（如"1.2.3" → "1.2"）。
        
        Args:
            section_id: 条款编号
        
        Returns:
            父级章节编号，无父级则返回None
        """
        if not section_id:
            return None
        
        parts = section_id.split('.')
        
        if len(parts) <= 1:
            return None
        
        # 移除最后一级
        parent_parts = parts[:-1]
        parent_section = '.'.join(parent_parts)
        
        logger.debug(f"检测父级章节: {section_id} → {parent_section}")
        
        return parent_section
    
    def extract_all(
        self,
        content: str,
        section_title: Optional[str] = None
    ) -> dict:
        """提取所有元数据
        
        一次性提取所有元数据字段，便于批量处理。
        
        Args:
            content: 条款内容
            section_title: 章节标题（可选，用于提取section_id）
        
        Returns:
            元数据字典，包含：
            - category: ClauseCategory
            - entity_role: EntityRole (可为None)
            - keywords: List[str]
            - section_id: str (可为None)
            - parent_section: str (可为None)
        """
        metadata = {}
        
        # 1. 分类条款类型
        metadata['category'] = self.classify_category(content)
        
        # 2. 识别主体角色
        metadata['entity_role'] = self.identify_entity_role(content)
        
        # 3. 提取关键词
        metadata['keywords'] = self.extract_keywords(content)
        
        # 4. 提取条款编号（如果提供了标题）
        section_id = None
        if section_title:
            section_id = self.extract_section_id(section_title)
        
        metadata['section_id'] = section_id
        
        # 5. 检测父级章节
        metadata['parent_section'] = self.detect_parent_section(section_id) if section_id else None
        
        logger.debug(f"提取元数据完成: category={metadata['category'].value}, keywords={metadata['keywords']}")
        
        return metadata


def get_metadata_extractor() -> MetadataExtractor:
    """工厂函数：获取MetadataExtractor实例
    
    Returns:
        MetadataExtractor实例
    """
    return MetadataExtractor()

