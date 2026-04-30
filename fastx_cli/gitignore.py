"""Append virtual-environment and tooling ignores to ``.gitignore``.

After creating a named virtual environment (e.g. ``.venv``), generated projects
should ignore that directory plus common Python noise. :class:`GitignoreUpdater`
either appends a standard block to an existing ``.gitignore`` or creates a new
file. It avoids duplicate entries when the venv name already appears in the file.
"""

from __future__ import annotations

from pathlib import Path

from fastx_cli.output import output


class GitignoreUpdater:
    """Synchronize ``.gitignore`` with the chosen virtualenv directory name.

    The appended block covers typical Python artifacts (``__pycache__``,
    ``.pytest_cache``, coverage output) in addition to the specific ``venv_name``.
    """

    def update_for_venv(self, target_path: Path, venv_name: str) -> None:
        """Append ignore rules for ``venv_name`` and common Python cruft.

        Parameters
        ----------
        target_path
            Root of the generated project (where ``.gitignore`` lives).
        venv_name
            Directory name of the virtual environment (e.g. ``.venv``).

        Notes
        -----
        Failures are logged as warnings via :class:`~fastx_cli.output.CliOutput`
        rather than raising, so generation can continue with partial setup.
        """
        gitignore_path = target_path / ".gitignore"
        venv_entries = [
            "",
            "# Virtual Environment",
            f"{venv_name}/",
            f"{venv_name}\\",
            ".env/",
            ".env\\",
            "venv/",
            "venv\\",
            "ENV/",
            "env/",
            "__pycache__/",
            "*.py[cod]",
            "*$py.class",
            ".Python",
            "*.so",
            ".pytest_cache/",
            ".coverage",
            "htmlcov/",
            ".DS_Store",
        ]
        try:
            if gitignore_path.exists():
                content = gitignore_path.read_text()
                if venv_name not in content:
                    with open(gitignore_path, "a", encoding="utf-8") as f:
                        f.write("\n".join(venv_entries) + "\n")
            else:
                gitignore_path.write_text("\n".join(venv_entries) + "\n")
            output.print_success(f"Updated .gitignore for '{venv_name}'")
        except OSError as e:
            output.print_warning(f"Could not update .gitignore: {e}")
