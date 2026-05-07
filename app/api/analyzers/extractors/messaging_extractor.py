import re

from analyzers.base import Analyzer
from analyzers.file_index import FileIndex
from analyzers.extractors._helpers import ev_tmp, file_basename, infer_service_id
from graph.models import GraphFactPatch, NodeFact, EdgeFact, MessagingFact, Evidence, WarningFact, make_node_id


_SRC_EXTS = frozenset({".py", ".ts", ".js", ".jsx", ".tsx"})
_DEP_NAMES = {"requirements.txt", "package.json", "Pipfile", "pyproject.toml"}

_MESSAGING_IMPORTS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"confluent_kafka",
        r"aiokafka",
        r"from kafka import",
        r"kafkajs",
        r"new Kafka\s*\(",
        r"import pika",
        r"celery",
        r"bullmq",
        r"new Queue\s*\(",
        r"new Worker\s*\(",
        r"boto3\.client\s*\(\s*['\"]sqs",
        r"SQSClient\s*\(",
    ]
]

# Kafka producer patterns
_KAFKA_PRODUCE_RE = re.compile(
    r'\.produce\s*\(\s*["\']([^"\']+)["\']|\.send\s*\(\s*\{\s*topic\s*:\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)
# Kafka consumer patterns
_KAFKA_CONSUME_RE = re.compile(
    r'Consumer\s*\(\s*\[?\s*["\']([^"\']+)["\']|\.subscribe\s*\(\s*\{\s*topics?\s*:\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)
# Celery task definitions
_CELERY_TASK_RE = re.compile(r'@(?:app|celery)\.task', re.IGNORECASE)
_CELERY_CALL_RE = re.compile(r'(\w+)\.(?:delay|apply_async)\s*\(', re.IGNORECASE)
# BullMQ
_BULL_QUEUE_RE = re.compile(r'new Queue\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE)
_BULL_WORKER_RE = re.compile(r'new Worker\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE)
# RabbitMQ
_RABBIT_PUBLISH_RE = re.compile(r'channel\.basic_publish\s*\(', re.IGNORECASE)
_RABBIT_CONSUME_RE = re.compile(r'channel\.basic_consume\s*\(', re.IGNORECASE)
# SQS
_SQS_SEND_RE = re.compile(r'sqs\.send_message\s*\(|\.sendMessage\s*\(', re.IGNORECASE)
_SQS_RECEIVE_RE = re.compile(r'sqs\.receive_message\s*\(|\.receiveMessage\s*\(', re.IGNORECASE)

_LITERAL_STR_RE = re.compile(r'^["\']')


def _is_literal(s: str) -> bool:
    return bool(s) and s[0] in ('"', "'")


class MessagingExtractor(Analyzer):
    def supports(self, file_index: FileIndex) -> bool:
        for p in file_index.paths:
            if file_basename(p) in _DEP_NAMES:
                content = file_index.get_content(p) or ""
                if any(rx.search(content) for rx in _MESSAGING_IMPORTS):
                    return True
            ext = ("." + p.rsplit(".", 1)[-1].lower()) if "." in file_basename(p) else ""
            if ext in _SRC_EXTS:
                content = file_index.get_content(p) or ""
                if any(rx.search(content) for rx in _MESSAGING_IMPORTS):
                    return True
        return False

    def analyze(self, file_index: FileIndex) -> GraphFactPatch:
        patch = GraphFactPatch()
        emitted_nodes: set[str] = set()
        # topic → {producers: set, consumers: set, evidence_ids: list}
        topic_meta: dict[str, dict] = {}
        msg_counter = 0

        def _ensure_topic(name: str, node_type: str = "topic") -> str:
            node_id = make_node_id(name)
            if node_id not in emitted_nodes:
                emitted_nodes.add(node_id)
                patch.nodes.append(NodeFact(
                    id=node_id,
                    type=node_type,  # type: ignore[arg-type]
                    name=name,
                    tags=["messaging"],
                    confidence="inferred",
                ))
            if node_id not in topic_meta:
                topic_meta[node_id] = {"producers": set(), "consumers": set(), "evidence_ids": []}
            return node_id

        for path in file_index.paths:
            base = file_basename(path)
            ext = ("." + base.rsplit(".", 1)[-1].lower()) if "." in base else ""
            if ext not in _SRC_EXTS:
                continue

            content = file_index.get_content(path) or ""
            if not any(rx.search(content) for rx in _MESSAGING_IMPORTS):
                continue

            svc_id = infer_service_id(path)
            lines = content.splitlines()

            for lineno, line in enumerate(lines, start=1):
                ev_id = None

                def _mk_ev() -> str:
                    nonlocal ev_id
                    if ev_id is None:
                        ev_id = ev_tmp()
                        patch.evidence.append(Evidence(
                            id=ev_id,
                            kind="code_reference",
                            file_path=path,
                            start_line=lineno,
                            end_line=lineno,
                            excerpt=line.strip()[:120],
                        ))
                    return ev_id

                # Kafka producer
                m = _KAFKA_PRODUCE_RE.search(line)
                if m:
                    topic_name = m.group(1) or m.group(2) or "unknown-topic"
                    if not topic_name or not topic_name[0].isalpha():
                        patch.warnings.append(WarningFact(
                            code="DYNAMIC_TOPIC_NAME",
                            message=f"Dynamic topic name in {path}:{lineno}",
                            file_path=path,
                        ))
                        continue
                    tid = _ensure_topic(topic_name, "topic")
                    topic_meta[tid]["producers"].add(svc_id)
                    topic_meta[tid]["evidence_ids"].append(_mk_ev())
                    continue

                # Kafka consumer
                m = _KAFKA_CONSUME_RE.search(line)
                if m:
                    topic_name = m.group(1) or m.group(2) or "unknown-topic"
                    if not topic_name or not topic_name[0].isalpha():
                        continue
                    tid = _ensure_topic(topic_name, "topic")
                    topic_meta[tid]["consumers"].add(svc_id)
                    topic_meta[tid]["evidence_ids"].append(_mk_ev())
                    continue

                # BullMQ Queue
                m = _BULL_QUEUE_RE.search(line)
                if m:
                    qname = m.group(1)
                    tid = _ensure_topic(qname, "queue")
                    topic_meta[tid]["producers"].add(svc_id)
                    topic_meta[tid]["evidence_ids"].append(_mk_ev())
                    continue

                # BullMQ Worker
                m = _BULL_WORKER_RE.search(line)
                if m:
                    qname = m.group(1)
                    tid = _ensure_topic(qname, "queue")
                    topic_meta[tid]["consumers"].add(svc_id)
                    topic_meta[tid]["evidence_ids"].append(_mk_ev())
                    continue

                # RabbitMQ
                if _RABBIT_PUBLISH_RE.search(line):
                    tid = _ensure_topic("rabbitmq-exchange", "queue")
                    topic_meta[tid]["producers"].add(svc_id)
                    topic_meta[tid]["evidence_ids"].append(_mk_ev())
                    continue
                if _RABBIT_CONSUME_RE.search(line):
                    tid = _ensure_topic("rabbitmq-exchange", "queue")
                    topic_meta[tid]["consumers"].add(svc_id)
                    topic_meta[tid]["evidence_ids"].append(_mk_ev())
                    continue

                # SQS
                if _SQS_SEND_RE.search(line):
                    tid = _ensure_topic("sqs-queue", "queue")
                    topic_meta[tid]["producers"].add(svc_id)
                    topic_meta[tid]["evidence_ids"].append(_mk_ev())
                    continue
                if _SQS_RECEIVE_RE.search(line):
                    tid = _ensure_topic("sqs-queue", "queue")
                    topic_meta[tid]["consumers"].add(svc_id)
                    topic_meta[tid]["evidence_ids"].append(_mk_ev())
                    continue

                # Celery tasks (no topic name, just mark the service)
                if _CELERY_TASK_RE.search(line) or _CELERY_CALL_RE.search(line):
                    tid = _ensure_topic("celery-tasks", "queue")
                    topic_meta[tid]["producers"].add(svc_id)
                    topic_meta[tid]["evidence_ids"].append(_mk_ev())

        # Build MessagingFact and edges for each topic
        for topic_id, meta in topic_meta.items():
            msg_counter += 1
            producers = list(meta["producers"])
            consumers = list(meta["consumers"])
            ev_ids = meta["evidence_ids"]
            topic_node = next((n for n in patch.nodes if n.id == topic_id), None)
            topic_name = topic_node.name if topic_node else topic_id

            patch.messaging.append(MessagingFact(
                id=f"msg_{msg_counter:03d}",
                type="topic" if (topic_node and topic_node.type == "topic") else "queue",
                name=topic_name,
                producer_component_ids=producers,
                consumer_component_ids=consumers,
                evidence_ids=ev_ids,
            ))

            for svc_id in producers:
                patch.edges.append(EdgeFact(
                    id=f"edge-{svc_id}-{topic_id}-pubsub",
                    src=svc_id,
                    dst=topic_id,
                    kind="pubsub",
                    direction="outbound",
                    confidence="inferred",
                    evidence_ids=ev_ids[:1],
                ))
            for svc_id in consumers:
                patch.edges.append(EdgeFact(
                    id=f"edge-{topic_id}-{svc_id}-pubsub",
                    src=topic_id,
                    dst=svc_id,
                    kind="pubsub",
                    direction="inbound",
                    confidence="inferred",
                    evidence_ids=ev_ids[:1],
                ))

        return patch
