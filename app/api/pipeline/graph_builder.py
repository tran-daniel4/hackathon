"""
Architecture Graph Builder — pure Python, no LLM.
Converts RepoScan output into a directed architecture graph (nodes + edges).
"""
import re
from typing import Literal

from pydantic import BaseModel

from pipeline.scanner import RepoScan


# ── Output schema ──────────────────────────────────────────────────────────────

NodeType = Literal["service", "database", "cache", "external_api", "queue", "frontend"]
EdgeType = Literal["reads/writes", "caches", "calls", "http", "publishes", "consumes"]


class Node(BaseModel):
    id: str
    label: str
    type: NodeType
    metadata: dict = {}


class Edge(BaseModel):
    source: str
    target: str
    type: EdgeType
    label: str = ""
    confidence: Literal["verified", "inferred"] = "verified"
    evidence: dict = {}


class ArchGraph(BaseModel):
    nodes: list[Node]
    edges: list[Edge]


# ── Classification tables ──────────────────────────────────────────────────────

_CACHE_DBS       = {"Redis", "Memcached"}
_FRONTEND_FWS    = {"React", "Next.js", "Vue.js", "Angular", "Nuxt.js", "Svelte", "Blazor"}
_BACKEND_FWS     = {"FastAPI", "Django", "Flask", "Express", "NestJS", "Fastify",
                     "Spring Boot", "Ruby on Rails", "Laravel", "ASP.NET Core", ".NET Aspire"}
_QUEUE_FWS       = {"Celery", "RabbitMQ", "Kafka"}

# Used to assign per-service edges in multi-service repos from dep file contents
_DB_DEP_INDICATORS: dict[str, list[str]] = {
    "PostgreSQL":    ["psycopg2", "asyncpg", "postgresql", "pg"],
    "SQL Server":    ["sqlclient", "usesqlserver"],
    "MySQL":         ["pymysql", "mysqlclient", "mysql", "mysql2"],
    "MongoDB":       ["pymongo", "motor", "mongodb", "mongoose"],
    "SQLite":        ["sqlite3", "sqlite"],
    "Elasticsearch": ["elasticsearch"],
    "DynamoDB":      ["dynamodb", "boto3"],
    "Cassandra":     ["cassandra"],
    "InfluxDB":      ["influxdb"],
}

_CACHE_DEP_INDICATORS: dict[str, list[str]] = {
    "Redis":       ["redis", "aioredis"],
    "Memcached":   ["memcached", "pylibmc"],
}

_EXT_DEP_INDICATORS: dict[str, list[str]] = {
    "Stripe":        ["stripe"],
    "OpenAI":        ["openai"],
    "Anthropic":     ["anthropic"],
    "AWS SDK":       ["boto3", "aws-sdk", "@aws-sdk"],
    "Twilio":        ["twilio"],
    "SendGrid":      ["sendgrid", "@sendgrid"],
    "GitHub API":    ["pygithub", "octokit", "@octokit"],
    "Google APIs":   ["google-cloud", "googleapiclient", "@google-cloud"],
    "Slack":         ["slack_sdk", "@slack/web-api"],
    "Plaid":         ["plaid"],
    "Pinecone":      ["pinecone", "@pinecone-database"],
    "Weaviate":      ["weaviate", "weaviate-client"],
    "Hugging Face":  ["huggingface_hub", "@huggingface"],
    "Deepgram":      ["deepgram", "@deepgram"],
    "Mailgun":       ["mailgun"],
    "Cloudinary":    ["cloudinary"],
}

# Service directory names that indicate a frontend, not a backend service
_FRONTEND_DIR_NAMES = {"web", "frontend", "client", "ui", "app-web", "fe"}


# ── Public API ─────────────────────────────────────────────────────────────────

def build_graph(scan: RepoScan) -> ArchGraph:
    """
    Convert a RepoScan into an ArchGraph.
    Pure function — no file I/O, no LLM calls.
    """
    nodes: list[Node] = []
    edges: list[Edge] = []

    # Separate databases from caches
    databases = [db for db in scan.databases if db not in _CACHE_DBS]
    caches    = [db for db in scan.databases if db in _CACHE_DBS]

    has_queue    = any(f in _QUEUE_FWS    for f in scan.frameworks)
    has_frontend = any(f in _FRONTEND_FWS for f in scan.frameworks)
    # Split detected services into frontend / backend buckets
    frontend_svcs = [s for s in scan.services if s.lower() in _FRONTEND_DIR_NAMES]
    backend_svcs  = [s for s in scan.services if s.lower() not in _FRONTEND_DIR_NAMES]

    # ── Service nodes ──────────────────────────────────────────────────────────
    backend_ids: list[str] = []
    for svc in backend_svcs:
        nid = _to_id(svc)
        backend_ids.append(nid)
        nodes.append(Node(id=nid, label=svc, type="service"))

    # If no explicit frontend service dir but a frontend framework is present,
    # synthesise a frontend node so the graph shows the full picture.
    frontend_ids: list[str] = []
    if frontend_svcs:
        for svc in frontend_svcs:
            nid = _to_id(svc)
            frontend_ids.append(nid)
            nodes.append(Node(
                id=nid, label=svc, type="frontend",
                metadata={"framework": next((f for f in scan.frameworks if f in _FRONTEND_FWS), "")},
            ))
    elif has_frontend:
        fw = next(f for f in scan.frameworks if f in _FRONTEND_FWS)
        nodes.append(Node(id="frontend", label=fw, type="frontend", metadata={"framework": fw}))
        frontend_ids.append("frontend")

    # ── Database / cache / queue / external nodes ──────────────────────────────
    db_ids: list[str] = []
    for db in databases:
        nid = _to_id(db)
        db_ids.append(nid)
        nodes.append(Node(id=nid, label=db, type="database"))

    cache_ids: list[str] = []
    for cache in caches:
        nid = _to_id(cache)
        cache_ids.append(nid)
        nodes.append(Node(id=nid, label=cache, type="cache"))

    if has_queue:
        fw = next(f for f in scan.frameworks if f in _QUEUE_FWS)
        nodes.append(Node(id="queue", label=fw, type="queue"))

    ext_ids: list[str] = []
    for ext in scan.external_calls:
        nid = _to_id(ext)
        ext_ids.append(nid)
        nodes.append(Node(id=nid, label=ext, type="external_api"))

    # ── Edges: frontend → backend ──────────────────────────────────────────────
    if frontend_ids and backend_ids:
        fe_confidence: Literal["verified", "inferred"] = "verified" if frontend_svcs else "inferred"
        for fid in frontend_ids:
            edges.append(Edge(source=fid, target=backend_ids[0], type="http", label="REST",
                              confidence=fe_confidence))

    # ── Edges: backend → resources ────────────────────────────────────────────
    if len(backend_ids) == 1:
        _connect_single_service(backend_ids[0], db_ids, cache_ids, ext_ids, has_queue, edges)

    elif len(backend_ids) > 1:
        _connect_multi_service(scan, backend_svcs, backend_ids, db_ids, cache_ids, ext_ids, has_queue, edges)

    elif not backend_ids and not frontend_ids and scan.services:
        # Fallback: treat any service as a generic node and connect everything
        sid = _to_id(scan.services[0])
        _connect_single_service(sid, db_ids, cache_ids, ext_ids, has_queue, edges, confidence="inferred")

    return ArchGraph(nodes=nodes, edges=edges)


# ── Edge builders ──────────────────────────────────────────────────────────────

def _connect_single_service(
    svc_id: str,
    db_ids: list[str],
    cache_ids: list[str],
    ext_ids: list[str],
    has_queue: bool,
    edges: list[Edge],
    confidence: Literal["verified", "inferred"] = "verified",
) -> None:
    for db_id in db_ids:
        edges.append(Edge(source=svc_id, target=db_id, type="reads/writes", confidence=confidence))
    for cache_id in cache_ids:
        edges.append(Edge(source=svc_id, target=cache_id, type="caches", confidence=confidence))
    for ext_id in ext_ids:
        edges.append(Edge(source=svc_id, target=ext_id, type="calls", confidence=confidence))
    if has_queue:
        edges.append(Edge(source=svc_id, target="queue", type="publishes", confidence=confidence))


def _connect_multi_service(
    scan: RepoScan,
    svc_names: list[str],
    svc_ids: list[str],
    db_ids: list[str],
    cache_ids: list[str],
    ext_ids: list[str],
    has_queue: bool,
    edges: list[Edge],
) -> None:
    # Build a per-service text corpus from dependency files whose path
    # falls under that service's directory.
    svc_corpus: dict[str, str] = {sid: "" for sid in svc_ids}

    for rel_path, content in scan.dependency_files.items():
        norm = rel_path.replace("\\", "/").lower()
        for svc_name, svc_id in zip(svc_names, svc_ids):
            if norm.startswith(svc_name.lower() + "/") or f"/{svc_name.lower()}/" in norm:
                svc_corpus[svc_id] += content.lower() + "\n"
                break

    has_any_match = False

    for svc_name, svc_id in zip(svc_names, svc_ids):
        corpus = svc_corpus[svc_id]
        if not corpus:
            continue
        has_any_match = True

        for db_name, indicators in _DB_DEP_INDICATORS.items():
            db_id = _to_id(db_name)
            if db_id in db_ids:
                hit = next((ind for ind in indicators if ind in corpus), None)
                if hit:
                    edges.append(Edge(source=svc_id, target=db_id, type="reads/writes",
                                      confidence="verified", evidence={"indicator": hit, "service": svc_name}))

        for cache_name, indicators in _CACHE_DEP_INDICATORS.items():
            cache_id = _to_id(cache_name)
            if cache_id in cache_ids:
                hit = next((ind for ind in indicators if ind in corpus), None)
                if hit:
                    edges.append(Edge(source=svc_id, target=cache_id, type="caches",
                                      confidence="verified", evidence={"indicator": hit, "service": svc_name}))

        for ext_name, indicators in _EXT_DEP_INDICATORS.items():
            ext_id = _to_id(ext_name)
            if ext_id in ext_ids:
                hit = next((ind for ind in indicators if ind in corpus), None)
                if hit:
                    edges.append(Edge(source=svc_id, target=ext_id, type="calls",
                                      confidence="verified", evidence={"indicator": hit, "service": svc_name}))

    # Fallback: if dep files couldn't be matched to any service, share all resources
    if not has_any_match:
        for svc_id in svc_ids:
            _connect_single_service(svc_id, db_ids, cache_ids, ext_ids, False, edges, confidence="inferred")

    if has_queue and svc_ids:
        edges.append(Edge(source=svc_ids[0], target="queue", type="publishes"))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _to_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
