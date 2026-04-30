"""``fast completion`` — print shell tab-completion script for bash/zsh/fish."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import click

from fastx_cli.constants import CLI_ENTRY_POINTS, TIMEOUT_COMPLETION_HELPER
from fastx_cli.output import output


def _env_var_for_executable(exe_name: str) -> str:
    """Match Click's ``_<PROG>_COMPLETE`` (hyphens in the name become underscores)."""
    return f"_{exe_name.upper().replace('-', '_')}_COMPLETE"


def register_completion_command(cli: click.Group) -> None:
    """Register ``completion`` on the root group."""

    @cli.command("completion")
    @click.argument(
        "shell",
        type=click.Choice(["bash", "zsh", "fish"], case_sensitive=False),
    )
    def completion(shell: str) -> None:
        """Print Click 8+ shell completion script for bash, zsh, or fish.

        Typical setup (bash):

            eval "$(fast completion bash)"

        Or add the ``eval`` line printed at the top to ``~/.bashrc``.
        """
        shell_l = shell.lower()
        mapping = {"bash": "bash_source", "zsh": "zsh_source", "fish": "fish_source"}
        source = mapping[shell_l]

        exe: str | None = None
        for entry_point in CLI_ENTRY_POINTS:
            exe = shutil.which(entry_point)
            if exe:
                break
        if not exe:
            output.print_error(
                "Could not find 'fast', 'fast-cli', or 'fastmvc' on PATH."
            )
            output.print_info("Install with: pip install fastmvc-cli")
            raise SystemExit(1)

        argv = [exe]
        exe_name = Path(exe).name
        env_var = _env_var_for_executable(exe_name)
        env = {**os.environ, env_var: source}
        try:
            result = subprocess.run(
                argv,
                env=env,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_COMPLETION_HELPER,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            output.print_error(f"Could not run completion helper: {e}")
            raise SystemExit(1) from e

        if result.returncode != 0:
            err = (result.stderr or "").strip()
            output.print_error(f"Completion helper failed ({result.returncode}): {err}")
            raise SystemExit(1)

        script = (result.stdout or "").strip()
        if not script:
            output.print_warning("No completion script was produced.")
            output.print_info(
                "Install the ``fast`` script on PATH (``pip install fastmvc-cli``) "
                "and use Click 8+."
            )
            raise SystemExit(1)

        one_liner = f'eval "$({env_var}={source} {exe_name})"'
        output.console.print(
            f"\n[bold]One-line setup for [cyan]{shell_l}[/cyan]:[/bold]\n"
            f"  [green]{one_liner}[/green]\n"
        )
        output.console.print("[bold]Completion script:[/bold]\n")
        click.echo(script)
