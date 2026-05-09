from __future__ import annotations

import re
from collections import Counter

from pipeline.graph_builder import ArchGraph
from pipeline.scanner import RepoScan
from pipeline.system_context import build_system_context_spec

_COMMON_ROUTE_SEGMENTS = {
    "", "api", "v1", "v2", "v3", "internal", "public", "private",
    "admin", "app", "service", "services",
}

_CAPABILITY_MAP = {
    "auth": "Identity Management",
    "login": "Identity Management",
    "logout": "Identity Management",
    "signup": "Identity Management",
    "session": "Identity Management",
    "user": "Identity Management",
    "users": "Identity Management",
    "profile": "Identity Management",
    "account": "Identity Management",
    "identity": "Identity Management",
    "book": "Catalog & Discovery",
    "books": "Catalog & Discovery",
    "catalog": "Catalog & Discovery",
    "product": "Catalog & Discovery",
    "products": "Catalog & Discovery",
    "item": "Catalog & Discovery",
    "items": "Catalog & Discovery",
    "inventory": "Catalog & Discovery",
    "search": "Catalog & Discovery",
    "discover": "Catalog & Discovery",
    "order": "Order Management",
    "orders": "Order Management",
    "cart": "Order Management",
    "checkout": "Order Management",
    "fulfillment": "Order Management",
    "payment": "Payments & Billing",
    "payments": "Payments & Billing",
    "billing": "Payments & Billing",
    "invoice": "Payments & Billing",
    "subscription": "Payments & Billing",
    "analytics": "Analytics & Reporting",
    "metrics": "Analytics & Reporting",
    "report": "Analytics & Reporting",
    "reports": "Analytics & Reporting",
    "dashboard": "Analytics & Reporting",
    "notification": "Notifications & Integrations",
    "notifications": "Notifications & Integrations",
    "message": "Notifications & Integrations",
    "messages": "Notifications & Integrations",
    "email": "Notifications & Integrations",
    "webhook": "Notifications & Integrations",
    "webhooks": "Notifications & Integrations",
    "team": "Collaboration & Access",
    "teams": "Collaboration & Access",
    "member": "Collaboration & Access",
    "members": "Collaboration & Access",
    "workspace": "Collaboration & Access",
    "workspaces": "Collaboration & Access",
    "repo": "Repository Analysis",
    "repos": "Repository Analysis",
    "repository": "Repository Analysis",
    "repositories": "Repository Analysis",
    "diagram": "Repository Analysis",
    "diagrams": "Repository Analysis",
    "analysis": "Repository Analysis",
    "architecture": "Repository Analysis",
    "file": "Content & Asset Management",
    "files": "Content & Asset Management",
    "asset": "Content & Asset Management",
    "assets": "Content & Asset Management",
    "upload": "Content & Asset Management",
    "uploads": "Content & Asset Management",
    "storage": "Content & Asset Management",
    "media": "Content & Asset Management",
    "content": "Content & Asset Management",
}

_PARTNER_CAPABILITY_KEYWORDS = {
    "Identity Management": {"auth0", "okta", "cognito", "keycloak", "supabase", "identity", "auth"},
    "Payments & Billing": {"stripe", "paypal", "plaid", "billing", "payment"},
    "Notifications & Integrations": {"twilio", "sendgrid", "mailgun", "slack", "webhook"},
    "Repository Analysis": {"github", "openai", "anthropic", "hugging face", "pinecone", "weaviate"},
    "Content & Asset Management": {"cloudinary", "aws", "s3", "storage"},
    "Analytics & Reporting": {"google", "analytics", "datadog", "sentry"},
}


def build_conceptual_spec(scan: RepoScan, graph: ArchGraph) -> dict:
    system_context = build_system_context_spec(scan, graph)
    capabilities = _build_capabilities(scan, graph)

    external_partners = [
        {**node, "group": "external_partners"}
        for node in [*system_context["identity"], *system_context["partners"]][:6]
    ]
    gaps = [
        {
            "id": f"gap-{idx}",
            "label": _gap_label(gap),
            "description": gap,
        }
        for idx, gap in enumerate(_derive_gaps(scan), start=1)
    ]

    edges: list[dict] = []
    for actor in system_context["actors"]:
        edges.append({
            "source": actor["id"],
            "target": "concept-system",
            "label": actor["edge_label"],
            "confidence": actor["confidence"],
        })

    for capability in capabilities:
        edges.append({
            "source": "concept-system",
            "target": capability["id"],
            "label": "Delivers capability",
            "confidence": "verified" if capability["score"] >= 2 else "inferred",
        })

    for partner in external_partners:
        linked = False
        for capability in capabilities:
            if _partner_matches_capability(partner["label"], capability["label"]):
                edges.append({
                    "source": capability["id"],
                    "target": partner["id"],
                    "label": "Depends on partner",
                    "confidence": partner.get("confidence", "inferred"),
                })
                linked = True
        if not linked:
            edges.append({
                "source": "concept-system",
                "target": partner["id"],
                "label": "Uses partner service",
                "confidence": partner.get("confidence", "inferred"),
            })

    for gap in gaps:
        edges.append({
            "source": "concept-system",
            "target": gap["id"],
            "label": "Needs clarification",
            "confidence": "inferred",
        })

    return {
        "actors": system_context["actors"],
        "system": {
            "id": "concept-system",
            "label": system_context["system"]["label"],
            "description": system_context["system"]["description"],
            "all_ids": system_context["system"]["all_ids"],
        },
        "capabilities": capabilities,
        "external_partners": external_partners,
        "gaps": gaps,
        "edges": _dedupe_edges(edges),
    }


def _build_capabilities(scan: RepoScan, graph: ArchGraph) -> list[dict]:
    scores: Counter[str] = Counter()
    reasons: dict[str, list[str]] = {}

    for api in scan.apis:
        for segment in _route_segments(api.path):
            capability = _CAPABILITY_MAP.get(segment)
            if not capability:
                continue
            scores[capability] += 3
            reasons.setdefault(capability, []).append(f"API route {api.method} {api.path}")

    for node in graph.nodes:
        if node.type not in {"service", "frontend"}:
            continue
        for token in _service_tokens(node.label):
            capability = _CAPABILITY_MAP.get(token)
            if not capability:
                continue
            scores[capability] += 2
            reasons.setdefault(capability, []).append(f"Service {node.label}")

    if scan.readme_summary:
        lowered = scan.readme_summary.lower()
        for token, capability in _CAPABILITY_MAP.items():
            if token in lowered:
                scores[capability] += 1
                reasons.setdefault(capability, []).append("README summary")

    if not scores:
        fallback = "Core Application Workflows"
        scores[fallback] = 1
        reasons[fallback] = ["Detected application services"]

    capabilities = []
    for idx, (label, score) in enumerate(scores.most_common(6), start=1):
        reason_bits = list(dict.fromkeys(reasons.get(label, [])))[:2]
        description = (
            f"Supports {label.lower()} based on "
            + " and ".join(reason_bits)
            + "."
        )
        capabilities.append({
            "id": f"capability-{_slug(label)}",
            "label": label,
            "description": description,
            "score": score,
        })
    return capabilities


def _route_segments(path: str) -> list[str]:
    segments = []
    for raw in path.lower().split("/"):
        cleaned = raw.strip().strip("{}").strip(":")
        if not cleaned or cleaned in _COMMON_ROUTE_SEGMENTS:
            continue
        cleaned = re.sub(r"[^a-z0-9]+", "", cleaned)
        if not cleaned:
            continue
        segments.append(cleaned)
    return segments


def _service_tokens(label: str) -> list[str]:
    tokens = [token for token in re.split(r"[^A-Za-z0-9]+", label.lower()) if token]
    return [token for token in tokens if token not in {"api", "app", "application", "service", "worker", "frontend", "backend", "server"}]


def _partner_matches_capability(partner_label: str, capability_label: str) -> bool:
    keywords = _PARTNER_CAPABILITY_KEYWORDS.get(capability_label, set())
    lowered = partner_label.lower()
    return any(keyword in lowered for keyword in keywords)


def _derive_gaps(scan: RepoScan) -> list[str]:
    gaps: list[str] = []
    if scan.http_calls and not scan.external_calls:
        gaps.append("Outbound integrations were detected in code, but not all external partners were mapped.")
    if scan.webhook_routes and not any("webhook" in ext.lower() for ext in scan.external_calls):
        gaps.append("Webhook endpoints exist, but the responsible partner integration is only partially understood.")
    if scan.auth_patterns and not any(hit.provider.lower() in {"auth0", "okta", "cognito", "keycloak", "supabase"} for hit in scan.env_vars):
        gaps.append("Authentication patterns exist, but the identity provider is not fully configured in environment signals.")
    return gaps[:3]


def _gap_label(gap: str) -> str:
    if "Webhook" in gap or "webhook" in gap:
        return "Webhook Integration Gap"
    if "identity" in gap.lower() or "authentication" in gap.lower():
        return "Identity Configuration Gap"
    if "external" in gap.lower() or "partner" in gap.lower():
        return "External Partner Gap"
    return "Architecture Gap"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _dedupe_edges(edges: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict] = []
    for edge in edges:
        key = (edge["source"], edge["target"], edge["label"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(edge)
    return deduped
