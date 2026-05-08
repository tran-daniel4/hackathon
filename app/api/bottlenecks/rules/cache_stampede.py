from __future__ import annotations

from bottlenecks.models import FindingSignal, RepoSignals, RuleFinding
from bottlenecks.rules.base import finding
from graph.models import GraphFacts


def detect_cache_stampede(graph_facts: GraphFacts, repo_signals: RepoSignals) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    db_by_route: dict[str, list] = {}
    for db_call in repo_signals.db_calls:
        if db_call.enclosing_route_id:
            db_by_route.setdefault(db_call.enclosing_route_id, []).append(db_call)
    route_groups: dict[tuple[str, str | None], list] = {}
    for cache_call in repo_signals.cache_calls:
        route_groups.setdefault((cache_call.file_path, cache_call.enclosing_route_id), []).append(cache_call)

    for (_, route_id), cache_calls in route_groups.items():
        has_get = any(call.operation == "get" for call in cache_calls)
        has_set = any(call.operation == "set" for call in cache_calls)
        coordinated = any(call.coordination_detected for call in cache_calls)
        if not has_get or not has_set or coordinated:
            continue
        db_calls = db_by_route.get(route_id or "", [])
        if not db_calls:
            continue
        component_id = cache_calls[0].component_id
        evidence_ids = [call.evidence_id for call in cache_calls] + [call.evidence_id for call in db_calls]
        findings.append(finding(
            id=f"rf_cache_stampede_{len(findings) + 1:03d}",
            rule_id="cache_stampede",
            risk_type="cache_stampede",
            category="cache",
            title="Possible cache stampede pattern",
            severity_hint="medium",
            confidence=0.68,
            confidence_label="medium_static_signal",
            affected_node_ids=[component_id],
            affected_route_ids=[route_id] if route_id else [],
            evidence_ids=evidence_ids,
            signals=[FindingSignal(
                type="cache_call",
                file_path=cache_calls[0].file_path,
                start_line=cache_calls[0].start_line,
                end_line=cache_calls[-1].end_line,
                details={"coordination_detected": coordinated},
            )],
            why="A cache get -> database query -> cache set flow was detected without an obvious coordination mechanism.",
            impact="A cold or expired key can cause many identical database loads at once under burst traffic.",
            recommendations=[
                "Add singleflight, lock, or stale-while-revalidate protection around hot keys.",
                "Add jitter to TTLs for high-traffic cached reads.",
            ],
            telemetry_needed_to_confirm=["cache miss bursts", "database spikes during key expiry", "cache hit ratio"],
        ))
    return findings
