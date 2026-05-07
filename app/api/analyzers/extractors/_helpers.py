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
_SOURCE_ROOTS = {"src", "source"}
_PROJECT_EXTS = {".csproj", ".fsproj", ".vbproj", ".sln"}
_PROJECT_ENTRY_FILES = {"Program.cs", "Startup.cs", "AppHost.cs"}
_PROJECTISH_NAMES = {"api", "server", "backend", "frontend", "web", "apphost", "service"}


def _extension(path_part: str) -> str:
    if "." not in path_part:
        return ""
    return "." + path_part.rsplit(".", 1)[-1].lower()


def _looks_like_project_dir(name: str) -> bool:
    lower = name.lower()
    return (
        "." in name
        or "-" in name
        or "_" in name
        or lower in _PROJECTISH_NAMES
        or lower.endswith(("api", "service", "server", "apphost", "worker"))
    )


def infer_service_name(file_path: str) -> str:
    """Return a human-readable service/project name inferred from a repo path."""
    parts = file_parts(file_path)
    if not parts:
        return "service-unknown"

    for idx, part in enumerate(parts[:-1]):
        if part.lower() in _CONTAINER_DIRS and idx + 1 < len(parts):
            return parts[idx + 1]

    for idx, part in enumerate(parts[:-1]):
        if part.lower() in _SOURCE_ROOTS and idx + 1 < len(parts):
            candidate = parts[idx + 1]
            if _looks_like_project_dir(candidate):
                return candidate

    basename = parts[-1]
    if _extension(basename) in _PROJECT_EXTS and len(parts) >= 2:
        return parts[-2]

    if basename in _PROJECT_ENTRY_FILES and len(parts) >= 2:
        return parts[-2]

    return parts[0]


def infer_service_id(file_path: str) -> str:
    """Return a stable service node ID inferred from the file's directory structure."""
    from graph.models import make_node_id
    return make_node_id(infer_service_name(file_path))
