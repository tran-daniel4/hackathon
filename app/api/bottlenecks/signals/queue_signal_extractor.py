from __future__ import annotations

import re

from analyzers.extractors._helpers import infer_service_id
from analyzers.file_index import FileIndex
from bottlenecks.evidence import EvidenceRegistry
from bottlenecks.models import QueueConfigSignal
from graph.models import GraphFacts

_QUEUE_HINT_RE = re.compile(r"\b(queue|topic|exchange|consumer|worker|bullmq|celery|rabbitmq|sqs|kafka)\b", re.IGNORECASE)
_DLQ_RE = re.compile(r"\b(dlq|dead.?letter|dead_letter)\b", re.IGNORECASE)
_RETRY_RE = re.compile(r"\bretry|retries|max.?retry|attempts\b", re.IGNORECASE)
_BACKOFF_RE = re.compile(r"\bbackoff|delay|exponential\b", re.IGNORECASE)
_CONCURRENCY_RE = re.compile(r"\b(concurrency|prefetch|parallelism)\b", re.IGNORECASE)


def extract_queue_configs(
    file_index: FileIndex,
    facts: GraphFacts,
    evidence: EvidenceRegistry,
) -> list[QueueConfigSignal]:
    signals: list[QueueConfigSignal] = []
    counter = 0
    for message in facts.messaging:
        evidence_id = next((eid for eid in message.evidence_ids if eid), None)
        file_path = ""
        start_line = None
        if evidence_id:
            evidence_item = next((e for e in facts.evidence if e.id == evidence_id), None)
            if evidence_item:
                file_path = evidence_item.file_path
                start_line = evidence_item.start_line
        component_id = message.producer_component_ids[0] if message.producer_component_ids else (message.consumer_component_ids[0] if message.consumer_component_ids else "unknown")
        counter += 1
        signals.append(QueueConfigSignal(
            id=f"queue_{counter:04d}",
            component_id=component_id,
            queue_name=message.name,
            dlq_detected=False,
            retry_detected=False,
            max_retries=None,
            backoff_detected=False,
            concurrency_limit=None,
            prefetch_limit=None,
            file_path=file_path,
            start_line=start_line,
            end_line=start_line,
            evidence_id=evidence_id or "",
        ))

    for path in file_index.paths:
        if not any(token in path.lower() for token in ("queue", "worker", "consumer", "messaging", "rabbit", "kafka", "sqs", "celery", "bull")):
            continue
        content = file_index.get_content(path) or ""
        if not _QUEUE_HINT_RE.search(content):
            continue
        lines = content.splitlines()
        component_id = infer_service_id(path)
        for lineno, line in enumerate(lines, start=1):
            if not _QUEUE_HINT_RE.search(line):
                continue
            counter += 1
            ev_id = evidence.ensure(file_path=path, start_line=lineno, end_line=lineno, excerpt=line)
            signals.append(QueueConfigSignal(
                id=f"queue_{counter:04d}",
                component_id=component_id,
                queue_name=_infer_queue_name(line),
                dlq_detected=bool(_DLQ_RE.search(content)),
                retry_detected=bool(_RETRY_RE.search(content)),
                max_retries=_extract_int(content, ("max_retries", "retries", "attempts")),
                backoff_detected=bool(_BACKOFF_RE.search(content)),
                concurrency_limit=_extract_int(content, ("concurrency", "parallelism")),
                prefetch_limit=_extract_int(content, ("prefetch",)),
                file_path=path.replace("\\", "/"),
                start_line=lineno,
                end_line=lineno,
                evidence_id=ev_id,
            ))
            break
    deduped: dict[tuple[str, str], QueueConfigSignal] = {}
    for signal in signals:
        key = (signal.component_id, signal.queue_name)
        existing = deduped.get(key)
        if not existing:
            deduped[key] = signal
            continue
        deduped[key] = existing.model_copy(update={
            "dlq_detected": existing.dlq_detected or signal.dlq_detected,
            "retry_detected": existing.retry_detected or signal.retry_detected,
            "backoff_detected": existing.backoff_detected or signal.backoff_detected,
            "max_retries": existing.max_retries if existing.max_retries is not None else signal.max_retries,
            "concurrency_limit": existing.concurrency_limit if existing.concurrency_limit is not None else signal.concurrency_limit,
            "prefetch_limit": existing.prefetch_limit if existing.prefetch_limit is not None else signal.prefetch_limit,
            "evidence_id": existing.evidence_id or signal.evidence_id,
            "file_path": existing.file_path or signal.file_path,
            "start_line": existing.start_line or signal.start_line,
            "end_line": existing.end_line or signal.end_line,
        })
    return list(deduped.values())


def _extract_int(content: str, keys: tuple[str, ...]) -> int | None:
    for key in keys:
        match = re.search(rf"{re.escape(key)}[^0-9]{{0,8}}([0-9]+)", content, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _infer_queue_name(line: str) -> str:
    match = re.search(r"['\"]([A-Za-z0-9._:-]{3,})['\"]", line)
    if match:
        return match.group(1)
    return "async-jobs"
