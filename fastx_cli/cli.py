"""Compatibility shim for imports of ``cli`` and ``main``.

Historically the entire application lived in a single ``cli.py`` file. After
refactoring, the implementation moved to :mod:`fastx_cli.app`. This module
re-exports :data:`cli` and :data:`main` so that::

    from fastx_cli.cli import main

continues to work and documentation links to ``fastx_cli.cli:main`` remain valid
if you update entry points—though the canonical entry point is now
``fastx_cli.app:main``.
"""

from fastx_cli.app import cli, main

__all__ = ["cli", "main"]
