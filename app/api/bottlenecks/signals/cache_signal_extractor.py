from __future__ import annotations

import re

from analyzers.extractors._helpers import infer_service_id
from analyzers.file_index import FileIndex
from bottlenecks.evidence import EvidenceRegistry
from bottlenecks.models import CacheCallSignal, RouteSignal
from bottlenecks.signals.code_signal_extractor import route_lookup

_GET_RE = re.compile(r"\.(get|GetString|tryGet|TryGetValue)\s*\(", re.IGNORECASE)
_SET_RE = re.compile(r"\.(set|SetString|setex|remember|cache\.set)\s*\(", re.IGNORECASE)
_DELETE_RE = re.compile(r"\.(delete|del|remove|invalidate)\s*\(", re.IGNORECASE)
_LOCK_RE = re.compile(r"\b(lock|mutex|singleflight|stale|coalesc|semaphore)\b", re.IGNORECASE)
_KEY_RE = re.compile(r"['\"]([A-Za-z0-9:_-]{3,})['\"]")


def extract_cache_calls(
    file_index: FileIndex,
    routes: list[RouteSignal],
    evidence: EvidenceRegistry,
) -> list[CacheCallSignal]:
    results: list[CacheCallSignal] = []
    counter = 0
    for path in file_index.paths:
        content = file_index.get_content(path) or ""
        lines = content.splitlines()
        component_id = infer_service_id(path)
        for lineno, line in enumerate(lines, start=1):
            operation = None
            if _GET_RE.search(line):
                operation = "get"
            elif _SET_RE.search(line):
                operation = "set"
            elif _DELETE_RE.search(line):
                operation = "delete"
            if not operation:
                continue
            counter += 1
            ev_id = evidence.ensure(
                file_path=path,
                start_line=lineno,
                end_line=lineno,
                excerpt=line,
            )
            window = "\n".join(lines[max(0, lineno - 3): min(len(lines), lineno + 4)])
            key_match = _KEY_RE.search(line)
            results.append(CacheCallSignal(
                id=f"cache_{counter:04d}",
                component_id=component_id,
                enclosing_route_id=route_lookup(routes, path, lineno, component_id),
                operation=operation,  # type: ignore[arg-type]
                cache="redis",
                key_hint=key_match.group(1) if key_match else None,
                file_path=path.replace("\\", "/"),
                start_line=lineno,
                end_line=lineno,
                evidence_id=ev_id,
                coordination_detected=bool(_LOCK_RE.search(window)),
            ))
    return results
