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
        extensions=frozenset({".ts"}),
        regex=re.compile(
            r'@(Get|Post|Put|Delete|Patch)\s*\(\s*["\']([^"\']*)["\']',
            re.IGNORECASE,
        ),
        method_group=1,
        path_group=2,
    ),
    _ApiPattern(
        extensions=frozenset({".java"}),
        regex=re.compile(
            r'@(?:Get|Post|Put|Delete|Patch|Request)Mapping\s*\(\s*(?:value\s*=\s*)?["\']([^"\']+)["\']'
        ),
        method_group=None,
        path_group=1,
    ),
]

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
                        m.group(pat.method_group).upper()
                        if pat.method_group
                        else _infer_method(line)
                    )
                    key = (method, api_path)
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
                        path=api_path,
                        evidence_ids=[ev_id],
                    ))

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
