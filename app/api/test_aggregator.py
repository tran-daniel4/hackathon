"""
Smoke test for the bottleneck aggregator.
Run: python test_aggregator.py [optional/path/to/repo]
"""
import json
import sys
from pathlib import Path

from pipeline.scanner import scan_repo
from pipeline.graph_builder import build_graph
from pipeline.rules_engine import run_rules
from pipeline.llm_wrapper import LLMConfig, enrich_issues
from pipeline.aggregator import aggregate

target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent.parent

print(f"Scanning: {target}\n")
scan    = scan_repo(target)
graph   = build_graph(scan)
issues  = run_rules(scan, graph, root=target)
enriched = enrich_issues(issues, graph, root=target, config=LLMConfig())
report  = aggregate(enriched)

print(json.dumps(report.model_dump(), indent=2))
print("\n=== Final Report ===")
print(f"  Risk score:   {report.risk_score} / 100")
print(f"  Total issues: {report.total_issues}")
print(f"  By severity:  {report.by_severity}")
print()
for issue in report.issues:
    print(f"  [{issue.severity.upper():8}] [{issue.source:10}] {issue.type}")
    print(f"    confidence: {issue.confidence}")
    print(f"    affected:   {issue.affected[:4]}")
    print(f"    fix:        {issue.fix[:80]}")
