from __future__ import annotations

import hashlib
from collections import defaultdict

from pydantic import BaseModel

from analyzers.file_index import FileIndex
from bottlenecks.llm.deepseek_risk_reviewer import review_findings_with_deepseek
from bottlenecks.models import (
    BottleneckReportV2,
    BottleneckSummaryV2,
    FinalFinding,
    HotEdge,
    HotNode,
    LegacyIssue,
    RepoSignals,
    RuleFinding,
)
from bottlenecks.rules.base import run_all_rules
from bottlenecks.scoring import average_confidence, clamp_confidence, compute_score, overall_risk, sort_findings
from bottlenecks.signals.signal_index import build_repo_signals
from bottlenecks.validators.evidence_gate import validate_review
from bottlenecks.validators.finding_validator import validate_rule_findings
from graph.models import GraphFacts
from pipeline.aggregator import BottleneckReport as LegacyDiagramReport
from pipeline.aggregator import BottleneckSummary as LegacyDiagramIssue
from pipeline.llm_wrapper import LLMConfig


class LegacyBottleneckIssue(BaseModel):
    title: str
    severity: str
    summary: str
    affected: list[str]
    confidence: float


class LegacyBottleneckReport(BaseModel):
    risk_score: float
    total_issues: int
    by_severity: dict[str, int]
    issues: list[LegacyBottleneckIssue]


class BottleneckAnalysisResult(BaseModel):
    repo_signals: RepoSignals
    rule_findings: list[RuleFinding]
    report: BottleneckReportV2

    model_config = {"arbitrary_types_allowed": True}


def run_bottleneck_analysis(
    *,
    file_index: FileIndex,
    graph_facts: GraphFacts,
    config: LLMConfig | None = None,
) -> tuple[BottleneckAnalysisResult, LegacyDiagramReport]:
    repo_signals = build_repo_signals(file_index, graph_facts)
    rule_findings = validate_rule_findings(run_all_rules(graph_facts, repo_signals), graph_facts)
    review = validate_review(review_findings_with_deepseek(rule_findings, graph_facts, repo_signals, config=config), rule_findings, graph_facts)
    review_map = {item.finding_id: item for item in review.reviewed_findings}

    final_findings: list[FinalFinding] = []
    for finding in rule_findings:
        reviewed = review_map.get(finding.id)
        severity = reviewed.recommended_severity if reviewed else finding.severity_hint
        confidence_raw = reviewed.recommended_confidence if reviewed else finding.confidence
        confidence, confidence_label = clamp_confidence(confidence_raw, reviewed.confidence_label if reviewed else finding.confidence_label)
        score = compute_score(
            severity=severity,
            confidence=confidence,
            affected_route_ids=finding.affected_route_ids,
            affected_node_ids=finding.affected_node_ids,
            signals=repo_signals,
            external_provider=any(signal.type == "http_call" and signal.details.get("target") for signal in finding.signals),
            database_write=any(signal.type == "db_call" and signal.details.get("operation") in {"insert", "update", "delete"} for signal in finding.signals),
            config_only=all(signal.start_line is None for signal in finding.signals) if finding.signals else False,
        )
        final_findings.append(FinalFinding(
            id=finding.id,
            title=reviewed.recommended_title if reviewed else finding.title,
            risk_type=finding.risk_type,
            category=finding.category,
            affected_node_ids=finding.affected_node_ids,
            affected_edge_ids=finding.affected_edge_ids,
            affected_route_ids=finding.affected_route_ids,
            severity=severity,
            score=score,
            confidence=confidence,
            confidence_label=confidence_label,
            why=reviewed.why if reviewed else finding.why,
            impact=reviewed.impact if reviewed else finding.impact,
            evidence_ids=finding.evidence_ids,
            recommendations=reviewed.recommendations if reviewed and reviewed.recommendations else finding.recommendations,
            detected_by=["rule:" + finding.rule_id, *([f"llm_review:deepseek"] if reviewed else [])],
            telemetry_needed_to_confirm=reviewed.telemetry_needed_to_confirm if reviewed and reviewed.telemetry_needed_to_confirm else finding.telemetry_needed_to_confirm,
        ))

    final_findings = sort_findings(final_findings)
    hot_nodes = _build_hot_nodes(final_findings)
    hot_edges = _build_hot_edges(final_findings)
    report = BottleneckReportV2(
        analysis_id=graph_facts.analysis_id,
        source_graph_facts_hash=_hash_model(graph_facts.model_dump()),
        source_repo_signals_hash=_hash_model(repo_signals.model_dump()),
        disclaimer="Findings indicate structural performance risk based on code and configuration. They do not prove production latency or saturation without telemetry.",
        summary=BottleneckSummaryV2(
            overall_risk=overall_risk(final_findings),
            total_findings=len(final_findings),
            highest_risk_type=final_findings[0].risk_type if final_findings else None,
            highest_severity=final_findings[0].severity if final_findings else None,
            static_confidence=average_confidence(final_findings),
        ),
        hot_nodes=hot_nodes,
        hot_edges=hot_edges,
        findings=final_findings,
        issues=[
            LegacyIssue(
                title=finding.title,
                severity=finding.severity,
                summary=finding.why,
                affected=finding.affected_node_ids or finding.affected_edge_ids or finding.affected_route_ids,
                confidence=finding.confidence,
            )
            for finding in final_findings
        ],
    )
    analysis_result = BottleneckAnalysisResult(
        repo_signals=repo_signals,
        rule_findings=rule_findings,
        report=report,
    )
    return analysis_result, _to_legacy_diagram_report(report)


def build_component_annotations(report: BottleneckReportV2) -> list[dict]:
    annotations: list[dict] = []
    for item in report.hot_nodes:
        annotations.append({
            "nodeId": item.node_id,
            "severity": item.severity,
            "findingIds": item.finding_ids,
            "riskType": item.risk_type,
            "confidence": item.confidence,
            "text": item.why,
        })
    for item in report.hot_edges:
        annotations.append({
            "edgeId": item.edge_id,
            "severity": item.severity,
            "findingIds": item.finding_ids,
            "riskType": item.risk_type,
            "confidence": item.confidence,
            "text": item.why,
        })
    return annotations


def _build_hot_nodes(findings: list[FinalFinding]) -> list[HotNode]:
    grouped: dict[str, list[FinalFinding]] = defaultdict(list)
    for finding in findings:
        for node_id in finding.affected_node_ids:
            grouped[node_id].append(finding)
    hot_nodes: list[HotNode] = []
    for node_id, items in grouped.items():
        top = max(items, key=lambda item: item.score)
        hot_nodes.append(HotNode(
            node_id=node_id,
            risk_type=top.risk_type,
            severity=top.severity,
            score=round(max(item.score for item in items), 3),
            confidence=round(max(item.confidence for item in items), 2),
            finding_ids=[item.id for item in items],
            why=top.why,
        ))
    return sorted(hot_nodes, key=lambda item: (-item.score, item.node_id))


def _build_hot_edges(findings: list[FinalFinding]) -> list[HotEdge]:
    grouped: dict[str, list[FinalFinding]] = defaultdict(list)
    for finding in findings:
        for edge_id in finding.affected_edge_ids:
            grouped[edge_id].append(finding)
    hot_edges: list[HotEdge] = []
    for edge_id, items in grouped.items():
        top = max(items, key=lambda item: item.score)
        hot_edges.append(HotEdge(
            edge_id=edge_id,
            risk_type=top.risk_type,
            severity=top.severity,
            score=round(max(item.score for item in items), 3),
            confidence=round(max(item.confidence for item in items), 2),
            finding_ids=[item.id for item in items],
            why=top.why,
        ))
    return sorted(hot_edges, key=lambda item: (-item.score, item.edge_id))


def _to_legacy_diagram_report(report: BottleneckReportV2) -> LegacyDiagramReport:
    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    issues: list[LegacyDiagramIssue] = []
    for finding in report.findings:
        by_severity[finding.severity] += 1
        issues.append(LegacyDiagramIssue(
            type=finding.risk_type,
            severity="high" if finding.severity == "critical" else finding.severity,  # type: ignore[arg-type]
            affected=finding.affected_node_ids or finding.affected_edge_ids or finding.affected_route_ids,
            explanation=finding.why,
            fix=finding.recommendations[0] if finding.recommendations else "Inspect the highlighted code path first.",
            confidence=finding.confidence,
            source="rules+llm" if any("llm_review" in source for source in finding.detected_by) else "rules",
        ))
    risk_score = round(min(100.0, sum(finding.score for finding in report.findings) * 100 / max(len(report.findings), 1)), 1) if report.findings else 0.0
    return LegacyDiagramReport(
        risk_score=risk_score,
        total_issues=len(issues),
        by_severity=by_severity,
        issues=issues,
    )


def _hash_model(payload: dict) -> str:
    return "sha256-" + hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()
