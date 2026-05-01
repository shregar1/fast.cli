"""Structured log viewer for FastX JSON logs."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import click

from fastx_cli.commands.project_root import resolve_fastmvc_project_root
from fastx_cli.output import output

# Log levels in ascending severity order.
_LEVEL_ORDER = {
    "DEBUG": 0,
    "INFO": 1,
    "WARNING": 2,
    "ERROR": 3,
    "CRITICAL": 4,
}

_LEVEL_STYLES: dict[str, str] = {
    "DEBUG": "dim",
    "INFO": "cyan",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "bold red",
}


def _style_level(level: str) -> str:
    """Return a Rich-styled level string."""
    style = _LEVEL_STYLES.get(level.upper(), "white")
    return f"[{style}]{level.upper():<8}[/{style}]"


def _format_line(record: dict) -> str:
    """Format a parsed JSON log record into a human-readable line."""
    ts = record.get("timestamp", "---")
    level = record.get("level", "INFO").upper()
    module = record.get("module", "?")
    message = record.get("message", "")
    styled_level = _style_level(level)
    return f"[dim][{ts}][/dim] {styled_level} [dim]|[/dim] [blue]{module}[/blue] [dim]|[/dim] {message}"


def _parse_line(raw: str) -> dict | None:
    """Try to parse a single line as JSON. Returns None on failure."""
    raw = raw.strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _passes_filters(
    record: dict,
    min_level: int,
    search: str | None,
) -> bool:
    """Return True if the record passes the active filters."""
    record_level = _LEVEL_ORDER.get(record.get("level", "INFO").upper(), 1)
    if record_level < min_level:
        return False
    if search and search.lower() not in json.dumps(record).lower():
        return False
    return True


def _resolve_log_file(project_root: Path, file_path: str | None) -> Path:
    """Determine which log file to read."""
    if file_path:
        p = Path(file_path)
        if not p.is_absolute():
            p = project_root / p
        return p

    logs_dir = project_root / "logs"
    candidates = ["app.log", "error.log"]
    for name in candidates:
        candidate = logs_dir / name
        if candidate.exists():
            return candidate

    # Fall back to the first .log file found in logs/
    if logs_dir.is_dir():
        log_files = sorted(logs_dir.glob("*.log"), key=lambda f: f.stat().st_mtime, reverse=True)
        if log_files:
            return log_files[0]

    # Nothing found — return default so the error message is clear
    return logs_dir / "app.log"


def _print_records(
    lines: list[str],
    min_level: int,
    search: str | None,
    raw_json: bool,
) -> int:
    """Parse, filter, and print log lines. Returns number printed."""
    printed = 0
    for raw in lines:
        record = _parse_line(raw)
        if record is None:
            continue
        if not _passes_filters(record, min_level, search):
            continue
        if raw_json:
            output.console.print_json(json.dumps(record))
        else:
            output.console.print(_format_line(record))
        printed += 1
    return printed


def register_logs_command(cli: click.Group) -> None:
    """Register the ``logs`` command on the root CLI group."""

    @cli.command()
    @click.option(
        "--level", "-l",
        type=click.Choice(["debug", "info", "warning", "error", "critical"], case_sensitive=False),
        default="debug",
        help="Minimum log level to display.",
    )
    @click.option("--tail", "-t", "follow", is_flag=True, help="Follow mode — watch for new lines (like tail -f).")
    @click.option("--lines", "-n", "num_lines", default=50, type=int, help="Number of recent lines to show.")
    @click.option("--file", "-f", "file_path", default=None, type=str, help="Path to a specific log file.")
    @click.option("--search", "-s", default=None, type=str, help="Filter lines containing this search term.")
    @click.option("--json", "raw_json", is_flag=True, help="Output raw JSON instead of formatted lines.")
    def logs(
        level: str,
        follow: bool,
        num_lines: int,
        file_path: str | None,
        search: str | None,
        raw_json: bool,
    ) -> None:
        """View structured FastX JSON logs.

        \b
        Reads JSON-formatted log files from the project's logs/ directory and
        pretty-prints them with colour coding by level.

        \b
        Examples:
            fastx logs                        # Last 50 lines from default log
            fastx logs -n 100 -l warning      # Last 100 lines, WARNING and above
            fastx logs -t                     # Follow mode
            fastx logs -f logs/error.log      # Specific file
            fastx logs -s "user_id"           # Search for a term
            fastx logs --json                 # Raw JSON output
        """
        project_root = resolve_fastmvc_project_root(Path.cwd())
        log_file = _resolve_log_file(project_root, file_path)

        if not log_file.exists():
            output.console.print(f"[red]Log file not found:[/red] {log_file}")
            output.console.print("[dim]Hint: make sure your app writes JSON logs to the logs/ directory.[/dim]")
            sys.exit(1)

        min_level = _LEVEL_ORDER.get(level.upper(), 0)

        if not raw_json:
            output.console.print()
            output.console.print(f"[bold cyan]Log viewer[/bold cyan]  [dim]{log_file}[/dim]")
            if level.upper() != "DEBUG":
                output.console.print(f"  [dim]min level:[/dim] {level.upper()}")
            if search:
                output.console.print(f"  [dim]search:[/dim]    {search}")
            output.console.print()

        # Read the last N lines
        try:
            all_lines = log_file.read_text().splitlines()
        except OSError as exc:
            output.console.print(f"[red]Cannot read log file:[/red] {exc}")
            sys.exit(1)

        tail_lines = all_lines[-num_lines:] if len(all_lines) > num_lines else all_lines
        _print_records(tail_lines, min_level, search, raw_json)

        # Follow mode — poll for new content
        if follow:
            if not raw_json:
                output.console.print()
                output.console.print("[dim]Following log file — press Ctrl+C to stop[/dim]")

            try:
                last_size = log_file.stat().st_size
                while True:
                    time.sleep(0.5)
                    try:
                        current_size = log_file.stat().st_size
                    except OSError:
                        continue

                    if current_size > last_size:
                        with open(log_file) as fh:
                            fh.seek(last_size)
                            new_data = fh.read()
                        last_size = current_size

                        new_lines = new_data.splitlines()
                        _print_records(new_lines, min_level, search, raw_json)
                    elif current_size < last_size:
                        # File was truncated / rotated — start from beginning
                        last_size = 0
            except KeyboardInterrupt:
                output.console.print("\n[dim]Stopped following.[/dim]")
