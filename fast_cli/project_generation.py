"""Interactive and non-interactive new-project generation flows.

The :class:`ProjectGenerationOrchestrator` is the **application service** for
project scaffolding. It wires together:

* :class:`fast_cli.paths.FrameworkSourceLocator` — find ``fast_mvc`` sources
* :class:`fast_cli.file_copy.ProjectCopier` — copy with progress + templates
* :class:`fast_cli.project_setup.ProjectBootstrap` — extra dirs, ``pyproject.toml``, ``.env``
* :class:`fast_cli.github_workflows.GitHubWorkflowsCopier` — optional CI YAML
* :class:`fast_cli.gitignore.GitignoreUpdater` / :class:`fast_cli.venv.VirtualEnvironmentService`
  / :class:`fast_cli.precommit.PreCommitInstaller` — post-copy setup
* :class:`fast_cli.generation_ui.GenerationSummaryPresenter` — UX

**Entry modes**

* ``run_interactive`` — Questionary wizard (falls back to :meth:`run_basic` if
  Questionary is not installed).
* ``run_basic`` — Click prompts only; simpler copy loop without the bar copier.
* ``run_cli_options`` — Non-interactive flags from ``fast-cli generate``.
* ``run_quickstart`` — Opinionated defaults under the current working directory.

Raises
------
click.Abort
    Propagated when a user cancels or a fatal error occurs after messaging.

See Also
--------
fast_cli.commands.generate_cmd.register_generate_commands : CLI registration.
"""

from __future__ import annotations

import os
import secrets
import shutil
from pathlib import Path

from fast_cli.constants import (
    BCRYPT_RANDOM_LENGTH,
    BCRYPT_SALT_PREFIX,
    DEFAULT_APP_PORT,
    DEFAULT_AUTHOR_NAME,
    DEFAULT_PYTHON_VERSION,
    DEFAULT_PROJECT_VERSION,
    DEFAULT_VENV_NAME,
    JWT_SECRET_KEY_LENGTH,
    SUPPORTED_PYTHON_VERSIONS,
)

import click
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.rule import Rule

from fast_cli.file_copy import ProjectCopier, template_copytree_ignore
from fast_cli.generation_ui import GenerationSummaryPresenter
from fast_cli.github_workflows import GitHubWorkflowsCopier
from fast_cli.gitignore import GitignoreUpdater
from fast_cli.output import output
from fast_cli.paths import FrameworkSourceLocator
from fast_cli.precommit import PreCommitInstaller
from fast_cli.project_setup import ProjectBootstrap
from fast_cli.template_engine import TemplateRenderer
from fast_cli.user_config import load_user_defaults
from fast_cli.validators import (
    HAS_QUESTIONARY,
    EmailValidator,
    PathValidator,
    ProjectNameValidator,
)
from fast_cli.venv import VirtualEnvironmentService

if HAS_QUESTIONARY:
    import questionary


class ProjectGenerationOrchestrator:
    """Coordinates copying, templating, venv, and post-generation UI.

    The orchestrator constructs its dependencies once; each ``run_*`` method is
    safe to call on the same instance for multiple projects in one process
    (e.g. tests), though the CLI does not reuse it that way today.
    """

    def __init__(self) -> None:
        """Build shared services (locator, renderer, copier, bootstrap, etc.)."""
        self._locator = FrameworkSourceLocator()
        self._renderer = TemplateRenderer()
        self._copier = ProjectCopier(self._renderer)
        self._bootstrap = ProjectBootstrap(self._renderer)
        self._workflows = GitHubWorkflowsCopier(
            repo_root=self._locator.repo_root, renderer=self._renderer
        )
        self._gitignore = GitignoreUpdater()
        self._precommit = PreCommitInstaller()
        self._venv = VirtualEnvironmentService()
        self._ui = GenerationSummaryPresenter()

    def run_interactive(self) -> None:
        """Run the full Questionary multi-step wizard, then :meth:`_execute_pipeline`.

        If ``questionary`` is unavailable, prints a tip and delegates to
        :meth:`run_basic`.
        """
        output.print_banner()
        cfg = load_user_defaults()
        if not HAS_QUESTIONARY:
            output.console.print(
                Panel(
                    "[yellow]For the best experience, install with:[/yellow]\n"
                    "[bold]pip install fastmvc-cli[interactive][/bold]",
                    title="💡 Tip",
                    border_style="yellow",
                )
            )
            output.console.print()
            self.run_basic()
            return

        output.print_step(1, "Project Identification")
        project_name = questionary.text(
            "📛 Project name:",
            validate=ProjectNameValidator,
            instruction="(valid Python identifier, e.g., 'my_backend')",
        ).ask()
        if not project_name:
            output.print_error("Cancelled.")
            return

        output.print_step(2, "Project Location")
        default_path = str(Path.cwd() / project_name)
        target_path_str = questionary.text(
            "📁 Target directory:", default=default_path, validate=PathValidator
        ).ask()
        if not target_path_str:
            output.print_error("Cancelled.")
            return

        target_path = Path(target_path_str).expanduser().resolve()
        if target_path.exists() and any(target_path.iterdir()):
            overwrite = questionary.confirm(
                f"⚠️ Directory '{target_path}' is not empty. Continue anyway?",
                default=False,
            ).ask()
            if not overwrite:
                output.print_error("Cancelled.")
                return

        output.print_step(3, "Author Information")
        _author_default: str = (
            (cfg.get("author") if isinstance(cfg.get("author"), str) else None)
            or os.getenv("USER", "Developer")
            or DEFAULT_AUTHOR_NAME
        )
        author_name = questionary.text(
            "👤 Author name:", default=_author_default
        ).ask()
        _email_default = (
            cfg.get("author_email")
            if isinstance(cfg.get("author_email"), str)
            else (cfg.get("email") if isinstance(cfg.get("email"), str) else None)
        )
        if isinstance(_email_default, str) and _email_default.strip():
            author_email = questionary.text(
                "📧 Author email:",
                default=_email_default.strip(),
                validate=EmailValidator,
            ).ask()
        else:
            author_email = questionary.text(
                "📧 Author email:", validate=EmailValidator
            ).ask()

        output.print_step(4, "Project Details")
        _desc_raw = cfg.get("description")
        _desc_default: str = (
            _desc_raw
            if isinstance(_desc_raw, str)
            else f"{project_name} - FastAPI backend built with FastMVC"
        )
        description = questionary.text(
            "📝 Project description:",
            default=_desc_default,
        ).ask()
        version = questionary.text("🔢 Initial version:", default=DEFAULT_PROJECT_VERSION).ask()
        python_version = questionary.select(
            "🐍 Python version:",
            choices=list(SUPPORTED_PYTHON_VERSIONS),
            default=DEFAULT_PYTHON_VERSION,
        ).ask()

        output.print_step(5, "Virtual Environment")
        create_venv = questionary.confirm(
            "🐍 Create virtual environment automatically?", default=True
        ).ask()
        venv_name = DEFAULT_VENV_NAME
        install_deps = False
        if create_venv:
            _venv_raw = cfg.get("venv_name")
            _venv_default: str = _venv_raw if isinstance(_venv_raw, str) else DEFAULT_VENV_NAME
            venv_name = (
                questionary.text(
                    "📁 Virtual environment name:",
                    default=_venv_default,
                    instruction="(.venv or venv recommended)",
                ).ask()
                or DEFAULT_VENV_NAME
            )
            install_deps = questionary.confirm(
                "📦 Install dependencies automatically?",
                default=True,
                instruction="(requires internet connection)",
            ).ask()

        output.print_step(6, "Code Quality")
        init_precommit = False
        if create_venv and HAS_QUESTIONARY:
            init_precommit = questionary.confirm(
                "🔒 Install pre-commit hooks?",
                default=True,
                instruction="(auto-format code on git commit)",
            ).ask()

        context = {
            "project_name": project_name,
            "project_slug": project_name.lower().replace(" ", "_").replace("-", "_"),
            "author_name": author_name or DEFAULT_AUTHOR_NAME,
            "author_email": author_email or "",
            "description": description or "",
            "version": version or DEFAULT_PROJECT_VERSION,
            "python_version": python_version or DEFAULT_PYTHON_VERSION,
            "venv_name": venv_name,
            "create_venv": create_venv,
            "install_deps": install_deps,
            "init_precommit": init_precommit,
            "jwt_secret_key": secrets.token_urlsafe(JWT_SECRET_KEY_LENGTH),
            "bcrypt_salt": f"{BCRYPT_SALT_PREFIX}{secrets.token_urlsafe(BCRYPT_RANDOM_LENGTH)[:22]}",
            "app_port": DEFAULT_APP_PORT,
        }

        output.console.print(
            Rule(
                "[bold #38bdf8]Configuration summary[/bold #38bdf8]",
                style="dim #475569",
                characters="─",
            )
        )
        self._ui.show_summary_table(context)
        if not questionary.confirm(
            "Generate project with these settings?", default=True
        ).ask():
            output.print_error("Cancelled.")
            return

        output.console.print(
            Rule(
                "[bold #34d399]Generating project[/bold #34d399]",
                style="dim #475569",
                characters="─",
            )
        )
        try:
            self._execute_pipeline(target_path, context)
        except Exception as e:
            output.print_error(f"Error: {e}")
            raise click.Abort() from e

    def run_basic(self) -> None:
        """Fallback generation using only :mod:`click` prompts (no Questionary).

        Uses a simpler copy loop than :meth:`_execute_pipeline` (spinner only,
        no per-file progress bar) and does not offer pre-commit installation.
        """
        output.console.print("[bold]Basic Mode - Enter project details:[/bold]\n")
        cfg = load_user_defaults()
        project_name = click.prompt("📛 Project name (valid Python identifier)")
        default_path = str(Path.cwd() / project_name)
        target_path_str = click.prompt("📁 Target directory", default=default_path)
        target_path = Path(target_path_str).expanduser().resolve()
        _ad = cfg.get("author") if isinstance(cfg.get("author"), str) else None
        author_name = click.prompt(
            "👤 Author name", default=_ad or os.getenv("USER", DEFAULT_AUTHOR_NAME)
        )
        _em = cfg.get("author_email") or cfg.get("email")
        if isinstance(_em, str) and _em.strip():
            author_email = click.prompt("📧 Author email", default=_em.strip())
        else:
            author_email = click.prompt("📧 Author email")
        _dd = cfg.get("description") if isinstance(cfg.get("description"), str) else None
        description = click.prompt(
            "📝 Project description", default=_dd or f"{project_name} backend"
        )
        version = click.prompt("🔢 Initial version", default=DEFAULT_PROJECT_VERSION)
        create_venv = click.confirm("🐍 Create virtual environment?", default=True)
        venv_name = DEFAULT_VENV_NAME
        install_deps = False
        if create_venv:
            _vn = cfg.get("venv_name") if isinstance(cfg.get("venv_name"), str) else None
            venv_name = click.prompt(
                "📁 Virtual environment name", default=_vn or DEFAULT_VENV_NAME
            )
            install_deps = click.confirm("📦 Install dependencies?", default=True)

        context = {
            "project_name": project_name,
            "project_slug": project_name.lower().replace(" ", "_").replace("-", "_"),
            "author_name": author_name,
            "author_email": author_email,
            "description": description,
            "version": version,
            "python_version": DEFAULT_PYTHON_VERSION,
            "venv_name": venv_name,
            "create_venv": create_venv,
            "install_deps": install_deps,
            "jwt_secret_key": secrets.token_urlsafe(JWT_SECRET_KEY_LENGTH),
            "bcrypt_salt": f"{BCRYPT_SALT_PREFIX}{secrets.token_urlsafe(BCRYPT_RANDOM_LENGTH)}",
            "app_port": DEFAULT_APP_PORT,
        }

        try:
            source = self._locator.fast_mvc_root()
            items = self._locator.list_existing_template_items()
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                console=output.console,
            ) as progress:
                _ = progress.add_task("Generating project...", total=None)
                target_path.mkdir(parents=True, exist_ok=True)
                for item in items:
                    source_path = source / item
                    target_item_path = target_path / item
                    try:
                        if source_path.is_dir():
                            shutil.copytree(
                                source_path,
                                target_item_path,
                                ignore=template_copytree_ignore(source_path),
                            )
                        else:
                            shutil.copy2(source_path, target_item_path)
                            self._renderer.process_file(target_item_path, context)
                    except OSError:
                        pass
                self._bootstrap.create_project_structure(target_path, context)
                context["github_actions_copied"] = self._workflows.copy_into_project(
                    target_path, context
                )
                self._bootstrap.update_pyproject_toml(target_path, context)
                self._bootstrap.generate_env_file(target_path, context)

            venv_created = False
            deps_installed = False
            if create_venv:
                output.console.print()
                venv_created = self._venv.create(target_path, venv_name)
                if venv_created:
                    self._gitignore.update_for_venv(target_path, venv_name)
                    if install_deps:
                        deps_installed = self._venv.install_requirements(
                            target_path, venv_name
                        )
            context["venv_created"] = venv_created
            context["deps_installed"] = deps_installed
            self._ui.show_next_steps(target_path, context)
        except Exception as e:
            output.print_error(f"Error: {e}")
            raise click.Abort() from e

    def run_cli_options(
        self,
        name: str,
        path: str,
        author: str | None,
        email: str | None,
        description: str | None,
        version: str,
        venv: bool,
        venv_name: str,
        install_deps: bool,
    ) -> None:
        """Non-interactive generation from ``fast-cli generate --name ... --path ...``."""
        output.print_banner()
        target_path = Path(path or ".").expanduser().resolve()
        _name = name or "project"
        context = {
            "project_name": _name,
            "project_slug": _name.lower().replace(" ", "_").replace("-", "_"),
            "author_name": author or os.getenv("USER", DEFAULT_AUTHOR_NAME),
            "author_email": email or "",
            "description": description or f"{name} - FastAPI backend",
            "version": version,
            "python_version": DEFAULT_PYTHON_VERSION,
            "venv_name": venv_name,
            "create_venv": venv,
            "install_deps": install_deps,
            "jwt_secret_key": secrets.token_urlsafe(JWT_SECRET_KEY_LENGTH),
            "bcrypt_salt": f"{BCRYPT_SALT_PREFIX}{secrets.token_urlsafe(BCRYPT_RANDOM_LENGTH)}",
            "app_port": DEFAULT_APP_PORT,
        }
        try:
            output.console.print(f"\n[bold cyan]Generating project:[/bold cyan] {name}")
            self._execute_pipeline(target_path, context)
        except Exception as e:
            output.print_error(f"Error: {e}")
            raise click.Abort() from e

    def run_quickstart(
        self, name: str, venv_name: str, install_deps: bool
    ) -> None:
        """Create ``./<name>`` under the current working directory with defaults."""
        output.print_banner()
        cfg = load_user_defaults()
        vn = cfg.get("venv_name")
        if isinstance(vn, str) and vn.strip():
            venv_name = vn.strip()
        _auth = cfg.get("author") if isinstance(cfg.get("author"), str) else None
        _em = cfg.get("author_email") or cfg.get("email")
        _email_s = _em.strip() if isinstance(_em, str) else ""
        _desc = (
            cfg.get("description")
            if isinstance(cfg.get("description"), str)
            else "FastAPI project built with FastMVC"
        )
        target_path = Path.cwd() / name
        context = {
            "project_name": name,
            "project_slug": name,
            "author_name": _auth or os.getenv("USER", DEFAULT_AUTHOR_NAME),
            "author_email": _email_s,
            "description": _desc,
            "version": DEFAULT_PROJECT_VERSION,
            "python_version": DEFAULT_PYTHON_VERSION,
            "venv_name": venv_name,
            "create_venv": True,
            "install_deps": install_deps,
            "jwt_secret_key": secrets.token_urlsafe(JWT_SECRET_KEY_LENGTH),
            "bcrypt_salt": f"{BCRYPT_SALT_PREFIX}{secrets.token_urlsafe(BCRYPT_RANDOM_LENGTH)}",
            "app_port": DEFAULT_APP_PORT,
        }
        try:
            output.console.print(f"\n[bold cyan]Quick starting:[/bold cyan] {name}")
            self._execute_pipeline(target_path, context)
        except Exception as e:
            output.print_error(f"Error: {e}")
            raise click.Abort() from e

    def _execute_pipeline(self, target_path: Path, context: dict) -> None:
        """Shared path: copy, bootstrap, optional venv/pre-commit, then next steps.

        ``context`` must include ``create_venv``, ``install_deps``, and
        ``init_precommit`` (interactive) or sensible defaults (CLI/quickstart).
        """
        source = self._locator.fast_mvc_root()
        items = self._locator.list_existing_template_items()
        output.console.print(f"\n[bold cyan]Source:[/bold cyan] {source}")
        output.console.print(f"[bold cyan]Target:[/bold cyan] {target_path}")
        output.console.print(f"[bold cyan]Files:[/bold cyan] {len(items)} items\n")
        copied = self._copier.copy_with_progress(source, target_path, items, context)
        output.print_success(f"Copied {copied} items")
        self._bootstrap.create_project_structure(target_path, context)
        context["github_actions_copied"] = self._workflows.copy_into_project(
            target_path, context
        )
        self._bootstrap.update_pyproject_toml(target_path, context)
        self._bootstrap.generate_env_file(target_path, context)

        venv_created = False
        deps_installed = False
        if context.get("create_venv", False):
            output.console.print()
            vn = str(context.get("venv_name", DEFAULT_VENV_NAME))
            venv_created = self._venv.create(target_path, vn)
            if venv_created:
                self._gitignore.update_for_venv(target_path, vn)
                if context.get("install_deps", False):
                    deps_installed = self._venv.install_requirements(target_path, vn)
                precommit_initialized = False
                if context.get("init_precommit", False):
                    output.console.print()
                    precommit_initialized = self._precommit.install(target_path, vn)
                context["precommit_initialized"] = precommit_initialized
        context["venv_created"] = venv_created
        context["deps_installed"] = deps_installed
        self._ui.show_next_steps(target_path, context)
