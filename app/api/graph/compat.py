"""
Backward-compatibility adapter: converts new GraphFacts → old ArchGraph format.
The old ArchGraph is still consumed by rules_engine, aggregator, and diagram generators.
"""
from collections import Counter
from typing import cast

from graph.models import GraphFacts

# Import old models from their original location
from pipeline.graph_builder import ArchGraph, Node, Edge, NodeType, EdgeType


_NODE_TYPE_MAP: dict[str, str] = {
    "service":          "service",
    "gateway":          "service",
    "worker":           "service",
    "database":         "database",
    "cache":            "cache",
    "queue":            "queue",
    "topic":            "queue",
    "external_service": "external_api",
    "auth_provider":    "external_api",
    "object_storage":   "external_api",
    "client":           "frontend",
    "unknown":          "service",
}

_EDGE_KIND_MAP: dict[str, str] = {
    "http":          "http",
    "grpc":          "http",
    "webhook":       "http",
    "read":          "reads/writes",
    "write":         "reads/writes",
    "cache_read":    "caches",
    "cache_write":   "caches",
    "object_read":   "calls",
    "object_write":  "calls",
    "pubsub":        "publishes",
    "queue":         "publishes",
    "sdk":           "calls",
    "unknown":       "calls",
}


def graph_facts_to_arch_graph(facts: GraphFacts) -> ArchGraph:
    nodes: list[Node] = []
    for nf in facts.nodes:
        old_type = _NODE_TYPE_MAP.get(nf.type, "service")
        nodes.append(Node(
            id=nf.id,
            label=nf.name,
            type=cast(NodeType, old_type),
            metadata={
                "language": nf.language,
                "framework": nf.framework,
                "tags": nf.tags,
                "confidence": nf.confidence,
            },
        ))

    edges: list[Edge] = []
    for ef in facts.edges:
        old_kind = _EDGE_KIND_MAP.get(ef.kind, "calls")
        # pubsub from topic→service should be "consumes"
        if ef.kind in ("pubsub", "queue") and ef.direction == "inbound":
            old_kind = "consumes"
        edges.append(Edge(
            source=ef.src,
            target=ef.dst,
            type=cast(EdgeType, old_kind),
            confidence=ef.confidence,
            evidence={
                "label": ef.label or "",
                "protocol": ef.protocol or "",
                "operation": ef.operation or "",
            },
        ))

    _add_inferred_client_edges(facts, nodes, edges)

    return ArchGraph(nodes=nodes, edges=edges)


def _add_inferred_client_edges(facts: GraphFacts, nodes: list[Node], edges: list[Edge]) -> None:
    node_type_by_id = {node.id: node.type for node in nodes}
    client_ids = [node.id for node in nodes if node.type == "frontend"]
    if not client_ids:
        return

    route_counts: Counter[str] = Counter(
        api.component_id
        for api in facts.apis
        if node_type_by_id.get(api.component_id) == "service"
    )
    if not route_counts:
        return

    existing_pairs = {(edge.source, edge.target) for edge in edges}
    ranked_targets = sorted(
        route_counts,
        key=lambda node_id: (
            0 if any(token in node_id for token in ("api", "gateway")) else 1,
            -route_counts[node_id],
            node_id,
        ),
    )

    for client_id in client_ids:
        if any((client_id, target_id) in existing_pairs for target_id in ranked_targets):
            continue

        target_id = ranked_targets[0]
        edges.append(Edge(
            source=client_id,
            target=target_id,
            type="http",
            label="HTTP request",
            confidence="inferred",
            evidence={
                "label": "HTTP request",
                "protocol": "http",
                "operation": "request",
            },
        ))
