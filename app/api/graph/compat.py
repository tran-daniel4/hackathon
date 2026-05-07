"""
Backward-compatibility adapter: converts new GraphFacts → old ArchGraph format.
The old ArchGraph is still consumed by rules_engine, aggregator, and diagram generators.
"""
from graph.models import GraphFacts

# Import old models from their original location
from pipeline.graph_builder import ArchGraph, Node, Edge


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
            type=old_type,
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
            type=old_kind,
            confidence=ef.confidence,
            evidence={
                "label": ef.label or "",
                "protocol": ef.protocol or "",
                "operation": ef.operation or "",
            },
        ))

    return ArchGraph(nodes=nodes, edges=edges)
