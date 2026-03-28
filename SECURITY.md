# Security policy

## Supported versions

We aim to fix security issues in the **latest minor release** on the default branch.

| Scope | Supported |
|--------|------------|
| **Python** | **3.10+** (see `requires-python` in `pyproject.toml`) |
| **fastmvc-cli** | Latest **1.x** release on PyPI |

Older releases may not receive backports unless we explicitly say otherwise.

## Reporting a vulnerability

**Please do not** open a public GitHub issue for undisclosed security bugs.

1. **Preferred:** Use [GitHub private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability) for this repository, if enabled by the maintainers.
2. **Otherwise:** Contact the maintainers privately (e.g. via the email on PyPI package metadata or the organization’s security contact).

Include:

- A short description of the issue and its impact
- Steps to reproduce (or a proof-of-concept)
- Affected versions / components, if known

We will acknowledge receipt and work on a fix and disclosure timeline. Credit for responsible disclosure can be discussed when the issue is resolved.

## General bug reports

Non-security bugs and feature requests can use **GitHub Issues** in the normal way.
