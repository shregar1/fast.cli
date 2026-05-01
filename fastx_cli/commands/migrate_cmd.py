"""Auto-detect model changes and generate Alembic migrations.

The ``migrate`` group provides a streamlined workflow for detecting
SQLAlchemy model changes and generating corresponding Alembic migrations
without manually writing revision files.

Subcommands
-----------
- ``auto``    — scan models, compare against the current DB schema, auto-generate
- ``status``  — show current migration head vs database
- ``history`` — show migration history

Examples::

    fastx migrate auto -m "Add users table"
    fastx migrate auto --dry-run
    fastx migrate status
    fastx migrate history -v
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import click
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from fastx_cli.output import output

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TIMEOUT_QUERY = 30
_TIMEOUT_MUTATION = 120


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_alembic_binary() -> None:
    """Ensure ``alembic`` is on ``PATH``; abort if missing."""
    if not shutil.which("alembic"):
        output.print_error("Alembic not found. Install with: pip install alembic")
        output.console.print(
            Panel(
                "[dim]Make sure you're in your virtual environment:\n"
                "  source .venv/bin/activate  # Linux/Mac\n"
                "  .venv\\Scripts\\activate    # Windows[/dim]",
                title="Tip",
                border_style="yellow",
            )
        )
        raise click.Abort()


def _require_alembic_ini() -> None:
    """Ensure ``alembic.ini`` exists in the process CWD; abort if missing."""
    if not Path("alembic.ini").exists():
        output.print_error(
            "alembic.ini not found in the current directory. "
            "Are you in a FastMVC project root?"
        )
        raise click.Abort()


# ---------------------------------------------------------------------------
# Click group
# ---------------------------------------------------------------------------


@click.group()
def migrate() -> None:
    """Auto-detect model changes and manage Alembic migrations.

    Provides shortcuts for the most common Alembic migration workflows.

    Examples:
        fastx migrate auto -m "Add users table"
        fastx migrate status
        fastx migrate history
    """


# ---------------------------------------------------------------------------
# auto
# ---------------------------------------------------------------------------


@migrate.command()
@click.option(
    "--message",
    "-m",
    default="auto migration",
    show_default=True,
    help="Migration message/description.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would change without generating a migration.",
)
@click.option(
    "--autogenerate/--no-autogenerate",
    default=True,
    help="Use Alembic autogenerate (default: true).",
)
def auto(message: str, dry_run: bool, autogenerate: bool) -> None:
    """Scan models and auto-generate an Alembic migration.

    Compares SQLAlchemy models against the current database schema and
    generates a new migration revision capturing the differences.
    """
    output.print_banner()
    _require_alembic_binary()
    _require_alembic_ini()

    if dry_run:
        output.console.print(
            "\n[bold cyan]Dry run:[/bold cyan] checking for pending model changes\n"
        )
        try:
            result = subprocess.run(
                ["alembic", "check"],
                capture_output=True,
                text=True,
                timeout=_TIMEOUT_QUERY,
            )
            if result.returncode == 0:
                output.console.print(
                    "[green]No new model changes detected.[/green] "
                    "Database schema is up to date."
                )
            else:
                output.console.print(
                    "[yellow]Model changes detected.[/yellow] "
                    "A migration would be generated.\n"
                )
                if result.stdout:
                    output.console.print(f"[dim]{result.stdout.strip()}[/dim]")
                if result.stderr:
                    output.console.print(f"[dim]{result.stderr.strip()}[/dim]")
        except subprocess.TimeoutExpired:
            output.print_error("Dry-run check timed out.")
            raise click.Abort()
        except Exception as exc:
            output.print_error(f"Error during dry-run check: {exc}")
            raise click.Abort()
        return

    # Full migration generation
    output.console.print(
        f"\n[bold cyan]Generating migration:[/bold cyan] {message}\n"
    )

    cmd = ["alembic", "revision"]
    if autogenerate:
        cmd.append("--autogenerate")
    cmd.extend(["-m", message])

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        console=output.console,
    ) as progress:
        task = progress.add_task("[cyan]Generating migration...", total=None)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=_TIMEOUT_MUTATION,
            )
            progress.update(task, completed=True)

            if result.returncode != 0:
                output.print_error(f"Migration failed:\n{result.stderr}")
                raise click.Abort()

            # Try to extract the generated file path from Alembic output
            migration_file = None
            for line in result.stdout.split("\n"):
                if "Generating" in line and ".py" in line:
                    migration_file = line.split()[-1]
                    break

            output.print_success("Migration created successfully!")
            if migration_file:
                output.console.print(
                    f"\n[dim]Migration file:[/dim] [cyan]{migration_file}[/cyan]"
                )

            output.console.print(
                Panel(
                    "[dim]Next steps:[/dim]\n"
                    "  1. Review the generated migration file\n"
                    "  2. Edit if needed (e.g., add data migrations)\n"
                    "  3. Run [cyan]fastx db upgrade[/cyan] to apply",
                    title="Review Migration",
                    border_style="blue",
                )
            )
        except subprocess.TimeoutExpired:
            output.print_error("Migration generation timed out.")
            raise click.Abort()
        except click.Abort:
            raise
        except Exception as exc:
            output.print_error(f"Error creating migration: {exc}")
            raise click.Abort()


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@migrate.command()
def status() -> None:
    """Show current migration head vs database revision."""
    output.print_banner()
    output.console.print("\n[bold cyan]Migration Status[/bold cyan]\n")
    _require_alembic_binary()
    _require_alembic_ini()

    try:
        # Current database revision
        result = subprocess.run(
            ["alembic", "current"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_QUERY,
        )
        if result.returncode == 0:
            current = result.stdout.strip()
            if current:
                output.console.print(
                    f"[bold]Database revision:[/bold] [green]{current}[/green]"
                )
            else:
                output.console.print(
                    "[bold]Database revision:[/bold] "
                    "[yellow]None (database not initialized)[/yellow]"
                )
        else:
            output.print_error(f"Failed to get current revision:\n{result.stderr}")

        # Latest head
        result = subprocess.run(
            ["alembic", "heads"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_QUERY,
        )
        if result.returncode == 0:
            heads = result.stdout.strip()
            if heads:
                output.console.print(
                    f"[bold]Migration head:[/bold]   [cyan]{heads.split()[0]}[/cyan]"
                )
            else:
                output.console.print(
                    "[bold]Migration head:[/bold]   [dim]No migrations found[/dim]"
                )

        # Pending count
        result = subprocess.run(
            ["alembic", "history", "--indicate-current"],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_QUERY,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            pending = [
                ln for ln in lines if "(current)" not in ln and ln.strip()
            ]
            output.console.print()
            if pending:
                output.console.print(
                    f"[bold]Pending:[/bold]          "
                    f"[yellow]{len(pending)} migration(s) not applied[/yellow]"
                )
                output.console.print(
                    "\n[dim]Run 'fastx db upgrade' to apply pending migrations.[/dim]"
                )
            else:
                output.console.print(
                    "[bold]Pending:[/bold]          "
                    "[green]Database is up to date[/green]"
                )
    except subprocess.TimeoutExpired:
        output.print_error("Status check timed out.")
        raise click.Abort()
    except Exception as exc:
        output.print_error(f"Error checking status: {exc}")
        raise click.Abort()


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------


@migrate.command()
@click.option(
    "--verbose/--no-verbose",
    "-v",
    default=False,
    help="Show detailed information.",
)
def history(verbose: bool) -> None:
    """Show migration history."""
    output.print_banner()
    output.console.print("\n[bold cyan]Migration History[/bold cyan]\n")
    _require_alembic_binary()
    _require_alembic_ini()

    try:
        cmd = ["alembic", "history"]
        if verbose:
            cmd.append("--verbose")
        cmd.append("--indicate-current")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_QUERY,
        )

        if result.returncode != 0:
            output.print_error(f"Failed to get history:\n{result.stderr}")
            raise click.Abort()

        history_output = result.stdout.strip()
        if not history_output:
            output.console.print("[dim]No migrations found.[/dim]")
            return

        for line in history_output.split("\n"):
            if "(current)" in line:
                output.console.print(f"[green]> {line}[/green]")
            elif line.strip():
                output.console.print(f"  {line}")
    except subprocess.TimeoutExpired:
        output.print_error("History retrieval timed out.")
        raise click.Abort()
    except click.Abort:
        raise
    except Exception as exc:
        output.print_error(f"Error getting history: {exc}")
        raise click.Abort()


# ---------------------------------------------------------------------------
# Registration helper
# ---------------------------------------------------------------------------


def register_migrate(cli):
    """Register the ``migrate`` group on the top-level CLI."""
    cli.add_command(migrate)
