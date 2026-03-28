"""FastTasks / ``fast_platform`` worker commands (optional dependency).

Imports ``fast_platform.src.task`` at runtime. Missing packages produce a
clear error message rather than failing at import time, so ``fast-cli`` stays
installable without the full Fast stack.

The dashboard command uses :class:`rich.live.Live` for periodic refresh; interrupt
with Ctrl+C.
"""

from __future__ import annotations

import asyncio
import time

import click
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich import box

from fast_cli.output import output


@click.group(name="tasks")
def tasks_group() -> None:
    """⚙️ Manage FastTasks background processing.

    Administrative tools for launching workers, monitoring job status,
    and managing the task queue lifecycle.
    """
    pass


@tasks_group.command(name="worker")
@click.option("--concurrency", "-c", default=10, help="Max active tasks")
def tasks_worker(concurrency: int) -> None:
    """Launch a background task worker."""
    output.print_banner()
    try:
        from fast_platform.src.task import Worker
    except ImportError:
        output.print_error("fast_tasks package not found in paths")
        return

    output.print_success(f"Starting FastTasks Worker (concurrency={concurrency})...")
    worker = Worker(concurrency=concurrency)
    try:
        asyncio.run(worker.start())
    except KeyboardInterrupt:
        output.print_info("Shutdown signal received...")
        output.print_success("Worker stopped.")


@tasks_group.command(name="list")
def tasks_list() -> None:
    """List all registered task definitions."""
    output.print_banner()
    try:
        from fast_platform.src.task import TaskRegistry
    except ImportError:
        output.print_error("fast_tasks package not found in paths")
        return

    tasks = TaskRegistry.all_tasks()
    if not tasks:
        output.print_info("No tasks registered in the registry.")
        return

    table = Table(title="Registered FastTasks", box=box.ROUNDED)
    table.add_column("Task Name", style="cyan")
    table.add_column("Function", style="green")
    table.add_column("Retries", style="magenta")
    for name, meta in tasks.items():
        table.add_row(name, meta.fn.__name__, str(meta.retry))
    output.console.print(table)


@tasks_group.command(name="status")
@click.argument("task_id")
def tasks_status(task_id: str) -> None:
    """Check the status of a specific job."""
    output.print_banner()
    try:
        from fast_platform.src.task import fast_tasks
    except ImportError:
        output.print_error("fast_tasks package not found in paths")
        return

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    result = loop.run_until_complete(fast_tasks.backend.get_result(task_id))
    if not result:
        output.print_error(f"Task {task_id} not found.")
        return

    table = Table(show_header=False, box=box.SIMPLE_HEAD)
    table.add_column("Key", style="bold cyan")
    table.add_column("Value")
    table.add_row("Task ID", result.task_id)
    status_style = (
        "green"
        if result.status == "success"
        else "yellow" if result.status == "running" else "red"
    )
    table.add_row("Status", f"[{status_style}]{result.status}")
    table.add_row("Timestamp", str(result.timestamp))
    if result.result:
        table.add_row("Result", str(result.result))
    if result.error:
        table.add_row("Error", f"[red]{result.error}")
    output.console.print(Panel(table, title=f"Task Info: {task_id}", border_style="blue"))


@tasks_group.command(name="dashboard")
@click.option("--refresh", "-r", default=1000, help="Refresh interval (ms)")
def tasks_dashboard(refresh: int) -> None:
    """📊 Live dashboard for FastTasks monitoring."""
    try:
        from fast_platform.src.task import TaskRegistry, fast_tasks
    except ImportError:
        output.print_error("fast_tasks package not found in paths")
        return

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    def build_table() -> Table:
        table = Table(title="FastTasks Dashboard", box=box.HORIZONTALS)
        table.add_column("Task", style="cyan")
        table.add_column("Status", style="magenta")
        table.add_column("Last Run", style="dim")
        table.add_column("Success Rate", justify="right")
        for name, _meta in TaskRegistry.all_tasks().items():
            result = loop.run_until_complete(fast_tasks.backend.get_result(name))
            status = result.status if result else "N/A"
            table.add_row(name, status, "Just now", "100%")
        return table

    with Live(build_table(), refresh_per_second=1000 / refresh) as live:
        try:
            while True:
                time.sleep(refresh / 1000)
                live.update(build_table())
        except KeyboardInterrupt:
            pass
