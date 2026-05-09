"""
Bottleneck Aggregator — pure Python, no LLM.
Merges rule-based detections and LLM enrichments into a single clean report.

Steps:
  1. Deduplicate issues of the same type (merge affected lists)
  2. Pick the best available explanation (LLM > rule)
  3. Assign a final confidence score
  4. Compute an overall risk score (0–100)
"""
from typing import Literal

from pydantic import BaseModel

from pipeline.llm_wrapper import EnrichedIssue


# ── Output schema ──────────────────────────────────────────────────────────────

class BottleneckSummary(BaseModel):
    type: str
    severity: Literal["low", "medium", "high", "critical"]
    affected: list[str]
    explanation: str      # best available explanation
    fix: str              # best available fix
    confidence: float     # 0.0 – 1.0
    source: Literal["rules", "rules+llm"]


class BottleneckReport(BaseModel):
    risk_score: float                # 0–100 weighted aggregate
    total_issues: int
    by_severity: dict[str, int]      # {"critical": N, "high": N, ...}
    issues: list[BottleneckSummary]


# ── Weights ────────────────────────────────────────────────────────────────────

_SEVERITY_RANK: dict[str, int] = {
    "critical": 0, "high": 1, "medium": 2, "low": 3,
}

# Base confidence when the LLM didn't enrich (rule-only)
_RULE_CONFIDENCE: dict[str, float] = {
    "critical": 0.90,
    "high":     0.80,
    "medium":   0.65,
    "low":      0.50,
}

# Points contributed to risk score per issue
_SEVERITY_WEIGHT: dict[str, float] = {
    "critical": 25.0,
    "high":     15.0,
    "medium":    8.0,
    "low":       3.0,
}

_MAX_RISK_SCORE = 100.0


# ── Public API ─────────────────────────────────────────────────────────────────

def aggregate(issues: list[EnrichedIssue]) -> BottleneckReport:
    """
    Produce a clean BottleneckReport from a list of (possibly LLM-enriched) issues.
    """
    deduped    = _deduplicate(issues)
    summaries  = [_to_summary(i) for i in deduped]
    summaries  = _sort_by_severity(summaries)

    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    raw_score   = 0.0
    for s in summaries:
        by_severity[s.severity] += 1
        raw_score += _SEVERITY_WEIGHT[s.severity] * s.confidence

    risk_score = min(raw_score, _MAX_RISK_SCORE)

    return BottleneckReport(
        risk_score=round(risk_score, 1),
        total_issues=len(summaries),
        by_severity=by_severity,
        issues=summaries,
    )


# ── Deduplication ──────────────────────────────────────────────────────────────

def _deduplicate(issues: list[EnrichedIssue]) -> list[EnrichedIssue]:
    """
    Merge issues of the same type into one entry.
    Keeps the highest severity and best (LLM-enriched) explanation.
    """
    groups: dict[str, list[EnrichedIssue]] = {}
    for issue in issues:
        groups.setdefault(issue.type, []).append(issue)

    merged: list[EnrichedIssue] = []
    for issue_type, group in groups.items():
        if len(group) == 1:
            merged.append(group[0])
            continue

        # Union of all affected nodes/files
        all_affected = list(dict.fromkeys(a for i in group for a in i.affected))

        # Worst severity in the group
        worst = min(group, key=lambda i: _SEVERITY_RANK[i.severity])

        # Best explanation: prefer LLM-enriched with highest confidence
        best = max(
            group,
            key=lambda i: (int(i.llm_enriched), i.llm_confidence),
        )

        merged.append(EnrichedIssue(
            type=issue_type,
            severity=worst.severity,
            affected=all_affected,
            description=best.description,
            recommendation=best.recommendation,
            llm_explanation=best.llm_explanation,
            llm_fix=best.llm_fix,
            llm_confidence=best.llm_confidence,
            llm_enriched=best.llm_enriched,
        ))

    return merged


# ── Summary builder ────────────────────────────────────────────────────────────

def _to_summary(issue: EnrichedIssue) -> BottleneckSummary:
    if issue.llm_enriched and issue.llm_explanation:
        explanation = issue.llm_explanation
        fix         = issue.llm_fix
        confidence  = issue.llm_confidence
        source: Literal["rules", "rules+llm"] = "rules+llm"
    else:
        explanation = issue.description
        fix         = issue.recommendation
        confidence  = _RULE_CONFIDENCE[issue.severity]
        source      = "rules"

    return BottleneckSummary(
        type=issue.type,
        severity=issue.severity,
        affected=issue.affected,
        explanation=explanation,
        fix=fix,
        confidence=round(confidence, 2),
        source=source,
    )


def _sort_by_severity(summaries: list[BottleneckSummary]) -> list[BottleneckSummary]:
    return sorted(summaries, key=lambda s: _SEVERITY_RANK.get(s.severity, 99))
