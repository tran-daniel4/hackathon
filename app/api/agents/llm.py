import json
import re
import httpx
from core.config import settings

OLLAMA_BASE_URL = settings.ollama_base_url

CODE_MODEL = "deepseek-coder"  
REASON_MODEL = "llama3"


def run_llm(model: str, prompt: str) -> dict:
    """Call Ollama and return parsed JSON. Raises ValueError if response is not valid JSON."""
    response = httpx.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        },
        timeout=120.0,
    )
    response.raise_for_status()

    content = response.json()["message"]["content"].strip()

    # Strip markdown code fences if the model wrapped the JSON
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
    if fenced:
        content = fenced.group(1).strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model {model} returned non-JSON output: {e}\n\nRaw output:\n{content}")
