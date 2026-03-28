"""Resolve the FastMVC “project root” for commands that mutate an existing app.

Some repositories place the runnable package under ``fast_mvc/`` without a
``pyproject.toml`` at the same level. When the user runs the CLI from such a
layout, paths to ``apis/``, ``dtos/``, etc. must be under ``fast_mvc/`` rather
than the repository root.
"""

from __future__ import annotations

from pathlib import Path


def resolve_fastmvc_project_root(cwd: Path | None = None) -> Path:
    """Return the directory that contains framework code for the current project.

    Parameters
    ----------
    cwd
        Optional override; defaults to :func:`pathlib.Path.cwd`.

    Returns
    -------
    pathlib.Path
        ``cwd / "fast_mvc"`` when ``pyproject.toml`` is missing but ``fast_mvc``
        exists in ``cwd``; otherwise ``cwd`` unchanged.
    """
    target = cwd or Path.cwd()
    if (
        not (target / "pyproject.toml").exists()
        and (target / "fast_mvc").exists()
    ):
        return target / "fast_mvc"
    return target
