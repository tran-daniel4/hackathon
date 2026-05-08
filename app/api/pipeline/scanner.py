"""
Repo Scanner — pure Python, no LLM.
Recursively parses a codebase and extracts structured metadata for downstream analysis.
"""
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from analyzers.extractors._helpers import infer_service_name
from pydantic import BaseModel


# ── Output schema ──────────────────────────────────────────────────────────────

class ApiEndpoint(BaseModel):
    method: str
    path: str
    file: str
    line: int


class EnvVarHit(BaseModel):
    name: str
    provider: str
    file: str
    line: int


class HttpCallHit(BaseModel):
    domain: str
    client: str
    file: str
    line: int


class CiCdInfo(BaseModel):
    platform: str
    files: list[str]


class WebhookEndpoint(BaseModel):
    path: str
    provider: str
    file: str
    line: int


class RepoScan(BaseModel):
    services: list[str]
    languages: list[str]
    frameworks: list[str]
    dependency_files: dict[str, str]      # rel_path -> content (capped)
    apis: list[ApiEndpoint]
    databases: list[str]
    external_calls: list[str]
    file_tree: list[str]                  # rel paths of all scanned files
    # Enriched evidence for hybrid LLM view generation (all default to empty)
    env_vars: list[EnvVarHit]             = []
    http_calls: list[HttpCallHit]         = []
    cicd: list[CiCdInfo]                  = []
    webhook_routes: list[WebhookEndpoint] = []
    observability_libs: list[str]         = []
    auth_patterns: list[str]              = []
    infra_content: dict[str, str]         = {}  # rel_path -> first 3 KB
    readme_summary: str                   = ""  # first 600 chars of root README.md prose


# ── Skip / size limits ─────────────────────────────────────────────────────────

_SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".next",
    "dist", "build", ".mypy_cache", ".pytest_cache", "coverage",
    ".idea", ".vscode", "target", "out", ".gradle", ".terraform",
    ".eggs", ".tox", "htmlcov",
}

_SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".pdf", ".zip", ".tar", ".gz", ".whl", ".exe", ".dll", ".so",
    ".pyc", ".class", ".jar", ".war", ".lock", ".bin", ".db",
}

_MAX_FILE_BYTES = 200 * 1024   # 200 KB per file
_MAX_DEP_BYTES  = 5  * 1024    # 5 KB per dependency file stored in output
_MAX_INFRA_BYTES = 3 * 1024    # 3 KB per infra file stored in output


# ── Language detection ─────────────────────────────────────────────────────────

_LANG_MAP: dict[str, str] = {
    ".py": "Python",    ".js": "JavaScript", ".ts": "TypeScript",
    ".jsx": "JavaScript", ".tsx": "TypeScript", ".java": "Java",
    ".go": "Go",        ".rb": "Ruby",       ".php": "PHP",
    ".cs": "C#",        ".rs": "Rust",       ".cpp": "C++",
    ".c": "C",          ".kt": "Kotlin",     ".swift": "Swift",
    ".scala": "Scala",  ".ex": "Elixir",     ".exs": "Elixir",
    ".clj": "Clojure",  ".hs": "Haskell",
}


# ── Framework detection ────────────────────────────────────────────────────────

_FRAMEWORKS: list[tuple[str, list[tuple[str, str]]]] = [
    ("FastAPI",         [("requirements.txt", "fastapi"), ("pyproject.toml", "fastapi")]),
    ("Django",          [("requirements.txt", "django"), ("manage.py", "")]),
    ("Flask",           [("requirements.txt", "flask")]),
    ("Celery",          [("requirements.txt", "celery")]),
    ("LangChain",       [("requirements.txt", "langchain")]),
    ("LangGraph",       [("requirements.txt", "langgraph")]),
    ("Express",         [("package.json", '"express"')]),
    ("Next.js",         [("package.json", '"next"')]),
    ("React",           [("package.json", '"react"')]),
    ("Vue.js",          [("package.json", '"vue"')]),
    ("NestJS",          [("package.json", '"@nestjs/core"')]),
    ("Fastify",         [("package.json", '"fastify"')]),
    ("Angular",         [("package.json", '"@angular/core"')]),
    ("Spring Boot",     [("pom.xml", "spring-boot-starter"), ("build.gradle", "spring-boot")]),
    ("Ruby on Rails",   [("Gemfile", "rails")]),
    ("Laravel",         [("composer.json", '"laravel/framework"')]),
    ("Prisma",          [("package.json", '"prisma"')]),
    ("SQLAlchemy",      [("requirements.txt", "sqlalchemy"), ("pyproject.toml", "sqlalchemy")]),
    ("ASP.NET Core",    [(".csproj", "Microsoft.NET.Sdk.Web"), (".csproj", "Microsoft.AspNetCore"), ("Program.cs", "WebApplication.CreateBuilder")]),
    (".NET Aspire",     [(".csproj", "Aspire.Hosting"), ("AppHost.cs", "DistributedApplication")]),
    ("Entity Framework Core", [(".csproj", "Microsoft.EntityFrameworkCore"), (".csproj", "Npgsql.EntityFrameworkCore")]),
    ("Blazor",          [(".csproj", "Microsoft.AspNetCore.Components.WebAssembly")]),
]


# ── Dependency file names ──────────────────────────────────────────────────────

_DEP_FILENAMES = {
    "requirements.txt", "package.json", "pom.xml", "go.mod",
    "Gemfile", "composer.json", "Cargo.toml", "build.gradle",
    "pyproject.toml", "Pipfile", "Directory.Packages.props",
    "Directory.Build.props", "Directory.Build.targets",
}


# ── Database indicators ────────────────────────────────────────────────────────

_DATABASES: list[tuple[str, list[str]]] = [
    ("PostgreSQL",    ["psycopg2", "asyncpg", "postgresql://", "postgres://", 'provider = "postgresql"', "jdbc:postgresql://", 'sql.open("postgres"']),
    ("MySQL",         ["pymysql", "mysqlclient", "mysql://", "aiomysql", 'provider = "mysql"', "jdbc:mysql://", 'sql.open("mysql"']),
    ("MongoDB",       ["pymongo", "motor", "mongodb://", "mongoose", "spring.data.mongodb", "mongotemplate"]),
    ("SQLite",        ["sqlite3", "sqlite:///", 'provider = "sqlite"', 'sql.open("sqlite']),
    ("Redis",         ["redis://", "aioredis", "import redis", '"redis"', "ioredis", "new redis(", "redis.newclient(", "spring.data.redis", "redistemplate"]),
    ("PostgreSQL",    ["npgsql", "Aspire.Hosting.PostgreSQL"]),
    ("SQL Server",    ["Microsoft.Data.SqlClient", "UseSqlServer", "Aspire.Hosting.SqlServer"]),
    ("SQLite",        ["Microsoft.Data.Sqlite", "UseSqlite"]),
    ("Redis",         ["StackExchange.Redis", "Aspire.Hosting.Redis"]),
    ("Elasticsearch", ["elasticsearch", "from elastic"]),
    ("DynamoDB",      ["dynamodb", "boto3"]),
    ("Cassandra",     ["cassandra-driver", "cassandra"]),
    ("InfluxDB",      ["influxdb"]),
]


# ── External API indicators ────────────────────────────────────────────────────

_EXTERNAL_APIS: list[tuple[str, list[str]]] = [
    ("Stripe",        ["import stripe", "from stripe", '"stripe"']),
    ("Twilio",        ["import twilio", "from twilio", '"twilio"']),
    ("SendGrid",      ["import sendgrid", "from sendgrid", '"@sendgrid"']),
    ("OpenAI",        ["import openai", "from openai", '"openai"']),
    ("Anthropic",     ["import anthropic", "from anthropic", '"@anthropic-ai"']),
    ("AWS SDK",       ["import boto3", "from boto3", '"aws-sdk"', '"@aws-sdk"']),
    ("GitHub API",    ["pygithub", "octokit", '"@octokit"']),
    ("Google APIs",   ["google-cloud", "googleapiclient", '"@google-cloud"']),
    ("Slack",         ["slack_sdk", '"@slack/web-api"']),
    ("PayPal",        ["paypalrestsdk", '"paypal"']),
    ("Plaid",         ["import plaid", '"plaid"']),
    ("Pinecone",      ["import pinecone", '"@pinecone-database"']),
    ("Weaviate",      ["import weaviate", '"weaviate-client"']),
    ("Hugging Face",  ["huggingface_hub", '"@huggingface"']),
    ("Deepgram",      ["deepgram", '"@deepgram"']),
    ("Mailgun",       ["mailgun"]),
    ("Cloudinary",    ["cloudinary"]),
    ("Keycloak",      ["Keycloak", "Keycloak.AuthServices"]),
    ("Azure",         ["Azure.", "Azure.Identity", "Azure.Storage"]),
]


# ── API endpoint patterns ──────────────────────────────────────────────────────

@dataclass
class _ApiPattern:
    extensions: frozenset[str]
    regex: re.Pattern
    method_group: Optional[int]
    path_group: int
    filename_filter: Optional[frozenset[str]] = None


_API_PATTERNS: list[_ApiPattern] = [
    _ApiPattern(
        extensions=frozenset({".py"}),
        regex=re.compile(
            r'@\w+(?:\.\w+)*\.(get|post|put|delete|patch|head|options)\s*\(\s*["\']([^"\']+)["\']',
            re.IGNORECASE,
        ),
        method_group=1,
        path_group=2,
    ),
    _ApiPattern(
        extensions=frozenset({".py"}),
        regex=re.compile(r'^\s*path\s*\(\s*["\']([^"\']+)["\']'),
        method_group=None,
        path_group=1,
        filename_filter=frozenset({"urls.py"}),
    ),
    _ApiPattern(
        extensions=frozenset({".js", ".ts", ".mjs", ".cjs"}),
        regex=re.compile(
            r'(?:app|router|server)\.(get|post|put|delete|patch|head|options)\s*\(\s*["\']([^"\']+)["\']',
            re.IGNORECASE,
        ),
        method_group=1,
        path_group=2,
    ),
    _ApiPattern(
        extensions=frozenset({".cs"}),
        regex=re.compile(
            r'\bMap(Get|Post|Put|Delete|Patch)\s*\(\s*["\']([^"\']+)["\']',
            re.IGNORECASE,
        ),
        method_group=1,
        path_group=2,
    ),
    _ApiPattern(
        extensions=frozenset({".cs"}),
        regex=re.compile(
            r'\[(HttpGet|HttpPost|HttpPut|HttpDelete|HttpPatch|Route)\s*\(\s*["\']([^"\']+)["\']',
            re.IGNORECASE,
        ),
        method_group=1,
        path_group=2,
    ),
]
_FLASK_ROUTE_RE = re.compile(
    r'@(?:\w+\.)?route\s*\(\s*["\']([^"\']+)["\'](?P<rest>[^)]*)\)',
    re.IGNORECASE,
)
_FLASK_METHODS_RE = re.compile(r'methods\s*=\s*\[([^\]]+)\]', re.IGNORECASE)
_NEST_CONTROLLER_RE = re.compile(
    r'@Controller\s*\(\s*(?:["\']([^"\']*)["\']|\{[^}]*path\s*:\s*["\']([^"\']*)["\'][^}]*\})?\s*\)',
    re.IGNORECASE,
)
_NEST_METHOD_RE = re.compile(
    r'@(Get|Post|Put|Delete|Patch|Head|Options|All)\s*\(\s*(?:["\']([^"\']*)["\'])?',
    re.IGNORECASE,
)
_SPRING_CLASS_ROUTE_RE = re.compile(
    r'@RequestMapping\s*\(\s*(?:(?:value|path)\s*=\s*)?["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_SPRING_METHOD_RE = re.compile(
    r'@(?:(Get|Post|Put|Delete|Patch)Mapping|RequestMapping)\s*\(([^)]*)\)',
    re.IGNORECASE,
)


# ── Service detection helpers ──────────────────────────────────────────────────

_CONTAINER_DIRS = {"app", "apps", "application", "applications", "services", "packages", "modules", "microservices"}
_PROJECTISH_NAMES = {"api", "server", "backend", "frontend", "web", "apphost", "service"}
_ENTRY_FILES = {
    "main.py", "app.py", "server.py", "wsgi.py", "asgi.py",
    "index.js", "index.ts", "server.js", "server.ts", "app.js",
    "Main.java", "Application.java", "main.go", "main.rb",
    "Program.cs", "Startup.cs", "AppHost.cs",
}
_SERVICE_MARKER_EXTS = {".csproj", ".fsproj", ".vbproj"}


def _looks_like_project_dir(name: str) -> bool:
    lower = name.lower()
    return (
        "." in name
        or "-" in name
        or "_" in name
        or lower in _PROJECTISH_NAMES
        or lower.endswith(("api", "service", "server", "apphost", "worker"))
    )


# ── Env var provider patterns (new) ───────────────────────────────────────────

_ENV_EXTS = frozenset({".py", ".ts", ".js", ".jsx", ".tsx", ".yml", ".yaml", ".toml"})

_ENV_VAR_PROVIDERS: list[tuple[str, re.Pattern]] = [
    ("Stripe",     re.compile(r'\b(STRIPE_[A-Z_]+)\b')),
    ("Twilio",     re.compile(r'\b(TWILIO_[A-Z_]+)\b')),
    ("SendGrid",   re.compile(r'\b(SENDGRID_[A-Z_]+)\b')),
    ("OpenAI",     re.compile(r'\b(OPENAI_[A-Z_]+)\b')),
    ("Anthropic",  re.compile(r'\b(ANTHROPIC_[A-Z_]+)\b')),
    ("AWS",        re.compile(r'\b(AWS_(?:ACCESS|SECRET|REGION|BUCKET|ACCOUNT)[A-Z_]*)\b')),
    ("GitHub",     re.compile(r'\b(GITHUB_(?:CLIENT|TOKEN|SECRET|APP)[A-Z_]*)\b')),
    ("Google",     re.compile(r'\b(GOOGLE_[A-Z_]+|GCP_[A-Z_]+)\b')),
    ("Auth0",      re.compile(r'\b(AUTH0_[A-Z_]+)\b')),
    ("Okta",       re.compile(r'\b(OKTA_[A-Z_]+)\b')),
    ("Slack",      re.compile(r'\b(SLACK_[A-Z_]+)\b')),
    ("PayPal",     re.compile(r'\b(PAYPAL_[A-Z_]+)\b')),
    ("Plaid",      re.compile(r'\b(PLAID_[A-Z_]+)\b')),
    ("Mailgun",    re.compile(r'\b(MAILGUN_[A-Z_]+)\b')),
    ("Cloudinary", re.compile(r'\b(CLOUDINARY_[A-Z_]+)\b')),
    ("Sentry",     re.compile(r'\b(SENTRY_[A-Z_]+)\b')),
    ("Datadog",    re.compile(r'\b(DD_[A-Z_]+|DATADOG_[A-Z_]+)\b')),
    ("Keycloak",   re.compile(r'\b(KEYCLOAK_[A-Z_]+)\b')),
]

# ── HTTP client call patterns (new) ───────────────────────────────────────────

_HTTP_CALL_RE = re.compile(
    r'(?:httpx|requests|axios|fetch)\s*\.\s*(?:get|post|put|delete|patch)\s*\(\s*["\']'
    r'(https?://([a-zA-Z0-9.-]+))',
    re.I,
)
_BASE_URL_RE = re.compile(
    r'(?:BASE_URL|base_url|API_URL|api_url)\s*[=:]\s*[f"\']+\s*'
    r'(https?://([a-zA-Z0-9.-]+))',
    re.I,
)
_CS_HTTP_CALL_RE = re.compile(
    r'\b(?:Get|Post|Put|Delete|Patch)Async\s*\(\s*["\']'
    r'(https?://([a-zA-Z0-9.-]+))',
    re.I,
)
_JAVA_HTTP_CALL_RE = re.compile(
    r'\b(?:uri|URI\.create|WebClient\.create)\s*\(\s*["\']'
    r'(https?://([a-zA-Z0-9.-]+))',
    re.I,
)
_GO_HTTP_CALL_RE = re.compile(
    r'\b(?:http\.(?:Get|Post)|NewRequest)\s*\([^"\']*["\']'
    r'(https?://([a-zA-Z0-9.-]+))',
    re.I,
)

# ── CI/CD platform detection (new) ────────────────────────────────────────────

_CICD_PATTERNS: list[tuple[str, str]] = [
    ("github_actions", ".github/workflows/"),
    ("gitlab_ci",      ".gitlab-ci.yml"),
    ("jenkins",        "jenkinsfile"),
    ("circleci",       ".circleci/"),
    ("travis",         ".travis.yml"),
    ("azure_devops",   "azure-pipelines.yml"),
]

# ── Webhook path indicators (new) ─────────────────────────────────────────────

_WEBHOOK_PATH_RE = re.compile(
    r'["\']([^"\']*(?:webhook|hook|callback)[^"\']*)["\']',
    re.I,
)
_WEBHOOK_PROVIDERS: dict[str, str] = {
    "stripe":  "Stripe",
    "github":  "GitHub",
    "twilio":  "Twilio",
    "paypal":  "PayPal",
    "shopify": "Shopify",
    "slack":   "Slack",
    "square":  "Square",
}

# ── Observability library indicators (new) ────────────────────────────────────

_OBSERVABILITY: list[tuple[str, list[str]]] = [
    ("opentelemetry",     ["opentelemetry", "from opentelemetry"]),
    ("prometheus-client", ["prometheus_client", "prometheus-client"]),
    ("structlog",         ["import structlog"]),
    ("datadog",           ["ddtrace", "from ddtrace", "import datadog"]),
    ("sentry",            ["import sentry_sdk", '"@sentry/node"', "sentry-sdk"]),
    ("loguru",            ["from loguru"]),
    ("jaeger",            ["jaeger", "opentracing"]),
    ("newrelic",          ["newrelic"]),
    ("opentelemetry-dotnet", ["OpenTelemetry", "AddOpenTelemetry"]),
    ("serilog",             ["Serilog", "UseSerilog"]),
]

# ── Auth pattern indicators (new) ─────────────────────────────────────────────

_AUTH_PATTERNS: list[tuple[str, list[str]]] = [
    ("PyJWT",     ["import jwt", "from jwt import", "pyjwt"]),
    ("next-auth", ["next-auth", "nextauth", '"next-auth"']),
    ("passport",  ['"passport"', "require('passport')"]),
    ("OAuth2",    ["oauth2", "authlib", '"oauth"']),
    ("Auth0",     ['"auth0"', '"@auth0"', "auth0-spa"]),
    ("Okta",      ['"@okta"', "okta-auth-js"]),
    ("Cognito",   ["amazon-cognito", "aws-amplify/auth", "cognito"]),
    ("Keycloak",  ["keycloak"]),
    ("OpenIddict", ["OpenIddict"]),
    ("ASP.NET Identity", ["Microsoft.AspNetCore.Identity", "AddIdentity"]),
    ("JWT bearer", ["AddJwtBearer", "JwtBearerDefaults"]),
]

# ── Infra file names (new) ─────────────────────────────────────────────────────

_INFRA_FILENAMES = frozenset({
    "dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "main.tf", "variables.tf", "outputs.tf",
    "deployment.yaml", "deployment.yml",
    "service.yaml", "service.yml",
    "ingress.yaml", "ingress.yml",
    "chart.yaml",
})


# ── Public API ─────────────────────────────────────────────────────────────────

def scan_repo(root: str | Path) -> RepoScan:
    """Scan *root* and return structured repository metadata. No LLM, no network."""
    root = Path(root).resolve()

    files: dict[Path, str] = {}
    file_tree: list[str] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            d for d in dirnames
            if d not in _SKIP_DIRS and not d.startswith(".")
        ]
        for filename in filenames:
            fpath = Path(dirpath) / filename
            if fpath.suffix.lower() in _SKIP_EXTENSIONS:
                continue
            rel = str(fpath.relative_to(root))
            file_tree.append(rel)
            try:
                if fpath.stat().st_size > _MAX_FILE_BYTES:
                    continue
                files[fpath] = fpath.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                pass

    sorted_tree = sorted(file_tree)
    return RepoScan(
        services=_detect_services(root, files),
        languages=_detect_languages(files),
        frameworks=_detect_frameworks(files),
        dependency_files=_extract_dep_files(root, files),
        apis=_detect_apis(root, files),
        databases=_detect_databases(files),
        external_calls=_detect_external_apis(files),
        file_tree=sorted_tree,
        env_vars=_detect_env_vars(root, files),
        http_calls=_detect_http_calls(root, files),
        cicd=_detect_cicd(sorted_tree),
        webhook_routes=_detect_webhooks(root, files),
        observability_libs=_detect_observability(files),
        auth_patterns=_detect_auth_patterns(files),
        infra_content=_extract_infra_content(files, root),
        readme_summary=_extract_readme_summary(files, root),
    )


def scan_files(uploaded: dict[str, str]) -> RepoScan:
    """
    Like scan_repo but works from browser-uploaded file contents.
    *uploaded* maps webkitRelativePath strings to file text.
    """
    if not uploaded:
        return RepoScan(
            services=[], languages=[], frameworks=[], dependency_files={},
            apis=[], databases=[], external_calls=[], file_tree=[],
        )

    first_key  = next(iter(uploaded)).replace("\\", "/")
    root_name  = first_key.split("/")[0] if "/" in first_key else "repo"
    pseudo_root = Path(root_name)

    files: dict[Path, str] = {}
    for rel_str, content in uploaded.items():
        norm = rel_str.replace("\\", "/")
        if not norm.startswith(root_name + "/"):
            norm = root_name + "/" + norm
        fpath = Path(norm)
        if fpath.suffix.lower() in _SKIP_EXTENSIONS:
            continue
        files[fpath] = content[:_MAX_FILE_BYTES]

    file_tree = sorted(str(p.relative_to(pseudo_root)) for p in files)

    return RepoScan(
        services=_detect_services(pseudo_root, files),
        languages=_detect_languages(files),
        frameworks=_detect_frameworks(files),
        dependency_files=_extract_dep_files(pseudo_root, files),
        apis=_detect_apis(pseudo_root, files),
        databases=_detect_databases(files),
        external_calls=_detect_external_apis(files),
        file_tree=file_tree,
        env_vars=_detect_env_vars(pseudo_root, files),
        http_calls=_detect_http_calls(pseudo_root, files),
        cicd=_detect_cicd(file_tree),
        webhook_routes=_detect_webhooks(pseudo_root, files),
        observability_libs=_detect_observability(files),
        auth_patterns=_detect_auth_patterns(files),
        infra_content=_extract_infra_content(files, pseudo_root),
        readme_summary=_extract_readme_summary(files, pseudo_root),
    )


# ── Detection helpers ──────────────────────────────────────────────────────────

def _detect_languages(files: dict[Path, str]) -> list[str]:
    seen: set[str] = set()
    for path in files:
        lang = _LANG_MAP.get(path.suffix.lower())
        if lang:
            seen.add(lang)
    return sorted(seen)


def _detect_frameworks(files: dict[Path, str]) -> list[str]:
    found: list[str] = []
    for framework, checks in _FRAMEWORKS:
        for filename, needle in checks:
            match = next(
                (
                    content
                    for path, content in files.items()
                    if (
                        (filename.startswith(".") and path.name.endswith(filename))
                        or path.name == filename
                    )
                    and (not needle or needle.lower() in content.lower())
                ),
                None,
            )
            if match is not None:
                found.append(framework)
                break
    return found


def _extract_dep_files(root: Path, files: dict[Path, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for path, content in files.items():
        if path.name in _DEP_FILENAMES or path.suffix.lower() in {".csproj", ".fsproj", ".vbproj"}:
            rel = str(path.relative_to(root))
            result[rel] = content[:_MAX_DEP_BYTES]
    return result


def _detect_services(root: Path, files: dict[Path, str]) -> list[str]:
    services: set[str] = set()
    for path in files:
        rel = path.relative_to(root)
        parts = rel.parts
        if len(parts) >= 2 and parts[0].lower() in _CONTAINER_DIRS:
            services.add(parts[1])
            continue
        if (
            len(parts) >= 2
            and parts[0].lower() in {"src", "source"}
            and _looks_like_project_dir(parts[1])
        ):
            services.add(parts[1])
            continue
        if (
            path.name in _DEP_FILENAMES
            or path.name in _ENTRY_FILES
            or path.suffix.lower() in _SERVICE_MARKER_EXTS
        ):
            services.add(infer_service_name(str(rel)))
    return sorted(services) if services else [root.name]


def _detect_apis(root: Path, files: dict[Path, str]) -> list[ApiEndpoint]:
    endpoints: list[ApiEndpoint] = []
    seen: set[tuple[str, str]] = set()

    for path, content in files.items():
        ext = path.suffix.lower()
        lines = content.splitlines()
        for pat in _API_PATTERNS:
            if ext not in pat.extensions:
                continue
            if pat.filename_filter and path.name not in pat.filename_filter:
                continue
            for lineno, line in enumerate(lines, start=1):
                m = pat.regex.search(line)
                if not m:
                    continue
                raw_path = m.group(pat.path_group).strip()
                api_path = raw_path if raw_path.startswith("/") else f"/{raw_path}"
                method = (
                    _normalize_method(m.group(pat.method_group))
                    if pat.method_group
                    else _infer_method(line)
                )
                key = (method, api_path)
                if key in seen:
                    continue
                seen.add(key)
                endpoints.append(ApiEndpoint(
                    method=method,
                    path=api_path,
                    file=str(path.relative_to(root)),
                    line=lineno,
                ))
        if ext == ".py":
            _detect_flask_apis(root, path, lines, endpoints, seen)
        elif ext == ".ts":
            _detect_nestjs_apis(root, path, lines, endpoints, seen)
        elif ext == ".java":
            _detect_spring_apis(root, path, lines, endpoints, seen)
    return endpoints


def _infer_method(line: str) -> str:
    lower = line.lower()
    for method in ("get", "post", "put", "delete", "patch", "head", "options"):
        if method in lower:
            return method.upper()
    return "ROUTE"


def _normalize_method(method: str) -> str:
    method = method.upper()
    return method[4:] if method.startswith("HTTP") else method


def _join_api_path(prefix: str, suffix: str) -> str:
    prefix = (prefix or "").strip()
    suffix = (suffix or "").strip()
    if not prefix and not suffix:
        return "/"
    segments = [segment.strip("/") for segment in (prefix, suffix) if segment and segment != "/"]
    return "/" + "/".join(segments) if segments else "/"


def _append_endpoint(
    root: Path,
    path: Path,
    lineno: int,
    method: str,
    api_path: str,
    endpoints: list[ApiEndpoint],
    seen: set[tuple[str, str]],
) -> None:
    key = (method, api_path)
    if key in seen:
        return
    seen.add(key)
    endpoints.append(ApiEndpoint(
        method=method,
        path=api_path,
        file=str(path.relative_to(root)),
        line=lineno,
    ))


def _detect_flask_apis(
    root: Path,
    path: Path,
    lines: list[str],
    endpoints: list[ApiEndpoint],
    seen: set[tuple[str, str]],
) -> None:
    for lineno, line in enumerate(lines, start=1):
        match = _FLASK_ROUTE_RE.search(line)
        if not match:
            continue
        methods_match = _FLASK_METHODS_RE.search(match.group("rest") or "")
        methods = ["GET"]
        if methods_match:
            methods = [token.strip(" '\"").upper() for token in methods_match.group(1).split(",") if token.strip()]
        api_path = _join_api_path("", match.group(1))
        for method in methods:
            _append_endpoint(root, path, lineno, method, api_path, endpoints, seen)


def _detect_nestjs_apis(
    root: Path,
    path: Path,
    lines: list[str],
    endpoints: list[ApiEndpoint],
    seen: set[tuple[str, str]],
) -> None:
    controller_prefix = ""
    for lineno, line in enumerate(lines, start=1):
        controller = _NEST_CONTROLLER_RE.search(line)
        if controller:
            controller_prefix = controller.group(1) or controller.group(2) or ""
            continue
        route = _NEST_METHOD_RE.search(line)
        if not route:
            continue
        api_path = _join_api_path(controller_prefix, route.group(2) or "")
        _append_endpoint(root, path, lineno, route.group(1).upper(), api_path, endpoints, seen)


def _extract_spring_path(args: str) -> str:
    value_match = re.search(r'(?:value|path)\s*=\s*["\']([^"\']+)["\']', args, re.IGNORECASE)
    if value_match:
        return value_match.group(1)
    direct_match = re.search(r'["\']([^"\']+)["\']', args)
    return direct_match.group(1) if direct_match else ""


def _extract_spring_method(method_group: str | None, args: str) -> str:
    if method_group:
        return method_group.upper()
    request_method = re.search(r'RequestMethod\.(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)', args, re.IGNORECASE)
    return request_method.group(1).upper() if request_method else "ROUTE"


def _detect_spring_apis(
    root: Path,
    path: Path,
    lines: list[str],
    endpoints: list[ApiEndpoint],
    seen: set[tuple[str, str]],
) -> None:
    class_prefix = ""
    for lineno, line in enumerate(lines, start=1):
        class_route = _SPRING_CLASS_ROUTE_RE.search(line)
        if class_route:
            class_prefix = class_route.group(1) or ""
            continue
        route = _SPRING_METHOD_RE.search(line)
        if not route:
            continue
        args = route.group(2)
        api_path = _join_api_path(class_prefix, _extract_spring_path(args))
        method = _extract_spring_method(route.group(1), args)
        _append_endpoint(root, path, lineno, method, api_path, endpoints, seen)


def _detect_databases(files: dict[Path, str]) -> list[str]:
    corpus = _build_corpus(files)
    seen: set[str] = set()
    results: list[str] = []
    for db, indicators in _DATABASES:
        if db in seen:
            continue
        if any(i.lower() in corpus for i in indicators):
            seen.add(db)
            results.append(db)
    return results


def _detect_external_apis(files: dict[Path, str]) -> list[str]:
    corpus = _build_corpus(files)
    return [api for api, indicators in _EXTERNAL_APIS if any(i in corpus for i in indicators)]


def _build_corpus(files: dict[Path, str]) -> str:
    return "\n".join(files.values()).lower()


# ── New detection helpers ──────────────────────────────────────────────────────

def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.name


def _detect_env_vars(root: Path, files: dict[Path, str]) -> list[EnvVarHit]:
    results: list[EnvVarHit] = []
    seen: set[tuple[str, str]] = set()   # (provider, rel_file)

    for path, content in files.items():
        fname = path.name.lower()
        ext   = path.suffix.lower()
        if not (fname.startswith(".env") or ext in _ENV_EXTS):
            continue
        rel   = _rel(path, root)
        lines = content.splitlines()
        for lineno, line in enumerate(lines, 1):
            for provider, pattern in _ENV_VAR_PROVIDERS:
                m = pattern.search(line)
                if m:
                    key = (provider, rel)
                    if key not in seen:
                        seen.add(key)
                        results.append(EnvVarHit(
                            name=m.group(1), provider=provider,
                            file=rel, line=lineno,
                        ))
    return results


def _detect_http_calls(root: Path, files: dict[Path, str]) -> list[HttpCallHit]:
    results: list[HttpCallHit] = []
    seen: set[str] = set()
    _src = frozenset({".py", ".ts", ".js", ".jsx", ".tsx", ".cs", ".java", ".go"})

    for path, content in files.items():
        if path.suffix.lower() not in _src:
            continue
        lines = content.splitlines()
        for lineno, line in enumerate(lines, 1):
            for pattern in (_HTTP_CALL_RE, _BASE_URL_RE, _CS_HTTP_CALL_RE, _JAVA_HTTP_CALL_RE, _GO_HTTP_CALL_RE):
                m = pattern.search(line)
                if not m:
                    continue
                domain = m.group(2).lower().rstrip(".")
                if not domain or "localhost" in domain or "127.0" in domain or "example.com" in domain:
                    continue
                if domain not in seen:
                    seen.add(domain)
                    low = line.lower()
                    client = (
                        "httpx"    if "httpx"    in low else
                        "requests" if "requests" in low else
                        "axios"    if "axios"    in low else
                        "fetch"    if "fetch"    in low else "http"
                    )
                    results.append(HttpCallHit(
                        domain=domain, client=client,
                        file=_rel(path, root), line=lineno,
                    ))
    return results


def _detect_cicd(file_tree: list[str]) -> list[CiCdInfo]:
    results: list[CiCdInfo] = []
    for platform, pattern in _CICD_PATTERNS:
        matches = [f for f in file_tree if pattern in f.replace("\\", "/").lower()]
        if matches:
            results.append(CiCdInfo(platform=platform, files=matches[:5]))
    return results


def _detect_webhooks(root: Path, files: dict[Path, str]) -> list[WebhookEndpoint]:
    results: list[WebhookEndpoint] = []
    seen: set[str] = set()
    _src = frozenset({".py", ".ts", ".js", ".jsx", ".tsx", ".java"})

    for path, content in files.items():
        if path.suffix.lower() not in _src:
            continue
        rel   = _rel(path, root)
        lines = content.splitlines()
        for lineno, line in enumerate(lines, 1):
            m = _WEBHOOK_PATH_RE.search(line)
            if not m:
                continue
            route_path = m.group(1)
            if route_path in seen:
                continue
            seen.add(route_path)
            provider = "Generic"
            lower_path = route_path.lower()
            for keyword, prov_name in _WEBHOOK_PROVIDERS.items():
                if keyword in lower_path:
                    provider = prov_name
                    break
            results.append(WebhookEndpoint(
                path=route_path, provider=provider,
                file=rel, line=lineno,
            ))
    return results


def _detect_observability(files: dict[Path, str]) -> list[str]:
    corpus = _build_corpus(files)
    return [lib for lib, indicators in _OBSERVABILITY if any(i in corpus for i in indicators)]


def _detect_auth_patterns(files: dict[Path, str]) -> list[str]:
    corpus = _build_corpus(files)
    return [name for name, indicators in _AUTH_PATTERNS if any(i.lower() in corpus for i in indicators)]


def _extract_infra_content(files: dict[Path, str], root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path, content in files.items():
        fname = path.name.lower()
        ext   = path.suffix.lower()
        if fname in _INFRA_FILENAMES or ext in {".tf", ".hcl"}:
            result[_rel(path, root)] = content[:_MAX_INFRA_BYTES]
    return result


def _extract_readme_summary(files: dict[Path, str], root: Path) -> str:
    """Return up to 600 chars of prose from the root-level README.md, stripping headings."""
    for path, content in files.items():
        try:
            rel_parts = path.relative_to(root).parts
        except ValueError:
            continue
        if len(rel_parts) == 1 and rel_parts[0].lower().startswith("readme"):
            lines = [l for l in content.splitlines() if not l.strip().startswith("#")]
            prose = " ".join(" ".join(l.split()) for l in lines if l.strip())
            return prose[:600]
    return ""
