"""Rich-backed user feedback for the terminal.

The CLI avoids scattering raw ``print`` calls: instead, :class:`CliOutput`
centralizes styling (success, error, warnings, multi-line banner) and exposes
the shared :class:`rich.console.Console` instance for advanced layouts used by
other modules (tables, panels, progress bars).

Attributes
----------
output : CliOutput
    Module singleton used across ``fastx_cli`` so all commands share one console
    and consistent visual language.
"""

from __future__ import annotations

import os
import sys

from rich import box
from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

from fastx_cli.constants import (
    BANNER_SUBTITLE,
    BANNER_WIDTH_THRESHOLD,
    BOOLEAN_TRUE_VALUES,
    ENV_MINIMAL_BANNER,
)


def _lerp_hex(t: float) -> str:
    """Interpolate between cyan (#22d3ee) and violet (#a78bfa) for line gradients."""
    t = max(0.0, min(1.0, t))
    r1, g1, b1 = 0x22, 0xD3, 0xEE
    r2, g2, b2 = 0xA7, 0x8B, 0xFA
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


# Semantic accents (truecolor-friendly; Rich falls back gracefully on basic terminals)
_C_SUCCESS = "#34d399"
_C_ERROR = "#fb7185"
_C_WARN = "#fbbf24"
_C_INFO = "#38bdf8"
_C_MUTED = "#64748b"
_C_BORDER = "#38bdf8"
_C_TITLE = "#f8fafc"


def _env_flag(name: str) -> bool:
    v = os.environ.get(name, "").strip().lower()
    return v in BOOLEAN_TRUE_VALUES


def _ascii_stdout() -> bool:
    enc = getattr(sys.stdout, "encoding", None) or ""
    return enc.lower() in ("ascii", "ansi_x3.4-1968")


def _use_compact_banner(console: Console) -> bool:
    """Prefer a short banner for narrow terminals, CI logs, or explicit opt-in."""
    if _env_flag(ENV_MINIMAL_BANNER):
        return True
    w = console.width
    if w and w < BANNER_WIDTH_THRESHOLD:
        return True
    return False


class CliOutput:
    """Facade for banners, status lines, and the shared Rich ``Console``.

    Methods are intentionally thin wrappers: they encode the project's UX
    conventions (glyphs, colors) in one place. Callers that need full control
    (e.g. :class:`rich.progress.Progress`) should use :attr:`console` directly.

    Notes
    -----
    * :meth:`print_banner` uses a gradient wordmark on wide terminals; set
      ``FAST_CLI_MINIMAL_BANNER=1`` or use a narrow terminal (``< 56`` columns)
      for a short text banner. ``NO_COLOR`` / ``TERM=dumb`` are respected via
      Rich (see Rich console docs).
    * Error paths should use :meth:`print_error`; avoid raising without user-facing
      text when the failure is expected (missing optional deps, etc.).
    """

    __slots__ = ("console",)

    def __init__(self) -> None:
        self.console = Console()

    def _print_banner_compact(self) -> None:
        """Plain banner for small terminals, dumb TERM, or ASCII-only streams."""
        sub = (
            BANNER_SUBTITLE
            if _ascii_stdout()
            else BANNER_SUBTITLE.replace(" / ", " · ")
        )
        self.console.print()
        self.console.print(Align.center(Text("FastMVC CLI", style="bold")))
        self.console.print(Align.center(Text(sub, style="dim")))
        self.console.print()

    def print_banner(self) -> None:
        """Render the FastMVC wordmark with a soft cyan→violet gradient."""
        if _use_compact_banner(self.console):
            self._print_banner_compact()
            return

        raw_lines = [
            r"  ███████╗ █████╗ ███████╗████████╗ ███╗   ███╗██╗   ██╗ ██████╗",
            r"  ██╔════╝██╔══██╗██╔════╝╚══██╔══╝ ████╗ ████║██║   ██║██╔════╝",
            r"  █████╗  ███████║███████╗   ██║    ██╔████╔██║██║   ██║██║     ",
            r"  ██╔══╝  ██╔══██║╚════██║   ██║    ██║╚██╔╝██║╚██╗ ██╔╝██║     ",
            r"  ██║     ██║  ██║███████║   ██║    ██║ ╚═╝ ██║ ╚████╔╝ ╚██████╗",
            r"  ╚═╝     ╚═╝  ╚═╝╚══════╝   ╚═╝    ╚═╝     ╚═╝  ╚═══╝   ╚═════╝",
        ]
        n = max(len(raw_lines) - 1, 1)
        body = Text()
        for i, line in enumerate(raw_lines):
            if i:
                body.append("\n")
            style = f"bold {_lerp_hex(i / n)}"
            body.append(line, style=style)

        panel = Panel(
            Align.center(body),
            title=f"[bold {_C_TITLE}]⚡ FastMVC[/bold {_C_TITLE}]",
            subtitle="[italic dim]FastAPI · MVC · Production-ready[/italic dim]",
            border_style=_C_BORDER,
            box=box.ROUNDED,
            padding=(1, 2),
        )
        self.console.print()
        self.console.print(Align.center(panel))
        self.console.print()

    def print_success(self, message: str) -> None:
        """Print a success line with a soft green accent."""
        self.console.print(
            f"[bold {_C_SUCCESS}]▸[/bold {_C_SUCCESS}]  [default]{message}[/default]"
        )

    def print_error(self, message: str) -> None:
        """Print a failure line with a rose accent."""
        self.console.print(
            f"[bold {_C_ERROR}]▸[/bold {_C_ERROR}]  [default]{message}[/default]"
        )

    def print_warning(self, message: str) -> None:
        """Print a warning line with amber accent."""
        self.console.print(
            f"[bold {_C_WARN}]▸[/bold {_C_WARN}]  [default]{message}[/default]"
        )

    def print_info(self, message: str) -> None:
        """Print an info line with sky accent."""
        self.console.print(
            f"[bold {_C_INFO}]▸[/bold {_C_INFO}]  [default]{message}[/default]"
        )

    def print_step(self, number: int, message: str) -> None:
        """Print a numbered step heading for multi-step wizards."""
        self.console.print()
        self.console.print(
            Rule(
                title=f"[bold {_C_INFO}]Step {number}[/bold {_C_INFO}]  [default]{message}[/default]",
                style=f"dim {_C_MUTED}",
                characters="─",
            )
        )


output = CliOutput()
