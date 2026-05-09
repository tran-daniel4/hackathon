from __future__ import annotations

import re

from graph.models import Evidence, GraphFacts


class EvidenceRegistry:
    def __init__(self, facts: GraphFacts):
        self.facts = facts
        self._by_span: dict[tuple[str, int | None, int | None, str], str] = {}
        self._next_index = len(facts.evidence) + 1
        for evidence in facts.evidence:
            key = (
                evidence.file_path.replace("\\", "/"),
                evidence.start_line,
                evidence.end_line,
                evidence.excerpt,
            )
            self._by_span[key] = evidence.id

    def ensure(
        self,
        *,
        file_path: str,
        start_line: int | None,
        end_line: int | None,
        excerpt: str,
        kind: str = "code_reference",
        symbol: str | None = None,
    ) -> str:
        normalized_excerpt = excerpt.strip()[:240]
        key = (file_path.replace("\\", "/"), start_line, end_line, normalized_excerpt)
        existing = self._by_span.get(key)
        if existing:
            return existing
        evidence_id = f"ev_{self._next_index:03d}"
        self._next_index += 1
        self.facts.evidence.append(Evidence(
            id=evidence_id,
            kind=kind,  # type: ignore[arg-type]
            file_path=file_path.replace("\\", "/"),
            start_line=start_line,
            end_line=end_line,
            symbol=symbol,
            excerpt=normalized_excerpt,
        ))
        self._by_span[key] = evidence_id
        return evidence_id


def build_evidence_snippets(
    facts: GraphFacts,
    evidence_ids: list[str],
    *,
    max_items: int = 8,
    max_excerpt_chars: int = 240,
) -> list[dict]:
    evidence_map = {e.id: e for e in facts.evidence}
    snippets: list[dict] = []
    for evidence_id in evidence_ids[:max_items]:
        evidence = evidence_map.get(evidence_id)
        if not evidence:
            continue
        snippets.append({
            "evidence_id": evidence.id,
            "file_path": evidence.file_path,
            "start_line": evidence.start_line,
            "end_line": evidence.end_line,
            "excerpt": evidence.excerpt[:max_excerpt_chars],
        })
    return snippets


def path_is_test_only(file_path: str) -> bool:
    lowered = file_path.replace("\\", "/").lower()
    return any(token in lowered for token in (
        "/test/", "/tests/", "/spec/", "/specs/", "__tests__", ".spec.", ".test.", "/fixtures/", "/examples/", "/demo/",
    ))


def is_collection_path(path: str) -> bool:
    lowered = path.lower()
    if "{" in lowered or ":" in lowered:
        return False
    parts = [part for part in lowered.strip("/").split("/") if part and part not in {"api", "v1", "v2", "v3"}]
    if not parts:
        return False
    last = parts[-1]
    return last.endswith("s") or last in {"search", "list", "items", "results", "catalog"}


def is_public_path(path: str) -> bool:
    lowered = path.lower()
    return not any(token in lowered for token in ("/internal", "/admin", "/private"))


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
