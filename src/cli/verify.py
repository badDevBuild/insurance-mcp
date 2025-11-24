"""
审核员CLI - 用于人工审核PDF转Markdown结果

审核流程：
1. 列出所有PENDING状态的文档
2. 查看转换结果预览
3. 标记为VERIFIED（通过）或REJECTED（驳回）
"""

import sys
from pathlib import Path

# Path handling
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown

from src.common.repository import SQLiteRepository
from src.common.models import VerificationStatus
from src.common.logging import setup_logging, logger

app = typer.Typer(help="审核员工具 - 审核PDF转Markdown结果")
console = Console()


@app.command("list")
def list_pending(
    doc_type: Optional[str] = typer.Option(None, help="文档类型过滤"),
    limit: int = typer.Option(20, help="显示数量")
):
    """
    列出所有待审核的文档
    
    示例:
    - python -m src.cli.verify list
    - python -m src.cli.verify list --doc-type 产品条款
    """
    setup_logging()
    repo = SQLiteRepository()
    
    console.print("\n🔍 查询待审核文档...\n", style="bold blue")
    
    # 获取PENDING文档
    pending_docs = repo.get_pending_documents()
    
    # 过滤
    if doc_type:
        pending_docs = [doc for doc in pending_docs if doc.doc_type == doc_type]
    
    pending_docs = pending_docs[:limit]
    
    if not pending_docs:
        console.print("✅ 没有待审核的文档", style="green")
        return
    
    # 创建表格
    table = Table(title=f"待审核文档列表 ({len(pending_docs)}份)")
    
    table.add_column("ID", style="cyan", no_wrap=True, width=8)
    table.add_column("文档类型", style="magenta")
    table.add_column("文件名", style="green")
    table.add_column("产品ID", style="yellow", no_wrap=True, width=8)
    table.add_column("下载时间", style="blue")
    table.add_column("Markdown长度", style="white", justify="right")
    
    for doc in pending_docs:
        # 读取markdown文件获取实际长度
        md_path = Path("data/processed") / f"{doc.id}.md"
        md_length = "N/A"
        if md_path.exists():
            md_length = f"{len(md_path.read_text(encoding='utf-8')):,}"
        
        table.add_row(
            doc.id[:8],
            doc.doc_type,
            doc.filename,
            (doc.product_id or "N/A")[:8],
            doc.downloaded_at.strftime("%Y-%m-%d") if doc.downloaded_at else "N/A",
            md_length
        )
    
    console.print(table)
    console.print(f"\n💡 使用 'python -m src.cli.verify preview <doc_id>' 查看详情", style="dim")
    console.print(f"   使用 'python -m src.cli.verify approve <doc_id>' 批准", style="dim")
    console.print(f"   使用 'python -m src.cli.verify reject <doc_id>' 驳回\n", style="dim")


@app.command("preview")
def preview_document(
    doc_id: str = typer.Argument(..., help="文档ID（可使用前8位）"),
    lines: int = typer.Option(50, help="预览行数")
):
    """
    预览文档的Markdown转换结果
    
    示例:
    - python -m src.cli.verify preview 067afcfc
    """
    setup_logging()
    repo = SQLiteRepository()
    
    # 查找文档（支持前8位ID）
    with repo.get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT * FROM policy_documents WHERE id LIKE ?",
            (f"{doc_id}%",)
        ).fetchone()
    
    if not row:
        console.print(f"❌ 未找到文档: {doc_id}", style="red")
        raise typer.Exit(code=1)
    
    doc = repo._row_to_doc(row)
    
    # 读取Markdown文件
    md_path = Path("data/processed") / f"{doc.id}.md"
    
    if not md_path.exists():
        console.print(f"❌ Markdown文件不存在: {md_path}", style="red")
        raise typer.Exit(code=1)
    
    md_content = md_path.read_text(encoding='utf-8')
    md_lines = md_content.split('\n')
    
    # 显示文档信息
    info_panel = Panel(
        f"""[bold]文档信息[/bold]
        
ID: {doc.id}
文档类型: {doc.doc_type}
文件名: {doc.filename}
PDF路径: {doc.local_path}
Markdown长度: {len(md_content):,} 字符 ({len(md_lines)} 行)
状态: {doc.verification_status.value}
""",
        title="📄 Document Info",
        border_style="blue"
    )
    
    console.print(info_panel)
    
    # 显示Markdown预览
    preview_text = '\n'.join(md_lines[:lines])
    
    console.print(f"\n[bold]Markdown预览（前{lines}行）:[/bold]\n", style="yellow")
    console.print("─" * 80)
    console.print(preview_text)
    console.print("─" * 80)
    
    if len(md_lines) > lines:
        console.print(f"\n... 还有 {len(md_lines) - lines} 行未显示", style="dim")
    
    console.print(f"\n💡 完整文件: {md_path}", style="dim")
    console.print(f"   使用 'cat {md_path}' 查看完整内容\n", style="dim")


@app.command("approve")
def approve_document(
    doc_id: str = typer.Argument(..., help="文档ID（可使用前8位）"),
    notes: str = typer.Option("", help="审核备注")
):
    """
    批准文档（标记为VERIFIED）
    
    示例:
    - python -m src.cli.verify approve 067afcfc
    - python -m src.cli.verify approve 067afcfc --notes "格式完整，内容准确"
    """
    setup_logging()
    repo = SQLiteRepository()
    
    # 查找文档
    with repo.get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT * FROM policy_documents WHERE id LIKE ?",
            (f"{doc_id}%",)
        ).fetchone()
    
    if not row:
        console.print(f"❌ 未找到文档: {doc_id}", style="red")
        raise typer.Exit(code=1)
    
    doc = repo._row_to_doc(row)
    
    # 更新状态
    repo.update_document_status(
        doc.id,
        VerificationStatus.VERIFIED,
        notes or "审核通过"
    )
    
    console.print(f"✅ 文档已批准: {doc.filename}", style="green")
    console.print(f"   ID: {doc.id}", style="dim")
    if notes:
        console.print(f"   备注: {notes}", style="dim")


@app.command("reject")
def reject_document(
    doc_id: str = typer.Argument(..., help="文档ID（可使用前8位）"),
    reason: str = typer.Option(..., "--reason", "-r", help="驳回原因（必填）")
):
    """
    驳回文档（标记为REJECTED）
    
    示例:
    - python -m src.cli.verify reject 067afcfc -r "表格格式错误"
    """
    setup_logging()
    repo = SQLiteRepository()
    
    # 查找文档
    with repo.get_db_connection() as conn:
        cursor = conn.cursor()
        row = cursor.execute(
            "SELECT * FROM policy_documents WHERE id LIKE ?",
            (f"{doc_id}%",)
        ).fetchone()
    
    if not row:
        console.print(f"❌ 未找到文档: {doc_id}", style="red")
        raise typer.Exit(code=1)
    
    doc = repo._row_to_doc(row)
    
    # 更新状态
    repo.update_document_status(
        doc.id,
        VerificationStatus.REJECTED,
        reason
    )
    
    console.print(f"❌ 文档已驳回: {doc.filename}", style="red")
    console.print(f"   ID: {doc.id}", style="dim")
    console.print(f"   原因: {reason}", style="yellow")


@app.command("stats")
def show_stats():
    """
    显示文档审核统计
    
    示例:
    - python -m src.cli.verify stats
    """
    setup_logging()
    repo = SQLiteRepository()
    
    with repo.get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 统计各状态的文档数
        stats = {}
        for status in VerificationStatus:
            count = cursor.execute(
                "SELECT COUNT(*) FROM policy_documents WHERE verification_status = ?",
                (status.value,)
            ).fetchone()[0]
            stats[status.value] = count
        
        # 按文档类型统计
        type_stats = cursor.execute(
            """
            SELECT doc_type, verification_status, COUNT(*) 
            FROM policy_documents 
            WHERE doc_type IN ('产品条款', '产品说明书')
            GROUP BY doc_type, verification_status
            """
        ).fetchall()
    
    # 创建总体统计表
    table = Table(title="文档审核统计")
    
    table.add_column("状态", style="cyan")
    table.add_column("数量", style="magenta", justify="right")
    table.add_column("占比", style="green", justify="right")
    
    total = sum(stats.values())
    
    for status, count in stats.items():
        percentage = (count / total * 100) if total > 0 else 0
        
        # 状态颜色
        if status == "VERIFIED":
            status_text = f"✅ {status}"
            style = "green"
        elif status == "REJECTED":
            status_text = f"❌ {status}"
            style = "red"
        else:
            status_text = f"⏳ {status}"
            style = "yellow"
        
        table.add_row(
            status_text,
            str(count),
            f"{percentage:.1f}%"
        )
    
    table.add_row("━" * 10, "━" * 5, "━" * 8, style="dim")
    table.add_row("[bold]总计[/bold]", f"[bold]{total}[/bold]", "[bold]100.0%[/bold]")
    
    console.print("\n")
    console.print(table)
    
    # 按类型统计
    if type_stats:
        console.print("\n")
        type_table = Table(title="按文档类型统计")
        type_table.add_column("文档类型", style="cyan")
        type_table.add_column("状态", style="magenta")
        type_table.add_column("数量", style="green", justify="right")
        
        for doc_type, status, count in type_stats:
            type_table.add_row(doc_type, status, str(count))
        
        console.print(type_table)
    
    console.print("\n")


if __name__ == "__main__":
    app()

