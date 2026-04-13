"""Replace ``{{PLACEHOLDER}}`` markers in generated text files.

Copied templates are not a full Jinja2 pass: they use simple string
substitution keyed by a **context** dictionary (see :meth:`process_file`).
Binary files should not be routed through this class.

Context keys
------------
The following keys are typically required (see
:class:`fast_cli.project_generation.ProjectGenerationOrchestrator`):

``project_name``, ``project_slug``, ``author_name``, ``author_email``,
``description``, ``version``, ``python_version``

Optional keys (with defaults in :meth:`process_file`):

``jwt_secret_key``, ``bcrypt_salt``, ``app_port``
"""

from __future__ import annotations

from pathlib import Path

from fast_cli.constants import (
    DEFAULT_APP_PORT,
    DEFAULT_BCRYPT_SALT,
    TEMPLATE_PLACEHOLDER_APP_PORT,
    TEMPLATE_PLACEHOLDER_AUTHOR_EMAIL,
    TEMPLATE_PLACEHOLDER_AUTHOR_NAME,
    TEMPLATE_PLACEHOLDER_BCRYPT_SALT,
    TEMPLATE_PLACEHOLDER_DESCRIPTION,
    TEMPLATE_PLACEHOLDER_JWT_SECRET_KEY,
    TEMPLATE_PLACEHOLDER_PROJECT_NAME,
    TEMPLATE_PLACEHOLDER_PROJECT_SLUG,
    TEMPLATE_PLACEHOLDER_PYTHON_VERSION,
    TEMPLATE_PLACEHOLDER_VERSION,
)


class TemplateRenderer:
    """Applies ``{{PLACEHOLDER}}`` substitutions for project scaffolding."""

    def process_file(self, file_path: Path, context: dict) -> None:
        """Read ``file_path``, replace known placeholders, write back UTF-8.

        If the file cannot be read as UTF-8 or is not a text file, the method
        returns silently (no exception) to match legacy behaviour for mixed
        binary trees.

        Parameters
        ----------
        file_path
            Path to a single file (not a directory).
        context
            Mapping with at least the required keys listed in the module docstring.
        """
        try:
            content = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return

        replacements = {
            TEMPLATE_PLACEHOLDER_PROJECT_NAME: context["project_name"],
            TEMPLATE_PLACEHOLDER_PROJECT_SLUG: context["project_slug"],
            TEMPLATE_PLACEHOLDER_AUTHOR_NAME: context["author_name"],
            TEMPLATE_PLACEHOLDER_AUTHOR_EMAIL: context["author_email"],
            TEMPLATE_PLACEHOLDER_DESCRIPTION: context["description"],
            TEMPLATE_PLACEHOLDER_VERSION: context["version"],
            TEMPLATE_PLACEHOLDER_PYTHON_VERSION: context["python_version"],
            TEMPLATE_PLACEHOLDER_JWT_SECRET_KEY: context.get("jwt_secret_key", "your-secret-key-here"),
            TEMPLATE_PLACEHOLDER_BCRYPT_SALT: context.get(
                "bcrypt_salt", DEFAULT_BCRYPT_SALT
            ),
            TEMPLATE_PLACEHOLDER_APP_PORT: context.get("app_port", DEFAULT_APP_PORT),
        }
        for placeholder, value in replacements.items():
            content = content.replace(placeholder, value)
        try:
            file_path.write_text(content, encoding="utf-8")
        except OSError:
            pass
