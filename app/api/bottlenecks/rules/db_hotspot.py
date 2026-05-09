from __future__ import annotations

from bottlenecks.models import RepoSignals, RuleFinding
from bottlenecks.rules.base import finding
from graph.models import GraphFacts


def detect_db_hotspot(graph_facts: GraphFacts, repo_signals: RepoSignals) -> list[RuleFinding]:
    database_ids = {node.id for node in graph_facts.nodes if node.type == "database"}
    findings: list[RuleFinding] = []
    for db_id in database_ids:
        readers = [edge for edge in graph_facts.edges if edge.dst == db_id and edge.kind == "read"]
        reader_ids = sorted({edge.src for edge in readers})
        if len(reader_ids) < 4:
            continue
        findings.append(finding(
            id=f"rf_db_hotspot_{len(findings) + 1:03d}",
            rule_id="db_hotspot",
            risk_type="db_hotspot",
            category="database",
            title="Potential shared database read hotspot",
            severity_hint="medium",
            confidence=0.65,
            confidence_label="medium_static_signal",
            affected_node_ids=[db_id, *reader_ids],
            affected_edge_ids=[edge.id for edge in readers],
            evidence_ids=[eid for edge in readers for eid in edge.evidence_ids],
            why="Many components read from the same database dependency.",
            impact="A single shared read path can become a concentration point for latency and connection pressure.",
            recommendations=[
                "Introduce caching or read replicas for the heaviest read paths.",
                "Review whether all readers need direct database access.",
            ],
            telemetry_needed_to_confirm=["read QPS by consumer", "slow query logs", "pool wait time"],
        ))
    return findings
