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
_LAYER_ROOTS = {"backend", "backends", "frontend", "frontends", "client", "clients", "server", "servers", "worker", "workers"}
_GENERIC_DIR_NAMES = {
    "src", "source", "lib", "libs", "bin", "obj", "dist", "build", "public", "static",
    "components", "pages", "app", "domain", "shared", "common", "config", "configs",
    "controllers", "models", "views", "routes", "templates", "tests", "test", "spec",
    "specs", "resources", "assets",
}
_PROJECT_MARKER_FILES = {
    "requirements.txt", "pyproject.toml", "package.json", "pom.xml", "build.gradle",
    "go.mod", "Gemfile", "composer.json", "Cargo.toml", "Pipfile", "manage.py",
    "main.py", "app.py", "server.py", "wsgi.py", "asgi.py", "index.js", "index.ts",
    "server.js", "server.ts", "app.js", "Application.java", "Main.java", "main.go",
    "main.rb", "Program.cs", "Startup.cs", "AppHost.cs",
}


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


def _is_generic_dir(name: str) -> bool:
    return name.lower() in _GENERIC_DIR_NAMES


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

    for idx, part in enumerate(parts[:-1]):
        if part.lower() in _LAYER_ROOTS and idx + 1 < len(parts):
            candidate = parts[idx + 1]
            if not _is_generic_dir(candidate):
                return candidate
            return part

    for idx in range(len(parts) - 2, -1, -1):
        candidate = parts[idx]
        if _is_generic_dir(candidate):
            continue
        parent = parts[idx - 1].lower() if idx > 0 else ""
        if parent in _CONTAINER_DIRS or parent in _SOURCE_ROOTS or parent in _LAYER_ROOTS:
            return candidate

    basename = parts[-1]
    if _extension(basename) in _PROJECT_EXTS and len(parts) >= 2:
        return parts[-2]

    if basename in _PROJECT_ENTRY_FILES and len(parts) >= 2:
        return parts[-2]

    if basename in _PROJECT_MARKER_FILES and len(parts) >= 2:
        parent = parts[-2]
        if not _is_generic_dir(parent):
            return parent
        if len(parts) >= 3 and not _is_generic_dir(parts[-3]):
            return parts[-3]

    return parts[0]


def infer_service_id(file_path: str) -> str:
    """Return a stable service node ID inferred from the file's directory structure."""
    from graph.models import make_node_id
    return make_node_id(infer_service_name(file_path))
