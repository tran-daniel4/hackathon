import re

from analyzers.base import Analyzer
from analyzers.file_index import FileIndex
from analyzers.extractors._helpers import ev_tmp, file_basename, infer_service_id
from graph.models import GraphFactPatch, NodeFact, EdgeFact, Evidence, make_node_id


_HTTP_CALL_RE = re.compile(
    r'(?:httpx|requests|axios|fetch)\s*\.\s*(?:get|post|put|delete|patch)\s*\(\s*["\']'
    r'(https?://([a-zA-Z0-9.-]+))',
    re.IGNORECASE,
)
_BASE_URL_RE = re.compile(
    r'(?:BASE_URL|base_url|API_URL|api_url)\s*[=:]\s*[f"\']+\s*'
    r'(https?://([a-zA-Z0-9.-]+))',
    re.IGNORECASE,
)
_CS_HTTP_CALL_RE = re.compile(
    r'\b(?:Get|Post|Put|Delete|Patch)Async\s*\(\s*["\']'
    r'(https?://([a-zA-Z0-9.-]+))',
    re.IGNORECASE,
)

_SRC_EXTS = frozenset({".py", ".ts", ".js", ".jsx", ".tsx", ".cs"})
_IGNORE_DOMAINS = {"localhost", "127.0.0.1", "example.com", "0.0.0.0"}


class HttpClientExtractor(Analyzer):
    def supports(self, file_index: FileIndex) -> bool:
        return any(
            ("." + p.rsplit(".", 1)[-1].lower()) in _SRC_EXTS
            for p in file_index.paths
            if "." in file_basename(p)
        )

    def analyze(self, file_index: FileIndex) -> GraphFactPatch:
        patch = GraphFactPatch()
        # (src_id, domain) → edge_id + evidence accumulator
        edge_evidence: dict[tuple[str, str], tuple[str, list[str]]] = {}

        for path in file_index.paths:
            base = file_basename(path)
            ext = ("." + base.rsplit(".", 1)[-1].lower()) if "." in base else ""
            if ext not in _SRC_EXTS:
                continue

            content = file_index.get_content(path) or ""
            lines = content.splitlines()

            for lineno, line in enumerate(lines, start=1):
                for pattern in (_HTTP_CALL_RE, _BASE_URL_RE, _CS_HTTP_CALL_RE):
                    m = pattern.search(line)
                    if not m:
                        continue
                    domain = m.group(2).lower().rstrip(".")
                    if not domain:
                        continue
                    if any(ig in domain for ig in _IGNORE_DOMAINS):
                        continue

                    svc_id = infer_service_id(path)
                    dst_id = make_node_id(domain)
                    key = (svc_id, dst_id)

                    ev_id = ev_tmp()
                    patch.evidence.append(Evidence(
                        id=ev_id,
                        kind="code_reference",
                        file_path=path,
                        start_line=lineno,
                        end_line=lineno,
                        excerpt=line.strip()[:120],
                    ))

                    if key not in edge_evidence:
                        edge_id = f"edge-{svc_id}-{dst_id}-http"
                        edge_evidence[key] = (edge_id, [ev_id])
                        # Emit external service node (graph_builder deduplicates by ID)
                        patch.nodes.append(NodeFact(
                            id=dst_id,
                            type="external_service",
                            name=domain,
                            tags=["http"],
                            confidence="inferred",
                            evidence_ids=[ev_id],
                        ))
                    else:
                        edge_evidence[key][1].append(ev_id)

        for (svc_id, dst_id), (edge_id, ev_ids) in edge_evidence.items():
            patch.edges.append(EdgeFact(
                id=edge_id,
                src=svc_id,
                dst=dst_id,
                kind="http",
                direction="outbound",
                confidence="inferred",
                evidence_ids=ev_ids,
            ))

        return patch
