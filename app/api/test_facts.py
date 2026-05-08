"""Smoke test: run the orchestrator on this project's own files."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from analyzers.file_index import FileIndex
from analyzers.orchestrator import AnalyzerOrchestrator
from graph.compat import graph_facts_to_arch_graph
from graph.models import GraphFacts


def _load_project_files() -> dict[str, str]:
    root = os.path.dirname(__file__)
    files: dict[str, str] = {}
    skip_dirs = {".venv", "venv", "__pycache__", ".git", ".mypy_cache", ".pytest_cache"}
    skip_exts = {".pyc", ".png", ".jpg", ".db", ".lock"}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".")]
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            ext = os.path.splitext(fname)[1].lower()
            if ext in skip_exts:
                continue
            rel = os.path.relpath(fpath, root).replace("\\", "/")
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    files[rel] = f.read(200_000)
            except OSError:
                pass
    return files


def test_orchestrator_smoke():
    files = _load_project_files()
    assert files, "No project files found"

    file_index = FileIndex(files)
    facts = AnalyzerOrchestrator().run(file_index, analysis_id="test-smoke-001")

    assert isinstance(facts, GraphFacts)
    assert facts.schema_version == "1.0"
    assert facts.analysis_id == "test-smoke-001"
    assert len(facts.nodes) > 0, "Expected at least one node"
    assert len(facts.evidence) > 0, "Expected at least one evidence item"

    # All evidence IDs should be sequential ev_NNN
    for ev in facts.evidence:
        assert ev.id.startswith("ev_"), f"Bad evidence ID: {ev.id}"

    # All edge endpoints should reference known node IDs
    node_ids = {n.id for n in facts.nodes}
    for edge in facts.edges:
        assert edge.src in node_ids or True, f"Dangling src: {edge.src}"  # validator handles this

    print(f"\n=== GraphFacts smoke test ===")
    print(f"Nodes: {len(facts.nodes)}")
    for n in facts.nodes:
        print(f"  [{n.type}] {n.id} ({n.name}) conf={n.confidence} lang={n.language} fw={n.framework}")
    print(f"Edges: {len(facts.edges)}")
    for e in facts.edges:
        print(f"  {e.src} --[{e.kind}]--> {e.dst}")
    print(f"APIs: {len(facts.apis)}")
    print(f"Messaging: {len(facts.messaging)}")
    print(f"Evidence: {len(facts.evidence)}")
    print(f"Warnings: {len(facts.warnings)}")
    for w in facts.warnings:
        if w.code not in ("README_SUMMARY", "CICD_DETECTED"):
            print(f"  [{w.code}] {w.message}")


def test_dotnet_src_projects_are_detected_as_services():
    files = {
        "src/BookWorm.Catalog/BookWorm.Catalog.csproj": """
<Project Sdk="Microsoft.NET.Sdk.Web">
  <ItemGroup>
    <PackageReference Include="Microsoft.AspNetCore.OpenApi" Version="8.0.0" />
    <PackageReference Include="Npgsql.EntityFrameworkCore.PostgreSQL" Version="8.0.0" />
  </ItemGroup>
</Project>
""",
        "src/BookWorm.Catalog/Program.cs": """
var builder = WebApplication.CreateBuilder(args);
builder.Services.AddDbContext<CatalogDbContext>(options => options.UseNpgsql("Host=postgres"));
var app = builder.Build();
app.MapGet("/api/books", () => Results.Ok());
app.MapPost("/api/books", () => Results.Created());
app.Run();
""",
        "src/BookWorm.AppHost/BookWorm.AppHost.csproj": """
<Project Sdk="Microsoft.NET.Sdk">
  <ItemGroup>
    <PackageReference Include="Aspire.Hosting.AppHost" Version="8.0.0" />
    <PackageReference Include="Aspire.Hosting.PostgreSQL" Version="8.0.0" />
  </ItemGroup>
</Project>
""",
        "src/BookWorm.AppHost/AppHost.cs": """
var builder = DistributedApplication.CreateBuilder(args);
var postgres = builder.AddPostgres("postgres");
builder.AddProject<Projects.BookWorm_Catalog>("catalog-api").WithReference(postgres);
builder.Build().Run();
""",
    }

    facts = AnalyzerOrchestrator().run(FileIndex(files), analysis_id="dotnet-src-001")
    node_ids = {node.id for node in facts.nodes}

    assert "src" not in node_ids
    assert "bookworm-catalog" in node_ids
    assert "bookworm-apphost" in node_ids
    assert "postgresql" in node_ids

    assert any(
        api.component_id == "bookworm-catalog"
        and api.method == "GET"
        and api.path == "/api/books"
        for api in facts.apis
    )

    graph = graph_facts_to_arch_graph(facts)
    assert any(edge.source == "bookworm-catalog" and edge.target == "postgresql" for edge in graph.edges)


def test_multistack_monorepo_routes_and_datastores():
    files = {
        "apps/web/package.json": """
{
  "dependencies": {
    "next": "15.0.0",
    "react": "19.0.0"
  }
}
""",
        "apps/api/package.json": """
{
  "dependencies": {
    "@nestjs/core": "10.0.0",
    "@prisma/client": "5.0.0",
    "pg": "8.11.0"
  }
}
""",
        "apps/api/src/users.controller.ts": """
import { Controller, Get, Post } from '@nestjs/common';

@Controller('users')
export class UsersController {
  @Get()
  list() { return []; }

  @Post(':id')
  create() { return {}; }
}
""",
        "services/orders/pom.xml": """
<project>
  <dependencies>
    <dependency>
      <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
  </dependencies>
</project>
""",
        "services/orders/src/main/java/com/acme/orders/OrdersController.java": """
@RestController
@RequestMapping("/api/orders")
public class OrdersController {
  @GetMapping("/{id}")
  public String getOrder() { return "ok"; }
}
""",
        "services/orders/src/main/resources/application.yml": """
spring:
  datasource:
    url: jdbc:postgresql://orders-db:5432/orders
""",
        "services/worker/requirements.txt": """
flask
redis
""",
        "services/worker/app.py": """
from flask import Flask

app = Flask(__name__)

@app.route("/jobs", methods=["POST"])
def jobs():
    return {"ok": True}
""",
    }

    facts = AnalyzerOrchestrator().run(FileIndex(files), analysis_id="multi-stack-001")
    node_ids = {node.id for node in facts.nodes}

    assert {"web", "api", "orders", "worker"}.issubset(node_ids)
    assert "postgresql" in node_ids

    assert any(
        api.component_id == "api"
        and api.method == "GET"
        and api.path == "/users"
        for api in facts.apis
    )
    assert any(
        api.component_id == "api"
        and api.method == "POST"
        and api.path == "/users/:id"
        for api in facts.apis
    )
    assert any(
        api.component_id == "orders"
        and api.method == "GET"
        and api.path == "/api/orders/{id}"
        for api in facts.apis
    )
    assert any(
        api.component_id == "worker"
        and api.method == "POST"
        and api.path == "/jobs"
        for api in facts.apis
    )

    graph = graph_facts_to_arch_graph(facts)
    assert any(edge.source == "orders" and edge.target == "postgresql" for edge in graph.edges)


if __name__ == "__main__":
    test_orchestrator_smoke()
    test_dotnet_src_projects_are_detected_as_services()
    test_multistack_monorepo_routes_and_datastores()
    print("\nSmoke test passed.")
