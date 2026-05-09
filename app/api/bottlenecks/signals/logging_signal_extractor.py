from __future__ import annotations

import re

from analyzers.extractors._helpers import infer_service_id
from analyzers.file_index import FileIndex
from bottlenecks.evidence import EvidenceRegistry
from bottlenecks.models import LoggingSignal, LoopSignal, RouteSignal
from bottlenecks.signals.code_signal_extractor import line_in_loop, route_lookup

_LOG_RE = re.compile(r"\b(logger|logging|console|Serilog|Log\.)\s*\.(debug|info|warn|warning|error|trace|log)\s*\(", re.IGNORECASE)
_PAYLOAD_RE = re.compile(r"\b(body|payload|request|response|json|headers)\b", re.IGNORECASE)


def extract_logging_calls(
    file_index: FileIndex,
    routes: list[RouteSignal],
    loops: list[LoopSignal],
    evidence: EvidenceRegistry,
) -> list[LoggingSignal]:
    results: list[LoggingSignal] = []
    counter = 0
    for path in file_index.paths:
        content = file_index.get_content(path) or ""
        lines = content.splitlines()
        component_id = infer_service_id(path)
        for lineno, line in enumerate(lines, start=1):
            match = _LOG_RE.search(line)
            if not match:
                continue
            counter += 1
            ev_id = evidence.ensure(file_path=path, start_line=lineno, end_line=lineno, excerpt=line)
            level = match.group(2).lower()
            results.append(LoggingSignal(
                id=f"log_{counter:04d}",
                component_id=component_id,
                enclosing_route_id=route_lookup(routes, path, lineno, component_id),
                level=level,
                file_path=path.replace("\\", "/"),
                start_line=lineno,
                end_line=lineno,
                evidence_id=ev_id,
                inside_loop_id=line_in_loop(path, lineno, loops),
                logs_payload=bool(_PAYLOAD_RE.search(line)),
                debug_logging=level in {"debug", "trace", "log"},
            ))
    return results
