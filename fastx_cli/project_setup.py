"""Post-copy project structure and metadata updates.

After :class:`fastx_cli.file_copy.ProjectCopier` finishes, :class:`ProjectBootstrap`
adds opinionated folders (``tests/``, ``docs/``, ``scripts/``), materializes
``.env`` from ``.env.example`` when safe, and regex-patches ``pyproject.toml``
name/description/authors.

The ``context`` ``dict`` mirrors the same keys used by
:class:`fastx_cli.template_engine.TemplateRenderer`
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from fastx_cli.constants import (
    ENV_EXAMPLE_FILENAME,
    ENV_FILENAME,
    PYPROJECT_FILENAME,
)
from fastx_cli.output import output
from fastx_cli.template_engine import TemplateRenderer


class ProjectBootstrap:
    """Create auxiliary directories and patch packaging metadata."""

    def __init__(self, renderer: TemplateRenderer | None = None) -> None:
        self._renderer = renderer or TemplateRenderer()

    def generate_env_file(self, target_path: Path, context: dict) -> bool:
        """Copy ``.env.example`` to ``.env`` and run template substitution.

        Does nothing if ``.env`` already exists (to avoid overwriting secrets).

        Returns
        -------
        bool
            ``True`` if a new ``.env`` was created.
        """
        example_env = target_path / ENV_EXAMPLE_FILENAME
        target_env = target_path / ENV_FILENAME
        if example_env.exists() and not target_env.exists():
            try:
                shutil.copy2(example_env, target_env)
                self._renderer.process_file(target_env, context)
                output.print_success(f"Generated {ENV_FILENAME} from {ENV_EXAMPLE_FILENAME}")
                return True
            except OSError as e:
                output.print_warning(f"Could not generate {ENV_FILENAME}: {e}")
        return False

    def create_project_structure(self, target_path: Path, context: dict) -> None:
        """Create ``tests``, ``docs``, ``scripts`` trees and ``__init__.py`` under tests.

        The ``context`` parameter is reserved for future per-directory
        customization but is currently unused.
        """
        dirs = [
            ("tests", "🧪"),
            ("tests/unit", "  └─"),
            ("tests/integration", "  └─"),
            ("docs", "📚"),
            ("scripts", "🔧"),
        ]
        output.console.print("\n[bold cyan]Creating project structure:[/bold cyan]")
        for dir_name, icon in dirs:
            full_path = target_path / dir_name
            full_path.mkdir(parents=True, exist_ok=True)
            if dir_name.startswith("tests"):
                (full_path / "__init__.py").touch()
            output.console.print(f"  [green]{icon}[/green] {dir_name}/")

    def update_pyproject_toml(self, target_path: Path, context: dict) -> None:
        """Replace name, description, authors, and maintainers in ``pyproject.toml``.

        Uses regular expressions; complex TOML with nested tables may need
        manual follow-up after generation.
        """
        pyproject_path = target_path / PYPROJECT_FILENAME
        if not pyproject_path.exists():
            return
        try:
            content = pyproject_path.read_text()
            content = re.sub(
                r'name = "[^"]*"', f'name = "{context["project_slug"]}"', content
            )
            content = re.sub(
                r'description = "[^"]*"',
                f'description = "{context["description"]}"',
                content,
            )
            authors_str = (
                f'{{name = "{context["author_name"]}", email = "{context["author_email"]}"}}'
            )
            content = re.sub(r"authors = \[[^\]]*\]", f"authors = [{authors_str}]", content)
            content = re.sub(
                r"maintainers = \[[^\]]*\]", f"maintainers = [{authors_str}]", content
            )
            pyproject_path.write_text(content)
            output.print_success(f"Updated {PYPROJECT_FILENAME}")
        except OSError as e:
            output.print_warning(f"Could not update {PYPROJECT_FILENAME}: {e}")
