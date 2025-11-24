"""
产品查询工具

提供模糊匹配的产品查询功能,用于AI客户端查找精确的产品信息
"""
from typing import List, Optional
from difflib import SequenceMatcher
from src.common.repository import repository
from src.common.models import Product
from src.common.logging import logger


class ProductInfo:
    """产品信息返回结构"""
    def __init__(self, product: Product):
        self.product_id = product.id
        self.product_code = product.product_code
        self.product_name = product.name
        self.company = product.company
        self.category = product.category
        self.publish_time = product.publish_time
    
    def to_dict(self):
        return {
            "product_id": self.product_id,
            "product_code": self.product_code,
            "product_name": self.product_name,
            "company": self.company,
            "category": self.category,
            "publish_time": self.publish_time
        }


def calculate_similarity(query: str, target: str) -> float:
    """
    计算两个字符串的相似度
    
    Args:
        query: 查询字符串
        target: 目标字符串
    
    Returns:
        相似度分数 (0-1)
    """
    # 转换为小写进行比较
    query = query.lower()
    target = target.lower()
    
    # 使用SequenceMatcher计算相似度
    similarity = SequenceMatcher(None, query, target).ratio()
    
    # 如果query是target的子串,给予额外加分
    if query in target:
        similarity = max(similarity, 0.8 + (len(query) / len(target)) * 0.2)
    
    return similarity


def lookup_product(
    product_name: str,
    company: Optional[str] = None,
    top_k: int = 5
) -> List[ProductInfo]:
    """
    根据产品名称查询产品信息(支持模糊匹配)
    
    Args:
        product_name: 产品名称(支持部分匹配)
        company: 保险公司名称(可选,用于过滤)
        top_k: 返回结果数量
    
    Returns:
        ProductInfo列表,按相似度排序
    
    Examples:
        >>> # 查询"盈添悦"
        >>> results = lookup_product("盈添悦")
        >>> results[0].product_name
        '平安盈添悦两全保险（分红型）'
        
        >>> # 查询"平安 养老"
        >>> results = lookup_product("养老", company="平安人寿")
        >>> len(results)
        2  # 返回平安的养老年金产品
    """
    logger.info(f"产品查询: product_name='{product_name}', company='{company}'")
    
    # 获取所有产品
    # 注意: repository是单例,直接使用
    with repository.get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 构建查询
        if company:
            query = "SELECT * FROM products WHERE company = ?"
            rows = cursor.execute(query, (company,)).fetchall()
        else:
            query = "SELECT * FROM products"
            rows = cursor.execute(query).fetchall()
    
    # 转换为Product对象
    products = []
    for row in rows:
        from datetime import datetime
        product = Product(
            id=row["id"],
            product_code=row["product_code"],
            name=row["name"],
            company=row["company"],
            category=row["category"],
            publish_time=row["publish_time"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
        )
        products.append(product)
    
    logger.info(f"找到 {len(products)} 个候选产品")
    
    # 计算相似度并排序
    scored_products = []
    for product in products:
        similarity = calculate_similarity(product_name, product.name)
        scored_products.append((similarity, product))
    
    # 按相似度降序排序
    scored_products.sort(key=lambda x: x[0], reverse=True)
    
    # 取Top-K
    top_products = scored_products[:top_k]
    
    # 转换为ProductInfo
    results = [ProductInfo(product) for score, product in top_products]
    
    logger.info(f"返回 {len(results)} 个结果")
    if results:
        logger.info(f"Top 1: {results[0].product_name} (similarity: {top_products[0][0]:.2f})")
    
    return results


def get_product_by_code(product_code: str) -> Optional[ProductInfo]:
    """
    根据产品代码精确查询
    
    Args:
        product_code: 产品代码
    
    Returns:
        ProductInfo或None
    """
    with repository.get_db_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM products WHERE product_code = ?"
        row = cursor.execute(query, (product_code,)).fetchone()
        
        if row:
            from datetime import datetime
            product = Product(
                id=row["id"],
                product_code=row["product_code"],
                name=row["name"],
                company=row["company"],
                category=row["category"],
                publish_time=row["publish_time"],
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
            )
            return ProductInfo(product)
    
    return None
