"""Rich UI for configuration summary and post-generation steps.

:class:`GenerationSummaryPresenter` owns **read-only** terminal output after a
successful scaffold: a configuration table before confirmation (interactive
mode) and a long “next steps” experience including shell commands, VS Code and
Makefile hints, optional pre-commit and GitHub Actions panels, and a short
example ``FastAPI`` snippet.

It deliberately depends on :class:`fastx_cli.output.output` and
:class:`fastx_cli.venv.VirtualEnvironmentService` only for activation command
text—no filesystem mutations occur here.
"""

from __future__ import annotations

from pathlib import Path

from rich import box
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table

from fastx_cli.output import output
from fastx_cli.venv import VirtualEnvironmentService


class GenerationSummaryPresenter:
    """Tables and panels shown after a project is generated.

    Parameters to methods are **context** dictionaries produced by
    :class:`fastx_cli.project_generation.ProjectGenerationOrchestrator`, extended
    with keys such as ``venv_created``, ``deps_installed``,
    ``precommit_initialized``, and ``github_actions_copied`` after optional
    post-steps.
    """

    def show_summary_table(self, context: dict) -> None:
        """Render the “Project Configuration” table before final confirmation."""
        table = Table(
            title="📋 Project configuration",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold #38bdf8",
            border_style="dim #334155",
        )
        table.add_column("Setting", style="dim", width=20)
        table.add_column("Value", style="bold")
        table.add_row("Project Name", context["project_name"])
        table.add_row("Package Name", context["project_slug"])
        table.add_row("Author", f"{context['author_name']} <{context['author_email']}>")
        desc = context["description"]
        table.add_row(
            "Description",
            desc[:50] + "..." if len(desc) > 50 else desc,
        )
        table.add_row("Version", context["version"])
        table.add_row("Python Version", context["python_version"])
        table.add_row("Virtual Env", context.get("venv_name", ".venv"))
        table.add_row(
            "Auto-install Deps",
            "Yes" if context.get("install_deps", False) else "No",
        )
        table.add_row(
            "Pre-commit Hooks",
            "Yes" if context.get("init_precommit", False) else "No",
        )
        output.console.print()
        output.console.print(table)

    def show_next_steps(self, target_path: Path, context: dict) -> None:
        """Print success banner, command checklist, and optional panels.

        The checklist adapts when the venv was created in-process or dependencies
        were installed automatically, so the user is not told to repeat steps
        unnecessarily.
        """
        venv_name = context.get("venv_name", ".venv")
        venv_created = context.get("venv_created", False)
        deps_installed = context.get("deps_installed", False)
        venv_svc = VirtualEnvironmentService()

        output.console.print(
            Rule(
                "[bold #34d399]🎉 Project generated successfully[/bold #34d399]",
                style="dim #475569",
                characters="─",
            )
        )
        output.console.print()
        output.console.print(
            f"[bold #f8fafc]📂[/bold #f8fafc] [bold]Location[/bold]  [bold #38bdf8]{target_path}[/bold #38bdf8]"
        )
        output.console.print()

        if venv_created:
            output.console.print(
                Panel(
                    f"[green]✓ Virtual environment created:[/green] [cyan]{venv_name}/[/cyan]\n"
                    f"[green]✓ .gitignore updated for {venv_name}/[/green]",
                    title="🐍 Virtual Environment",
                    border_style="green",
                )
            )

        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        table.add_column(style="bold yellow", width=30)
        table.add_column(style="white")
        steps: list[tuple[str, str]] = []
        step_num = 1
        steps.append((f"{step_num}. Navigate to project", f"cd {target_path.name}"))
        step_num += 1
        if not venv_created:
            steps.append(
                (f"{step_num}. Create virtual env", f"python -m venv {venv_name}")
            )
            step_num += 1
        activate_unix, activate_windows = venv_svc.activation_commands(venv_name)
        steps.append(
            (
                f"{step_num}. Activate venv",
                f"{activate_unix}  # Windows: {activate_windows}",
            )
        )
        step_num += 1
        if not deps_installed:
            steps.append(
                (f"{step_num}. Install dependencies", "pip install -r requirements.txt")
            )
            step_num += 1
        else:
            steps.append(
                (f"{step_num}. Dependencies", "[green]✓ Already installed[/green]")
            )
            step_num += 1
        steps.append((f"{step_num}. Setup environment", "cp .env.example .env"))
        step_num += 1
        steps.append(
            (
                f"{step_num}. Run the server",
                "python app.py  # or: uvicorn app:app --reload",
            )
        )
        for label, command in steps:
            if "Already installed" in command:
                table.add_row(label, command)
            else:
                table.add_row(label, Syntax(command, "bash", theme="monokai"))
        output.console.print(table)

        if venv_created:
            output.console.print(
                "\n[bold cyan]💡 Remember to activate your virtual environment:[/bold cyan]"
            )
            output.console.print(
                Syntax(f"source {venv_name}/bin/activate", "bash", theme="monokai")
            )

        output.console.print(
            Panel(
                "[bold]VS Code is configured for this project![/bold]\n\n"
                "Recommended extensions will be suggested when you open the folder.\n"
                "Press [bold]F5[/bold] to debug or [bold]Cmd/Ctrl+Shift+P[/bold] → 'Tasks: Run Task'\n\n"
                "[dim]Key shortcuts:[/dim]\n"
                "  • F5 - Debug FastAPI server\n"
                "  • Cmd/Ctrl+Shift+B - Run build task\n"
                "  • Cmd/Ctrl+Shift+T - Run tests",
                title="📝 VS Code Ready",
                border_style="blue",
            )
        )

        if context.get("precommit_initialized", False):
            output.console.print(
                Panel(
                    "[bold]Pre-commit hooks installed![/bold]\n\n"
                    "[green]✓[/green] Ruff linter and formatter\n"
                    "[green]✓[/green] MyPy type checking\n"
                    "[green]✓[/green] Security checks (bandit, secrets)\n"
                    "[green]✓[/green] File validation\n\n"
                    "Hooks run automatically on 'git commit'\n"
                    "To skip hooks: [dim]git commit --no-verify[/dim]",
                    title="🔒 Pre-commit Hooks",
                    border_style="green",
                )
            )

        output.console.print(
            Panel(
                "[bold]Makefile commands available![/bold]\n\n"
                "[dim]Common commands:[/dim]\n"
                "  [cyan]make install[/cyan]   - Install dependencies\n"
                "  [cyan]make dev[/cyan]       - Start development server\n"
                "  [cyan]make test[/cyan]      - Run tests\n"
                "  [cyan]make lint[/cyan]      - Run linter\n"
                "  [cyan]make format[/cyan]    - Format code\n"
                "  [cyan]make migrate[/cyan]   - Create migration\n\n"
                "Run [cyan]make help[/cyan] to see all available commands",
                title="🔧 Makefile",
                border_style="green",
            )
        )

        if context.get("github_actions_copied", False):
            output.console.print(
                Panel(
                    "[bold]GitHub Actions CI/CD workflows added![/bold]\n\n"
                    "[dim]Workflows:[/dim]\n"
                    "  [green]✓[/green] CI/CD - Test, lint, build on push\n"
                    "  [green]✓[/green] PR Checks - Validate pull requests\n"
                    "  [green]✓[/green] Release - Build and push on tag\n\n"
                    "[dim]Setup required:[/dim]\n"
                    "  1. Push to GitHub\n"
                    "  2. Go to repository Settings → Actions → General\n"
                    "  3. Enable 'Read and write permissions' for workflows\n\n"
                    "[dim]Container registry:[/dim]\n"
                    "  Images will be pushed to ghcr.io/<username>/<repo>",
                    title="🚀 CI/CD Ready",
                    border_style="blue",
                )
            )

        output.console.print("\n[bold]🚀 Example API is ready![/bold]")
        code = """from fastapi import FastAPI
from fast_mvc.example.controllers.item_controller import router as item_router

app = FastAPI()
app.include_router(item_router)

# Try these endpoints:
# POST   /items          - Create item
# GET    /items          - List items
# GET    /items/{id}     - Get item
# PATCH  /items/{id}     - Update item
# DELETE /items/{id}     - Delete item"""
        output.console.print(Syntax(code, "python", theme="monokai", line_numbers=True))
        output.console.print(
            "\n[italic dim #94a3b8]Happy coding with FastMVC · ship something great[/italic dim #94a3b8]\n"
        )
