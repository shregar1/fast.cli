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
from fast_cli.commands.completion_cmd import register_completion_command
from fast_cli.commands.db_cmd import db_group
from fast_cli.commands.decimate_cmd import register_decimate_command
from fast_cli.commands.docs_cmd import docs_group
from fast_cli.commands.doctor_cmd import register_doctor_commands
from fast_cli.commands.generate_cmd import register_generate_commands
from fast_cli.commands.misc_cmd import register_misc_commands
from fast_cli.commands.tasks_cmd import tasks_group


@click.group(
    context_settings={
        "help_option_names": ["-h", "--help"],
        "max_content_width": 92,
    },
)
@click.version_option(version=__version__, prog_name="fast")
def cli() -> None:
    r"""✨ FastMVC CLI — FastAPI project generator and tooling.

    \b
    Projects:
        generate, new       Create a project (interactive or --name/--path)
        quickstart          Create a project with defaults
        add resource        Scaffold DTOs, services, and API layers
        env                 Generate .env from .env.example

    \b
    Database (Alembic):
        db migrate          New revision (-m message)
        db upgrade          Apply migrations
        db downgrade        Roll back
        db reset            Drop and recreate (dangerous)
        db status, history  Inspect state

    \b
    Docs & ops:
        docs generate       MkDocs-style API stubs under docs/api/
        docs deploy         mkdocs gh-deploy
        cache clear         Clear FastCaching backend (optional dep)
        cache invalidate    Invalidate cache tags
        tasks worker        Background worker (fast_platform)
        tasks list, status, dashboard

    \b
    Cleanup & repo:
        decimate            Remove build/cache artifacts (python, java, rust, …)
        setup-commit-log    Commit history JSON + pre-commit post-commit hook

    \b
    Diagnostics:
        doctor, check-env   Print Python, toolchain, and optional deps
        completion          Print shell tab-completion script (bash/zsh/fish)

    \b
    Legacy:
        make                Deprecated; use add or env

    \b
    Examples:
        fast generate
        fast new --name my_api --path ./my_api
        fast add resource -f user -r create
        fast db upgrade
        fast setup-commit-log
    """
    pass


register_generate_commands(cli)
register_misc_commands(cli)
register_commit_history_setup(cli)
register_decimate_command(cli)
register_doctor_commands(cli)
register_completion_command(cli)
cli.add_command(docs_group)
cli.add_command(db_group, name="db")
cli.add_command(add_group, name="add")
cli.add_command(cache_group)
cli.add_command(tasks_group)


def main() -> None:
    """Invoke the root Click group; used as setuptools console script entry point.

    This function is referenced from ``pyproject.toml``::

        [project.scripts]
        fast = "fast_cli.app:main"
        fast-cli = "fast_cli.app:main"
        fastmvc = "fast_cli.app:main"

    It intentionally contains no logic beyond delegating to :func:`cli` so
    that test runners can patch or wrap :func:`cli` if needed.
    """
    cli()


if __name__ == "__main__":
    main()
