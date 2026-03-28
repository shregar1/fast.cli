# Release process

This document is the checklist for maintainers. It complements [CONTRIBUTING.md](CONTRIBUTING.md) (short release bullets) with **end-to-end** steps, **PyPI verification**, and **rollback**.

## Prerequisites

- **PyPI trusted publishing** is configured for this repo (see [.github/workflows/publish-pypi.yml](.github/workflows/publish-pypi.yml) and [PyPI publishing docs](https://docs.pypi.org/trusted-publishers/)).
- Default branch is green: **CI** (Python matrix + smoke + lint) passes on the commit you intend to release.

## Standard release (tag → PyPI)

1. **Changelog** — Add/update [CHANGELOG.md](CHANGELOG.md) for this version (date, highlights, fixes).
2. **Version** — Set **`fast_cli/__init__.py`** `__version__` to the new semantic version (e.g. `1.5.1`).
3. **Commit** — Single commit or PR: e.g. `chore: release 1.5.1`.
4. **Tag** — Create an annotated tag matching the version with a `v` prefix:

   ```bash
   git tag -a v1.5.1 -m "Release v1.5.1"
   git push origin v1.5.1
   ```

5. **Automation** — [publish-pypi.yml](.github/workflows/publish-pypi.yml) runs on `v*` tags:
   - Runs the **test suite** on the tagged commit.
   - Builds **sdist + wheel**.
   - **Smoke-installs** the wheel in a fresh venv and runs `python -m fast_cli.app --help` and `doctor`.
   - Uploads to **PyPI** via OIDC (no long-lived token in the repo).

6. **Verify on PyPI** — Confirm the new version appears at `https://pypi.org/project/fastmvc-cli/#history` and that files match the tag.

7. **Smoke from PyPI (optional but recommended)** — In a clean environment:

   ```bash
   python -m venv /tmp/fastmvc-smoke
   source /tmp/fastmvc-smoke/bin/activate   # Windows: \tmp\fastmvc-smoke\Scripts\activate
   pip install fastmvc-cli==<version>
   fast --help
   fast doctor
   ```

## Version alignment

| Artifact | Must match |
|----------|------------|
| Git tag | `v` + `__version__` (e.g. tag `v1.5.1` ↔ version `1.5.1`) |
| PyPI | Same version string as `__version__` |

## Rollback plan

PyPI **does not** allow re-uploading the same version string. Options:

1. **Yank** the bad release on PyPI (keeps the file but hides it from default `pip install` unless pinned). Use for broken wheels/metadata when a quick fix is not ready.
2. **New patch** — Prefer releasing **`x.y.(z+1)`** with a fix, changelog entry, and new tag. Users unpinned get the fix on upgrade.
3. **Communicate** — If the bad build affected users, note it in CHANGELOG and (if severe) GitHub Discussions / advisory.

## Dry run locally (no upload)

```bash
python -m pip install -U build
python -m build
python -m venv .venv-dist
# POSIX:
.venv-dist/bin/pip install dist/*.whl
.venv-dist/bin/python -m fast_cli.app --help
# Inspect dist/ before any real tag push.
```

## Emergency: disable automated publish

Temporarily disable or rename `publish-pypi.yml` in a branch only if you must stop tag-triggered uploads—prefer fixing forward with a patch release instead.
