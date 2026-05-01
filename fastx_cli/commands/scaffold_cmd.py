"""Scaffold commands: generate a complete CRUD API stack from a YAML/JSON spec.

``fastx scaffold api spec.yaml`` reads model definitions (fields, types,
operations) and emits a full set of files: SQLAlchemy models, repositories,
services, FastAPI routers, request/response DTOs, and test stubs.

The generated layout follows the standard FastX directory conventions so files
can be dropped straight into an existing project.
"""

from __future__ import annotations

import json
import os
import sys
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import click

# Optional YAML support -------------------------------------------------
try:
    import yaml  # type: ignore[import-untyped]

    HAS_YAML = True
except ImportError:  # pragma: no cover
    HAS_YAML = False

# -----------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------

VALID_OPERATIONS: Set[str] = {"create", "read", "update", "delete", "list"}

TYPE_MAP: Dict[str, str] = {
    "string": "String",
    "text": "Text",
    "integer": "Integer",
    "float": "Float",
    "boolean": "Boolean",
    "uuid": "UUID",
    "datetime": "DateTime",
    "date": "Date",
    "json": "JSON",
}

# Pydantic equivalents for DTOs
PYDANTIC_TYPE_MAP: Dict[str, str] = {
    "string": "str",
    "text": "str",
    "integer": "int",
    "float": "float",
    "boolean": "bool",
    "uuid": "UUID",
    "datetime": "datetime",
    "date": "date",
    "json": "Any",
}

# -----------------------------------------------------------------------
# Spec parsing
# -----------------------------------------------------------------------


def _load_spec(spec_path: Path) -> Dict[str, Any]:
    """Load a YAML or JSON spec file and return the parsed dict."""
    raw = spec_path.read_text(encoding="utf-8")
    ext = spec_path.suffix.lower()

    if ext in (".yaml", ".yml"):
        if not HAS_YAML:
            raise click.ClickException(
                "PyYAML is required to parse YAML specs. "
                "Install it with: pip install pyyaml"
            )
        return yaml.safe_load(raw)  # type: ignore[no-any-return]

    if ext == ".json":
        return json.loads(raw)  # type: ignore[no-any-return]

    # Try YAML first, then JSON
    if HAS_YAML:
        try:
            return yaml.safe_load(raw)  # type: ignore[no-any-return]
        except Exception:
            pass
    try:
        return json.loads(raw)  # type: ignore[no-any-return]
    except Exception:
        pass

    raise click.ClickException(
        f"Unable to parse {spec_path}. Provide a valid YAML or JSON file."
    )


def _validate_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Basic validation of a parsed spec dict.  Returns the models dict."""
    if not isinstance(spec, dict) or "models" not in spec:
        raise click.ClickException("Spec must contain a top-level 'models' key.")

    models = spec["models"]
    if not isinstance(models, dict) or not models:
        raise click.ClickException("'models' must be a non-empty mapping.")

    for model_name, model_def in models.items():
        if not isinstance(model_def, dict):
            raise click.ClickException(f"Model '{model_name}' must be a mapping.")
        if "fields" not in model_def or not model_def["fields"]:
            raise click.ClickException(
                f"Model '{model_name}' must have a non-empty 'fields' mapping."
            )
        ops = model_def.get("operations", list(VALID_OPERATIONS))
        if isinstance(ops, list):
            for op in ops:
                if op not in VALID_OPERATIONS:
                    raise click.ClickException(
                        f"Model '{model_name}': unknown operation '{op}'. "
                        f"Valid operations: {', '.join(sorted(VALID_OPERATIONS))}"
                    )
            model_def["operations"] = ops
        else:
            raise click.ClickException(
                f"Model '{model_name}': 'operations' must be a list."
            )

    return models


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------


def _snake(name: str) -> str:
    """Convert PascalCase to snake_case."""
    out: list[str] = []
    for i, ch in enumerate(name):
        if ch.isupper() and i > 0:
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


def _needs_uuid_import(fields: Dict[str, Any]) -> bool:
    for fdef in fields.values():
        ftype = fdef if isinstance(fdef, str) else fdef.get("type", "string")
        if ftype == "uuid":
            return True
    return False


def _needs_datetime_import(fields: Dict[str, Any]) -> bool:
    for fdef in fields.values():
        ftype = fdef if isinstance(fdef, str) else fdef.get("type", "string")
        if ftype in ("datetime", "date"):
            return True
    return False


# -----------------------------------------------------------------------
# Code generators
# -----------------------------------------------------------------------


def _gen_model(model_name: str, fields: Dict[str, Any]) -> str:
    """Generate a SQLAlchemy model file."""
    snake_name = _snake(model_name)
    table_name = snake_name + "s"

    # Collect SA column type names
    sa_types: set[str] = set()
    for fdef in fields.values():
        ftype = fdef if isinstance(fdef, str) else fdef.get("type", "string")
        sa_types.add(TYPE_MAP.get(ftype, "String"))

    sa_imports = ", ".join(sorted(sa_types | {"Column"}))

    lines: list[str] = [
        '"""SQLAlchemy model for {model}."""'.format(model=model_name),
        "",
        "from __future__ import annotations",
        "",
        f"from sqlalchemy import {sa_imports}",
        "from sqlalchemy.orm import Mapped, mapped_column",
    ]

    if _needs_uuid_import(fields):
        lines.append("from sqlalchemy.dialects.postgresql import UUID as PG_UUID")
        lines.append("import uuid")

    has_fk = any(
        (isinstance(fdef, dict) and "foreign_key" in fdef) for fdef in fields.values()
    )
    if has_fk:
        lines.append("from sqlalchemy import ForeignKey")

    lines += [
        "",
        "from app.models.base import Base",
        "",
        "",
        f"class {model_name}(Base):",
        f'    __tablename__ = "{table_name}"',
        "",
    ]

    for fname, fdef in fields.items():
        if isinstance(fdef, str):
            fdef = {"type": fdef}

        ftype = fdef.get("type", "string")
        sa_type = TYPE_MAP.get(ftype, "String")

        col_args: list[str] = []

        # Type with parameters
        if sa_type == "String":
            max_len = fdef.get("max_length", 255)
            col_args.append(f"String({max_len})")
        elif sa_type == "UUID":
            col_args.append("PG_UUID(as_uuid=True)")
        else:
            col_args.append(sa_type)

        # Foreign key
        if "foreign_key" in fdef:
            col_args.append(f'ForeignKey("{fdef["foreign_key"]}")')

        col_kwargs: list[str] = []
        if fdef.get("required") is False:
            col_kwargs.append("nullable=True")
        elif fdef.get("required") is True:
            col_kwargs.append("nullable=False")
        if "default" in fdef:
            default_val = fdef["default"]
            if isinstance(default_val, bool):
                col_kwargs.append(f"default={default_val}")
            elif isinstance(default_val, str):
                col_kwargs.append(f'default="{default_val}"')
            else:
                col_kwargs.append(f"default={default_val}")

        args_str = ", ".join(col_args + col_kwargs)
        lines.append(f"    {fname}: Mapped = mapped_column({args_str})")

    lines.append("")
    return "\n".join(lines)


def _gen_repository(model_name: str, op: str) -> str:
    """Generate a repository file for a single operation."""
    snake = _snake(model_name)
    lines = [
        f'"""Repository layer: {op} operation for {model_name}."""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import Any, Optional",
        "",
        "from sqlalchemy.ext.asyncio import AsyncSession",
        "",
        f"from app.models.{snake} import {model_name}",
        "",
        "",
    ]

    if op == "create":
        lines += [
            f"async def create_{snake}(session: AsyncSession, data: dict[str, Any]) -> {model_name}:",
            f'    """Persist a new {model_name} row."""',
            f"    instance = {model_name}(**data)",
            "    session.add(instance)",
            "    await session.flush()",
            "    return instance",
        ]
    elif op == "read":
        lines += [
            f"async def get_{snake}(session: AsyncSession, pk: Any) -> Optional[{model_name}]:",
            f'    """Fetch a single {model_name} by primary key."""',
            f"    return await session.get({model_name}, pk)",
        ]
    elif op == "update":
        lines += [
            f"async def update_{snake}(",
            "    session: AsyncSession, pk: Any, data: dict[str, Any]",
            f") -> Optional[{model_name}]:",
            f'    """Update an existing {model_name} row."""',
            f"    instance = await session.get({model_name}, pk)",
            "    if instance is None:",
            "        return None",
            "    for key, value in data.items():",
            "        setattr(instance, key, value)",
            "    await session.flush()",
            "    return instance",
        ]
    elif op == "delete":
        lines += [
            f"async def delete_{snake}(session: AsyncSession, pk: Any) -> bool:",
            f'    """Delete a {model_name} row by primary key."""',
            f"    instance = await session.get({model_name}, pk)",
            "    if instance is None:",
            "        return False",
            "    await session.delete(instance)",
            "    await session.flush()",
            "    return True",
        ]
    elif op == "list":
        lines += [
            "from sqlalchemy import select",
            "",
            f"async def list_{snake}s(",
            "    session: AsyncSession,",
            "    skip: int = 0,",
            "    limit: int = 100,",
            f") -> list[{model_name}]:",
            f'    """Return a paginated list of {model_name} rows."""',
            f"    stmt = select({model_name}).offset(skip).limit(limit)",
            "    result = await session.execute(stmt)",
            "    return list(result.scalars().all())",
        ]

    lines.append("")
    return "\n".join(lines)


def _gen_service(model_name: str, op: str) -> str:
    """Generate a service layer file for a single operation."""
    snake = _snake(model_name)
    lines = [
        f'"""Service layer: {op} operation for {model_name}."""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import Any, Optional",
        "",
        "from sqlalchemy.ext.asyncio import AsyncSession",
        "",
        f"from app.models.{snake} import {model_name}",
        f"from app.repositories.{snake}.{op} import ",
    ]

    # Build import and function
    if op == "create":
        lines[-1] += f"create_{snake}"
        lines += [
            "",
            "",
            f"async def create_{snake}_service(",
            "    session: AsyncSession, data: dict[str, Any]",
            f") -> {model_name}:",
            f'    """Create a new {model_name}."""',
            f"    return await create_{snake}(session, data)",
        ]
    elif op == "read":
        lines[-1] += f"get_{snake}"
        lines += [
            "",
            "",
            f"async def get_{snake}_service(",
            "    session: AsyncSession, pk: Any",
            f") -> Optional[{model_name}]:",
            f'    """Retrieve a {model_name} by primary key."""',
            f"    return await get_{snake}(session, pk)",
        ]
    elif op == "update":
        lines[-1] += f"update_{snake}"
        lines += [
            "",
            "",
            f"async def update_{snake}_service(",
            "    session: AsyncSession, pk: Any, data: dict[str, Any]",
            f") -> Optional[{model_name}]:",
            f'    """Update a {model_name}."""',
            f"    return await update_{snake}(session, pk, data)",
        ]
    elif op == "delete":
        lines[-1] += f"delete_{snake}"
        lines += [
            "",
            "",
            f"async def delete_{snake}_service(",
            "    session: AsyncSession, pk: Any",
            ") -> bool:",
            f'    """Delete a {model_name}."""',
            f"    return await delete_{snake}(session, pk)",
        ]
    elif op == "list":
        lines[-1] += f"list_{snake}s"
        lines += [
            "",
            "",
            f"async def list_{snake}s_service(",
            "    session: AsyncSession,",
            "    skip: int = 0,",
            "    limit: int = 100,",
            f") -> list[{model_name}]:",
            f'    """List {model_name} records with pagination."""',
            f"    return await list_{snake}s(session, skip=skip, limit=limit)",
        ]

    lines.append("")
    return "\n".join(lines)


def _gen_request_dto(
    model_name: str, op: str, fields: Dict[str, Any], version: str
) -> str:
    """Generate a Pydantic request DTO."""
    snake = _snake(model_name)
    imports: set[str] = set()
    field_lines: list[str] = []

    for fname, fdef in fields.items():
        if isinstance(fdef, str):
            fdef = {"type": fdef}
        ftype = fdef.get("type", "string")
        py_type = PYDANTIC_TYPE_MAP.get(ftype, "str")

        if py_type == "UUID":
            imports.add("from uuid import UUID")
        if py_type == "datetime":
            imports.add("from datetime import datetime")
        if py_type == "date":
            imports.add("from datetime import date")
        if py_type == "Any":
            imports.add("from typing import Any")

        required = fdef.get("required", True)
        if op in ("update",):
            # All fields optional for update
            imports.add("from typing import Optional")
            field_lines.append(f"    {fname}: Optional[{py_type}] = None")
        elif not required:
            imports.add("from typing import Optional")
            default = fdef.get("default")
            if default is not None:
                field_lines.append(f"    {fname}: Optional[{py_type}] = {default!r}")
            else:
                field_lines.append(f"    {fname}: Optional[{py_type}] = None")
        else:
            field_lines.append(f"    {fname}: {py_type}")

    lines = [
        f'"""Request DTO: {op} for {model_name} ({version})."""',
        "",
        "from __future__ import annotations",
        "",
        "from pydantic import BaseModel",
    ]
    lines += sorted(imports)
    lines += [
        "",
        "",
    ]

    if op == "create":
        lines.append(f"class {model_name}CreateRequest(BaseModel):")
        lines += field_lines
    elif op == "update":
        lines.append(f"class {model_name}UpdateRequest(BaseModel):")
        lines += field_lines
    elif op == "read":
        lines.append(f"class {model_name}ReadRequest(BaseModel):")
        lines.append("    id: str")
    elif op == "delete":
        lines.append(f"class {model_name}DeleteRequest(BaseModel):")
        lines.append("    id: str")
    elif op == "list":
        lines.append(f"class {model_name}ListRequest(BaseModel):")
        lines.append("    skip: int = 0")
        lines.append("    limit: int = 100")

    if not field_lines and op in ("create", "update"):
        lines.append("    pass")

    lines.append("")
    return "\n".join(lines)


def _gen_response_dto(
    model_name: str, op: str, fields: Dict[str, Any], version: str
) -> str:
    """Generate a Pydantic response DTO."""
    snake = _snake(model_name)
    imports: set[str] = set()
    field_lines: list[str] = []

    for fname, fdef in fields.items():
        if isinstance(fdef, str):
            fdef = {"type": fdef}
        ftype = fdef.get("type", "string")
        py_type = PYDANTIC_TYPE_MAP.get(ftype, "str")

        if py_type == "UUID":
            imports.add("from uuid import UUID")
        if py_type == "datetime":
            imports.add("from datetime import datetime")
        if py_type == "date":
            imports.add("from datetime import date")
        if py_type == "Any":
            imports.add("from typing import Any")

        imports.add("from typing import Optional")
        field_lines.append(f"    {fname}: Optional[{py_type}] = None")

    lines = [
        f'"""Response DTO: {op} for {model_name} ({version})."""',
        "",
        "from __future__ import annotations",
        "",
        "from pydantic import BaseModel, ConfigDict",
    ]
    lines += sorted(imports)
    lines += ["", ""]

    if op == "list":
        lines.append(f"class {model_name}Response(BaseModel):")
        lines.append('    model_config = ConfigDict(from_attributes=True)')
        lines += field_lines
        lines += [
            "",
            "",
            f"class {model_name}ListResponse(BaseModel):",
            f"    items: list[{model_name}Response]",
            "    total: int = 0",
        ]
    elif op == "delete":
        lines.append(f"class {model_name}DeleteResponse(BaseModel):")
        lines.append("    success: bool")
        lines.append("    message: str = ''")
    else:
        suffix = op.capitalize()
        lines.append(f"class {model_name}{suffix}Response(BaseModel):")
        lines.append('    model_config = ConfigDict(from_attributes=True)')
        lines += field_lines

    lines.append("")
    return "\n".join(lines)


def _gen_api_route(
    model_name: str, op: str, fields: Dict[str, Any], version: str
) -> str:
    """Generate a FastAPI router file for a single operation."""
    snake = _snake(model_name)

    lines = [
        f'"""API route: {op} for {model_name} ({version})."""',
        "",
        "from __future__ import annotations",
        "",
        "from fastapi import APIRouter, Depends, HTTPException",
        "from sqlalchemy.ext.asyncio import AsyncSession",
        "",
        "from app.deps import get_session",
        f"from app.services.{snake}.{op} import ",
    ]

    if op == "create":
        lines[-1] += f"create_{snake}_service"
        lines += [
            f"from app.dtos.requests.apis.{version}.{snake}.{op} import {model_name}CreateRequest",
            f"from app.dtos.responses.apis.{version}.{snake}.{op} import {model_name}CreateResponse",
            "",
            f'router = APIRouter(prefix="/{snake}s", tags=["{model_name}"])',
            "",
            "",
            f'@router.post("/", response_model={model_name}CreateResponse)',
            f"async def create_{snake}_endpoint(",
            f"    body: {model_name}CreateRequest,",
            "    session: AsyncSession = Depends(get_session),",
            f") -> {model_name}CreateResponse:",
            f'    """Create a new {model_name}."""',
            f"    result = await create_{snake}_service(session, body.model_dump())",
            f"    return {model_name}CreateResponse.model_validate(result)",
        ]
    elif op == "read":
        lines[-1] += f"get_{snake}_service"
        lines += [
            f"from app.dtos.responses.apis.{version}.{snake}.{op} import {model_name}ReadResponse",
            "",
            f'router = APIRouter(prefix="/{snake}s", tags=["{model_name}"])',
            "",
            "",
            f'@router.get("/{{pk}}", response_model={model_name}ReadResponse)',
            f"async def get_{snake}_endpoint(",
            "    pk: str,",
            "    session: AsyncSession = Depends(get_session),",
            f") -> {model_name}ReadResponse:",
            f'    """Get a {model_name} by ID."""',
            f"    result = await get_{snake}_service(session, pk)",
            "    if result is None:",
            f'        raise HTTPException(status_code=404, detail="{model_name} not found")',
            f"    return {model_name}ReadResponse.model_validate(result)",
        ]
    elif op == "update":
        lines[-1] += f"update_{snake}_service"
        lines += [
            f"from app.dtos.requests.apis.{version}.{snake}.{op} import {model_name}UpdateRequest",
            f"from app.dtos.responses.apis.{version}.{snake}.{op} import {model_name}UpdateResponse",
            "",
            f'router = APIRouter(prefix="/{snake}s", tags=["{model_name}"])',
            "",
            "",
            f'@router.patch("/{{pk}}", response_model={model_name}UpdateResponse)',
            f"async def update_{snake}_endpoint(",
            "    pk: str,",
            f"    body: {model_name}UpdateRequest,",
            "    session: AsyncSession = Depends(get_session),",
            f") -> {model_name}UpdateResponse:",
            f'    """Update a {model_name}."""',
            f"    result = await update_{snake}_service(",
            "        session, pk, body.model_dump(exclude_unset=True)",
            "    )",
            "    if result is None:",
            f'        raise HTTPException(status_code=404, detail="{model_name} not found")',
            f"    return {model_name}UpdateResponse.model_validate(result)",
        ]
    elif op == "delete":
        lines[-1] += f"delete_{snake}_service"
        lines += [
            f"from app.dtos.responses.apis.{version}.{snake}.{op} import {model_name}DeleteResponse",
            "",
            f'router = APIRouter(prefix="/{snake}s", tags=["{model_name}"])',
            "",
            "",
            f'@router.delete("/{{pk}}", response_model={model_name}DeleteResponse)',
            f"async def delete_{snake}_endpoint(",
            "    pk: str,",
            "    session: AsyncSession = Depends(get_session),",
            f") -> {model_name}DeleteResponse:",
            f'    """Delete a {model_name}."""',
            f"    deleted = await delete_{snake}_service(session, pk)",
            "    if not deleted:",
            f'        raise HTTPException(status_code=404, detail="{model_name} not found")',
            f'    return {model_name}DeleteResponse(success=True, message="{model_name} deleted")',
        ]
    elif op == "list":
        lines[-1] += f"list_{snake}s_service"
        lines += [
            f"from app.dtos.responses.apis.{version}.{snake}.{op} import (",
            f"    {model_name}ListResponse,",
            f"    {model_name}Response,",
            ")",
            "",
            f'router = APIRouter(prefix="/{snake}s", tags=["{model_name}"])',
            "",
            "",
            f'@router.get("/", response_model={model_name}ListResponse)',
            f"async def list_{snake}s_endpoint(",
            "    skip: int = 0,",
            "    limit: int = 100,",
            "    session: AsyncSession = Depends(get_session),",
            f") -> {model_name}ListResponse:",
            f'    """List {model_name} records."""',
            f"    results = await list_{snake}s_service(session, skip=skip, limit=limit)",
            f"    return {model_name}ListResponse(",
            f"        items=[{model_name}Response.model_validate(r) for r in results],",
            "        total=len(results),",
            "    )",
        ]

    lines.append("")
    return "\n".join(lines)


def _gen_test(model_name: str, op: str, version: str) -> str:
    """Generate a test stub for a single operation."""
    snake = _snake(model_name)
    lines = [
        f'"""Tests for {model_name} {op} operation."""',
        "",
        "from __future__ import annotations",
        "",
        "import pytest",
        "from httpx import AsyncClient",
        "",
        "",
    ]

    if op == "create":
        lines += [
            "@pytest.mark.asyncio",
            f"async def test_create_{snake}(client: AsyncClient) -> None:",
            f'    """Test creating a new {model_name}."""',
            f'    response = await client.post("/{version}/{snake}s/", json={{}})',
            "    assert response.status_code in (200, 201)",
            "    data = response.json()",
            "    assert data is not None",
        ]
    elif op == "read":
        lines += [
            "@pytest.mark.asyncio",
            f"async def test_get_{snake}(client: AsyncClient) -> None:",
            f'    """Test reading a {model_name} by ID."""',
            f'    response = await client.get("/{version}/{snake}s/test-id")',
            "    assert response.status_code in (200, 404)",
        ]
    elif op == "update":
        lines += [
            "@pytest.mark.asyncio",
            f"async def test_update_{snake}(client: AsyncClient) -> None:",
            f'    """Test updating a {model_name}."""',
            f'    response = await client.patch("/{version}/{snake}s/test-id", json={{}})',
            "    assert response.status_code in (200, 404)",
        ]
    elif op == "delete":
        lines += [
            "@pytest.mark.asyncio",
            f"async def test_delete_{snake}(client: AsyncClient) -> None:",
            f'    """Test deleting a {model_name}."""',
            f'    response = await client.delete("/{version}/{snake}s/test-id")',
            "    assert response.status_code in (200, 404)",
        ]
    elif op == "list":
        lines += [
            "@pytest.mark.asyncio",
            f"async def test_list_{snake}s(client: AsyncClient) -> None:",
            f'    """Test listing {model_name} records."""',
            f'    response = await client.get("/{version}/{snake}s/")',
            "    assert response.status_code == 200",
            '    data = response.json()',
            '    assert "items" in data',
        ]

    lines.append("")
    return "\n".join(lines)


# -----------------------------------------------------------------------
# File-plan builder
# -----------------------------------------------------------------------


def _build_file_plan(
    models: Dict[str, Any], output_dir: str, version: str
) -> List[Tuple[Path, str]]:
    """Return a list of ``(path, content)`` tuples for every file to generate."""
    base = Path(output_dir)
    plan: list[tuple[Path, str]] = []

    for model_name, model_def in models.items():
        fields: Dict[str, Any] = model_def["fields"]
        operations: list[str] = model_def["operations"]
        snake = _snake(model_name)

        # Model
        plan.append(
            (base / "models" / f"{snake}.py", _gen_model(model_name, fields))
        )

        for op in operations:
            # Repository
            plan.append(
                (
                    base / "repositories" / snake / f"{op}.py",
                    _gen_repository(model_name, op),
                )
            )
            # Service
            plan.append(
                (
                    base / "services" / snake / f"{op}.py",
                    _gen_service(model_name, op),
                )
            )
            # API route
            plan.append(
                (
                    base / "apis" / version / snake / f"{op}.py",
                    _gen_api_route(model_name, op, fields, version),
                )
            )
            # Request DTO
            plan.append(
                (
                    base / "dtos" / "requests" / "apis" / version / snake / f"{op}.py",
                    _gen_request_dto(model_name, op, fields, version),
                )
            )
            # Response DTO
            plan.append(
                (
                    base / "dtos" / "responses" / "apis" / version / snake / f"{op}.py",
                    _gen_response_dto(model_name, op, fields, version),
                )
            )
            # Test
            plan.append(
                (
                    base / "tests" / snake / f"test_{op}.py",
                    _gen_test(model_name, op, version),
                )
            )

    return plan


def _ensure_init_files(plan: List[Tuple[Path, str]]) -> List[Tuple[Path, str]]:
    """Add ``__init__.py`` files in every generated directory."""
    dirs: set[Path] = set()
    for path, _ in plan:
        parent = path.parent
        while parent != parent.parent:
            dirs.add(parent)
            parent = parent.parent

    init_additions: list[tuple[Path, str]] = []
    for d in sorted(dirs):
        init = d / "__init__.py"
        if not init.exists() and init not in {p for p, _ in plan}:
            init_additions.append((init, ""))

    return plan + init_additions


# -----------------------------------------------------------------------
# Click commands
# -----------------------------------------------------------------------


@click.group("scaffold")
def scaffold_group() -> None:
    """Scaffold a full CRUD stack from a spec file.

    Generate models, repositories, services, API routes, DTOs, and tests
    from a YAML or JSON specification.
    """
    pass


@scaffold_group.command("api")
@click.argument("spec_file", type=click.Path(exists=True))
@click.option(
    "--output-dir",
    "-o",
    default=".",
    type=click.Path(),
    help="Output directory (default: current directory).",
)
@click.option(
    "--version",
    "-v",
    default="v1",
    help="API version prefix (default: v1).",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing files without prompting.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Show what would be generated without writing files.",
)
def scaffold_api_cmd(
    spec_file: str,
    output_dir: str,
    version: str,
    force: bool,
    dry_run: bool,
) -> None:
    """Generate a complete CRUD API stack from a YAML/JSON spec.

    SPEC_FILE is the path to a YAML or JSON specification that defines
    models, their fields, and desired CRUD operations.

    \b
    Example:
        fastx scaffold api spec.yaml
        fastx scaffold api spec.json -o src/ -v v2 --force
        fastx scaffold api spec.yaml --dry-run
    """
    spec_path = Path(spec_file)
    spec = _load_spec(spec_path)
    models = _validate_spec(spec)

    plan = _build_file_plan(models, output_dir, version)
    plan = _ensure_init_files(plan)

    # Check for conflicts
    if not force and not dry_run:
        conflicts = [p for p, _ in plan if p.exists()]
        if conflicts:
            click.echo("The following files already exist:", err=True)
            for c in conflicts:
                click.echo(f"  - {c}", err=True)
            click.echo(
                "\nUse --force to overwrite or --dry-run to preview.", err=True
            )
            raise SystemExit(1)

    if dry_run:
        click.echo(f"Dry run: {len(plan)} file(s) would be generated:\n")
        for fpath, _ in sorted(plan, key=lambda t: str(t[0])):
            marker = " (exists)" if fpath.exists() else ""
            click.echo(f"  {fpath}{marker}")
        click.echo(f"\nModels: {', '.join(models.keys())}")
        for mname, mdef in models.items():
            click.echo(f"  {mname}: {', '.join(mdef['operations'])}")
        return

    # Write files
    written = 0
    for fpath, content in plan:
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(content, encoding="utf-8")
        written += 1

    click.echo(f"Generated {written} file(s) in {Path(output_dir).resolve()}")
    click.echo(f"Models: {', '.join(models.keys())}")
    for mname, mdef in models.items():
        click.echo(f"  {mname}: {', '.join(mdef['operations'])}")


# -----------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------


def register_scaffold(cli: click.Group) -> None:
    """Attach the ``scaffold`` group to the root CLI."""
    cli.add_command(scaffold_group)
