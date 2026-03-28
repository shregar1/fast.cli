# fast.cli

Fast Framework CLI.

## Related — FastMVC repo

The **framework** and canonical **`_maint`** tooling (including the same commit-history script) live in the sibling checkout:

| | |
|--|--|
| **Local path** | `../fast_mvc` |
| **GitHub** | https://github.com/shregar1/fast.mvc |

This repo records commits to **`commit_history.json`** via **`.pre-commit-config.yaml`** (`post-commit`). To install the same tooling in **any** git repository (writes `_maint/scripts/git_log_recorder.py` and merges the hook):

```bash
fast-cli setup-commit-log
# or: fastmvc setup-commit-log
```

In this repository the hook runs **`fast_cli/bundled/git_log_recorder.py`**; the setup command copies that script into `_maint/scripts/` when used elsewhere.

Manual hook install (if you skip `--install-hooks`):

```bash
pip install pre-commit
pre-commit install
pre-commit install --hook-type post-commit
```

See **`_maint/README.md`** for details.

## Layout

```
fast.cli/
├── fast_cli/bundled/   # git_log_recorder.py (source for setup-commit-log)
├── _maint/scripts/     # optional copy in other repos (see setup-commit-log)
├── .pre-commit-config.yaml
└── …
```
