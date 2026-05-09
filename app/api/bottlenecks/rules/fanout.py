from __future__ import annotations

from bottlenecks.models import RepoSignals, RuleFinding
from bottlenecks.rules.base import finding
from graph.models import GraphFacts

_SYNC_KINDS = {"http", "grpc", "sdk"}


def detect_fanout(graph_facts: GraphFacts, repo_signals: RepoSignals) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    for node in graph_facts.nodes:
        if node.type not in {"service", "gateway"}:
            continue
        outgoing = [edge for edge in graph_facts.edges if edge.src == node.id and edge.kind in _SYNC_KINDS]
        if len(outgoing) < 4:
            continue
        findings.append(finding(
            id=f"rf_fanout_{len(findings) + 1:03d}",
            rule_id="fanout",
            risk_type="fanout",
            category="architecture",
            title="Chatty downstream fanout",
            severity_hint="medium",
            confidence=0.70,
            confidence_label="strong_static_signal",
            affected_node_ids=[node.id, *[edge.dst for edge in outgoing]],
            affected_edge_ids=[edge.id for edge in outgoing],
            evidence_ids=[eid for edge in outgoing for eid in edge.evidence_ids],
            why="One component makes many synchronous downstream calls.",
            impact="Request latency and failure probability can grow as every downstream call contributes its own delay and instability.",
            recommendations=[
                "Parallelize independent downstream calls where possible.",
                "Introduce an aggregator or cache for repeated fanout patterns.",
            ],
            telemetry_needed_to_confirm=["downstream call counts per request", "trace fanout timing"],
        ))
    return findings
