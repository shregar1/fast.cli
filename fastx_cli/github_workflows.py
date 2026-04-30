"""Copy optional GitHub Actions workflow YAMLs into a new project.

Workflow templates are expected at ``<repo_root>/templates/github`` relative to
the monorepo checkout (parent of the ``fastx_cli`` package). They are **not**
shipped inside the PyPI wheel; if the directory is missing, the copier warns and
returns ``False``.

Each copied file is passed through :class:`fastx_cli.template_engine.TemplateRenderer`
so ``{{PROJECT_NAME}}`` and similar markers can be expanded in CI YAML.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fastx_cli.output import output
from fastx_cli.template_engine import TemplateRenderer


class GitHubWorkflowsCopier:
    """Copy ``ci.yml``, ``pr-check.yml``, and ``release.yml`` into ``.github/workflows/``."""

    def __init__(
        self,
        repo_root: Path | None = None,
        renderer: TemplateRenderer | None = None,
    ) -> None:
        self._repo_root = repo_root or Path(__file__).resolve().parent.parent
        self._renderer = renderer or TemplateRenderer()

    def copy_into_project(self, target_path: Path, context: dict) -> bool:
        """Create ``.github/workflows`` and copy any workflow files present.

        Parameters
        ----------
        target_path
            Root of the generated application.
        context
            Template context for :class:`~fastx_cli.template_engine.TemplateRenderer`.

        Returns
        -------
        bool
            ``True`` if at least one workflow file was copied.
        """
        templates_dir = self._repo_root / "templates" / "github"
        if not templates_dir.exists():
            output.print_warning("GitHub Actions templates not found")
            return False
        try:
            workflows_dir = target_path / ".github" / "workflows"
            workflows_dir.mkdir(parents=True, exist_ok=True)
            workflow_files = ["ci.yml", "pr-check.yml", "release.yml"]
            copied = 0
            for name in workflow_files:
                src = templates_dir / name
                if src.exists():
                    dst = workflows_dir / name
                    shutil.copy2(src, dst)
                    self._renderer.process_file(dst, context)
                    copied += 1
            if copied > 0:
                output.print_success(f"Added {copied} GitHub Actions workflows")
                return True
            return False
        except OSError as e:
            output.print_warning(f"Could not copy GitHub Actions templates: {e}")
            return False
