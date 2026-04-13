"""Alembic / DataI migration commands.

These subcommands are thin **wrappers** around the ``alembic`` CLI installed in
the user’s environment. They assume the user has ``cd``’d into a project with
``alembic.ini`` at the current working directory (typical FastMVC layout).

:class:`AlembicProjectGuard` centralizes preflight checks so each command stays
focused on subprocess orchestration and Rich output.

Dangerous operations (``db reset``, ``db downgrade``) use Questionary or Click
confirmations when available.

See Also
--------
https://alembic.sqlalchemy.org/en/latest/tutorial.html — Alembic concepts.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import click
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from fast_cli.constants import (
    TIMEOUT_ALEMBIC_MUTATION,
    TIMEOUT_ALEMBIC_QUERY,
    TIMEOUT_SEED_SCRIPT,
)
from fast_cli.output import output
from fast_cli.validators import HAS_QUESTIONARY

if HAS_QUESTIONARY:
    import questionary


class AlembicProjectGuard:
    """Fail fast with user-facing errors before spawning ``alembic``."""

    @staticmethod
    def require_alembic_binary() -> None:
        """Ensure ``alembic`` is on ``PATH``; abort if missing."""
        if not shutil.which("alembic"):
            output.print_error("Alembic not found. Install with: pip install alembic")
            raise click.Abort()

    @staticmethod
    def require_alembic_ini() -> None:
        """Ensure ``alembic.ini`` exists in the process CWD; abort if missing."""
        if not Path("alembic.ini").exists():
            output.print_error(
                "alembic.ini not found. Are you in a FastMVC project directory?"
            )
            raise click.Abort()


@click.group(name="db")
def db_group() -> None:
    """🗄️ DataI migration commands using Alembic.

    Manage dataI schema migrations with simple commands.
    Requires Alembic to be installed in your project.

    Examples:
        fast db migrate -m "Add users table"
        fast db upgrade
        fast db reset

    """
    pass


@db_group.command(name="migrate")
@click.option("--message", "-m", required=True, help="Migration message/description")
@click.option(
    "--autogenerate/--no-autogenerate",
    default=True,
    help="Auto-generate migration from models (default: True)",
)
def db_migrate(message: str, autogenerate: bool) -> None:
    """📝 Create a new dataI migration."""
    output.print_banner()
    output.console.print(f"\n[bold cyan]Creating migration:[/bold cyan] {message}\n")

    if not shutil.which("alembic"):
        output.print_error("Alembic not found. Install with: pip install alembic")
        output.console.print(
            Panel(
                "[dim]Make sure you're in your virtual environment:\n"
                "  source .venv/bin/activate  # Linux/Mac\n"
                "  .venv\\Scripts\\activate    # Windows[/dim]",
                title="💡 Tip",
                border_style="yellow",
            )
        )
        raise click.Abort()

    AlembicProjectGuard.require_alembic_ini()

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
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_ALEMBIC_MUTATION)
            progress.update(task, completed=True)
            if result.returncode != 0:
                output.print_error(f"Migration failed:\n{result.stderr}")
                raise click.Abort()
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
                    "  3. Run [cyan]fast db upgrade[/cyan] to apply",
                    title="📝 Review Migration",
                    border_style="blue",
                )
            )
        except subprocess.TimeoutExpired:
            output.print_error("Migration timed out")
            raise click.Abort()
        except Exception as e:
            output.print_error(f"Error creating migration: {e}")
            raise click.Abort()


@db_group.command(name="upgrade")
@click.option(
    "--revision", "-r", default="head", help="Target revision (default: head)"
)
def db_upgrade(revision: str) -> None:
    """⬆️ Apply dataI migrations."""
    output.print_banner()
    output.console.print(f"\n[bold cyan]Upgrading dataI to:[/bold cyan] {revision}\n")
    AlembicProjectGuard.require_alembic_binary()
    AlembicProjectGuard.require_alembic_ini()

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        console=output.console,
    ) as progress:
        task = progress.add_task("[cyan]Applying migrations...", total=None)
        try:
            current_result = subprocess.run(
                ["alembic", "current"], capture_output=True, text=True, timeout=TIMEOUT_ALEMBIC_QUERY
            )
            current_rev = (
                current_result.stdout.strip()
                if current_result.returncode == 0
                else "None"
            )
            result = subprocess.run(
                ["alembic", "upgrade", revision],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_ALEMBIC_MUTATION,
            )
            progress.update(task, completed=True)
            if result.returncode != 0:
                output.print_error(f"Upgrade failed:\n{result.stderr}")
                raise click.Abort()
            new_result = subprocess.run(
                ["alembic", "current"], capture_output=True, text=True, timeout=30
            )
            new_rev = (
                new_result.stdout.strip() if new_result.returncode == 0 else "Unknown"
            )
            output.print_success("DataI upgraded successfully!")
            output.console.print(f"\n[dim]Previous:[/dim] {current_rev}")
            output.console.print(f"[dim]Current:[/dim]  [green]{new_rev}[/green]")
            if result.stdout:
                output.console.print(f"\n[dim]Output:[/dim]\n{result.stdout}")
        except subprocess.TimeoutExpired:
            output.print_error("Upgrade timed out")
            raise click.Abort()
        except Exception as e:
            output.print_error(f"Error upgrading dataI: {e}")
            raise click.Abort()


@db_group.command(name="downgrade")
@click.option(
    "--revision",
    "-r",
    default="-1",
    help="Target revision (default: -1, one step back)",
)
def db_downgrade(revision: str) -> None:
    """⬇️ Rollback dataI migrations."""
    output.print_banner()
    output.console.print(
        f"\n[bold yellow]Downgrading dataI to:[/bold yellow] {revision}\n"
    )
    output.console.print(
        Panel(
            "[bold yellow]⚠️ Warning:[/bold yellow] This will rollback dataI changes.\n"
            "Data loss may occur if migrations include data transformations.",
            border_style="yellow",
        )
    )
    if HAS_QUESTIONARY:
        if not questionary.confirm("Are you sure you want to continue?").ask():
            output.print_error("Cancelled.")
            return
    elif not click.confirm("Are you sure you want to continue?"):
        output.print_error("Cancelled.")
        return

    AlembicProjectGuard.require_alembic_binary()
    AlembicProjectGuard.require_alembic_ini()

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        console=output.console,
    ) as progress:
        task = progress.add_task("[cyan]Rolling back migrations...", total=None)
        try:
            current_result = subprocess.run(
                ["alembic", "current"], capture_output=True, text=True, timeout=TIMEOUT_ALEMBIC_QUERY
            )
            current_rev = (
                current_result.stdout.strip()
                if current_result.returncode == 0
                else "None"
            )
            result = subprocess.run(
                ["alembic", "downgrade", revision],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_ALEMBIC_MUTATION,
            )
            progress.update(task, completed=True)
            if result.returncode != 0:
                output.print_error(f"Downgrade failed:\n{result.stderr}")
                raise click.Abort()
            new_result = subprocess.run(
                ["alembic", "current"], capture_output=True, text=True, timeout=30
            )
            new_rev = (
                new_result.stdout.strip() if new_result.returncode == 0 else "Unknown"
            )
            output.print_success("DataI downgraded successfully!")
            output.console.print(f"\n[dim]Previous:[/dim] {current_rev}")
            output.console.print(f"[dim]Current:[/dim]  [yellow]{new_rev}[/yellow]")
        except subprocess.TimeoutExpired:
            output.print_error("Downgrade timed out")
            raise click.Abort()
        except Exception as e:
            output.print_error(f"Error downgrading dataI: {e}")
            raise click.Abort()


@db_group.command(name="reset")
@click.option("--seed/--no-seed", default=False, help="Run seed data after reset")
def db_reset(seed: bool) -> None:
    """🔄 Reset dataI (drop all tables and recreate)."""
    output.print_banner()
    output.console.print("\n[bold red]⚠️ DataI Reset[/bold red]\n")
    output.console.print(
        Panel(
            "[bold red]DANGER:[/bold red] This will DELETE ALL DATA in the dataI!\n\n"
            "This operation will:\n"
            "  1. Rollback all migrations (drop all tables)\n"
            "  2. Re-apply all migrations (recreate tables)\n"
            "  3. Optionally run seed data\n\n"
            "[bold]This action cannot be undone![/bold]",
            border_style="red",
        )
    )

    if HAS_QUESTIONARY:
        if not questionary.confirm("Do you want to continue?").ask():
            output.print_error("Cancelled.")
            return
        confirm_text = questionary.text(
            "Type 'RESET' to confirm:",
            validate=lambda x: x == "RESET" or "Please type RESET exactly",
        ).ask()
        if confirm_text != "RESET":
            output.print_error("Cancelled.")
            return
    else:
        if not click.confirm("Do you want to continue?"):
            output.print_error("Cancelled.")
            return
        confirm_text = click.prompt("Type 'RESET' to confirm")
        if confirm_text != "RESET":
            output.print_error("Cancelled.")
            return

    AlembicProjectGuard.require_alembic_binary()
    AlembicProjectGuard.require_alembic_ini()
    output.console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        console=output.console,
    ) as progress:
        task = progress.add_task("[red]Step 1/3: Dropping tables...", total=None)
        try:
            result = subprocess.run(
                ["alembic", "downgrade", "I"],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_ALEMBIC_MUTATION,
            )
            if result.returncode != 0:
                progress.update(task, completed=True)
                output.print_error(f"Failed to drop tables:\n{result.stderr}")
                raise click.Abort()
            progress.update(task, completed=True)
        except Exception as e:
            progress.update(task, completed=True)
            output.print_error(f"Error dropping tables: {e}")
            raise click.Abort()

        task = progress.add_task("[green]Step 2/3: Recreating tables...", total=None)
        try:
            result = subprocess.run(
                ["alembic", "upgrade", "head"],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_ALEMBIC_MUTATION,
            )
            if result.returncode != 0:
                progress.update(task, completed=True)
                output.print_error(f"Failed to recreate tables:\n{result.stderr}")
                raise click.Abort()
            progress.update(task, completed=True)
        except Exception as e:
            progress.update(task, completed=True)
            output.print_error(f"Error recreating tables: {e}")
            raise click.Abort()

        if seed:
            task = progress.add_task("[cyan]Step 3/3: Running seed data...", total=None)
            try:
                seed_script = Path("scripts/seed.py")
                if seed_script.exists():
                    result = subprocess.run(
                        [sys.executable, str(seed_script)],
                        capture_output=True,
                        text=True,
                        timeout=TIMEOUT_SEED_SCRIPT,
                    )
                    if result.returncode != 0:
                        output.print_warning(
                            f"Seed script returned errors:\n{result.stderr}"
                        )
                    else:
                        output.print_success("Seed data applied")
                else:
                    output.print_warning("No seed script found (scripts/seed.py)")
                progress.update(task, completed=True)
            except Exception as e:
                progress.update(task, completed=True)
                output.print_warning(f"Error running seed script: {e}")

    output.print_success("DataI reset complete!")
    output.console.print(
        Panel(
            "[green]✓[/green] All tables dropped and recreated\n"
            f"{'[green]✓[/green] Seed data applied' if seed else '[dim]○ Seed data skipped[/dim]'}\n\n"
            "Your dataI is now fresh and ready to use.",
            title="✅ Reset Complete",
            border_style="green",
        )
    )


@db_group.command(name="history")
@click.option(
    "--verbose/--no-verbose", "-v", default=False, help="Show detailed information"
)
def db_history(verbose: bool) -> None:
    """📜 Show migration history."""
    output.print_banner()
    output.console.print("\n[bold cyan]Migration History[/bold cyan]\n")
    AlembicProjectGuard.require_alembic_binary()
    AlembicProjectGuard.require_alembic_ini()

    try:
        output.console.print("[bold]Current Revision:[/bold]")
        result = subprocess.run(
            ["alembic", "current"], capture_output=True, text=True, timeout=TIMEOUT_ALEMBIC_QUERY
        )
        if result.returncode == 0:
            output.console.print(f"  {result.stdout}")
        else:
            output.console.print("  [dim]No current revision[/dim]")
        output.console.print()
        output.console.print("[bold]Migration History:[/bold]")
        cmd = ["alembic", "history"]
        if verbose:
            cmd.append("--verbose")
        cmd.append("--indicate-current")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_ALEMBIC_QUERY)
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if "(current)" in line:
                    output.console.print(f"[green]▶ {line}[/green]")
                elif "→" in line:
                    output.console.print(f"[dim]  {line}[/dim]")
                else:
                    output.console.print(f"  {line}")
        else:
            output.print_error(f"Failed to get history:\n{result.stderr}")
    except Exception as e:
        output.print_error(f"Error getting history: {e}")
        raise click.Abort()


@db_group.command(name="status")
def db_status() -> None:
    """📊 Show dataI migration status."""
    output.print_banner()
    output.console.print("\n[bold cyan]DataI Status[/bold cyan]\n")
    AlembicProjectGuard.require_alembic_binary()
    AlembicProjectGuard.require_alembic_ini()

    try:
        result = subprocess.run(
            ["alembic", "current"], capture_output=True, text=True, timeout=TIMEOUT_ALEMBIC_QUERY
        )
        if result.returncode == 0:
            current = result.stdout.strip()
            if current:
                output.console.print(f"[bold]Current:[/bold] [green]{current}[/green]")
            else:
                output.console.print(
                    "[bold]Current:[/bold] [yellow]None (dataI not initialized)[/yellow]"
                )
        result = subprocess.run(
            ["alembic", "heads"], capture_output=True, text=True, timeout=TIMEOUT_ALEMBIC_QUERY
        )
        if result.returncode == 0:
            heads = result.stdout.strip()
            if heads:
                output.console.print(f"[bold]Latest:[/bold]  [cyan]{heads.split()[0]}[/cyan]")
            else:
                output.console.print("[bold]Latest:[/bold]  [dim]No migrations found[/dim]")

        result = subprocess.run(
            ["alembic", "history", "--indicate-current"],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_ALEMBIC_QUERY,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            pending = [ln for ln in lines if "(current)" not in ln and "→" in ln]
            output.console.print()
            if pending:
                output.console.print(
                    f"[bold]Status:[/bold]  [yellow]{len(pending)} pending migration(s)[/yellow]"
                )
                output.console.print(
                    "\n[dim]Run 'fast db upgrade' to apply pending migrations[/dim]"
                )
            else:
                output.console.print(
                    "[bold]Status:[/bold]  [green]✓ DataI is up to date[/green]"
                )
    except Exception as e:
        output.print_error(f"Error checking status: {e}")
        raise click.Abort()
