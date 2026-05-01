"""Built-in HTTP load testing for FastX endpoints.

Run concurrent HTTP requests against a target URL and report latency
percentiles, throughput, and error rates.  Uses ``httpx`` with
``asyncio.Semaphore`` for concurrency control.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import List, Optional, Tuple

import click

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_headers(raw_headers: Tuple[str, ...]) -> dict[str, str]:
    """Turn ``("Content-Type: application/json", ...)`` into a dict."""
    headers: dict[str, str] = {}
    for h in raw_headers:
        if ":" not in h:
            raise click.BadParameter(f"Invalid header format (missing ':'): {h}")
        key, _, value = h.partition(":")
        headers[key.strip()] = value.strip()
    return headers


def _percentile(sorted_data: List[float], pct: float) -> float:
    """Return the *pct*-th percentile from an already-sorted list."""
    if not sorted_data:
        return 0.0
    k = (len(sorted_data) - 1) * (pct / 100.0)
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[f]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


# ---------------------------------------------------------------------------
# Core benchmark runner
# ---------------------------------------------------------------------------

async def _send_request(
    client: "httpx.AsyncClient",
    method: str,
    url: str,
    headers: dict[str, str],
    body: Optional[str],
) -> Tuple[bool, float, int]:
    """Fire a single request and return ``(success, latency_ms, status)``."""
    start = time.perf_counter()
    try:
        response = await client.request(
            method,
            url,
            headers=headers or None,
            content=body,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return (response.status_code < 400, elapsed_ms, response.status_code)
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return (False, elapsed_ms, 0)


async def _run_bench(
    url: str,
    method: str,
    headers: dict[str, str],
    body: Optional[str],
    concurrency: int,
    total_requests: Optional[int],
    duration: Optional[float],
) -> dict:
    """Execute the load test and return a results dict."""
    sem = asyncio.Semaphore(concurrency)
    latencies: List[float] = []
    successes = 0
    failures = 0
    status_counts: dict[int, int] = {}

    async def _worker(client: "httpx.AsyncClient") -> None:
        nonlocal successes, failures
        async with sem:
            ok, lat, status = await _send_request(client, method, url, headers, body)
            latencies.append(lat)
            status_counts[status] = status_counts.get(status, 0) + 1
            if ok:
                successes += 1
            else:
                failures += 1

    wall_start = time.perf_counter()

    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        if duration is not None:
            # Duration-based: keep sending until time runs out
            deadline = wall_start + duration
            tasks: list[asyncio.Task] = []
            while time.perf_counter() < deadline:
                task = asyncio.create_task(_worker(client))
                tasks.append(task)
                # Yield to let tasks run and avoid over-scheduling
                if len(tasks) % concurrency == 0:
                    await asyncio.sleep(0)
            if tasks:
                await asyncio.gather(*tasks)
        else:
            # Request-count-based
            n = total_requests or 100
            tasks = [asyncio.create_task(_worker(client)) for _ in range(n)]
            await asyncio.gather(*tasks)

    wall_elapsed = time.perf_counter() - wall_start
    sorted_lat = sorted(latencies)
    total = successes + failures

    return {
        "url": url,
        "method": method.upper(),
        "concurrency": concurrency,
        "total_requests": total,
        "successes": successes,
        "failures": failures,
        "wall_time_s": round(wall_elapsed, 3),
        "requests_per_sec": round(total / wall_elapsed, 2) if wall_elapsed > 0 else 0,
        "latency_min_ms": round(min(sorted_lat), 2) if sorted_lat else 0,
        "latency_max_ms": round(max(sorted_lat), 2) if sorted_lat else 0,
        "latency_mean_ms": round(statistics.mean(sorted_lat), 2) if sorted_lat else 0,
        "latency_p50_ms": round(_percentile(sorted_lat, 50), 2),
        "latency_p95_ms": round(_percentile(sorted_lat, 95), 2),
        "latency_p99_ms": round(_percentile(sorted_lat, 99), 2),
        "status_codes": status_counts,
    }


# ---------------------------------------------------------------------------
# Pretty-print helpers
# ---------------------------------------------------------------------------

def _print_report(results: dict) -> None:
    """Print a coloured summary table to the terminal."""
    click.echo()
    click.secho("  FastX Bench — Load Test Results", fg="cyan", bold=True)
    click.echo()

    click.echo(f"  {'Target:':<18} {results['method']} {results['url']}")
    click.echo(f"  {'Concurrency:':<18} {results['concurrency']}")
    click.echo(f"  {'Wall time:':<18} {results['wall_time_s']} s")
    click.echo()

    click.secho("  Throughput", fg="white", bold=True)
    click.echo(f"  {'Total requests:':<18} {results['total_requests']}")
    click.secho(f"  {'Successes:':<18} {results['successes']}", fg="green")
    if results["failures"]:
        click.secho(f"  {'Failures:':<18} {results['failures']}", fg="red")
    else:
        click.echo(f"  {'Failures:':<18} {results['failures']}")
    click.echo(f"  {'Req/sec:':<18} {results['requests_per_sec']}")
    click.echo()

    click.secho("  Latency (ms)", fg="white", bold=True)
    click.echo(f"  {'Min:':<18} {results['latency_min_ms']}")
    click.echo(f"  {'Max:':<18} {results['latency_max_ms']}")
    click.echo(f"  {'Mean:':<18} {results['latency_mean_ms']}")
    click.echo(f"  {'P50:':<18} {results['latency_p50_ms']}")
    click.echo(f"  {'P95:':<18} {results['latency_p95_ms']}")
    click.echo(f"  {'P99:':<18} {results['latency_p99_ms']}")
    click.echo()

    if results["status_codes"]:
        click.secho("  Status Codes", fg="white", bold=True)
        for code, count in sorted(results["status_codes"].items()):
            label = f"  {code}:" if code else "  ERR:"
            color = "green" if 200 <= code < 400 else ("yellow" if 400 <= code < 500 else "red")
            if code == 0:
                color = "red"
            click.secho(f"  {label:<18} {count}", fg=color)
        click.echo()


# ---------------------------------------------------------------------------
# Click command
# ---------------------------------------------------------------------------

@click.command("bench")
@click.option("--url", default="http://localhost:8000", show_default=True, help="Base URL of the target server.")
@click.option("--endpoint", "-e", default="/health", show_default=True, help="Endpoint path to test.")
@click.option("--concurrency", "-c", default=10, show_default=True, type=int, help="Number of concurrent users.")
@click.option("--requests", "-n", "total_requests", default=100, show_default=True, type=int, help="Total number of requests to send.")
@click.option("--duration", "-d", default=None, type=float, help="Test duration in seconds (overrides --requests).")
@click.option("--method", default="GET", show_default=True, type=click.Choice(["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"], case_sensitive=False), help="HTTP method.")
@click.option("--header", multiple=True, help='HTTP header in "Key: Value" format (repeatable).')
@click.option("--body", default=None, help="Request body for POST/PUT/PATCH.")
@click.option("--output", "-o", "output_file", default=None, type=click.Path(), help="Save JSON report to file.")
def bench_cmd(
    url: str,
    endpoint: str,
    concurrency: int,
    total_requests: int,
    duration: Optional[float],
    method: str,
    header: Tuple[str, ...],
    body: Optional[str],
    output_file: Optional[str],
) -> None:
    """Run HTTP load tests against FastX endpoints.

    \b
    Examples:
        fastx bench                                # 100 GET /health, 10 concurrent
        fastx bench -e /api/users -n 500 -c 50     # 500 reqs, 50 concurrent
        fastx bench -d 10 -c 20                    # Run for 10 seconds
        fastx bench --method POST --body '{"x":1}' -e /api/items
        fastx bench --header "Authorization: Bearer tok" -e /api/me
        fastx bench -o report.json                 # Save JSON report
    """
    if httpx is None:
        click.secho(
            "Error: httpx is required for benchmarking. Install it with:\n"
            "  pip install httpx",
            fg="red",
            err=True,
        )
        raise SystemExit(1)

    # Build full target URL
    target = url.rstrip("/") + "/" + endpoint.lstrip("/")

    # Parse headers
    try:
        parsed_headers = _parse_headers(header)
    except click.BadParameter as exc:
        click.secho(str(exc), fg="red", err=True)
        raise SystemExit(1)

    click.secho("  FastX Bench", fg="cyan", bold=True)
    mode = f"{duration}s duration" if duration else f"{total_requests} requests"
    click.echo(f"  Targeting {method.upper()} {target}  ({mode}, {concurrency} concurrent)")
    click.echo()

    results = asyncio.run(
        _run_bench(
            url=target,
            method=method.upper(),
            headers=parsed_headers,
            body=body,
            concurrency=concurrency,
            total_requests=total_requests if duration is None else None,
            duration=duration,
        )
    )

    _print_report(results)

    if output_file:
        out_path = Path(output_file)
        out_path.write_text(json.dumps(results, indent=2))
        click.secho(f"  Report saved to {out_path}", fg="green")
        click.echo()


def register_bench(cli: click.Group) -> None:
    """Register the ``bench`` command on the root CLI group."""
    cli.add_command(bench_cmd)
