from __future__ import annotations

from bottlenecks.models import FindingSignal, RepoSignals, RuleFinding
from bottlenecks.rules.base import finding
from graph.models import GraphFacts


def detect_blocking_io(graph_facts: GraphFacts, repo_signals: RepoSignals) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    for signal in repo_signals.file_io_calls:
        if not signal.enclosing_route_id and not signal.sync:
            continue
        findings.append(finding(
            id=f"rf_blocking_io_{len(findings) + 1:03d}",
            rule_id="blocking_io",
            risk_type="blocking_io",
            category="runtime",
            title="Blocking I/O in request path",
            severity_hint="high" if signal.sync and signal.enclosing_route_id else "medium",
            confidence=0.78,
            confidence_label="strong_static_signal",
            affected_node_ids=[signal.component_id],
            affected_route_ids=[signal.enclosing_route_id] if signal.enclosing_route_id else [],
            evidence_ids=[signal.evidence_id],
            signals=[FindingSignal(
                type="file_io",
                file_path=signal.file_path,
                start_line=signal.start_line,
                end_line=signal.end_line,
                details={"operation": signal.operation, "sync": signal.sync},
            )],
            why="Synchronous or potentially blocking I/O was detected close to a request handler.",
            impact="Blocking file or network I/O can occupy worker threads or the event loop and slow other requests.",
            recommendations=[
                "Switch to async/non-blocking I/O where the framework supports it.",
                "Move exports, downloads, or large file work to background processing.",
            ],
            telemetry_needed_to_confirm=["thread pool saturation", "event loop lag", "request timing"],
        ))
    return findings
