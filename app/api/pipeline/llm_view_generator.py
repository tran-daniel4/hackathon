"""
Hybrid LLM View Generator.
Generates all 4 architecture views using LLM interpretation with per-view static fallback.

Feed: rich canonical package (services / data_stores / externals / connections / api_surface /
      signals / naming_hint / gaps) — all self-describing, semantic field names.
Get:  per-view JSON (nodes / edges / groups) grounded in facts, hypothesis edges clearly marked.
"""
import asyncio
import json
import logging

from pipeline.scanner import RepoScan
from pipeline.graph_builder import ArchGraph, Edge
from pipeline.aggregator import BottleneckReport
from pipeline.diagram_generator import (
    DiagramOutput, DiagramView, DiagramNode, DiagramEdge, DiagramGroup,
    _TYPE_LAYER, _TYPE_GROUP,
    generate_diagrams,
)
from pipeline.llm_wrapper import LLMConfig, _call_ollama, _call_openai_compat
from pipeline.conceptual import build_conceptual_spec
from pipeline.system_context import build_system_context_spec

logger = logging.getLogger(__name__)

_VIEW_MAX_TOKENS = 1500

_VALID_UI_TYPES = {"frontend", "backend", "database", "cache", "queue", "worker", "external"}
_LLM_TYPE_REMAP = {
    "actor":           "frontend",
    "capability":      "backend",
    "service":         "backend",
    "external_api":    "external",
    "external_system": "external",
    "identity":        "external",
    "partner":         "external",
    "gap":             "external",
    "infra":           "worker",
    "cicd":            "worker",
}

_COMMON_SUFFIXES = (
    "-service", "-api", "-worker", "-svc", "-backend",
    "-server", "-gateway", "-proxy", "_service", "_api", "_worker",
)

# Shared constraint added to every prompt
_CONSTRAINT_PREFIX = (
    "Return JSON only — no markdown, no explanation.\n"
    "Ground every node in FACTS. Synthetic actors, capabilities, system, and runtime nodes "
    "are allowed for non-component views when FACTS imply them. "
    "Any connection you infer beyond direct evidence must have confidence=inferred "
    "and label starting with 'suggested: '.\n\n"
)


# ── Public API ──────────────────────────────────────────────────────────────────

async def generate_diagrams_hybrid(
    scan: RepoScan,
    graph: ArchGraph,
    report: BottleneckReport,
    config: LLMConfig | None = None,
) -> DiagramOutput:
    cfg = config or LLMConfig()
    view_cfg = cfg.model_copy(update={"max_tokens": _VIEW_MAX_TOKENS, "timeout": 180.0})

    static_output = generate_diagrams(scan, graph, report)
    static_by_id = {v.id: v for v in static_output.views}

    ctx = _build_canonical_context(scan, graph)
    canonical_ids = {n.id for n in graph.nodes}

    async def try_view(vid: str) -> DiagramView:
        fallback = static_by_id[vid]
        try:
            return await _generate_view(vid, ctx, view_cfg, fallback, canonical_ids)
        except Exception as exc:
            logger.warning("LLM view '%s' failed, using static fallback: %s", vid, exc)
            return fallback

    views = list(await asyncio.gather(*[try_view(vid) for vid in static_by_id]))
    return DiagramOutput(views=views)


# ── View generation ─────────────────────────────────────────────────────────────

async def _generate_view(
    view_id: str,
    ctx: dict,
    cfg: LLMConfig,
    fallback: DiagramView,
    canonical_ids: set[str],
) -> DiagramView:
    prompt = _build_prompt(view_id, ctx)
    raw = await _call_llm_async(prompt, cfg)
    return _parse_view_response(raw, view_id, fallback, canonical_ids)


async def _call_llm_async(prompt: str, cfg: LLMConfig) -> str:
    if cfg.provider == "ollama":
        return await asyncio.to_thread(_call_ollama, prompt, cfg)
    return await asyncio.to_thread(_call_openai_compat, prompt, cfg)


# ── Canonical context builder ───────────────────────────────────────────────────

def _build_canonical_context(scan: RepoScan, graph: ArchGraph) -> dict:
    """
    Build a rich, self-describing package for LLM prompts.
    All field names are semantic (no single-letter abbreviations).
    Evidence strings are human-readable (file:line where available).
    """
    # ── Node categories ──────────────────────────────────────────────────────
    services = [
        {
            "id":        n.id,
            "name":      n.label,
            "type":      n.type,
            "framework": n.metadata.get("framework") or "",
        }
        for n in graph.nodes
        if n.type in ("service", "frontend")
    ]

    data_stores = [
        {"id": n.id, "name": n.label, "type": n.type}
        for n in graph.nodes
        if n.type in ("database", "cache", "queue")
    ]

    externals = [
        {
            "id":       n.id,
            "name":     n.label,
            "evidence": _external_evidence(n.id, n.label, scan),
        }
        for n in graph.nodes
        if n.type == "external_api"
    ]

    # ── Connections with human-readable evidence ─────────────────────────────
    seen: set[str] = set()
    connections: list[dict] = []
    for e in graph.edges:
        eid = f"{e.source}--{e.target}"
        if eid in seen:
            continue
        seen.add(eid)
        connections.append({
            "from":       e.source,
            "to":         e.target,
            "kind":       e.type,
            "confidence": e.confidence,
            "evidence":   _edge_evidence_str(e),
        })

    # ── API surface: top 20 endpoints sorted by path ─────────────────────────
    api_surface = [
        {"method": a.method, "path": a.path}
        for a in sorted(scan.apis, key=lambda a: a.path)[:20]
    ]

    # ── Signals: non-graph scanner observations ───────────────────────────────
    signals = {
        "env_providers":  sorted({h.provider for h in scan.env_vars})[:10],
        "auth_patterns":  scan.auth_patterns[:6],
        "cicd":           [c.platform for c in scan.cicd],
        "observability":  scan.observability_libs[:6],
        "webhooks":       [w.path for w in scan.webhook_routes[:6]],
        "infra_files":    list(scan.infra_content.keys())[:6],
    }
    system_context_hints = build_system_context_spec(scan, graph)
    conceptual_hints = build_conceptual_spec(scan, graph)

    return {
        "services":    services[:15],
        "data_stores": data_stores[:10],
        "externals":   externals[:12],
        "connections": connections[:25],
        "api_surface": api_surface,
        "signals":     signals,
        "system_context_hints": {
            "system": {
                "label": system_context_hints["system"]["label"],
                "description": system_context_hints["system"]["description"],
            },
            "actors": [
                {"label": actor["label"], "description": actor["description"]}
                for actor in system_context_hints["actors"]
            ],
            "identity": [
                {"label": node["label"], "description": node["description"]}
                for node in system_context_hints["identity"]
            ],
            "partners": [
                {"label": node["label"], "description": node["description"]}
                for node in system_context_hints["partners"]
            ],
            "edges": system_context_hints["edges"],
        },
        "conceptual_hints": {
            "system": {
                "label": conceptual_hints["system"]["label"],
                "description": conceptual_hints["system"]["description"],
            },
            "actors": [
                {"label": actor["label"], "description": actor["description"]}
                for actor in conceptual_hints["actors"]
            ],
            "capabilities": [
                {
                    "label": capability["label"],
                    "description": capability["description"],
                }
                for capability in conceptual_hints["capabilities"]
            ],
            "external_partners": [
                {"label": node["label"], "description": node["description"]}
                for node in conceptual_hints["external_partners"]
            ],
            "gaps": [
                {"label": gap["label"], "description": gap["description"]}
                for gap in conceptual_hints["gaps"]
            ],
            "edges": conceptual_hints["edges"],
        },
        "naming_hint":    _naming_hint(scan.services),
        "gaps":           _detect_gaps(scan, graph),
        "readme_summary": scan.readme_summary,
    }


# ── Evidence helpers ────────────────────────────────────────────────────────────

def _external_evidence(node_id: str, node_label: str, scan: RepoScan) -> str:
    label_lower = node_label.lower()
    # Prefer env var hit — most specific (has file:line)
    for hit in scan.env_vars:
        if hit.provider.lower() == label_lower or hit.provider.lower() in label_lower:
            return f"{hit.name} in {hit.file}:{hit.line}"
    # Fall back to http_call hit
    for hit in scan.http_calls:
        if any(part in hit.domain for part in node_id.replace("-", ".").split(".")):
            return f"HTTP call to {hit.domain} in {hit.file}:{hit.line}"
    return "detected in dependency files"


def _edge_evidence_str(edge: Edge) -> str:
    if edge.confidence == "inferred":
        indicator = (edge.evidence or {}).get("indicator", "")
        return f"inferred — no direct dep file match" + (f" (hint: {indicator})" if indicator else "")
    ev = edge.evidence or {}
    indicator = ev.get("indicator", "")
    service   = ev.get("service", "")
    if indicator and service:
        return f'"{indicator}" in {service} deps'
    if indicator:
        return f'"{indicator}" detected'
    return "detected in dependency files"


# ── Naming convention hint ──────────────────────────────────────────────────────

def _naming_hint(services: list[str]) -> str:
    if not services:
        return ""
    found_suffixes = [suf for suf in _COMMON_SUFFIXES
                      if any(s.lower().endswith(suf) for s in services)]
    if found_suffixes:
        return f"Services use '{found_suffixes[0]}' suffix pattern (e.g. {services[0]})"
    if sum(1 for s in services if "-" in s) > len(services) // 2:
        return "Services use kebab-case naming"
    if sum(1 for s in services if "_" in s) > len(services) // 2:
        return "Services use snake_case naming"
    return f"Service names: {', '.join(services[:5])}"


# ── Static gap detection ────────────────────────────────────────────────────────

def _detect_gaps(scan: RepoScan, graph: ArchGraph) -> list[str]:
    """
    Pre-compute obvious integration gaps from scanner evidence.
    Feeding these to the LLM means it can surface them in the diagram
    rather than having to infer them from raw data.
    """
    gaps: list[str] = []
    ext_labels_lower = {n.label.lower() for n in graph.nodes if n.type == "external_api"}
    ext_ids_lower    = {n.id.lower()    for n in graph.nodes if n.type == "external_api"}

    def _is_covered(name: str) -> bool:
        name_l = name.lower().replace(" ", "-")
        return (name_l in ext_labels_lower or
                name_l in ext_ids_lower or
                any(name_l in lbl for lbl in ext_labels_lower))

    # Outbound HTTP calls to domains not represented as external nodes
    seen_domains: set[str] = set()
    for hit in scan.http_calls[:15]:
        if hit.domain in seen_domains:
            continue
        seen_domains.add(hit.domain)
        # Strip subdomain — "api.stripe.com" → check "stripe"
        parts = hit.domain.lower().split(".")
        significant = [p for p in parts if p not in ("api", "www", "app", "com", "io", "net", "co")]
        covered = any(_is_covered(p) for p in significant)
        if not covered:
            gaps.append(
                f"Outbound HTTP to {hit.domain} ({hit.file}:{hit.line}) — no service node found"
            )

    # Env var providers with no matching graph node
    seen_providers: set[str] = set()
    for ev in scan.env_vars:
        p = ev.provider
        if p in seen_providers or p in {"Custom", "Unknown", "Generic", "App"}:
            continue
        seen_providers.add(p)
        if not _is_covered(p):
            gaps.append(
                f"{ev.name} env var ({p}) present but no {p} node in the graph"
            )

    # Webhook routes whose provider isn't a graph node
    for wh in scan.webhook_routes[:6]:
        if wh.provider and wh.provider not in {"Unknown", "generic"}:
            if not _is_covered(wh.provider):
                gaps.append(
                    f"Webhook {wh.path} references {wh.provider} but no {wh.provider} node found"
                )

    # Observability instrumented but no collector/sink in infra
    if scan.observability_libs and not scan.infra_content:
        libs = ", ".join(scan.observability_libs[:3])
        gaps.append(
            f"Observability libs ({libs}) detected but no infra collector/sink config found"
        )

    return gaps[:8]


# ── Prompt builders ─────────────────────────────────────────────────────────────

def _build_prompt(view_id: str, ctx: dict) -> str:
    if view_id == "conceptual":
        return _prompt_conceptual_v2(ctx)
    if view_id == "system_context":
        return _prompt_system_context_v2(ctx)
    if view_id == "component":
        return _prompt_component(ctx)
    if view_id == "operational":
        return _prompt_operational(ctx)
    raise ValueError(f"Unknown view_id: {view_id}")


def _prompt_conceptual(ctx: dict) -> str:
    facts_dict: dict = {
        "api_routes":    ctx["api_surface"][:12],
        "env_providers": ctx["signals"]["env_providers"],
        "auth_patterns": ctx["signals"]["auth_patterns"],
        "external_sdks": [e["name"] for e in ctx["externals"]],
        "gaps":          ctx["gaps"],
    }
    if ctx.get("readme_summary"):
        facts_dict["readme_summary"] = ctx["readme_summary"]
    facts = json.dumps(facts_dict, separators=(",", ":"))

    return (
        _CONSTRAINT_PREFIX
        + f"FACTS:\n{facts}\n\n"
        "Task: Business capability map.\n"
        "- type=actor: who uses the system (infer from auth_patterns and api_routes: "
        "'End User','Admin','Developer')\n"
        "- type=capability: one node per named business domain inferred from api_routes "
        "(/users→'Identity Management', /products→'Product Catalog', /orders→'Order Management')\n"
        "- type=external: one node per env_providers entry + per external_sdks entry (real names)\n"
        "- type=gap: one node per item in gaps, group=gaps\n"
        "- groups: actors→'users', capabilities→'capabilities', "
        "externals→'external_partners', gaps→'gaps'\n"
        "- description: one sentence describing what this actor/capability/integration does\n"
        "- Max 14 nodes total. Up to 3 inferred edges, label 'suggested: <reason>'\n\n"
        '{"nodes":[{"id":"..","label":"..","type":"actor|capability|external|gap",'
        '"group":"users|capabilities|external_partners|gaps","description":".."}],'
        '"edges":[{"source":"..","target":"..","label":"..","confidence":"verified|inferred"}],'
        '"groups":[{"id":"users","label":"Users & Actors"},'
        '{"id":"capabilities","label":"Business Capabilities"},'
        '{"id":"external_partners","label":"External Partners"},'
        '{"id":"gaps","label":"Detected Gaps"}]}'
    )


def _prompt_conceptual_v2(ctx: dict) -> str:
    facts_dict: dict = {
        "api_routes": ctx["api_surface"][:12],
        "env_providers": ctx["signals"]["env_providers"],
        "auth_patterns": ctx["signals"]["auth_patterns"],
        "external_sdks": [e["name"] for e in ctx["externals"]],
        "conceptual_hints": ctx["conceptual_hints"],
        "gaps": ctx["gaps"],
    }
    if ctx.get("readme_summary"):
        facts_dict["readme_summary"] = ctx["readme_summary"]
    facts = json.dumps(facts_dict, separators=(",", ":"))

    return (
        _CONSTRAINT_PREFIX
        + f"FACTS:\n{facts}\n\n"
        "Task: Business capability map.\n"
        "- Start from conceptual_hints. Preserve the same actor, system, capability, partner, and gap intent unless FACTS clearly contradict it.\n"
        "- group=users: actor nodes representing the people or external clients using the system\n"
        "- group=system: EXACTLY ONE node for the system boundary and value proposition\n"
        "- group=capabilities: named business capability nodes like catalog, orders, payments, collaboration, analytics, or repository analysis\n"
        "- group=external_partners: supporting partner platforms or providers\n"
        "- group=gaps: unresolved architecture ambiguities that matter to understanding the business view\n"
        "- description: one sentence explaining the role of each actor, capability, partner, gap, or system node\n"
        "- Max 14 nodes total. Up to 3 inferred edges, label 'suggested: <reason>'\n\n"
        '{"nodes":[{"id":"..","label":"..","type":"frontend|backend|external","group":"users|system|capabilities|external_partners|gaps","description":".."}],'
        '"edges":[{"source":"..","target":"..","label":"..","confidence":"verified|inferred"}],'
        '"groups":[{"id":"users","label":"Users & Actors"},'
        '{"id":"system","label":"System Boundary"},'
        '{"id":"capabilities","label":"Business Capabilities"},'
        '{"id":"external_partners","label":"External Partners"},'
        '{"id":"gaps","label":"Detected Gaps"}]}'
    )


def _prompt_system_context(ctx: dict) -> str:
    facts_dict: dict = {
        "env_providers": ctx["signals"]["env_providers"],
        "auth_patterns": ctx["signals"]["auth_patterns"],
        "webhooks":      ctx["signals"]["webhooks"],
        "externals":     [{"name": e["name"], "evidence": e["evidence"]}
                          for e in ctx["externals"]],
        "services":      [s["name"] for s in ctx["services"]],
        "gaps":          ctx["gaps"][:4],
    }
    if ctx.get("readme_summary"):
        facts_dict["readme_summary"] = ctx["readme_summary"]
    facts = json.dumps(facts_dict, separators=(",", ":"))

    return (
        _CONSTRAINT_PREFIX
        + f"FACTS:\n{facts}\n\n"
        "Task: C4 System Context diagram.\n"
        "- group=actors: max 3 nodes (infer from auth_patterns and api usage: "
        "'End User','Admin','Developer')\n"
        "- group=system: EXACTLY ONE node, id='your-system', "
        "label=<infer a good name from services list and readme_summary>, type=backend\n"
        "- group=partners: one external node per env_providers + per externals "
        "(use REAL service names: 'Stripe', 'AWS S3', 'Twilio')\n"
        "- group=identity: one node per auth_pattern that names a real IdP "
        "('Auth0','Okta','Cognito','Firebase Auth','Clerk')\n"
        "- description: one sentence — actors: who they are; system: what it does; "
        "partners: what integration it provides\n"
        "- Connections to partners with evidence: confidence=verified. Others: confidence=inferred.\n"
        "- Webhook inbound: arrow from the webhook provider to your-system\n\n"
        '{"nodes":[{"id":"..","label":"..","type":"frontend|backend|external",'
        '"group":"actors|system|partners|identity","description":".."}],'
        '"edges":[{"source":"..","target":"..","label":"..","confidence":"verified|inferred"}],'
        '"groups":[{"id":"actors","label":"Users & Actors"},'
        '{"id":"system","label":"Your System"},'
        '{"id":"partners","label":"External Partners"},'
        '{"id":"identity","label":"Identity Providers"}]}'
    )


def _prompt_system_context_v2(ctx: dict) -> str:
    facts_dict: dict = {
        "env_providers": ctx["signals"]["env_providers"],
        "auth_patterns": ctx["signals"]["auth_patterns"],
        "webhooks": ctx["signals"]["webhooks"],
        "externals": [{"name": e["name"], "evidence": e["evidence"]} for e in ctx["externals"]],
        "services": [s["name"] for s in ctx["services"]],
        "system_context_hints": ctx["system_context_hints"],
        "gaps": ctx["gaps"][:4],
    }
    if ctx.get("readme_summary"):
        facts_dict["readme_summary"] = ctx["readme_summary"]
    facts = json.dumps(facts_dict, separators=(",", ":"))

    return (
        _CONSTRAINT_PREFIX
        + f"FACTS:\n{facts}\n\n"
        "Task: C4 System Context diagram.\n"
        "- Start from system_context_hints. Preserve the same actor, system, partner, and identity intent unless FACTS clearly contradict it.\n"
        "- group=actors: at most 3 actor nodes, preferring the labels from system_context_hints.actors\n"
        "- group=system: EXACTLY ONE node representing our system boundary, using system_context_hints.system.label unless there is a stronger FACT-backed name\n"
        "- group=partners: external systems the application calls or receives webhooks from\n"
        "- group=identity: real authentication and identity providers only\n"
        "- description: one sentence explaining who the actor is, what the system does, or what the partner or identity system provides\n"
        "- Connections to partners with evidence: confidence=verified. Others: confidence=inferred.\n"
        "- Webhook inbound: arrow from the webhook provider to the system node\n\n"
        '{"nodes":[{"id":"..","label":"..","type":"frontend|backend|external",'
        '"group":"actors|system|partners|identity","description":".."}],'
        '"edges":[{"source":"..","target":"..","label":"..","confidence":"verified|inferred"}],'
        '"groups":[{"id":"actors","label":"Users & Actors"},'
        '{"id":"system","label":"Your System"},'
        '{"id":"partners","label":"External Partners"},'
        '{"id":"identity","label":"Identity Providers"}]}'
    )


def _prompt_component(ctx: dict) -> str:
    facts_dict: dict = {
        "services":    ctx["services"],
        "data_stores": ctx["data_stores"],
        "externals":   [{"id": e["id"], "name": e["name"]} for e in ctx["externals"]],
        "connections": ctx["connections"],
        "naming_hint": ctx["naming_hint"],
        "gaps":        ctx["gaps"][:3],
    }
    if ctx.get("readme_summary"):
        facts_dict["readme_summary"] = ctx["readme_summary"]
    facts = json.dumps(facts_dict, separators=(",", ":"))

    return (
        _CONSTRAINT_PREFIX
        + f"FACTS:\n{facts}\n\n"
        "Task: Component view.\n"
        "COMPONENT VIEW RULE: Use ONLY the node ids provided in services, data_stores, "
        "and externals. Never invent component nodes.\n"
        "CRITICAL: Use the EXACT ids from services, data_stores, and externals. "
        "Do not add or remove nodes.\n"
        "- Assign each node to a meaningful domain group (max 5 groups total)\n"
        "- Use naming_hint and readme_summary to infer domain groupings\n"
        "- description: one sentence describing what this service/datastore does\n"
        "- Improve connection labels with protocol names (REST, SQL, Redis, AMQP, gRPC, HTTPS)\n"
        "- Use connection evidence to choose the right label "
        "(evidence 'psycopg2' → label 'PostgreSQL/SQL'; 'redis' → 'Redis cache')\n"
        "- Add at most 3 hypothesized connections: confidence=inferred, "
        "label='suggested: <reason>'. Only use existing ids.\n\n"
        '{"nodes":[{"id":"..","label":"..","type":"..","group":"..","description":".."}],'
        '"edges":[{"source":"..","target":"..","label":"..","confidence":"verified|inferred"}],'
        '"groups":[{"id":"..","label":".."}]}'
    )


def _prompt_operational(ctx: dict) -> str:
    svc_ids = [s["id"] for s in ctx["services"]]
    facts = json.dumps({
        "services":      svc_ids,
        "cicd":          ctx["signals"]["cicd"],
        "infra_files":   ctx["signals"]["infra_files"],
        "observability": ctx["signals"]["observability"],
        "auth_patterns": ctx["signals"]["auth_patterns"],
    }, separators=(",", ":"))

    return (
        _CONSTRAINT_PREFIX
        + f"FACTS:\n{facts}\n\n"
        "Task: Deployment / DevOps view.\n"
        "- If cicd AND infra_files are BOTH empty: return "
        '{"nodes":[],"edges":[],"groups":[]}\n'
        "- group=cicd: stage nodes per platform in cicd "
        "(github_actions→'Build','Test','Deploy' nodes)\n"
        "- group=runtime: runtime environment from infra_files "
        "('Docker Compose','Kubernetes Cluster','Terraform Cloud')\n"
        "- group=services: one node per service id\n"
        "- group=observability: one collector/sink node per observability lib "
        "('OpenTelemetry Collector','Sentry','Datadog')\n"
        "- group=identity: auth service node if auth_patterns non-empty\n"
        "- description: one sentence describing the deployment role of each node\n"
        "- Flow: cicd → runtime → services; services → observability for telemetry\n\n"
        '{"nodes":[{"id":"..","label":"..","type":"worker|backend|external",'
        '"group":"cicd|runtime|services|observability|identity","description":".."}],'
        '"edges":[{"source":"..","target":"..","label":"..","confidence":"verified|inferred"}],'
        '"groups":[{"id":"cicd","label":"CI/CD Pipeline"},'
        '{"id":"runtime","label":"Runtime"},'
        '{"id":"services","label":"Services"},'
        '{"id":"observability","label":"Observability"}]}'
    )


# ── Response parser ─────────────────────────────────────────────────────────────

def _parse_view_response(
    raw: str,
    view_id: str,
    fallback: DiagramView,
    canonical_ids: set[str],
) -> DiagramView:
    try:
        data = _extract_json_object(raw)

        raw_nodes  = data.get("nodes", [])
        raw_edges  = data.get("edges", [])
        raw_groups = data.get("groups", [])

        if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
            raise ValueError("nodes/edges must be lists")

        nodes: list[DiagramNode] = []
        for n in raw_nodes:
            if not isinstance(n, dict) or not n.get("id"):
                continue
            nid = str(n["id"])
            # Anti-hallucination: component view must only use canonical graph ids
            if view_id == "component" and nid not in canonical_ids:
                logger.debug("Rejected hallucinated node '%s' in component view", nid)
                continue
            raw_type = str(n.get("type", "backend"))
            ui_type  = _LLM_TYPE_REMAP.get(raw_type, raw_type)
            if ui_type not in _VALID_UI_TYPES:
                ui_type = "backend"
            nodes.append(DiagramNode(
                id=nid,
                label=str(n.get("label", nid)),
                type=ui_type,
                layer=_TYPE_LAYER.get(ui_type, "application"),
                group=n.get("group") or _TYPE_GROUP.get(ui_type, "core"),
                severity=n.get("severity") or None,
                description=str(n.get("description", "")),
            ))

        if not nodes:
            raise ValueError("No valid nodes in LLM response")

        edges: list[DiagramEdge] = []
        inferred_count = 0
        for e in raw_edges:
            if not isinstance(e, dict) or not e.get("source") or not e.get("target"):
                continue
            conf  = e.get("confidence", "verified")
            if conf not in ("verified", "inferred"):
                conf = "inferred"
            label = str(e.get("label", ""))
            if conf == "inferred":
                if inferred_count >= 3:
                    continue
                inferred_count += 1
                if not label.startswith("suggested:"):
                    label = f"suggested: {label}" if label else "suggested"
            eid = e.get("id") or f"{e['source']}--{e['target']}"
            edges.append(DiagramEdge(
                id=str(eid), source=str(e["source"]), target=str(e["target"]),
                label=label, confidence=conf,
            ))

        groups: list[DiagramGroup] = []
        seen_gids: set[str] = set()
        for g in raw_groups:
            if not isinstance(g, dict) or not g.get("id"):
                continue
            gid = str(g["id"])
            if gid in seen_gids:
                continue
            seen_gids.add(gid)
            groups.append(DiagramGroup(id=gid, label=str(g.get("label", gid))))

        if view_id == "system_context" and not _is_valid_system_context(nodes):
            raise ValueError("System context response missing required system/actor structure")
        if view_id == "conceptual" and not _is_valid_conceptual(nodes):
            raise ValueError("Conceptual response missing required system/capability structure")

        return DiagramView(
            id=view_id,
            label=fallback.label,
            nodes=nodes,
            edges=edges,
            groups=groups,
        )

    except Exception as exc:
        logger.warning(
            "Failed to parse LLM response for '%s': %s — using fallback", view_id, exc
        )
        return fallback


def _extract_json_object(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found in LLM response")

    depth     = 0
    in_string = False
    escape    = False
    for i, ch in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])

    raise ValueError("Unbalanced braces in LLM response")


def _is_valid_system_context(nodes: list[DiagramNode]) -> bool:
    system_nodes = [node for node in nodes if node.group == "system" or node.id in {"your-system", "ctx-system"}]
    actor_nodes = [node for node in nodes if node.group == "actors"]
    partner_nodes = [node for node in nodes if node.group in {"partners", "identity"}]
    return len(system_nodes) == 1 and bool(actor_nodes or partner_nodes)


def _is_valid_conceptual(nodes: list[DiagramNode]) -> bool:
    system_nodes = [node for node in nodes if node.group == "system" or node.id == "concept-system"]
    capability_nodes = [node for node in nodes if node.group == "capabilities"]
    actor_nodes = [node for node in nodes if node.group == "users"]
    return len(system_nodes) == 1 and bool(capability_nodes) and bool(actor_nodes)
