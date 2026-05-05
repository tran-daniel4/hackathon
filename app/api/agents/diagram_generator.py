import re


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def generate_diagram(system_design: dict, bottlenecks: dict) -> dict:
    components = system_design.get("components", [])
    data_flow = system_design.get("data_flow", [])
    layers = system_design.get("layers", [])
    detected = bottlenecks.get("bottlenecks", [])

    # Build a lookup: component name → layer name
    component_layer: dict[str, str] = {}
    for layer in layers:
        for comp_name in layer.get("components", []):
            component_layer[comp_name] = layer.get("name", "")

    # Build a lookup: component name → bottleneck severity (worst if multiple)
    severity_rank = {"low": 1, "medium": 2, "high": 3}
    component_severity: dict[str, str] = {}
    for b in detected:
        comp = b.get("component", "")
        incoming = b.get("severity", "low")
        existing = component_severity.get(comp)
        if existing is None or severity_rank.get(incoming, 0) > severity_rank.get(existing, 0):
            component_severity[comp] = incoming

    nodes = [
        {
            "id": _slugify(c["name"]),
            "label": c["name"],
            "type": c.get("type", "unknown"),
            "layer": component_layer.get(c["name"], ""),
            "severity": component_severity.get(c["name"]),  # None if no bottleneck
        }
        for c in components
    ]

    edges = [
        {
            "id": f"{_slugify(f['from'])}-{_slugify(f['to'])}",
            "source": _slugify(f["from"]),
            "target": _slugify(f["to"]),
            "label": f.get("protocol", ""),
        }
        for f in data_flow
    ]

    annotations = [
        {
            "node_id": _slugify(b["component"]),
            "type": b.get("type", ""),
            "severity": b.get("severity", "low"),
            "description": b.get("description", ""),
        }
        for b in detected
    ]

    return {"nodes": nodes, "edges": edges, "annotations": annotations}
