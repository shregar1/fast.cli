"""Static configuration data shared by generators and tooling.

This module avoids magic strings scattered across copy logic and cleanup
commands. Lists are **candidates**: filesystem operations still verify each
path exists before copying (see :meth:`FrameworkSourceLocator.list_existing_template_items`).

DEFAULT_TEMPLATE_ITEMS
    Relative paths under the FastMVC source tree that form a new project
    skeleton (framework packages, ``app.py``, Docker files, etc.). The ``tests``
    tree is copied without ``tests/framework`` (FastMVC’s internal coverage suite);
    see :func:`fastx_cli.file_copy.template_copytree_ignore`.

ARTIFACTS_BY_LANGUAGE
    Maps a language key (``python``, ``java``, ``rust``) to directory names and
    file globs that :class:`fastx_cli.commands.decimate_cmd.ArtifactDecimator`
    removes when cleaning build/cache artifacts.
"""

from __future__ import annotations

# Candidate paths relative to FastMVC source root for new projects.
DEFAULT_TEMPLATE_ITEMS: list[str] = [
    "abstractions",
    "constants",
    "controllers",
    "core",
    "dependencies",
    "dtos",
    "entities",
    "errors",
    "middlewares",
    "migrations",
    "models",
    "repositories",
    "services",
    "utilities",
    "example",
    "tests",
    "config",
    "__init__.py",
    "app.py",
    "start_utils.py",
    "structured_log.py",
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
    "docker-entrypoint.sh",
    "postman",
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

# Project defaults
DEFAULT_VENV_NAME: str = ".venv"
DEFAULT_PROJECT_VERSION: str = "0.1.0"
DEFAULT_PYTHON_VERSION: str = "3.11"
SUPPORTED_PYTHON_VERSIONS: tuple[str, ...] = ("3.10", "3.11", "3.12", "3.13")
DEFAULT_APP_PORT: str = "8000"
DEFAULT_AUTHOR_NAME: str = "Developer"
DEFAULT_PROJECT_NAME: str = "my_fastapi_project"

# Framework
FRAMEWORK_PACKAGE_NAME: str = "fast_mvc"
FRAMEWORK_CONTROLLER_PATH: str = "abstractions/controller.py"

# File names
ENV_FILENAME: str = ".env"
ENV_EXAMPLE_FILENAME: str = ".env.example"
PYPROJECT_FILENAME: str = "pyproject.toml"
REQUIREMENTS_FILENAME: str = "requirements.txt"
ALEMBIC_INI_FILENAME: str = "alembic.ini"
MAKEFILE_FILENAME: str = "Makefile"

# Timeouts (seconds)
TIMEOUT_VENV_CREATE: int = 60
TIMEOUT_PIP_INSTALL: int = 120
TIMEOUT_ALEMBIC_QUERY: int = 30
TIMEOUT_ALEMBIC_MUTATION: int = 120
TIMEOUT_PRECOMMIT_INSTALL: int = 60
TIMEOUT_SEED_SCRIPT: int = 60
TIMEOUT_COMPLETION_HELPER: int = 30

# Security / crypto
JWT_SECRET_KEY_LENGTH: int = 32
BCRYPT_RANDOM_LENGTH: int = 16
BCRYPT_SALT_PREFIX: str = "$2b$12$"
DEFAULT_BCRYPT_SALT: str = "$2b$12$LQv3c1yqBWVHxkd0LHAkCO"

# CLI
CLI_PROG_NAME: str = "fast"
CLI_ENTRY_POINTS: tuple[str, ...] = ("fast", "fast-cli", "fastmvc")
CLI_MAX_CONTENT_WIDTH: int = 92

# Tasks / workers
DEFAULT_TASK_CONCURRENCY: int = 10
DEFAULT_DASHBOARD_REFRESH_MS: int = 1000

# Checkpoint
CHECKPOINT_JSON_INDENT: int = 2
CHECKPOINT_TIMESTAMP_DISPLAY_LEN: int = 19
CHECKPOINT_SHORT_HASH_LEN: int = 12
CHECKPOINT_MESSAGE_PREVIEW_LEN: int = 40

# Git log recorder
GIT_LOG_RECENT_WINDOW: int = 5
GIT_LOG_MAX_ENTRIES: int = 100

# Banner / UI
BANNER_WIDTH_THRESHOLD: int = 56
BANNER_SUBTITLE: str = "FastAPI / MVC / Production-ready"
ENV_MINIMAL_BANNER: str = "FAST_CLI_MINIMAL_BANNER"

# Template placeholders
TEMPLATE_PLACEHOLDER_PROJECT_NAME: str = "{{PROJECT_NAME}}"
TEMPLATE_PLACEHOLDER_PROJECT_SLUG: str = "{{PROJECT_SLUG}}"
TEMPLATE_PLACEHOLDER_AUTHOR_NAME: str = "{{AUTHOR_NAME}}"
TEMPLATE_PLACEHOLDER_AUTHOR_EMAIL: str = "{{AUTHOR_EMAIL}}"
TEMPLATE_PLACEHOLDER_DESCRIPTION: str = "{{DESCRIPTION}}"
TEMPLATE_PLACEHOLDER_VERSION: str = "{{VERSION}}"
TEMPLATE_PLACEHOLDER_PYTHON_VERSION: str = "{{PYTHON_VERSION}}"
TEMPLATE_PLACEHOLDER_JWT_SECRET_KEY: str = "{{JWT_SECRET_KEY}}"
TEMPLATE_PLACEHOLDER_BCRYPT_SALT: str = "{{BCRYPT_SALT}}"
TEMPLATE_PLACEHOLDER_APP_PORT: str = "{{APP_PORT}}"

# Optional dependency errors
OPTIONAL_DEPS_FAST_CACHING_IMPORT: str = "fast_caching.src.fast_caching"
OPTIONAL_DEPS_FAST_CACHING_ERROR: str = "fast_caching package not found in paths"
OPTIONAL_DEPS_FAST_PLATFORM_IMPORT: str = "fastx_platform.src.task"
OPTIONAL_DEPS_FAST_PLATFORM_ERROR: str = "fast_tasks package not found in paths"

# Venv / decimate
VENV_EXCLUDE_DIRS: frozenset[str] = frozenset({".git", ".venv", "venv", "ENV", "env"})

# Boolean parsing
BOOLEAN_TRUE_VALUES: tuple[str, ...] = ("1", "true", "yes", "on")
BOOLEAN_FALSE_VALUES: tuple[str, ...] = ("0", "false", "no", "off")
