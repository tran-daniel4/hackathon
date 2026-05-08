import re
import uuid
from dataclasses import dataclass
from typing import Optional

from analyzers.base import Analyzer
from analyzers.file_index import FileIndex
from analyzers.extractors._helpers import ev_tmp, file_basename, file_parts, infer_service_id
from graph.models import GraphFactPatch, NodeFact, ApiFact, Evidence, make_node_id


@dataclass
class _ApiPattern:
    extensions: frozenset
    regex: re.Pattern
    method_group: Optional[int]
    path_group: int
    filename_filter: Optional[frozenset] = None


_API_PATTERNS: list[_ApiPattern] = [
    _ApiPattern(
        extensions=frozenset({".py"}),
        regex=re.compile(
            r'@\w+(?:\.\w+)*\.(get|post|put|delete|patch|head|options)\s*\(\s*["\']([^"\']+)["\']',
            re.IGNORECASE,
        ),
        method_group=1,
        path_group=2,
    ),
    _ApiPattern(
        extensions=frozenset({".py"}),
        regex=re.compile(r'^\s*path\s*\(\s*["\']([^"\']+)["\']'),
        method_group=None,
        path_group=1,
        filename_filter=frozenset({"urls.py"}),
    ),
    _ApiPattern(
        extensions=frozenset({".js", ".ts", ".mjs", ".cjs"}),
        regex=re.compile(
            r'(?:app|router|server)\.(get|post|put|delete|patch|head|options)\s*\(\s*["\']([^"\']+)["\']',
            re.IGNORECASE,
        ),
        method_group=1,
        path_group=2,
    ),
    _ApiPattern(
        extensions=frozenset({".cs"}),
        regex=re.compile(
            r'\bMap(Get|Post|Put|Delete|Patch)\s*\(\s*["\']([^"\']+)["\']',
            re.IGNORECASE,
        ),
        method_group=1,
        path_group=2,
    ),
    _ApiPattern(
        extensions=frozenset({".cs"}),
        regex=re.compile(
            r'\[(HttpGet|HttpPost|HttpPut|HttpDelete|HttpPatch|Route)\s*\(\s*["\']([^"\']+)["\']',
            re.IGNORECASE,
        ),
        method_group=1,
        path_group=2,
    ),
]
_FLASK_ROUTE_RE = re.compile(
    r'@(?:\w+\.)?route\s*\(\s*["\']([^"\']+)["\'](?P<rest>[^)]*)\)',
    re.IGNORECASE,
)
_FLASK_METHODS_RE = re.compile(r'methods\s*=\s*\[([^\]]+)\]', re.IGNORECASE)
_NEST_CONTROLLER_RE = re.compile(
    r'@Controller\s*\(\s*(?:["\']([^"\']*)["\']|\{[^}]*path\s*:\s*["\']([^"\']*)["\'][^}]*\})?\s*\)',
    re.IGNORECASE,
)
_NEST_METHOD_RE = re.compile(
    r'@(Get|Post|Put|Delete|Patch|Head|Options|All)\s*\(\s*(?:["\']([^"\']*)["\'])?',
    re.IGNORECASE,
)
_SPRING_CLASS_ROUTE_RE = re.compile(
    r'@RequestMapping\s*\(\s*(?:(?:value|path)\s*=\s*)?["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_SPRING_METHOD_RE = re.compile(
    r'@(?:(Get|Post|Put|Delete|Patch)Mapping|RequestMapping)\s*\(([^)]*)\)',
    re.IGNORECASE,
)

_NEXT_EXPORT_METHOD_RE = re.compile(
    r'export\s+(?:async\s+)?function\s+(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\b',
    re.IGNORECASE,
)

_SRC_EXTS = frozenset({".py", ".ts", ".js", ".java", ".cs", ".mjs", ".cjs", ".jsx", ".tsx"})


def _infer_method(line: str) -> str:
    low = line.lower()
    for m in ("get", "post", "put", "delete", "patch", "head", "options"):
        if m in low:
            return m.upper()
    return "ROUTE"


def _normalize_method(method: str) -> str:
    method = method.upper()
    return method[4:] if method.startswith("HTTP") else method


def _join_api_path(prefix: str, suffix: str) -> str:
    prefix = (prefix or "").strip()
    suffix = (suffix or "").strip()
    if not prefix and not suffix:
        return "/"
    segments = [segment.strip("/") for segment in (prefix, suffix) if segment and segment != "/"]
    return "/" + "/".join(segments) if segments else "/"


def _extract_spring_path(args: str) -> str:
    value_match = re.search(r'(?:value|path)\s*=\s*["\']([^"\']+)["\']', args, re.IGNORECASE)
    if value_match:
        return value_match.group(1)
    direct_match = re.search(r'["\']([^"\']+)["\']', args)
    return direct_match.group(1) if direct_match else ""


def _extract_spring_method(method_group: str | None, args: str) -> str:
    if method_group:
        return method_group.upper()
    request_method = re.search(r'RequestMethod\.(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)', args, re.IGNORECASE)
    return request_method.group(1).upper() if request_method else "ROUTE"


class RouteExtractor(Analyzer):
    def supports(self, file_index: FileIndex) -> bool:
        return any(
            "." + p.rsplit(".", 1)[-1].lower() in _SRC_EXTS
            for p in file_index.paths
            if "." in file_basename(p)
        )

    def analyze(self, file_index: FileIndex) -> GraphFactPatch:
        patch = GraphFactPatch()
        seen_routes: set[tuple[str, str]] = set()
        seen_service_nodes: set[str] = set()
        api_counter = 0

        def _ensure_service_node(service_id: str) -> None:
            if service_id not in seen_service_nodes:
                seen_service_nodes.add(service_id)
                patch.nodes.append(NodeFact(
                    id=service_id,
                    type="service",
                    name=service_id.replace("-", " ").title(),
                    confidence="inferred",
                ))

        def _emit_api(path: str, lineno: int, method: str, api_path: str) -> None:
            nonlocal api_counter
            key = (method, api_path)
            if key in seen_routes:
                return
            seen_routes.add(key)
            api_counter += 1

            svc_id = infer_service_id(path)
            _ensure_service_node(svc_id)

            line = lines[lineno - 1] if 0 < lineno <= len(lines) else ""
            ev_id = ev_tmp()
            patch.evidence.append(Evidence(
                id=ev_id,
                kind="code_reference",
                file_path=path,
                start_line=lineno,
                end_line=lineno,
                excerpt=line.strip()[:120],
            ))
            patch.apis.append(ApiFact(
                id=f"api_{api_counter:04d}",
                component_id=svc_id,
                method=method,
                path=api_path,
                evidence_ids=[ev_id],
            ))

        # Standard route patterns
        for path in file_index.paths:
            base = file_basename(path)
            ext = ("." + base.rsplit(".", 1)[-1].lower()) if "." in base else ""
            if ext not in _SRC_EXTS:
                continue

            content = file_index.get_content(path) or ""
            lines = content.splitlines()

            for pat in _API_PATTERNS:
                if ext not in pat.extensions:
                    continue
                if pat.filename_filter and base not in pat.filename_filter:
                    continue
                for lineno, line in enumerate(lines, start=1):
                    m = pat.regex.search(line)
                    if not m:
                        continue
                    raw_path = m.group(pat.path_group).strip()
                    api_path = raw_path if raw_path.startswith("/") else f"/{raw_path}"
                    method = (
                        _normalize_method(m.group(pat.method_group))
                        if pat.method_group
                        else _infer_method(line)
                    )
                    _emit_api(path, lineno, method, api_path)

            if ext == ".py":
                for lineno, line in enumerate(lines, start=1):
                    match = _FLASK_ROUTE_RE.search(line)
                    if not match:
                        continue
                    methods_match = _FLASK_METHODS_RE.search(match.group("rest") or "")
                    methods = ["GET"]
                    if methods_match:
                        methods = [token.strip(" '\"").upper() for token in methods_match.group(1).split(",") if token.strip()]
                    api_path = _join_api_path("", match.group(1))
                    for method in methods:
                        _emit_api(path, lineno, method, api_path)
            elif ext == ".ts":
                controller_prefix = ""
                for lineno, line in enumerate(lines, start=1):
                    controller = _NEST_CONTROLLER_RE.search(line)
                    if controller:
                        controller_prefix = controller.group(1) or controller.group(2) or ""
                        continue
                    route = _NEST_METHOD_RE.search(line)
                    if not route:
                        continue
                    api_path = _join_api_path(controller_prefix, route.group(2) or "")
                    _emit_api(path, lineno, route.group(1).upper(), api_path)
            elif ext == ".java":
                class_prefix = ""
                for lineno, line in enumerate(lines, start=1):
                    class_route = _SPRING_CLASS_ROUTE_RE.search(line)
                    if class_route:
                        class_prefix = class_route.group(1) or ""
                        continue
                    route = _SPRING_METHOD_RE.search(line)
                    if not route:
                        continue
                    args = route.group(2)
                    api_path = _join_api_path(class_prefix, _extract_spring_path(args))
                    method = _extract_spring_method(route.group(1), args)
                    _emit_api(path, lineno, method, api_path)

        # Next.js App Router: app/api/**/route.ts
        for path in file_index.paths:
            norm = path.replace("\\", "/")
            if not re.search(r'app/api/.+/route\.[tj]sx?$', norm, re.IGNORECASE):
                continue
            # Derive HTTP path from file path
            match = re.search(r'app/api/(.+)/route\.[tj]sx?$', norm, re.IGNORECASE)
            if not match:
                continue
            http_path = "/" + match.group(1)
            content = file_index.get_content(path) or ""
            for lineno, line in enumerate(content.splitlines(), start=1):
                m = _NEXT_EXPORT_METHOD_RE.search(line)
                if not m:
                    continue
                method = m.group(1).upper()
                key = (method, http_path)
                if key in seen_routes:
                    continue
                seen_routes.add(key)
                api_counter += 1

                svc_id = infer_service_id(path)
                _ensure_service_node(svc_id)

                ev_id = ev_tmp()
                patch.evidence.append(Evidence(
                    id=ev_id,
                    kind="code_reference",
                    file_path=path,
                    start_line=lineno,
                    end_line=lineno,
                    excerpt=line.strip()[:120],
                ))
                patch.apis.append(ApiFact(
                    id=f"api_{api_counter:04d}",
                    component_id=svc_id,
                    method=method,
                    path=http_path,
                    evidence_ids=[ev_id],
                ))

        if api_counter > 20:
            from graph.models import WarningFact
            patch.warnings.append(WarningFact(
                code="LARGE_API_SURFACE",
                message=f"{api_counter} API routes detected; diagram may be dense.",
            ))

        return patch
