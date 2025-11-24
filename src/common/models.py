from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List
import uuid
from pydantic import BaseModel, Field

class VerificationStatus(str, Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"

class DocumentType(str, Enum):
    """文档类型枚举"""
    CLAUSE = "产品条款"          # 产品条款
    MANUAL = "产品说明书"        # 产品说明书
    RATE_TABLE = "产品费率表"    # 产品费率表

class ClauseCategory(str, Enum):
    """条款类型枚举"""
    LIABILITY = "Liability"      # 保险责任
    EXCLUSION = "Exclusion"      # 责任免除
    PROCESS = "Process"          # 流程
    DEFINITION = "Definition"    # 定义
    GENERAL = "General"          # 无法明确分类的条款（兜底）

class EntityRole(str, Enum):
    """主体角色枚举"""
    INSURER = "Insurer"          # 保险人（我们）
    INSURED = "Insured"          # 被保险人
    BENEFICIARY = "Beneficiary"  # 受益人

class Product(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    product_code: str  # 产品代码（用于去重）
    name: str
    company: str
    category: Optional[str] = None
    publish_time: Optional[str] = None  # 发布时间
    created_at: datetime = Field(default_factory=datetime.now)

class PolicyDocument(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    product_id: Optional[str] = None
    doc_type: DocumentType = Field(default=DocumentType.CLAUSE)  # 文档类型枚举
    filename: str
    local_path: str
    url: Optional[str] = None
    file_hash: Optional[str] = None  # 下载后计算
    file_size: Optional[int] = None  # 文件大小（字节）
    downloaded_at: Optional[datetime] = None
    verification_status: VerificationStatus = Field(default=VerificationStatus.PENDING)
    auditor_notes: Optional[str] = None
    markdown_content: Optional[str] = None
    pdf_links: Dict[str, str] = Field(default_factory=dict)  # 所有PDF链接 {"产品条款": "url1", "费率表": "url2"}

class TableData(BaseModel):
    """表格数据结构"""
    table_type: str = Field(..., description="表格类型，如'减额交清对比表'")
    headers: List[str] = Field(..., description="表头列表")
    rows: List[List[str]] = Field(..., description="数据行列表")
    row_count: int = Field(..., description="行数")
    column_count: int = Field(..., description="列数")
    
    class Config:
        schema_extra = {
            "example": {
                "table_type": "减额交清对比表",
                "headers": ["保单年度", "减额后年金", "备注"],
                "rows": [
                    ["第5年", "1000元/年", "终身领取"],
                    ["第10年", "1500元/年", "终身领取"]
                ],
                "row_count": 2,
                "column_count": 3
            }
        }

class PolicyChunk(BaseModel):
    """
    条款切片（语义块）
    
    用于向量索引和检索的文本段，包含丰富的元数据以支持精准过滤。
    """
    
    # 核心标识
    id: str = Field(
        default_factory=lambda: f"chunk_{uuid.uuid4().hex[:12]}",
        description="Chunk唯一标识"
    )
    document_id: str = Field(..., description="关联的PolicyDocument ID")
    
    # 产品上下文 (P0增强)
    company: str = Field(..., description="保险公司名称")
    product_code: str = Field(..., description="产品代码")
    product_name: str = Field(..., description="产品名称")
    doc_type: str = Field(default="产品条款", description="文档类型")  # FR-005: 多文档类型支持
    
    # 内容字段
    content: str = Field(..., description="Chunk文本内容")
    embedding_vector: Optional[List[float]] = Field(
        None, 
        description="OpenAI生成的向量（1536维）"
    )
    
    # 结构化元数据（新增/增强）
    section_id: str = Field(..., description="条款编号，如'1.2.6'")
    section_path: Optional[str] = Field(None, description="完整章节路径（面包屑），如'保险责任 > 重疾 > 给付条件'")
    section_title: str = Field(..., description="条款标题，如'身故保险金'")
    category: ClauseCategory = Field(
        default=ClauseCategory.GENERAL,
        description="条款类型（自动分类，无法识别时为GENERAL）"
    )
    entity_role: Optional[EntityRole] = Field(None, description="主体角色（可选，基于关键词识别）")
    parent_section: Optional[str] = Field(None, description="父级章节编号，如'1.2'")
    level: int = Field(..., ge=1, le=5, description="标题层级（1-5）")
    
    # 位置信息
    page_number: Optional[int] = Field(None, description="原PDF页码")
    chunk_index: int = Field(..., description="在文档中的顺序")
    
    # 语义增强
    keywords: List[str] = Field(default_factory=list, description="提取的关键词")
    
    # 表格专用字段
    is_table: bool = Field(default=False, description="是否为表格chunk")
    table_data: Optional[TableData] = Field(None, description="表格JSON结构")
    table_refs: List[str] = Field(default_factory=list, description="关联的费率表UUID列表（仅当表格被分离时）")
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    
    model_config = {
        "use_enum_values": True,
        "json_schema_extra": {
            "example": {
                "id": "chunk_a1b2c3d4e5f6",
                "document_id": "doc_067afcfc",
                "content": "1.2.6 身故保险金\n若被保险人在保险期间内身故...",
                "section_id": "1.2.6",
                "section_title": "身故保险金",
                "category": "Liability",
                "entity_role": "Insurer",
                "parent_section": "1.2",
                "level": 3,
                "page_number": 12,
                "chunk_index": 15,
                "keywords": ["身故", "保险金", "受益人"],
                "is_table": False,
                "table_data": None
            }
        }
    }
    
    def to_chroma_metadata(self) -> Dict:
        """
        转换为ChromaDB metadata格式
        
        ChromaDB对metadata有限制：
        - 不支持嵌套对象
        - 不支持list of objects
        - 数值类型需要是int/float
        """
        # Handle category (might be Enum or str)
        category_val = self.category
        if hasattr(category_val, 'value'):
            category_val = category_val.value
            
            metadata = {
            "document_id": self.document_id,
            # 产品上下文
            "company": self.company,
            "product_code": self.product_code,
            "product_name": self.product_name,
            "doc_type": self.doc_type,  # 新增: 文档类型
            # 结构化元数据
            "section_id": self.section_id,
            "section_title": self.section_title,
            "category": category_val,
            "level": self.level,
            "chunk_index": self.chunk_index,
            "is_table": self.is_table,
        }
        
        # 新增: section_path
        if self.section_path:
            metadata["section_path"] = self.section_path
        
        # 可选字段
        if self.entity_role:
            role_val = self.entity_role
            if hasattr(role_val, 'value'):
                role_val = role_val.value
            metadata["entity_role"] = role_val
            
        if self.parent_section:
            metadata["parent_section"] = self.parent_section
        if self.page_number:
            metadata["page_number"] = self.page_number
        
        # keywords作为字符串存储（ChromaDB限制）
        if self.keywords:
            metadata["keywords"] = ",".join(self.keywords)
        
        # table_data序列化为JSON字符串
        if self.table_data:
            import json
            # Use model_dump() for Pydantic V2
            metadata["table_data"] = json.dumps(self.table_data.model_dump())
            
        # table_refs作为字符串存储
        if self.table_refs:
            metadata["table_refs"] = ",".join(self.table_refs)
        
        # ChromaDB不接受None值,过滤掉所有None
        metadata = {k: v for k, v in metadata.items() if v is not None}
        
        return metadata
    
    @classmethod
    def from_chroma_result(cls, chroma_result: Dict) -> "PolicyChunk":
        """从ChromaDB查询结果构建PolicyChunk"""
        import json
        
        metadata = chroma_result.get("metadatas", [{}])[0]
        
        # 反序列化keywords
        keywords = []
        if "keywords" in metadata:
            keywords = metadata["keywords"].split(",")
        
        # 反序列化table_data
        table_data = None
        if metadata.get("table_data"):
            table_data = TableData(**json.loads(metadata["table_data"]))
        
        # Deserialize table_refs
        table_refs = []
        if "table_refs" in metadata and metadata["table_refs"]:
            table_refs = metadata["table_refs"].split(",")
            
        return cls(
            id=chroma_result["ids"][0],
            document_id=metadata.get("document_id", ""),
            # 产品上下文
            company=metadata.get("company", ""),
            product_code=metadata.get("product_code", ""),
            product_name=metadata.get("product_name", ""),
            doc_type=metadata.get("doc_type", "产品条款"),  # 新增: 默认值为产品条款
            # 内容和元数据
            content=chroma_result["documents"][0],
            embedding_vector=chroma_result.get("embeddings", [None])[0],
            section_id=metadata.get("section_id", ""),
            section_path=metadata.get("section_path"),
            section_title=metadata.get("section_title", ""),
            category=metadata.get("category", "General"),
            entity_role=metadata.get("entity_role"),
            parent_section=metadata.get("parent_section"),
            level=metadata.get("level", 1),
            page_number=metadata.get("page_number"),
            chunk_index=metadata.get("chunk_index", 0),
            keywords=keywords,
            is_table=metadata.get("is_table", False),
            table_data=table_data,
            table_refs=table_refs
        )

# Helper函数
def classify_category(content: str) -> ClauseCategory:
    """
    根据内容自动分类条款类型
    
    使用规则引擎+关键词匹配
    """
    content_lower = content.lower()
    
    # 免责条款特征（优先级最高）
    exclusion_keywords = ["责任免除", "我们不承担", "除外", "不负责", "免除责任", "不予给付"]
    if any(kw in content for kw in exclusion_keywords):
        return ClauseCategory.EXCLUSION
    
    # 保险责任特征
    liability_keywords = ["保险责任", "我们给付", "保险金", "我们支付", "承担责任", "给付"]
    if any(kw in content for kw in liability_keywords):
        return ClauseCategory.LIABILITY
    
    # 定义类特征（在流程之前检查）
    definition_keywords = ["本合同所称", "定义", "是指", "本条款中", "以下简称"]
    if any(kw in content for kw in definition_keywords):
        return ClauseCategory.DEFINITION
    
    # 流程类特征
    process_keywords = ["申请", "理赔", "手续", "流程", "提交材料", "审核", "办理"]
    if any(kw in content for kw in process_keywords):
        return ClauseCategory.PROCESS
    
    # 无法明确分类时使用 GENERAL
    return ClauseCategory.GENERAL

def identify_entity_role(content: str) -> Optional[EntityRole]:
    """
    识别条款中的主体角色
    
    基于关键词出现频率判断
    """
    insurer_keywords = ["我们", "本公司", "保险人"]
    insured_keywords = ["被保险人", "您的孩子", "受保人"]
    beneficiary_keywords = ["受益人", "继承人"]
    
    insurer_count = sum(content.count(kw) for kw in insurer_keywords)
    insured_count = sum(content.count(kw) for kw in insured_keywords)
    beneficiary_count = sum(content.count(kw) for kw in beneficiary_keywords)
    
    max_count = max(insurer_count, insured_count, beneficiary_count)
    
    if max_count == 0:
        return None
    
    if insurer_count == max_count:
        return EntityRole.INSURER
    elif insured_count == max_count:
        return EntityRole.INSURED
    else:
        return EntityRole.BENEFICIARY


# ==================== MCP 工具返回结构 ====================

class SourceRef(BaseModel):
    """MCP工具返回的来源引用信息"""
    product_name: str = Field(..., description="产品名称")
    document_type: str = Field(..., description="文档类型（产品条款/说明书）")
    pdf_path: str = Field(..., description="原始PDF路径")
    page_number: int = Field(..., description="页码")
    download_url: str = Field(..., description="原始下载链接")
    
    class Config:
        schema_extra = {
            "example": {
                "product_name": "平安福耀年金保险",
                "document_type": "产品条款",
                "pdf_path": "data/raw/平安人寿/C00012032212021087040652/产品条款.pdf",
                "page_number": 12,
                "download_url": "https://life.pingan.com/..."
            }
        }


class ClauseResult(BaseModel):
    """语义条款检索结果（search_policy_clause）"""
    chunk_id: str = Field(..., description="Chunk唯一ID")
    content: str = Field(..., description="条款原文")
    section_id: str = Field(..., description="条款编号（如'1.2.6'）")
    section_title: str = Field(..., description="条款标题")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="相似度分数（0-1）")
    source_reference: SourceRef = Field(..., description="来源引用")
    
    class Config:
        schema_extra = {
            "example": {
                "chunk_id": "chunk_a1b2c3d4e5f6",
                "content": "1.4 保险期间\n本合同的保险期间为...",
                "section_id": "1.4",
                "section_title": "保险期间",
                "similarity_score": 0.89,
                "source_reference": {
                    "product_name": "平安福耀年金保险",
                    "document_type": "产品条款",
                    "pdf_path": "data/raw/平安人寿/C00012032212021087040652/产品条款.pdf",
                    "page_number": 3,
                    "download_url": "https://..."
                }
            }
        }


class ExclusionCheckResult(BaseModel):
    """免责条款核查结果（check_exclusion_risk）"""
    is_excluded: bool = Field(..., description="是否明确免责")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度（0-1）")
    matched_clauses: List[ClauseResult] = Field(default_factory=list, description="匹配的免责条款")
    risk_summary: str = Field(..., description="风险总结")
    disclaimer: str = Field(
        default="本结果仅供参考，实际理赔以保险合同和公司审核为准",
        description="免责声明（必需）"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "is_excluded": True,
                "confidence": 0.95,
                "matched_clauses": [],
                "risk_summary": "该场景属于明确的免责范围，涉及酒后驾驶条款",
                "disclaimer": "本结果仅供参考，实际理赔以保险合同和公司审核为准"
            }
        }


class SurrenderLogicResult(BaseModel):
    """退保/减额交清逻辑提取结果（calculate_surrender_value_logic）"""
    operation_name: str = Field(..., description="操作名称（中文）")
    definition: str = Field(..., description="定义条款原文")
    calculation_rules: List[str] = Field(default_factory=list, description="计算规则列表")
    conditions: List[str] = Field(default_factory=list, description="前置条件")
    consequences: List[str] = Field(default_factory=list, description="后果说明")
    related_tables: List[Dict] = Field(
        default_factory=list, 
        description="相关表格（简化版：包含chunk_id和table_type）"
    )
    comparison_note: str = Field(..., description="对比说明（退保 vs 减额交清）")
    source_references: List[SourceRef] = Field(default_factory=list, description="来源引用")
    
    class Config:
        schema_extra = {
            "example": {
                "operation_name": "退保",
                "definition": "5.2 退保\n您可以随时申请解除本合同...",
                "calculation_rules": [
                    "退保金 = 保单当时的现金价值 - 欠缴保费 - 借款本息",
                    "现金价值按保单年度累积"
                ],
                "conditions": ["保单生效", "非犹豫期内"],
                "consequences": ["合同终止", "保障失效", "可能产生经济损失"],
                "related_tables": [
                    {"chunk_id": "chunk_table_001", "table_type": "现金价值表"}
                ],
                "comparison_note": "退保将终止保障，减额交清保留部分保障但降低保额",
                "source_references": []
            }
        }


# ==================== 黄金测试集数据结构 ====================

class QueryType(str, Enum):
    """查询类型"""
    BASIC = "basic"              # 基础查询（单一条款）
    COMPARISON = "comparison"     # 对比查询（多条款）
    EXCLUSION = "exclusion"       # 免责专项查询


class GoldenTestCase(BaseModel):
    """黄金测试集单个测试用例"""
    id: str = Field(default_factory=lambda: f"test_{uuid.uuid4().hex[:8]}", description="测试用例ID")
    question: str = Field(..., description="测试问题（自然语言）")
    query_type: QueryType = Field(..., description="查询类型")
    
    # Ground Truth
    expected_section_ids: List[str] = Field(..., description="期望返回的条款编号（如['1.4', '2.1']）")
    expected_chunks: List[str] = Field(
        default_factory=list, 
        description="期望返回的chunk_id列表（可选，用于精确验证）"
    )
    expected_category: Optional[ClauseCategory] = Field(None, description="期望的条款类型（用于过滤验证）")
    
    # 测试元数据
    product_name: Optional[str] = Field(None, description="关联产品名称（可选）")
    company: str = Field(default="平安人寿", description="保险公司")
    tier: int = Field(..., ge=1, le=3, description="测试层级（1=基础, 2=对比, 3=专项）")
    min_similarity_score: float = Field(default=0.7, description="最低相似度要求")
    
    # 验收标准
    top_k: int = Field(default=5, description="返回结果数量")
    success_criteria: str = Field(
        ..., 
        description="成功标准（如'Top-1包含1.4'、'Top-3包含所有期望条款'）"
    )
    
    # 额外信息
    notes: Optional[str] = Field(None, description="备注说明")
    created_by: str = Field(default="human", description="创建者（human/generated）")
    created_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        schema_extra = {
            "example": {
                "id": "test_001",
                "question": "这个保险保多久？",
                "query_type": "basic",
                "expected_section_ids": ["1.4"],
                "expected_category": "Process",
                "product_name": "平安福耀年金保险",
                "company": "平安人寿",
                "tier": 1,
                "top_k": 5,
                "success_criteria": "Top-1结果的section_id为'1.4'",
                "notes": "测试基本信息查询能力"
            }
        }


class GoldenTestSet(BaseModel):
    """黄金测试集"""
    name: str = Field(..., description="测试集名称")
    version: str = Field(default="1.0.0", description="版本号")
    description: str = Field(..., description="测试集描述")
    test_cases: List[GoldenTestCase] = Field(..., description="测试用例列表")
    
    # 统计信息
    total_count: int = Field(..., description="总测试用例数")
    tier_distribution: Dict[int, int] = Field(
        ..., 
        description="层级分布 {1: 20, 2: 15, 3: 15}"
    )
    category_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="类别分布"
    )
    
    created_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)
    
    class Config:
        schema_extra = {
            "example": {
                "name": "Phase5_Golden_Test_Set",
                "version": "1.0.0",
                "description": "第五阶段向量检索黄金测试集",
                "test_cases": [],
                "total_count": 50,
                "tier_distribution": {1: 20, 2: 15, 3: 15},
                "category_distribution": {"Liability": 15, "Exclusion": 15, "Process": 10, "Definition": 10}
            }
        }

