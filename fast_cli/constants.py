"""Static configuration data shared by generators and tooling.

This module avoids magic strings scattered across copy logic and cleanup
commands. Lists are **candidates**: filesystem operations still verify each
path exists before copying (see :meth:`FrameworkSourceLocator.list_existing_template_items`).

DEFAULT_TEMPLATE_ITEMS
    Relative paths under the FastMVC source tree that form a new project
    skeleton (framework packages, ``app.py``, Docker files, etc.).

ARTIFACTS_BY_LANGUAGE
    Maps a language key (``python``, ``java``, ``rust``) to directory names and
    file globs that :class:`fast_cli.commands.decimate_cmd.ArtifactDecimator`
    removes when cleaning build/cache artifacts.
"""

from __future__ import annotations

# Candidate paths relative to FastMVC source root for new projects.
DEFAULT_TEMPLATE_ITEMS: list[str] = [
    "abstractions",
    "constants",
    "core",
    "dependencies",
    "dtos",
    "middlewares",
    "example",
    "config",
    "__init__.py",
    "app.py",
    "start_utils.py",
    "pyproject.toml",
    "requirements.txt",
    "requirements-dev.txt",
    "Dockerfile",
    "docker-compose.yml",
    "alembic.ini",
    ".env.example",
    ".gitignore",
    "README.md",
    ".vscode",
    "Makefile",
    ".pre-commit-config.yaml",
]

ARTIFACTS_BY_LANGUAGE: dict[str, dict[str, list[str]]] = {
    "python": {
        "dirs": [
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
            ".mypy_cache",
            "htmlcov",
            ".hypothesis",
            "build",
            "dist",
            "*.egg-info",
            ".vulture_cache",
        ],
        "files": [".coverage", "*.pyc", "*.pyo", "*.pyd"],
    },
    "java": {
        "dirs": ["target", "build", ".gradle"],
        "files": ["*.class", "*.jar", "*.war", "*.ear"],
    },
    "rust": {"dirs": ["target"], "files": []},
}
