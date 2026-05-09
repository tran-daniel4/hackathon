import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from analyzers.file_index import FileIndex
from analyzers.orchestrator import AnalyzerOrchestrator
from bottlenecks.orchestrator import build_component_annotations, run_bottleneck_analysis
from pipeline.llm_wrapper import LLMConfig


def test_bottleneck_orchestrator_returns_rich_report_and_legacy_adapter():
    files = {
        "repo/services/api/src/app/api/orders/route.ts": """
export async function GET() {
  const rows = await prisma.order.findMany({});
  await axios.get("https://api.stripe.com/v1/payment_intents");
  return Response.json(rows);
}
""",
        "repo/services/api/package.json": """
{
  "dependencies": {
    "axios": "1.7.0",
    "@prisma/client": "5.0.0"
  }
}
""",
    }

    file_index = FileIndex(files)
    facts = AnalyzerOrchestrator().run(file_index, analysis_id="bn-orch-001")
    result, legacy = run_bottleneck_analysis(
        file_index=file_index,
        graph_facts=facts,
        config=LLMConfig(base_url="http://127.0.0.1:9"),
    )

    assert result.report.analysis_id == "bn-orch-001"
    assert result.report.mode == "static_analysis_only"
    assert result.report.summary.total_findings >= 1
    assert result.report.issues
    assert legacy.total_issues == len(result.report.findings)
    assert build_component_annotations(result.report)


if __name__ == "__main__":
    test_bottleneck_orchestrator_returns_rich_report_and_legacy_adapter()
    print("bottleneck orchestrator tests passed")
