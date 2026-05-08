from __future__ import annotations

from bottlenecks.models import FindingSignal, RepoSignals, RuleFinding
from bottlenecks.rules.base import finding
from graph.models import GraphFacts


def detect_missing_timeout(graph_facts: GraphFacts, repo_signals: RepoSignals) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    for signal in repo_signals.http_calls:
        if signal.timeout_detected:
            continue
        findings.append(finding(
            id=f"rf_missing_timeout_{len(findings) + 1:03d}",
            rule_id="missing_timeout",
            risk_type="missing_timeout",
            category="integration",
            title="Outbound HTTP call without verified timeout",
            severity_hint="medium" if signal.enclosing_route_id else "low",
            confidence=0.76,
            confidence_label="strong_static_signal",
            affected_node_ids=[signal.component_id],
            affected_route_ids=[signal.enclosing_route_id] if signal.enclosing_route_id else [],
            evidence_ids=[signal.evidence_id],
            signals=[FindingSignal(
                type="http_call",
                file_path=signal.file_path,
                start_line=signal.start_line,
                end_line=signal.end_line,
                details={
                    "client": signal.client,
                    "target": signal.target_hint,
                    "timeout_detected": signal.timeout_detected,
                    "retry_detected": signal.retry_detected,
                },
            )],
            why="An outbound HTTP client call was detected without a verified timeout configuration.",
            impact="Without a timeout, a slow downstream dependency can keep request resources busy much longer than intended.",
            recommendations=[
                "Set a client timeout or cancellation deadline.",
                "Add retry with backoff only when the call is safe to retry.",
            ],
            telemetry_needed_to_confirm=["socket duration", "request timeout metrics", "thread/event-loop utilization"],
        ))
    return findings
