from __future__ import annotations

from bottlenecks.models import FindingSignal, RepoSignals, RuleFinding
from bottlenecks.rules.base import finding
from graph.models import GraphFacts


def detect_n_plus_one(graph_facts: GraphFacts, repo_signals: RepoSignals) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    for db_call in repo_signals.db_calls:
        if not db_call.inside_loop_id:
            continue
        findings.append(finding(
            id=f"rf_n_plus_one_{len(findings) + 1:03d}",
            rule_id="n_plus_one",
            risk_type="n_plus_one",
            category="database",
            title="Possible N+1 database query",
            severity_hint="high",
            confidence=0.82,
            confidence_label="very_strong_static_signal",
            affected_node_ids=[db_call.component_id],
            affected_route_ids=[db_call.enclosing_route_id] if db_call.enclosing_route_id else [],
            evidence_ids=[db_call.evidence_id, db_call.inside_loop_id],
            signals=[FindingSignal(
                type="db_call",
                file_path=db_call.file_path,
                start_line=db_call.start_line,
                end_line=db_call.end_line,
                details={"operation": db_call.operation, "model": db_call.table_or_model},
            )],
            why="A database or repository call was detected inside a loop.",
            impact="Query count can grow with the size of the returned collection, increasing latency and database load.",
            recommendations=[
                "Batch related lookups in a single query.",
                "Use eager loading, joins, or include/select-related patterns.",
            ],
            telemetry_needed_to_confirm=["query count per request", "slow query logs", "endpoint P95/P99 latency"],
        ))
    return findings
