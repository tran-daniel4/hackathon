from __future__ import annotations

from bottlenecks.models import FindingSignal, RepoSignals, RuleFinding
from bottlenecks.rules.base import finding
from graph.models import GraphFacts


def detect_cpu_heavy_request_path(graph_facts: GraphFacts, repo_signals: RepoSignals) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    for signal in repo_signals.cpu_calls:
        if not signal.enclosing_route_id:
            continue
        findings.append(finding(
            id=f"rf_cpu_hot_path_{len(findings) + 1:03d}",
            rule_id="cpu_heavy_request_path",
            risk_type="cpu_hot_path",
            category="runtime",
            title="CPU-heavy work in request path",
            severity_hint="medium",
            confidence=0.63,
            confidence_label="medium_static_signal",
            affected_node_ids=[signal.component_id],
            affected_route_ids=[signal.enclosing_route_id],
            evidence_ids=[signal.evidence_id],
            signals=[FindingSignal(
                type="cpu_call",
                file_path=signal.file_path,
                start_line=signal.start_line,
                end_line=signal.end_line,
                details={"operation": signal.operation},
            )],
            why="Potentially expensive CPU work appears inside a user-facing request path.",
            impact="CPU-bound work in request handlers can increase response time and reduce throughput under load.",
            recommendations=[
                "Move heavy transforms or export work to a background worker where possible.",
                "Cache or precompute repeated expensive results.",
            ],
            telemetry_needed_to_confirm=["CPU per request", "handler execution time", "worker saturation"],
        ))
    return findings
