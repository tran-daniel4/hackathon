from __future__ import annotations

from bottlenecks.models import RepoSignals, RuleFinding
from bottlenecks.rules.base import finding
from graph.models import GraphFacts


def detect_shared_database(graph_facts: GraphFacts, repo_signals: RepoSignals) -> list[RuleFinding]:
    database_ids = {node.id for node in graph_facts.nodes if node.type == "database"}
    findings: list[RuleFinding] = []
    for db_id in database_ids:
        writers = [edge for edge in graph_facts.edges if edge.dst == db_id and edge.kind == "write"]
        writer_ids = sorted({edge.src for edge in writers})
        if len(writer_ids) < 2:
            continue
        findings.append(finding(
            id=f"rf_shared_database_{len(findings) + 1:03d}",
            rule_id="shared_database",
            risk_type="shared_database",
            category="database",
            title="Shared database write hotspot",
            severity_hint="high",
            confidence=0.78,
            confidence_label="strong_static_signal",
            affected_node_ids=[db_id, *writer_ids],
            affected_edge_ids=[edge.id for edge in writers],
            evidence_ids=[eid for edge in writers for eid in edge.evidence_ids],
            why="Multiple services write to the same database.",
            impact="Shared write ownership can increase coupling, contention risk, and operational fragility around schema changes or pool pressure.",
            recommendations=[
                "Clarify one service as the write owner for this datastore.",
                "Split workloads or use APIs/events instead of direct shared writes.",
            ],
            telemetry_needed_to_confirm=["connection pool utilization", "database write latency", "lock wait metrics"],
        ))
    return findings
