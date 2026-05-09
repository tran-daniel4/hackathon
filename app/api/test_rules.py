"""
Smoke test for the rules engine.
Run: python test_rules.py [optional/path/to/repo]
"""
import json
import sys
from pathlib import Path

from pipeline.scanner import scan_repo
from pipeline.graph_builder import build_graph
from pipeline.rules_engine import run_rules

target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent.parent

print(f"Scanning: {target}\n")
scan   = scan_repo(target)
graph  = build_graph(scan)
issues = run_rules(scan, graph, root=target)

print(json.dumps([i.model_dump() for i in issues], indent=2))
print(f"\n--- Summary ({len(issues)} issues) ---")
for issue in issues:
    print(f"  [{issue.severity.upper():8}]  {issue.type}")
    print(f"             affected: {issue.affected}")
