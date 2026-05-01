"""Legacy ``make`` and ``env`` commands."""

from __future__ import annotations

from pathlib import Path

import click

from fastx_cli.commands.add_cmd import add_resource
from fastx_cli.commands.project_root import resolve_fastmvc_project_root
from fastx_cli.constants import ENV_EXAMPLE_FILENAME, ENV_FILENAME
from fastx_cli.output import output
from fastx_cli.project_setup import ProjectBootstrap


def register_misc_commands(cli: click.Group) -> None:
    """Register ``make`` and ``env`` on the root ``cli`` group.

    ``make`` is deprecated: it forwards to :func:`add_resource` or
    :func:`generate_env` for backwards compatibility with older tutorials.
    ``generate_env`` uses :meth:`ProjectBootstrap.generate_env_file` with the
    parent Click context’s ``params`` as template context (often empty).
    """

    bootstrap = ProjectBootstrap()

    @cli.command()
    @click.argument("type", type=click.Choice(["resource", "env"], case_sensitive=False))
    @click.option("--name", "-n", help="Name of the resource")
    def make(type: str, name: str) -> None:
        """[DEPRECATED] Use 'fast add' or 'fast env' instead."""
        ctx = click.get_current_context()
        if type.lower() == "resource":
            ctx.invoke(add_resource, folder=name, resource="fetch", version="v1")
        elif type.lower() == "env":
            output.print_warning("Use 'fast env sync' or 'fast env generate' instead.")
            output.print_banner()
            target_path = resolve_fastmvc_project_root(Path.cwd())
            context = ctx.parent.params if ctx.parent else {}
            if bootstrap.generate_env_file(target_path, context):
                output.print_success("Environment file generated successfully!")
            else:
                output.print_error(
                    f"Failed to generate {ENV_FILENAME} (ensure {ENV_EXAMPLE_FILENAME} exists and {ENV_FILENAME} does not)."
                )
