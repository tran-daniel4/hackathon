import json
import anthropic

MODEL = "claude-sonnet-4-6"
CODE_MODEL = MODEL
REASON_MODEL = MODEL

_client = anthropic.Anthropic()


def _message_text(message) -> str:
    parts: list[str] = []
    for block in message.content:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts).strip()


def run_llm(_model: str, prompt: str) -> dict:
    """Call Claude API and return parsed JSON."""
    message = _client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system="Respond with valid JSON only. No markdown fences, no explanation, no extra text.",
        messages=[{"role": "user", "content": prompt}],
    )
    content = _message_text(message)
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude returned invalid JSON: {e}\n\nRaw output:\n{content}")
