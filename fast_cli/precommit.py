"""Install pre-commit into a project virtual environment.

Requires:

* ``.pre-commit-config.yaml`` at the project root.
* An existing venv at ``target_path / venv_name`` with ``pip`` and enough
  permissions to run ``git`` commands.

The installer performs two steps: ``pip install pre-commit`` inside the venv,
then ``pre-commit install`` from the project directory (initializing a git repo
if none exists). The process restores the original working directory in a
``finally`` block.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from rich.progress import Progress, SpinnerColumn, TextColumn

from fast_cli.output import output


class PreCommitInstaller:
    """Install the ``pre-commit`` package and Git hook scripts in a project."""

    def install(self, target_path: Path, venv_name: str = ".venv") -> bool:
        """Install pre-commit hooks under ``target_path``.

        Parameters
        ----------
        target_path
            Project root containing ``.pre-commit-config.yaml``.
        venv_name
            Name of the virtual environment directory created earlier.

        Returns
        -------
        bool
            ``True`` if hooks were installed, ``False`` if the config is missing,
            pip/pre-commit failed, or ``pre-commit install`` returned non-zero.

        Notes
        -----
        On Windows, ``pip.exe`` and ``pre-commit.exe`` live under ``Scripts``;
        on Unix, under ``bin``. Initial ``git commit`` may fail silently if
        user identity is not configured (same as ``git commit -q`` with
        ``check=False`` is not used for that call—see source).
        """
        venv_path = target_path / venv_name
        precommit_config = target_path / ".pre-commit-config.yaml"
        if not precommit_config.exists():
            return False

        if sys.platform == "win32":
            pip_path = venv_path / "Scripts" / "pip.exe"
            precommit_path = venv_path / "Scripts" / "pre-commit.exe"
        else:
            pip_path = venv_path / "bin" / "pip"
            precommit_path = venv_path / "bin" / "pre-commit"

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            console=output.console,
        ) as progress:
            task = progress.add_task("[cyan]Installing pre-commit...", total=None)
            try:
                result = subprocess.run(
                    [str(pip_path), "install", "pre-commit", "-q"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode != 0:
                    output.print_warning(f"Could not install pre-commit: {result.stderr}")
                    return False
                progress.update(task, completed=True)
            except OSError as e:
                output.print_warning(f"Could not install pre-commit: {e}")
                return False

            task = progress.add_task("[cyan]Installing pre-commit hooks...", total=None)
            original_cwd = os.getcwd()
            try:
                os.chdir(target_path)
                if not (target_path / ".git").exists():
                    subprocess.run(["git", "init", "-q"], check=True)
                    subprocess.run(["git", "add", "."], check=True)
                    subprocess.run(
                        ["git", "commit", "-m", "Initial commit", "-q"],
                        check=False,
                    )
                result = subprocess.run(
                    [str(precommit_path), "install"],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if result.returncode != 0:
                    output.print_warning(f"Could not install hooks: {result.stderr}")
                    return False
                progress.update(task, completed=True)
                output.print_success("Installed pre-commit hooks")
                output.print_info("Hooks will run automatically on 'git commit'")
                return True
            except OSError as e:
                output.print_warning(f"Could not initialize pre-commit: {e}")
                return False
            finally:
                os.chdir(original_cwd)
