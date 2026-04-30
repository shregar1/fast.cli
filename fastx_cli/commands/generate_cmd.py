"""Project generation commands: ``generate``, ``new``, ``quickstart``.

Registers three subcommands on the root :class:`click.Group` by closure over a
single :class:`fastx_cli.project_generation.ProjectGenerationOrchestrator`
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

import click

from fastx_cli.constants import DEFAULT_PROJECT_NAME, DEFAULT_PROJECT_VERSION, DEFAULT_VENV_NAME
from fastx_cli.project_generation import ProjectGenerationOrchestrator
from fastx_cli.user_config import load_user_defaults


def register_generate_commands(cli: click.Group) -> None:
    """Attach ``generate``, ``new``, and ``quickstart`` to ``cli``.

    Parameters
    ----------
    cli
        The root group from :mod:`fastx_cli.app`.
    """
    orchestrator = ProjectGenerationOrchestrator()

    @cli.command()
    @click.option("--name", "-n", help="Project name")
    @click.option("--path", "-p", help="Target directory path")
    @click.option("--author", "-a", help="Author name")
    @click.option("--email", "-e", help="Author email")
    @click.option("--description", "-d", help="Project description")
    @click.option("--version", "-v", default=DEFAULT_PROJECT_VERSION, help="Initial version")
    @click.option("--venv/--no-venv", default=True, help="Create virtual environment")
    @click.option("--venv-name", default=DEFAULT_VENV_NAME, help="Virtual environment name")
    @click.option(
        "--install-deps/--no-install-deps", default=True, help="Install dependencies"
    )
    def generate(
        name: str | None,
        path: str | None,
        author: str | None,
        email: str | None,
        description: str | None,
        version: str,
        venv: bool,
        venv_name: str,
        install_deps: bool,
    ) -> None:
        """🚀 Generate a new FastMVC project interactively or with options."""
        if not all([name, path]):
            orchestrator.run_interactive()
            return
        assert name is not None and path is not None
        cfg = load_user_defaults()
        if author is None and isinstance(cfg.get("author"), str):
            author = cfg["author"]
        if email is None:
            e = cfg.get("author_email") or cfg.get("email")
            if isinstance(e, str):
                email = e
        if description is None and isinstance(cfg.get("description"), str):
            description = cfg["description"]
        vname = cfg.get("venv_name")
        if isinstance(vname, str) and vname.strip():
            venv_name = vname.strip()
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
    @click.pass_context
    @click.option("--name", "-n", help="Project name")
    @click.option("--path", "-p", help="Target directory path")
    @click.option("--author", "-a", help="Author name")
    @click.option("--email", "-e", help="Author email")
    @click.option("--description", "-d", help="Project description")
    @click.option("--version", "-v", default=DEFAULT_PROJECT_VERSION, help="Initial version")
    @click.option("--venv/--no-venv", default=True, help="Create virtual environment")
    @click.option("--venv-name", default=DEFAULT_VENV_NAME, help="Virtual environment name")
    @click.option(
        "--install-deps/--no-install-deps", default=True, help="Install dependencies"
    )
    def new(
        ctx: click.Context,
        name: str | None,
        path: str | None,
        author: str | None,
        email: str | None,
        description: str | None,
        version: str,
        venv: bool,
        venv_name: str,
        install_deps: bool,
    ) -> None:
        """🆕 Alias for ``generate`` — create a new FastMVC project."""
        ctx.invoke(
            generate,
            name=name,
            path=path,
            author=author,
            email=email,
            description=description,
            version=version,
            venv=venv,
            venv_name=venv_name,
            install_deps=install_deps,
        )

    @cli.command()
    @click.option("--name", "-n", default=DEFAULT_PROJECT_NAME, help="Project name")
    @click.option("--venv-name", default=DEFAULT_VENV_NAME, help="Virtual environment name")
    @click.option(
        "--install-deps/--no-install-deps", default=True, help="Install dependencies"
    )
    def quickstart(name: str, venv_name: str, install_deps: bool) -> None:
        """⚡ Quick start with default settings."""
        orchestrator.run_quickstart(name, venv_name, install_deps)
