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

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import click
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from fastx_cli.commands.project_root import resolve_fastmvc_project_root
from fastx_cli.constants import (
    TIMEOUT_ALEMBIC_MUTATION,
    TIMEOUT_ALEMBIC_QUERY,
    TIMEOUT_SEED_SCRIPT,
)
from fastx_cli.output import output
from fastx_cli.validators import HAS_QUESTIONARY

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


# ---------------------------------------------------------------------------
# Seed template
# ---------------------------------------------------------------------------

_SEED_TEMPLATE = '''\
"""Database seed script.

Run via:  fastx db seed
          fastx db seed --count 50 --model User --reset

Environment variables (set automatically by the CLI):
    SEED_COUNT  — number of records to create per model (default 10)
    SEED_MODEL  — restrict seeding to a single model name
    SEED_RESET  — when set to "1", truncate target tables before seeding
    DATABASE_URL — SQLAlchemy-compatible connection string
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from faker import Faker
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

fake = Faker()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./app.db")
SEED_COUNT = int(os.environ.get("SEED_COUNT", "10"))
SEED_MODEL = os.environ.get("SEED_MODEL", "")
SEED_RESET = os.environ.get("SEED_RESET", "0") == "1"

engine = create_engine(DATABASE_URL)


def seed_users(session: Session, count: int) -> None:
    """Create *count* fake user rows."""
    if SEED_RESET:
        session.execute(text("DELETE FROM users"))
        session.commit()
        print("  Truncated users table")

    for _ in range(count):
        session.execute(
            text(
                "INSERT INTO users (name, email, created_at) "
                "VALUES (:name, :email, :created_at)"
            ),
            {
                "name": fake.name(),
                "email": fake.unique.email(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    session.commit()
    print(f"  Seeded {count} users")


# Map model names to seeder functions.
# Add more entries as your project grows.
SEEDERS: dict[str, callable] = {
    "User": seed_users,
}


if __name__ == "__main__":
    with Session(engine) as session:
        if SEED_MODEL:
            seeder = SEEDERS.get(SEED_MODEL)
            if seeder is None:
                print(f"Unknown model: {SEED_MODEL}")
                print(f"Available models: {', '.join(SEEDERS)}")
                raise SystemExit(1)
            seeder(session, SEED_COUNT)
        else:
            for name, seeder in SEEDERS.items():
                print(f"Seeding {name}...")
                seeder(session, SEED_COUNT)

    print("Done!")
'''


def _generate_seed_file(seeds_dir: Path) -> Path:
    """Write the sample seed script and return its path."""
    seeds_dir.mkdir(parents=True, exist_ok=True)
    seed_file = seeds_dir / "seed.py"
    seed_file.write_text(_SEED_TEMPLATE)
    return seed_file


@db_group.command(name="seed")
@click.option(
    "--count",
    "-c",
    default=10,
    show_default=True,
    help="Number of records to create per model.",
)
@click.option(
    "--model",
    "-m",
    default=None,
    help="Specific model name to seed (seeds all models if omitted).",
)
@click.option(
    "--reset",
    is_flag=True,
    default=False,
    help="Truncate target tables before seeding.",
)
@click.option(
    "--generate",
    is_flag=True,
    default=False,
    help="Force-generate the sample seed file even if seeds/ exists.",
)
def db_seed(
    count: int,
    model: Optional[str],
    reset: bool,
    generate: bool,
) -> None:
    """🌱 Seed the database with fake data.

    Looks for a ``seeds/seed.py`` script in the project root and runs it.
    If no seed script exists, a sample template is generated automatically.

    Examples:\n
        fastx db seed\n
        fastx db seed --count 50 --model User\n
        fastx db seed --reset\n
        fastx db seed --generate
    """
    output.print_banner()
    project_root = resolve_fastmvc_project_root()
    seeds_dir = project_root / "seeds"
    seed_file = seeds_dir / "seed.py"

    # --generate: create/overwrite the template regardless
    if generate:
        path = _generate_seed_file(seeds_dir)
        output.print_success(f"Generated seed template at {path}")
        output.console.print(
            Panel(
                "[dim]Next steps:[/dim]\n"
                "  1. Edit [cyan]seeds/seed.py[/cyan] to match your models\n"
                "  2. Run [cyan]fastx db seed[/cyan] to populate data",
                title="🌱 Seed Template",
                border_style="green",
            )
        )
        return

    # If seeds/ directory doesn't exist, generate the template
    if not seeds_dir.exists():
        output.console.print(
            "\n[bold yellow]No seeds/ directory found.[/bold yellow] "
            "Generating sample seed template...\n"
        )
        path = _generate_seed_file(seeds_dir)
        output.print_success(f"Generated seed template at {path}")
        output.console.print(
            Panel(
                "[dim]Next steps:[/dim]\n"
                "  1. Edit [cyan]seeds/seed.py[/cyan] to match your models\n"
                "  2. Run [cyan]fastx db seed[/cyan] again to populate data",
                title="🌱 Seed Template",
                border_style="green",
            )
        )
        return

    # seeds/ exists but seed.py is missing
    if not seed_file.exists():
        output.print_error(
            f"seeds/ directory exists but seeds/seed.py was not found.\n"
            f"Run [cyan]fastx db seed --generate[/cyan] to create a template."
        )
        raise click.Abort()

    # Run the seed script
    output.console.print(
        f"\n[bold cyan]Seeding database[/bold cyan]  "
        f"count={count}"
        f"{f'  model={model}' if model else ''}"
        f"{'  reset=True' if reset else ''}\n"
    )

    env = os.environ.copy()
    env["SEED_COUNT"] = str(count)
    if model:
        env["SEED_MODEL"] = model
    if reset:
        env["SEED_RESET"] = "1"

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        console=output.console,
    ) as progress:
        task = progress.add_task("[cyan]Running seed script...", total=None)
        try:
            result = subprocess.run(
                [sys.executable, str(seed_file)],
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SEED_SCRIPT,
                env=env,
                cwd=str(project_root),
            )
            progress.update(task, completed=True)

            if result.stdout:
                output.console.print(f"\n[dim]{result.stdout.strip()}[/dim]")

            if result.returncode != 0:
                output.print_error(f"Seed script failed:\n{result.stderr}")
                raise click.Abort()

            output.print_success("Database seeded successfully!")
        except subprocess.TimeoutExpired:
            progress.update(task, completed=True)
            output.print_error("Seed script timed out")
            raise click.Abort()
        except click.Abort:
            raise
        except Exception as e:
            progress.update(task, completed=True)
            output.print_error(f"Error running seed script: {e}")
            raise click.Abort()
