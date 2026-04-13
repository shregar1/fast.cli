"""Virtual environment creation and dependency installation.

Uses the standard library ``venv`` module via ``python -m venv`` and invokes
``pip install -r requirements.txt`` inside the new environment. Paths to
``pip`` differ on Windows vs POSIX.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn

from fast_cli.constants import REQUIREMENTS_FILENAME, TIMEOUT_PIP_INSTALL, TIMEOUT_VENV_CREATE
from fast_cli.output import output


class VirtualEnvironmentService:
    """Create a venv and install ``requirements.txt`` with Rich progress output."""

    def create(self, target_path: Path, venv_name: str, python_exe: str = sys.executable) -> bool:
        """Run ``python -m venv`` under ``target_path / venv_name``.

        Parameters
        ----------
        target_path
            Project root containing the future venv directory.
        venv_name
            Directory name only (e.g. ``.venv``), not an absolute path.
        python_exe
            Interpreter used to create the environment (defaults to
            :data:`sys.executable`).

        Returns
        -------
        bool
            ``True`` if the venv was created successfully.
        """
        venv_path = target_path / venv_name
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            console=output.console,
        ) as progress:
            task = progress.add_task(
                f"[cyan]Creating virtual environment '{venv_name}'...", total=None
            )
            try:
                result = subprocess.run(
                    [python_exe, "-m", "venv", str(venv_path)],
                    capture_output=True,
                    text=True,
                    timeout=TIMEOUT_VENV_CREATE,
                )
                if result.returncode != 0:
                    output.print_error(f"Failed to create venv: {result.stderr}")
                    return False
                progress.update(task, completed=True)
                output.print_success(f"Created virtual environment: {venv_name}/")
                return True
            except subprocess.TimeoutExpired:
                output.print_error("Virtual environment creation timed out")
                return False
            except FileNotFoundError:
                output.print_error(f"Python executable not found: {python_exe}")
                return False
            except OSError as e:
                output.print_error(f"Error creating venv: {e}")
                return False

    @staticmethod
    def activation_commands(venv_name: str) -> tuple[str, str]:
        """Return shell snippets for Unix and Windows activation.

        Returns
        -------
        tuple[str, str]
            ``(unix_source, windows_activate)`` for display in help text.
        """
        activate_unix = f"source {venv_name}/bin/activate"
        activate_windows = f"{venv_name}\\Scripts\\activate"
        return activate_unix, activate_windows

    def install_requirements(self, target_path: Path, venv_name: str) -> bool:
        """Run ``pip install -r requirements.txt`` inside the venv.

        Returns
        -------
        bool
            ``True`` if ``pip`` exited 0 and ``requirements.txt`` existed.
        """
        venv_path = target_path / venv_name
        if sys.platform == "win32":
            pip_path = venv_path / "Scripts" / "pip.exe"
        else:
            pip_path = venv_path / "bin" / "pip"

        requirements_path = target_path / REQUIREMENTS_FILENAME
        if not requirements_path.exists():
            output.print_warning(f"{REQUIREMENTS_FILENAME} not found, skipping dependency installation")
            return False

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            console=output.console,
        ) as progress:
            task = progress.add_task("[cyan]Installing dependencies...", total=None)
            try:
                result = subprocess.run(
                    [str(pip_path), "install", "-r", str(requirements_path)],
                    capture_output=True,
                    text=True,
                    timeout=TIMEOUT_PIP_INSTALL,
                )
                if result.returncode != 0:
                    output.print_warning(f"Some dependencies failed to install: {result.stderr}")
                    return False
                progress.update(task, completed=True)
                output.print_success("Installed dependencies")
                return True
            except subprocess.TimeoutExpired:
                output.print_warning("Dependency installation timed out")
                return False
            except OSError as e:
                output.print_warning(f"Error installing dependencies: {e}")
                return False
