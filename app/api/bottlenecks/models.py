from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Severity = Literal["low", "medium", "high", "critical"]
ConfidenceLabel = Literal[
    "weak_static_signal",
    "medium_static_signal",
    "strong_static_signal",
    "very_strong_static_signal",
]
SignalKind = Literal[
    "route",
    "http_call",
    "db_call",
    "loop",
    "cache_call",
    "queue_config",
    "file_io",
    "logging",
    "dependency",
    "cpu_call",
]


class RouteSignal(BaseModel):
    id: str
    component_id: str
    method: str
    path: str
    handler_symbol: str | None = None
    file_path: str
    start_line: int | None = None
    end_line: int | None = None
    evidence_id: str
    auth_required: bool = False
    request_path: bool = True
    public_endpoint: bool = True
    background_only: bool = False
    test_only: bool = False
    pagination_params: list[str] = []


class HttpCallSignal(BaseModel):
    id: str
    component_id: str
    enclosing_route_id: str | None = None
    target_hint: str
    client: str
    method: str | None = None
    timeout_detected: bool = False
    retry_detected: bool = False
    circuit_breaker_detected: bool = False
    file_path: str
    start_line: int
    end_line: int
    evidence_id: str
    external_provider: bool = False


class DbCallSignal(BaseModel):
    id: str
    component_id: str
    enclosing_route_id: str | None = None
    operation: str
    table_or_model: str | None = None
    has_limit: bool = False
    inside_loop_id: str | None = None
    file_path: str
    start_line: int
    end_line: int
    evidence_id: str
    is_write: bool = False


class LoopSignal(BaseModel):
    id: str
    component_id: str
    enclosing_route_id: str | None = None
    file_path: str
    start_line: int
    end_line: int
    evidence_id: str


class CacheCallSignal(BaseModel):
    id: str
    component_id: str
    enclosing_route_id: str | None = None
    operation: Literal["get", "set", "delete", "other"]
    cache: str
    key_hint: str | None = None
    file_path: str
    start_line: int
    end_line: int
    evidence_id: str
    coordination_detected: bool = False


class QueueConfigSignal(BaseModel):
    id: str
    component_id: str
    queue_name: str
    dlq_detected: bool = False
    retry_detected: bool = False
    max_retries: int | None = None
    backoff_detected: bool = False
    concurrency_limit: int | None = None
    prefetch_limit: int | None = None
    file_path: str
    start_line: int | None = None
    end_line: int | None = None
    evidence_id: str


class FileIoSignal(BaseModel):
    id: str
    component_id: str
    enclosing_route_id: str | None = None
    operation: str
    sync: bool
    file_path: str
    start_line: int
    end_line: int
    evidence_id: str


class LoggingSignal(BaseModel):
    id: str
    component_id: str
    enclosing_route_id: str | None = None
    level: str
    file_path: str
    start_line: int
    end_line: int
    evidence_id: str
    inside_loop_id: str | None = None
    logs_payload: bool = False
    debug_logging: bool = False


class DependencySignal(BaseModel):
    id: str
    component_id: str | None = None
    name: str
    category: str
    file_path: str
    start_line: int
    end_line: int
    evidence_id: str


class CpuCallSignal(BaseModel):
    id: str
    component_id: str
    enclosing_route_id: str | None = None
    operation: str
    file_path: str
    start_line: int
    end_line: int
    evidence_id: str


class RepoSignals(BaseModel):
    schema_version: str = "1.0"
    analysis_id: str
    routes: list[RouteSignal] = Field(default_factory=list)
    http_calls: list[HttpCallSignal] = Field(default_factory=list)
    db_calls: list[DbCallSignal] = Field(default_factory=list)
    loops: list[LoopSignal] = Field(default_factory=list)
    cache_calls: list[CacheCallSignal] = Field(default_factory=list)
    queue_configs: list[QueueConfigSignal] = Field(default_factory=list)
    file_io_calls: list[FileIoSignal] = Field(default_factory=list)
    logging_calls: list[LoggingSignal] = Field(default_factory=list)
    dependency_signals: list[DependencySignal] = Field(default_factory=list)
    cpu_calls: list[CpuCallSignal] = Field(default_factory=list)


class FindingSignal(BaseModel):
    type: SignalKind
    file_path: str
    start_line: int | None = None
    end_line: int | None = None
    details: dict = Field(default_factory=dict)


class RuleFinding(BaseModel):
    id: str
    rule_id: str
    risk_type: str
    category: str
    title: str
    affected_node_ids: list[str] = Field(default_factory=list)
    affected_edge_ids: list[str] = Field(default_factory=list)
    affected_route_ids: list[str] = Field(default_factory=list)
    severity_hint: Severity
    confidence: float
    confidence_label: ConfidenceLabel
    evidence_ids: list[str] = Field(default_factory=list)
    signals: list[FindingSignal] = Field(default_factory=list)
    why: str
    impact: str = ""
    recommendations: list[str] = Field(default_factory=list)
    telemetry_needed_to_confirm: list[str] = Field(default_factory=list)


class ReviewedFinding(BaseModel):
    finding_id: str
    risk_type: str
    recommended_title: str
    recommended_severity: Severity
    recommended_confidence: float
    confidence_label: ConfidenceLabel
    why: str
    impact: str
    recommendations: list[str] = Field(default_factory=list)
    telemetry_needed_to_confirm: list[str] = Field(default_factory=list)


class GroupedFinding(BaseModel):
    group_id: str
    title: str
    finding_ids: list[str]
    risk_type: str
    affected_node_ids: list[str] = Field(default_factory=list)
    affected_edge_ids: list[str] = Field(default_factory=list)
    affected_route_ids: list[str] = Field(default_factory=list)
    why: str
    recommended_severity: Severity
    recommended_confidence: float


class RejectedReviewItem(BaseModel):
    finding_id: str
    reason: str
    recommended_action: Literal["reject", "downgrade", "keep"]


class DeepSeekReview(BaseModel):
    schema_version: str = "1.0"
    reviewed_findings: list[ReviewedFinding] = Field(default_factory=list)
    grouped_findings: list[GroupedFinding] = Field(default_factory=list)
    rejected_or_downgraded: list[RejectedReviewItem] = Field(default_factory=list)


class FinalFinding(BaseModel):
    id: str
    title: str
    risk_type: str
    category: str
    affected_node_ids: list[str] = Field(default_factory=list)
    affected_edge_ids: list[str] = Field(default_factory=list)
    affected_route_ids: list[str] = Field(default_factory=list)
    severity: Severity
    score: float
    confidence: float
    confidence_label: ConfidenceLabel
    why: str
    impact: str
    evidence_ids: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    detected_by: list[str] = Field(default_factory=list)
    telemetry_needed_to_confirm: list[str] = Field(default_factory=list)


class HotNode(BaseModel):
    node_id: str
    risk_type: str
    severity: Severity
    score: float
    confidence: float
    finding_ids: list[str]
    why: str


class HotEdge(BaseModel):
    edge_id: str
    risk_type: str
    severity: Severity
    score: float
    confidence: float
    finding_ids: list[str]
    why: str


class BottleneckSummaryV2(BaseModel):
    overall_risk: Severity
    total_findings: int
    highest_risk_type: str | None = None
    highest_severity: Severity | None = None
    static_confidence: float = 0.0


class LegacyIssue(BaseModel):
    title: str
    severity: Severity
    summary: str
    affected: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class BottleneckReportV2(BaseModel):
    schema_version: str = "1.0"
    analysis_id: str
    source_graph_facts_hash: str
    source_repo_signals_hash: str
    mode: Literal["static_analysis_only"] = "static_analysis_only"
    disclaimer: str
    summary: BottleneckSummaryV2
    hot_nodes: list[HotNode] = Field(default_factory=list)
    hot_edges: list[HotEdge] = Field(default_factory=list)
    findings: list[FinalFinding] = Field(default_factory=list)
    issues: list[LegacyIssue] = Field(default_factory=list)
