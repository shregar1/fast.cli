"""Run project tests via pytest with common options."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import click

from fastx_cli.commands.project_root import resolve_fastmvc_project_root
from fastx_cli.output import output


def register_test_command(cli: click.Group) -> None:
    """Register the ``test`` command on the root CLI group."""

    @cli.command()
    @click.option("--watch", "-w", is_flag=True, help="Auto-rerun tests on file changes (pytest-watch)")
    @click.option("--coverage", "-c", is_flag=True, help="Run with coverage reporting")
    @click.option("--parallel", "-p", is_flag=True, help="Run tests in parallel with pytest-xdist")
    @click.option("--verbose", "-v", is_flag=True, help="Verbose pytest output")
    @click.option("--failfast", "-x", is_flag=True, help="Stop on first failure")
    @click.option("--marker", "-m", default=None, type=str, help='Pytest marker expression (e.g. "not slow")')
    @click.option("--path", default="tests/", type=str, help="Test path (default: tests/)")
    @click.option("--filter", "-k", "filter_expr", default=None, type=str, help="Pytest -k filter expression")
    def test(
        watch: bool,
        coverage: bool,
        parallel: bool,
        verbose: bool,
        failfast: bool,
        marker: str | None,
        path: str,
        filter_expr: str | None,
    ) -> None:
        """Run project tests with pytest.

        \b
        Examples:
            fastx test                        # Run all tests
            fastx test -v                     # Verbose output
            fastx test -x                     # Stop on first failure
            fastx test -w                     # Watch mode (auto-rerun)
            fastx test -c                     # With coverage report
            fastx test -p                     # Parallel execution
            fastx test -m "not slow"          # Skip slow-marked tests
            fastx test --path tests/unit      # Run only unit tests
            fastx test -k "test_login"        # Filter by test name
        """
        project_root = resolve_fastmvc_project_root(Path.cwd())

        output.console.print()
        output.console.print("[bold cyan]🧪 FastX Test Runner[/bold cyan]")
        output.console.print()

        if watch:
            # Use pytest-watch (ptw) for auto-rerun
            cmd = [sys.executable, "-m", "pytest_watch", "--"]
        else:
            cmd = [sys.executable, "-m", "pytest"]

        # Append pytest flags
        if coverage:
            cmd.extend(["--cov=.", "--cov-report=term-missing", "--cov-report=html"])

        if parallel:
            cmd.extend(["-n", "auto"])

        if verbose:
            cmd.append("-v")

        if failfast:
            cmd.append("-x")

        if marker:
            cmd.extend(["-m", marker])

        if filter_expr:
            cmd.extend(["-k", filter_expr])

        # Test path goes last
        cmd.append(path)

        output.console.print(f"  [dim]Command:[/dim]  [bold]{' '.join(cmd)}[/bold]")
        output.console.print()

        try:
            proc = subprocess.run(cmd, cwd=str(project_root))
            sys.exit(proc.returncode)
        except KeyboardInterrupt:
            output.console.print("\n[bold cyan]🧪 Test run stopped[/bold cyan]")
