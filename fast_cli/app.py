"""Click application root and ``main`` entry point.

This module is the **single assembly point** for the CLI: it defines the root
:class:`click.Group`, attaches the :func:`click.version_option`, and registers
all subcommands by calling small ``register_*`` helpers and
:meth:`click.Group.add_command`.

Why keep this separate from :mod:`fast_cli.cli`?
    ``pyproject.toml`` points console scripts at ``fast_cli.app:main``. A tiny
    :mod:`fast_cli.cli` module remains for backwards compatibility so that
    ``from fast_cli.cli import cli`` continues to work for anyone who imported
    the old monolithic package layout.

Extension
---------
To add a new top-level command, implement it in ``fast_cli/commands/`` and
register it here (or expose a ``register_your_commands(cli)`` function and call
it below).
"""

from __future__ import annotations

import click

from fast_cli import __version__
from fast_cli.commands.add_cmd import add_group
from fast_cli.commands.cache_cmd import cache_group
from fast_cli.commands.commit_history_setup import register_commit_history_setup
from fast_cli.commands.db_cmd import db_group
from fast_cli.commands.decimate_cmd import register_decimate_command
from fast_cli.commands.docs_cmd import docs_group
from fast_cli.commands.generate_cmd import register_generate_commands
from fast_cli.commands.misc_cmd import register_misc_commands
from fast_cli.commands.tasks_cmd import tasks_group


@click.group()
@click.version_option(version=__version__, prog_name="fast-cli")
def cli() -> None:
    r"""✨ FastMVC CLI - Beautiful FastAPI Project Generator.

    Generate production-ready FastAPI projects with MVC architecture.

    \b
    Project Commands:
        generate    Interactive project generation
        new         Alias for generate
        quickstart  Create project with defaults
        add middleware Scaffold application middleware
        add auth       Scaffold complete JWT Auth stack
        add test       Scaffold async Pytest for resource
        add task       Scaffold background worker task
        add env        Generate .env from template

     \b
    DataI Commands:
        db migrate   Create new migration
        db upgrade   Apply migrations
        db downgrade Rollback migrations
        db reset     Reset dataI (drop & recreate)
        db status    Check migration status
        db history   Show migration history

    \b
    Infrastructure Commands:
        dockerize    Generate Docker & Docker Compose config

    \b
    Repository tooling:
        setup-commit-log  Install commit_history.json recorder in any git repo

    \b
    Documentation Commands:
        docs generate  Generate API documentation site

    \b
    Examples:
        fastmvc generate
        fastmvc new --name my_api
        fastmvc add resource user
        fastmvc add auth
        fastmvc dockerize
    """
    pass


register_generate_commands(cli)
register_misc_commands(cli)
register_commit_history_setup(cli)
register_decimate_command(cli)
cli.add_command(docs_group)
cli.add_command(db_group, name="db")
cli.add_command(add_group, name="add")
cli.add_command(cache_group)
cli.add_command(tasks_group)


def main() -> None:
    """Invoke the root Click group; used as setuptools console script entry point.

    This function is referenced from ``pyproject.toml``::

        [project.scripts]
        fast-cli = "fast_cli.app:main"
        fastmvc = "fast_cli.app:main"

    It intentionally contains no logic beyond delegating to :func:`cli` so
    that test runners can patch or wrap :func:`cli` if needed.
    """
    cli()


if __name__ == "__main__":
    main()
