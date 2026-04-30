"""Development server with auto-reload and optional tunnel."""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import click

from fastx_cli.commands.project_root import resolve_fastmvc_project_root
from fastx_cli.output import output


def register_dev_command(cli: click.Group) -> None:
    """Register the ``dev`` command on the root CLI group."""

    @cli.command()
    @click.option("--host", default="0.0.0.0", help="Bind host")
    @click.option("--port", "-p", default=8000, type=int, help="Bind port")
    @click.option("--open", "open_browser", is_flag=True, help="Open browser to /docs")
    @click.option("--tunnel", is_flag=True, help="Start ngrok tunnel for external access")
    @click.option("--tunnel-provider", type=click.Choice(["ngrok", "cloudflare"]), default="ngrok", help="Tunnel provider")
    @click.option("--workers", "-w", default=1, type=int, help="Number of workers (reload disabled when >1)")
    def dev(host: str, port: int, open_browser: bool, tunnel: bool, tunnel_provider: str, workers: int) -> None:
        """Start development server with auto-reload.

        \b
        Examples:
            fastx dev                     # Start on 0.0.0.0:8000 with reload
            fastx dev -p 3000 --open      # Port 3000, open browser
            fastx dev --tunnel            # Start with ngrok tunnel
            fastx dev --tunnel --tunnel-provider cloudflare
        """
        project_root = resolve_fastmvc_project_root(Path.cwd())

        # Print dev banner
        output.console.print()
        output.console.print("[bold cyan]⚡ FastX Dev Server[/bold cyan]")
        output.console.print()

        local_url = f"http://{'localhost' if host == '0.0.0.0' else host}:{port}"
        output.console.print(f"  [dim]Local:[/dim]    [bold]{local_url}[/bold]")
        output.console.print(f"  [dim]Docs:[/dim]     [bold]{local_url}/docs[/bold]")
        output.console.print(f"  [dim]Health:[/dim]   [bold]{local_url}/health[/bold]")

        # Start tunnel if requested
        tunnel_process = None
        if tunnel:
            tunnel_process = _start_tunnel(tunnel_provider, port)

        # Open browser after a short delay
        if open_browser:
            def _open():
                time.sleep(2)
                webbrowser.open(f"{local_url}/docs")
            threading.Thread(target=_open, daemon=True).start()

        output.console.print()
        output.console.print("  [dim]Press Ctrl+C to stop[/dim]")
        output.console.print()

        # Build uvicorn command
        reload = workers <= 1
        cmd = [
            sys.executable, "-m", "uvicorn",
            "app:app",
            "--host", host,
            "--port", str(port),
        ]
        if reload:
            cmd.extend([
                "--reload",
                "--reload-dir", str(project_root),
                "--reload-include", "*.py",
                "--reload-include", "*.env",
            ])
        else:
            cmd.extend(["--workers", str(workers)])

        try:
            proc = subprocess.run(cmd, cwd=str(project_root))
            sys.exit(proc.returncode)
        except KeyboardInterrupt:
            output.console.print("\n[bold cyan]⚡ FastX Dev Server stopped[/bold cyan]")
        finally:
            if tunnel_process is not None:
                tunnel_process.terminate()


def _start_tunnel(provider: str, port: int) -> subprocess.Popen | None:
    """Start a tunnel process in the background."""
    try:
        if provider == "ngrok":
            proc = subprocess.Popen(
                ["ngrok", "http", str(port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            # Give ngrok a moment to start
            time.sleep(2)
            # Try to get the public URL from ngrok API
            try:
                import json
                import urllib.request
                resp = urllib.request.urlopen("http://localhost:4040/api/tunnels")
                data = json.loads(resp.read())
                for t in data.get("tunnels", []):
                    public_url = t.get("public_url", "")
                    if public_url.startswith("https"):
                        output.console.print(f"  [dim]Tunnel:[/dim]  [bold green]{public_url}[/bold green]")
                        break
            except Exception:
                output.console.print("  [dim]Tunnel:[/dim]  [yellow]ngrok started (check http://localhost:4040)[/yellow]")
            return proc

        elif provider == "cloudflare":
            proc = subprocess.Popen(
                ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            output.console.print("  [dim]Tunnel:[/dim]  [yellow]cloudflared starting (URL in logs)[/yellow]")
            return proc

    except FileNotFoundError:
        output.console.print(f"  [dim]Tunnel:[/dim]  [red]{provider} not installed — skipping[/red]")
        tip = "pip install pyngrok" if provider == "ngrok" else "brew install cloudflare/cloudflare/cloudflared"
        output.console.print(f"           [dim]Install: {tip}[/dim]")
    return None
