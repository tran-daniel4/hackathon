from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from core.config import settings
from pipeline.scanner import scan_files
from pipeline.graph_builder import build_graph
from pipeline.rules_engine import run_rules
from pipeline.llm_wrapper import LLMConfig, enrich_issues
from pipeline.aggregator import aggregate
from pipeline.llm_view_generator import generate_diagrams_hybrid

router = APIRouter(prefix="/analyze", tags=["analyze"])


class AnalyzeRequest(BaseModel):
    file_tree: str           # newline-separated paths (informational, not used by scanner)
    files: dict[str, str]    # webkitRelativePath → file content


class AnalyzeResponse(BaseModel):
    repo_analysis: dict
    system_design: dict
    bottlenecks: dict
    diagram: dict        # component view — keeps current frontend contract
    diagrams: list[dict] # all 4 views — for future multi-view UI


@router.post("", response_model=AnalyzeResponse)
async def analyze(body: AnalyzeRequest):
    try:
        scan     = scan_files(body.files)
        graph    = build_graph(scan)
        issues   = run_rules(scan, graph)   # N+1 rule skipped (no local path)
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
    )
