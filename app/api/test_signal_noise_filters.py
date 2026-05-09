import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from analyzers.file_index import FileIndex
from analyzers.orchestrator import AnalyzerOrchestrator
from pipeline.scanner import scan_files


def test_dependency_only_integrations_and_template_envs_do_not_create_nodes():
    files = {
        "repo/package.json": """
{
  "dependencies": {
    "openai": "^4.0.0",
    "@deepgram/sdk": "^3.0.0",
    "@aws-sdk/client-s3": "^3.0.0",
    "@supabase/supabase-js": "^2.0.0"
  }
}
""",
        "repo/.env.example": """
OPENAI_API_KEY=
PAYPAL_CLIENT_ID=
AUTH0_DOMAIN=
""",
        "repo/app/api/main.py": """
from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}
""",
    }

    scan = scan_files(files)
    assert scan.external_calls == []
    assert scan.databases == []
    assert scan.env_vars == []

    facts = AnalyzerOrchestrator().run(FileIndex(files), analysis_id="noise-filter-001")
    node_ids = {node.id for node in facts.nodes}

    assert "api" in node_ids
    assert "openai" not in node_ids
    assert "paypal" not in node_ids
    assert "deepgram" not in node_ids
    assert "auth0" not in node_ids


def test_direct_code_and_runtime_config_still_create_real_nodes():
    files = {
        "repo/app/api/requirements.txt": """
fastapi==0.116.0
asyncpg==0.29.0
redis==5.0.0
openai==1.0.0
requests==2.0.0
""",
        "repo/app/api/main.py": """
import openai
import requests
from fastapi import FastAPI

app = FastAPI()

@app.get("/analyze")
async def analyze():
    openai.api_key = "test"
    requests.get("https://api.github.com/repos/openai/openai-python")
    return {"ok": True}
""",
        "repo/app/api/data.py": """
import asyncpg
import redis

async def load_data():
    cache = redis.get("reports")
    conn = await asyncpg.connect("postgresql://db")
    return cache, conn
""",
    }

    scan = scan_files(files)
    assert "OpenAI" in scan.external_calls
    assert "GitHub API" not in scan.external_calls
    assert "Redis" in scan.databases
    assert "PostgreSQL" in scan.databases

    facts = AnalyzerOrchestrator().run(FileIndex(files), analysis_id="noise-filter-002")
    node_ids = {node.id for node in facts.nodes}

    assert "openai" in node_ids
    assert "api-github-com" in node_ids
    assert "redis" in node_ids
    assert "postgresql" in node_ids


if __name__ == "__main__":
    test_dependency_only_integrations_and_template_envs_do_not_create_nodes()
    test_direct_code_and_runtime_config_still_create_real_nodes()
    print("signal noise filter tests passed")
