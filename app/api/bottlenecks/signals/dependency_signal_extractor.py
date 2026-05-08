from __future__ import annotations

import re

from analyzers.extractors._helpers import infer_service_id
from analyzers.file_index import FileIndex
from bottlenecks.evidence import EvidenceRegistry
from bottlenecks.models import DependencySignal

_DEPENDENCY_PATTERNS: list[tuple[str, str, re.Pattern]] = [
    ("prisma", "orm", re.compile(r'"prisma"|@prisma/client', re.IGNORECASE)),
    ("sqlalchemy", "orm", re.compile(r"sqlalchemy", re.IGNORECASE)),
    ("entityframework", "orm", re.compile(r"EntityFramework|DbContext", re.IGNORECASE)),
    ("resilience4j", "resilience", re.compile(r"resilience4j", re.IGNORECASE)),
    ("polly", "resilience", re.compile(r"\bPolly\b|WaitAndRetry|CircuitBreaker", re.IGNORECASE)),
    ("opentelemetry", "observability", re.compile(r"opentelemetry|AddOpenTelemetry|OpenTelemetry", re.IGNORECASE)),
    ("sentry", "observability", re.compile(r"sentry", re.IGNORECASE)),
    ("redis", "cache", re.compile(r"\bredis\b|ioredis|StackExchange\.Redis", re.IGNORECASE)),
    ("rabbitmq", "queue", re.compile(r"rabbitmq|amqp|RabbitListener", re.IGNORECASE)),
    ("celery", "queue", re.compile(r"\bcelery\b", re.IGNORECASE)),
    ("kafka", "queue", re.compile(r"\bkafka\b", re.IGNORECASE)),
    ("auth0", "identity", re.compile(r"auth0", re.IGNORECASE)),
]


def extract_dependency_signals(file_index: FileIndex, evidence: EvidenceRegistry) -> list[DependencySignal]:
    results: list[DependencySignal] = []
    counter = 0
    for path in file_index.paths:
        base = path.rsplit("/", 1)[-1].lower()
        if base not in {"package.json", "requirements.txt", "pyproject.toml", "pom.xml", "build.gradle", "build.gradle.kts", "csproj", "go.mod", "gemfile", "composer.json"} and not base.endswith((".csproj", ".props", ".targets")):
            continue
        content = file_index.get_content(path) or ""
        lines = content.splitlines()
        component_id = infer_service_id(path)
        for lineno, line in enumerate(lines, start=1):
            for name, category, pattern in _DEPENDENCY_PATTERNS:
                if not pattern.search(line):
                    continue
                counter += 1
                ev_id = evidence.ensure(file_path=path, start_line=lineno, end_line=lineno, excerpt=line, kind="manifest")
                results.append(DependencySignal(
                    id=f"dep_{counter:04d}",
                    component_id=component_id,
                    name=name,
                    category=category,
                    file_path=path.replace("\\", "/"),
                    start_line=lineno,
                    end_line=lineno,
                    evidence_id=ev_id,
                ))
                break
    return results
