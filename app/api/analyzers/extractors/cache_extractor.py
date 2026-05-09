import re

from analyzers.base import Analyzer
from analyzers.file_index import FileIndex
from analyzers.extractors._helpers import ev_tmp, file_basename, infer_service_id
from graph.models import GraphFactPatch, NodeFact, EdgeFact, Evidence, make_node_id


_SRC_EXTS = frozenset({".py", ".ts", ".js", ".jsx", ".tsx", ".cs"})

_REDIS_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"redis\.Redis\s*\(",
        r"redis\.from_url\s*\(",
        r"aioredis\.from_url\s*\(",
        r"aioredis\.create_redis_pool\s*\(",
        r"new\s+Redis\s*\(",
        r'require\s*\(\s*["\']ioredis["\']',
        r'from redis import',
        r'import redis',
        r"redis://",
        r"StackExchange\.Redis",
        r"AddRedis\s*\(",
        r"Aspire\.Hosting\.Redis",
        r"\bredis\.(?:get|set|setex|delete|del|exists|hget|hset|mget|mset)\s*\(",
    ]
]

_MEMCACHED_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"memcache\.Client\s*\(",
        r"pylibmc\.Client\s*\(",
        r"new\s+Memcached\s*\(",
        r"memcached://",
    ]
]

# Patterns that suggest a read operation on the cache
_READ_HINT_RE = re.compile(r'\.get\s*\(', re.IGNORECASE)


class CacheExtractor(Analyzer):
    def supports(self, file_index: FileIndex) -> bool:
        return any(
            ("." + p.rsplit(".", 1)[-1].lower()) in _SRC_EXTS
            for p in file_index.paths
            if "." in file_basename(p)
        )

    def analyze(self, file_index: FileIndex) -> GraphFactPatch:
        patch = GraphFactPatch()
        emitted_cache_nodes: set[str] = set()
        emitted_edges: set[tuple[str, str, str]] = set()  # (svc, cache, kind)

        for path in file_index.paths:
            base = file_basename(path)
            ext = ("." + base.rsplit(".", 1)[-1].lower()) if "." in base else ""
            if ext not in _SRC_EXTS:
                continue

            content = file_index.get_content(path) or ""
            lines = content.splitlines()

            for lineno, line in enumerate(lines, start=1):
                matched_cache: str | None = None

                if any(rx.search(line) for rx in _REDIS_PATTERNS):
                    matched_cache = "Redis"
                elif any(rx.search(line) for rx in _MEMCACHED_PATTERNS):
                    matched_cache = "Memcached"

                if not matched_cache:
                    continue

                cache_id = make_node_id(matched_cache)
                svc_id = infer_service_id(path)
                edge_kind = "cache_read" if _READ_HINT_RE.search(line) else "cache_write"
                edge_key = (svc_id, cache_id, edge_kind)

                ev_id = ev_tmp()
                patch.evidence.append(Evidence(
                    id=ev_id,
                    kind="code_reference",
                    file_path=path,
                    start_line=lineno,
                    end_line=lineno,
                    excerpt=line.strip()[:120],
                ))

                if cache_id not in emitted_cache_nodes:
                    emitted_cache_nodes.add(cache_id)
                    patch.nodes.append(NodeFact(
                        id=cache_id,
                        type="cache",
                        name=matched_cache,
                        tags=["cache"],
                        confidence="verified",
                        evidence_ids=[ev_id],
                    ))

                if edge_key not in emitted_edges:
                    emitted_edges.add(edge_key)
                    patch.edges.append(EdgeFact(
                        id=f"edge-{svc_id}-{cache_id}-{edge_kind}",
                        src=svc_id,
                        dst=cache_id,
                        kind=edge_kind,  # type: ignore[arg-type]
                        confidence="inferred",
                        evidence_ids=[ev_id],
                    ))

        return patch
