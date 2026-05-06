import json
import httpx
from core.config import settings

OLLAMA_BASE_URL = settings.ollama_base_url

CODE_MODEL   = "deepseek-coder:6.7b-instruct-q4_K_M"
REASON_MODEL = CODE_MODEL


def run_llm(model: str, prompt: str) -> dict:
    """Call Ollama in JSON mode and return parsed JSON."""
    response = httpx.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "format": "json",
            "stream": False,
            "keep_alive": "10m",   # keep model in RAM across pipeline stages
            "options": {
                "num_ctx": 8192,   # fits 20 KB input (~5 k tokens) + JSON output
                "num_thread": 4,   # match vCPU count; prevents CPU thrashing
                "num_batch": 128,  # smaller than default 512; reduces memory spikes
            },
        },
        timeout=900.0,
    )
    response.raise_for_status()

    content = response.json()["message"]["content"].strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model {model} returned invalid JSON even in JSON mode: {e}\n\nRaw output:\n{content}")
