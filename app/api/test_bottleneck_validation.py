import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from analyzers.file_index import FileIndex
from analyzers.orchestrator import AnalyzerOrchestrator
from bottlenecks.models import DeepSeekReview, GroupedFinding, ReviewedFinding
from bottlenecks.rules.base import run_all_rules
from bottlenecks.signals.signal_index import build_repo_signals
from bottlenecks.validators.evidence_gate import validate_review


def test_evidence_gate_rejects_invented_ids_and_runtime_claims():
    files = {
        "repo/services/api/src/app/api/orders/route.ts": """
export async function GET() {
  await axios.get("https://api.stripe.com/v1/payment_intents");
  return Response.json([]);
}
""",
        "repo/services/api/package.json": """
{
  "dependencies": {
    "axios": "1.7.0"
  }
}
""",
    }

    file_index = FileIndex(files)
    facts = AnalyzerOrchestrator().run(file_index, analysis_id="bn-validate-001")
    signals = build_repo_signals(file_index, facts)
    findings = run_all_rules(facts, signals)

    review = DeepSeekReview(
        reviewed_findings=[
            ReviewedFinding(
                finding_id="made_up",
                risk_type="missing_timeout",
                recommended_title="Fake",
                recommended_severity="high",
                recommended_confidence=0.99,
                confidence_label="very_strong_static_signal",
                why="This API is slow in production.",
                impact="P99 latency is 900ms.",
                recommendations=["Do something"],
                telemetry_needed_to_confirm=[],
            )
        ],
        grouped_findings=[
            GroupedFinding(
                group_id="group-1",
                title="Fake Group",
                finding_ids=["made_up"],
                risk_type="missing_timeout",
                affected_node_ids=["fake-node"],
                affected_edge_ids=["fake-edge"],
                affected_route_ids=["fake-route"],
                why="This service is overloaded.",
                recommended_severity="high",
                recommended_confidence=0.9,
            )
        ],
    )

    validated = validate_review(review, findings, facts)
    assert validated.reviewed_findings == []
    assert validated.grouped_findings == []


if __name__ == "__main__":
    test_evidence_gate_rejects_invented_ids_and_runtime_claims()
    print("bottleneck validation tests passed")
