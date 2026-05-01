"""Environment file validation and synchronization commands.

Provides ``fastx env check`` to validate ``.env`` against ``.env.example``
and ``fastx env sync`` to copy missing variables from the example file.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List

import click
from rich.table import Table

from fastx_cli.commands.project_root import resolve_fastmvc_project_root
from fastx_cli.constants import ENV_EXAMPLE_FILENAME, ENV_FILENAME
from fastx_cli.output import output
from fastx_cli.project_setup import ProjectBootstrap


def _parse_env_file(path: Path) -> Dict[str, str]:
    """Parse a .env file and return a dict of variable names to values.

    Blank lines and comments (lines starting with ``#``) are skipped.
    Values are stripped of surrounding quotes (single or double).
    """
    variables: Dict[str, str] = {}
    if not path.exists():
        return variables

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        if key:
            variables[key] = value
    return variables


def _extract_var_names(path: Path) -> List[str]:
    """Return an ordered list of variable names from an env file."""
    names: List[str] = []
    if not path.exists():
        return names
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key = line.partition("=")[0].strip()
        if key and key not in names:
            names.append(key)
    return names


def register_env_check_command(cli: click.Group) -> None:
    """Register the ``env`` command group on the root CLI group."""

    @cli.group(name="env", invoke_without_command=True)
    @click.pass_context
    def env_group(ctx: click.Context) -> None:
        """Manage environment files (.env / .env.example).

        \b
        Subcommands:
            check    Validate .env against .env.example
            sync     Copy missing vars from .env.example into .env
            generate Generate .env from .env.example template (legacy)

        \b
        Running ``fastx env`` without a subcommand shows this help.
        """
        if ctx.invoked_subcommand is None:
            click.echo(ctx.get_help())

    @env_group.command()
    @click.option(
        "--strict",
        is_flag=True,
        default=False,
        help="Treat extra vars and empty vars as errors (exit 1).",
    )
    @click.option(
        "--env-file",
        "env_file",
        default=".env",
        help="Path to .env file (default: .env).",
    )
    @click.option(
        "--example-file",
        "example_file",
        default=".env.example",
        help="Path to .env.example file (default: .env.example).",
    )
    def check(strict: bool, env_file: str, example_file: str) -> None:
        """Validate .env against .env.example.

        \b
        Checks performed:
          - Missing vars (in .env.example but not in .env)  -> ERROR
          - Extra vars (in .env but not in .env.example)    -> WARNING
          - Empty vars (in .env but value is empty)         -> WARNING
          - Set vars                                        -> OK

        \b
        With --strict, extra and empty vars are also treated as errors.

        \b
        Examples:
            fastx env check
            fastx env check --strict
            fastx env check --env-file .env.production --example-file .env.example
        """
        project_root = resolve_fastmvc_project_root(Path.cwd())
        env_path = project_root / env_file
        example_path = project_root / example_file

        if not example_path.exists():
            output.print_error(f"{example_file} not found at {example_path}")
            sys.exit(1)

        if not env_path.exists():
            output.print_error(f"{env_file} not found at {env_path}")
            sys.exit(1)

        example_names = _extract_var_names(example_path)
        env_vars = _parse_env_file(env_path)
        env_names = set(env_vars.keys())
        example_set = set(example_names)

        missing = [n for n in example_names if n not in env_names]
        extra = sorted(env_names - example_set)
        empty = [n for n in example_names if n in env_names and env_vars[n] == ""]
        ok = [n for n in example_names if n in env_names and env_vars[n] != ""]

        # Build the table
        table = Table(title="Environment Variable Check", show_lines=False)
        table.add_column("Variable", style="bold")
        table.add_column("Status")
        table.add_column("Value")

        has_errors = False

        for var in missing:
            table.add_row(var, "[bold red]MISSING[/bold red]", "[dim]-[/dim]")
            has_errors = True

        for var in empty:
            status_style = "[bold red]EMPTY[/bold red]" if strict else "[bold yellow]EMPTY[/bold yellow]"
            table.add_row(var, status_style, "[dim](empty)[/dim]")
            if strict:
                has_errors = True

        for var in ok:
            # Mask the value for display
            val = env_vars[var]
            masked = val[:3] + "***" if len(val) > 3 else "***"
            table.add_row(var, "[bold green]OK[/bold green]", f"[dim]{masked}[/dim]")

        for var in extra:
            status_style = "[bold red]EXTRA[/bold red]" if strict else "[bold yellow]EXTRA[/bold yellow]"
            val = env_vars[var]
            masked = val[:3] + "***" if len(val) > 3 else "***"
            table.add_row(var, status_style, f"[dim]{masked}[/dim]")
            if strict:
                has_errors = True

        output.console.print()
        output.console.print(table)
        output.console.print()

        # Summary
        output.console.print(
            f"  [green]{len(ok)} OK[/green]  "
            f"[red]{len(missing)} missing[/red]  "
            f"[yellow]{len(empty)} empty[/yellow]  "
            f"[yellow]{len(extra)} extra[/yellow]"
        )
        output.console.print()

        if has_errors:
            output.print_error("Environment check failed.")
            sys.exit(1)
        else:
            output.print_success("Environment check passed.")

    @env_group.command()
    @click.option(
        "--env-file",
        "env_file",
        default=".env",
        help="Path to .env file (default: .env).",
    )
    @click.option(
        "--example-file",
        "example_file",
        default=".env.example",
        help="Path to .env.example file (default: .env.example).",
    )
    def sync(env_file: str, example_file: str) -> None:
        """Copy missing vars from .env.example to .env.

        Only variables that exist in .env.example but are absent from .env
        are appended.  Existing variables in .env are never overwritten.

        \b
        Examples:
            fastx env sync
            fastx env sync --env-file .env.local
        """
        project_root = resolve_fastmvc_project_root(Path.cwd())
        env_path = project_root / env_file
        example_path = project_root / example_file

        if not example_path.exists():
            output.print_error(f"{example_file} not found at {example_path}")
            sys.exit(1)

        example_vars = _parse_env_file(example_path)
        env_vars = _parse_env_file(env_path) if env_path.exists() else {}

        missing_keys = [k for k in example_vars if k not in env_vars]

        if not missing_keys:
            output.print_success("Nothing to sync -- .env already has all variables.")
            return

        # Build lines to append
        lines_to_add: List[str] = []
        for key in missing_keys:
            value = example_vars[key]
            lines_to_add.append(f"{key}={value}")

        # Ensure file ends with newline before appending
        if env_path.exists():
            existing = env_path.read_text(encoding="utf-8")
            if existing and not existing.endswith("\n"):
                lines_to_add[0] = "\n" + lines_to_add[0]
        else:
            # Create the file if it doesn't exist
            pass

        with env_path.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines_to_add) + "\n")

        output.print_success(f"Synced {len(missing_keys)} variable(s) to {env_file}:")
        for key in missing_keys:
            output.console.print(f"  [green]+[/green] {key}")

    @env_group.command()
    @click.pass_context
    def generate(ctx: click.Context) -> None:
        """Generate .env from .env.example template (legacy).

        Creates a new .env file from the .env.example template using
        ProjectBootstrap. Will not overwrite an existing .env file.
        """
        bootstrap = ProjectBootstrap()
        output.print_banner()
        target_path = resolve_fastmvc_project_root(Path.cwd())
        context = ctx.parent.params if ctx.parent else {}
        if bootstrap.generate_env_file(target_path, context):
            output.print_success("Environment file generated successfully!")
        else:
            output.print_error(
                f"Failed to generate {ENV_FILENAME} "
                f"(ensure {ENV_EXAMPLE_FILENAME} exists and {ENV_FILENAME} does not)."
            )
