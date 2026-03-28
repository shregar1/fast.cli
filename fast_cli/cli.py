"""Compatibility shim for imports of ``cli`` and ``main``.

Historically the entire application lived in a single ``cli.py`` file. After
refactoring, the implementation moved to :mod:`fast_cli.app`. This module
re-exports :data:`cli` and :data:`main` so that::

    from fast_cli.cli import main

continues to work and documentation links to ``fast_cli.cli:main`` remain valid
if you update entry points—though the canonical entry point is now
``fast_cli.app:main``.
"""

from fast_cli.app import cli, main

__all__ = ["cli", "main"]
