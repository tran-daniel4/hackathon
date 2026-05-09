import re

from analyzers.base import Analyzer
from analyzers.file_index import FileIndex
from analyzers.extractors._helpers import ev_tmp, file_basename, infer_service_id
from graph.models import GraphFactPatch, NodeFact, EdgeFact, Evidence, make_node_id


_SRC_EXTS = frozenset({".py", ".ts", ".js", ".jsx", ".tsx", ".java", ".go", ".cs", ".rb", ".yml", ".yaml", ".json", ".toml", ".properties"})
_DEP_NAMES = {"requirements.txt", "package.json", "Pipfile", "pyproject.toml", "Directory.Packages.props"}
_LOCK_NAMES = {"package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb", "poetry.lock", "uv.lock"}
_CONFIG_NAMES = {
    "application.yml",
    "application.yaml",
    "application.properties",
    "appsettings.json",
    "appsettings.development.json",
    "appsettings.production.json",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
}

# (db_name, [pattern_strings])
_DB_PATTERNS: list[tuple[str, list[str]]] = [
    ("PostgreSQL", [
        r"create_engine\s*\(\s*['\"]postgresql",
        r"asyncpg\.connect\s*\(",
        r"psycopg2\.connect\s*\(",
        r"pg\.Pool\s*\(",
        r"new\s+Pool\s*\(",
        r'provider\s*=\s*["\']postgresql["\']',
        r"jdbc:postgresql://",
        r'sql\.Open\s*\(\s*["\']postgres["\']',
        r"postgresql://",
        r"postgres://",
        r"\bNpgsql\b",
        r"UseNpgsql\s*\(",
        r"Aspire\.Hosting\.PostgreSQL",
    ]),
    ("SQL Server", [
        r"Microsoft\.Data\.SqlClient",
        r"UseSqlServer\s*\(",
        r"jdbc:sqlserver://",
        r"Aspire\.Hosting\.SqlServer",
    ]),
    ("MySQL", [
        r"pymysql\.connect\s*\(",
        r"aiomysql\.connect\s*\(",
        r"mysql\.createConnection\s*\(",
        r"mysql2\.createConnection\s*\(",
        r'provider\s*=\s*["\']mysql["\']',
        r"jdbc:mysql://",
        r'sql\.Open\s*\(\s*["\']mysql["\']',
        r"mysql://",
    ]),
    ("MongoDB", [
        r"pymongo\.MongoClient\s*\(",
        r"MongoClient\s*\(",
        r"motor_asyncio\.AsyncIOMotorClient\s*\(",
        r"mongodb://",
        r"mongoose\.connect\s*\(",
        r"spring\.data\.mongodb",
        r"MongoTemplate",
    ]),
    ("SQLite", [
        r"sqlite3\.connect\s*\(",
        r"sqlite:///",
        r"Microsoft\.Data\.Sqlite",
        r"UseSqlite\s*\(",
        r'provider\s*=\s*["\']sqlite["\']',
        r'sql\.Open\s*\(\s*["\']sqlite3?["\']',
    ]),
    ("Redis", [
        r"\bioredis\b",
        r"new\s+Redis\s*\(",
        r"redis\.NewClient\s*\(",
        r"spring\.data\.redis",
        r"RedisTemplate",
    ]),
    ("Elasticsearch", [
        r"elasticsearch\.Elasticsearch\s*\(",
        r"from elasticsearch import",
        r"new Client\s*\(\s*\{[^}]*node",
    ]),
    ("DynamoDB", [
        r"boto3\.resource\s*\(\s*['\"]dynamodb",
        r"boto3\.client\s*\(\s*['\"]dynamodb",
        r"DynamoDBClient\s*\(",
    ]),
    ("Cassandra", [
        r"cassandra\.cluster\.Cluster\s*\(",
        r"from cassandra",
    ]),
    ("InfluxDB", [
        r"InfluxDBClient\s*\(",
        r"from influxdb",
    ]),
]


def _looks_like_pattern_definition(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith(("r\"", "r'")):
        return True
    if stripped.startswith('("') and "[" in stripped:
        return True
    quote_count = stripped.count('"') + stripped.count("'")
    if quote_count >= 4 and any(token in stripped for token in ("{", "[", "],", "},")):
        return True
    return bool(re.match(r'^\(?["\'][^"\']+["\']\s*,?\s*$', stripped))


class DatastoreExtractor(Analyzer):
    def supports(self, file_index: FileIndex) -> bool:
        return any(
            ("." + p.rsplit(".", 1)[-1].lower()) in _SRC_EXTS
            for p in file_index.paths
            if "." in file_basename(p)
        )

    def analyze(self, file_index: FileIndex) -> GraphFactPatch:
        patch = GraphFactPatch()
        emitted_db_nodes: set[str] = set()
        emitted_edges: set[tuple[str, str]] = set()

        compiled = [(db, [re.compile(p, re.IGNORECASE) for p in patterns])
                    for db, patterns in _DB_PATTERNS]

        for path in file_index.paths:
            base = file_basename(path)
            ext = ("." + base.rsplit(".", 1)[-1].lower()) if "." in base else ""
            if not _should_scan_file(base, ext):
                continue

            content = file_index.get_content(path) or ""
            lines = content.splitlines()

            for lineno, line in enumerate(lines, start=1):
                if _looks_like_pattern_definition(line):
                    continue
                for db_name, patterns in compiled:
                    if not any(rx.search(line) for rx in patterns):
                        continue

                    db_id = make_node_id(db_name)
                    svc_id = infer_service_id(path)
                    edge_key = (svc_id, db_id)

                    ev_id = ev_tmp()
                    patch.evidence.append(Evidence(
                        id=ev_id,
                        kind="code_reference",
                        file_path=path,
                        start_line=lineno,
                        end_line=lineno,
                        excerpt=line.strip()[:120],
                    ))

                    if db_id not in emitted_db_nodes:
                        emitted_db_nodes.add(db_id)
                        patch.nodes.append(NodeFact(
                            id=db_id,
                            type="database",
                            name=db_name,
                            tags=["datastore"],
                            confidence="verified",
                            evidence_ids=[ev_id],
                        ))

                    if edge_key not in emitted_edges:
                        emitted_edges.add(edge_key)
                        patch.edges.append(EdgeFact(
                            id=f"edge-{svc_id}-{db_id}-write",
                            src=svc_id,
                            dst=db_id,
                            kind="write",
                            confidence="inferred",
                            evidence_ids=[ev_id],
                        ))
                    break  # only match first DB pattern per line

        return patch


def _is_template_env_file(filename: str) -> bool:
    lower = filename.lower()
    return lower.startswith(".env.") and any(marker in lower for marker in ("example", "sample", "template"))


def _should_scan_file(base: str, ext: str) -> bool:
    lower = base.lower()
    if lower in _LOCK_NAMES or _is_template_env_file(lower):
        return False
    if lower in _DEP_NAMES or ext in {".csproj", ".fsproj", ".vbproj"}:
        return False
    if lower.startswith(".env"):
        return True
    if lower in _CONFIG_NAMES:
        return True
    return ext in {".py", ".ts", ".js", ".jsx", ".tsx", ".java", ".go", ".cs", ".rb"}
