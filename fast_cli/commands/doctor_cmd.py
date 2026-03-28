"""``fast doctor`` / ``fast check-env`` — toolchain and optional dependency probe."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from importlib import metadata

import click
from rich import box
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

from fast_cli import __version__
from fast_cli.output import output


def _version_dist(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "—"


def _tool_install_hint(tool_label: str) -> str:
    """One-line install guidance for common PATH tools."""
    if tool_label == "git":
        if sys.platform == "win32":
            return "Install Git for Windows: https://git-scm.com/download/win"
        if sys.platform == "darwin":
            return "brew install git"
        return "sudo apt install git   # Fedora: sudo dnf install git"
    if tool_label == "alembic":
        return "pip install alembic   # in your project virtual environment"
    if tool_label == "pre-commit":
        return "pip install pre-commit   or: pipx install pre-commit"
    if tool_label == "python3":
        return "Install Python 3.10+ from python.org or your OS package manager"
    return "Install via your OS package manager"


def _optional_install_hint(dist_name: str) -> str:
    if dist_name == "questionary":
        return "pip install 'fastmvc-cli[interactive]'"
    return f"pip install {dist_name}"


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

        missing_tools: list[tuple[str, str]] = []
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
                missing_tools.append((label, _tool_install_hint(label)))
        output.console.print()
        output.console.print(table)

        missing_optional: list[tuple[str, str]] = []
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
                missing_optional.append((mod, _optional_install_hint(dist)))
        output.console.print()
        output.console.print(opt_table)

        output.print_info(
            "Install optional stacks as needed (see fastmvc-cli extras on PyPI)."
        )

        _print_suggested_fixes(missing_tools, missing_optional)

    def _print_suggested_fixes(
        missing_tools: list[tuple[str, str]],
        missing_optional: list[tuple[str, str]],
    ) -> None:
        output.console.print()
        if not missing_tools and not missing_optional:
            output.console.print(
                Panel(
                    "[bold #34d399]You are in good shape.[/bold #34d399]\n\n"
                    "[dim]Next:[/dim]  [cyan]fast quickstart[/cyan]  or  [cyan]fast generate[/cyan]  "
                    "to scaffold a project, then open the generated README.",
                    title="[bold #34d399]Ready[/bold #34d399]",
                    border_style="#34d399",
                    box=box.ROUNDED,
                )
            )
            return

        lines: list[str] = []
        if missing_tools:
            lines.append("[bold]PATH tools[/bold]")
            for name, hint in missing_tools:
                lines.append(f"  • [yellow]{name}[/yellow]: {hint}")
            lines.append("")
        if missing_optional:
            lines.append("[bold]Python packages[/bold]")
            for mod, hint in missing_optional:
                lines.append(f"  • [yellow]{mod}[/yellow]: {hint}")

        text = "\n".join(lines).strip()
        output.console.print(
            Panel(
                text,
                title="[bold #fbbf24]Suggested next steps[/bold #fbbf24]",
                border_style="#fbbf24",
                box=box.ROUNDED,
            )
        )

    @cli.command("doctor")
    def doctor() -> None:
        """Check toolchain (git, alembic, …) and optional packages."""
        _run()

    @cli.command("check-env")
    def check_env() -> None:
        """Alias for ``doctor``."""
        _run()
