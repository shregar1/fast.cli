# Security policy

## Supported versions

We aim to fix security issues in the **latest minor release** on the default branch.

| Scope | Supported |
|--------|------------|
| **Python** | **3.10+** (see `requires-python` in `pyproject.toml`) |
| **fastmvc-cli** | Latest **1.x** release on PyPI |

Older releases may not receive backports unless we explicitly say otherwise.

## Dependency and supply-chain posture

- **Runtime dependencies** (`fast-*`, `click`, `rich`, …) are installed from **PyPI** (or your configured index). Version ranges are declared in `pyproject.toml`; see [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md) for trust boundaries and pinning guidance.
- **Builds** use **Hatch**; **wheels** are published via **GitHub Actions** and **PyPI trusted publishing (OIDC)**—no long-lived PyPI token stored in the repo (see [.github/workflows/publish-pypi.yml](.github/workflows/publish-pypi.yml)).
- **GitHub Actions** use tagged action versions; updates are proposed via **Dependabot** where configured.

## Reporting a vulnerability

**Please do not** open a public GitHub issue for undisclosed security bugs.

1. **Preferred:** Use [GitHub private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability) for this repository, if enabled by the maintainers.
2. **Otherwise:** Contact the maintainers privately (e.g. via the email on PyPI package metadata or the organization’s security contact).

Include:

- A short description of the issue and its impact
- Steps to reproduce (or a proof-of-concept)
- Affected versions / components, if known

### Response expectations

- **Acknowledgment:** We aim to acknowledge receipt within a few business days (not a legal SLA).
- **Triage:** We will assess severity and scope; we may ask follow-up questions.
- **Disclosure:** We coordinate a fix release and, when appropriate, a GitHub Security Advisory with credit for responsible disclosure.

## General bug reports

Non-security bugs and feature requests can use **GitHub Issues** in the normal way.
