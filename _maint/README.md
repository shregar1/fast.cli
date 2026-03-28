# `_maint` — CLI tooling

This folder mirrors the **FastMVC application** repo layout. The **git commit history recorder** matches **`fast_mvc`**’s `_maint/scripts/git_log_recorder.py` (see sibling checkout **`../fast_mvc`** or https://github.com/shregar1/fast.mvc).

| Path | Purpose |
|------|---------|
| **`scripts/git_log_recorder.py`** | In other repos, installed by **`fast setup-commit-log`**; appends to **`commit_history.json`** at the repo root (pre-commit **`post-commit`**). |

## Setup

**Recommended — any repository** (requires **`fast`** on your PATH, or `fast-cli` / `fastmvc`):

```bash
fast setup-commit-log
```

This writes `_maint/scripts/git_log_recorder.py`, updates `.pre-commit-config.yaml`, and runs `pre-commit install` when possible.

**Manual — fast.cli repo only:** from the repo root, install hooks after [pre-commit](https://pre-commit.com/) is available:

```bash
pip install pre-commit
pre-commit install
pre-commit install --hook-type post-commit
```

Requires **Python 3** on your PATH (`python3` runs the script; the post-commit hook in this repo targets **`fast_cli/bundled/git_log_recorder.py`**).

## Related repository

- **FastMVC source:** sibling directory **`../fast_mvc`** — framework and `_maint` reference implementation: https://github.com/shregar1/fast.mvc
