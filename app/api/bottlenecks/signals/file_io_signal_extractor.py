from __future__ import annotations

import re

from analyzers.extractors._helpers import infer_service_id
from analyzers.file_index import FileIndex
from bottlenecks.evidence import EvidenceRegistry
from bottlenecks.models import FileIoSignal, RouteSignal
from bottlenecks.signals.code_signal_extractor import route_lookup

_FILE_IO_PATTERNS: list[tuple[str, bool, re.Pattern]] = [
    ("readFileSync", True, re.compile(r"\breadFileSync\b|\bwriteFileSync\b", re.IGNORECASE)),
    ("fs_stream", False, re.compile(r"\breadFile\b|\bwriteFile\b|createReadStream|createWriteStream", re.IGNORECASE)),
    ("python_open", False, re.compile(r"\bopen\s*\(", re.IGNORECASE)),
    ("python_requests_sync", True, re.compile(r"\brequests\.(get|post|put|delete)\s*\(", re.IGNORECASE)),
    ("subprocess", True, re.compile(r"\bsubprocess\.(run|call)\s*\(", re.IGNORECASE)),
    ("storage_download", False, re.compile(r"\b(download_file|get_object|GetObjectAsync|BlobClient)\b", re.IGNORECASE)),
]


def extract_file_io_calls(
    file_index: FileIndex,
    routes: list[RouteSignal],
    evidence: EvidenceRegistry,
) -> list[FileIoSignal]:
    results: list[FileIoSignal] = []
    counter = 0
    for path in file_index.paths:
        content = file_index.get_content(path) or ""
        lines = content.splitlines()
        component_id = infer_service_id(path)
        for lineno, line in enumerate(lines, start=1):
            matched = None
            sync = False
            for operation, op_sync, pattern in _FILE_IO_PATTERNS:
                if pattern.search(line):
                    matched = operation
                    sync = op_sync
                    break
            if not matched:
                continue
            counter += 1
            ev_id = evidence.ensure(file_path=path, start_line=lineno, end_line=lineno, excerpt=line)
            results.append(FileIoSignal(
                id=f"fileio_{counter:04d}",
                component_id=component_id,
                enclosing_route_id=route_lookup(routes, path, lineno, component_id),
                operation=matched,
                sync=sync,
                file_path=path.replace("\\", "/"),
                start_line=lineno,
                end_line=lineno,
                evidence_id=ev_id,
            ))
    return results
