from __future__ import annotations

from bottlenecks.models import RuleFinding
from graph.models import GraphFacts


def validate_rule_findings(findings: list[RuleFinding], graph_facts: GraphFacts) -> list[RuleFinding]:
    node_ids = {node.id for node in graph_facts.nodes}
    edge_ids = {edge.id for edge in graph_facts.edges}
    route_ids = {api.id for api in graph_facts.apis}
    evidence_ids = {evidence.id for evidence in graph_facts.evidence}
    validated: list[RuleFinding] = []
    for finding in findings:
        finding.affected_node_ids = [node_id for node_id in finding.affected_node_ids if node_id in node_ids]
        finding.affected_edge_ids = [edge_id for edge_id in finding.affected_edge_ids if edge_id in edge_ids]
        finding.affected_route_ids = [route_id for route_id in finding.affected_route_ids if route_id in route_ids]
        finding.evidence_ids = [evidence_id for evidence_id in finding.evidence_ids if evidence_id in evidence_ids]
        validated.append(finding)
    return validated
