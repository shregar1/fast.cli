"""Tests for :mod:`fast_cli.template_engine` and :mod:`fast_cli.validators`."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fast_cli.template_engine import TemplateRenderer


def _ctx() -> dict:
    return {
        "project_name": "P",
        "project_slug": "p",
        "author_name": "A",
        "author_email": "a@b.co",
        "description": "D",
        "version": "1.0.0",
        "python_version": "3.11",
    }


def test_template_renderer_substitutions(tmp_path: Path) -> None:
    p = tmp_path / "f.txt"
    p.write_text(
        "{{PROJECT_NAME}} {{PROJECT_SLUG}} {{AUTHOR_NAME}} {{AUTHOR_EMAIL}} "
        "{{DESCRIPTION}} {{VERSION}} {{PYTHON_VERSION}} {{JWT_SECRET_KEY}} "
        "{{BCRYPT_SALT}} {{APP_PORT}}"
    )
    TemplateRenderer().process_file(p, _ctx())
    text = p.read_text()
    assert "P" in text and "p" in text and "A" in text


def test_template_renderer_binary_skip(tmp_path: Path) -> None:
    p = tmp_path / "b.bin"
    p.write_bytes(b"\xff\xfe")
    TemplateRenderer().process_file(p, _ctx())  # should not raise


@pytest.mark.skipif(sys.platform == "win32", reason="chmod read-only not reliable on Windows")
def test_template_renderer_read_error(tmp_path: Path) -> None:
    p = tmp_path / "ro.txt"
    p.write_text("{{PROJECT_NAME}}")
    p.chmod(0)
    try:
        TemplateRenderer().process_file(p, _ctx())
    finally:
        p.chmod(0o644)


def test_validators_with_questionary() -> None:
    pytest.importorskip("questionary")
    from fast_cli.validators import (
        HAS_QUESTIONARY,
        EmailValidator,
        PathValidator,
        ProjectNameValidator,
    )
    from questionary import ValidationError

    assert HAS_QUESTIONARY is True

    ev = EmailValidator()
    doc = MagicMock()
    doc.text = "bad"
    with pytest.raises(ValidationError):
        ev.validate(doc)
    doc.text = "a@b.co"
    ev.validate(doc)

    pv = PathValidator()
    doc.text = ""
    with pytest.raises(ValidationError):
        pv.validate(doc)
    doc.text = 'a<b'
    with pytest.raises(ValidationError):
        pv.validate(doc)
    doc.text = "ok/path"
    pv.validate(doc)

    pnv = ProjectNameValidator()
    doc.text = ""
    with pytest.raises(ValidationError):
        pnv.validate(doc)
    doc.text = "123bad"
    with pytest.raises(ValidationError):
        pnv.validate(doc)
    doc.text = "good_name"
    pnv.validate(doc)


def test_validators_stub_without_questionary() -> None:
    """Fresh interpreter with ``questionary`` blocked covers stub validator classes."""
    prog = """
import builtins
_real = builtins.__import__
def _imp(name, *a, **kw):
    if name == "questionary" or name.startswith("questionary."):
        raise ImportError("blocked")
    return _real(name, *a, **kw)
builtins.__import__ = _imp
import fast_cli.validators as v
assert v.HAS_QUESTIONARY is False
assert v.EmailValidator.__doc__ is not None
"""
    subprocess.run([sys.executable, "-c", prog], check=True)
