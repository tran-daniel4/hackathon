from __future__ import annotations

from bottlenecks.models import ConfidenceLabel, FinalFinding, RepoSignals, Severity

_SEVERITY_WEIGHT: dict[Severity, float] = {
    "low": 0.25,
    "medium": 0.50,
    "high": 0.75,
    "critical": 1.00,
}

_CONFIDENCE_BASELINE: dict[ConfidenceLabel, float] = {
    "weak_static_signal": 0.35,
    "medium_static_signal": 0.55,
    "strong_static_signal": 0.75,
    "very_strong_static_signal": 0.90,
}

_SEVERITY_RANK: dict[Severity, int] = {
    "critical": 0,
    "high": 1,
    "medium": 2,
    "low": 3,
}


def severity_rank(severity: Severity) -> int:
    return _SEVERITY_RANK[severity]


def label_for_confidence(confidence: float) -> ConfidenceLabel:
    if confidence >= 0.90:
        return "very_strong_static_signal"
    if confidence >= 0.75:
        return "strong_static_signal"
    if confidence >= 0.55:
        return "medium_static_signal"
    return "weak_static_signal"


def clamp_confidence(confidence: float, fallback_label: ConfidenceLabel) -> tuple[float, ConfidenceLabel]:
    bounded = max(0.0, min(confidence, 1.0))
    label = label_for_confidence(bounded) if bounded else fallback_label
    return round(bounded, 2), label


def compute_score(
    *,
    severity: Severity,
    confidence: float,
    affected_route_ids: list[str],
    affected_node_ids: list[str],
    signals: RepoSignals,
    external_provider: bool = False,
    database_write: bool = False,
    config_only: bool = False,
) -> float:
    route_map = {route.id: route for route in signals.routes}
    modifier = 0.0
    for route_id in affected_route_ids:
        route = route_map.get(route_id)
        if not route:
            continue
        if route.request_path:
            modifier += 0.10
        if route.public_endpoint:
            modifier += 0.10
        if route.background_only:
            modifier -= 0.10
        if route.test_only:
            modifier -= 0.20
    if external_provider:
        modifier += 0.10
    if database_write:
        modifier += 0.10
    if config_only:
        modifier -= 0.10
    base = _SEVERITY_WEIGHT[severity] * confidence
    return round(max(0.0, min(1.0, base + modifier)), 3)


def overall_risk(findings: list[FinalFinding]) -> Severity:
    if not findings:
        return "low"
    return min((finding.severity for finding in findings), key=severity_rank)


def average_confidence(findings: list[FinalFinding]) -> float:
    if not findings:
        return 0.0
    return round(sum(finding.confidence for finding in findings) / len(findings), 2)


def sort_findings(findings: list[FinalFinding]) -> list[FinalFinding]:
    return sorted(findings, key=lambda item: (-item.score, severity_rank(item.severity), item.title.lower()))
