from __future__ import annotations

import re

from analyzers.extractors._helpers import infer_service_id
from analyzers.file_index import FileIndex
from bottlenecks.evidence import EvidenceRegistry, path_is_test_only
from bottlenecks.models import CpuCallSignal, LoopSignal, RouteSignal

_LOOP_PATTERNS: dict[str, re.Pattern] = {
    ".py": re.compile(r"^\s*(for|while)\s+"),
    ".js": re.compile(r"\b(for|while)\s*[\(\s]"),
    ".ts": re.compile(r"\b(for|while)\s*[\(\s]"),
    ".jsx": re.compile(r"\b(for|while)\s*[\(\s]"),
    ".tsx": re.compile(r"\b(for|while)\s*[\(\s]"),
    ".java": re.compile(r"\b(for|while)\s*\("),
    ".cs": re.compile(r"\b(for|foreach|while)\s*\("),
}

_CPU_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("bcrypt", re.compile(r"\bbcrypt\.(hash|compare)|BCrypt\.", re.IGNORECASE)),
    ("crypto", re.compile(r"\bcrypto\b|SHA256|SHA512|PBKDF2|Argon2", re.IGNORECASE)),
    ("image_processing", re.compile(r"\bsharp\(|PIL\.|ImageMagick|SkiaSharp|opencv", re.IGNORECASE)),
    ("pdf_generation", re.compile(r"\bpdf\b|PdfDocument|wkhtml|reportlab|itext", re.IGNORECASE)),
    ("excel_export", re.compile(r"\bopenpyxl\b|xlsxwriter|EPPlus|ClosedXML", re.IGNORECASE)),
    ("compression", re.compile(r"\bgzip\b|brotli|zipfile|tarfile|Compress-", re.IGNORECASE)),
    ("ml_inference", re.compile(r"\btransformers\b|torch\.|onnxruntime|sentence_transformers", re.IGNORECASE)),
]


def route_lookup(routes: list[RouteSignal], file_path: str, lineno: int | None, component_id: str) -> str | None:
    file_path = file_path.replace("\\", "/")
    same_file = [route for route in routes if route.file_path == file_path and route.component_id == component_id]
    if not same_file:
        same_file = [route for route in routes if route.component_id == component_id]
    if not same_file:
        return None
    if len(same_file) == 1 or lineno is None:
        return same_file[0].id
    return min(
        same_file,
        key=lambda route: abs((route.start_line or lineno) - lineno),
    ).id


def extract_loops(
    file_index: FileIndex,
    analysis_id: str,
    routes: list[RouteSignal],
    evidence: EvidenceRegistry,
) -> list[LoopSignal]:
    loops: list[LoopSignal] = []
    counter = 0
    for path in file_index.paths:
        ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
        pattern = _LOOP_PATTERNS.get(ext)
        if not pattern:
            continue
        content = file_index.get_content(path) or ""
        lines = content.splitlines()
        component_id = infer_service_id(path)
        for lineno, line in enumerate(lines, start=1):
            if not pattern.search(line):
                continue
            counter += 1
            ev_id = evidence.ensure(
                file_path=path,
                start_line=lineno,
                end_line=lineno,
                excerpt=line,
            )
            loops.append(LoopSignal(
                id=f"loop_{counter:04d}",
                component_id=component_id,
                enclosing_route_id=route_lookup(routes, path, lineno, component_id),
                file_path=path.replace("\\", "/"),
                start_line=lineno,
                end_line=min(lineno + 12, len(lines)),
                evidence_id=ev_id,
            ))
    return loops


def extract_cpu_calls(
    file_index: FileIndex,
    routes: list[RouteSignal],
    evidence: EvidenceRegistry,
) -> list[CpuCallSignal]:
    signals: list[CpuCallSignal] = []
    counter = 0
    for path in file_index.paths:
        content = file_index.get_content(path) or ""
        lines = content.splitlines()
        component_id = infer_service_id(path)
        for lineno, line in enumerate(lines, start=1):
            for operation, pattern in _CPU_PATTERNS:
                if not pattern.search(line):
                    continue
                counter += 1
                ev_id = evidence.ensure(
                    file_path=path,
                    start_line=lineno,
                    end_line=lineno,
                    excerpt=line,
                )
                signals.append(CpuCallSignal(
                    id=f"cpu_{counter:04d}",
                    component_id=component_id,
                    enclosing_route_id=route_lookup(routes, path, lineno, component_id),
                    operation=operation,
                    file_path=path.replace("\\", "/"),
                    start_line=lineno,
                    end_line=lineno,
                    evidence_id=ev_id,
                ))
                break
    return signals


def line_in_loop(file_path: str, lineno: int, loops: list[LoopSignal]) -> str | None:
    file_path = file_path.replace("\\", "/")
    for loop in loops:
        if loop.file_path != file_path:
            continue
        if loop.start_line <= lineno <= loop.end_line:
            return loop.id
    return None


def is_test_path(path: str) -> bool:
    return path_is_test_only(path)
