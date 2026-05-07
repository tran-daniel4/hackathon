import re
from typing import Optional, Literal
from pydantic import BaseModel


def make_node_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


NodeType = Literal[
    "client", "gateway", "service", "worker",
    "database", "cache", "queue", "topic",
    "object_storage", "external_service", "auth_provider", "unknown",
]

EdgeKind = Literal[
    "http", "grpc", "pubsub", "queue",
    "read", "write", "cache_read", "cache_write",
    "object_read", "object_write", "webhook", "sdk", "unknown",
]

Confidence = Literal["verified", "inferred"]

EvidenceKind = Literal["file", "code_reference", "manifest", "env_var"]


class Evidence(BaseModel):
    id: str
    kind: EvidenceKind
    file_path: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    symbol: Optional[str] = None
    excerpt: str


class NodeFact(BaseModel):
    id: str
    type: NodeType
    name: str
    runtime: Optional[str] = None
    language: Optional[str] = None
    framework: Optional[str] = None
    tags: list[str] = []
    confidence: Confidence = "inferred"
    evidence_ids: list[str] = []


class EdgeFact(BaseModel):
    id: str
    src: str
    dst: str
    kind: EdgeKind
    label: Optional[str] = None
    protocol: Optional[str] = None
    operation: Optional[str] = None
    direction: Literal["outbound", "request_response", "inbound"] = "outbound"
    confidence: Confidence = "inferred"
    evidence_ids: list[str] = []


class ApiFact(BaseModel):
    id: str
    component_id: str
    method: str
    path: str
    handler: Optional[str] = None
    auth_required: bool = False
    evidence_ids: list[str] = []


class MessagingFact(BaseModel):
    id: str
    type: Literal["topic", "queue", "exchange"]
    name: str
    producer_component_ids: list[str] = []
    consumer_component_ids: list[str] = []
    evidence_ids: list[str] = []


class DataResourceFact(BaseModel):
    id: str
    type: Literal["table", "collection", "bucket", "stream"]
    name: str
    owner_component_id: Optional[str] = None
    datastore_node_id: str
    evidence_ids: list[str] = []


class WarningFact(BaseModel):
    code: str
    message: str
    file_path: Optional[str] = None


class GraphFactPatch(BaseModel):
    nodes: list[NodeFact] = []
    edges: list[EdgeFact] = []
    apis: list[ApiFact] = []
    data_resources: list[DataResourceFact] = []
    messaging: list[MessagingFact] = []
    evidence: list[Evidence] = []
    warnings: list[WarningFact] = []


class RepoMeta(BaseModel):
    name: str = "unknown"
    url: Optional[str] = None
    branch: Optional[str] = None
    commit_sha: Optional[str] = None
    analyzed_at: str = ""


class GraphFacts(BaseModel):
    schema_version: str = "1.0"
    analysis_id: str
    repo: RepoMeta = RepoMeta()
    nodes: list[NodeFact] = []
    edges: list[EdgeFact] = []
    apis: list[ApiFact] = []
    data_resources: list[DataResourceFact] = []
    messaging: list[MessagingFact] = []
    evidence: list[Evidence] = []
    warnings: list[WarningFact] = []
