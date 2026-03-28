"""Project generation commands: ``generate``, ``new``, ``quickstart``.

Registers three subcommands on the root :class:`click.Group` by closure over a
single :class:`fast_cli.project_generation.ProjectGenerationOrchestrator`
instance.

* ``generate`` — If ``--name`` and ``--path`` are **both** provided, runs
  :meth:`ProjectGenerationOrchestrator.run_cli_options`; otherwise starts the
  interactive flow (:meth:`~ProjectGenerationOrchestrator.run_interactive`).
* ``new`` — Forwards to the same ``generate`` callback with identical options
  (alias for muscle memory / docs).
* ``quickstart`` — :meth:`~ProjectGenerationOrchestrator.run_quickstart` with
  defaults for author and description.
"""

from __future__ import annotations

from typing import Optional

import click

from fast_cli.project_generation import ProjectGenerationOrchestrator


def register_generate_commands(cli: click.Group) -> None:
    """Attach ``generate``, ``new``, and ``quickstart`` to ``cli``.

    Parameters
    ----------
    cli
        The root group from :mod:`fast_cli.app`.
    """
    orchestrator = ProjectGenerationOrchestrator()

    @cli.command()
    @click.option("--name", "-n", help="Project name")
    @click.option("--path", "-p", help="Target directory path")
    @click.option("--author", "-a", help="Author name")
    @click.option("--email", "-e", help="Author email")
    @click.option("--description", "-d", help="Project description")
    @click.option("--version", "-v", default="0.1.0", help="Initial version")
    @click.option("--venv/--no-venv", default=True, help="Create virtual environment")
    @click.option("--venv-name", default=".venv", help="Virtual environment name")
    @click.option(
        "--install-deps/--no-install-deps", default=True, help="Install dependencies"
    )
    def generate(
        name: Optional[str],
        path: Optional[str],
        author: Optional[str],
        email: Optional[str],
        description: Optional[str],
        version: str,
        venv: bool,
        venv_name: str,
        install_deps: bool,
    ) -> None:
        """🚀 Generate a new FastMVC project interactively or with options."""
        if not all([name, path]):
            orchestrator.run_interactive()
            return
        orchestrator.run_cli_options(
            name=name,
            path=path or ".",
            author=author,
            email=email,
            description=description,
            version=version,
            venv=venv,
            venv_name=venv_name,
            install_deps=install_deps,
        )

    @cli.command(name="new")
    @click.option("--name", "-n", help="Project name")
    @click.option("--path", "-p", help="Target directory path")
    @click.option("--author", "-a", help="Author name")
    @click.option("--email", "-e", help="Author email")
    @click.option("--description", "-d", help="Project description")
    @click.option("--version", "-v", default="0.1.0", help="Initial version")
    @click.option("--venv/--no-venv", default=True, help="Create virtual environment")
    @click.option("--venv-name", default=".venv", help="Virtual environment name")
    @click.option(
        "--install-deps/--no-install-deps", default=True, help="Install dependencies"
    )
    def new(
        name: Optional[str],
        path: Optional[str],
        author: Optional[str],
        email: Optional[str],
        description: Optional[str],
        version: str,
        venv: bool,
        venv_name: str,
        install_deps: bool,
    ) -> None:
        """🆕 Alias for ``generate`` — create a new FastMVC project."""
        generate.callback(
            name,
            path,
            author,
            email,
            description,
            version,
            venv,
            venv_name,
            install_deps,
        )

    @cli.command()
    @click.option("--name", "-n", default="my_fastapi_project", help="Project name")
    @click.option("--venv-name", default=".venv", help="Virtual environment name")
    @click.option(
        "--install-deps/--no-install-deps", default=True, help="Install dependencies"
    )
    def quickstart(name: str, venv_name: str, install_deps: bool) -> None:
        """⚡ Quick start with default settings."""
        orchestrator.run_quickstart(name, venv_name, install_deps)
