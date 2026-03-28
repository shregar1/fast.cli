"""Documentation generation and deploy commands.

``docs generate`` walks the on-disk ``apis/`` and ``dtos/`` trees and emits
Markdown files with `mkdocstrings <https://mkdocstrings.github.io/>`_-style
``:::`` directives so a separate MkDocs build can render API reference pages.

``docs deploy`` is a thin wrapper around ``mkdocs gh-deploy`` and assumes the
user has MkDocs configured (``mkdocs.yml``) and appropriate Git remotes.

See Also
--------
fast_cli.commands.project_root.resolve_fastmvc_project_root : Chooses project root.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import click

from fast_cli.commands.project_root import resolve_fastmvc_project_root
from fast_cli.output import output


class MkdocsStyleReferenceGenerator:
    """Build Markdown stubs for mkdocstrings from the project tree.

    The generator writes (when applicable):

    * ``docs/api/endpoints.md`` — sections per API version and resource.
    * ``docs/api/dtos.md`` — request/response DTO modules.
    * ``docs/api/ecosystem.md`` — sibling ``fast_*`` packages next to the project.

    It does **not** invoke MkDocs; it only prepares content for a later build.
    """

    def __init__(self, target_path: Path) -> None:
        """``target_path`` is the resolved FastMVC project root (see ``resolve_*``)."""
        self._root = target_path

    def run(self) -> None:
        """Generate all documentation fragments and print success."""
        api_doc_path = self._root / "docs" / "api" / "endpoints.md"
        dto_doc_path = self._root / "docs" / "api" / "dtos.md"
        api_doc_path.parent.mkdir(parents=True, exist_ok=True)

        output.console.print("\n[bold cyan]📚 Generating Documentation:[/bold cyan]\n")

        self._write_api_endpoints(api_doc_path)
        self._write_dto_reference(dto_doc_path)
        self._write_ecosystem()

        output.print_success("Comprehensive Ecosystem Documentation generated!")

    def _write_api_endpoints(self, api_doc_path: Path) -> None:
        """Emit ``endpoints.md`` from ``apis/<v>/<resource>/*.py``."""
        api_content = (
            "# 🛰️ API Reference\n\nAutomated reference for all API endpoints.\n\n"
        )
        api_dir = self._root / "apis"
        if api_dir.exists():
            versions = sorted(
                [d.name for d in api_dir.iterdir() if d.is_dir() and d.name.startswith("v")]
            )
            for version in versions:
                api_content += f"## 📦 {version.upper()}\n\n"
                version_dir = api_dir / version
                for resource in sorted(
                    [
                        d.name
                        for d in version_dir.iterdir()
                        if d.is_dir() and d.name != "__pycache__"
                    ]
                ):
                    api_content += f"### 📂 {resource.capitalize()}\n"
                    resource_dir = version_dir / resource
                    for ep in sorted(resource_dir.glob("*.py")):
                        if ep.name == "__init__.py":
                            continue
                        api_content += f"#### 🚀 {ep.stem.capitalize()}\n"
                        api_content += f"::: apis.{version}.{resource}.{ep.stem}\n\n"
            api_doc_path.write_text(api_content)
            output.console.print(
                f"  [green]✓[/green] Generated API Endpoints: [dim]{api_doc_path.name}[/dim]"
            )

    def _write_dto_reference(self, dto_doc_path: Path) -> None:
        """Emit ``dtos.md`` from ``dtos/{requests,responses}/apis/...``."""
        dto_content = (
            "# 📦 Data Transfer Objects (DTOs)\n\n"
            "Automated reference for request and response models.\n\n"
        )
        dto_dir = self._root / "dtos"
        if dto_dir.exists():
            for category in ["requests", "responses"]:
                cat_dir = dto_dir / category / "apis"
                if not cat_dir.exists():
                    continue
                dto_content += f"## 📥 {category.capitalize()}\n\n"
                versions = sorted([d.name for d in cat_dir.iterdir() if d.is_dir()])
                for version in versions:
                    dto_content += f"### {version.upper()}\n"
                    version_dir = cat_dir / version
                    for resource in sorted(
                        [
                            d.name
                            for d in version_dir.iterdir()
                            if d.is_dir() and d.name != "__pycache__"
                        ]
                    ):
                        dto_content += f"#### 📂 {resource.capitalize()}\n"
                        for dto_file in sorted((version_dir / resource).glob("*.py")):
                            if dto_file.name == "__init__.py":
                                continue
                            dto_content += (
                                f"::: dtos.{category}.apis.{version}.{resource}."
                                f"{dto_file.stem}\n\n"
                            )
            dto_doc_path.write_text(dto_content)
            output.console.print(
                f"  [green]✓[/green] Generated DTO Reference: [dim]{dto_doc_path.name}[/dim]"
            )

    def _write_ecosystem(self) -> None:
        """Emit ``ecosystem.md`` for sibling ``fast_*`` repos (optional)."""
        ecosystem_doc_path = self._root / "docs" / "api" / "ecosystem.md"
        ecosystem_content = (
            "# 🌐 Ecosystem API Reference\n\n"
            "Automated reference for all packages in the FastMVC ecosystem.\n\n"
        )
        parent_dir = self._root.parent
        ecosystem_packages = sorted(
            [
                d.name
                for d in parent_dir.iterdir()
                if d.is_dir() and d.name.startswith("fast_") and d.name != "fast_mvc"
            ]
        )
        if not ecosystem_packages:
            return
        for pkg in ecosystem_packages:
            ecosystem_content += f"## 🔗 {pkg.replace('_', '-').title()}\n"
            src_dir = parent_dir / pkg / "src"
            search_dir = src_dir if src_dir.exists() else parent_dir / pkg
            for item in sorted(search_dir.iterdir()):
                if (
                    item.name.startswith(".")
                    or item.name == "__pycache__"
                    or item.name == "tests"
                    or item.name == "examples"
                ):
                    continue
                if item.is_dir() or (
                    item.suffix == ".py" and item.name != "__init__.py"
                ):
                    mod_name = item.stem
                    if src_dir.exists():
                        ecosystem_content += f"#### 📦 {mod_name}\n::: {mod_name}\n\n"
                    else:
                        ecosystem_content += f"#### 📦 {mod_name}\n::: {mod_name}\n\n"
        ecosystem_doc_path.write_text(ecosystem_content)
        output.console.print(
            f"  [green]✓[/green] Generated Ecosystem Reference: [dim]{ecosystem_doc_path.name}[/dim]"
        )


@click.group(name="docs")
def docs_group() -> None:
    """📚 Manage application documentation."""
    pass


@docs_group.command(name="generate")
def generate_docs() -> None:
    """📖 Generate API Reference documentation."""
    output.print_banner()
    target_path = resolve_fastmvc_project_root(Path.cwd())
    MkdocsStyleReferenceGenerator(target_path).run()


@docs_group.command(name="deploy")
@click.option(
    "--message", "-m", default="Deploy documentation", help="Deployment commit message"
)
def deploy_docs(message: str) -> None:
    """🚀 Deploy documentation to GitHub Pages."""
    output.print_banner()
    output.console.print("\n[bold cyan]🚀 Deploying to GitHub Pages:[/bold cyan]\n")
    try:
        subprocess.run(["mkdocs", "gh-deploy", "--message", message], check=True)
        output.print_success("Documentation deployed successfully to GitHub Pages!")
    except Exception as e:
        output.print_error(f"Failed to deploy: {e}")
        output.console.print(
            "[dim]Hint: Ensure you have 'gh-pages' branch set up or write access to the repo.[/dim]"
        )
