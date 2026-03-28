# Contributing

## Quick setup

Clone the repository and install in editable mode with dev dependencies:

```bash
git clone https://github.com/fastmvc/fast.cli.git
cd fast.cli
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Run the test suite (same command as CI):

```bash
python -m pytest
```

Coverage is enforced at **≥ 99%** for `fast_cli` (see `pyproject.toml`).

Linting (also run in CI’s **`lint`** job):

```bash
ruff check fast_cli tests
mypy fast_cli
```

Optional: install [pre-commit](https://pre-commit.com/) hooks from the repo root:

```bash
pre-commit install
```

## Cutting a release

1. Update **`__version__`** in **`fast_cli/__init__.py`** (and refresh **`CHANGELOG.md`**).
2. Commit and push.
3. Tag with a **`v`** prefix matching the version, e.g. **`v1.5.1`** if the version is `1.5.1`:

   ```bash
   git tag v1.5.1
   git push origin v1.5.1
   ```

4. **PyPI:** If the repo uses [trusted publishing](https://docs.pypi.org/trusted-publishers/), **`.github/workflows/publish-pypi.yml`** uploads on tag push. Otherwise publish manually with `python -m build` and `twine upload` (see README).

The tag and **`fast_cli.__version__`** should match.

## Code style

Match existing patterns in the repo; keep changes focused and covered by tests.

Dependency updates are proposed automatically via **Dependabot** (weekly PRs for `pyproject.toml` and GitHub Actions).
