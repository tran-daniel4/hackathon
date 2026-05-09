from __future__ import annotations

from bottlenecks.models import FindingSignal, RepoSignals, RuleFinding
from bottlenecks.rules.base import finding
from graph.models import GraphFacts


def detect_excessive_logging(graph_facts: GraphFacts, repo_signals: RepoSignals) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    for signal in repo_signals.logging_calls:
        risky = signal.inside_loop_id is not None or (signal.enclosing_route_id is not None and (signal.logs_payload or signal.debug_logging))
        if not risky:
            continue
        findings.append(finding(
            id=f"rf_excessive_logging_{len(findings) + 1:03d}",
            rule_id="excessive_logging",
            risk_type="over_logging",
            category="runtime",
            title="Potential excessive logging in hot path",
            severity_hint="low" if signal.debug_logging else "medium",
            confidence=0.62,
            confidence_label="medium_static_signal",
            affected_node_ids=[signal.component_id],
            affected_route_ids=[signal.enclosing_route_id] if signal.enclosing_route_id else [],
            evidence_ids=[signal.evidence_id, signal.inside_loop_id] if signal.inside_loop_id else [signal.evidence_id],
            signals=[FindingSignal(
                type="logging",
                file_path=signal.file_path,
                start_line=signal.start_line,
                end_line=signal.end_line,
                details={"level": signal.level, "logs_payload": signal.logs_payload, "inside_loop": signal.inside_loop_id is not None},
            )],
            why="Verbose or payload-heavy logging appears in a request or loop hot path.",
            impact="Frequent logging can increase CPU, I/O, and observability cost, especially under burst traffic.",
            recommendations=[
                "Reduce log level in hot loops or high-volume request middleware.",
                "Avoid logging full payload bodies on normal request paths.",
            ],
            telemetry_needed_to_confirm=["log volume by route", "logger I/O time", "CPU overhead from logging"],
        ))
    return findings
