# `_maint` — CLI tooling

This folder mirrors the **FastMVC application** repo layout. The **git commit history recorder** matches **`fast_mvc`**’s `_maint/scripts/git_log_recorder.py` (see sibling checkout **`../fast_mvc`** or https://github.com/shregar1/fast.mvc).

| Path | Purpose |
|------|---------|
| **`scripts/git_log_recorder.py`** | Appends the latest commit to **`GIT_METADATA.json`** at the repo root (via pre-commit **`post-commit`**). |

## Setup

From the **fast.cli** repo root:

```bash
pip install pre-commit
pre-commit install
pre-commit install --hook-type post-commit
```

Requires **Python 3** on your PATH (`python3` runs the script).

## Related repository

- **FastMVC source:** sibling directory **`../fast_mvc`** — framework and `_maint` reference implementation: https://github.com/shregar1/fast.mvc
