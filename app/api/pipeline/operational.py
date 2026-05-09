from __future__ import annotations

from collections import OrderedDict

from pipeline.graph_builder import ArchGraph
from pipeline.scanner import RepoScan
from pipeline.system_context import build_system_context_spec

_CICD_LABELS = {
    "github_actions": "GitHub Actions",
    "gitlab_ci": "GitLab CI",
    "jenkins": "Jenkins",
    "circleci": "CircleCI",
    "travis": "Travis CI",
    "azure_devops": "Azure DevOps",
}

_OBSERVABILITY_LABELS = {
    "opentelemetry": ("OpenTelemetry Collector", "Collects traces, metrics, and logs from running workloads."),
    "opentelemetry-dotnet": ("OpenTelemetry Collector", "Collects traces, metrics, and logs from .NET workloads."),
    "prometheus-client": ("Prometheus Metrics", "Captures application metrics for scraping and alerting."),
    "datadog": ("Datadog", "Receives application telemetry and operational health signals."),
    "sentry": ("Sentry", "Captures exceptions and application health events."),
    "jaeger": ("Jaeger", "Stores and visualizes distributed tracing spans."),
    "newrelic": ("New Relic", "Provides application performance monitoring and observability."),
    "serilog": ("Centralized Logging", "Aggregates structured logs from running services."),
    "structlog": ("Centralized Logging", "Aggregates structured logs from running services."),
    "loguru": ("Centralized Logging", "Aggregates structured logs from running services."),
}

_CLOUD_HINTS = OrderedDict([
    ("aws", "AWS Cloud"),
    ("amazon", "AWS Cloud"),
    ("azurerm", "Azure Cloud"),
    ("azure", "Azure Cloud"),
    ("google", "Google Cloud"),
    ("gcp", "Google Cloud"),
    ("digitalocean", "DigitalOcean"),
    ("do_token", "DigitalOcean"),
    ("cloudflare", "Cloudflare Edge"),
])


def build_operational_spec(scan: RepoScan, graph: ArchGraph) -> dict:
    runtime = _build_runtime_nodes(scan, graph)
    ingress = _build_ingress_nodes(scan, graph, runtime)
    cicd = _build_cicd_nodes(scan)
    services = _build_service_nodes(graph)
    data_plane = _build_data_nodes(graph)
    observability = _build_observability_nodes(scan)
    identity = [
        {**node, "group": "identity", "type": "external"}
        for node in build_system_context_spec(scan, graph)["identity"]
    ]

    edges: list[dict] = []
    runtime_chain = [node["id"] for node in runtime]
    for idx in range(len(runtime_chain) - 1):
        edges.append({
            "source": runtime_chain[idx],
            "target": runtime_chain[idx + 1],
            "label": "Provisioned into",
            "confidence": "inferred",
        })

    cicd_ids = [node["id"] for node in cicd]
    for idx in range(len(cicd_ids) - 1):
        label = "Promotes artifact" if idx == len(cicd_ids) - 2 else "Pipeline stage"
        edges.append({
            "source": cicd_ids[idx],
            "target": cicd_ids[idx + 1],
            "label": label,
            "confidence": "verified",
        })
    if cicd_ids and runtime_chain:
        edges.append({
            "source": cicd_ids[-1],
            "target": runtime_chain[0],
            "label": "Deploys infrastructure",
            "confidence": "verified",
        })

    ingress_ids = [node["id"] for node in ingress]
    if runtime_chain and ingress_ids:
        edges.append({
            "source": runtime_chain[-1],
            "target": ingress_ids[0],
            "label": "Exposes traffic through",
            "confidence": "inferred",
        })

    frontend_ids = [node["id"] for node in services if node["type"] == "frontend"]
    backend_ids = [node["id"] for node in services if node["type"] == "backend"]

    if ingress_ids:
        targets = frontend_ids or backend_ids[:3]
        for target in targets:
            edges.append({
                "source": ingress_ids[0],
                "target": target,
                "label": "Routes user traffic",
                "confidence": "inferred",
            })

    host_targets = backend_ids if backend_ids else [node["id"] for node in services]
    if runtime_chain:
        for target in host_targets[:6]:
            edges.append({
                "source": runtime_chain[-1],
                "target": target,
                "label": "Runs workload",
                "confidence": "inferred",
            })

    data_ids = {node["id"] for node in data_plane}
    for edge in graph.edges:
        if edge.target not in data_ids:
            continue
        edges.append({
            "source": edge.source,
            "target": edge.target,
            "label": _operational_label(edge.type),
            "confidence": edge.confidence,
        })

    for service_id in backend_ids[:6]:
        for obs in observability[:3]:
            edges.append({
                "source": service_id,
                "target": obs["id"],
                "label": "Emits telemetry",
                "confidence": "inferred",
            })

    if identity:
        auth_target = (frontend_ids + backend_ids[:2])[:2]
        for target in auth_target:
            edges.append({
                "source": target,
                "target": identity[0]["id"],
                "label": "Authenticates users",
                "confidence": "inferred",
            })

    return {
        "runtime": runtime,
        "ingress": ingress,
        "cicd": cicd,
        "services": services,
        "data": data_plane,
        "observability": observability,
        "identity": identity,
        "edges": _dedupe_edges(edges),
    }


def _build_runtime_nodes(scan: RepoScan, graph: ArchGraph) -> list[dict]:
    nodes: list[dict] = []
    cloud_label = _detect_cloud_platform(scan, graph)
    if cloud_label:
        nodes.append({
            "id": f"runtime-{_slug(cloud_label)}",
            "label": cloud_label,
            "type": "worker",
            "description": "Cloud environment inferred from infrastructure configuration and provider signals.",
            "confidence": "inferred",
            "group": "runtime",
        })

    file_tree = [path.replace("\\", "/").lower() for path in scan.file_tree]
    infra_keys = [path.replace("\\", "/").lower() for path in scan.infra_content]
    has_k8s = any(token in path for path in [*file_tree, *infra_keys] for token in ("k8s", "kubernetes", "ingress.", "deployment.", "service.", "chart.yaml"))
    has_terraform = any(path.endswith(".tf") or path.endswith(".hcl") for path in [*file_tree, *infra_keys])
    has_aspire = ".NET Aspire" in scan.frameworks
    has_docker = any(name.endswith("dockerfile") or name.endswith("docker-compose.yml") or name.endswith("docker-compose.yaml") for name in [*file_tree, *infra_keys])

    if has_terraform:
        nodes.append({
            "id": "runtime-terraform",
            "label": "Terraform Provisioning",
            "type": "worker",
            "description": "Infrastructure is provisioned or configured through Terraform.",
            "confidence": "verified",
            "group": "runtime",
        })
    if has_k8s:
        nodes.append({
            "id": "runtime-kubernetes",
            "label": "Kubernetes Cluster",
            "type": "worker",
            "description": "Application workloads are deployed into Kubernetes resources.",
            "confidence": "verified",
            "group": "runtime",
        })
    if has_aspire:
        nodes.append({
            "id": "runtime-aspire",
            "label": ".NET Aspire AppHost",
            "type": "worker",
            "description": "Aspire orchestrates local or cloud service composition for the application.",
            "confidence": "verified",
            "group": "runtime",
        })
    if has_docker:
        label = "Docker Compose" if any("docker-compose" in name for name in [*file_tree, *infra_keys]) else "Container Runtime"
        nodes.append({
            "id": "runtime-containers",
            "label": label,
            "type": "worker",
            "description": "Containerized workloads are built and run as part of the deployment topology.",
            "confidence": "verified",
            "group": "runtime",
        })

    if not nodes:
        nodes.append({
            "id": "runtime-application-host",
            "label": "Application Runtime",
            "type": "worker",
            "description": "Primary hosting environment inferred from repository structure and frameworks.",
            "confidence": "inferred",
            "group": "runtime",
        })

    return _dedupe_nodes(nodes)


def _build_ingress_nodes(scan: RepoScan, graph: ArchGraph, runtime: list[dict]) -> list[dict]:
    has_frontend = any(node.type == "frontend" for node in graph.nodes)
    has_api = bool(scan.apis)
    if not has_frontend and not has_api:
        return []

    label = "Web Ingress" if has_frontend else "API Gateway"
    description = (
        "Receives browser traffic and forwards requests into the deployed application services."
        if has_frontend
        else "Receives external API traffic and forwards it to the application workloads."
    )
    return [{
        "id": "ops-ingress",
        "label": label,
        "type": "worker",
        "description": description,
        "confidence": "inferred" if runtime and runtime[-1]["confidence"] != "verified" else "verified",
        "group": "ingress",
    }]


def _build_cicd_nodes(scan: RepoScan) -> list[dict]:
    if not scan.cicd:
        return []
    platform = scan.cicd[0].platform
    platform_label = _CICD_LABELS.get(platform, platform.replace("_", " ").title())
    return [
        {
            "id": f"cicd-{platform}-build",
            "label": "Build",
            "type": "worker",
            "description": f"{platform_label} builds application artifacts and validates dependencies.",
            "confidence": "verified",
            "group": "cicd",
        },
        {
            "id": f"cicd-{platform}-test",
            "label": "Test",
            "type": "worker",
            "description": f"{platform_label} runs quality checks before deployment.",
            "confidence": "verified",
            "group": "cicd",
        },
        {
            "id": f"cicd-{platform}-deploy",
            "label": "Deploy",
            "type": "worker",
            "description": f"{platform_label} promotes the latest release into the runtime environment.",
            "confidence": "verified",
            "group": "cicd",
        },
    ]


def _build_service_nodes(graph: ArchGraph) -> list[dict]:
    services: list[dict] = []
    for node in graph.nodes:
        if node.type not in {"service", "frontend"}:
            continue
        framework = node.metadata.get("framework") if isinstance(node.metadata, dict) else ""
        description = (
            f"User-facing workload built with {framework}."
            if node.type == "frontend" and framework
            else "User-facing workload serving the application interface."
            if node.type == "frontend"
            else f"Core application workload built with {framework}."
            if framework
            else "Core application workload serving business logic."
        )
        services.append({
            "id": node.id,
            "label": node.label,
            "type": "frontend" if node.type == "frontend" else "backend",
            "description": description,
            "confidence": "verified",
            "group": "services",
        })
    return services


def _build_data_nodes(graph: ArchGraph) -> list[dict]:
    nodes: list[dict] = []
    for node in graph.nodes:
        if node.type not in {"database", "cache", "queue"}:
            continue
        if node.type == "database":
            description = "Persistent data store used by application services."
        elif node.type == "cache":
            description = "Low-latency cache layer used to reduce backend load."
        else:
            description = "Message or background processing queue used for asynchronous work."
        nodes.append({
            "id": node.id,
            "label": node.label,
            "type": node.type,
            "description": description,
            "confidence": "verified",
            "group": "data",
        })
    return nodes


def _build_observability_nodes(scan: RepoScan) -> list[dict]:
    nodes: list[dict] = []
    seen: set[str] = set()
    for lib in scan.observability_libs:
        label, description = _OBSERVABILITY_LABELS.get(
            lib,
            (lib.replace("-", " ").title(), "Observability tooling used to monitor or trace workloads."),
        )
        node_id = f"obs-{_slug(label)}"
        if node_id in seen:
            continue
        seen.add(node_id)
        nodes.append({
            "id": node_id,
            "label": label,
            "type": "worker",
            "description": description,
            "confidence": "verified",
            "group": "observability",
        })
    return nodes[:3]


def _detect_cloud_platform(scan: RepoScan, graph: ArchGraph) -> str | None:
    corpus = "\n".join(scan.infra_content.values()).lower()
    for node in graph.nodes:
        if node.type == "external_api":
            corpus += f"\n{node.label.lower()}"
    for needle, label in _CLOUD_HINTS.items():
        if needle in corpus:
            return label
    return None


def _operational_label(edge_type: str) -> str:
    return {
        "reads/writes": "Reads and writes data",
        "caches": "Uses cache",
        "publishes": "Publishes async work",
        "consumes": "Consumes async work",
        "calls": "Service call",
        "http": "HTTP request",
    }.get(edge_type, "Operational dependency")


def _slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


def _dedupe_nodes(nodes: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for node in nodes:
        if node["id"] in seen:
            continue
        seen.add(node["id"])
        result.append(node)
    return result


def _dedupe_edges(edges: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict] = []
    for edge in edges:
        key = (edge["source"], edge["target"], edge["label"])
        if key in seen:
            continue
        seen.add(key)
        result.append(edge)
    return result
