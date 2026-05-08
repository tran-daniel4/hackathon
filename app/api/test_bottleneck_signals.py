import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from analyzers.file_index import FileIndex
from analyzers.orchestrator import AnalyzerOrchestrator
from bottlenecks.signals.signal_index import build_repo_signals


def test_repo_signals_associate_routes_http_and_loop_db_calls():
    files = {
        "repo/apps/api/src/app/api/orders/route.ts": """
export async function GET(request: Request) {
  const orders = await prisma.order.findMany({});
  for (const order of orders) {
    await prisma.user.findUnique({ where: { id: order.userId } });
  }
  await axios.get("https://api.stripe.com/v1/payment_intents");
  return Response.json(orders);
}
""",
        "repo/apps/api/package.json": """
{
  "dependencies": {
    "axios": "1.7.0",
    "@prisma/client": "5.0.0"
  }
}
""",
    }

    file_index = FileIndex(files)
    facts = AnalyzerOrchestrator().run(file_index, analysis_id="bn-signals-001")
    signals = build_repo_signals(file_index, facts)

    assert any(route.path == "/orders" or route.path == "/api/orders" for route in signals.routes)
    assert any(call.target_hint == "api.stripe.com" and call.enclosing_route_id for call in signals.http_calls)
    assert any(loop.enclosing_route_id for loop in signals.loops)
    assert any(db_call.inside_loop_id is not None for db_call in signals.db_calls)


if __name__ == "__main__":
    test_repo_signals_associate_routes_http_and_loop_db_calls()
    print("bottleneck signal tests passed")
