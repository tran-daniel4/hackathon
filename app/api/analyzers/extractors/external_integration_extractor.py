import re

from analyzers.base import Analyzer
from analyzers.file_index import FileIndex
from analyzers.extractors._helpers import ev_tmp, file_basename, infer_service_id
from graph.models import EdgeFact, Evidence, GraphFactPatch, NodeFact, make_node_id


_SRC_EXTS = frozenset({".py", ".ts", ".js", ".jsx", ".tsx", ".mjs", ".cs"})
_DEP_NAMES = {"requirements.txt", "package.json", "Pipfile", "pyproject.toml", "Directory.Packages.props"}
_DEP_EXTS = frozenset({".csproj", ".fsproj", ".vbproj", ".props", ".targets"})

# (name, node_type, [indicator_strings])
_EXTERNAL_APIS: list[tuple[str, str, list[str]]] = [
    ("Stripe", "external_service", ["import stripe", "from stripe", '"stripe"']),
    ("Twilio", "external_service", ["import twilio", "from twilio", '"twilio"']),
    ("SendGrid", "external_service", ["import sendgrid", "from sendgrid", '"@sendgrid"']),
    ("OpenAI", "external_service", ["import openai", "from openai", '"openai"']),
    ("Anthropic", "external_service", ["import anthropic", "from anthropic", '"@anthropic-ai"']),
    ("AWS SDK", "external_service", ["import boto3", "from boto3", '"aws-sdk"', '"@aws-sdk"']),
    ("GitHub API", "external_service", ["pygithub", "octokit", '"@octokit"']),
    ("Google APIs", "external_service", ["google-cloud", "googleapiclient", '"@google-cloud"']),
    ("Slack", "external_service", ["slack_sdk", '"@slack/web-api"']),
    ("PayPal", "external_service", ["paypalrestsdk", '"paypal"']),
    ("Plaid", "external_service", ["import plaid", '"plaid"']),
    ("Pinecone", "external_service", ["import pinecone", '"@pinecone-database"']),
    ("Weaviate", "external_service", ["import weaviate", '"weaviate-client"']),
    ("Hugging Face", "external_service", ["huggingface_hub", '"@huggingface"']),
    ("Deepgram", "external_service", ["deepgram", '"@deepgram"']),
    ("Mailgun", "external_service", ["mailgun"]),
    ("Cloudinary", "external_service", ["cloudinary"]),
    ("Auth0", "auth_provider", ['"auth0"', '"@auth0"', "auth0-spa"]),
    ("Okta", "auth_provider", ['"@okta"', "okta-auth-js"]),
    ("Cognito", "auth_provider", ["amazon-cognito", "aws-amplify/auth", "cognito"]),
    ("Keycloak", "auth_provider", ["keycloak", "Keycloak.AuthServices"]),
    ("Supabase", "auth_provider", ['"@supabase"', "supabase"]),
    ("OpenIddict", "auth_provider", ["OpenIddict"]),
    ("Azure", "external_service", ["Azure.", "Azure.Identity", "Azure.Storage"]),
]

_ENV_VAR_PROVIDERS: list[tuple[str, re.Pattern]] = [
    ("Stripe", re.compile(r"\b(STRIPE_[A-Z_]+)\b")),
    ("Twilio", re.compile(r"\b(TWILIO_[A-Z_]+)\b")),
    ("SendGrid", re.compile(r"\b(SENDGRID_[A-Z_]+)\b")),
    ("OpenAI", re.compile(r"\b(OPENAI_[A-Z_]+)\b")),
    ("Anthropic", re.compile(r"\b(ANTHROPIC_[A-Z_]+)\b")),
    ("AWS SDK", re.compile(r"\b(AWS_(?:ACCESS|SECRET|REGION|BUCKET|ACCOUNT)[A-Z_]*)\b")),
    ("GitHub API", re.compile(r"\b(GITHUB_(?:CLIENT|TOKEN|SECRET|APP)[A-Z_]*)\b")),
    ("Google APIs", re.compile(r"\b(GOOGLE_[A-Z_]+|GCP_[A-Z_]+)\b")),
    ("Auth0", re.compile(r"\b(AUTH0_[A-Z_]+)\b")),
    ("Okta", re.compile(r"\b(OKTA_[A-Z_]+)\b")),
    ("Slack", re.compile(r"\b(SLACK_[A-Z_]+)\b")),
    ("PayPal", re.compile(r"\b(PAYPAL_[A-Z_]+)\b")),
    ("Plaid", re.compile(r"\b(PLAID_[A-Z_]+)\b")),
    ("Mailgun", re.compile(r"\b(MAILGUN_[A-Z_]+)\b")),
    ("Cloudinary", re.compile(r"\b(CLOUDINARY_[A-Z_]+)\b")),
    ("Sentry", re.compile(r"\b(SENTRY_[A-Z_]+)\b")),
    ("Keycloak", re.compile(r"\b(KEYCLOAK_[A-Z_]+)\b")),
]


def _is_template_env_file(filename: str) -> bool:
    lower = filename.lower()
    return lower.startswith(".env.") and any(marker in lower for marker in ("example", "sample", "template"))


def _looks_like_pattern_definition(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith(('r"', "r'")):
        return True
    if stripped.startswith('("') and "[" in stripped and "]" in stripped:
        return True
    quote_count = stripped.count('"') + stripped.count("'")
    return quote_count >= 4 and any(token in stripped for token in ("{", "[", "],", "},"))


def _looks_like_env_config_file(base: str) -> bool:
    lower = base.lower()
    if lower.startswith(".env"):
        return True
    if lower in {
        "application.yml",
        "application.yaml",
        "application.properties",
        "appsettings.json",
        "appsettings.development.json",
        "appsettings.production.json",
    }:
        return True
    return any(token in lower for token in ("config", "settings", "application")) and lower.endswith(
        (".json", ".yaml", ".yml", ".toml", ".properties")
    )


def _line_matches_usage(line: str, indicator: str) -> bool:
    lower_line = line.lower()
    lower_indicator = indicator.lower()

    if lower_indicator.startswith(('"', "'")):
        token = lower_indicator.strip("\"'")
        if not (token.startswith("@") or "/" in token):
            return False
        return bool(
            re.search(
                rf'(?:from\s+["\'][^"\']*{re.escape(token)}[^"\']*["\']|require\(\s*["\'][^"\']*{re.escape(token)}[^"\']*["\']|import\(\s*["\'][^"\']*{re.escape(token)}[^"\']*["\'])',
                lower_line,
            )
        )

    if lower_indicator.startswith(("import ", "from ")):
        return lower_indicator in lower_line

    if not re.search(rf"\b{re.escape(lower_indicator)}\b", lower_line):
        return False

    return any(
        hint in lower_line
        for hint in (
            "import ",
            "from ",
            "using ",
            "require(",
            "import(",
            "new ",
            ".add",
            ".use",
            ".create",
            ".connect",
            "client(",
            "builder.",
            "services.",
            "oauth",
            "oidc",
        )
    )


class ExternalIntegrationExtractor(Analyzer):
    def supports(self, file_index: FileIndex) -> bool:
        return True

    def analyze(self, file_index: FileIndex) -> GraphFactPatch:
        patch = GraphFactPatch()
        emitted_nodes: set[str] = set()
        emitted_edges: set[tuple[str, str]] = set()
        env_var_evidence: dict[str, list[str]] = {}
        dep_hits: dict[str, tuple[str, str, str]] = {}

        # Step 1: dependency files are corroborating evidence only.
        for path in file_index.paths:
            base = file_basename(path)
            ext = ("." + base.rsplit(".", 1)[-1].lower()) if "." in base else ""
            if base not in _DEP_NAMES and ext not in _DEP_EXTS:
                continue
            content = file_index.get_content(path) or ""
            for name, node_type, indicators in _EXTERNAL_APIS:
                if name in dep_hits:
                    continue
                for indicator in indicators:
                    if indicator.lower() in content.lower():
                        dep_hits[name] = (path, indicator, node_type)
                        break

        # Step 2: runtime env/config files can still corroborate inferred integrations.
        for path in file_index.paths:
            base = file_basename(path)
            if not _looks_like_env_config_file(base) or _is_template_env_file(base):
                continue
            content = file_index.get_content(path) or ""
            lines = content.splitlines()
            for line_number, line in enumerate(lines, start=1):
                if _looks_like_pattern_definition(line):
                    continue
                for provider, pattern in _ENV_VAR_PROVIDERS:
                    match = pattern.search(line)
                    if not match:
                        continue
                    evidence_id = ev_tmp()
                    patch.evidence.append(
                        Evidence(
                            id=evidence_id,
                            kind="env_var",
                            file_path=path,
                            start_line=line_number,
                            end_line=line_number,
                            symbol=match.group(1),
                            excerpt=line.strip()[:120],
                        )
                    )
                    env_var_evidence.setdefault(provider, []).append(evidence_id)
                    break

        # Step 3: source files must show direct usage before we create integration nodes/edges.
        for name, node_type, indicators in _EXTERNAL_APIS:
            node_id = make_node_id(name)
            dep_hit = dep_hits.get(name)

            found_path: str | None = None
            found_line: int | None = None
            found_excerpt = ""

            for path in file_index.paths:
                base = file_basename(path)
                ext = ("." + base.rsplit(".", 1)[-1].lower()) if "." in base else ""
                if ext not in _SRC_EXTS:
                    continue
                content = file_index.get_content(path) or ""
                lines = content.splitlines()
                for line_number, line in enumerate(lines, start=1):
                    if _looks_like_pattern_definition(line):
                        continue
                    if any(_line_matches_usage(line, indicator) for indicator in indicators):
                        found_path = path
                        found_line = line_number
                        found_excerpt = line.strip()[:120]
                        break
                if found_path:
                    break

            if not found_path:
                env_ids = env_var_evidence.get(name, [])
                if not env_ids:
                    continue
                self._emit_node_and_edge(
                    name,
                    node_id,
                    node_type,
                    "inferred",
                    env_ids,
                    patch,
                    emitted_nodes,
                    emitted_edges,
                    None,
                )
                continue

            evidence_ids: list[str] = []

            code_evidence_id = ev_tmp()
            patch.evidence.append(
                Evidence(
                    id=code_evidence_id,
                    kind="code_reference",
                    file_path=found_path,
                    start_line=found_line,
                    end_line=found_line,
                    excerpt=found_excerpt,
                )
            )
            evidence_ids.append(code_evidence_id)

            if dep_hit:
                dep_path, indicator, _ = dep_hit
                dep_evidence_id = ev_tmp()
                patch.evidence.append(
                    Evidence(
                        id=dep_evidence_id,
                        kind="manifest",
                        file_path=dep_path,
                        excerpt=indicator[:80],
                    )
                )
                evidence_ids.append(dep_evidence_id)

            evidence_ids.extend(env_var_evidence.get(name, []))
            confidence = "verified" if dep_hit else "inferred"
            self._emit_node_and_edge(
                name,
                node_id,
                node_type,
                confidence,
                evidence_ids,
                patch,
                emitted_nodes,
                emitted_edges,
                found_path,
            )

        return patch

    def _emit_node_and_edge(
        self,
        name: str,
        node_id: str,
        node_type: str,
        confidence: str,
        evidence_ids: list[str],
        patch: GraphFactPatch,
        emitted_nodes: set[str],
        emitted_edges: set[tuple[str, str]],
        file_path: str | None,
    ) -> None:
        if node_id not in emitted_nodes:
            emitted_nodes.add(node_id)
            patch.nodes.append(
                NodeFact(
                    id=node_id,
                    type=node_type,  # type: ignore[arg-type]
                    name=name,
                    tags=["external"],
                    confidence=confidence,  # type: ignore[arg-type]
                    evidence_ids=evidence_ids,
                )
            )

        if file_path:
            service_id = infer_service_id(file_path)
            edge_key = (service_id, node_id)
            if edge_key not in emitted_edges:
                emitted_edges.add(edge_key)
                patch.edges.append(
                    EdgeFact(
                        id=f"edge-{service_id}-{node_id}-sdk",
                        src=service_id,
                        dst=node_id,
                        kind="sdk",
                        direction="outbound",
                        confidence=confidence,  # type: ignore[arg-type]
                        evidence_ids=evidence_ids,
                    )
                )
