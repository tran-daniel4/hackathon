"""
Test for the LLM wrapper.
Run: python test_llm.py [optional/path/to/repo]

Tests prompt construction without a model, then attempts a live call.
"""
import json
import sys
from pathlib import Path

from pipeline.scanner import scan_repo
from pipeline.graph_builder import build_graph
from pipeline.rules_engine import run_rules
from pipeline.llm_wrapper import LLMConfig, enrich_issues, _build_prompt

target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent.parent

print(f"Scanning: {target}\n")
scan   = scan_repo(target)
graph  = build_graph(scan)
issues = run_rules(scan, graph, root=target)

if not issues:
    print("No issues detected — nothing to enrich.")
    sys.exit(0)

# ── Show prompt for first issue (no model needed) ─────────────────────────────
print(f"=== Prompt preview for: '{issues[0].type}' ===")
prompt = _build_prompt(issues[0], graph, root=target)
print(prompt)
print(f"\nPrompt length: {len(prompt)} chars (~{len(prompt)//4} tokens)\n")

# ── Attempt live enrichment ───────────────────────────────────────────────────
print("=== Attempting live LLM enrichment ===")
print("(Requires Ollama running with deepseek-coder loaded)\n")

cfg = LLMConfig()
enriched = enrich_issues(issues, graph, root=target, config=cfg)

print(json.dumps([e.model_dump() for e in enriched], indent=2))
print(f"\n--- Summary ---")
for e in enriched:
    status = "enriched" if e.llm_enriched else "rule-only"
    print(f"  [{e.severity.upper():8}] [{status}]  {e.type}")
    if e.llm_enriched:
        print(f"             explanation: {e.llm_explanation[:80]}...")
        print(f"             fix:         {e.llm_fix[:80]}...")
        print(f"             confidence:  {e.llm_confidence}")
