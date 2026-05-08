import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from pipeline.aggregator import aggregate
from pipeline.diagram_generator import generate_diagrams
from pipeline.graph_builder import build_graph
from pipeline.scanner import scan_files


def test_system_context_synthesizes_actors_identity_and_partners():
    scan = scan_files({
        "bookworm/app/web/package.json": """
{
  "dependencies": {
    "next": "15.0.0",
    "react": "19.0.0",
    "@auth0/nextjs-auth0": "3.0.0",
    "stripe": "16.0.0"
  }
}
""",
        "bookworm/app/web/src/app/api/orders/route.ts": """
export async function GET() {
  await fetch("https://api.stripe.com/v1/payment_intents");
  return Response.json({ ok: true });
}
""",
        "bookworm/app/api/.env.example": """
AUTH0_DOMAIN=tenant.us.auth0.com
STRIPE_SECRET_KEY=sk_test_123
""",
        "bookworm/app/api/routes.py": """
@app.post("/webhooks/stripe")
def stripe_webhook():
    return {"ok": True}
""",
    })

    graph = build_graph(scan)
    output = generate_diagrams(scan, graph, aggregate([]))
    view = next(diagram for diagram in output.views if diagram.id == "system_context")

    node_ids = {node.id for node in view.nodes}
    labels = {node.label for node in view.nodes}

    assert "ctx-system" in node_ids
    assert any(node.group == "actors" for node in view.nodes)
    assert any(node.group == "identity" and "Auth0" in node.label for node in view.nodes)
    assert any(node.group == "partners" and "Stripe" in node.label for node in view.nodes)
    assert "Web Users" in labels or "API Clients" in labels

    assert any(edge.target == "ctx-system" and "Webhook" in edge.label for edge in view.edges)
    assert any(edge.source == "ctx-system" and edge.target.endswith("stripe") for edge in view.edges)


if __name__ == "__main__":
    test_system_context_synthesizes_actors_identity_and_partners()
    print("system_context tests passed")
