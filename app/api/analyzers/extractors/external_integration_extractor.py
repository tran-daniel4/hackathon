import re

from analyzers.base import Analyzer
from analyzers.file_index import FileIndex
from analyzers.extractors._helpers import ev_tmp, file_basename, infer_service_id
from graph.models import GraphFactPatch, NodeFact, EdgeFact, Evidence, make_node_id


_SRC_EXTS = frozenset({".py", ".ts", ".js", ".jsx", ".tsx", ".mjs"})
_DEP_NAMES = {"requirements.txt", "package.json", "Pipfile", "pyproject.toml"}
_ENV_EXTS = frozenset({".py", ".ts", ".js", ".jsx", ".tsx", ".yml", ".yaml", ".toml"})

# (name, node_type, [indicator_strings])
_EXTERNAL_APIS: list[tuple[str, str, list[str]]] = [
    ("Stripe",       "external_service", ["import stripe", "from stripe", '"stripe"']),
    ("Twilio",       "external_service", ["import twilio", "from twilio", '"twilio"']),
    ("SendGrid",     "external_service", ["import sendgrid", "from sendgrid", '"@sendgrid"']),
    ("OpenAI",       "external_service", ["import openai", "from openai", '"openai"']),
    ("Anthropic",    "external_service", ["import anthropic", "from anthropic", '"@anthropic-ai"']),
    ("AWS SDK",      "external_service", ["import boto3", "from boto3", '"aws-sdk"', '"@aws-sdk"']),
    ("GitHub API",   "external_service", ["pygithub", "octokit", '"@octokit"']),
    ("Google APIs",  "external_service", ["google-cloud", "googleapiclient", '"@google-cloud"']),
    ("Slack",        "external_service", ["slack_sdk", '"@slack/web-api"']),
    ("PayPal",       "external_service", ["paypalrestsdk", '"paypal"']),
    ("Plaid",        "external_service", ["import plaid", '"plaid"']),
    ("Pinecone",     "external_service", ["import pinecone", '"@pinecone-database"']),
    ("Weaviate",     "external_service", ["import weaviate", '"weaviate-client"']),
    ("Hugging Face", "external_service", ["huggingface_hub", '"@huggingface"']),
    ("Deepgram",     "external_service", ["deepgram", '"@deepgram"']),
    ("Mailgun",      "external_service", ["mailgun"]),
    ("Cloudinary",   "external_service", ["cloudinary"]),
    # Auth providers
    ("Auth0",      "auth_provider", ['"auth0"', '"@auth0"', "auth0-spa"]),
    ("Okta",       "auth_provider", ['"@okta"', "okta-auth-js"]),
    ("Cognito",    "auth_provider", ["amazon-cognito", "aws-amplify/auth", "cognito"]),
    ("Keycloak",   "auth_provider", ["keycloak"]),
    ("Supabase",   "auth_provider", ['"@supabase"', "supabase"]),
]

_ENV_VAR_PROVIDERS: list[tuple[str, re.Pattern]] = [
    ("Stripe",     re.compile(r'\b(STRIPE_[A-Z_]+)\b')),
    ("Twilio",     re.compile(r'\b(TWILIO_[A-Z_]+)\b')),
    ("SendGrid",   re.compile(r'\b(SENDGRID_[A-Z_]+)\b')),
    ("OpenAI",     re.compile(r'\b(OPENAI_[A-Z_]+)\b')),
    ("Anthropic",  re.compile(r'\b(ANTHROPIC_[A-Z_]+)\b')),
    ("AWS SDK",    re.compile(r'\b(AWS_(?:ACCESS|SECRET|REGION|BUCKET|ACCOUNT)[A-Z_]*)\b')),
    ("GitHub API", re.compile(r'\b(GITHUB_(?:CLIENT|TOKEN|SECRET|APP)[A-Z_]*)\b')),
    ("Google APIs",re.compile(r'\b(GOOGLE_[A-Z_]+|GCP_[A-Z_]+)\b')),
    ("Auth0",      re.compile(r'\b(AUTH0_[A-Z_]+)\b')),
    ("Okta",       re.compile(r'\b(OKTA_[A-Z_]+)\b')),
    ("Slack",      re.compile(r'\b(SLACK_[A-Z_]+)\b')),
    ("PayPal",     re.compile(r'\b(PAYPAL_[A-Z_]+)\b')),
    ("Plaid",      re.compile(r'\b(PLAID_[A-Z_]+)\b')),
    ("Mailgun",    re.compile(r'\b(MAILGUN_[A-Z_]+)\b')),
    ("Cloudinary", re.compile(r'\b(CLOUDINARY_[A-Z_]+)\b')),
    ("Sentry",     re.compile(r'\b(SENTRY_[A-Z_]+)\b')),
]


class ExternalIntegrationExtractor(Analyzer):
    def supports(self, file_index: FileIndex) -> bool:
        return True

    def analyze(self, file_index: FileIndex) -> GraphFactPatch:
        patch = GraphFactPatch()
        emitted_nodes: set[str] = set()
        emitted_edges: set[tuple[str, str]] = set()
        # integration_name → extra evidence from env vars
        env_var_evidence: dict[str, list[str]] = {}

        # Step 1: scan dependency files first (higher confidence)
        dep_hits: dict[str, tuple[str, str, str]] = {}  # name → (file_path, indicator, node_type)
        for path in file_index.paths:
            if file_basename(path) not in _DEP_NAMES:
                continue
            content = file_index.get_content(path) or ""
            for name, node_type, indicators in _EXTERNAL_APIS:
                if name in dep_hits:
                    continue
                for ind in indicators:
                    if ind.lower() in content.lower():
                        dep_hits[name] = (path, ind, node_type)
                        break

        # Step 2: scan env files for env var corroboration
        for path in file_index.paths:
            base = file_basename(path)
            ext = ("." + base.rsplit(".", 1)[-1].lower()) if "." in base else ""
            if not (base.lower().startswith(".env") or ext in _ENV_EXTS):
                continue
            content = file_index.get_content(path) or ""
            lines = content.splitlines()
            for lineno, line in enumerate(lines, start=1):
                for provider, rx in _ENV_VAR_PROVIDERS:
                    m = rx.search(line)
                    if m:
                        ev_id = ev_tmp()
                        patch.evidence.append(Evidence(
                            id=ev_id,
                            kind="env_var",
                            file_path=path,
                            start_line=lineno,
                            end_line=lineno,
                            symbol=m.group(1),
                            excerpt=line.strip()[:120],
                        ))
                        env_var_evidence.setdefault(provider, []).append(ev_id)
                        break

        # Step 3: build nodes/edges for dep-file hits
        for name, (dep_path, indicator, node_type) in dep_hits.items():
            node_id = make_node_id(name)
            ev_id = ev_tmp()
            patch.evidence.append(Evidence(
                id=ev_id,
                kind="manifest",
                file_path=dep_path,
                excerpt=indicator[:80],
            ))
            all_ev_ids = [ev_id] + env_var_evidence.get(name, [])
            confidence = "verified"
            self._emit_node_and_edge(name, node_id, node_type, confidence, all_ev_ids,
                                     patch, emitted_nodes, emitted_edges, dep_path)

        # Step 4: scan source files for any remaining integrations not found in deps
        for name, node_type, indicators in _EXTERNAL_APIS:
            if name in dep_hits:
                continue
            node_id = make_node_id(name)
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
                for lineno, line in enumerate(lines, start=1):
                    if any(ind.lower() in line.lower() for ind in indicators):
                        found_path = path
                        found_line = lineno
                        found_excerpt = line.strip()[:120]
                        break
                if found_path:
                    break

            if not found_path:
                # Check env var evidence only
                ev_ids = env_var_evidence.get(name, [])
                if not ev_ids:
                    continue
                self._emit_node_and_edge(name, node_id, node_type, "inferred", ev_ids,
                                         patch, emitted_nodes, emitted_edges, None)
                continue

            ev_id = ev_tmp()
            patch.evidence.append(Evidence(
                id=ev_id,
                kind="code_reference",
                file_path=found_path,
                start_line=found_line,
                end_line=found_line,
                excerpt=found_excerpt,
            ))
            all_ev_ids = [ev_id] + env_var_evidence.get(name, [])
            self._emit_node_and_edge(name, node_id, node_type, "inferred", all_ev_ids,
                                     patch, emitted_nodes, emitted_edges, found_path)

        return patch

    def _emit_node_and_edge(
        self,
        name: str,
        node_id: str,
        node_type: str,
        confidence: str,
        ev_ids: list[str],
        patch: GraphFactPatch,
        emitted_nodes: set[str],
        emitted_edges: set[tuple[str, str]],
        file_path: str | None,
    ) -> None:
        if node_id not in emitted_nodes:
            emitted_nodes.add(node_id)
            patch.nodes.append(NodeFact(
                id=node_id,
                type=node_type,  # type: ignore[arg-type]
                name=name,
                tags=["external"],
                confidence=confidence,  # type: ignore[arg-type]
                evidence_ids=ev_ids,
            ))

        # Emit an edge from the inferred service (if file_path available)
        if file_path:
            svc_id = infer_service_id(file_path)
            edge_key = (svc_id, node_id)
            if edge_key not in emitted_edges:
                emitted_edges.add(edge_key)
                patch.edges.append(EdgeFact(
                    id=f"edge-{svc_id}-{node_id}-sdk",
                    src=svc_id,
                    dst=node_id,
                    kind="sdk",
                    direction="outbound",
                    confidence=confidence,  # type: ignore[arg-type]
                    evidence_ids=ev_ids,
                ))
