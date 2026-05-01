"""Auto-upgrade all fastx packages to their latest PyPI versions."""

from __future__ import annotations

import importlib.metadata
import re
import subprocess
import sys

import click

from fastx_cli.output import output

FASTX_PACKAGES = [
    "fastx-platform",
    "fastx-database",
    "fastx-middleware",
    "fastx-cli",
    "fastx-dashboards",
    "fastx-mvc",
    "fastx-channels",
]


def _get_installed_version(pkg: str) -> str | None:
    """Return the installed version string, or None if not installed."""
    try:
        return importlib.metadata.version(pkg)
    except importlib.metadata.PackageNotFoundError:
        return None


def _get_latest_version(pkg: str) -> str | None:
    """Query PyPI for the latest version via ``pip install <pkg>==``."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", f"{pkg}=="],
            capture_output=True,
            text=True,
        )
        # pip prints available versions in the error output like:
        # "... (from versions: 0.1.0, 0.2.0, 1.0.0)"
        stderr = result.stderr
        match = re.search(r"\(from versions:\s*(.+?)\)", stderr)
        if match:
            versions = [v.strip() for v in match.group(1).split(",") if v.strip()]
            if versions:
                return versions[-1]
    except Exception:
        pass
    return None


def _build_package_table(packages: list[str]) -> list[dict]:
    """Build a list of dicts with package info for display."""
    rows: list[dict] = []
    for pkg in packages:
        installed = _get_installed_version(pkg)
        latest = _get_latest_version(pkg)
        if installed is None:
            status = "not installed"
        elif latest is None:
            status = "unknown"
        elif installed == latest:
            status = "up-to-date"
        else:
            status = "outdated"
        rows.append({
            "package": pkg,
            "installed": installed or "-",
            "latest": latest or "-",
            "status": status,
        })
    return rows


def _print_table(rows: list[dict]) -> None:
    """Render the package status table using Rich."""
    from rich.table import Table

    table = Table(title="FastX Packages", show_lines=False)
    table.add_column("Package", style="bold")
    table.add_column("Current", justify="center")
    table.add_column("Latest", justify="center")
    table.add_column("Status", justify="center")

    status_styles = {
        "up-to-date": "[green]up-to-date[/green]",
        "outdated": "[yellow]outdated[/yellow]",
        "not installed": "[dim]not installed[/dim]",
        "unknown": "[red]unknown[/red]",
    }

    for row in rows:
        table.add_row(
            row["package"],
            row["installed"],
            row["latest"],
            status_styles.get(row["status"], row["status"]),
        )

    output.console.print()
    output.console.print(table)
    output.console.print()


def register_upgrade_command(cli: click.Group) -> None:
    """Register the ``upgrade`` command on the root CLI group."""

    @cli.command()
    @click.option("--check", is_flag=True, help="Only check versions, don't upgrade")
    @click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
    @click.option("--package", "-p", multiple=True, help="Upgrade specific package(s) only")
    def upgrade(check: bool, yes: bool, package: tuple[str, ...]) -> None:
        """Auto-upgrade all fastx packages to latest versions.

        \b
        Examples:
            fastx upgrade              # Upgrade all fastx packages
            fastx upgrade --check      # Just show version status
            fastx upgrade -y           # Upgrade without confirmation
            fastx upgrade -p fastx-cli # Upgrade only fastx-cli
        """
        packages = list(package) if package else FASTX_PACKAGES

        # Validate user-specified packages
        if package:
            invalid = [p for p in packages if p not in FASTX_PACKAGES]
            if invalid:
                output.print_error(
                    f"Unknown package(s): {', '.join(invalid)}. "
                    f"Valid packages: {', '.join(FASTX_PACKAGES)}"
                )
                raise SystemExit(1)

        output.console.print()
        output.print_info("Checking fastx package versions...")

        rows = _build_package_table(packages)
        _print_table(rows)

        outdated = [r["package"] for r in rows if r["status"] == "outdated"]

        if not outdated:
            output.print_success("All packages are up-to-date!")
            return

        if check:
            output.print_warning(f"{len(outdated)} package(s) can be upgraded.")
            return

        output.print_info(f"{len(outdated)} package(s) to upgrade: {', '.join(outdated)}")

        if not yes:
            if not click.confirm("Proceed with upgrade?"):
                output.print_warning("Upgrade cancelled.")
                return

        cmd = [sys.executable, "-m", "pip", "install", "--upgrade", *outdated]
        output.console.print()
        output.print_info(f"Running: {' '.join(cmd)}")
        output.console.print()

        result = subprocess.run(cmd)
        output.console.print()

        if result.returncode == 0:
            output.print_success("Upgrade completed successfully!")
        else:
            output.print_error(f"Upgrade failed with exit code {result.returncode}.")
            raise SystemExit(result.returncode)
