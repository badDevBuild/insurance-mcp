import typer
import asyncio
import json
from typing import Optional
from src.common.db import init_db
from src.common.config import config
from src.common.logging import setup_logging
from src.crawler.discovery.iac_spider import IACSpider
from src.crawler.pipelines.save_pipeline import save_pipeline

app = typer.Typer(help="Insurance MCP Management CLI")
crawl_app = typer.Typer(help="Crawler commands")
process_app = typer.Typer(help="PDF processing commands")
index_app = typer.Typer(help="Indexing commands")
app.add_typer(crawl_app, name="crawl")
app.add_typer(process_app, name="process")
app.add_typer(index_app, name="index")

@app.callback()
def callback():
    """
    Insurance MCP Management CLI
    """
    pass

@app.command()
def init():
    """Initialize the application: database and directories."""
    setup_logging()
    typer.echo("Initializing Insurance MCP...")
    config.ensure_dirs()
    init_db()
    typer.echo("Initialization complete.")

@crawl_app.command()
def discover(company: Optional[str] = None, limit: int = 10, output: Optional[str] = None, headless: bool = True):
    """Discover products from IAC."""
    setup_logging()
    spider = IACSpider(headless=headless)
    products = asyncio.run(spider.discover_products(company_filter=company, limit=limit))
    
    if output:
        with open(output, 'w') as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
        typer.echo(f"Saved {len(products)} products to {output}")
    else:
        typer.echo(json.dumps(products, ensure_ascii=False, indent=2))

@crawl_app.command()
def acquire(input_file: str):
    """Download PDF documents from a JSON file (output of discover)."""
    setup_logging()
    
    try:
        with open(input_file, 'r') as f:
            items = json.load(f)
    except Exception as e:
        typer.echo(f"Error reading input file: {e}")
        raise typer.Exit(code=1)
    
    async def run_pipeline():
        for item in items:
            await save_pipeline.process_item(item)
            
    asyncio.run(run_pipeline())
    typer.echo("Acquisition complete.")

@crawl_app.command()
def run(
    company: str = typer.Option("pingan-life", help="公司代码 (pingan-life)"),
    limit: int = typer.Option(100, help="最大爬取产品数量")
):
    """
    运行完整的采集流程: 发现产品 -> 下载PDF -> 保存到数据库
    
    这是一站式命令，包含了discover和acquire的所有功能。
    """
    setup_logging()
    
    try:
        # 公司代码映射
        company_map = {
            "pingan-life": "平安人寿",
        }
        
        company_name = company_map.get(company)
        if not company_name:
            typer.echo(f"❌ 不支持的公司: {company}. 支持: {', '.join(company_map.keys())}")
            raise typer.Exit(code=1)
        
        typer.echo(f"🚀 开始采集 {company_name} 数据...")
        typer.echo(f"配置: limit={limit}\n")
        
        # 导入并运行采集管道
        from src.crawler.pipelines.acquisition_pipeline import run_acquisition
        
        stats = asyncio.run(run_acquisition(company=company_name, limit=limit))
        
        typer.echo(f"\n" + "="*60)
        typer.echo(f"✅ 采集完成!")
        typer.echo(f"="*60)
        typer.echo(f"产品: 发现 {stats['products_discovered']}, 新增 {stats['products_new']}, 已存在 {stats['products_existing']}")
        typer.echo(f"PDF: 下载 {stats['pdfs_downloaded']}, 跳过 {stats['pdfs_skipped']}, 失败 {stats['pdfs_failed']}")
        typer.echo(f"="*60)
        
        if stats['pdfs_failed'] > 0:
            typer.echo(f"⚠️  有 {stats['pdfs_failed']} 个PDF下载失败，请查看日志")
        
    except KeyboardInterrupt:
        typer.echo("\n⚠️  采集已中断")
        raise typer.Exit(code=130)
    except Exception as e:
        typer.echo(f"❌ 采集失败: {e}")
        import traceback
        from src.common.logging import logger
        logger.error(traceback.format_exc())
        raise typer.Exit(code=1)

@process_app.command("convert")
def process_convert(
    doc_type: str = typer.Option(None, help="文档类型过滤 (产品条款/产品说明书/产品费率表)"),
    limit: int = typer.Option(10, help="最多转换文档数"),
    all_docs: bool = typer.Option(False, "--all", help="转换所有PENDING文档")
):
    """
    将PENDING状态的PDF文档转换为Markdown
    
    支持的文档类型：
    - 产品条款
    - 产品说明书
    - 产品费率表
    
    示例：
    - python -m src.cli.manage process convert --doc-type 产品条款 --limit 5
    - python -m src.cli.manage process convert --all
    """
    setup_logging()
    
    from src.parser.markdown.converter import get_converter
    
    typer.echo("\n🔄 开始PDF转Markdown转换...")
    typer.echo(f"文档类型过滤: {doc_type or '全部（条款+说明书）'}")
    typer.echo(f"限制数量: {'无限制' if all_docs else limit}\n")
    
    converter = get_converter()
    
    # 执行转换
    stats = converter.convert_batch(
        doc_type_filter=doc_type,
        limit=999999 if all_docs else limit
    )
    
    # 显示结果
    typer.echo("\n" + "="*60)
    typer.echo("✅ 转换完成")
    typer.echo("="*60)
    typer.echo(f"总计: {stats['total']}")
    typer.echo(f"成功: {stats['success']}")
    typer.echo(f"失败: {stats['failed']}")
    typer.echo("="*60)
    
    if stats['failed'] > 0:
        typer.echo("\n⚠️  部分文档转换失败，请查看日志")
    
    if stats['success'] > 0:
        typer.echo(f"\n💡 提示: 转换后的Markdown文件保存在 data/processed/ 目录")
        typer.echo(f"   使用 'python -m src.cli.verify' 命令进行人工审核")

@process_app.command("analyze")
def process_analyze(
    product_code: str = typer.Argument(..., help="产品代码，如 5004")
):
    """
    分析指定产品的PDF文档版面结构
    
    示例:
    - python -m src.cli.manage process analyze 5004
    """
    setup_logging()
    
    from src.common.repository import SQLiteRepository
    from src.parser.layout.analyzer import get_analyzer
    from pathlib import Path
    
    typer.echo(f"\n🔍 分析产品 {product_code} 的PDF文档版面...\n")
    
    repo = SQLiteRepository()
    analyzer = get_analyzer()
    
    # 获取该产品的所有文档
    with repo.get_db_connection() as conn:
        cursor = conn.cursor()
        rows = cursor.execute(
            """
            SELECT id, doc_type, filename, local_path 
            FROM policy_documents 
            WHERE product_id = (SELECT id FROM products WHERE product_code = ?)
            AND doc_type IN ('产品条款', '产品说明书')
            """,
            (product_code,)
        ).fetchall()
    
    if not rows:
        typer.echo(f"❌ 未找到产品 {product_code} 的条款或说明书文档")
        raise typer.Exit(code=1)
    
    # 分析每个文档
    for row in rows:
        doc_type = row[1]
        filename = row[2]
        local_path = row[3]
        
        typer.echo(f"📄 {doc_type}: {filename}")
        
        pdf_path = Path(local_path)
        if not pdf_path.exists():
            typer.echo(f"   ❌ 文件不存在: {local_path}\n")
            continue
        
        result = analyzer.analyze_pdf(pdf_path)
        
        if result["success"]:
            typer.echo(f"   ✅ 分析成功")
            typer.echo(f"   页数: {result['total_pages']}")
            typer.echo(f"   布局类型: {result['layout_type']}")
            typer.echo(f"   包含表格: {'是' if result['has_tables'] else '否'}")
            typer.echo(f"   包含图像: {'是' if result['has_images'] else '否'}")
            
            quality = analyzer.get_quality_score(result)
            typer.echo(f"   质量评分: {quality:.2f}")
            
            if quality < 0.8:
                typer.echo(f"   ⚠️  建议人工复核")
        else:
            typer.echo(f"   ❌ 分析失败: {result['error']}")
        
        typer.echo("")


@process_app.command("postprocess")
def process_postprocess(
    doc_id: Optional[str] = typer.Option(None, "--doc-id", help="指定文档ID进行后处理"),
    all_docs: bool = typer.Option(False, "--all", help="后处理所有VERIFIED文档"),
    steps: Optional[str] = typer.Option(None, "--steps", help="指定执行的步骤（逗号分隔），如: footnote,noise,format"),
):
    """
    对已转换的Markdown文档执行后处理
    
    后处理步骤包括：
    1. footnote: 脚注内联（提升50%检索效果）
    2. noise: 噪音去除（页眉、页脚、水印）
    3. format: 格式标准化（统一标题、列表格式）
    4. table: 表格验证（检查行列完整性）
    
    示例:
    - python -m src.cli.manage process postprocess --all
    - python -m src.cli.manage process postprocess --doc-id doc123
    - python -m src.cli.manage process postprocess --all --steps footnote,noise
    """
    setup_logging()
    
    from src.common.repository import SQLiteRepository
    from src.parser.markdown.postprocessor import MarkdownPostProcessor
    from pathlib import Path
    
    if not doc_id and not all_docs:
        typer.echo("❌ 请指定 --doc-id 或 --all 参数")
        raise typer.Exit(code=1)
    
    # 解析步骤参数
    step_list = None
    if steps:
        step_list = [s.strip() for s in steps.split(',')]
        typer.echo(f"📝 执行步骤: {', '.join(step_list)}\n")
    
    # 初始化后处理器
    processor = MarkdownPostProcessor(steps=step_list)
    
    repo = SQLiteRepository()
    
    # 获取要处理的文档
    with repo.get_db_connection() as conn:
        cursor = conn.cursor()
        
        if doc_id:
            # 处理单个文档
            rows = cursor.execute(
                """
                SELECT id, filename, local_path 
                FROM policy_documents 
                WHERE id = ? AND verification_status = 'VERIFIED'
                """,
                (doc_id,)
            ).fetchall()
        else:
            # 处理所有VERIFIED文档
            rows = cursor.execute(
                """
                SELECT id, filename, local_path 
                FROM policy_documents 
                WHERE verification_status = 'VERIFIED'
                AND markdown_content IS NOT NULL
                """
            ).fetchall()
    
    if not rows:
        typer.echo("❌ 未找到符合条件的文档")
        raise typer.Exit(code=1)
    
    typer.echo(f"🔧 找到 {len(rows)} 个文档需要后处理\n")
    
    success_count = 0
    fail_count = 0
    
    # 处理每个文档
    for row in rows:
        doc_id_val = row[0]
        filename = row[1]
        
        typer.echo(f"📄 处理: {filename} (ID: {doc_id_val[:8]}...)")
        
        # 获取Markdown文件路径
        md_path = Path(f"data/processed/{doc_id_val}.md")
        
        if not md_path.exists():
            typer.echo(f"   ⚠️  Markdown文件不存在，跳过\n")
            fail_count += 1
            continue
        
        try:
            # 执行后处理
            processor.process(str(md_path))
            typer.echo(f"   ✅ 后处理完成\n")
            success_count += 1
        except Exception as e:
            typer.echo(f"   ❌ 后处理失败: {e}\n")
            fail_count += 1
    
    # 总结
    typer.echo(f"\n{'='*60}")
    typer.echo(f"✅ 成功: {success_count}")
    typer.echo(f"❌ 失败: {fail_count}")
    typer.echo(f"{'='*60}\n")


# ============================================================================
# Index Commands
# ============================================================================

@index_app.command("rebuild")
def index_rebuild(
    reset: bool = typer.Option(False, "--reset", help="先清空现有索引"),
    enable_bm25: bool = typer.Option(True, "--enable-bm25/--no-bm25", help="是否构建BM25索引"),
):
    """
    重建向量索引
    
    从所有VERIFIED文档重新构建ChromaDB和BM25索引。
    
    示例:
    - python -m src.cli.manage index rebuild
    - python -m src.cli.manage index rebuild --reset
    - python -m src.cli.manage index rebuild --no-bm25
    """
    setup_logging()
    
    from src.indexing.indexer import create_indexer
    from src.indexing.vector_store.hybrid_retriever import BM25Index
    
    typer.echo("\n🔧 准备重建索引...\n")
    
    # 创建BM25索引（如果启用）
    bm25_index = BM25Index() if enable_bm25 else None
    
    # 创建索引器
    indexer = create_indexer(bm25_index=bm25_index)
    
    # 重建索引
    try:
        stats = indexer.rebuild_index(reset=reset, update_bm25=enable_bm25)
        
        # 显示结果
        typer.echo(f"\n{'='*60}")
        typer.echo(f"✅ 索引重建完成！")
        typer.echo(f"{'='*60}")
        typer.echo(f"文档总数: {stats['total_documents']}")
        typer.echo(f"成功索引: {stats['success']}")
        typer.echo(f"失败: {stats['failed']}")
        typer.echo(f"总Chunks: {stats['total_chunks']}")
        
        if stats['errors']:
            typer.echo(f"\n错误详情:")
            for error in stats['errors']:
                typer.echo(f"  - {error}")
        
        # 显示存储统计
        chroma_stats = indexer.chroma_store.get_stats()
        typer.echo(f"\n📊 存储统计:")
        typer.echo(f"  - ChromaDB总Chunks: {chroma_stats['total_chunks']}")
        typer.echo(f"  - 向量维度: {chroma_stats['vector_dimension']}")
        
        # 显示Embedding统计
        embed_stats = indexer.embedder.get_stats()
        typer.echo(f"\n💰 Embedding成本:")
        typer.echo(f"  - 总Tokens: {embed_stats['total_tokens']}")
        typer.echo(f"  - 估算成本: ${embed_stats['estimated_cost_usd']:.6f}")
        
        typer.echo(f"{'='*60}\n")
        
    except Exception as e:
        typer.echo(f"\n❌ 索引重建失败: {e}\n")
        raise typer.Exit(code=1)


@index_app.command("test-search")
def index_test_search(
    query: str = typer.Argument(..., help="查询字符串"),
    n_results: int = typer.Option(5, "--top-k", help="返回结果数量"),
    company: Optional[str] = typer.Option(None, "--company", help="按公司过滤"),
    category: Optional[str] = typer.Option(None, "--category", help="按类别过滤（Liability/Exclusion/Process/Definition）"),
    use_hybrid: bool = typer.Option(False, "--hybrid", help="使用混合检索（Dense + BM25）"),
):
    """
    测试向量检索
    
    对索引执行测试检索，查看返回结果。
    
    示例:
    - python -m src.cli.manage index test-search "保险期间多久"
    - python -m src.cli.manage index test-search "酒驾赔吗" --category Exclusion
    - python -m src.cli.manage index test-search "保险期间90天" --hybrid
    """
    setup_logging()
    
    from src.indexing.embedding.bge import get_embedder
    from src.indexing.vector_store.chroma import get_chroma_store
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.syntax import Syntax
    
    console = Console()
    
    console.print(f"\n🔍 搜索查询: [bold cyan]{query}[/bold cyan]\n")
    
    try:
        # 生成查询向量
        embedder = get_embedder()
        query_embedding = embedder.embed_single(query)
        
        # 构建过滤条件
        where = {}
        if company:
            where['company'] = company
        if category:
            where['category'] = category
        
        # 执行检索
        if use_hybrid:
            # 混合检索
            console.print("📊 使用混合检索（Dense Vector + BM25）\n")
            
            from src.indexing.vector_store.hybrid_retriever import BM25Index, create_hybrid_retriever
            from src.common.models import PolicyChunk
            
            chroma_store = get_chroma_store()
            
            # 加载BM25索引（需要先构建）
            # 简化版：直接使用Dense检索
            console.print("[yellow]注意: 混合检索需要先运行 `index rebuild --enable-bm25`[/yellow]\n")
            results = chroma_store.search(query_embedding, n_results=n_results, where=where if where else None)
        else:
            # 纯向量检索
            console.print("🎯 使用Dense Vector检索\n")
            chroma_store = get_chroma_store()
            results = chroma_store.search(query_embedding, n_results=n_results, where=where if where else None)
        
        # 显示结果
        if not results:
            console.print("[yellow]未找到匹配结果[/yellow]\n")
            return
        
        console.print(f"找到 [bold green]{len(results)}[/bold green] 个结果:\n")
        
        for i, result in enumerate(results, 1):
            metadata = result['metadata']
            distance = result.get('distance', 0)
            similarity = 1 - distance  # 余弦相似度
            
            # 创建结果面板
            panel_content = f"""
[bold]相似度:[/bold] {similarity:.4f}
[bold]类别:[/bold] {metadata.get('category', 'N/A')}
[bold]章节:[/bold] {metadata.get('section_title', 'N/A')}
[bold]编号:[/bold] {metadata.get('section_id', 'N/A')}

[bold]内容:[/bold]
{result['document'][:300]}...
"""
            
            console.print(Panel(
                panel_content,
                title=f"结果 #{i}",
                border_style="green" if i == 1 else "blue"
            ))
            console.print()
        
    except Exception as e:
        console.print(f"\n[red]❌ 检索失败: {e}[/red]\n")
        raise typer.Exit(code=1)


@index_app.command("stats")
def index_stats():
    """
    显示索引统计信息
    
    示例:
    - python -m src.cli.manage index stats
    """
    setup_logging()
    
    from src.indexing.vector_store.chroma import get_chroma_store
    from rich.console import Console
    from rich.table import Table
    
    console = Console()
    
    console.print("\n📊 索引统计信息\n")
    
    try:
        chroma_store = get_chroma_store()
        stats = chroma_store.get_stats()
        
        # 创建表格
        table = Table(title="ChromaDB统计")
        table.add_column("指标", style="cyan")
        table.add_column("值", style="green")
        
        table.add_row("Collection名称", stats['collection_name'])
        table.add_row("总Chunks数", str(stats['total_chunks']))
        table.add_row("向量维度", str(stats['vector_dimension']))
        table.add_row("距离度量", stats['distance_metric'])
        table.add_row("持久化目录", stats['persist_directory'])
        
        console.print(table)
        console.print()
        
    except Exception as e:
        console.print(f"\n[red]❌ 获取统计信息失败: {e}[/red]\n")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
