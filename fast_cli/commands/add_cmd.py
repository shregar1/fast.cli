"""``fast-cli add`` — scaffold resources inside an existing project.

The ``add resource`` command creates a **vertical slice** for one operation under
a versioned API: request/response DTOs, repository, service, dependency
provider, core controller, and FastAPI-facing API controller. File contents are
string templates (not Jinja) aligned with FastMVC conventions.

Requires a project layout where ``abstractions/controller.py`` exists under
:func:`fast_cli.commands.project_root.resolve_fastmvc_project_root`.
"""

from __future__ import annotations

from pathlib import Path

import click

from fast_cli.commands.project_root import resolve_fastmvc_project_root
from fast_cli.constants import FRAMEWORK_CONTROLLER_PATH
from fast_cli.output import output
from fast_cli.validators import HAS_QUESTIONARY

if HAS_QUESTIONARY:
    import questionary


@click.group(name="add")
def add_group() -> None:
    """➕ Add new components to your FastMVC project.

    Quickly scaffold new resources, services, or controllers with
    context-aware templates that follow framework standards.

    Examples:
        fast add resource --folder user --resource fetch
        fast add resource -f billing -r create

    Other ``add`` subcommands (middleware, auth, test) print guidance only;
    templates are not bundled in this package.

    """
    pass


class ResourceScaffolder:
    """Write DTOs, repository, service, dependency, and API layers for one operation.

    Parameters
    ----------
    folder, resource
        Lowercased segments for paths and import paths (e.g. ``user``, ``create``).
    api_version
        Normalized ``v1``-style segment used in ``apis/`` and ``dtos/`` trees.
    _crud
        Reserved for future template variants (currently unused).
    """

    def __init__(self, target_path: Path) -> None:
        """``target_path`` is the resolved project root containing ``apis/``, ``dtos/``, etc."""
        self._root = target_path

    def run(
        self,
        folder: str,
        resource: str,
        api_version: str,
        _crud: bool,
    ) -> None:
        """Generate all scaffold files and print success lines."""
        folder_name = folder.lower()
        resource_name = resource.lower()
        folder_camel = "".join(word.capitalize() for word in folder_name.split("_"))
        resource_camel = "".join(word.capitalize() for word in resource_name.split("_"))
        class_prefix = f"{resource_camel}{folder_camel}"

        fields: list[tuple[str, str]] = [("name", "str"), ("description", "str | None")]
        if HAS_QUESTIONARY and resource_name in ("create", "update", "post", "patch"):
            while questionary.confirm(
                f"Add a custom field to {resource_name} {folder_name} ({api_version})?",
                default=False,
            ).ask():
                f_name = questionary.text("Field name:").ask()
                f_type = questionary.select(
                    "Field type:",
                    choices=["str", "int", "float", "bool", "dict", "list"],
                    default="str",
                ).ask()
                if f_name:
                    fields.append((f_name, f_type))

        output.console.print(
            f"\n[bold cyan]🏗️  Scaffolding Operation:[/bold cyan] {resource_name} in {folder_name} ([bold]{api_version}[/bold])"
        )
        output.console.print(f"[dim]Class: {class_prefix}Controller[/dim]\n")

        create_dto_fields = "\n    ".join(
            [
                f"{n}: {t} = Field(..., description='{n.capitalize()}')"
                if "| None" not in t
                else f"{n}: {t} = Field(None, description='{n.capitalize()}')"
                for n, t in fields
            ]
        )

        self._write(
            self._root
            / "dtos"
            / "requests"
            / "apis"
            / api_version
            / folder_name
            / f"{resource_name}.py",
            f'''"""{class_prefix} {api_version.upper()} Request DTO."""
from pydantic import Field
from dtos.requests.abstraction import IRequestDTO

class {class_prefix}RequestDTO(IRequestDTO):
    """{class_prefix} request payload."""
    {create_dto_fields}
''',
            "Request DTO",
        )

        self._write(
            self._root
            / "dtos"
            / "responses"
            / "apis"
            / api_version
            / folder_name
            / f"{resource_name}.py",
            f'''"""{class_prefix} {api_version.upper()} Response DTO."""
from pydantic import IModel

class {class_prefix}ResponseDataDTO(IModel):
    """{class_prefix} response payload data."""
    id: str
    status: str = "active"
''',
            "Response DTO",
        )

        self._write(
            self._root / "repositories" / folder_name / f"{resource_name}.py",
            f'''"""{class_prefix} Repository."""
from typing import Any, Dict
from abstractions.repository import IRepository

class {class_prefix}Repository(IRepository):
    def create_record(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {{"id": "1", **data}}
''',
            "Repository",
        )

        self._write(
            self._root / "services" / folder_name / f"{resource_name}.py",
            f'''"""{class_prefix} Service."""
from abstractions.service import IService
from dtos.requests.apis.{api_version}.{folder_name}.{resource_name} import {class_prefix}RequestDTO
from repositories.{folder_name}.{resource_name} import {class_prefix}Repository

class {class_prefix}Service(IService):
    def __init__(self, repo: {class_prefix}Repository, **kwargs):
        super().__init__(**kwargs)
        self.repo = repo

    def run(self, request_dto: {class_prefix}RequestDTO) -> dict:
        self.logger.info("Executing {resource_name} service")
        return {{ "item": {{ "id": "1" }}, "message": "Success" }}
''',
            "Service",
        )

        self._write(
            self._root
            / "dependencies"
            / "services"
            / api_version
            / folder_name
            / f"{resource_name}.py",
            f'''"""{class_prefix} Dependencies."""
from fastapi import Request
from abstractions.dependency import IDependency
from services.{folder_name}.{resource_name} import {class_prefix}Service
from repositories.{folder_name}.{resource_name} import {class_prefix}Repository

class {class_prefix}ServiceDependency(IDependency):
    @staticmethod
    def derive(request: Request) -> {class_prefix}Service:
        repo = {class_prefix}Repository(urn=getattr(request.state, "urn", None))
        return {class_prefix}Service(repo=repo, urn=getattr(request.state, "urn", None))
''',
            "Dependency",
        )

        self._write(
            self._root / "controllers" / folder_name / f"{resource_name}.py",
            f'''"""{class_prefix} Core Controller."""
from abstractions.controller import IController
from services.{folder_name}.{resource_name} import {class_prefix}Service
from dtos.requests.apis.{api_version}.{folder_name}.{resource_name} import {class_prefix}RequestDTO
from dtos.responses.I import IResponseDTO
from constants.api_status import APIStatus

class {class_prefix}Controller(IController):
    async def handle(self, urn, payload, api_name) -> IResponseDTO:
        await self.validate_request(urn=urn, request_payload=payload, api_name=api_name)
        return IResponseDTO(status=APIStatus.SUCCESS, responseMessage="Flow check")
''',
            "Core Controller",
        )

        api_dir = self._root / "apis" / api_version / folder_name
        self._write(
            api_dir / f"{resource_name}.py",
            f'''"""{api_version.upper()} API {class_prefix} Controller."""
from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from apis.v1.abstraction import IV1APIController  # Reuse v1 abstraction if I is similar
from dependencies.services.{api_version}.{folder_name}.{resource_name} import {class_prefix}ServiceDependency
from services.{folder_name}.{resource_name} import {class_prefix}Service
from dtos.requests.apis.{api_version}.{folder_name}.{resource_name} import {class_prefix}RequestDTO
from dtos.responses.I import IResponseDTO
from constants.api_status import APIStatus

class {class_prefix}APIController(IV1APIController):
    async def execute(self, request: Request, payload: {class_prefix}RequestDTO, service: {class_prefix}Service = Depends({class_prefix}ServiceDependency.derive)) -> JSONResponse:
        async def _run():
            result = service.run(payload)
            return self._to_json_response(IResponseDTO(transactionUrn=request.state.urn, status=APIStatus.SUCCESS, data=result["item"]))
        return await self.invoke_with_exception_handling(request, _run)
''',
            f"API {api_version.upper()} Controller",
        )

        output.print_success(
            f"Operation '{resource_name}' scaffolded successfully in [bold]{api_version}[/bold] stack!"
        )
        output.print_success(
            f"Operation '{resource_name}' scaffolded successfully in folder '{folder_name}'!"
        )

    def _write(self, path: Path, content: str, label: str) -> None:
        """Create parent dirs, write ``content`` UTF-8, log a relative path line."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        output.console.print(
            f"  [green]✓[/green] Created {label}: [dim]{path.relative_to(self._root)}[/dim]"
        )


@add_group.command(name="resource")
@click.option("--folder", "-f", required=True, help="Folder name (e.g., user, auth)")
@click.option(
    "--resource",
    "-r",
    required=True,
    help="Resource/Operation name (e.g., fetch, create, delete)",
)
@click.option("--version", "-v", default="v1", help="API version (e.g., v1, v2)")
@click.option("--crud/--no-crud", default=True, help="Include standard CRUD methods")
def add_resource(folder: str, resource: str, version: str, crud: bool) -> None:
    """🏗️ Scaffold a new versioned resource operation (per-operation files)."""
    output.print_banner()
    api_version = version.lower()
    if not api_version.startswith("v"):
        api_version = f"v{api_version}"

    target_path = resolve_fastmvc_project_root()
    if not (target_path / FRAMEWORK_CONTROLLER_PATH).exists():
        output.print_error(
            f"Not in a FastMVC project (could not find abstractions/controller.py in {target_path})"
        )
        raise click.Abort()

    ResourceScaffolder(target_path).run(folder, resource, api_version, crud)


@add_group.command(name="middleware")
def add_middleware() -> None:
    """Middleware scaffolding (templates not bundled in fastmvc-cli)."""
    output.print_banner()
    output.print_warning(
        "Middleware scaffolding is not bundled in this package."
    )
    output.print_info(
        "Use the FastMVC (fast_mvc) framework repo as reference, or extend "
        "``middlewares/`` manually."
    )


@add_group.command(name="auth")
def add_auth() -> None:
    """JWT / auth stack scaffolding (templates not bundled in fastmvc-cli)."""
    output.print_banner()
    output.print_warning(
        "A full auth stack is not bundled in this package."
    )
    output.print_info(
        "Copy patterns from the FastMVC application template or implement auth "
        "in your ``services/`` and ``apis/`` layers."
    )


@add_group.command(name="test")
def add_test() -> None:
    """Async pytest scaffolding for a resource (templates not bundled)."""
    output.print_banner()
    output.print_warning(
        "Resource test scaffolding is not bundled in this package."
    )
    output.print_info(
        "Add tests under ``tests/`` following your FastMVC project conventions."
    )
