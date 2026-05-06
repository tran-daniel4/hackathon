"""
Smoke test for the diagram generator.
Run: python test_diagrams.py [optional/path/to/repo]
"""
import json
import sys
from pathlib import Path

from pipeline.scanner import scan_repo
from pipeline.graph_builder import build_graph
from pipeline.rules_engine import run_rules
from pipeline.llm_wrapper import LLMConfig, enrich_issues
from pipeline.aggregator import aggregate
from pipeline.diagram_generator import generate_diagrams

target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent.parent

print(f"Scanning: {target}\n")
scan    = scan_repo(target)
graph   = build_graph(scan)
issues  = run_rules(scan, graph, root=target)
enriched = enrich_issues(issues, graph, root=target, config=LLMConfig())
report  = aggregate(enriched)
output  = generate_diagrams(scan, graph, report)

print(f"Generated {len(output.views)} view(s):\n")
for view in output.views:
    print(f"  [{view.id}]  '{view.label}'")
    print(f"    nodes ({len(view.nodes)}): {[n.id for n in view.nodes]}")
    print(f"    edges ({len(view.edges)}): {[(e.source, e.target) for e in view.edges]}")
    if view.annotations:
        print(f"    annotations: {view.annotations}")
    print()

# Print component view as the canonical diagram (matches current frontend contract)
component = next((v for v in output.views if v.id == "component"), output.views[0])
print("=== Component view (frontend-ready JSON) ===")
print(json.dumps({
    "nodes": [n.model_dump() for n in component.nodes],
    "edges": [e.model_dump() for e in component.edges],
    "annotations": component.annotations,
}, indent=2))
