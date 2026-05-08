from __future__ import annotations

from bottlenecks.models import FindingSignal, RepoSignals, RuleFinding
from bottlenecks.rules.base import finding
from graph.models import GraphFacts


def detect_external_dependency_in_request_path(graph_facts: GraphFacts, repo_signals: RepoSignals) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    for signal in repo_signals.http_calls:
        if not signal.enclosing_route_id or not signal.external_provider:
            continue
        related_edges = [
            edge for edge in graph_facts.edges
            if edge.src == signal.component_id and edge.kind in {"http", "sdk"} and signal.target_hint in edge.dst
        ]
        severity = "high" if (not signal.timeout_detected and not signal.circuit_breaker_detected) else "medium"
        findings.append(finding(
            id=f"rf_external_dependency_{len(findings) + 1:03d}",
            rule_id="external_dependency_in_request_path",
            risk_type="external_dependency_risk",
            category="integration",
            title="External dependency in request path",
            severity_hint=severity,
            confidence=0.74,
            confidence_label="strong_static_signal",
            affected_node_ids=[signal.component_id],
            affected_edge_ids=[edge.id for edge in related_edges],
            affected_route_ids=[signal.enclosing_route_id],
            evidence_ids=[signal.evidence_id, *[eid for edge in related_edges for eid in edge.evidence_ids]],
            signals=[FindingSignal(
                type="http_call",
                file_path=signal.file_path,
                start_line=signal.start_line,
                end_line=signal.end_line,
                details={"client": signal.client, "target": signal.target_hint},
            )],
            why="An outbound dependency call occurs inside a request path.",
            impact="Third-party or cross-service latency can directly delay the user-facing request and amplify failure risk.",
            recommendations=[
                "Add timeouts and defensive fallbacks around the dependency.",
                "Move non-essential external work to a background flow if possible.",
            ],
            telemetry_needed_to_confirm=["request traces", "dependency latency", "rate-limit/error responses"],
        ))
    return findings
