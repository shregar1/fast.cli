"""Remove build and cache artifacts from a tree (``fast decimate``).

:class:`ArtifactDecimator` walks the filesystem under a root path and deletes
directories/files matching patterns from :data:`fastx_cli.constants.ARTIFACTS_BY_LANGUAGE`.
Common virtualenv directory names are pruned from the walk to avoid deleting
active environments.

This is a **destructive** operation; there is no undo. Use for local cleanup
before packaging or after failed builds.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import click
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.text import Text

from fastx_cli.constants import ARTIFACTS_BY_LANGUAGE, VENV_EXCLUDE_DIRS
from fastx_cli.output import output


class ArtifactDecimator:
    """Scan a directory tree and delete known language artifact paths."""

    def __init__(self, language: str, root: Path) -> None:
        """``language`` selects ``ARTIFACTS_BY_LANGUAGE`` (e.g. ``python``, ``java``)."""
        self._language = language
        self._root = root.resolve()

    def run(self) -> None:
        """Perform the scan and deletion pass, printing each removed path."""
        dir_patterns, file_patterns = self._patterns()
        exclude_dirs = VENV_EXCLUDE_DIRS

        output.print_banner()
        output.console.print(
            Panel.fit(
                Text("DECIMATING ARTIFACTS", style="bold red"),
                title="[bold white]Destruction Mode[/bold white]",
                border_style="red",
            )
        )
        output.console.print(f"[bold blue]Target:[/bold blue] {self._root}")
        output.console.print(f"[bold blue]Mode:[/bold blue] {self._language}")
        output.console.print()

        found: list[Path] = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold red]{task.description}"),
            console=output.console,
        ) as progress:
            progress.add_task(
                f"Scanning for {self._language} artifacts...", total=None
            )
            for walk_root, dirs, files in os.walk(self._root, topdown=True):
                valid_dirs = [d for d in dirs if d not in exclude_dirs]
                dirs.clear()
                dirs.extend(valid_dirs)
                p_root = Path(walk_root)
                for d in dirs:
                    full_p = p_root / d
                    for pattern in dir_patterns:
                        if full_p.match(pattern):
                            found.append(full_p)
                            break
                for f in files:
                    full_p = p_root / f
                    for pattern in file_patterns:
                        if full_p.match(pattern):
                            found.append(full_p)
                            break

        if not found:
            output.console.print(
                "[bold green]✓ Clean as a whistle! No artifacts found.[/bold green]"
            )
            return

        count = 0
        for item in found:
            try:
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
                rel = item.relative_to(self._root)
                output.console.print(f"  [bold red][-] Removed:[/bold red] {rel}")
                count += 1
            except OSError as e:
                output.console.print(f"  [bold yellow][!] Failed:[/bold yellow] {item} ({e})")

        output.console.print(
            f"\n[bold green]Successfully decimated {count} artifacts.[/bold green]"
        )

    def _patterns(self) -> tuple[list[str], list[str]]:
        """Return ``(dir_globs, file_globs)`` for the selected language alias."""
        if self._language in ARTIFACTS_BY_LANGUAGE:
            data = ARTIFACTS_BY_LANGUAGE[self._language]
            return list(set(data["dirs"])), list(set(data["files"]))
        if self._language in ("pycache", "python"):
            data = ARTIFACTS_BY_LANGUAGE["python"]
            return list(set(data["dirs"])), list(set(data["files"]))
        return [], []


def register_decimate_command(cli: click.Group) -> None:
    """Attach the ``decimate`` command to the root ``cli`` group."""

    @cli.command(name="decimate")
    @click.argument("language", default="python")
    @click.argument("path", default=".")
    def decimate_command(language: str, path: str) -> None:
        """🔥 Decimate: destroy cache and build artifacts."""
        ArtifactDecimator(language, Path(path)).run()
