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
from pipeline.conceptual import build_conceptual_spec
from pipeline.operational import build_operational_spec
from pipeline.system_context import build_system_context_spec


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
        _conceptual_view(graph, scan, sev_index),
        _system_context_view(graph, scan, sev_index),
        _component_view(graph, sev_index),
    ]

    op = _operational_view(graph, scan, sev_index)
    if op:
        views.append(op)

    return DiagramOutput(views=views)


# ── View builders ──────────────────────────────────────────────────────────────

def _conceptual_view(
    graph: ArchGraph,
    scan: RepoScan,
    sev_index: dict[str, str],
) -> DiagramView:
    """
    High-level business view centered on actors, the system boundary, and
    major business capabilities derived from API and integration evidence.
    """
    spec = build_conceptual_spec(scan, graph)
    nodes: list[DiagramNode] = []
    groups = [
        DiagramGroup(id="users", label="Users & Actors"),
        DiagramGroup(id="system", label="System Boundary"),
        DiagramGroup(id="capabilities", label="Business Capabilities"),
        DiagramGroup(id="external_partners", label="External Partners"),
        DiagramGroup(id="gaps", label="Detected Gaps"),
    ]

    for actor in spec["actors"]:
        nodes.append(DiagramNode(
            id=actor["id"],
            label=actor["label"],
            type="frontend",
            layer="presentation",
            group="users",
            description=actor["description"],
        ))

    system = spec["system"]
    nodes.append(DiagramNode(
            id=system["id"],
            label=system["label"],
            type="backend", layer="application",
            group="system",
            severity=_worst_severity(sev_index, system["all_ids"]),
            description=system["description"],
    ))

    for capability in spec["capabilities"]:
        nodes.append(DiagramNode(
            id=capability["id"],
            label=capability["label"],
            type="backend",
            layer="application",
            group="capabilities",
            description=capability["description"],
        ))

    for partner in spec["external_partners"]:
        nodes.append(DiagramNode(
            id=partner["id"],
            label=partner["label"],
            type="external",
            layer="external",
            group="external_partners",
            description=partner["description"],
        ))

    for gap in spec["gaps"]:
        nodes.append(DiagramNode(
            id=gap["id"],
            label=gap["label"],
            type="external",
            layer="external",
            group="gaps",
            description=gap["description"],
        ))

    edges = [
        DiagramEdge(
            id=f"{edge['source']}--{edge['target']}--{idx}",
            source=edge["source"],
            target=edge["target"],
            label=edge["label"],
            confidence=edge["confidence"],
        )
        for idx, edge in enumerate(spec["edges"], start=1)
    ]

    used_groups = {node.group for node in nodes if node.group}
    return DiagramView(
        id="conceptual",
        label="Conceptual",
        groups=[group for group in groups if group.id in used_groups],
        nodes=nodes,
        edges=edges,
    )


def _system_context_view(
    graph: ArchGraph,
    scan: RepoScan,
    sev_index: dict[str, str],
) -> DiagramView:
    """
    C4-style system context: User → Your System → External Systems.
    The whole application is represented as a single node.
    """
    spec = build_system_context_spec(scan, graph)
    all_ids = spec["system"]["all_ids"]

    nodes: list[DiagramNode] = []
    groups = [
        DiagramGroup(id="actors", label="Users & Actors"),
        DiagramGroup(id="system", label="Your System"),
        DiagramGroup(id="partners", label="External Partners"),
        DiagramGroup(id="identity", label="Identity Providers"),
    ]

    for actor in spec["actors"]:
        nodes.append(DiagramNode(
            id=actor["id"],
            label=actor["label"],
            type="frontend",
            layer="presentation",
            group="actors",
            description=actor["description"],
        ))

    nodes.append(DiagramNode(
        id="ctx-system",
        label=spec["system"]["label"],
        type="backend",
        layer="application",
        group="system",
        severity=_worst_severity(sev_index, all_ids),
        description=spec["system"]["description"],
    ))

    for identity in spec["identity"]:
        nodes.append(DiagramNode(
            id=identity["id"],
            label=identity["label"],
            type="external",
            layer="external",
            group="identity",
            description=identity["description"],
        ))

    for partner in spec["partners"]:
        nodes.append(DiagramNode(
            id=partner["id"],
            label=partner["label"],
            type="external",
            layer="external",
            group="partners",
            description=partner["description"],
        ))

    edges = [
        DiagramEdge(
            id=f"{edge['source']}--{edge['target']}--{idx}",
            source=edge["source"],
            target=edge["target"],
            label=edge["label"],
            confidence=edge["confidence"],
        )
        for idx, edge in enumerate(spec["edges"], start=1)
    ]

    used_groups = {node.group for node in nodes if node.group}
    return DiagramView(
        id="system_context",
        label="System Context",
        groups=[group for group in groups if group.id in used_groups],
        nodes=nodes,
        edges=edges,
    )


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
    has_aspire    = ".NET Aspire" in scan.frameworks

    if not has_docker and not has_terraform and not has_k8s and not has_aspire:
        return None

    spec = build_operational_spec(scan, graph)
    nodes: list[DiagramNode] = []
    groups = [
        DiagramGroup(id="cicd", label="CI/CD Pipeline"),
        DiagramGroup(id="runtime", label="Runtime"),
        DiagramGroup(id="ingress", label="Ingress"),
        DiagramGroup(id="services", label="Services"),
        DiagramGroup(id="data", label="Data Plane"),
        DiagramGroup(id="observability", label="Observability"),
        DiagramGroup(id="identity", label="Identity"),
    ]

    for node in [
        *spec["cicd"],
        *spec["runtime"],
        *spec["ingress"],
        *spec["services"],
        *spec["data"],
        *spec["observability"],
        *spec["identity"],
    ]:
        nodes.append(DiagramNode(
            id=node["id"],
            label=node["label"],
            type=node["type"],
            layer=_TYPE_LAYER.get(node["type"], "application"),
            group=node["group"],
            severity=sev_index.get(node["id"]),
            description=node["description"],
        ))

    edges = [
        DiagramEdge(
            id=f"{edge['source']}--{edge['target']}--{idx}",
            source=edge["source"],
            target=edge["target"],
            label=edge["label"],
            confidence=edge["confidence"],
        )
        for idx, edge in enumerate(spec["edges"], start=1)
    ]

    used_groups = {n.group for n in nodes if n.group}

    return DiagramView(
        id="operational",
        label="Operational",
        groups=[g for g in groups if g.id in used_groups],
        nodes=nodes,
        edges=edges,
    )


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _graph_nodes_to_diagram(
    graph: ArchGraph,
    sev_index: dict[str, str],
    label_prefix: str = "",
) -> list[DiagramNode]:
    node_by_id = {node.id: node for node in graph.nodes}
    incoming_by_target: dict[str, list] = {}
    outgoing_by_source: dict[str, list] = {}

    for edge in graph.edges:
        incoming_by_target.setdefault(edge.target, []).append(edge)
        outgoing_by_source.setdefault(edge.source, []).append(edge)

    nodes: list[DiagramNode] = []
    for n in graph.nodes:
        ui_type = _TO_UI_TYPE.get(n.type, "backend")
        layer   = _TYPE_LAYER.get(ui_type, "application")
        group   = _component_group_for_node(
            node=n,
            ui_type=ui_type,
            node_by_id=node_by_id,
            incoming_by_target=incoming_by_target,
            outgoing_by_source=outgoing_by_source,
        )
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
        edges.append(DiagramEdge(id=eid, source=e.source, target=e.target, label=_edge_label(e),
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


def _edge_label(edge) -> str:
    explicit = (edge.label or "").strip()
    if explicit:
        return explicit

    return {
        "http": "HTTP request",
        "reads/writes": "SQL query",
        "caches": "Cache lookup",
        "calls": "External call",
        "publishes": "Async event",
        "consumes": "Queue consume",
    }.get(edge.type, edge.type.replace("/", " "))


def _component_group_for_node(
    *,
    node,
    ui_type: str,
    node_by_id: dict[str, object],
    incoming_by_target: dict[str, list],
    outgoing_by_source: dict[str, list],
) -> str:
    if ui_type != "backend":
        return _TYPE_GROUP.get(ui_type, "core")

    incoming = incoming_by_target.get(node.id, [])
    outgoing = outgoing_by_source.get(node.id, [])

    if any(
        getattr(edge, "type", "") == "http"
        and getattr(node_by_id.get(edge.source), "type", "") == "frontend"
        for edge in incoming
    ):
        return "gateway"

    if any(
        getattr(node_by_id.get(edge.target), "type", "") in {"external_api", "queue"}
        for edge in outgoing
    ):
        return "supporting"

    return "core"
