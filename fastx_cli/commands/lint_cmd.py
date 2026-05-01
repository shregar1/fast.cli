"""Lint and format the project using ruff and optionally mypy."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import click

from fastx_cli.commands.project_root import resolve_fastmvc_project_root
from fastx_cli.output import output


def _tool_exists(name: str) -> bool:
    """Return True if *name* is on ``$PATH``."""
    return shutil.which(name) is not None


def _run(cmd: list[str], label: str) -> int:
    """Run *cmd*, print a header, and return the exit code."""
    output.console.print(f"\n[bold cyan]>>> {label}[/bold cyan]")
    output.console.print(f"[dim]  {' '.join(cmd)}[/dim]\n")
    result = subprocess.run(cmd)
    return result.returncode


def register_lint_command(cli: click.Group) -> None:
    """Register the ``lint`` command on the root CLI group."""

    @cli.command()
    @click.option("--fix", is_flag=True, help="Auto-fix issues (ruff check --fix + ruff format)")
    @click.option("--type-check", is_flag=True, help="Also run mypy for type checking")
    @click.option("--strict", is_flag=True, help="Strict mode: --strict for mypy, --select ALL for ruff")
    @click.option("--path", "target_path", default=None, type=click.Path(exists=True), help="Path to lint (default: project root)")
    def lint(fix: bool, type_check: bool, strict: bool, target_path: str | None) -> None:
        """Lint and format the project with ruff (and optionally mypy).

        \b
        Examples:
            fastx lint                  # Check for lint errors and formatting
            fastx lint --fix            # Auto-fix lint errors and reformat
            fastx lint --type-check     # Also run mypy
            fastx lint --strict         # Strict ruff (--select ALL) and mypy (--strict)
            fastx lint --path src/      # Lint a specific directory
        """
        project_root = resolve_fastmvc_project_root(Path.cwd())
        lint_target = target_path if target_path else str(project_root)

        output.console.print()
        output.console.print("[bold cyan]Lint & Format[/bold cyan]")

        results: list[tuple[str, int]] = []

        # --- ruff check ---
        if not _tool_exists("ruff"):
            output.print_error("ruff not found — install with: pip install ruff")
            sys.exit(1)

        ruff_check_cmd = ["ruff", "check"]
        if fix:
            ruff_check_cmd.append("--fix")
        if strict:
            ruff_check_cmd.extend(["--select", "ALL"])
        ruff_check_cmd.append(lint_target)

        rc = _run(ruff_check_cmd, "Ruff Check")
        results.append(("Ruff Check", rc))

        # --- ruff format ---
        ruff_fmt_cmd = ["ruff", "format"]
        if not fix:
            ruff_fmt_cmd.append("--check")
        ruff_fmt_cmd.append(lint_target)

        rc = _run(ruff_fmt_cmd, "Ruff Format")
        results.append(("Ruff Format", rc))

        # --- mypy (optional) ---
        if type_check:
            if not _tool_exists("mypy"):
                output.print_error("mypy not found — install with: pip install mypy")
                sys.exit(1)

            mypy_cmd = ["mypy"]
            if strict:
                mypy_cmd.append("--strict")
            mypy_cmd.append(lint_target)

            rc = _run(mypy_cmd, "Mypy")
            results.append(("Mypy", rc))

        # --- Summary ---
        output.console.print()
        output.console.print("[bold]Summary[/bold]")
        output.console.print()

        all_passed = True
        for name, code in results:
            if code == 0:
                output.print_success(f"{name}: passed")
            else:
                output.print_error(f"{name}: failed (exit code {code})")
                all_passed = False

        output.console.print()

        if all_passed:
            output.print_success("All checks passed!")
        else:
            output.print_error("Some checks failed.")
            sys.exit(1)
