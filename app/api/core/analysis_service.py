from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from analyzers.file_index import FileIndex
from analyzers.orchestrator import AnalyzerOrchestrator
from bottlenecks.models import RepoSignals
from bottlenecks.orchestrator import build_component_annotations, run_bottleneck_analysis
from core.config import settings
from core.repo_loader import clone_github_repo, load_repo_files
from graph.compat import graph_facts_to_arch_graph
from pipeline.graph_builder import ArchGraph, Edge, Node
from pipeline.llm_view_generator import generate_diagrams_hybrid
from pipeline.llm_wrapper import LLMConfig
from pipeline.scanner import RepoScan, scan_files, scan_repo


@dataclass
class AnalysisBundle:
    payload: dict[str, Any]
    source: str
    repo_meta: dict[str, Any]
    component_count: int


async def execute_analysis(
    *,
    files: dict[str, str] | None = None,
    repo_url: str | None = None,
    repo_branch: str | None = None,
    github_token: str | None = None,
) -> AnalysisBundle:
    source = _prepare_analysis_source(
        files=files or {},
        repo_url=repo_url,
        repo_branch=repo_branch,
        github_token=github_token,
    )

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

    component = next((view for view in output.views if view.id == "component"), output.views[0])
    component.annotations = [
        *build_component_annotations(bottleneck_result.report),
        *_build_request_flow_annotations(graph, bottleneck_result.repo_signals, bottleneck_result.report.hot_nodes),
    ]
    severity_by_node = {
        item.node_id: ("high" if item.severity == "critical" else item.severity)
        for item in bottleneck_result.report.hot_nodes
    }
    for node in component.nodes:
        if node.id in severity_by_node:
            node.severity = severity_by_node[node.id]

    payload = {
        "repo_analysis": source["scan"].model_dump(),
        "system_design": graph.model_dump(),
        "bottlenecks": bottleneck_result.report.model_dump(),
        "diagram": {
            "nodes": [node.model_dump() for node in component.nodes],
            "edges": [edge.model_dump() for edge in component.edges],
            "annotations": component.annotations,
        },
        "diagrams": [view.model_dump() for view in output.views],
        "graph_facts": facts.model_dump(),
        "analysis_debug": {
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
    }

    return AnalysisBundle(
        payload=payload,
        source=source["source"],
        repo_meta=source["repo_meta"],
        component_count=len(component.nodes),
    )


def _prepare_analysis_source(
    *,
    files: dict[str, str],
    repo_url: str | None,
    repo_branch: str | None,
    github_token: str | None,
) -> dict[str, Any]:
    analyzed_at = datetime.now(timezone.utc).isoformat()

    if repo_url:
        snapshot = clone_github_repo(
            repo_url,
            branch=repo_branch,
            github_token=github_token,
        )
        try:
            repo_files = load_repo_files(snapshot.root)
            scan = scan_repo(snapshot.root)
        finally:
            snapshot.cleanup()

        return {
            "source": "github",
            "files": repo_files,
            "scan": scan,
            "repo_meta": {
                "name": snapshot.repo_name,
                "url": snapshot.repo_url,
                "branch": snapshot.branch,
                "commit_sha": snapshot.commit_sha,
                "analyzed_at": analyzed_at,
            },
        }

    if not files:
        raise ValueError("Provide either uploaded files or a GitHub repository URL")

    repo_name = _infer_uploaded_repo_name(files)
    return {
        "source": "upload",
        "files": files,
        "scan": scan_files(files),
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


def _build_request_flow_annotations(
    graph: ArchGraph,
    repo_signals: RepoSignals,
    hot_nodes: list[Any],
) -> list[dict[str, Any]]:
    node_by_id = {node.id: node for node in graph.nodes}
    edge_by_id = {f"{edge.source}--{edge.target}": edge for edge in graph.edges}
    incoming: dict[str, list[Edge]] = {}
    outgoing: dict[str, list[Edge]] = {}

    for edge in graph.edges:
        incoming.setdefault(edge.target, []).append(edge)
        outgoing.setdefault(edge.source, []).append(edge)

    frontend_ids = {node.id for node in graph.nodes if node.type == "frontend"}
    hot_node_ids = {item.node_id for item in hot_nodes}
    route_candidates: list[tuple[int, dict[str, Any]]] = []
    seen_components: set[str] = set()

    for route in sorted(repo_signals.routes, key=lambda item: (not item.public_endpoint, item.path, item.method)):
        component_id = route.component_id
        if component_id in seen_components or component_id not in node_by_id:
            continue

        ingress = _pick_ingress_edge(component_id, incoming, frontend_ids)
        cache_edge = _pick_edge_to_type(component_id, outgoing, node_by_id, {"cache"})
        db_edge = _pick_edge_to_type(component_id, outgoing, node_by_id, {"database"})
        external_edge = _pick_external_edge(component_id, outgoing, node_by_id, repo_signals, route.id)

        segments: list[dict[str, Any]] = []
        score = 0

        if ingress:
            segments.append(_segment(ingress))
            score += 1

        route_cache_calls = _matching_route_signals(repo_signals.cache_calls, route.id, component_id)
        route_db_calls = _matching_route_signals(repo_signals.db_calls, route.id, component_id)
        route_http_calls = _matching_route_signals(repo_signals.http_calls, route.id, component_id)

        if cache_edge and route_cache_calls:
            segments.append(_segment(cache_edge))
            segments.append(_segment(cache_edge, reverse=True))
            score += 2

        if db_edge and route_db_calls:
            segments.append(_segment(db_edge))
            segments.append(_segment(db_edge, reverse=True))
            score += 3 if cache_edge else 2

        if external_edge and route_http_calls:
            segments.append(_segment(external_edge))
            segments.append(_segment(external_edge, reverse=True))
            score += 2

        if ingress and len(segments) > 1:
            segments.append(_segment(ingress, reverse=True))

        if len(segments) < 2:
            continue

        seen_components.add(component_id)
        route_candidates.append((
            score + (1 if route.public_endpoint else 0),
            {
                "kind": "request_flow",
                "flowId": f"flow-{route.id}",
                "routeId": route.id,
                "componentId": component_id,
                "label": _flow_label(route, cache_edge is not None and db_edge is not None, external_edge is not None),
                "segments": segments,
                "bottleneck": component_id in hot_node_ids or any(
                    _segment_targets_hot(segment, edge_by_id, hot_node_ids) for segment in segments
                ),
            },
        ))

    route_candidates.sort(key=lambda item: (-item[0], item[1]["label"]))
    return [candidate for _, candidate in route_candidates[:3]]


def _matching_route_signals(signals: list[Any], route_id: str, component_id: str) -> list[Any]:
    exact = [signal for signal in signals if getattr(signal, "enclosing_route_id", None) == route_id]
    if exact:
        return exact
    return [signal for signal in signals if getattr(signal, "component_id", None) == component_id]


def _pick_ingress_edge(component_id: str, incoming: dict[str, list[Edge]], frontend_ids: set[str]) -> Edge | None:
    candidates = incoming.get(component_id, [])
    if not candidates:
        return None
    frontend_edge = next((edge for edge in candidates if edge.source in frontend_ids), None)
    return frontend_edge or candidates[0]


def _pick_edge_to_type(
    component_id: str,
    outgoing: dict[str, list[Edge]],
    node_by_id: dict[str, Node],
    target_types: set[str],
) -> Edge | None:
    for edge in outgoing.get(component_id, []):
        target = node_by_id.get(edge.target)
        if target and target.type in target_types:
            return edge
    return None


def _pick_external_edge(
    component_id: str,
    outgoing: dict[str, list[Edge]],
    node_by_id: dict[str, Node],
    repo_signals: RepoSignals,
    route_id: str,
) -> Edge | None:
    route_http_calls = [signal for signal in repo_signals.http_calls if signal.enclosing_route_id == route_id]
    external_edges = [
        edge for edge in outgoing.get(component_id, [])
        if node_by_id.get(edge.target) and node_by_id[edge.target].type == "external_api"
    ]
    if not external_edges:
        return None
    for call in route_http_calls:
        for edge in external_edges:
            target_label = node_by_id[edge.target].label.lower()
            target_id = edge.target.lower()
            if call.target_hint.lower() in target_label or call.target_hint.lower() in target_id:
                return edge
    return external_edges[0]


def _segment(edge: Edge, reverse: bool = False) -> dict[str, Any]:
    return {"edgeId": f"{edge.source}--{edge.target}", "reverse": reverse}


def _segment_targets_hot(segment: dict[str, Any], edge_by_id: dict[str, Edge], hot_node_ids: set[str]) -> bool:
    edge = edge_by_id.get(segment["edgeId"])
    if not edge:
        return False
    return edge.source in hot_node_ids or edge.target in hot_node_ids


def _flow_label(route: Any, has_cache_miss: bool, has_external_call: bool) -> str:
    base = f"{route.method} {route.path}"
    if has_cache_miss:
        return f"{base} cache-miss path"
    if has_external_call:
        return f"{base} external call path"
    return f"{base} request path"
