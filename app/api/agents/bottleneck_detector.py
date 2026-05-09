from agents.llm import run_llm, REASON_MODEL

SCHEMA = {
    "bottlenecks": [
        {
            "type": "db | api | compute | network | coupling | single_point_of_failure",
            "component": "string",
            "description": "string",
            "severity": "low | medium | high",
        }
    ]
}

PROMPT_TEMPLATE = """\
You are a software reliability and performance analysis agent. Your job is to identify \
architectural bottlenecks, scaling risks, and failure points in a system design.

Return ONLY valid JSON. No explanation, no markdown, no extra text.

Output schema:
{schema}

Rules:
- "type": classify each issue as one of: db, api, compute, network, coupling, single_point_of_failure
- "component": the exact component name from the system design that has the issue
- "description": one concise sentence explaining the specific risk
- "severity": rate impact as low, medium, or high
- Look for:
  - Components with many inbound dependencies (high coupling)
  - Single databases or caches with no replication (single point of failure)
  - Synchronous chains of 3+ services (latency amplification)
  - Missing queues between high-throughput producers and consumers
  - APIs that call databases directly with no caching layer
- If no bottlenecks are found, return {{"bottlenecks": []}}
- Only report issues supported by the input — do not invent

System design input:
{system_design}
"""


def detect_bottlenecks(system_design: dict) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        schema=SCHEMA,
        system_design=system_design,
    )
    return run_llm(REASON_MODEL, prompt)
