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


@deploy_group.command(name="gcp")
@click.option("--app-name", "-n", default=None, help="Cloud Run service name")
@click.option("--region", "-r", default="us-central1", help="GCP region")
@click.option("--project", "-p", default=None, help="GCP project ID")
@click.option("--memory", default="512Mi", help="Memory limit (e.g. 512Mi, 1Gi)")
@click.option("--cpu", default="1", help="CPU limit (1, 2, 4)")
@click.option("--min-instances", default=0, type=int, help="Minimum instances (0 = scale to zero)")
@click.option("--max-instances", default=10, type=int, help="Maximum instances")
def deploy_gcp(
    app_name: str | None,
    region: str,
    project: str | None,
    memory: str,
    cpu: str,
    min_instances: int,
    max_instances: int,
) -> None:
    """Deploy to Google Cloud Run.

    \b
    Prerequisites:
        brew install google-cloud-sdk
        gcloud auth login
        gcloud config set project <PROJECT_ID>

    \b
    Example:
        fastx deploy gcp --app-name my-api --project my-gcp-project
        fastx deploy gcp --region europe-west1 --memory 1Gi --cpu 2
    """
    root = resolve_fastmvc_project_root(Path.cwd())
    name = app_name or root.name.replace("_", "-")

    if not _command_exists("gcloud"):
        output.console.print("[red]gcloud CLI not found. Install: brew install google-cloud-sdk[/red]")
        return

    _ensure_dockerfile(root)

    # Generate Cloud Run service YAML
    deploy_dir = root / "deploy" / "gcp"
    deploy_dir.mkdir(parents=True, exist_ok=True)

    service_yaml = deploy_dir / "service.yaml"
    project_id = project or "<PROJECT_ID>"
    service_yaml.write_text(f"""apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: {name}
  annotations:
    run.googleapis.com/ingress: all
spec:
  template:
    metadata:
      annotations:
        autoscaling.knative.dev/minScale: "{min_instances}"
        autoscaling.knative.dev/maxScale: "{max_instances}"
    spec:
      containerConcurrency: 80
      containers:
        - image: gcr.io/{project_id}/{name}:latest
          ports:
            - containerPort: 8000
          resources:
            limits:
              memory: {memory}
              cpu: "{cpu}"
          startupProbe:
            httpGet:
              path: /health/live
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
            failureThreshold: 3
          livenessProbe:
            httpGet:
              path: /health/live
              port: 8000
            periodSeconds: 15
""")
    output.console.print(f"[green]✓[/green] {service_yaml.relative_to(root)}")

    # Generate deploy script
    deploy_script = deploy_dir / "deploy.sh"
    deploy_script.write_text(f'''#!/bin/bash
set -euo pipefail

APP_NAME="{name}"
REGION="{region}"
PROJECT="{project_id}"
TAG="${{GIT_SHA:-latest}}"

echo "=== Building and pushing to GCR ==="
gcloud builds submit --tag "gcr.io/$PROJECT/$APP_NAME:$TAG" .

echo "=== Deploying to Cloud Run ==="
gcloud run deploy "$APP_NAME" \\
    --image "gcr.io/$PROJECT/$APP_NAME:$TAG" \\
    --platform managed \\
    --region "$REGION" \\
    --port 8000 \\
    --memory {memory} \\
    --cpu {cpu} \\
    --min-instances {min_instances} \\
    --max-instances {max_instances} \\
    --allow-unauthenticated

echo "=== Service URL ==="
gcloud run services describe "$APP_NAME" --region "$REGION" --format "value(status.url)"
''')
    deploy_script.chmod(0o755)
    output.console.print(f"[green]✓[/green] {deploy_script.relative_to(root)}")

    output.console.print(f"\n[bold]Next steps:[/bold]")
    if project is None:
        output.console.print(f"  1. Set your project: [dim]gcloud config set project <PROJECT_ID>[/dim]")
        output.console.print(f"  2. Update PROJECT in deploy/gcp/deploy.sh")
        output.console.print(f"  3. Run: [dim]./deploy/gcp/deploy.sh[/dim]")
    else:
        output.console.print(f"  1. Run: [dim]./deploy/gcp/deploy.sh[/dim]")


@deploy_group.command(name="azure")
@click.option("--app-name", "-n", default=None, help="Container App name")
@click.option("--region", "-r", default="eastus", help="Azure region")
@click.option("--resource-group", "-g", default=None, help="Resource group name")
@click.option("--registry", default=None, help="Azure Container Registry name (e.g. myregistry.azurecr.io)")
@click.option("--cpu", default="0.5", help="CPU cores (0.25, 0.5, 1, 2, 4)")
@click.option("--memory", default="1.0Gi", help="Memory (e.g. 0.5Gi, 1.0Gi, 2.0Gi)")
@click.option("--min-replicas", default=0, type=int, help="Minimum replicas (0 = scale to zero)")
@click.option("--max-replicas", default=10, type=int, help="Maximum replicas")
def deploy_azure(
    app_name: str | None,
    region: str,
    resource_group: str | None,
    registry: str | None,
    cpu: str,
    memory: str,
    min_replicas: int,
    max_replicas: int,
) -> None:
    """Deploy to Azure Container Apps.

    \b
    Prerequisites:
        brew install azure-cli
        az login
        az extension add --name containerapp

    \b
    Example:
        fastx deploy azure --app-name my-api --resource-group my-rg
        fastx deploy azure --registry myregistry.azurecr.io --cpu 1 --memory 2.0Gi
    """
    root = resolve_fastmvc_project_root(Path.cwd())
    name = app_name or root.name.replace("_", "-")

    if not _command_exists("az"):
        output.console.print("[red]Azure CLI not found. Install: brew install azure-cli[/red]")
        return

    _ensure_dockerfile(root)

    rg = resource_group or f"{name}-rg"
    acr = registry or f"<REGISTRY_NAME>.azurecr.io"

    # Generate Azure Container App config
    deploy_dir = root / "deploy" / "azure"
    deploy_dir.mkdir(parents=True, exist_ok=True)

    container_app_yaml = deploy_dir / "container-app.yaml"
    container_app_yaml.write_text(f"""name: {name}
resourceGroup: {rg}
location: {region}
properties:
  configuration:
    ingress:
      external: true
      targetPort: 8000
      transport: auto
    registries:
      - server: {acr}
  template:
    containers:
      - name: {name}
        image: {acr}/{name}:latest
        resources:
          cpu: {cpu}
          memory: {memory}
        probes:
          - type: liveness
            httpGet:
              path: /health/live
              port: 8000
            periodSeconds: 15
          - type: readiness
            httpGet:
              path: /health/ready
              port: 8000
            periodSeconds: 10
          - type: startup
            httpGet:
              path: /health/live
              port: 8000
            failureThreshold: 3
            periodSeconds: 10
    scale:
      minReplicas: {min_replicas}
      maxReplicas: {max_replicas}
""")
    output.console.print(f"[green]✓[/green] {container_app_yaml.relative_to(root)}")

    # Generate deploy script
    deploy_script = deploy_dir / "deploy.sh"
    deploy_script.write_text(f'''#!/bin/bash
set -euo pipefail

APP_NAME="{name}"
REGION="{region}"
RESOURCE_GROUP="{rg}"
ACR="{acr}"
TAG="${{GIT_SHA:-latest}}"

echo "=== Ensuring resource group ==="
az group create --name "$RESOURCE_GROUP" --location "$REGION" 2>/dev/null || true

echo "=== Building and pushing to ACR ==="
az acr build --registry "${{ACR%%.*}}" --image "$APP_NAME:$TAG" .

echo "=== Creating/Updating Container App ==="
az containerapp up \\
    --name "$APP_NAME" \\
    --resource-group "$RESOURCE_GROUP" \\
    --location "$REGION" \\
    --image "$ACR/$APP_NAME:$TAG" \\
    --target-port 8000 \\
    --ingress external \\
    --cpu {cpu} \\
    --memory {memory} \\
    --min-replicas {min_replicas} \\
    --max-replicas {max_replicas}

echo "=== Application URL ==="
az containerapp show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" \\
    --query "properties.configuration.ingress.fqdn" -o tsv
''')
    deploy_script.chmod(0o755)
    output.console.print(f"[green]✓[/green] {deploy_script.relative_to(root)}")

    output.console.print(f"\n[bold]Next steps:[/bold]")
    steps = []
    if registry is None:
        steps.append(f"  Create ACR: [dim]az acr create --name <registry> --resource-group {rg} --sku Basic[/dim]")
        steps.append(f"  Update ACR in deploy/azure/deploy.sh")
    steps.append(f"  Run: [dim]./deploy/azure/deploy.sh[/dim]")
    for i, step in enumerate(steps, 1):
        output.console.print(f"  {i}. {step}")


def _command_exists(cmd: str) -> bool:
    """Check if a shell command is available."""
    try:
        subprocess.run([cmd, "--version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
