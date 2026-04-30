"""Questionary validators for interactive prompts.

When ``questionary`` is installed (recommended extra: ``fastmvc-cli[interactive]``),
these classes subclass :class:`questionary.Validator` and enforce input rules
for project names, paths, and emails.

If ``questionary`` is **not** installed, :data:`HAS_QUESTIONARY` is ``False`` and
placeholder empty classes are defined so imports still resolve; interactive
flows should fall back to plain :mod:`click` prompts (see
:class:`fastx_cli.project_generation.ProjectGenerationOrchestrator`).

See Also
--------
fastx_cli.validators.HAS_QUESTIONARY : Feature flag checked before using Questionary.
"""

from __future__ import annotations

import re

try:
    from questionary import ValidationError, Validator

    HAS_QUESTIONARY = True

    class EmailValidator(Validator):
        """Validate a single-line email address using a conservative regex.

        The pattern matches common RFC-like local and domain parts; it is
        intended for developer UX, not cryptographic identity verification.
        """

        def validate(self, document):  # type: ignore[no-untyped-def]
            email = document.text
            pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if not re.match(pattern, email):
                raise ValidationError(
                    message="Please enter a valid email address",
                    cursor_position=len(email),
                )

    class PathValidator(Validator):
        """Ensure the target path string is non-empty and free of illegal characters."""

        def validate(self, document):  # type: ignore[no-untyped-def]
            path = document.text.strip()
            if not path:
                raise ValidationError(message="Path cannot be empty", cursor_position=0)
            invalid_chars = '<>:"|?*'
            for char in invalid_chars:
                if char in path:
                    raise ValidationError(
                        message=f"Path cannot contain invalid character: {char}",
                        cursor_position=path.find(char),
                    )

    class ProjectNameValidator(Validator):
        """Require a non-empty string that is a valid Python identifier."""

        def validate(self, document):  # type: ignore[no-untyped-def]
            name = document.text.strip()
            if not name:
                raise ValidationError(
                    message="Project name cannot be empty", cursor_position=0
                )
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
                raise ValidationError(
                    message="Must be a valid Python identifier (letters, numbers, underscores)",
                    cursor_position=0,
                )

except ImportError:
    HAS_QUESTIONARY = False

    class EmailValidator:
        """Stub when Questionary is unavailable."""

        pass

    class PathValidator:
        """Stub when Questionary is unavailable."""

        pass

    class ProjectNameValidator:
        """Stub when Questionary is unavailable."""

        pass
