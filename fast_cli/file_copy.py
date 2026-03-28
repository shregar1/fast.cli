"""Copy the framework tree into a new project with Rich progress feedback.

:class:`ProjectCopier` walks a list of relative paths (files and directories)
under the FastMVC source root. Directories use :func:`shutil.copytree` with
ignore patterns for ``.git`` and caches; files use :func:`shutil.copy2` followed
by :meth:`fast_cli.template_engine.TemplateRenderer.process_file` for text
substitution.

The return value is the **count** of items successfully copied (directories and
files each count as one item), matching the legacy CLI behaviour.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from fast_cli.output import output
from fast_cli.template_engine import TemplateRenderer


class ProjectCopier:
    """Copy template items from ``source`` into ``target`` with a progress bar."""

    def __init__(self, renderer: TemplateRenderer | None = None) -> None:
        self._renderer = renderer or TemplateRenderer()

    def copy_with_progress(
        self, source: Path, target: Path, items: list[str], context: dict
    ) -> int:
        """Copy each ``item`` in ``items`` from ``source`` to ``target``.

        Parameters
        ----------
        source
            Resolved :meth:`FrameworkSourceLocator.fast_mvc_root`.
        target
            New project directory (created by caller if needed).
        items
            Basenames from :meth:`FrameworkSourceLocator.list_existing_template_items`.
        context
            Passed to :class:`~fast_cli.template_engine.TemplateRenderer` for files.

        Returns
        -------
        int
            Number of items copied (skipped items do not increment).
        """
        copied = 0
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(complete_style="green", finished_style="green"),
            TaskProgressColumn(),
            TimeRemainingColumn(),
            console=output.console,
        ) as progress:
            task = progress.add_task("[cyan]Copying files...", total=len(items))
            for item in items:
                source_path = source / item
                target_item_path = target / item
                progress.update(task, description=f"[cyan]Copying {item}...")
                try:
                    if source_path.is_dir():
                        if item == ".git":
                            progress.update(task, advance=1)
                            continue
                        shutil.copytree(
                            source_path,
                            target_item_path,
                            ignore=shutil.ignore_patterns(
                                ".git", "__pycache__", "*.pyc", ".DS_Store"
                            ),
                        )
                    else:
                        shutil.copy2(source_path, target_item_path)
                        self._renderer.process_file(target_item_path, context)
                    copied += 1
                except OSError as e:
                    output.print_warning(f"Skipped {item}: {e}")
                progress.update(task, advance=1)
        return copied
