"""Shared helpers for extractors."""
import uuid
from os.path import basename


def ev_tmp() -> str:
    return f"ev_tmp_{uuid.uuid4().hex[:8]}"


def file_basename(path: str) -> str:
    return path.replace("\\", "/").rsplit("/", 1)[-1]


def file_parts(path: str) -> list[str]:
    return [p for p in path.replace("\\", "/").split("/") if p]


_CONTAINER_DIRS = {"services", "apps", "packages", "modules", "microservices"}


def infer_service_id(file_path: str) -> str:
    """Return a stable service node ID inferred from the file's directory structure."""
    from graph.models import make_node_id
    parts = file_parts(file_path)
    if not parts:
        return "service-unknown"
    if len(parts) >= 2 and parts[0].lower() in _CONTAINER_DIRS:
        return make_node_id(parts[1])
    if len(parts) >= 2:
        return make_node_id(parts[0])
    return make_node_id(parts[0])
