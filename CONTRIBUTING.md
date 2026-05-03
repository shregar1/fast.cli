# Contributing

New to the tool from a user perspective? Start with **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)** (~15 minutes).

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

Coverage is enforced at **≥ 99%** for `fastx_cli` (see `pyproject.toml`).

Linting (also run in CI’s **`lint`** job):

```bash
ruff check fastx_cli tests
mypy fastx_cli
```

Optional: install [pre-commit](https://pre-commit.com/) hooks from the repo root:

```bash
pre-commit install
```

## Cutting a release

Short version:

1. Update **`__version__`** in **`fastx_cli/__init__.py`** (and **`CHANGELOG.md`**).
2. Tag **`vX.Y.Z`** and push the tag; **publish-pypi.yml** runs tests, smoke-installs the wheel, then uploads to PyPI (trusted publishing).

Full checklist, PyPI verification, rollback (yank / patch), and local dry run: **[RELEASING.md](RELEASING.md)**.

The tag and **`fastx_cli.__version__`** must match.

## Code style

Match existing patterns in the repo; keep changes focused and covered by tests.

Dependency updates are proposed automatically via **Dependabot** (weekly PRs for `pyproject.toml` and GitHub Actions).
