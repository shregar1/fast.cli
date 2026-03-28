# Dependencies and supply chain

## Runtime stack (`fast-*`)

`fastmvc-cli` depends on the **FastMVC / FastAPI ecosystem** packages (see `pyproject.toml` `[project] dependencies`):

- **fast-platform**, **fast-middleware**, **fast-database**, **fast-dashboards**, **fast-mvc** — application framework and tooling pulled in as libraries for codegen paths, imports, and optional integrations.

### Version ranges

- Versions are specified as **compatible lower bounds** (e.g. `fast-mvc>=1.4.0`) so patch/minor updates can flow to users via `pip install -U`.
- **Pinning** exact versions is a **consumer choice**: use `pip-tools`, **uv** lockfiles, or `requirements.txt` with `==` in **your** application or deployment repo—not necessarily in this package’s `pyproject.toml`, which would block security patches for downstream users.

### Trust boundaries

| Trust | Scope |
|-------|--------|
| **This repo** | Source code, CI workflows, Hatch build metadata |
| **PyPI** | Wheels/sdists we publish and dependencies we install from PyPI |
| **Upstream `fast-*`** | Behavior and security of those packages; review their changelogs when bumping lower bounds |

For high-assurance environments, **verify hashes** (`pip hash` / lockfile digests) and run **private index mirrors** if policy requires.

## Development tools

Dev-only tools (**pytest**, **ruff**, **mypy**, etc.) are in `[project.optional-dependencies] dev`. They are not installed for end users installing `fastmvc-cli` from PyPI unless they opt into extras.

## GitHub Actions

Workflows use **versioned** actions (`@v4`, `@v5`, `@release/v1`). [Dependabot](.github/dependabot.yml) can propose updates. For stricter supply-chain control, your org may pin actions to full commit SHAs (see [SECURITY.md](../SECURITY.md)).
