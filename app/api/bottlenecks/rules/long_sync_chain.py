from __future__ import annotations

from bottlenecks.models import FindingSignal, RepoSignals, RuleFinding
from bottlenecks.rules.base import finding
from graph.models import GraphFacts

_SYNC_KINDS = {"http", "grpc", "sdk"}


def detect_long_sync_chain(graph_facts: GraphFacts, repo_signals: RepoSignals) -> list[RuleFinding]:
    evidence_by_id = {item.id: item for item in graph_facts.evidence}
    outgoing: dict[str, list] = {}
    for edge in graph_facts.edges:
        if edge.kind not in _SYNC_KINDS:
            continue
        outgoing.setdefault(edge.src, []).append(edge)
    starts = [node.id for node in graph_facts.nodes if node.type in {"client", "gateway", "service"}]
    findings: list[RuleFinding] = []
    seen: set[tuple[str, ...]] = set()

    def dfs(node_id: str, path_nodes: list[str], path_edges: list) -> None:
        if len(path_edges) >= 4:
            key = tuple(path_nodes)
            if key in seen:
                return
            seen.add(key)
            severity = "high" if len(path_edges) >= 4 else "medium"
            evidence_ids = [eid for edge in path_edges for eid in edge.evidence_ids]
            first_evidence = next((evidence_by_id[eid] for eid in evidence_ids if eid in evidence_by_id), None)
            findings.append(finding(
                id=f"rf_long_sync_chain_{len(findings) + 1:03d}",
                rule_id="long_sync_chain",
                risk_type="long_sync_chain",
                category="architecture",
                title="Long synchronous request chain",
                severity_hint=severity,
                confidence=0.78,
                confidence_label="strong_static_signal",
                affected_node_ids=path_nodes,
                affected_edge_ids=[edge.id for edge in path_edges],
                evidence_ids=evidence_ids,
                signals=[
                    FindingSignal(
                        type="http_call",
                        file_path=first_evidence.file_path if first_evidence else "",
                        start_line=first_evidence.start_line if first_evidence else None,
                        end_line=first_evidence.end_line if first_evidence else None,
                        details={"path": " -> ".join(path_nodes)},
                    )
                ],
                why="The architecture contains multiple synchronous hops in a single request path.",
                impact="Each synchronous hop can add latency and increase the risk of cascading failure.",
                recommendations=[
                    "Collapse non-critical hops behind an aggregator service.",
                    "Move non-blocking work onto a queue or event flow.",
                ],
                telemetry_needed_to_confirm=["end-to-end trace spans", "P95/P99 latency per hop"],
            ))
            return
        for edge in outgoing.get(node_id, []):
            if edge.dst in path_nodes:
                continue
            dfs(edge.dst, [*path_nodes, edge.dst], [*path_edges, edge])

    for start in starts:
        dfs(start, [start], [])
    return findings
