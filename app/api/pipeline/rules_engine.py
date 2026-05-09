"""
Rules Engine — pure Python, no LLM.
Evaluates an ArchGraph and optionally source code to flag architectural bottlenecks.
"""
import os
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from pipeline.scanner import RepoScan
from pipeline.graph_builder import ArchGraph


# ── Output schema ──────────────────────────────────────────────────────────────

class Issue(BaseModel):
    type: str
    severity: Literal["low", "medium", "high", "critical"]
    affected: list[str]      # node IDs or file paths involved
    description: str
    recommendation: str


# ── Thresholds ─────────────────────────────────────────────────────────────────

_CHAIN_DEPTH_THRESHOLD   = 5
_MANY_EXTERNAL_THRESHOLD = 3


# ── Public API ─────────────────────────────────────────────────────────────────

def run_rules(
    scan: RepoScan,
    graph: ArchGraph,
    root: Path | None = None,
) -> list[Issue]:
    """
    Run all rules and return issues sorted by severity.
    Pass *root* to also enable source-code level rules (N+1 detection).
    """
    issues: list[Issue] = []

    # Graph-based rules (fast, no I/O)
    issues += _rule_missing_cache(graph)
    issues += _rule_shared_db_contention(graph)
    issues += _rule_external_api_coupling(graph)
    issues += _rule_deep_service_chain(graph)
    issues += _rule_no_async_queue(graph)

    # Code-based rules (requires walking source files)
    if root is not None:
        issues += _rule_n_plus_one(root, scan, graph)

    return _sort_by_severity(issues)


# ── Rule 1: Missing cache layer ────────────────────────────────────────────────

def _rule_missing_cache(graph: ArchGraph) -> list[Issue]:
    db_ids    = [n.id for n in graph.nodes if n.type == "database"]
    cache_ids = [n.id for n in graph.nodes if n.type == "cache"]

    if db_ids and not cache_ids:
        return [Issue(
            type="Missing Cache Layer",
            severity="medium",
            affected=db_ids,
            description=(
                f"{len(db_ids)} database(s) detected but no caching layer found. "
                "Every read hits the database directly."
            ),
            recommendation=(
                "Add Redis or Memcached in front of frequently read data. "
                "Start with read-through caching on the hottest queries."
            ),
        )]
    return []


# ── Rule 2: Shared database contention ────────────────────────────────────────

def _rule_shared_db_contention(graph: ArchGraph) -> list[Issue]:
    service_ids = {n.id for n in graph.nodes if n.type == "service"}
    db_ids      = {n.id for n in graph.nodes if n.type == "database"}

    db_writers: dict[str, list[str]] = {db: [] for db in db_ids}
    for edge in graph.edges:
        if edge.source in service_ids and edge.target in db_ids and edge.type == "reads/writes":
            db_writers[edge.target].append(edge.source)

    issues: list[Issue] = []
    for db_id, writers in db_writers.items():
        if len(writers) > 1:
            issues.append(Issue(
                type="Shared Database Contention",
                severity="high",
                affected=[db_id] + writers,
                description=(
                    f"'{db_id}' is shared by {len(writers)} services: {writers}. "
                    "Services competing for the same database create connection pool pressure "
                    "and tight coupling — a schema change in one service can break others."
                ),
                recommendation=(
                    "Apply database-per-service pattern. If sharing is unavoidable, "
                    "introduce a single service as the authoritative owner of this database "
                    "and expose it via API to others."
                ),
            ))
    return issues


# ── Rule 3: External API coupling ─────────────────────────────────────────────

def _rule_external_api_coupling(graph: ArchGraph) -> list[Issue]:
    ext_node_ids = {n.id for n in graph.nodes if n.type == "external_api"}
    if not ext_node_ids:
        return []

    # Group external dependencies per calling service
    service_to_exts: dict[str, list[str]] = {}
    for edge in graph.edges:
        if edge.type == "calls" and edge.target in ext_node_ids:
            service_to_exts.setdefault(edge.source, []).append(edge.target)

    issues: list[Issue] = []
    for svc_id, exts in service_to_exts.items():
        severity: Literal["low", "medium", "high", "critical"] = (
            "medium" if len(exts) > _MANY_EXTERNAL_THRESHOLD else "low"
        )
        issues.append(Issue(
            type="External API Latency Risk",
            severity=severity,
            affected=[svc_id] + exts,
            description=(
                f"'{svc_id}' depends on {len(exts)} external API(s): {exts}. "
                "Each call adds network latency and is a potential failure point outside your control."
            ),
            recommendation=(
                "Wrap every external call with a timeout and retry policy. "
                "Cache responses where the data allows it. "
                "Use a circuit breaker to prevent cascade failures."
            ),
        ))
    return issues


# ── Rule 4: Deep service chain ─────────────────────────────────────────────────

def _rule_deep_service_chain(graph: ArchGraph) -> list[Issue]:
    service_ids = {n.id for n in graph.nodes if n.type in ("service", "frontend")}

    # Build adjacency from any edge between two services/frontends
    adj: dict[str, list[str]] = {sid: [] for sid in service_ids}
    for edge in graph.edges:
        if edge.source in service_ids and edge.target in service_ids:
            adj[edge.source].append(edge.target)

    depth = _longest_path(adj)

    if depth >= _CHAIN_DEPTH_THRESHOLD:
        return [Issue(
            type="Deep Service Chain",
            severity="high",
            affected=list(service_ids),
            description=(
                f"Synchronous service call chain depth of {depth} detected. "
                "Each hop multiplies latency — one slow service stalls every caller above it."
            ),
            recommendation=(
                "Break long chains with async messaging (queues or events) for non-critical paths. "
                "For critical paths, introduce an aggregator/BFF service to parallelise downstream calls."
            ),
        )]
    return []


# ── Rule 5: No async queue between services ────────────────────────────────────

def _rule_no_async_queue(graph: ArchGraph) -> list[Issue]:
    service_ids = [n.id for n in graph.nodes if n.type == "service"]
    has_queue   = any(n.type == "queue" for n in graph.nodes)

    if len(service_ids) > 2 and not has_queue:
        return [Issue(
            type="No Async Queue Between Services",
            severity="medium",
            affected=service_ids,
            description=(
                f"{len(service_ids)} backend services detected with no message queue. "
                "All inter-service communication is synchronous and tightly coupled."
            ),
            recommendation=(
                "Introduce a message queue (Celery + Redis, RabbitMQ, or Kafka) for "
                "operations that don't need an immediate response — notifications, "
                "background jobs, event fanout."
            ),
        )]
    return []


# ── Rule 6: N+1 query (code-level) ────────────────────────────────────────────

_SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".next",
    "dist", "build", "target", "out", ".mypy_cache", ".pytest_cache",
}
_MAX_FILE_BYTES = 200 * 1024

# Loop openers per language bucket
_LOOP_RE: dict[str, re.Pattern] = {
    "python": re.compile(r"^\s*(for|while)\s+"),
    "js":     re.compile(r"\b(for|while)\s*[\(\s]"),
    "java":   re.compile(r"\b(for|while)\s*\("),
}

# Database call signatures per language bucket
_DB_CALL_RE: dict[str, re.Pattern] = {
    "python": re.compile(
        r"\b("
        r"session\.(get|query|execute|scalar|scalars)\b"
        r"|db\.(query|execute|get)\b"
        r"|\.objects\.(get|filter|all|exclude)\b"
        r"|await\s+\w+\.(fetch|execute|fetchrow|fetchval)\b"
        r"|\.first\(\)|\.all\(\)"
        r")",
        re.IGNORECASE,
    ),
    "js": re.compile(
        r"\b("
        r"prisma\.\w+\.(find\w*|create|update\w*|delete\w*|upsert)\b"
        r"|await\s+\w+\.(find\w*|save|update|delete|query|execute)\b"
        r"|repository\.(find\w*|save|update|delete)\b"
        r")",
        re.IGNORECASE,
    ),
    "java": re.compile(
        r"\b("
        r"repository\.(find\w*|save|delete\w*)\b"
        r"|entityManager\.(find|persist|merge|remove)\b"
        r"|\.findById\(|\.findAll\("
        r")",
        re.IGNORECASE,
    ),
}

_EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".js": "js", ".ts": "js", ".jsx": "js", ".tsx": "js",
    ".java": "java",
}


def _rule_n_plus_one(
    root: Path,
    scan: RepoScan,
    graph: ArchGraph,
) -> list[Issue]:
    db_ids = [n.id for n in graph.nodes if n.type == "database"]
    if not db_ids:
        return []

    issues: list[Issue] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in _SKIP_DIRS and not d.startswith(".")
        ]
        for filename in filenames:
            fpath = Path(dirpath) / filename
            lang  = _EXT_TO_LANG.get(fpath.suffix.lower())
            if not lang:
                continue
            try:
                if fpath.stat().st_size > _MAX_FILE_BYTES:
                    continue
                content = fpath.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            lineno = _find_n_plus_one(content, lang)
            if lineno is None:
                continue

            rel     = str(fpath.relative_to(root))
            service = _file_to_service(rel, scan.services)
            issues.append(Issue(
                type="N+1 Query",
                severity="high",
                affected=[service] if service else [],
                description=(
                    f"Database call inside a loop detected at {rel}:{lineno}. "
                    "This executes one query per iteration — O(n) DB hits instead of one."
                ),
                recommendation=(
                    "Move the query outside the loop and fetch all needed records in a single "
                    "batch (IN clause, eager loading, or joinedload/select_related)."
                ),
            ))

    return issues


def _find_n_plus_one(content: str, lang: str) -> int | None:
    """Return the 1-based line number of the loop that contains a DB call, or None."""
    loop_re = _LOOP_RE.get(lang)
    db_re   = _DB_CALL_RE.get(lang)
    if not loop_re or not db_re:
        return None

    lines = content.splitlines()
    for i, line in enumerate(lines):
        if not loop_re.search(line):
            continue

        loop_indent = len(line) - len(line.lstrip())

        # Inspect up to 30 lines of the loop body
        for j in range(i + 1, min(i + 31, len(lines))):
            body = lines[j]
            if not body.strip():
                continue
            body_indent = len(body) - len(body.lstrip())
            if body_indent <= loop_indent:
                break          # walked out of the loop body
            if db_re.search(body):
                return i + 1  # report the loop's line number (1-based)

    return None


def _file_to_service(rel_path: str, services: list[str]) -> str:
    norm = rel_path.replace("\\", "/")
    for svc in services:
        if norm.startswith(svc + "/") or f"/{svc}/" in norm:
            return svc
    return services[0] if services else "unknown"


# ── Graph utilities ────────────────────────────────────────────────────────────

def _longest_path(adj: dict[str, list[str]]) -> int:
    """Longest path in a DAG via memoised DFS. Returns 0 for an empty graph."""
    memo: dict[str, int] = {}

    def dfs(node: str) -> int:
        if node in memo:
            return memo[node]
        result = 1 + max((dfs(nb) for nb in adj.get(node, [])), default=0)
        memo[node] = result
        return result

    return max((dfs(n) for n in adj), default=0)


_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _sort_by_severity(issues: list[Issue]) -> list[Issue]:
    return sorted(issues, key=lambda i: _SEVERITY_RANK.get(i.severity, 99))
