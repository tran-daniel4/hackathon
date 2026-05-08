from __future__ import annotations

import json
import logging
from collections import defaultdict

from bottlenecks.evidence import build_evidence_snippets
from bottlenecks.models import DeepSeekReview, RepoSignals, RuleFinding
from graph.models import GraphFacts
from pipeline.llm_wrapper import LLMConfig, _call_ollama, _call_openai_compat

logger = logging.getLogger(__name__)


def review_findings_with_deepseek(
    findings: list[RuleFinding],
    graph_facts: GraphFacts,
    repo_signals: RepoSignals,
    *,
    config: LLMConfig | None = None,
) -> DeepSeekReview:
    if not findings:
        return DeepSeekReview()
    cfg = config or LLMConfig()
    bundles = _bundle_findings(findings)
    merged = DeepSeekReview()
    for bundle in bundles:
        prompt = _build_prompt(bundle, graph_facts, repo_signals)
        try:
            raw = _call_llm(prompt, cfg)
            payload = json.loads(_extract_json(raw))
            review = DeepSeekReview.model_validate(payload)
        except Exception as exc:
            logger.warning("DeepSeek bottleneck review skipped for bundle: %s", exc)
            continue
        merged.reviewed_findings.extend(review.reviewed_findings)
        merged.grouped_findings.extend(review.grouped_findings)
        merged.rejected_or_downgraded.extend(review.rejected_or_downgraded)
    return merged


def _bundle_findings(findings: list[RuleFinding]) -> list[list[RuleFinding]]:
    grouped: dict[str, list[RuleFinding]] = defaultdict(list)
    for finding in findings:
        bundle_key = (
            finding.affected_route_ids[0]
            if finding.affected_route_ids
            else finding.affected_node_ids[0]
            if finding.affected_node_ids
            else finding.risk_type
        )
        grouped[bundle_key].append(finding)
    bundles: list[list[RuleFinding]] = []
    for items in grouped.values():
        chunk: list[RuleFinding] = []
        for item in items:
            chunk.append(item)
            if len(chunk) >= 4:
                bundles.append(chunk)
                chunk = []
        if chunk:
            bundles.append(chunk)
    return bundles


def _build_prompt(bundle: list[RuleFinding], graph_facts: GraphFacts, repo_signals: RepoSignals) -> str:
    affected_routes = [route for route in repo_signals.routes if any(route.id in finding.affected_route_ids for finding in bundle)]
    path_summary = [
        {
            "route_id": route.id,
            "component_id": route.component_id,
            "method": route.method,
            "path": route.path,
        }
        for route in affected_routes[:4]
    ]
    repo_summary = {
        "repo": graph_facts.repo.name,
        "services": len(graph_facts.nodes),
        "apis": len(graph_facts.apis),
        "framework_hints": sorted({node.framework for node in graph_facts.nodes if node.framework})[:6],
    }
    evidence_ids = []
    for finding in bundle:
        evidence_ids.extend(finding.evidence_ids)
    prompt_payload = {
        "graph_path_summary": path_summary,
        "repo_summary": repo_summary,
        "rule_findings": [finding.model_dump() for finding in bundle],
        "evidence_snippets": build_evidence_snippets(graph_facts, list(dict.fromkeys(evidence_ids))),
    }
    return (
        "You are a static architecture bottleneck review agent.\n"
        "Rules:\n"
        "1. Do not invent new bottlenecks.\n"
        "2. Do not invent telemetry.\n"
        "3. Do not claim that a system is slow in production.\n"
        "4. You may only review provided finding_ids.\n"
        "5. You may only reference provided evidence_ids.\n"
        "6. You may adjust severity/confidence within reason.\n"
        "7. You may group related findings.\n"
        "8. Return valid JSON only.\n\n"
        f"Review these deterministic bottleneck findings.\n{json.dumps(prompt_payload, separators=(',', ':'))}\n\n"
        "Return JSON only in this shape:\n"
        '{"schema_version":"1.0","reviewed_findings":[{"finding_id":"string","risk_type":"string","recommended_title":"string","recommended_severity":"low|medium|high|critical","recommended_confidence":0.7,"confidence_label":"weak_static_signal|medium_static_signal|strong_static_signal|very_strong_static_signal","why":"string","impact":"string","recommendations":["string"],"telemetry_needed_to_confirm":["string"]}],"grouped_findings":[{"group_id":"string","title":"string","finding_ids":["string"],"risk_type":"string","affected_node_ids":["string"],"affected_edge_ids":["string"],"affected_route_ids":["string"],"why":"string","recommended_severity":"low|medium|high|critical","recommended_confidence":0.7}],"rejected_or_downgraded":[{"finding_id":"string","reason":"string","recommended_action":"reject|downgrade|keep"}]}'
    )


def _call_llm(prompt: str, cfg: LLMConfig) -> str:
    if cfg.provider == "ollama":
        return _call_ollama(prompt, cfg)
    return _call_openai_compat(prompt, cfg)


def _extract_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("{") and raw.endswith("}"):
        return raw
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        return raw[start:end + 1]
    raise ValueError("No JSON object found in DeepSeek response")
