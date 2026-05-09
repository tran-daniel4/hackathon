import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from analyzers.file_index import FileIndex
from analyzers.orchestrator import AnalyzerOrchestrator
from bottlenecks.rules.base import run_all_rules
from bottlenecks.signals.signal_index import build_repo_signals


def test_bottleneck_rules_detect_key_static_risks():
    files = {
        "repo/services/api/package.json": """
{
  "dependencies": {
    "axios": "1.7.0",
    "@prisma/client": "5.0.0",
    "ioredis": "5.4.1"
  }
}
""",
        "repo/services/api/src/app/api/orders/route.ts": """
export async function GET() {
  const orders = await prisma.order.findMany({});
  for (const order of orders) {
    await prisma.user.findUnique({ where: { id: order.userId } });
    logger.debug(order);
  }
  const cached = await redis.get("orders");
  if (!cached) {
    const fresh = await prisma.order.findMany({});
    await redis.set("orders", JSON.stringify(fresh));
  }
  await axios.get("https://api.stripe.com/v1/payment_intents");
  return Response.json(orders);
}
""",
        "repo/services/payments/src/worker.ts": """
import axios from "axios";
export async function syncPayments() {
  return axios.post("https://api.stripe.com/v1/charges");
}
""",
        "repo/services/api/src/db.ts": """
const db = new Pool({ connectionString: process.env.DATABASE_URL });
""",
        "repo/services/payments/src/db.ts": """
const db = new Pool({ connectionString: process.env.DATABASE_URL });
""",
    }

    file_index = FileIndex(files)
    facts = AnalyzerOrchestrator().run(file_index, analysis_id="bn-rules-001")
    signals = build_repo_signals(file_index, facts)
    findings = run_all_rules(facts, signals)
    risk_types = {finding.risk_type for finding in findings}

    assert "missing_timeout" in risk_types
    assert "n_plus_one" in risk_types
    assert "missing_pagination" in risk_types
    assert "cache_stampede" in risk_types
    assert "external_dependency_risk" in risk_types


if __name__ == "__main__":
    test_bottleneck_rules_detect_key_static_risks()
    print("bottleneck rule tests passed")
