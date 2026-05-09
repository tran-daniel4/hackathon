import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from analyzers.file_index import FileIndex
from analyzers.orchestrator import AnalyzerOrchestrator
from bottlenecks.orchestrator import run_bottleneck_analysis
from endpoints.analyze import _build_request_flow_annotations  # type: ignore[attr-defined]
from graph.compat import graph_facts_to_arch_graph
from pipeline.llm_wrapper import LLMConfig


def test_app_monorepo_paths_collapse_to_real_services_and_emit_cache_miss_flow():
    files = {
        "repo/app/web/package.json": """
{
  "dependencies": {
    "next": "16.0.0",
    "react": "19.0.0"
  }
}
""",
        "repo/app/api/requirements.txt": """
fastapi==0.116.0
asyncpg==0.29.0
redis==5.0.0
""",
        "repo/app/api/routes/orders.py": """
@router.get("/orders")
async def list_orders():
    cached = redis.get("orders")
    if cached:
        return cached
    conn = await asyncpg.connect("postgresql://db")
    rows = await conn.fetch("SELECT * FROM orders")
    return rows
""",
    }

    file_index = FileIndex(files)
    facts = AnalyzerOrchestrator().run(file_index, analysis_id="flow-001")
    graph = graph_facts_to_arch_graph(facts)

    node_ids = {node.id for node in graph.nodes}
    assert "web" in node_ids
    assert "api" in node_ids
    assert "auth-ts" not in node_ids
    assert "types" not in node_ids

    result, _legacy = run_bottleneck_analysis(
        file_index=file_index,
        graph_facts=facts,
        config=LLMConfig(base_url="http://127.0.0.1:9"),
    )
    annotations = _build_request_flow_annotations(graph, result.repo_signals, result.report.hot_nodes)

    assert annotations
    flow = annotations[0]
    edge_ids = [segment["edgeId"] for segment in flow["segments"]]
    assert "web--api" in edge_ids
    assert "api--redis" in edge_ids
    assert "api--postgresql" in edge_ids
    assert any(segment["reverse"] for segment in flow["segments"])


if __name__ == "__main__":
    test_app_monorepo_paths_collapse_to_real_services_and_emit_cache_miss_flow()
    print("component request flow tests passed")
