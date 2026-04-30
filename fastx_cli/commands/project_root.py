"""Resolve the FastMVC “project root” for commands that mutate an existing app.

Some repositories place the runnable package under ``fast_mvc/`` without a
``pyproject.toml`` at the same level. When the user runs the CLI from such a
layout, paths to ``apis/``, ``dtos/``, etc. must be under ``fast_mvc/`` rather
than the repository root.
"""

from __future__ import annotations

from pathlib import Path

from fastx_cli.constants import FRAMEWORK_PACKAGE_NAME, PYPROJECT_FILENAME


def resolve_fastmvc_project_root(cwd: Path | None = None) -> Path:
    """Return the directory that contains framework code for the current project.

    Parameters
    ----------
    cwd
        Optional override; defaults to :func:`pathlib.Path.cwd`.

    Returns
    -------
    pathlib.Path
        ``cwd / FRAMEWORK_PACKAGE_NAME`` when ``PYPROJECT_FILENAME`` is missing but ``fast_mvc``
        exists in ``cwd``; otherwise ``cwd`` unchanged.
    """
    target = cwd or Path.cwd()
    if (
        not (target / PYPROJECT_FILENAME).exists()
        and (target / FRAMEWORK_PACKAGE_NAME).exists()
    ):
        return target / FRAMEWORK_PACKAGE_NAME
    return target
