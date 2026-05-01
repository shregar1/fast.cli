"""Serve mock API responses from an OpenAPI spec.

Parses an OpenAPI JSON specification and generates a FastAPI app with
route handlers that return example or fake responses.  Supports
artificial delay, configurable error rates, and static/random response
generation.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import click


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

def _resolve_ref(ref: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve a ``$ref`` pointer like ``#/components/schemas/Foo``."""
    parts = ref.lstrip("#/").split("/")
    node: Any = spec
    for part in parts:
        node = node[part]
    return node


def _generate_value(
    schema: Dict[str, Any],
    spec: Dict[str, Any],
    field_name: str = "value",
    static: bool = False,
    depth: int = 0,
) -> Any:
    """Recursively generate a fake value from a JSON Schema node."""
    if depth > 20:
        return None

    # Handle $ref
    if "$ref" in schema:
        schema = _resolve_ref(schema["$ref"], spec)

    # Return explicit example when available and static mode requested
    if static and "example" in schema:
        return schema["example"]

    # Handle allOf / oneOf / anyOf by picking the first entry
    for combiner in ("allOf", "oneOf", "anyOf"):
        if combiner in schema:
            items = schema[combiner]
            if items:
                return _generate_value(items[0], spec, field_name, static, depth + 1)

    schema_type = schema.get("type", "string")

    # Enum
    if "enum" in schema:
        return schema["enum"][0] if static else random.choice(schema["enum"])

    if schema_type == "string":
        fmt = schema.get("format", "")
        if fmt == "date":
            return "2024-01-01"
        if fmt == "date-time":
            return "2024-01-01T00:00:00Z"
        if fmt == "email":
            return "user@example.com"
        if fmt == "uri" or fmt == "url":
            return "https://example.com"
        if fmt == "uuid":
            return "00000000-0000-0000-0000-000000000000"
        return f"string_{field_name}"

    if schema_type == "integer":
        if static:
            return 0
        return random.randint(0, 100)

    if schema_type == "number":
        if static:
            return 0.0
        return round(random.uniform(0, 100), 2)

    if schema_type == "boolean":
        if static:
            return True
        return random.choice([True, False])

    if schema_type == "array":
        items_schema = schema.get("items", {"type": "string"})
        count = 1 if static else random.randint(1, 3)
        return [
            _generate_value(items_schema, spec, field_name, static, depth + 1)
            for _ in range(count)
        ]

    if schema_type == "object":
        properties = schema.get("properties", {})
        result: Dict[str, Any] = {}
        for prop_name, prop_schema in properties.items():
            result[prop_name] = _generate_value(
                prop_schema, spec, prop_name, static, depth + 1,
            )
        # Handle additionalProperties when no explicit properties
        if not properties and "additionalProperties" in schema:
            ap = schema["additionalProperties"]
            if isinstance(ap, dict):
                result["key"] = _generate_value(ap, spec, "key", static, depth + 1)
        return result

    return None


def _extract_response_schema(
    responses: Dict[str, Any], spec: Dict[str, Any],
) -> tuple[int, Optional[Dict[str, Any]], Optional[Any]]:
    """Pick the best success response and return (status_code, schema, example)."""
    # Prefer 200, then 201, then first 2xx
    for code in ("200", "201"):
        if code in responses:
            resp = responses[code]
            status = int(code)
            break
    else:
        for code in sorted(responses):
            if code.startswith("2"):
                resp = responses[code]
                status = int(code)
                break
        else:
            resp = next(iter(responses.values()), {})
            status = 200

    content = resp.get("content", {})
    json_content = content.get("application/json", {})

    example = json_content.get("example")
    schema = json_content.get("schema")

    return status, schema, example


# ---------------------------------------------------------------------------
# Mock app builder
# ---------------------------------------------------------------------------

def _build_mock_app(
    spec: Dict[str, Any],
    delay_ms: int,
    error_rate: int,
    static: bool,
) -> Any:
    """Build a FastAPI application with mock route handlers."""
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    title = spec.get("info", {}).get("title", "Mock API")
    description = spec.get("info", {}).get("description", "Auto-generated mock server")

    app = FastAPI(title=f"{title} (Mock)", description=description)
    paths = spec.get("paths", {})
    route_info: List[tuple[str, str, int]] = []

    for path, path_item in paths.items():
        for method in ("get", "post", "put", "patch", "delete", "head", "options"):
            if method not in path_item:
                continue

            operation = path_item[method]
            responses = operation.get("responses", {})
            status_code, schema, example = _extract_response_schema(responses, spec)

            # Pre-generate the response body
            if example is not None:
                body = example
            elif schema is not None:
                body = _generate_value(schema, spec, "root", static)
            else:
                body = None

            # Convert OpenAPI path params ``{id}`` to FastAPI format (same)
            fastapi_path = path

            route_info.append((method.upper(), fastapi_path, status_code))

            # Closure must capture loop vars via defaults
            def _make_handler(
                _body: Any = body,
                _status: int = status_code,
                _delay: int = delay_ms,
                _err_rate: int = error_rate,
                _schema: Optional[Dict[str, Any]] = schema,
                _static: bool = static,
                _spec: Dict[str, Any] = spec,
            ):  # type: ignore[return]
                async def _handler() -> JSONResponse:
                    # Artificial delay
                    if _delay > 0:
                        await asyncio.sleep(_delay / 1000.0)

                    # Random error injection
                    if _err_rate > 0 and random.randint(1, 100) <= _err_rate:
                        return JSONResponse(
                            status_code=500,
                            content={"detail": "Simulated error (--error-rate)"},
                        )

                    response_body = _body
                    # Regenerate non-static responses on each call
                    if not _static and _schema is not None:
                        response_body = _generate_value(
                            _schema, _spec, "root", False,
                        )

                    return JSONResponse(
                        status_code=_status,
                        content=response_body,
                    )

                return _handler

            app.add_api_route(
                fastapi_path,
                _make_handler(),
                methods=[method.upper()],
                name=operation.get("operationId", f"{method}_{path}"),
            )

    return app, route_info


# ---------------------------------------------------------------------------
# CLI command
# ---------------------------------------------------------------------------

@click.command("mock")
@click.option(
    "--input", "-i", "input_path",
    type=click.Path(exists=True, dir_okay=False),
    default=None,
    help="Path to an OpenAPI spec JSON file.",
)
@click.option(
    "--url", "-u",
    default=None,
    help="URL to fetch the OpenAPI spec from (default: http://localhost:8000/openapi.json).",
)
@click.option("--port", "-p", default=9000, type=int, help="Mock server port (default: 9000).")
@click.option("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0).")
@click.option("--delay", default=0, type=int, help="Artificial response delay in milliseconds.")
@click.option(
    "--error-rate", default=0, type=int,
    help="Percentage of requests that return a 500 error (0-100).",
)
@click.option(
    "--static", "static_mode", is_flag=True, default=False,
    help="Use static example values from the spec instead of random data.",
)
def mock_cmd(
    input_path: Optional[str],
    url: Optional[str],
    port: int,
    host: str,
    delay: int,
    error_rate: int,
    static_mode: bool,
) -> None:
    """Serve mock API responses from an OpenAPI spec.

    \b
    Examples:
        fastx mock                              # Mock from running server
        fastx mock -i openapi.json              # Mock from local file
        fastx mock -u http://api:8000/openapi.json
        fastx mock -p 9001 --delay 200          # Port 9001 with 200ms delay
        fastx mock --static                     # Use spec examples only
        fastx mock --error-rate 10              # 10% random 500 errors
    """
    # ---- Load spec --------------------------------------------------------
    if input_path:
        spec_path = Path(input_path)
        try:
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise click.ClickException(f"Failed to read spec file: {exc}") from exc
        click.echo(f"Loaded spec from {spec_path}")
    else:
        target_url = url or "http://localhost:8000/openapi.json"
        click.echo(f"Fetching spec from {target_url} ...")
        try:
            import urllib.request

            with urllib.request.urlopen(target_url, timeout=10) as resp:
                spec = json.loads(resp.read().decode())
        except Exception as exc:
            raise click.ClickException(
                f"Failed to fetch spec from {target_url}: {exc}\n"
                "Hint: pass --input / -i to use a local file instead.",
            ) from exc

    # Validate minimal structure
    if "paths" not in spec:
        raise click.ClickException("Invalid OpenAPI spec: missing 'paths' key.")

    # ---- Build app --------------------------------------------------------
    app, route_info = _build_mock_app(spec, delay, error_rate, static_mode)

    # ---- Print route table ------------------------------------------------
    click.echo()
    title = spec.get("info", {}).get("title", "Mock API")
    click.echo(click.style(f"  Mock Server: {title}", bold=True))
    click.echo()

    if route_info:
        method_width = max(len(m) for m, _, _ in route_info)
        for method, path, status in route_info:
            m_colored = click.style(method.ljust(method_width), fg="green", bold=True)
            s_colored = click.style(str(status), fg="cyan")
            click.echo(f"  {m_colored}  {path}  -> {s_colored}")
    else:
        click.echo("  (no routes found in spec)")

    click.echo()
    local_url = f"http://{'localhost' if host == '0.0.0.0' else host}:{port}"
    click.echo(f"  Listening on {click.style(local_url, bold=True)}")
    if delay:
        click.echo(f"  Response delay: {delay}ms")
    if error_rate:
        click.echo(f"  Error rate: {error_rate}%")
    click.echo()

    # ---- Start server -----------------------------------------------------
    try:
        import uvicorn
    except ImportError:
        raise click.ClickException(
            "uvicorn is required to run the mock server. Install it with: pip install uvicorn"
        )

    uvicorn.run(app, host=host, port=port, log_level="info")


def register_mock(cli: click.Group) -> None:
    """Register the ``mock`` command on the root CLI group."""
    cli.add_command(mock_cmd)
