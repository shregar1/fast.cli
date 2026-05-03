"""FastCaching admin commands (optional dependency).

These commands import ``fastx_caching`` at runtime. If the package is not
installed in the active environment, the CLI prints an error and returns
without raising—mirroring the original behaviour for optional ecosystem tools.

Requires an asyncio event loop to call async cache backends; the implementation
creates a loop when none is running.
"""

from __future__ import annotations

import asyncio

import click
from rich.progress import Progress, SpinnerColumn, TextColumn

from fastx_cli.constants import (
    OPTIONAL_DEPS_FAST_CACHING_ERROR,
    OPTIONAL_DEPS_FAST_CACHING_IMPORT,
)
from fastx_cli.output import output


@click.group(name="cache")
def cache_group() -> None:
    """🚀 Manage FastCaching performance engine.

    Administrative tools for managing resident data, purging stale entries,
    and monitoring cache efficiency.
    """
    pass


@cache_group.command(name="clear")
def cache_clear() -> None:
    """Purge all resident cache data."""
    output.print_banner()
    try:
        from fastx_caching.src.fastx_caching import fastx_cache
    except ImportError:
        output.print_error(OPTIONAL_DEPS_FAST_CACHING_ERROR)
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        console=output.console,
    ) as progress:
        task = progress.add_task("[cyan]Purging cache entries...", total=None)
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        success = loop.run_until_complete(fastx_cache.backend.clear())
        progress.update(task, completed=True)

    if success:
        output.print_success("Global cache cleared successfully")
    else:
        output.print_error("Failed to clear cache")


@cache_group.command(name="invalidate")
@click.argument("tags", nargs=-1)
def cache_invalidate(tags: tuple[str, ...]) -> None:
    """Invalidate specific cache tags."""
    if not tags:
        output.print_error("Please specify at least one tag to invalidate")
        return

    output.print_banner()
    try:
        from fastx_caching.src.fastx_caching import fastx_cache
    except ImportError:
        output.print_error(OPTIONAL_DEPS_FAST_CACHING_ERROR)
        return

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        console=output.console,
    ) as progress:
        task = progress.add_task(
            f"[cyan]Invalidating tags: {', '.join(tags)}...", total=None
        )
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        count = loop.run_until_complete(fastx_cache.invalidate(list(tags)))
        progress.update(task, completed=True)

    output.print_success(
        f"Purged {count} entries associated with tags: {', '.join(tags)}"
    )
