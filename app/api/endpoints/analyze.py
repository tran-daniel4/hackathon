import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from analyzers.file_index import FileIndex
from analyzers.orchestrator import AnalyzerOrchestrator
from bottlenecks.orchestrator import build_component_annotations, run_bottleneck_analysis
from core.config import settings
from core.repo_loader import clone_github_repo, load_repo_files
from graph.compat import graph_facts_to_arch_graph
from pipeline.llm_view_generator import generate_diagrams_hybrid
from pipeline.llm_wrapper import LLMConfig
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

        cfg = LLMConfig(base_url=settings.ollama_base_url)
        bottleneck_result, legacy_report = run_bottleneck_analysis(
            file_index=file_index,
            graph_facts=facts,
            config=cfg,
        )
        output = await generate_diagrams_hybrid(source["scan"], graph, legacy_report, config=cfg)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline error: {exc}",
        )

    component = next((view for view in output.views if view.id == "component"), output.views[0])
    component.annotations = build_component_annotations(bottleneck_result.report)
    severity_by_node = {
        item.node_id: ("high" if item.severity == "critical" else item.severity)
        for item in bottleneck_result.report.hot_nodes
    }
    for node in component.nodes:
        if node.id in severity_by_node:
            node.severity = severity_by_node[node.id]

    return AnalyzeResponse(
        repo_analysis=source["scan"].model_dump(),
        system_design=graph.model_dump(),
        bottlenecks=bottleneck_result.report.model_dump(),
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
                "bottleneck_count": len(bottleneck_result.report.findings),
                "hot_node_count": len(bottleneck_result.report.hot_nodes),
            },
            "repo_signals": {
                "counts": {
                    "routes": len(bottleneck_result.repo_signals.routes),
                    "http_calls": len(bottleneck_result.repo_signals.http_calls),
                    "db_calls": len(bottleneck_result.repo_signals.db_calls),
                    "loops": len(bottleneck_result.repo_signals.loops),
                    "cache_calls": len(bottleneck_result.repo_signals.cache_calls),
                    "queue_configs": len(bottleneck_result.repo_signals.queue_configs),
                    "file_io_calls": len(bottleneck_result.repo_signals.file_io_calls),
                    "logging_calls": len(bottleneck_result.repo_signals.logging_calls),
                    "cpu_calls": len(bottleneck_result.repo_signals.cpu_calls),
                },
                "sample_evidence_ids": [
                    *[route.evidence_id for route in bottleneck_result.repo_signals.routes[:2]],
                    *[call.evidence_id for call in bottleneck_result.repo_signals.http_calls[:2]],
                    *[call.evidence_id for call in bottleneck_result.repo_signals.db_calls[:2]],
                ],
                "raw": bottleneck_result.repo_signals.model_dump(),
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
