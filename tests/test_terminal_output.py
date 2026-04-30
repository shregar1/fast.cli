"""Terminal / Rich output behavior (compact banner, env flags)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastx_cli.output import CliOutput, _use_compact_banner
from rich.console import Console


def test_compact_banner_via_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAST_CLI_MINIMAL_BANNER", "1")
    CliOutput().print_banner()


def test_compact_banner_narrow_console() -> None:
    o = CliOutput()
    o.console = Console(width=40)
    o.print_banner()


def test_use_compact_banner_respects_width() -> None:
    assert _use_compact_banner(SimpleNamespace(width=40)) is True
    assert _use_compact_banner(SimpleNamespace(width=80)) is False


def test_full_banner_wide_console() -> None:
    o = CliOutput()
    o.console = Console(width=120)
    o.print_banner()
