from __future__ import annotations

from collections.abc import Callable

from bottlenecks.models import ConfidenceLabel, RepoSignals, RuleFinding
from graph.models import GraphFacts

RuleFn = Callable[[GraphFacts, RepoSignals], list[RuleFinding]]


def finding(
    *,
    id: str,
    rule_id: str,
    risk_type: str,
    category: str,
    title: str,
    severity_hint: str,
    confidence: float,
    confidence_label: ConfidenceLabel,
    why: str,
    affected_node_ids: list[str] | None = None,
    affected_edge_ids: list[str] | None = None,
    affected_route_ids: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    signals: list | None = None,
    impact: str = "",
    recommendations: list[str] | None = None,
    telemetry_needed_to_confirm: list[str] | None = None,
) -> RuleFinding:
    return RuleFinding(
        id=id,
        rule_id=rule_id,
        risk_type=risk_type,
        category=category,
        title=title,
        affected_node_ids=affected_node_ids or [],
        affected_edge_ids=affected_edge_ids or [],
        affected_route_ids=affected_route_ids or [],
        severity_hint=severity_hint,  # type: ignore[arg-type]
        confidence=round(confidence, 2),
        confidence_label=confidence_label,
        evidence_ids=list(dict.fromkeys(evidence_ids or [])),
        signals=signals or [],
        why=why,
        impact=impact,
        recommendations=recommendations or [],
        telemetry_needed_to_confirm=telemetry_needed_to_confirm or [],
    )


def run_all_rules(graph_facts: GraphFacts, repo_signals: RepoSignals) -> list[RuleFinding]:
    from bottlenecks.rules.blocking_io import detect_blocking_io
    from bottlenecks.rules.cache_stampede import detect_cache_stampede
    from bottlenecks.rules.cpu_heavy_request_path import detect_cpu_heavy_request_path
    from bottlenecks.rules.db_hotspot import detect_db_hotspot
    from bottlenecks.rules.excessive_logging import detect_excessive_logging
    from bottlenecks.rules.external_dependency_path import detect_external_dependency_in_request_path
    from bottlenecks.rules.fanout import detect_fanout
    from bottlenecks.rules.long_sync_chain import detect_long_sync_chain
    from bottlenecks.rules.missing_pagination import detect_missing_pagination
    from bottlenecks.rules.missing_timeout import detect_missing_timeout
    from bottlenecks.rules.n_plus_one import detect_n_plus_one
    from bottlenecks.rules.shared_database import detect_shared_database
    from bottlenecks.rules.unbounded_queue import detect_unbounded_queue_or_missing_dlq

    rules: list[RuleFn] = [
        detect_long_sync_chain,
        detect_fanout,
        detect_shared_database,
        detect_db_hotspot,
        detect_external_dependency_in_request_path,
        detect_missing_timeout,
        detect_n_plus_one,
        detect_missing_pagination,
        detect_blocking_io,
        detect_cache_stampede,
        detect_unbounded_queue_or_missing_dlq,
        detect_cpu_heavy_request_path,
        detect_excessive_logging,
    ]
    findings: list[RuleFinding] = []
    for rule in rules:
        findings.extend(rule(graph_facts, repo_signals))
    return findings
