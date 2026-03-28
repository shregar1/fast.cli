"""Fast CLI — FastMVC framework command-line tools.

This package publishes the ``fast-cli`` / ``fastmvc`` console entry points and
the programmatic building blocks used to scaffold FastAPI projects that follow
the FastMVC layout (controllers, services, DTOs, Alembic, etc.).

**Version**

    The public version string is exposed as :data:`__version__` and is read by
    Hatch at build time from this module (see ``[tool.hatch.version]`` in
    ``pyproject.toml``).

**Typical usage**

    Applications and tests usually import the Click application from
    :mod:`fast_cli.app` or the thin re-export :mod:`fast_cli.cli`::

        from fast_cli.app import cli, main

    End users run the tool via the installed scripts ``fast-cli`` or ``fastmvc``,
    or ``python -m fast_cli``.

See Also
--------
fast_cli.app : Root Click group and ``main`` entry point.
fast_cli.project_generation : High-level new-project orchestration.
"""

__version__ = "1.5.0"

__all__ = ["__version__"]
