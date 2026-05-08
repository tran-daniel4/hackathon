from __future__ import annotations

import re

from analyzers.extractors._helpers import infer_service_id
from analyzers.file_index import FileIndex
from bottlenecks.evidence import EvidenceRegistry
from bottlenecks.models import HttpCallSignal, RouteSignal
from bottlenecks.signals.code_signal_extractor import route_lookup

_CALL_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("httpx", re.compile(r"httpx\.(get|post|put|delete|patch)\s*\(", re.IGNORECASE)),
    ("requests", re.compile(r"requests\.(get|post|put|delete|patch)\s*\(", re.IGNORECASE)),
    ("axios", re.compile(r"axios\.(get|post|put|delete|patch)\s*\(", re.IGNORECASE)),
    ("fetch", re.compile(r"\bfetch\s*\(", re.IGNORECASE)),
    ("csharp_http", re.compile(r"\b(?:Get|Post|Put|Delete|Patch)Async\s*\(", re.IGNORECASE)),
    ("java_http", re.compile(r"\b(WebClient|RestTemplate|HttpClient)\b", re.IGNORECASE)),
    ("go_http", re.compile(r"\bhttp\.(Get|Post|NewRequest)\s*\(", re.IGNORECASE)),
]
_TARGET_HINT_RE = re.compile(r"https?://([a-zA-Z0-9.-]+)", re.IGNORECASE)
_TIMEOUT_RE = re.compile(r"\btimeout\b|AbortController|WithTimeout|callTimeout|readTimeout|writeTimeout", re.IGNORECASE)
_RETRY_RE = re.compile(r"\bretry\b|backoff|tenacity|resilience4j|Polly|RetryPolicy|WaitAndRetry", re.IGNORECASE)
_CIRCUIT_BREAKER_RE = re.compile(r"circuit.?breaker|resilience4j|Polly|opossum|cockatiel|fallback", re.IGNORECASE)


def extract_http_calls(
    file_index: FileIndex,
    routes: list[RouteSignal],
    evidence: EvidenceRegistry,
) -> list[HttpCallSignal]:
    results: list[HttpCallSignal] = []
    counter = 0
    for path in file_index.paths:
        content = file_index.get_content(path) or ""
        lines = content.splitlines()
        component_id = infer_service_id(path)
        for lineno, line in enumerate(lines, start=1):
            matched_client = None
            method = None
            for client, pattern in _CALL_PATTERNS:
                match = pattern.search(line)
                if not match:
                    continue
                matched_client = client
                if match.lastindex:
                    method = match.group(1).upper()
                break
            if not matched_client:
                continue
            window = "\n".join(lines[max(0, lineno - 3): min(len(lines), lineno + 4)])
            target_match = _TARGET_HINT_RE.search(window)
            target_hint = (target_match.group(1) if target_match else "external-service").lower()
            counter += 1
            ev_id = evidence.ensure(
                file_path=path,
                start_line=lineno,
                end_line=lineno,
                excerpt=line,
            )
            results.append(HttpCallSignal(
                id=f"http_{counter:04d}",
                component_id=component_id,
                enclosing_route_id=route_lookup(routes, path, lineno, component_id),
                target_hint=target_hint,
                client=matched_client,
                method=method,
                timeout_detected=bool(_TIMEOUT_RE.search(window)),
                retry_detected=bool(_RETRY_RE.search(window)),
                circuit_breaker_detected=bool(_CIRCUIT_BREAKER_RE.search(window)),
                file_path=path.replace("\\", "/"),
                start_line=lineno,
                end_line=lineno,
                evidence_id=ev_id,
                external_provider=target_hint not in {"localhost", "127.0.0.1", "0.0.0.0"},
            ))
    return results
