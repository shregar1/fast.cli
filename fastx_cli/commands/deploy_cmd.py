"""Cloud deployment commands."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import click

from fastx_cli.commands.project_root import resolve_fastmvc_project_root
from fastx_cli.output import output


DOCKERFILE_TEMPLATE = '''FROM python:3.13-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \\
    gcc libpq-dev && \\
    rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \\
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live')" || exit 1

# Run with uvicorn
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
'''

FLY_TOML_TEMPLATE = '''app = "{app_name}"
primary_region = "{region}"

[build]

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true
  auto_start_machines = true
  min_machines_running = 1

[checks]
  [checks.health]
    port = 8000
    type = "http"
    interval = "15s"
    timeout = "5s"
    path = "/health/live"
'''

ECS_TASK_DEFINITION = {
    "family": "",
    "networkMode": "awsvpc",
    "requiresCompatibilities": ["FARGATE"],
    "cpu": "256",
    "memory": "512",
    "executionRoleArn": "arn:aws:iam::role/ecsTaskExecutionRole",
    "containerDefinitions": [
        {
            "name": "",
            "image": "",
            "portMappings": [{"containerPort": 8000, "protocol": "tcp"}],
            "healthCheck": {
                "command": ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live')\" || exit 1"],
                "interval": 30,
                "timeout": 5,
                "retries": 3,
                "startPeriod": 10,
            },
            "logConfiguration": {
                "logDriver": "awslogs",
                "options": {
                    "awslogs-group": "",
                    "awslogs-region": "",
                    "awslogs-stream-prefix": "ecs",
                },
            },
            "environment": [],
            "essential": True,
        }
    ],
}


@click.group()
def deploy_group() -> None:
    """Deploy your FastX app to cloud platforms."""
    pass


@deploy_group.command(name="dockerfile")
@click.option("--force", is_flag=True, help="Overwrite existing Dockerfile")
def gen_dockerfile(force: bool) -> None:
    """Generate a production Dockerfile.

    \b
    Example:
        fastx deploy dockerfile
        fastx deploy dockerfile --force
    """
    root = resolve_fastmvc_project_root(Path.cwd())
    dockerfile = root / "Dockerfile"
    if dockerfile.exists() and not force:
        output.console.print("[yellow]Dockerfile already exists. Use --force to overwrite.[/yellow]")
        return
    dockerfile.write_text(DOCKERFILE_TEMPLATE)
    output.console.print("[green]✓[/green] Dockerfile generated")

    # Also generate .dockerignore if missing
    dockerignore = root / ".dockerignore"
    if not dockerignore.exists():
        dockerignore.write_text(
            "__pycache__\n*.pyc\n.env\n.git\n.venv\nvenv\n"
            "node_modules\n*.egg-info\ndist\nbuild\n"
            ".pytest_cache\n.mypy_cache\n.ruff_cache\n"
            "tests/\ndocs/\n*.md\n"
        )
        output.console.print("[green]✓[/green] .dockerignore generated")


def _ensure_dockerfile(root: Path) -> None:
    """Generate Dockerfile if it doesn't exist."""
    if not (root / "Dockerfile").exists():
        (root / "Dockerfile").write_text(DOCKERFILE_TEMPLATE)
        output.console.print("[green]✓[/green] Dockerfile generated")


@deploy_group.command(name="fly")
@click.option("--app-name", "-n", default=None, help="Fly.io app name")
@click.option("--region", "-r", default="iad", help="Primary region (default: iad)")
def deploy_fly(app_name: str | None, region: str) -> None:
    """Deploy to Fly.io.

    \b
    Prerequisites:
        brew install flyctl
        fly auth login

    \b
    Example:
        fastx deploy fly
        fastx deploy fly --app-name my-api --region lhr
    """
    root = resolve_fastmvc_project_root(Path.cwd())

    # Check flyctl is installed
    if not _command_exists("fly"):
        output.console.print("[red]flyctl not found. Install: brew install flyctl[/red]")
        return

    _ensure_dockerfile(root)

    # Generate fly.toml if missing
    fly_toml = root / "fly.toml"
    if not fly_toml.exists():
        name = app_name or root.name.replace("_", "-")
        fly_toml.write_text(FLY_TOML_TEMPLATE.format(app_name=name, region=region))
        output.console.print(f"[green]✓[/green] fly.toml generated (app: {name}, region: {region})")

    # Deploy
    output.console.print("\n[bold cyan]Deploying to Fly.io...[/bold cyan]\n")
    result = subprocess.run(["fly", "deploy"], cwd=str(root))
    if result.returncode == 0:
        output.console.print("\n[bold green]✓ Deployed to Fly.io![/bold green]")
        subprocess.run(["fly", "status"], cwd=str(root))
    else:
        output.console.print("\n[red]Deploy failed. Run 'fly auth login' if not authenticated.[/red]")


@deploy_group.command(name="railway")
def deploy_railway() -> None:
    """Deploy to Railway.

    \b
    Prerequisites:
        npm install -g @railway/cli
        railway login

    \b
    Example:
        fastx deploy railway
    """
    root = resolve_fastmvc_project_root(Path.cwd())

    if not _command_exists("railway"):
        output.console.print("[red]railway CLI not found. Install: npm install -g @railway/cli[/red]")
        return

    _ensure_dockerfile(root)

    output.console.print("\n[bold cyan]Deploying to Railway...[/bold cyan]\n")
    result = subprocess.run(["railway", "up"], cwd=str(root))
    if result.returncode == 0:
        output.console.print("\n[bold green]✓ Deployed to Railway![/bold green]")
    else:
        output.console.print("\n[red]Deploy failed. Run 'railway login' if not authenticated.[/red]")


@deploy_group.command(name="aws")
@click.option("--app-name", "-n", default=None, help="App/service name")
@click.option("--region", "-r", default="us-east-1", help="AWS region")
@click.option("--ecr-repo", default=None, help="ECR repository URI")
@click.option("--cpu", default="256", help="Task CPU units (256, 512, 1024, 2048, 4096)")
@click.option("--memory", default="512", help="Task memory MB (512, 1024, 2048, ...)")
def deploy_aws(app_name: str | None, region: str, ecr_repo: str | None, cpu: str, memory: str) -> None:
    """Generate AWS ECS/Fargate deployment files.

    \b
    Prerequisites:
        brew install awscli
        aws configure

    \b
    Example:
        fastx deploy aws --app-name my-api --ecr-repo 123456789.dkr.ecr.us-east-1.amazonaws.com/my-api
    """
    root = resolve_fastmvc_project_root(Path.cwd())
    name = app_name or root.name.replace("_", "-")

    _ensure_dockerfile(root)

    # Generate task definition
    task_def = json.loads(json.dumps(ECS_TASK_DEFINITION))
    task_def["family"] = name
    task_def["cpu"] = cpu
    task_def["memory"] = memory
    container = task_def["containerDefinitions"][0]
    container["name"] = name
    container["image"] = ecr_repo or f"<ECR_REPO_URI>/{name}:latest"
    container["logConfiguration"]["options"]["awslogs-group"] = f"/ecs/{name}"
    container["logConfiguration"]["options"]["awslogs-region"] = region

    deploy_dir = root / "deploy" / "aws"
    deploy_dir.mkdir(parents=True, exist_ok=True)

    task_def_path = deploy_dir / "task-definition.json"
    task_def_path.write_text(json.dumps(task_def, indent=2) + "\n")
    output.console.print(f"[green]✓[/green] {task_def_path.relative_to(root)}")

    # Generate deploy script
    deploy_script = deploy_dir / "deploy.sh"
    ecr_uri = ecr_repo or f"<ECR_REPO_URI>/{name}"
    deploy_script.write_text(f'''#!/bin/bash
set -euo pipefail

APP_NAME="{name}"
REGION="{region}"
ECR_REPO="{ecr_uri}"
TAG="${{GIT_SHA:-latest}}"

echo "=== Building Docker image ==="
docker build -t "$APP_NAME:$TAG" .

echo "=== Pushing to ECR ==="
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ECR_REPO"
docker tag "$APP_NAME:$TAG" "$ECR_REPO:$TAG"
docker push "$ECR_REPO:$TAG"

echo "=== Updating ECS service ==="
aws ecs update-service \\
    --cluster "$APP_NAME-cluster" \\
    --service "$APP_NAME-service" \\
    --force-new-deployment \\
    --region "$REGION"

echo "=== Done! ==="
''')
    deploy_script.chmod(0o755)
    output.console.print(f"[green]✓[/green] {deploy_script.relative_to(root)}")

    output.console.print(f"\n[bold]Next steps:[/bold]")
    output.console.print(f"  1. Create ECR repo:  [dim]aws ecr create-repository --repository-name {name} --region {region}[/dim]")
    output.console.print(f"  2. Create ECS cluster: [dim]aws ecs create-cluster --cluster-name {name}-cluster[/dim]")
    output.console.print(f"  3. Update ECR_REPO in deploy/aws/deploy.sh")
    output.console.print(f"  4. Run: [dim]./deploy/aws/deploy.sh[/dim]")


def _command_exists(cmd: str) -> bool:
    """Check if a shell command is available."""
    try:
        subprocess.run([cmd, "--version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
