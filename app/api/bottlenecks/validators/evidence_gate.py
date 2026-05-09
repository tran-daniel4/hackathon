from __future__ import annotations

import re

from bottlenecks.models import DeepSeekReview, GroupedFinding, ReviewedFinding, RuleFinding
from graph.models import GraphFacts

_TELEMETRY_CLAIMS_RE = re.compile(
    r"\b(p99|p95|p50|latency is|is overloaded|backlog is|throughput is|error rate is|saturated|currently slow)\b",
    re.IGNORECASE,
)


def validate_review(review: DeepSeekReview, deterministic_findings: list[RuleFinding], graph_facts: GraphFacts) -> DeepSeekReview:
    finding_ids = {finding.id for finding in deterministic_findings}
    node_ids = {node.id for node in graph_facts.nodes}
    edge_ids = {edge.id for edge in graph_facts.edges}
    route_ids = {api.id for api in graph_facts.apis}

    valid_reviewed: list[ReviewedFinding] = []
    for item in review.reviewed_findings:
        if item.finding_id not in finding_ids:
            continue
        if _contains_invalid_runtime_claim(item.why) or _contains_invalid_runtime_claim(item.impact):
            continue
        valid_reviewed.append(item)

    valid_grouped: list[GroupedFinding] = []
    for item in review.grouped_findings:
        if not item.finding_ids or any(finding_id not in finding_ids for finding_id in item.finding_ids):
            continue
        if any(node_id not in node_ids for node_id in item.affected_node_ids):
            continue
        if any(edge_id not in edge_ids for edge_id in item.affected_edge_ids):
            continue
        if any(route_id not in route_ids for route_id in item.affected_route_ids):
            continue
        if _contains_invalid_runtime_claim(item.why):
            continue
        valid_grouped.append(item)

    return DeepSeekReview(
        reviewed_findings=valid_reviewed,
        grouped_findings=valid_grouped,
        rejected_or_downgraded=review.rejected_or_downgraded,
    )


def _contains_invalid_runtime_claim(text: str) -> bool:
    return bool(_TELEMETRY_CLAIMS_RE.search(text or ""))
