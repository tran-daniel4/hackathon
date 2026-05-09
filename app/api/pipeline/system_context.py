from __future__ import annotations

import re
from collections import Counter

from pipeline.graph_builder import ArchGraph
from pipeline.scanner import RepoScan

_IDENTITY_NAMES = {
    "auth0": "Auth0",
    "okta": "Okta",
    "cognito": "Amazon Cognito",
    "keycloak": "Keycloak",
    "supabase": "Supabase Auth",
    "openiddict": "OpenIddict",
    "firebase-auth": "Firebase Auth",
    "firebase": "Firebase Auth",
    "clerk": "Clerk",
    "authentik": "Authentik",
}
_IDENTITY_PATTERNS = {
    "Auth0": "Auth0",
    "Okta": "Okta",
    "Cognito": "Amazon Cognito",
    "Keycloak": "Keycloak",
    "OpenIddict": "OpenIddict",
    "ASP.NET Identity": "Application Identity",
    "JWT bearer": "JWT / OIDC",
    "OAuth2": "OAuth2 / OIDC",
    "next-auth": "Hosted Identity",
}
_EXTERNAL_SKIP_WORDS = {"api", "sdk", "service", "auth"}


def build_system_context_spec(scan: RepoScan, graph: ArchGraph) -> dict:
    system_name = _infer_system_name(scan, graph)
    all_ids = [node.id for node in graph.nodes]
    externals_by_id = {node.id: node for node in graph.nodes if node.type == "external_api"}

    identity_nodes = _build_identity_nodes(scan, externals_by_id)
    identity_ids = {node["id"] for node in identity_nodes}

    partner_nodes = _build_partner_nodes(scan, graph, externals_by_id, identity_ids)
    actor_nodes = _build_actor_nodes(scan, graph)

    edges: list[dict] = []
    for actor in actor_nodes:
        edges.append({
            "source": actor["id"],
            "target": "ctx-system",
            "label": actor["edge_label"],
            "confidence": actor["confidence"],
        })

    for identity in identity_nodes:
        edges.append({
            "source": identity["id"],
            "target": "ctx-system",
            "label": identity["edge_label"],
            "confidence": identity["confidence"],
        })

    webhook_provider_ids = set()
    for webhook in scan.webhook_routes:
        if not webhook.provider or webhook.provider.lower() in {"generic", "unknown"}:
            continue
        provider_name = _normalize_provider_name(webhook.provider)
        provider_id = _make_external_id(provider_name, "partner")
        webhook_provider_ids.add(provider_id)
        if provider_id not in {node["id"] for node in partner_nodes} and provider_id not in identity_ids:
            partner_nodes.append({
                "id": provider_id,
                "label": provider_name,
                "description": f"Webhook sender for {webhook.path}.",
                "confidence": "inferred",
            })
        edges.append({
            "source": provider_id,
            "target": "ctx-system",
            "label": "Webhook callback",
            "confidence": "verified",
        })

    partner_edge_map = _build_external_edge_map(graph, set(node["id"] for node in partner_nodes))
    for partner in partner_nodes:
        labels = partner_edge_map.get(partner["id"], [])
        if labels:
            label = _summarize_external_edge_labels(labels)
            confidence = "verified"
        elif partner["id"] in webhook_provider_ids:
            label = "Configured integration"
            confidence = partner["confidence"]
        else:
            label = "Integration"
            confidence = partner["confidence"]
        edges.append({
            "source": "ctx-system",
            "target": partner["id"],
            "label": label,
            "confidence": confidence,
        })

    return {
        "system": {
            "id": "ctx-system",
            "label": system_name,
            "description": _describe_system(system_name, scan),
            "confidence": "inferred",
            "all_ids": all_ids,
        },
        "actors": actor_nodes,
        "identity": identity_nodes,
        "partners": sorted(partner_nodes, key=lambda node: node["label"].lower()),
        "edges": _dedupe_edges(edges),
    }


def _infer_system_name(scan: RepoScan, graph: ArchGraph) -> str:
    service_labels = [node.label for node in graph.nodes if node.type in {"service", "frontend"}]
    if not service_labels:
        return "Application System"

    token_sets = [_service_tokens(label) for label in service_labels]
    common = token_sets[0]
    for tokens in token_sets[1:]:
        common = [token for token in common if token in tokens]
    if common:
        return " ".join(word.capitalize() for word in common[:2])

    for label in service_labels:
        cleaned = _strip_service_suffix(label)
        if cleaned and cleaned.lower() not in {"api", "app", "application", "service", "server", "worker", "frontend", "backend", "web"}:
            return cleaned

    return "Application Platform"


def _build_actor_nodes(scan: RepoScan, graph: ArchGraph) -> list[dict]:
    actors: list[dict] = []
    has_frontend = any(node.type == "frontend" for node in graph.nodes)
    api_paths = [api.path.lower() for api in scan.apis]
    readme = scan.readme_summary.lower()

    if has_frontend or scan.auth_patterns:
        actors.append({
            "id": "actor-web-users",
            "label": "Web Users",
            "description": "People using the application through the primary user interface.",
            "edge_label": "Uses application",
            "confidence": "verified" if has_frontend else "inferred",
        })
    elif api_paths:
        actors.append({
            "id": "actor-api-clients",
            "label": "API Clients",
            "description": "External consumers calling the application over HTTP APIs.",
            "edge_label": "Calls APIs",
            "confidence": "inferred",
        })
    else:
        actors.append({
            "id": "actor-users",
            "label": "Users",
            "description": "Primary users interacting with the system.",
            "edge_label": "Uses system",
            "confidence": "inferred",
        })

    if any("/admin" in path or "/manage" in path for path in api_paths) or "admin" in readme:
        actors.append({
            "id": "actor-admins",
            "label": "Administrators",
            "description": "Operators managing privileged or internal workflows.",
            "edge_label": "Admin operations",
            "confidence": "inferred",
        })

    if scan.webhook_routes or any("/api/" in path for path in api_paths):
        actors.append({
            "id": "actor-integrators",
            "label": "External Integrators",
            "description": "Other applications or automation clients integrating with the system.",
            "edge_label": "API integration",
            "confidence": "inferred",
        })

    deduped: list[dict] = []
    seen = set()
    for actor in actors:
        if actor["id"] in seen:
            continue
        seen.add(actor["id"])
        deduped.append(actor)
    return deduped[:3]


def _build_identity_nodes(scan: RepoScan, externals_by_id: dict[str, object]) -> list[dict]:
    candidates: dict[str, dict] = {}

    for provider in {hit.provider for hit in scan.env_vars}:
        normalized = _normalize_provider_name(provider)
        identity_label = _to_identity_label(normalized)
        if not identity_label:
            continue
        node_id = _make_external_id(identity_label, "identity")
        candidates[node_id] = {
            "id": node_id,
            "label": identity_label,
            "description": "Identity provider used for authentication and sign-in flows.",
            "edge_label": "Authentication / OIDC",
            "confidence": "verified",
        }

    for pattern in scan.auth_patterns:
        label = _IDENTITY_PATTERNS.get(pattern)
        if not label:
            continue
        node_id = _make_external_id(label, "identity")
        candidates.setdefault(node_id, {
            "id": node_id,
            "label": label,
            "description": "Identity service inferred from authentication configuration.",
            "edge_label": "Authentication / OIDC",
            "confidence": "inferred",
        })

    for external_id, external in externals_by_id.items():
        label = getattr(external, "label", "")
        identity_label = _to_identity_label(label)
        if not identity_label:
            continue
        node_id = _make_external_id(identity_label, "identity")
        candidates[node_id] = {
            "id": node_id,
            "label": identity_label,
            "description": "Identity provider integrated with the application.",
            "edge_label": "Authentication / OIDC",
            "confidence": "verified",
        }

    return sorted(candidates.values(), key=lambda node: node["label"].lower())[:3]


def _build_partner_nodes(
    scan: RepoScan,
    graph: ArchGraph,
    externals_by_id: dict[str, object],
    identity_ids: set[str],
) -> list[dict]:
    scores: Counter[str] = Counter()
    labels: dict[str, str] = {}

    for edge in graph.edges:
        if edge.target in externals_by_id:
            scores[edge.target] += 2 if edge.confidence == "verified" else 1
            labels[edge.target] = externals_by_id[edge.target].label

    for external_id, external in externals_by_id.items():
        scores[external_id] += 1
        labels.setdefault(external_id, external.label)

    partner_nodes: list[dict] = []
    for external_id, label in labels.items():
        partner_id = _make_external_id(label, "partner")
        if partner_id in identity_ids:
            continue
        partner_nodes.append({
            "id": partner_id,
            "label": label,
            "description": f"External system the application integrates with for {label.lower()} capabilities.",
            "confidence": "verified" if scores[external_id] >= 2 else "inferred",
            "_score": scores[external_id],
        })

    for provider in {hit.provider for hit in scan.env_vars}:
        normalized = _normalize_provider_name(provider)
        if _to_identity_label(normalized):
            continue
        partner_id = _make_external_id(normalized, "partner")
        if partner_id in identity_ids or any(node["id"] == partner_id for node in partner_nodes):
            continue
        partner_nodes.append({
            "id": partner_id,
            "label": normalized,
            "description": "Provider inferred from configuration and environment variables.",
            "confidence": "inferred",
            "_score": 1,
        })

    partner_nodes.sort(key=lambda node: (-node["_score"], node["label"].lower()))
    trimmed = partner_nodes[:6]
    for node in trimmed:
        node.pop("_score", None)
    return trimmed


def _build_external_edge_map(graph: ArchGraph, partner_ids: set[str]) -> dict[str, list[str]]:
    partner_labels_by_graph_id = {
        node.id: _make_external_id(node.label, "partner")
        for node in graph.nodes
        if node.type == "external_api"
    }
    edge_map: dict[str, list[str]] = {}
    for edge in graph.edges:
        partner_id = partner_labels_by_graph_id.get(edge.target)
        if not partner_id or partner_id not in partner_ids:
            continue
        edge_map.setdefault(partner_id, []).append(edge.type)
    return edge_map


def _summarize_external_edge_labels(labels: list[str]) -> str:
    counts = Counter(labels)
    dominant = counts.most_common(1)[0][0]
    return {
        "http": "API calls",
        "calls": "Service integration",
        "publishes": "Publishes events",
        "consumes": "Consumes events",
        "reads/writes": "Data exchange",
        "caches": "Cache access",
    }.get(dominant, "Integration")


def _describe_system(system_name: str, scan: RepoScan) -> str:
    if scan.readme_summary:
        sentence = scan.readme_summary.split(".")[0].strip()
        if sentence:
            return sentence if sentence.endswith(".") else f"{sentence}."
    if scan.frameworks:
        frameworks = ", ".join(scan.frameworks[:2])
        return f"{system_name} is built with {frameworks} and exposes its primary application workflows."
    return f"{system_name} is the application boundary being analyzed."


def _service_tokens(label: str) -> list[str]:
    tokens = [token for token in re.split(r"[^A-Za-z0-9]+", label) if token]
    cleaned = []
    for token in tokens:
        lowered = token.lower()
        if lowered in {"api", "service", "worker", "frontend", "backend", "server", "apphost"}:
            continue
        cleaned.append(lowered)
    return cleaned or [label.lower()]


def _strip_service_suffix(label: str) -> str:
    parts = [part for part in re.split(r"[-_. ]+", label) if part]
    cleaned = [part for part in parts if part.lower() not in {"api", "service", "worker", "frontend", "backend", "server", "apphost"}]
    if not cleaned:
        cleaned = parts
    return " ".join(word.capitalize() for word in cleaned[:3])


def _normalize_provider_name(provider: str) -> str:
    provider = provider.strip()
    if not provider:
        return "External System"
    lowered = provider.lower().replace("_", "-").replace(" ", "-")
    if lowered in _IDENTITY_NAMES:
        return _IDENTITY_NAMES[lowered]
    return provider.replace("_", " ").title()


def _to_identity_label(name: str) -> str | None:
    lowered = name.lower().replace(" ", "-")
    if lowered in _IDENTITY_NAMES:
        return _IDENTITY_NAMES[lowered]
    for key, value in _IDENTITY_NAMES.items():
        if key in lowered:
            return value
    return None


def _make_external_id(label: str, prefix: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    if prefix == "identity":
        return f"idp-{base}"
    return f"partner-{base}"


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
