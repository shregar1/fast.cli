"""List all registered FastAPI routes as a formatted table."""

from __future__ import annotations

import json as json_mod
import sys
from pathlib import Path

import click

from fastx_cli.commands.project_root import resolve_fastmvc_project_root
from fastx_cli.output import output


def register_routes_command(cli: click.Group) -> None:
    """Register the ``routes`` command on the root CLI group."""

    @cli.command()
    @click.option("--json", "as_json", is_flag=True, help="Output as JSON instead of a table")
    @click.option("--filter", "-f", "path_filter", default=None, help="Filter routes by path pattern")
    @click.option("--method", "-m", "method_filter", default=None, help="Filter by HTTP method (e.g. POST)")
    def routes(as_json: bool, path_filter: str | None, method_filter: str | None) -> None:
        """Print all registered FastAPI routes as a formatted table.

        \b
        Examples:
            fastx routes                    # Show all routes
            fastx routes --json             # Output as JSON
            fastx routes -f /api/v1         # Filter by path
            fastx routes -m POST            # Filter by method
            fastx routes -f /users -m GET   # Combine filters
        """
        project_root = resolve_fastmvc_project_root(Path.cwd())

        # Add project root to sys.path so we can import the app
        project_root_str = str(project_root)
        if project_root_str not in sys.path:
            sys.path.insert(0, project_root_str)

        try:
            from app import app  # noqa: WPS433
        except ImportError as exc:
            output.print_error(
                f"Could not import FastAPI app: {exc}\n"
                "  Make sure you are in a FastMVC project root with an app.py "
                "that exposes an `app` instance."
            )
            raise SystemExit(1) from None

        rows: list[dict[str, str]] = []

        for route in app.routes:
            # Skip non-API routes (Mount, etc.) that lack methods
            methods = getattr(route, "methods", None)
            if methods is None:
                continue

            path: str = getattr(route, "path", "")
            endpoint = getattr(route, "endpoint", None)
            name: str = getattr(route, "name", "") or (
                endpoint.__name__ if endpoint else ""
            )

            # Detect auth: check for dependencies on the route or endpoint
            has_auth = False
            dependencies = getattr(route, "dependencies", None) or []
            if dependencies:
                has_auth = True
            # Also check the dependant for security-related dependencies
            if not has_auth and hasattr(route, "dependant"):
                dep_list = getattr(route.dependant, "dependencies", []) or []
                for dep in dep_list:
                    dep_call = getattr(dep, "call", None)
                    dep_name = getattr(dep_call, "__name__", "") if dep_call else ""
                    if any(
                        kw in dep_name.lower()
                        for kw in ("auth", "current_user", "token", "permission", "security")
                    ):
                        has_auth = True
                        break

            method_str = ",".join(sorted(methods - {"HEAD", "OPTIONS"})) or ",".join(sorted(methods))

            # Apply filters
            if path_filter and path_filter not in path:
                continue
            if method_filter and method_filter.upper() not in methods:
                continue

            rows.append({
                "method": method_str,
                "path": path,
                "name": name,
                "auth": "Yes" if has_auth else "",
            })

        if not rows:
            output.print_warning("No routes found matching the given filters.")
            return

        # Sort by path, then method
        rows.sort(key=lambda r: (r["path"], r["method"]))

        if as_json:
            output.console.print(json_mod.dumps(rows, indent=2))
            return

        # Rich table output
        from rich.table import Table

        table = Table(
            title="Registered Routes",
            show_header=True,
            header_style="bold cyan",
            show_lines=False,
        )
        table.add_column("METHOD", style="bold green", no_wrap=True)
        table.add_column("PATH", style="bold")
        table.add_column("NAME", style="dim")
        table.add_column("AUTH", style="yellow", justify="center")

        for row in rows:
            table.add_row(row["method"], row["path"], row["name"], row["auth"])

        output.console.print()
        output.console.print(table)
        output.console.print()
        output.console.print(f"  [dim]{len(rows)} route(s) total[/dim]")
        output.console.print()
