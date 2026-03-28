"""``fast doctor`` / ``fast check-env`` — toolchain and optional dependency probe."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from importlib import metadata

import click
from rich.rule import Rule
from rich.table import Table

from fast_cli import __version__
from fast_cli.output import output


def _version_dist(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "—"


def register_doctor_commands(cli: click.Group) -> None:
    """Register ``doctor`` and ``check-env`` on the root group."""

    def _run() -> None:
        output.print_banner()
        output.console.print(
            Rule(
                "[bold #38bdf8]Environment[/bold #38bdf8]",
                style="dim #475569",
                characters="─",
            )
        )
        output.console.print()
        output.console.print(f"  [dim]fast_cli[/dim]  {__version__}")
        output.console.print(
            f"  [dim]python[/dim]  {sys.version.split()[0]} ({sys.executable})"
        )

        table = Table(
            title="Tools (PATH)",
            show_header=True,
            header_style="bold #38bdf8",
            border_style="dim #334155",
        )
        table.add_column("Name")
        table.add_column("Status")
        table.add_column("Path or note")
        for label, exe in (
            ("git", "git"),
            ("alembic", "alembic"),
            ("pre-commit", "pre-commit"),
            ("python3", "python3"),
        ):
            p = shutil.which(exe)
            if p:
                table.add_row(label, "[green]found[/green]", p)
            else:
                table.add_row(label, "[yellow]missing[/yellow]", "—")
        output.console.print()
        output.console.print(table)

        opt_table = Table(
            title="Optional Python packages",
            show_header=True,
            header_style="bold #a78bfa",
            border_style="dim #334155",
        )
        opt_table.add_column("Import")
        opt_table.add_column("Status")
        opt_table.add_column("Version")
        optional = [
            ("fast_caching", "fast-caching"),
            ("fast_platform", "fast-platform"),
            ("questionary", "questionary"),
        ]
        for mod, dist in optional:
            spec = importlib.util.find_spec(mod)
            if spec is not None:
                ver = _version_dist(dist)
                opt_table.add_row(mod, "[green]installed[/green]", ver)
            else:
                opt_table.add_row(mod, "[dim]not installed[/dim]", "—")
        output.console.print()
        output.console.print(opt_table)
        output.print_info(
            "Install optional stacks as needed (see fastmvc-cli extras on PyPI)."
        )

    @cli.command("doctor")
    def doctor() -> None:
        """Check toolchain (git, alembic, …) and optional packages."""
        _run()

    @cli.command("check-env")
    def check_env() -> None:
        """Alias for ``doctor``."""
        _run()
