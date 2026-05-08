import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from analyzers.file_index import FileIndex
from analyzers.orchestrator import AnalyzerOrchestrator
from core.config import settings
from core.repo_loader import clone_github_repo, load_repo_files
from graph.compat import graph_facts_to_arch_graph
from pipeline.aggregator import aggregate
from pipeline.llm_view_generator import generate_diagrams_hybrid
from pipeline.llm_wrapper import LLMConfig, enrich_issues
from pipeline.rules_engine import run_rules
from pipeline.scanner import RepoScan, scan_files, scan_repo

router = APIRouter(prefix="/analyze", tags=["analyze"])


class AnalyzeRequest(BaseModel):
    file_tree: str = ""
    files: dict[str, str] = Field(default_factory=dict)
    repo_url: str | None = None
    repo_branch: str | None = None
    github_token: str | None = None


class AnalyzeResponse(BaseModel):
    repo_analysis: dict
    system_design: dict
    bottlenecks: dict
    diagram: dict
    diagrams: list[dict]
    graph_facts: dict
    analysis_debug: dict


@router.post("", response_model=AnalyzeResponse)
async def analyze(body: AnalyzeRequest):
    try:
        source = await asyncio.to_thread(_prepare_analysis_source, body)

        file_index = FileIndex(source["files"])
        facts = AnalyzerOrchestrator().run(file_index, repo_meta=source["repo_meta"])
        graph = graph_facts_to_arch_graph(facts)

        issues = run_rules(source["scan"], graph)
        cfg = LLMConfig(base_url=settings.ollama_base_url)
        enriched = enrich_issues(issues, graph, config=cfg)
        report = aggregate(enriched)
        output = await generate_diagrams_hybrid(source["scan"], graph, report, config=cfg)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline error: {exc}",
        )

    component = next((view for view in output.views if view.id == "component"), output.views[0])

    return AnalyzeResponse(
        repo_analysis=source["scan"].model_dump(),
        system_design=graph.model_dump(),
        bottlenecks=report.model_dump(),
        diagram={
            "nodes": [node.model_dump() for node in component.nodes],
            "edges": [edge.model_dump() for edge in component.edges],
            "annotations": component.annotations,
        },
        diagrams=[view.model_dump() for view in output.views],
        graph_facts=facts.model_dump(),
        analysis_debug={
            "source": source["source"],
            "repo": facts.repo.model_dump(),
            "summary": {
                "input_file_count": len(source["files"]),
                "service_count": len(source["scan"].services),
                "framework_count": len(source["scan"].frameworks),
                "api_count": len(facts.apis),
                "node_count": len(facts.nodes),
                "edge_count": len(facts.edges),
                "warning_count": len(facts.warnings),
            },
        },
    )


def _prepare_analysis_source(body: AnalyzeRequest) -> dict[str, Any]:
    analyzed_at = datetime.now(timezone.utc).isoformat()

    if body.repo_url:
        snapshot = clone_github_repo(
            body.repo_url,
            branch=body.repo_branch,
            github_token=body.github_token,
        )
        try:
            files = load_repo_files(snapshot.root)
            scan = scan_repo(snapshot.root)
        finally:
            snapshot.cleanup()

        return {
            "source": "github",
            "files": files,
            "scan": scan,
            "repo_meta": {
                "name": snapshot.repo_name,
                "url": snapshot.repo_url,
                "branch": snapshot.branch,
                "commit_sha": snapshot.commit_sha,
                "analyzed_at": analyzed_at,
            },
        }

    if not body.files:
        raise ValueError("Provide either uploaded files or a GitHub repository URL")

    repo_name = _infer_uploaded_repo_name(body.files)
    return {
        "source": "upload",
        "files": body.files,
        "scan": scan_files(body.files),
        "repo_meta": {
            "name": repo_name,
            "analyzed_at": analyzed_at,
        },
    }


def _infer_uploaded_repo_name(files: dict[str, str]) -> str:
    if not files:
        return "uploaded"
    first_path = next(iter(files)).replace("\\", "/")
    return first_path.split("/", 1)[0] if "/" in first_path else "uploaded"
