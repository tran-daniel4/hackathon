from __future__ import annotations

from bottlenecks.models import FindingSignal, RepoSignals, RuleFinding
from bottlenecks.rules.base import finding
from graph.models import GraphFacts


def detect_unbounded_queue_or_missing_dlq(graph_facts: GraphFacts, repo_signals: RepoSignals) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    for signal in repo_signals.queue_configs:
        risky = (not signal.dlq_detected) or (signal.retry_detected and not signal.backoff_detected) or signal.concurrency_limit is None
        if not risky:
            continue
        findings.append(finding(
            id=f"rf_queue_risk_{len(findings) + 1:03d}",
            rule_id="unbounded_queue_or_missing_dlq",
            risk_type="queue_backlog_risk",
            category="messaging",
            title="Queue reliability configuration gap",
            severity_hint="medium",
            confidence=0.67,
            confidence_label="medium_static_signal",
            affected_node_ids=[signal.component_id],
            evidence_ids=[signal.evidence_id] if signal.evidence_id else [],
            signals=[FindingSignal(
                type="queue_config",
                file_path=signal.file_path,
                start_line=signal.start_line,
                end_line=signal.end_line,
                details={
                    "queue_name": signal.queue_name,
                    "dlq_detected": signal.dlq_detected,
                    "retry_detected": signal.retry_detected,
                    "backoff_detected": signal.backoff_detected,
                    "concurrency_limit": signal.concurrency_limit,
                },
            )],
            why="Queue configuration suggests missing dead-letter handling, backoff, or concurrency controls.",
            impact="Poison messages or retry bursts can increase backlog risk and make recovery slower under failure.",
            recommendations=[
                "Configure a dead-letter queue for failed messages.",
                "Add retry backoff and explicit concurrency or prefetch limits.",
            ],
            telemetry_needed_to_confirm=["queue depth", "retry counts", "consumer lag"],
        ))
    return findings
