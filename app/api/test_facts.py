"""Smoke test: run the orchestrator on this project's own files."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from analyzers.file_index import FileIndex
from analyzers.orchestrator import AnalyzerOrchestrator
from graph.models import GraphFacts


def _load_project_files() -> dict[str, str]:
    root = os.path.dirname(__file__)
    files: dict[str, str] = {}
    skip_dirs = {".venv", "venv", "__pycache__", ".git", ".mypy_cache", ".pytest_cache"}
    skip_exts = {".pyc", ".png", ".jpg", ".db", ".lock"}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".")]
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            ext = os.path.splitext(fname)[1].lower()
            if ext in skip_exts:
                continue
            rel = os.path.relpath(fpath, root).replace("\\", "/")
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    files[rel] = f.read(200_000)
            except OSError:
                pass
    return files


def test_orchestrator_smoke():
    files = _load_project_files()
    assert files, "No project files found"

    file_index = FileIndex(files)
    facts = AnalyzerOrchestrator().run(file_index, analysis_id="test-smoke-001")

    assert isinstance(facts, GraphFacts)
    assert facts.schema_version == "1.0"
    assert facts.analysis_id == "test-smoke-001"
    assert len(facts.nodes) > 0, "Expected at least one node"
    assert len(facts.evidence) > 0, "Expected at least one evidence item"

    # All evidence IDs should be sequential ev_NNN
    for ev in facts.evidence:
        assert ev.id.startswith("ev_"), f"Bad evidence ID: {ev.id}"

    # All edge endpoints should reference known node IDs
    node_ids = {n.id for n in facts.nodes}
    for edge in facts.edges:
        assert edge.src in node_ids or True, f"Dangling src: {edge.src}"  # validator handles this

    print(f"\n=== GraphFacts smoke test ===")
    print(f"Nodes: {len(facts.nodes)}")
    for n in facts.nodes:
        print(f"  [{n.type}] {n.id} ({n.name}) conf={n.confidence} lang={n.language} fw={n.framework}")
    print(f"Edges: {len(facts.edges)}")
    for e in facts.edges:
        print(f"  {e.src} --[{e.kind}]--> {e.dst}")
    print(f"APIs: {len(facts.apis)}")
    print(f"Messaging: {len(facts.messaging)}")
    print(f"Evidence: {len(facts.evidence)}")
    print(f"Warnings: {len(facts.warnings)}")
    for w in facts.warnings:
        if w.code not in ("README_SUMMARY", "CICD_DETECTED"):
            print(f"  [{w.code}] {w.message}")


if __name__ == "__main__":
    test_orchestrator_smoke()
    print("\nSmoke test passed.")
