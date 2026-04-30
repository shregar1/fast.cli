"""Locate FastMVC framework sources on disk.

The generator must find the directory that contains the ``fast_mvc`` package
(or equivalent) to copy into a new project. Resolution order:

1. ``<repo_root>/fast_mvc`` where ``repo_root`` is the parent of the installed
   ``fastx_cli`` package (editable installs or monorepo checkouts).
2. If missing, ``./fast_mvc`` under the current working directory.
3. Otherwise ``fast_mvc`` next to the package (legacy layout).

This allows both monorepo development and pip-installed CLI usage without
bundling the full framework inside the wheel.
"""

from __future__ import annotations

from pathlib import Path

from fastx_cli.constants import DEFAULT_TEMPLATE_ITEMS, FRAMEWORK_PACKAGE_NAME


class FrameworkSourceLocator:
    """Resolve ``fast_mvc`` on disk and filter template candidate paths.

    Parameters
    ----------
    package_dir
        Directory containing ``fastx_cli`` (defaults to this file's parent). Used
        to infer ``repo_root`` as ``package_dir.parent``.

    Attributes
    ----------
    _package_dir : pathlib.Path
        Absolute path to the ``fastx_cli`` package directory.
    """

    def __init__(self, package_dir: Path | None = None) -> None:
        self._package_dir = package_dir or Path(__file__).resolve().parent

    @property
    def repo_root(self) -> Path:
        """Filesystem root of the repository checkout (parent of ``fastx_cli``)."""
        return self._package_dir.parent

    def fast_mvc_root(self) -> Path:
        """Directory containing framework package sources (e.g. ``fast_mvc/``).

        Returns
        -------
        pathlib.Path
            Path to the framework tree. May not exist if the user runs the CLI
            without a local ``fast_mvc`` checkout; callers should handle empty
            template lists.
        """
        candidates = [
            self.repo_root / FRAMEWORK_PACKAGE_NAME,
            self.repo_root.parent / FRAMEWORK_PACKAGE_NAME,
            Path.cwd() / FRAMEWORK_PACKAGE_NAME,
            self._package_dir / FRAMEWORK_PACKAGE_NAME,
        ]
        for path in candidates:
            if path.exists():
                return path
        return candidates[0]

    def list_existing_template_items(self) -> list[str]:
        """Return only template entries that exist under :meth:`fast_mvc_root`."""
        source = self.fast_mvc_root()
        return [item for item in DEFAULT_TEMPLATE_ITEMS if (source / item).exists()]
