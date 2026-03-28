# fast.cli

Fast Framework CLI.

## Related — FastMVC repo

The **framework** and canonical **`_maint`** tooling (including the same commit-history script) live in the sibling checkout:

| | |
|--|--|
| **Local path** | `../fast_mvc` |
| **GitHub** | https://github.com/shregar1/fast.mvc |

This repo’s **`_maint/scripts/git_log_recorder.py`** and **`.pre-commit-config.yaml`** (`post-commit`) follow that project. Install hooks:

```bash
pip install pre-commit
pre-commit install
pre-commit install --hook-type post-commit
```

See **`_maint/README.md`** for details.

## Layout

```
fast.cli/
├── _maint/scripts/     # git_log_recorder.py → GIT_METADATA.json
├── .pre-commit-config.yaml
└── …
```
