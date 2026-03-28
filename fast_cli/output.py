"""Rich-backed user feedback for the terminal.

The CLI avoids scattering raw ``print`` calls: instead, :class:`CliOutput`
centralizes styling (success, error, warnings, multi-line banner) and exposes
the shared :class:`rich.console.Console` instance for advanced layouts used by
other modules (tables, panels, progress bars).

Attributes
----------
output : CliOutput
    Module singleton used across ``fast_cli`` so all commands share one console
    and consistent visual language.
"""

from __future__ import annotations

from rich.console import Console
from rich.text import Text


class CliOutput:
    """Facade for banners, status lines, and the shared Rich ``Console``.

    Methods are intentionally thin wrappers: they encode the project's UX
    conventions (glyphs, colors) in one place. Callers that need full control
    (e.g. :class:`rich.progress.Progress`) should use :attr:`console` directly.

    Notes
    -----
    * :meth:`print_banner` is ASCII art; it assumes a reasonably wide terminal.
    * Error paths should use :meth:`print_error`; avoid raising without user-facing
      text when the failure is expected (missing optional deps, etc.).
    """

    __slots__ = ("console",)

    def __init__(self) -> None:
        self.console = Console()

    def print_banner(self) -> None:
        """Render the FastMVC ASCII banner in bold cyan."""
        banner = r"""
╔════════════════════════════════════════════════════════════════╗
║  ███████╗ █████╗ ███████╗████████╗ ███╗   ███╗██╗   ██╗ ██████╗║
║  ██╔════╝██╔══██╗██╔════╝╚══██╔══╝ ████╗ ████║██║   ██║██╔════╝║
║  █████╗  ███████║███████╗   ██║    ██╔████╔██║██║   ██║██║     ║
║  ██╔══╝  ██╔══██║╚════██║   ██║    ██║╚██╔╝██║╚██╗ ██╔╝██║     ║
║  ██║     ██║  ██║███████║   ██║    ██║ ╚═╝ ██║ ╚████╔╝ ╚██████╗║
║  ╚═╝     ╚═╝  ╚═╝╚══════╝   ╚═╝    ╚═╝     ╚═╝  ╚═══╝   ╚═════╝║
║                                                                ║
║          Production-Grade MVC Framework for FastAPI            ║
╚════════════════════════════════════════════════════════════════╝
    """
        self.console.print(Text(banner.strip(), style="bold cyan"))

    def print_success(self, message: str) -> None:
        """Print a green checkmark line for successful operations."""
        self.console.print(f"[bold green]✓[/bold green] {message}")

    def print_error(self, message: str) -> None:
        """Print a red cross line for failures or validation errors."""
        self.console.print(f"[bold red]✗[/bold red] {message}")

    def print_warning(self, message: str) -> None:
        """Print a yellow warning line for non-fatal issues."""
        self.console.print(f"[bold yellow]⚠[/bold yellow] {message}")

    def print_info(self, message: str) -> None:
        """Print a blue info line for hints and secondary status."""
        self.console.print(f"[bold blue]ℹ[/bold blue] {message}")

    def print_step(self, number: int, message: str) -> None:
        """Print a numbered step heading for multi-step wizards."""
        self.console.print(f"\n[bold cyan]Step {number}:[/bold cyan] {message}")


output = CliOutput()
