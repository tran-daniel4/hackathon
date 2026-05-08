import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from pipeline.aggregator import aggregate
from pipeline.diagram_generator import generate_diagrams
from pipeline.graph_builder import build_graph
from pipeline.scanner import scan_files


def test_conceptual_view_synthesizes_business_capabilities():
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
        "bookworm/README.md": """
# BookWorm

BookWorm helps readers discover books, manage orders, and complete secure payments.
""",
        "bookworm/app/web/src/app/api/books/route.ts": """
export async function GET() {
  return Response.json({ books: [] });
}
""",
        "bookworm/app/web/src/app/api/orders/route.ts": """
export async function POST() {
  await fetch("https://api.stripe.com/v1/payment_intents");
  return Response.json({ ok: true });
}
""",
        "bookworm/app/web/src/app/api/auth/login/route.ts": """
export async function GET() {
  return Response.json({ login: true });
}
""",
        "bookworm/app/api/.env.example": """
AUTH0_DOMAIN=tenant.us.auth0.com
STRIPE_SECRET_KEY=sk_test_123
""",
    })

    graph = build_graph(scan)
    output = generate_diagrams(scan, graph, aggregate([]))
    view = next(diagram for diagram in output.views if diagram.id == "conceptual")

    node_ids = {node.id for node in view.nodes}
    labels = {node.label for node in view.nodes}

    assert "concept-system" in node_ids
    assert any(node.group == "users" for node in view.nodes)
    assert any(node.group == "capabilities" and node.label == "Catalog & Discovery" for node in view.nodes)
    assert any(node.group == "capabilities" and node.label == "Order Management" for node in view.nodes)
    assert any(node.group == "capabilities" and node.label == "Payments & Billing" for node in view.nodes)
    assert any(node.group == "external_partners" and "Auth0" in node.label for node in view.nodes)
    assert any(node.group == "external_partners" and "Stripe" in node.label for node in view.nodes)

    assert "Web Users" in labels or "External Integrators" in labels
    assert any(edge.target == "concept-system" for edge in view.edges)
    assert any(edge.source == "concept-system" and edge.target.startswith("capability-") for edge in view.edges)


if __name__ == "__main__":
    test_conceptual_view_synthesizes_business_capabilities()
    print("conceptual tests passed")
