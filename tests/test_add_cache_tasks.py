"""Tests for add, cache, and tasks commands."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from fastx_cli.app import cli
from fastx_cli.commands.add_cmd import ResourceScaffolder


def _fastmvc_project(tmp_path: Path) -> Path:
    root = tmp_path / "app"
    (root / "abstractions").mkdir(parents=True)
    (root / "abstractions" / "controller.py").write_text("#")
    return root


def _install_fake_fast_caching() -> None:
    inner = types.ModuleType("fast_caching.src.fast_caching")

    class Backend:
        async def clear(self) -> bool:
            return True

    class FC:
        backend = Backend()

        async def invalidate(self, tags: list) -> int:
            return len(tags)

    inner.fast_cache = FC()
    sys.modules["fast_caching"] = types.ModuleType("fast_caching")
    sys.modules["fast_caching.src"] = types.ModuleType("fast_caching.src")
    sys.modules["fast_caching.src.fast_caching"] = inner


def _remove_fake_fast_caching() -> None:
    for k in list(sys.modules):
        if k == "fast_caching" or k.startswith("fast_caching."):
            del sys.modules[k]


def test_add_resource_success(tmp_path: Path) -> None:
    root = _fastmvc_project(tmp_path)
    runner = CliRunner()
    with patch("fastx_cli.commands.add_cmd.resolve_fastmvc_project_root", return_value=root):
        with patch("fastx_cli.commands.add_cmd.HAS_QUESTIONARY", False):
            r = runner.invoke(
                cli,
                ["add", "resource", "--folder", "user", "--resource", "fetch"],
            )
            assert r.exit_code == 0


def test_add_resource_not_project(tmp_path: Path) -> None:
    runner = CliRunner()
    with patch(
        "fastx_cli.commands.add_cmd.resolve_fastmvc_project_root",
        return_value=tmp_path,
    ):
        r = runner.invoke(
            cli,
            ["add", "resource", "--folder", "u", "--resource", "f"],
        )
        assert r.exit_code != 0


def test_add_resource_with_questionary_fields(tmp_path: Path) -> None:
    pytest.importorskip("questionary")
    root = _fastmvc_project(tmp_path)
    runner = CliRunner()
    with patch("fastx_cli.commands.add_cmd.resolve_fastmvc_project_root", return_value=root):
        with patch("fastx_cli.commands.add_cmd.HAS_QUESTIONARY", True):
            with patch("fastx_cli.commands.add_cmd.questionary") as q:
                q.confirm.return_value.ask.side_effect = [True, False]
                q.text.return_value.ask.return_value = "extra"
                q.select.return_value.ask.return_value = "str"
                r = runner.invoke(
                    cli,
                    ["add", "resource", "--folder", "user", "--resource", "create"],
                )
                assert r.exit_code == 0


def test_resource_scaffolder_write(tmp_path: Path) -> None:
    ResourceScaffolder(tmp_path).run("user", "fetch", "v1", True)


def test_cache_clear_success() -> None:
    _install_fake_fast_caching()
    try:
        runner = CliRunner()
        r = runner.invoke(cli, ["cache", "clear"])
        assert r.exit_code == 0
    finally:
        _remove_fake_fast_caching()


def test_cache_invalidate_no_tags() -> None:
    runner = CliRunner()
    r = runner.invoke(cli, ["cache", "invalidate"])
    assert r.exit_code == 0


def test_cache_invalidate_success() -> None:
    _install_fake_fast_caching()
    try:
        runner = CliRunner()
        r = runner.invoke(cli, ["cache", "invalidate", "a", "b"])
        assert r.exit_code == 0
    finally:
        _remove_fake_fast_caching()


def test_tasks_worker_keyboardinterrupt() -> None:
    runner = CliRunner()

    class W:
        def __init__(self, *a, **k) -> None:
            pass

        async def start(self) -> None:
            raise KeyboardInterrupt()

    fake = types.ModuleType("fastx_platform.src.task")
    fake.Worker = W
    sys.modules["fastx_platform"] = types.ModuleType("fastx_platform")
    sys.modules["fastx_platform.src"] = types.ModuleType("fastx_platform.src")
    sys.modules["fastx_platform.src.task"] = fake
    try:
        r = runner.invoke(cli, ["tasks", "worker"])
        assert r.exit_code == 0
    finally:
        for k in ("fastx_platform.src.task", "fastx_platform.src", "fastx_platform"):
            sys.modules.pop(k, None)


def test_tasks_list_empty() -> None:
    runner = CliRunner()
    fake = types.ModuleType("fastx_platform.src.task")
    fake.TaskRegistry = MagicMock()
    fake.TaskRegistry.all_tasks.return_value = {}
    sys.modules["fastx_platform"] = types.ModuleType("fastx_platform")
    sys.modules["fastx_platform.src"] = types.ModuleType("fastx_platform.src")
    sys.modules["fastx_platform.src.task"] = fake
    try:
        r = runner.invoke(cli, ["tasks", "list"])
        assert r.exit_code == 0
    finally:
        for k in ("fastx_platform.src.task", "fastx_platform.src", "fastx_platform"):
            sys.modules.pop(k, None)


def test_tasks_list_with_tasks() -> None:
    runner = CliRunner()
    meta = MagicMock()
    meta.fn.__name__ = "fn"
    meta.retry = 1
    fake = types.ModuleType("fastx_platform.src.task")
    fake.TaskRegistry = MagicMock()
    fake.TaskRegistry.all_tasks.return_value = {"t": meta}
    sys.modules["fastx_platform"] = types.ModuleType("fastx_platform")
    sys.modules["fastx_platform.src"] = types.ModuleType("fastx_platform.src")
    sys.modules["fastx_platform.src.task"] = fake
    try:
        r = runner.invoke(cli, ["tasks", "list"])
        assert r.exit_code == 0
    finally:
        for k in ("fastx_platform.src.task", "fastx_platform.src", "fastx_platform"):
            sys.modules.pop(k, None)


def test_tasks_status_not_found() -> None:
    runner = CliRunner()
    fake = types.ModuleType("fastx_platform.src.task")
    ft = MagicMock()

    async def get_result(_tid: str):
        return None

    ft.backend.get_result = get_result
    fake.fast_tasks = ft
    sys.modules["fastx_platform"] = types.ModuleType("fastx_platform")
    sys.modules["fastx_platform.src"] = types.ModuleType("fastx_platform.src")
    sys.modules["fastx_platform.src.task"] = fake
    try:
        r = runner.invoke(cli, ["tasks", "status", "id1"])
        assert r.exit_code == 0
    finally:
        for k in ("fastx_platform.src.task", "fastx_platform.src", "fastx_platform"):
            sys.modules.pop(k, None)


def test_tasks_status_found() -> None:
    runner = CliRunner()
    res = MagicMock()
    res.task_id = "1"
    res.status = "success"
    res.timestamp = "t"
    res.result = "r"
    res.error = None

    async def get_result(_tid: str):
        return res

    fake = types.ModuleType("fastx_platform.src.task")
    ft = MagicMock()
    ft.backend.get_result = get_result
    fake.fast_tasks = ft
    sys.modules["fastx_platform"] = types.ModuleType("fastx_platform")
    sys.modules["fastx_platform.src"] = types.ModuleType("fastx_platform.src")
    sys.modules["fastx_platform.src.task"] = fake
    try:
        r = runner.invoke(cli, ["tasks", "status", "id1"])
        assert r.exit_code == 0
    finally:
        for k in ("fastx_platform.src.task", "fastx_platform.src", "fastx_platform"):
            sys.modules.pop(k, None)


def test_tasks_status_running_style() -> None:
    runner = CliRunner()
    res = MagicMock()
    res.task_id = "1"
    res.status = "running"
    res.timestamp = "t"
    res.result = None
    res.error = None

    async def get_result(_tid: str):
        return res

    fake = types.ModuleType("fastx_platform.src.task")
    ft = MagicMock()
    ft.backend.get_result = get_result
    fake.fast_tasks = ft
    sys.modules["fastx_platform"] = types.ModuleType("fastx_platform")
    sys.modules["fastx_platform.src"] = types.ModuleType("fastx_platform.src")
    sys.modules["fastx_platform.src.task"] = fake
    try:
        r = runner.invoke(cli, ["tasks", "status", "x"])
        assert r.exit_code == 0
    finally:
        for k in ("fastx_platform.src.task", "fastx_platform.src", "fastx_platform"):
            sys.modules.pop(k, None)


def test_tasks_dashboard_interrupt() -> None:
    runner = CliRunner()
    fake = types.ModuleType("fastx_platform.src.task")
    fake.TaskRegistry = MagicMock()
    fake.TaskRegistry.all_tasks.return_value = {}
    ft = MagicMock()

    async def get_result(_n: str):
        return None

    ft.backend.get_result = get_result
    fake.fast_tasks = ft
    sys.modules["fastx_platform"] = types.ModuleType("fastx_platform")
    sys.modules["fastx_platform.src"] = types.ModuleType("fastx_platform.src")
    sys.modules["fastx_platform.src.task"] = fake
    try:
        with patch("fastx_cli.commands.tasks_cmd.time.sleep", side_effect=KeyboardInterrupt):
            r = runner.invoke(cli, ["tasks", "dashboard", "--refresh", "100"])
            assert r.exit_code == 0
    finally:
        for k in ("fastx_platform.src.task", "fastx_platform.src", "fastx_platform"):
            sys.modules.pop(k, None)
