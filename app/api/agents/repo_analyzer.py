from agents.llm import run_llm, CODE_MODEL

SCHEMA = {
    "services": [{"name": "string", "type": "backend | frontend | worker | unknown"}],
    "modules": [{"name": "string", "path": "string", "responsibility": "string"}],
    "apis": [{"route": "string", "method": "string", "module": "string"}],
    "databases": [{"type": "string", "used_in": ["string"]}],
    "dependencies": [{"from": "string", "to": "string"}],
}

PROMPT_TEMPLATE = """\
You are a code analysis agent. Your job is to analyze a codebase and extract its structure.

Return ONLY valid JSON. No explanation, no markdown, no extra text.

Output schema:
{schema}

Rules:
- "services": top-level services or apps (e.g. FastAPI backend, Next.js frontend, Celery worker)
- "modules": logical groupings of code (files or directories with a clear responsibility)
- "apis": every HTTP route/endpoint found, with its HTTP method and which module defines it
- "databases": any database or cache technology detected (Postgres, Redis, SQLite, etc.)
- "dependencies": directed edges showing which module/service depends on which (from → to)
- If a field has no entries, return an empty list []
- Use only information present in the input — do not invent

File tree:
{file_tree}

File contents:
{file_contents}
"""


def analyze_repo(file_tree: str, file_contents: str) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        schema=SCHEMA,
        file_tree=file_tree,
        file_contents=file_contents,
    )
    return run_llm(CODE_MODEL, prompt)
