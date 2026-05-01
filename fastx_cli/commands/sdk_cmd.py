"""SDK client generator from OpenAPI spec."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import click

from fastx_cli.output import output


# ---------------------------------------------------------------------------
# OpenAPI diff / changelog types and logic
# ---------------------------------------------------------------------------

@dataclass
class Change:
    """A single difference between two OpenAPI specs."""

    category: str          # "breaking", "non_breaking", "modified"
    kind: str              # short tag, e.g. "removed_endpoint"
    path: str              # OpenAPI path or dotted location
    description: str       # human-readable explanation
    breaking: bool = False


@dataclass
class DiffReport:
    """Aggregated result of comparing two OpenAPI specs."""

    breaking_changes: list[Change] = field(default_factory=list)
    non_breaking_changes: list[Change] = field(default_factory=list)

    @property
    def summary(self) -> str:
        b = len(self.breaking_changes)
        nb = len(self.non_breaking_changes)
        return f"{b} breaking, {nb} non-breaking change{'s' if b + nb != 1 else ''}"

    @property
    def all_changes(self) -> list[Change]:
        return self.breaking_changes + self.non_breaking_changes


def _resolve_schema(schema: dict[str, Any], components: dict[str, Any]) -> dict[str, Any]:
    """Dereference a single $ref if present."""
    if "$ref" in schema:
        ref_path = schema["$ref"]  # e.g. "#/components/schemas/Foo"
        parts = ref_path.lstrip("#/").split("/")
        node: Any = components
        for p in parts[1:]:  # skip "components"
            node = node.get(p, {}) if isinstance(node, dict) else {}
        return node if isinstance(node, dict) else schema
    return schema


def _type_label(schema: dict[str, Any]) -> str:
    """Return a short human-readable type string for a schema."""
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[-1]
    t = schema.get("type", "any")
    fmt = schema.get("format")
    if t == "array":
        items = schema.get("items", {})
        return f"array[{_type_label(items)}]"
    if fmt:
        return f"{t}({fmt})"
    return t


def _compare_schemas(
    old_schema: dict[str, Any],
    new_schema: dict[str, Any],
    location: str,
    report: DiffReport,
    components_old: dict[str, Any],
    components_new: dict[str, Any],
    *,
    is_request: bool = True,
) -> None:
    """Recursively compare two schemas and populate *report*."""
    old_resolved = _resolve_schema(old_schema, components_old)
    new_resolved = _resolve_schema(new_schema, components_new)

    old_type = old_resolved.get("type", "any")
    new_type = new_resolved.get("type", "any")

    if old_type != new_type:
        report.breaking_changes.append(Change(
            category="breaking",
            kind="changed_type",
            path=location,
            description=f"Type changed from '{old_type}' to '{new_type}'",
            breaking=True,
        ))
        return

    if old_type == "object" or "properties" in old_resolved or "properties" in new_resolved:
        old_props = old_resolved.get("properties", {})
        new_props = new_resolved.get("properties", {})
        old_required = set(old_resolved.get("required", []))
        new_required = set(new_resolved.get("required", []))

        for prop_name in old_props:
            prop_loc = f"{location}.{prop_name}"
            if prop_name not in new_props:
                if is_request and prop_name in old_required:
                    report.breaking_changes.append(Change(
                        category="breaking",
                        kind="removed_required_field",
                        path=prop_loc,
                        description=f"Required request field '{prop_name}' removed",
                        breaking=True,
                    ))
                elif not is_request:
                    report.breaking_changes.append(Change(
                        category="breaking",
                        kind="removed_response_field",
                        path=prop_loc,
                        description=f"Response field '{prop_name}' removed",
                        breaking=True,
                    ))
                else:
                    report.non_breaking_changes.append(Change(
                        category="modified",
                        kind="removed_optional_field",
                        path=prop_loc,
                        description=f"Optional field '{prop_name}' removed",
                    ))
            else:
                _compare_schemas(
                    old_props[prop_name],
                    new_props[prop_name],
                    prop_loc,
                    report,
                    components_old,
                    components_new,
                    is_request=is_request,
                )

        for prop_name in new_props:
            if prop_name not in old_props:
                prop_loc = f"{location}.{prop_name}"
                if is_request and prop_name in new_required:
                    report.breaking_changes.append(Change(
                        category="breaking",
                        kind="added_required_field",
                        path=prop_loc,
                        description=f"New required request field '{prop_name}' added (breaking for existing clients)",
                        breaking=True,
                    ))
                else:
                    report.non_breaking_changes.append(Change(
                        category="non_breaking",
                        kind="added_field",
                        path=prop_loc,
                        description=f"Field '{prop_name}' added",
                    ))

    if old_type == "array":
        old_items = old_resolved.get("items", {})
        new_items = new_resolved.get("items", {})
        if old_items or new_items:
            _compare_schemas(old_items, new_items, f"{location}[]", report, components_old, components_new, is_request=is_request)


def _compare_parameters(
    old_params: list[dict[str, Any]],
    new_params: list[dict[str, Any]],
    path: str,
    method: str,
    report: DiffReport,
) -> None:
    """Compare parameter lists for a single operation."""
    def _key(p: dict[str, Any]) -> str:
        return f"{p.get('in', '?')}:{p.get('name', '?')}"

    old_map = {_key(p): p for p in old_params}
    new_map = {_key(p): p for p in new_params}

    for k, old_p in old_map.items():
        loc = f"{method.upper()} {path} param {old_p.get('name')}"
        if k not in new_map:
            if old_p.get("required", False):
                report.breaking_changes.append(Change(
                    category="breaking", kind="removed_required_param",
                    path=loc, description=f"Required parameter '{old_p.get('name')}' removed", breaking=True,
                ))
            else:
                report.non_breaking_changes.append(Change(
                    category="modified", kind="removed_optional_param",
                    path=loc, description=f"Optional parameter '{old_p.get('name')}' removed",
                ))
        else:
            new_p = new_map[k]
            if old_p.get("in") != new_p.get("in"):
                report.non_breaking_changes.append(Change(
                    category="modified", kind="changed_param_location",
                    path=loc, description=f"Parameter location changed from '{old_p.get('in')}' to '{new_p.get('in')}'",
                ))
            old_default = old_p.get("schema", {}).get("default")
            new_default = new_p.get("schema", {}).get("default")
            if old_default != new_default:
                report.non_breaking_changes.append(Change(
                    category="modified", kind="changed_default",
                    path=loc, description=f"Default value changed from {old_default!r} to {new_default!r}",
                ))

    for k, new_p in new_map.items():
        if k not in old_map:
            loc = f"{method.upper()} {path} param {new_p.get('name')}"
            report.non_breaking_changes.append(Change(
                category="non_breaking", kind="added_param",
                path=loc, description=f"Parameter '{new_p.get('name')}' added",
            ))


def _compare_operations(
    old_op: dict[str, Any],
    new_op: dict[str, Any],
    path: str,
    method: str,
    report: DiffReport,
    components_old: dict[str, Any],
    components_new: dict[str, Any],
) -> None:
    """Compare two operations (same method+path) and populate *report*."""
    loc = f"{method.upper()} {path}"

    # Descriptions
    old_desc = old_op.get("summary", "") or old_op.get("description", "")
    new_desc = new_op.get("summary", "") or new_op.get("description", "")
    if old_desc != new_desc and old_desc and new_desc:
        report.non_breaking_changes.append(Change(
            category="modified", kind="changed_description",
            path=loc, description="Description / summary changed",
        ))

    # Deprecated
    if not old_op.get("deprecated") and new_op.get("deprecated"):
        report.non_breaking_changes.append(Change(
            category="non_breaking", kind="deprecated_endpoint",
            path=loc, description="Endpoint marked as deprecated",
        ))

    # Parameters
    _compare_parameters(
        old_op.get("parameters", []),
        new_op.get("parameters", []),
        path, method, report,
    )

    # Request body
    old_body = old_op.get("requestBody", {})
    new_body = new_op.get("requestBody", {})
    if old_body or new_body:
        old_content = old_body.get("content", {})
        new_content = new_body.get("content", {})
        for media in ("application/json", "multipart/form-data", "application/x-www-form-urlencoded"):
            old_schema = old_content.get(media, {}).get("schema", {})
            new_schema = new_content.get(media, {}).get("schema", {})
            if old_schema or new_schema:
                _compare_schemas(
                    old_schema, new_schema,
                    f"{loc} requestBody({media})",
                    report, components_old, components_new,
                    is_request=True,
                )

    # Responses
    old_resps = old_op.get("responses", {})
    new_resps = new_op.get("responses", {})
    for status in set(old_resps) | set(new_resps):
        if status in old_resps and status in new_resps:
            old_resp_content = old_resps[status].get("content", {})
            new_resp_content = new_resps[status].get("content", {})
            for media in ("application/json",):
                old_schema = old_resp_content.get(media, {}).get("schema", {})
                new_schema = new_resp_content.get(media, {}).get("schema", {})
                if old_schema or new_schema:
                    _compare_schemas(
                        old_schema, new_schema,
                        f"{loc} response({status})",
                        report, components_old, components_new,
                        is_request=False,
                    )


def _diff_specs(old_spec: dict[str, Any], new_spec: dict[str, Any]) -> DiffReport:
    """Compare two full OpenAPI specs and return a :class:`DiffReport`."""
    report = DiffReport()
    components_old = old_spec.get("components", {}).get("schemas", {})
    components_new = new_spec.get("components", {}).get("schemas", {})

    old_paths: dict[str, Any] = old_spec.get("paths", {})
    new_paths: dict[str, Any] = new_spec.get("paths", {})

    methods = ("get", "post", "put", "patch", "delete", "head", "options", "trace")

    # Removed endpoints
    for path in old_paths:
        if path not in new_paths:
            for method in methods:
                if method in old_paths[path]:
                    report.breaking_changes.append(Change(
                        category="breaking", kind="removed_endpoint",
                        path=f"{method.upper()} {path}",
                        description=f"Endpoint removed",
                        breaking=True,
                    ))
            continue

        old_item = old_paths[path]
        new_item = new_paths[path]

        for method in methods:
            if method in old_item and method not in new_item:
                report.breaking_changes.append(Change(
                    category="breaking", kind="removed_endpoint",
                    path=f"{method.upper()} {path}",
                    description=f"Endpoint removed",
                    breaking=True,
                ))
            elif method in old_item and method in new_item:
                _compare_operations(
                    old_item[method], new_item[method],
                    path, method, report,
                    {"schemas": components_old},
                    {"schemas": components_new},
                )

        # Detect method change: if old has exactly one method and new has exactly
        # one *different* method for the same path, flag it.
        old_methods = {m for m in methods if m in old_item}
        new_methods = {m for m in methods if m in new_item}
        added_methods = new_methods - old_methods
        removed_methods = old_methods - new_methods
        if len(removed_methods) == 1 and len(added_methods) == 1:
            rm = removed_methods.pop()
            am = added_methods.pop()
            report.breaking_changes.append(Change(
                category="breaking", kind="changed_method",
                path=path,
                description=f"HTTP method changed from {rm.upper()} to {am.upper()}",
                breaking=True,
            ))

    # Added endpoints
    for path in new_paths:
        if path not in old_paths:
            for method in methods:
                if method in new_paths[path]:
                    report.non_breaking_changes.append(Change(
                        category="non_breaking", kind="added_endpoint",
                        path=f"{method.upper()} {path}",
                        description="New endpoint added",
                    ))
            continue

        old_item = old_paths[path]
        new_item = new_paths[path]
        for method in methods:
            if method in new_item and method not in old_item:
                report.non_breaking_changes.append(Change(
                    category="non_breaking", kind="added_endpoint",
                    path=f"{method.upper()} {path}",
                    description="New endpoint added",
                ))

    return report


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def _format_text(report: DiffReport, breaking_only: bool) -> str:
    """Render the diff report as colored terminal text (Rich markup)."""
    lines: list[str] = []
    if report.breaking_changes:
        lines.append("[bold red]BREAKING CHANGES[/bold red]")
        for c in report.breaking_changes:
            lines.append(f"  [red]\u2718[/red] [bold]{c.path}[/bold] \u2014 {c.description}")
        lines.append("")

    if not breaking_only:
        non_breaking = [c for c in report.non_breaking_changes if c.category == "non_breaking"]
        modified = [c for c in report.non_breaking_changes if c.category == "modified"]

        if non_breaking:
            lines.append("[bold green]ADDITIONS[/bold green]")
            for c in non_breaking:
                lines.append(f"  [green]+[/green] [bold]{c.path}[/bold] \u2014 {c.description}")
            lines.append("")

        if modified:
            lines.append("[bold yellow]MODIFICATIONS[/bold yellow]")
            for c in modified:
                lines.append(f"  [yellow]~[/yellow] [bold]{c.path}[/bold] \u2014 {c.description}")
            lines.append("")

    lines.append(f"[bold]Summary:[/bold] {report.summary}")
    return "\n".join(lines)


def _format_json(report: DiffReport, breaking_only: bool) -> str:
    """Render the diff report as JSON."""
    data: dict[str, Any] = {
        "summary": report.summary,
        "breaking_changes": [
            {"kind": c.kind, "path": c.path, "description": c.description}
            for c in report.breaking_changes
        ],
    }
    if not breaking_only:
        data["non_breaking_changes"] = [
            {"kind": c.kind, "path": c.path, "description": c.description, "category": c.category}
            for c in report.non_breaking_changes
        ]
    return json.dumps(data, indent=2)


def _format_markdown(report: DiffReport, breaking_only: bool) -> str:
    """Render the diff report as Markdown."""
    lines: list[str] = ["# OpenAPI Diff Report", ""]
    if report.breaking_changes:
        lines.append("## Breaking Changes")
        lines.append("")
        for c in report.breaking_changes:
            lines.append(f"- **{c.path}** -- {c.description}")
        lines.append("")

    if not breaking_only:
        non_breaking = [c for c in report.non_breaking_changes if c.category == "non_breaking"]
        modified = [c for c in report.non_breaking_changes if c.category == "modified"]

        if non_breaking:
            lines.append("## Additions")
            lines.append("")
            for c in non_breaking:
                lines.append(f"- **{c.path}** -- {c.description}")
            lines.append("")

        if modified:
            lines.append("## Modifications")
            lines.append("")
            for c in modified:
                lines.append(f"- **{c.path}** -- {c.description}")
            lines.append("")

    lines.append(f"**Summary:** {report.summary}")
    return "\n".join(lines)


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


@sdk_group.command(name="diff")
@click.option("--old", "-o", "old_spec_path", required=True, help="Path or URL to the old OpenAPI spec")
@click.option("--new", "-n", "new_spec_path", default=None, help="Path or URL to the new OpenAPI spec (default: http://localhost:8000/openapi.json)")
@click.option("--format", "-f", "fmt", type=click.Choice(["text", "json", "markdown"]), default="text", help="Output format")
@click.option("--breaking-only", is_flag=True, default=False, help="Only show breaking changes")
def diff(old_spec_path: str, new_spec_path: str | None, fmt: str, breaking_only: bool) -> None:
    """Compare two OpenAPI specs and report changes.

    \b
    Examples:
        fastx sdk diff -o old.json -n new.json
        fastx sdk diff -o v1.json                     # compare against running server
        fastx sdk diff -o v1.json -n v2.json --breaking-only
        fastx sdk diff -o v1.json -f markdown > changelog.md
        fastx sdk diff -o https://api.example.com/v1/openapi.json -n https://api.example.com/v2/openapi.json
    """
    new_url = new_spec_path or "http://localhost:8000/openapi.json"

    old_spec = _load_spec_from(old_spec_path)
    if old_spec is None:
        return
    new_spec = _load_spec_from(new_spec_path) if new_spec_path else _load_spec_from(new_url)
    if new_spec is None:
        return

    report = _diff_specs(old_spec, new_spec)

    if fmt == "json":
        output.console.print(_format_json(report, breaking_only))
    elif fmt == "markdown":
        output.console.print(_format_markdown(report, breaking_only))
    else:
        output.console.print(_format_text(report, breaking_only))

    if report.breaking_changes:
        raise SystemExit(1)


def _load_spec_from(source: str) -> dict[str, Any] | None:
    """Load an OpenAPI spec from a file path or URL."""
    if source.startswith("http://") or source.startswith("https://"):
        output.console.print(f"[dim]Fetching spec from {source}...[/dim]")
        try:
            import urllib.request
            resp = urllib.request.urlopen(source, timeout=10)
            return json.loads(resp.read())
        except Exception as e:
            output.console.print(f"[red]Failed to fetch spec from {source}: {e}[/red]")
            return None

    p = Path(source)
    if not p.exists():
        output.console.print(f"[red]File not found: {source}[/red]")
        return None
    with open(p) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            output.console.print(f"[red]Invalid JSON in {source}: {e}[/red]")
            return None


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
