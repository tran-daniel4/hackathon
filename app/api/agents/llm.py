import json
import httpx
from core.config import settings

OLLAMA_BASE_URL = settings.ollama_base_url

CODE_MODEL   = "deepseek-coder:6.7b-instruct-q4_K_M"  # technical extraction — code, deps, APIs
REASON_MODEL = "llama3:8b-instruct-q4_K_M"            # systems reasoning — architecture, bottlenecks


def run_llm(model: str, prompt: str) -> dict:
    """Call Ollama in JSON mode and return parsed JSON."""
    response = httpx.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "format": "json",   # Ollama JSON mode — forces valid JSON output
            "stream": False,
        },
        timeout=600.0, 
    )
    response.raise_for_status()

    content = response.json()["message"]["content"].strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Model {model} returned invalid JSON even in JSON mode: {e}\n\nRaw output:\n{content}")
