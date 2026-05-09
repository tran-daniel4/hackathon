from agents.llm import run_llm, REASON_MODEL

SCHEMA = {
    "architecture_type": "microservices | monolith | serverless | unknown",
    "components": [{"name": "string", "type": "string", "description": "string"}],
    "data_flow": [{"from": "string", "to": "string", "protocol": "string"}],
    "layers": [{"name": "string", "components": ["string"]}],
}

PROMPT_TEMPLATE = """\
You are a software architecture agent. Your job is to convert a raw code structure analysis \
into a clean architecture model.

Return ONLY valid JSON. No explanation, no markdown, no extra text.

Output schema:
{schema}

Rules:
- "architecture_type": classify the overall system as microservices, monolith, serverless, or unknown
- "components": every distinct logical unit (service, database, cache, queue, external API, etc.)
  - "type" must be one of: frontend, backend, database, cache, queue, external, worker
- "data_flow": directed communication paths between components
  - "protocol" must be one of: http, grpc, sql, redis, amqp, websocket, internal, unknown
- "layers": group components into architectural layers (e.g. presentation, application, data)
  - each layer lists the component names that belong to it
- Base everything strictly on the input — do not invent components or flows

Repo analysis input:
{repo_analysis}
"""


def design_system(repo_analysis: dict) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        schema=SCHEMA,
        repo_analysis=repo_analysis,
    )
    return run_llm(REASON_MODEL, prompt)
