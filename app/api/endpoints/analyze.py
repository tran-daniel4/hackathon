from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from core.config import settings
from pipeline.scanner import scan_files
from pipeline.rules_engine import run_rules
from pipeline.llm_wrapper import LLMConfig, enrich_issues
from pipeline.aggregator import aggregate
from pipeline.llm_view_generator import generate_diagrams_hybrid
from analyzers.file_index import FileIndex
from analyzers.orchestrator import AnalyzerOrchestrator
from graph.compat import graph_facts_to_arch_graph

router = APIRouter(prefix="/analyze", tags=["analyze"])


class AnalyzeRequest(BaseModel):
    file_tree: str           # newline-separated paths (informational)
    files: dict[str, str]    # webkitRelativePath → file content


class AnalyzeResponse(BaseModel):
    repo_analysis: dict
    system_design: dict
    bottlenecks: dict
    diagram: dict        # component view — keeps current frontend contract
    diagrams: list[dict] # all 4 views — for future multi-view UI
    graph_facts: dict    # new — structured evidence graph


@router.post("", response_model=AnalyzeResponse)
async def analyze(body: AnalyzeRequest):
    try:
        # New deterministic analyzer → graph_facts.json
        file_index = FileIndex(body.files)
        facts = AnalyzerOrchestrator().run(
            file_index,
            repo_meta={
                "name": "uploaded",
                "analyzed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        graph = graph_facts_to_arch_graph(facts)

        # Keep the old scanner for the LLM layer (env_vars, auth_patterns, etc.)
        scan = scan_files(body.files)

        issues   = run_rules(scan, graph)
        cfg      = LLMConfig(base_url=settings.ollama_base_url)
        enriched = enrich_issues(issues, graph, config=cfg)
        report   = aggregate(enriched)
        output   = await generate_diagrams_hybrid(scan, graph, report, config=cfg)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline error: {exc}",
        )

    component = next((v for v in output.views if v.id == "component"), output.views[0])

    return AnalyzeResponse(
        repo_analysis=scan.model_dump(),
        system_design=graph.model_dump(),
        bottlenecks=report.model_dump(),
        diagram={
            "nodes":       [n.model_dump() for n in component.nodes],
            "edges":       [e.model_dump() for e in component.edges],
            "annotations": component.annotations,
        },
        diagrams=[v.model_dump() for v in output.views],
        graph_facts=facts.model_dump(),
    )
