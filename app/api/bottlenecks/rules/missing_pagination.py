from __future__ import annotations

from bottlenecks.evidence import is_collection_path
from bottlenecks.models import FindingSignal, RepoSignals, RuleFinding
from bottlenecks.rules.base import finding
from graph.models import GraphFacts


def detect_missing_pagination(graph_facts: GraphFacts, repo_signals: RepoSignals) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    calls_by_route: dict[str, list] = {}
    for db_call in repo_signals.db_calls:
        if db_call.enclosing_route_id:
            calls_by_route.setdefault(db_call.enclosing_route_id, []).append(db_call)
    for route in repo_signals.routes:
        if route.method.upper() != "GET" or not is_collection_path(route.path):
            continue
        db_calls = calls_by_route.get(route.id, [])
        if not db_calls:
            continue
        has_pagination = bool(route.pagination_params) or any(call.has_limit for call in db_calls)
        if has_pagination:
            continue
        findings.append(finding(
            id=f"rf_missing_pagination_{len(findings) + 1:03d}",
            rule_id="missing_pagination",
            risk_type="missing_pagination",
            category="api",
            title="Collection endpoint without clear pagination",
            severity_hint="medium",
            confidence=0.76,
            confidence_label="strong_static_signal",
            affected_node_ids=[route.component_id],
            affected_route_ids=[route.id],
            evidence_ids=[route.evidence_id, *[call.evidence_id for call in db_calls]],
            signals=[FindingSignal(
                type="route",
                file_path=route.file_path,
                start_line=route.start_line,
                end_line=route.end_line,
                details={"method": route.method, "path": route.path},
            )],
            why="A collection-style GET endpoint does not appear to enforce pagination.",
            impact="Large result sets can increase database work, response size, and memory pressure as datasets grow.",
            recommendations=[
                "Add limit/offset, cursor, page, or take/skip parameters.",
                "Enforce server-side default page sizes for collection endpoints.",
            ],
            telemetry_needed_to_confirm=["response size", "rows scanned", "endpoint latency under large datasets"],
        ))
    return findings
