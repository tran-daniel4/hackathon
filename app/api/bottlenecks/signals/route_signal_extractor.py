from __future__ import annotations

import re

from analyzers.file_index import FileIndex
from bottlenecks.evidence import is_public_path, path_is_test_only
from bottlenecks.models import RouteSignal
from graph.models import GraphFacts

_PAGINATION_PATTERNS = [
    re.compile(r"\b(limit|offset|page|pagesize|page_size|cursor|take|skip|first|after)\b", re.IGNORECASE),
]
_AUTH_PATTERNS = [
    re.compile(r"\bauth(_required|enticate|orize)?\b", re.IGNORECASE),
    re.compile(r"\bRequireAuthorization\b|\bAuthorize\b", re.IGNORECASE),
]


def extract_route_signals(file_index: FileIndex, facts: GraphFacts) -> list[RouteSignal]:
    evidence_map = {e.id: e for e in facts.evidence}
    routes: list[RouteSignal] = []
    for api in facts.apis:
        evidence = next((evidence_map[eid] for eid in api.evidence_ids if eid in evidence_map), None)
        if not evidence:
            continue
        content = file_index.get_content(evidence.file_path) or ""
        auth_required = api.auth_required or any(pattern.search(content) for pattern in _AUTH_PATTERNS)
        pagination_params: list[str] = []
        for pattern in _PAGINATION_PATTERNS:
            pagination_params.extend(sorted({match.group(1).lower() for match in pattern.finditer(content)}))
        routes.append(RouteSignal(
            id=api.id,
            component_id=api.component_id,
            method=api.method,
            path=api.path,
            handler_symbol=api.handler,
            file_path=evidence.file_path.replace("\\", "/"),
            start_line=evidence.start_line,
            end_line=evidence.end_line,
            evidence_id=evidence.id,
            auth_required=auth_required,
            request_path=True,
            public_endpoint=is_public_path(api.path),
            background_only=False,
            test_only=path_is_test_only(evidence.file_path),
            pagination_params=list(dict.fromkeys(pagination_params)),
        ))
    return routes
