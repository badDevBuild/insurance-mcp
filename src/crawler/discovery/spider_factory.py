"""
爬虫工厂类
用于统一管理和创建各个保险公司的爬虫实例
"""
from typing import Dict, Type, Optional
from src.crawler.discovery.base_spider import BaseInsuranceSpider
from src.crawler.discovery.pingan_life_spider import PingAnLifeSpider
# from src.crawler.discovery.pingan_life_spider_v2 import PingAnLifeSpiderV2
# from src.crawler.discovery.chinalifeinsurance_spider import ChinaLifeInsuranceSpider
from src.common.logging import logger


class SpiderFactory:
    """
    爬虫工厂类
    
    负责:
    1. 注册各保险公司的爬虫类
    2. 根据公司代码创建爬虫实例
    3. 列出所有支持的保险公司
    """
    
    # 公司代码 -> 爬虫类的映射
    _registry: Dict[str, Type[BaseInsuranceSpider]] = {}
    
    # 公司代码 -> 公司名称的映射（用于显示）
    _company_names: Dict[str, str] = {}
    
    @classmethod
    def register(cls, company_code: str, spider_class: Type[BaseInsuranceSpider]):
        """
        注册爬虫类
        
        Args:
            company_code: 公司代码（如 "pingan-life"）
            spider_class: 爬虫类（必须继承BaseInsuranceSpider）
        """
        if not issubclass(spider_class, BaseInsuranceSpider):
            raise ValueError(f"{spider_class.__name__} must inherit from BaseInsuranceSpider")
        
        cls._registry[company_code] = spider_class
        cls._company_names[company_code] = spider_class.COMPANY_NAME
        logger.info(f"Registered spider for {company_code}: {spider_class.__name__}")
    
    @classmethod
    def create(cls, company_code: str, **kwargs) -> Optional[BaseInsuranceSpider]:
        """
        创建爬虫实例
        
        Args:
            company_code: 公司代码
            **kwargs: 传递给爬虫构造函数的参数（如 headless=True）
            
        Returns:
            爬虫实例，如果公司代码不存在则返回None
        """
        spider_class = cls._registry.get(company_code)
        
        if spider_class is None:
            logger.error(f"No spider registered for company code: {company_code}")
            logger.info(f"Available companies: {', '.join(cls.list_companies())}")
            return None
        
        return spider_class(**kwargs)
    
    @classmethod
    def list_companies(cls) -> list:
        """
        列出所有已注册的保险公司
        
        Returns:
            公司代码列表
        """
        return list(cls._registry.keys())
    
    @classmethod
    def get_company_info(cls) -> Dict[str, str]:
        """
        获取所有公司信息
        
        Returns:
            {公司代码: 公司名称} 的字典
        """
        return cls._company_names.copy()


# ============= 注册所有爬虫 =============

# 注册平安人寿爬虫
SpiderFactory.register("pingan-life", PingAnLifeSpider)

# 注册其他保险公司爬虫（添加新公司时取消注释）
# SpiderFactory.register("china-life", ChinaLifeInsuranceSpider)
# SpiderFactory.register("picc-life", PICCLifeSpider)
# SpiderFactory.register("taikang-life", TaikangLifeSpider)
# ... 继续添加其他公司


# ============= 使用示例 =============

if __name__ == "__main__":
    import asyncio
    
    print("=" * 80)
    print("支持的保险公司:")
    print("=" * 80)
    for code, name in SpiderFactory.get_company_info().items():
        print(f"  - {code}: {name}")
    print()
    
    # 创建平安人寿爬虫
    print("=" * 80)
    print("测试平安人寿爬虫:")
    print("=" * 80)
    spider = SpiderFactory.create("pingan-life", headless=False)
    
    if spider:
        products = asyncio.run(spider.discover_products(limit=3, fetch_details=True))
        print(f"\n✅ 成功爬取 {len(products)} 个产品")
        for p in products:
            print(f"  - {p['product_code']}: {p['name']}")
    
    # 测试不存在的公司
    print("\n" + "=" * 80)
    print("测试不存在的公司:")
    print("=" * 80)
    spider = SpiderFactory.create("nonexistent-company")
    if spider is None:
        print("✓ 正确处理了不存在的公司代码")

