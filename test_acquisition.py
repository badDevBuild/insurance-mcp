"""
快速测试数据采集流程

这个脚本会：
1. 初始化数据库
2. 爬取5个产品
3. 下载PDF文件
4. 显示结果
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.common.db import init_db
from src.crawler.pipelines.acquisition_pipeline import run_acquisition

async def main():
    print("=" * 80)
    print("🧪 数据采集流程测试")
    print("=" * 80)
    
    # 1. 初始化数据库
    print("\n步骤 1: 初始化数据库...")
    try:
        init_db()
        print("✓ 数据库初始化成功")
    except Exception as e:
        print(f"✗ 数据库初始化失败: {e}")
        return
    
    # 2. 运行采集（只采集5个产品用于测试）
    print("\n步骤 2: 开始采集数据...")
    print("-" * 80)
    
    try:
        stats = await run_acquisition(
            company="平安人寿",
            limit=5  # 只采集5个产品用于测试
        )
        
        # 3. 显示结果
        print("\n" + "=" * 80)
        print("✅ 测试完成！")
        print("=" * 80)
        print(f"\n📊 统计信息:")
        print(f"  产品: 发现 {stats['products_discovered']}, 新增 {stats['products_new']}, 已存在 {stats['products_existing']}")
        print(f"  PDF: 下载 {stats['pdfs_downloaded']}, 跳过 {stats['pdfs_skipped']}, 失败 {stats['pdfs_failed']}")
        
        print(f"\n📁 查看文件:")
        print(f"  数据库: data/db/metadata.sqlite")
        print(f"  PDF文件: data/raw/平安人寿/")
        
        print(f"\n💡 查询数据库:")
        print(f"  sqlite3 data/db/metadata.sqlite")
        print(f"  > SELECT * FROM products;")
        print(f"  > SELECT * FROM policy_documents;")
        
        if stats['pdfs_failed'] > 0:
            print(f"\n⚠️  有 {stats['pdfs_failed']} 个PDF下载失败")
            print(f"  可以重新运行脚本，系统会自动跳过已下载的文件")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  测试已中断")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

