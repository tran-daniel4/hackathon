"""
Diagram Generator — pure Python, no LLM.
Produces 4 architecture views from ArchGraph + BottleneckReport.

Output format matches what DiagramView.tsx / ArchDiagram.tsx expect:
  groups: { id, label, type }          — logical columns (new)
  nodes:  { id, label, type, layer, group, severity? }
  edges:  { id, source, target, label? }

Nodes are assigned to a `group` for column-based layout in the frontend.
`layer` is kept for backward-compat row ordering within a column.
"""
from typing import Literal

from pydantic import BaseModel

from pipeline.scanner import RepoScan
from pipeline.graph_builder import ArchGraph
from pipeline.aggregator import BottleneckReport


# ── Output schema ──────────────────────────────────────────────────────────────

class DiagramGroup(BaseModel):
    id: str
    label: str
    type: str = "layer"


class DiagramNode(BaseModel):
    id: str
    label: str
    type: str                    # frontend color key (matches TYPE_COLOR in DiagramView.tsx)
    layer: str                   # kept for backward-compat row ordering
    group: str | None = None     # logical column id (maps to DiagramGroup.id)
    severity: str | None = None  # "high" | "medium" | "low" — warning border
    description: str = ""        # LLM-generated 1-sentence summary of what this component does


class DiagramEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str = ""
    confidence: Literal["verified", "inferred"] | None = None


class DiagramView(BaseModel):
    id: str     # "conceptual" | "system_context" | "component" | "operational"
    label: str
    nodes: list[DiagramNode]
    edges: list[DiagramEdge]
    groups: list[DiagramGroup] = []
    annotations: list[dict] = []


class DiagramOutput(BaseModel):
    views: list[DiagramView]


# ── Type + layer/group mappings ────────────────────────────────────────────────

# ArchGraph type → frontend color key
_TO_UI_TYPE: dict[str, str] = {
    "frontend":    "frontend",
    "service":     "backend",
    "database":    "database",
    "cache":       "cache",
    "queue":       "queue",
    "external_api": "external",
}

# Frontend type → visual layer (kept for non-grouped views)
_TYPE_LAYER: dict[str, str] = {
    "frontend":  "presentation",
    "backend":   "application",
    "database":  "data",
    "cache":     "data",
    "queue":     "data",
    "external":  "external",
    "worker":    "infra",
}

# Frontend type → logical group column
_TYPE_GROUP: dict[str, str] = {
    "frontend":  "frontend",
    "backend":   "core",
    "database":  "data",
    "cache":     "supporting",
    "queue":     "supporting",
    "external":  "external",
    "worker":    "supporting",
}

# Canonical group definitions — order determines left→right column order
_STANDARD_GROUPS: list[DiagramGroup] = [
    DiagramGroup(id="frontend",   label="Frontend Services"),
    DiagramGroup(id="gateway",    label="API Gateway"),
    DiagramGroup(id="core",       label="Core Business Services"),
    DiagramGroup(id="supporting", label="Supporting Services"),
    DiagramGroup(id="external",   label="External Integrations"),
    DiagramGroup(id="data",       label="Data Stores"),
]

# Defines sort order for layer names → visual row order within a column
_LAYER_ORDER = ["presentation", "application", "data", "external", "infra"]

_SEVERITY_RANK: dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3}


# ── Public API ─────────────────────────────────────────────────────────────────

def generate_diagrams(
    scan: RepoScan,
    graph: ArchGraph,
    report: BottleneckReport,
) -> DiagramOutput:
    """
    Build all 4 architecture views.
    The operational view is omitted when no infra files are detected.
    """
    sev_index = _build_severity_index(report)

    views: list[DiagramView] = [
        _conceptual_view(graph, sev_index),
        _system_context_view(graph, scan, sev_index),
        _component_view(graph, sev_index),
    ]

    op = _operational_view(graph, scan, sev_index)
    if op:
        views.append(op)

    return DiagramOutput(views=views)


# ── View builders ──────────────────────────────────────────────────────────────

def _conceptual_view(graph: ArchGraph, sev_index: dict[str, str]) -> DiagramView:
    """
    High-level business view — one node per architectural concern.
    Shows: Presentation / Application / Data Layer / External Services.
    """
    frontend_ids  = [n.id for n in graph.nodes if n.type == "frontend"]
    service_ids   = [n.id for n in graph.nodes if n.type == "service"]
    data_ids      = [n.id for n in graph.nodes if n.type in ("database", "cache", "queue")]
    external_ids  = [n.id for n in graph.nodes if n.type == "external_api"]

    nodes: list[DiagramNode] = []
    edges: list[DiagramEdge] = []

    if frontend_ids:
        nodes.append(DiagramNode(
            id="concept-presentation", label="Presentation",
            type="frontend", layer="presentation",
        ))
    if service_ids:
        nodes.append(DiagramNode(
            id="concept-application", label="Application",
            type="backend", layer="application",
            severity=_worst_severity(sev_index, service_ids),
        ))
    if data_ids:
        nodes.append(DiagramNode(
            id="concept-data", label="Data Layer",
            type="database", layer="data",
            severity=_worst_severity(sev_index, data_ids),
        ))
    if external_ids:
        nodes.append(DiagramNode(
            id="concept-external", label="External Services",
            type="external", layer="external",
        ))

    # Edges between buckets (only if both exist)
    def _node_ids() -> set[str]:
        return {n.id for n in nodes}

    nids = _node_ids()
    pairs = [
        ("concept-presentation", "concept-application", "HTTP"),
        ("concept-application",  "concept-data",        "reads/writes"),
        ("concept-application",  "concept-external",    "calls"),
        ("concept-data",         "concept-external",    ""),
    ]
    for src, tgt, lbl in pairs:
        if src in nids and tgt in nids:
            edges.append(DiagramEdge(id=f"{src}--{tgt}", source=src, target=tgt, label=lbl))

    return DiagramView(id="conceptual", label="Conceptual", nodes=nodes, edges=edges)


def _system_context_view(
    graph: ArchGraph,
    scan: RepoScan,
    sev_index: dict[str, str],
) -> DiagramView:
    """
    C4-style system context: User → Your System → External Systems.
    The whole application is represented as a single node.
    """
    system_name = (scan.services[0] if scan.services else "System").replace("-", " ").title()
    all_ids = [n.id for n in graph.nodes]

    nodes: list[DiagramNode] = [
        DiagramNode(id="ctx-user",   label="User / Browser", type="frontend", layer="presentation"),
        DiagramNode(
            id="ctx-system", label=system_name,
            type="backend", layer="application",
            severity=_worst_severity(sev_index, all_ids),
        ),
    ]
    edges: list[DiagramEdge] = [
        DiagramEdge(id="ctx-user--system", source="ctx-user", target="ctx-system", label="HTTPS"),
    ]

    for n in graph.nodes:
        if n.type == "external_api":
            nodes.append(DiagramNode(
                id=f"ctx-{n.id}", label=n.label, type="external", layer="external",
            ))
            edges.append(DiagramEdge(
                id=f"ctx-system--{n.id}", source="ctx-system", target=f"ctx-{n.id}", label="API call",
            ))

    return DiagramView(id="system_context", label="System Context", nodes=nodes, edges=edges)


def _component_view(graph: ArchGraph, sev_index: dict[str, str]) -> DiagramView:
    """
    Detailed component view — strictly what was detected in the repo.
    No synthetic nodes are added; only groups that contain real nodes appear.
    """
    nodes = _graph_nodes_to_diagram(graph, sev_index)
    edges = list(_graph_edges_to_diagram(graph))
    annotations = _build_annotations(graph, sev_index)

    used_groups = {n.group for n in nodes if n.group}
    groups = [g for g in _STANDARD_GROUPS if g.id in used_groups]

    return DiagramView(
        id="component", label="Component",
        groups=groups, nodes=nodes, edges=edges, annotations=annotations,
    )


def _operational_view(
    graph: ArchGraph,
    scan: RepoScan,
    sev_index: dict[str, str],
) -> DiagramView | None:
    """
    Infrastructure / deployment view.
    Only generated when Docker or Terraform files are detected.
    """
    tree = {f.replace("\\", "/").rsplit("/", 1)[-1] for f in scan.file_tree}
    has_docker    = "Dockerfile" in tree or "docker-compose.yml" in tree
    has_terraform = any(f.endswith(".tf") for f in scan.file_tree)
    has_k8s       = any("k8s" in f or "kubernetes" in f for f in scan.file_tree)

    if not has_docker and not has_terraform and not has_k8s:
        return None

    nodes = _graph_nodes_to_diagram(graph, sev_index, label_prefix="[container] " if has_docker else "")
    edges = _graph_edges_to_diagram(graph)

    # Prepend an infra context node
    infra_label = (
        "Kubernetes" if has_k8s
        else "Terraform (Cloud)" if has_terraform
        else "Docker Compose"
    )
    nodes.insert(0, DiagramNode(
        id="infra-runtime", label=infra_label, type="worker", layer="infra",
    ))

    return DiagramView(id="operational", label="Operational", nodes=nodes, edges=edges)


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _graph_nodes_to_diagram(
    graph: ArchGraph,
    sev_index: dict[str, str],
    label_prefix: str = "",
) -> list[DiagramNode]:
    nodes: list[DiagramNode] = []
    for n in graph.nodes:
        ui_type = _TO_UI_TYPE.get(n.type, "backend")
        layer   = _TYPE_LAYER.get(ui_type, "application")
        group   = _TYPE_GROUP.get(ui_type, "core")
        nodes.append(DiagramNode(
            id=n.id,
            label=f"{label_prefix}{n.label}",
            type=ui_type,
            layer=layer,
            group=group,
            severity=sev_index.get(n.id),
        ))

    nodes.sort(key=lambda n: (
        _LAYER_ORDER.index(n.layer) if n.layer in _LAYER_ORDER else 99
    ))
    return nodes


def _graph_edges_to_diagram(graph: ArchGraph) -> list[DiagramEdge]:
    seen: set[str] = set()
    edges: list[DiagramEdge] = []
    for e in graph.edges:
        eid = f"{e.source}--{e.target}"
        if eid in seen:
            continue
        seen.add(eid)
        edges.append(DiagramEdge(id=eid, source=e.source, target=e.target, label=e.type,
                                 confidence=e.confidence))
    return edges


def _build_annotations(graph: ArchGraph, sev_index: dict[str, str]) -> list[dict]:
    return [
        {"nodeId": node_id, "severity": sev, "text": f"{sev.upper()} bottleneck"}
        for node_id, sev in sev_index.items()
        if any(n.id == node_id for n in graph.nodes)
    ]


def _build_severity_index(report: BottleneckReport) -> dict[str, str]:
    """Map each affected node ID to the worst severity across all issues."""
    index: dict[str, str] = {}
    for issue in report.issues:
        for node_id in issue.affected:
            current = index.get(node_id)
            if current is None or _SEVERITY_RANK[issue.severity] < _SEVERITY_RANK[current]:
                index[node_id] = issue.severity
    return index


def _worst_severity(sev_index: dict[str, str], node_ids: list[str]) -> str | None:
    sevs = [sev_index[nid] for nid in node_ids if nid in sev_index]
    if not sevs:
        return None
    return min(sevs, key=lambda s: _SEVERITY_RANK.get(s, 99))
