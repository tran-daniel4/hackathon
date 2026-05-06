"""
Smoke test for the architecture graph builder.
Run: python test_graph.py [optional/path/to/repo]
"""
import json
import sys
from pathlib import Path

from pipeline.scanner import scan_repo
from pipeline.graph_builder import build_graph

target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent.parent

print(f"Scanning: {target}\n")
scan   = scan_repo(target)
graph  = build_graph(scan)

print(json.dumps(graph.model_dump(), indent=2))
print("\n--- Summary ---")
print(f"Nodes ({len(graph.nodes)}):")
for n in graph.nodes:
    print(f"  [{n.type:12}]  {n.id}  ({n.label})")
print(f"\nEdges ({len(graph.edges)}):")
for e in graph.edges:
    print(f"  {e.source}  --[{e.type}]-->  {e.target}")
