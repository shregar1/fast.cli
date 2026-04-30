"""SDK client generator from OpenAPI spec."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import click

from fastx_cli.output import output


@click.group()
def sdk_group() -> None:
    """Generate typed client SDKs from your OpenAPI spec."""
    pass


@sdk_group.command(name="generate")
@click.option("--lang", "-l", type=click.Choice(["typescript", "python"]), default="typescript", help="Target language")
@click.option("--input", "-i", "input_path", type=click.Path(), default=None, help="Path to openapi.json (default: fetch from running server)")
@click.option("--url", "-u", default="http://localhost:8000/openapi.json", help="URL to fetch OpenAPI spec from")
@click.option("--output-dir", "-o", "output_dir", type=click.Path(), default="./sdk", help="Output directory")
@click.option("--name", "-n", default="api-client", help="Package/module name")
def generate(lang: str, input_path: str | None, url: str, output_dir: str, name: str) -> None:
    """Generate a typed client SDK from OpenAPI spec.

    \b
    Examples:
        fastx sdk generate                          # TypeScript from running server
        fastx sdk generate -l python                # Python client
        fastx sdk generate -i openapi.json -o ./client
        fastx sdk generate --url http://prod.api/openapi.json
    """
    # Load spec
    spec = _load_spec(input_path, url)
    if spec is None:
        return

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if lang == "typescript":
        _generate_typescript(spec, out, name)
    elif lang == "python":
        _generate_python(spec, out, name)

    output.console.print(f"\n[bold green]\u2713[/bold green] SDK generated at [bold]{out}[/bold]")


def _load_spec(input_path: str | None, url: str) -> dict[str, Any] | None:
    """Load OpenAPI spec from file or URL."""
    if input_path:
        p = Path(input_path)
        if not p.exists():
            output.console.print(f"[red]File not found: {input_path}[/red]")
            return None
        with open(p) as f:
            return json.load(f)

    output.console.print(f"[dim]Fetching spec from {url}...[/dim]")
    try:
        import urllib.request
        resp = urllib.request.urlopen(url, timeout=5)
        return json.loads(resp.read())
    except Exception as e:
        output.console.print(f"[red]Failed to fetch spec: {e}[/red]")
        output.console.print("[dim]Hint: start your server first, or use --input to point to a file[/dim]")
        return None


def _to_ts_type(schema: dict[str, Any], components: dict[str, Any]) -> str:
    """Convert OpenAPI schema to TypeScript type."""
    if "$ref" in schema:
        ref = schema["$ref"].split("/")[-1]
        return ref
    t = schema.get("type", "any")
    if t == "string":
        if schema.get("enum"):
            return " | ".join(f'"{v}"' for v in schema["enum"])
        return "string"
    if t == "integer" or t == "number":
        return "number"
    if t == "boolean":
        return "boolean"
    if t == "array":
        items = schema.get("items", {})
        return f"{_to_ts_type(items, components)}[]"
    if t == "object":
        return "Record<string, any>"
    return "any"


def _to_py_type(schema: dict[str, Any], components: dict[str, Any]) -> str:
    """Convert OpenAPI schema to Python type hint."""
    if "$ref" in schema:
        ref = schema["$ref"].split("/")[-1]
        return ref
    t = schema.get("type", "Any")
    if t == "string":
        if schema.get("enum"):
            return "str"
        return "str"
    if t == "integer":
        return "int"
    if t == "number":
        return "float"
    if t == "boolean":
        return "bool"
    if t == "array":
        items = schema.get("items", {})
        return f"list[{_to_py_type(items, components)}]"
    if t == "object":
        return "dict[str, Any]"
    return "Any"


def _slugify(text: str) -> str:
    """Convert operation ID or path to a valid function name."""
    s = re.sub(r"[^a-zA-Z0-9_]", "_", text)
    s = re.sub(r"_+", "_", s).strip("_")
    return s.lower()


def _generate_typescript(spec: dict[str, Any], out: Path, name: str) -> None:
    """Generate TypeScript SDK."""
    components = spec.get("components", {}).get("schemas", {})
    paths = spec.get("paths", {})
    info = spec.get("info", {})

    # Generate types.ts
    types_lines = [
        f"// Auto-generated types for {info.get('title', name)}",
        f"// Version: {info.get('version', '1.0.0')}",
        "",
    ]
    for schema_name, schema in components.items():
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        if not props:
            types_lines.append(f"export type {schema_name} = Record<string, any>;")
            types_lines.append("")
            continue
        types_lines.append(f"export interface {schema_name} {{")
        for prop_name, prop_schema in props.items():
            optional = "" if prop_name in required else "?"
            ts_type = _to_ts_type(prop_schema, components)
            types_lines.append(f"  {prop_name}{optional}: {ts_type};")
        types_lines.append("}")
        types_lines.append("")

    # Generate client.ts
    client_lines = [
        f'// Auto-generated API client for {info.get("title", name)}',
        f'// Version: {info.get("version", "1.0.0")}',
        "",
        'import type { ' + ', '.join(components.keys()) + ' } from "./types";' if components else '',
        "",
        "export interface ClientConfig {",
        "  baseUrl: string;",
        "  headers?: Record<string, string>;",
        "  token?: string;",
        "}",
        "",
        "export class ApiClient {",
        "  private baseUrl: string;",
        "  private headers: Record<string, string>;",
        "  private token?: string;",
        "",
        "  constructor(config: ClientConfig) {",
        "    this.baseUrl = config.baseUrl.replace(/\\/$/, '');",
        "    this.headers = config.headers ?? {};",
        "    this.token = config.token;",
        "  }",
        "",
        "  setToken(token: string) { this.token = token; }",
        "",
        "  private async request<T>(method: string, path: string, body?: any): Promise<T> {",
        "    const headers: Record<string, string> = {",
        '      "Content-Type": "application/json",',
        "      ...this.headers,",
        "    };",
        '    if (this.token) headers["Authorization"] = `Bearer ${this.token}`;',
        "    const res = await fetch(`${this.baseUrl}${path}`, {",
        "      method,",
        "      headers,",
        "      body: body ? JSON.stringify(body) : undefined,",
        "    });",
        "    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);",
        "    return res.json();",
        "  }",
        "",
    ]

    for path, path_item in paths.items():
        for method in ("get", "post", "put", "patch", "delete"):
            if method not in path_item:
                continue
            op = path_item[method]
            op_id = op.get("operationId") or f"{method}_{_slugify(path)}"
            fn_name = _slugify(op_id)
            summary = op.get("summary", "")

            # Determine params
            path_params = [p for p in op.get("parameters", []) if p.get("in") == "path"]
            query_params = [p for p in op.get("parameters", []) if p.get("in") == "query"]
            has_body = method in ("post", "put", "patch") and op.get("requestBody")

            # Build function signature
            params = []
            for p in path_params:
                params.append(f"{p['name']}: {_to_ts_type(p.get('schema', {}), components)}")
            for p in query_params:
                params.append(f"{p['name']}?: {_to_ts_type(p.get('schema', {}), components)}")
            if has_body:
                params.append("body: any")

            # Build path with interpolation
            ts_path = path
            for p in path_params:
                ts_path = ts_path.replace("{" + p["name"] + "}", "${" + p["name"] + "}")
            ts_path = f"`{ts_path}`"

            if summary:
                client_lines.append(f"  /** {summary} */")
            param_str = ", ".join(params)
            client_lines.append(f"  async {fn_name}({param_str}): Promise<any> {{")
            body_arg = "body" if has_body else "undefined"
            client_lines.append(f'    return this.request("{method.upper()}", {ts_path}, {body_arg});')
            client_lines.append("  }")
            client_lines.append("")

    client_lines.append("}")

    # Generate index.ts
    index_lines = [
        'export { ApiClient } from "./client";',
        'export type { ClientConfig } from "./client";',
        'export * from "./types";',
    ]

    # Write files
    (out / "types.ts").write_text("\n".join(types_lines) + "\n")
    (out / "client.ts").write_text("\n".join(client_lines) + "\n")
    (out / "index.ts").write_text("\n".join(index_lines) + "\n")

    output.console.print(f"  [green]\u2713[/green] types.ts  ({len(components)} types)")
    output.console.print(f"  [green]\u2713[/green] client.ts ({sum(len([m for m in ('get','post','put','patch','delete') if m in pi]) for pi in paths.values())} methods)")
    output.console.print(f"  [green]\u2713[/green] index.ts")


def _generate_python(spec: dict[str, Any], out: Path, name: str) -> None:
    """Generate Python SDK."""
    components = spec.get("components", {}).get("schemas", {})
    paths = spec.get("paths", {})
    info = spec.get("info", {})

    module_name = name.replace("-", "_")

    # Generate models.py
    models_lines = [
        f'"""Auto-generated models for {info.get("title", name)}."""',
        "",
        "from __future__ import annotations",
        "",
        "from dataclasses import dataclass, field",
        "from typing import Any",
        "",
    ]
    for schema_name, schema in components.items():
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        if not props:
            models_lines.append(f"# {schema_name}: empty schema")
            models_lines.append(f"{schema_name} = dict")
            models_lines.append("")
            continue
        models_lines.append("@dataclass")
        models_lines.append(f"class {schema_name}:")
        for prop_name, prop_schema in props.items():
            py_type = _to_py_type(prop_schema, components)
            if prop_name not in required:
                py_type = f"{py_type} | None"
                models_lines.append(f"    {prop_name}: {py_type} = None")
            else:
                models_lines.append(f"    {prop_name}: {py_type}")
        models_lines.append("")

    # Generate client.py
    client_lines = [
        f'"""Auto-generated API client for {info.get("title", name)}."""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import Any",
        "",
        "import httpx",
        "",
        "",
        "class ApiClient:",
        '    """Typed HTTP client generated from OpenAPI spec."""',
        "",
        "    def __init__(self, base_url: str, token: str | None = None, headers: dict[str, str] | None = None) -> None:",
        "        self.base_url = base_url.rstrip('/')",
        "        self._headers = headers or {}",
        "        if token:",
        '            self._headers["Authorization"] = f"Bearer {token}"',
        "        self._client = httpx.AsyncClient(base_url=self.base_url, headers=self._headers)",
        "",
        "    async def close(self) -> None:",
        "        await self._client.aclose()",
        "",
        "    async def __aenter__(self):",
        "        return self",
        "",
        "    async def __aexit__(self, *args):",
        "        await self.close()",
        "",
    ]

    for path, path_item in paths.items():
        for method in ("get", "post", "put", "patch", "delete"):
            if method not in path_item:
                continue
            op = path_item[method]
            op_id = op.get("operationId") or f"{method}_{_slugify(path)}"
            fn_name = _slugify(op_id)
            summary = op.get("summary", "")

            path_params = [p for p in op.get("parameters", []) if p.get("in") == "path"]
            has_body = method in ("post", "put", "patch") and op.get("requestBody")

            params = ["self"]
            for p in path_params:
                params.append(f"{p['name']}: {_to_py_type(p.get('schema', {}), components)}")
            if has_body:
                params.append("body: dict[str, Any] | None = None")

            py_path = path
            for p in path_params:
                py_path = py_path.replace("{" + p["name"] + "}", "{" + p["name"] + "}")

            param_str = ", ".join(params)
            if summary:
                client_lines.append(f'    async def {fn_name}({param_str}) -> dict[str, Any]:')
                client_lines.append(f'        """{summary}"""')
            else:
                client_lines.append(f'    async def {fn_name}({param_str}) -> dict[str, Any]:')

            if has_body:
                client_lines.append(f'        resp = await self._client.{method}(f"{py_path}", json=body)')
            else:
                client_lines.append(f'        resp = await self._client.{method}(f"{py_path}")')
            client_lines.append("        resp.raise_for_status()")
            client_lines.append("        return resp.json()")
            client_lines.append("")

    # Generate __init__.py
    init_lines = [
        f'"""Auto-generated SDK for {info.get("title", name)}."""',
        "",
        f"from {module_name}.client import ApiClient",
        "",
        f'__all__ = ["ApiClient"]',
    ]

    # Write files
    pkg_dir = out / module_name
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "models.py").write_text("\n".join(models_lines) + "\n")
    (pkg_dir / "client.py").write_text("\n".join(client_lines) + "\n")
    (pkg_dir / "__init__.py").write_text("\n".join(init_lines) + "\n")

    output.console.print(f"  [green]\u2713[/green] {module_name}/models.py  ({len(components)} models)")
    method_count = sum(len([m for m in ('get','post','put','patch','delete') if m in pi]) for pi in paths.values())
    output.console.print(f"  [green]\u2713[/green] {module_name}/client.py ({method_count} methods)")
    output.console.print(f"  [green]\u2713[/green] {module_name}/__init__.py")
