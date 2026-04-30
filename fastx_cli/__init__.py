"""Fast CLI — FastMVC framework command-line tools.

This package publishes the ``fast``, ``fast-cli``, and ``fastmvc`` console entry points and
the programmatic building blocks used to scaffold FastAPI projects that follow
the FastMVC layout (controllers, services, DTOs, Alembic, etc.).

**Version**

    The public version string is exposed as :data:`__version__` and is read by
    Hatch at build time from this module (see ``[tool.hatch.version]`` in
    ``pyproject.toml``).

**Typical usage**

    Applications and tests usually import the Click application from
    :mod:`fastx_cli.app` or the thin re-export :mod:`fastx_cli.cli`::

        from fastx_cli.app import cli, main

    End users run the tool via the installed script ``fast`` (or ``fast-cli`` / ``fastmvc``),
    or ``python -m fastx_cli``.

See Also
--------
fastx_cli.app : Root Click group and ``main`` entry point.
fastx_cli.project_generation : High-level new-project orchestration.
"""

__version__ = "1.7.2"

__all__ = ["__version__"]
