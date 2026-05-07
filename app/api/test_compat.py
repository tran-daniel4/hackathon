"""Tests for the GraphFacts → ArchGraph compat adapter."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from graph.models import GraphFacts, NodeFact, EdgeFact, RepoMeta
from graph.compat import graph_facts_to_arch_graph


def _make_facts(**kwargs) -> GraphFacts:
    defaults = dict(
        analysis_id="test-001",
        repo=RepoMeta(name="test"),
        nodes=[],
        edges=[],
    )
    defaults.update(kwargs)
    return GraphFacts(**defaults)


def test_node_type_mapping():
    mapping = [
        ("service",          "service"),
        ("gateway",          "service"),
        ("worker",           "service"),
        ("database",         "database"),
        ("cache",            "cache"),
        ("queue",            "queue"),
        ("topic",            "queue"),
        ("external_service", "external_api"),
        ("auth_provider",    "external_api"),
        ("object_storage",   "external_api"),
        ("client",           "frontend"),
        ("unknown",          "service"),
    ]
    for new_type, expected_old in mapping:
        facts = _make_facts(nodes=[
            NodeFact(id="n1", type=new_type, name="Test Node")
        ])
        graph = graph_facts_to_arch_graph(facts)
        assert len(graph.nodes) == 1
        assert graph.nodes[0].type == expected_old, \
            f"'{new_type}' should map to '{expected_old}', got '{graph.nodes[0].type}'"


def test_edge_kind_mapping():
    mapping = [
        ("http",         "outbound",  "http"),
        ("grpc",         "outbound",  "http"),
        ("webhook",      "outbound",  "http"),
        ("read",         "outbound",  "reads/writes"),
        ("write",        "outbound",  "reads/writes"),
        ("cache_read",   "outbound",  "caches"),
        ("cache_write",  "outbound",  "caches"),
        ("sdk",          "outbound",  "calls"),
        ("pubsub",       "outbound",  "publishes"),
        ("pubsub",       "inbound",   "consumes"),
        ("queue",        "inbound",   "consumes"),
    ]
    for kind, direction, expected_old in mapping:
        facts = _make_facts(
            nodes=[
                NodeFact(id="a", type="service", name="A"),
                NodeFact(id="b", type="service", name="B"),
            ],
            edges=[
                EdgeFact(id="e1", src="a", dst="b", kind=kind, direction=direction)
            ],
        )
        graph = graph_facts_to_arch_graph(facts)
        assert len(graph.edges) == 1
        assert graph.edges[0].type == expected_old, \
            f"kind='{kind}' dir='{direction}' should map to '{expected_old}', got '{graph.edges[0].type}'"


def test_metadata_preserved():
    facts = _make_facts(nodes=[
        NodeFact(id="svc", type="service", name="My Service",
                 language="Python", framework="FastAPI", tags=["backend"])
    ])
    graph = graph_facts_to_arch_graph(facts)
    node = graph.nodes[0]
    assert node.metadata["language"] == "Python"
    assert node.metadata["framework"] == "FastAPI"
    assert node.metadata["tags"] == ["backend"]


if __name__ == "__main__":
    test_node_type_mapping()
    test_edge_kind_mapping()
    test_metadata_preserved()
    print("All compat tests passed.")
