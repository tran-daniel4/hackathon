from __future__ import annotations

import re

from analyzers.extractors._helpers import infer_service_id
from analyzers.file_index import FileIndex
from bottlenecks.evidence import EvidenceRegistry
from bottlenecks.models import DbCallSignal, LoopSignal, RouteSignal
from bottlenecks.signals.code_signal_extractor import line_in_loop, route_lookup

_DB_CALLS: list[tuple[str, re.Pattern, bool]] = [
    ("findMany", re.compile(r"\.findMany\s*\(", re.IGNORECASE), False),
    ("findAll", re.compile(r"\.findAll\s*\(", re.IGNORECASE), False),
    ("find", re.compile(r"\.find\w*\s*\(", re.IGNORECASE), False),
    ("query", re.compile(r"\b(query|execute|fetch|fetchrow|fetchall)\s*\(", re.IGNORECASE), False),
    ("select", re.compile(r"\bSELECT\b", re.IGNORECASE), False),
    ("insert", re.compile(r"\b(insert|create|save|persist)\b", re.IGNORECASE), True),
    ("update", re.compile(r"\b(update|merge)\b", re.IGNORECASE), True),
    ("delete", re.compile(r"\bdelete\b", re.IGNORECASE), True),
]
_LIMIT_RE = re.compile(r"\b(limit|offset|page|pagesize|page_size|cursor|take|skip|first|after)\b", re.IGNORECASE)
_MODEL_RE = re.compile(r"\b(from|into|update|table)\s+([A-Za-z_][A-Za-z0-9_]*)|\b([A-Za-z_][A-Za-z0-9_]*)\.(findMany|findUnique|findFirst)\b", re.IGNORECASE)


def extract_db_calls(
    file_index: FileIndex,
    routes: list[RouteSignal],
    loops: list[LoopSignal],
    evidence: EvidenceRegistry,
) -> list[DbCallSignal]:
    results: list[DbCallSignal] = []
    counter = 0
    for path in file_index.paths:
        content = file_index.get_content(path) or ""
        lines = content.splitlines()
        component_id = infer_service_id(path)
        for lineno, line in enumerate(lines, start=1):
            operation = None
            is_write = False
            for op_name, pattern, op_is_write in _DB_CALLS:
                if pattern.search(line):
                    operation = op_name
                    is_write = op_is_write
                    break
            if not operation:
                continue
            counter += 1
            ev_id = evidence.ensure(
                file_path=path,
                start_line=lineno,
                end_line=lineno,
                excerpt=line,
            )
            model_match = _MODEL_RE.search(line)
            model = None
            if model_match:
                model = next((group for group in model_match.groups() if group and group.lower() not in {"from", "into", "update", "table", "findmany", "findunique", "findfirst"}), None)
            results.append(DbCallSignal(
                id=f"db_{counter:04d}",
                component_id=component_id,
                enclosing_route_id=route_lookup(routes, path, lineno, component_id),
                operation=operation,
                table_or_model=model,
                has_limit=bool(_LIMIT_RE.search(line)),
                inside_loop_id=line_in_loop(path, lineno, loops),
                file_path=path.replace("\\", "/"),
                start_line=lineno,
                end_line=lineno,
                evidence_id=ev_id,
                is_write=is_write,
            ))
    return results
