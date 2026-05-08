import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from pipeline.aggregator import aggregate
from pipeline.diagram_generator import generate_diagrams
from pipeline.graph_builder import build_graph
from pipeline.scanner import scan_files


def test_operational_view_synthesizes_runtime_pipeline_and_data_plane():
    scan = scan_files({
        "bookworm/app/web/package.json": """
{
  "dependencies": {
    "next": "15.0.0",
    "react": "19.0.0",
    "@auth0/nextjs-auth0": "3.0.0"
  }
}
""",
        "bookworm/app/api/requirements.txt": """
fastapi
asyncpg
redis
opentelemetry-sdk
sentry-sdk
""",
        "bookworm/docker-compose.yml": """
services:
  api:
    build: ./app/api
  redis:
    image: redis:7
""",
        "bookworm/infra/main.tf": """
terraform {
  required_providers {
    aws = {
      source = "hashicorp/aws"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}
""",
        "bookworm/.github/workflows/deploy.yml": """
name: deploy
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: npm test
      - run: terraform apply -auto-approve
""",
        "bookworm/app/api/.env.example": """
AUTH0_DOMAIN=tenant.us.auth0.com
DATABASE_URL=postgresql://localhost:5432/bookworm
REDIS_URL=redis://localhost:6379/0
""",
        "bookworm/app/api/routes.py": """
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}
""",
    })

    graph = build_graph(scan)
    output = generate_diagrams(scan, graph, aggregate([]))
    view = next(diagram for diagram in output.views if diagram.id == "operational")

    assert any(node.group == "cicd" and node.label == "Build" for node in view.nodes)
    assert any(node.group == "runtime" and "Terraform" in node.label for node in view.nodes)
    assert any(node.group == "runtime" and "AWS" in node.label for node in view.nodes)
    assert any(node.group == "runtime" and ("Docker" in node.label or "Container" in node.label) for node in view.nodes)
    assert any(node.group == "services" and node.type in {"frontend", "backend"} for node in view.nodes)
    assert any(node.group == "data" and node.label == "PostgreSQL" for node in view.nodes)
    assert any(node.group == "data" and node.label == "Redis" for node in view.nodes)
    assert any(node.group == "observability" and "OpenTelemetry" in node.label for node in view.nodes)
    assert any(node.group == "observability" and "Sentry" in node.label for node in view.nodes)
    assert any(node.group == "identity" and "Auth0" in node.label for node in view.nodes)

    assert any(edge.label == "Deploys infrastructure" for edge in view.edges)
    assert any(edge.label == "Runs workload" for edge in view.edges)
    assert any(edge.label == "Emits telemetry" for edge in view.edges)


if __name__ == "__main__":
    test_operational_view_synthesizes_runtime_pipeline_and_data_plane()
    print("operational tests passed")
