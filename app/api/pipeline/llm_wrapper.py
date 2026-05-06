"""
LLM Integration Layer — DeepSeek Coder wrapper.
Accepts rule-based issues + graph context + optional code snippets.
Returns enriched analysis. Prompts stay under 1500 tokens.

Two providers:
  "ollama"        — local Ollama server (default, current setup)
  "openai_compat" — any OpenAI-compatible endpoint (for deployed fine-tuned model)
"""
import json
import logging
import re
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel

from pipeline.graph_builder import ArchGraph
from pipeline.rules_engine import Issue

logger = logging.getLogger(__name__)


# ── Config ─────────────────────────────────────────────────────────────────────

class LLMConfig(BaseModel):
    provider: Literal["ollama", "openai_compat"] = "ollama"
    base_url: str = "http://localhost:11434"
    model: str = "deepseek-coder:6.7b-instruct-q4_K_M"
    api_key: str = ""       # required only for openai_compat
    timeout: float = 120.0  # shorter than pipeline timeout — prompts are focused
    max_tokens: int = 512


# ── Output schema ──────────────────────────────────────────────────────────────

class EnrichedIssue(BaseModel):
    # Mirrors Issue fields so this is self-contained
    type: str
    severity: Literal["low", "medium", "high", "critical"]
    affected: list[str]
    description: str
    recommendation: str
    # LLM enrichment (empty when enrichment fails)
    llm_explanation: str = ""
    llm_fix: str = ""
    llm_confidence: float = 0.0
    llm_enriched: bool = False


# ── Public API ─────────────────────────────────────────────────────────────────

def enrich_issues(
    issues: list[Issue],
    graph: ArchGraph,
    root: Path | None = None,
    config: LLMConfig | None = None,
) -> list[EnrichedIssue]:
    """
    Send each rule-based issue to DeepSeek for deeper analysis.
    Falls back gracefully to the original rule data if the model is unreachable
    or returns unparseable output — the pipeline never breaks.
    """
    cfg = config or LLMConfig()
    enriched: list[EnrichedIssue] = []

    for issue in issues:
        base = EnrichedIssue(
            type=issue.type,
            severity=issue.severity,
            affected=issue.affected,
            description=issue.description,
            recommendation=issue.recommendation,
        )
        try:
            prompt   = _build_prompt(issue, graph, root)
            raw      = _call_llm(prompt, cfg)
            analysis = _parse_response(raw)

            base.llm_explanation = analysis.get("explanation", "")
            base.llm_fix         = analysis.get("fix", "")
            base.llm_confidence  = float(analysis.get("confidence", 0.0))
            base.llm_enriched    = True
        except Exception as exc:
            logger.warning("LLM enrichment skipped for '%s': %s", issue.type, exc)

        enriched.append(base)

    return enriched


# ── Prompt construction ────────────────────────────────────────────────────────

_MAX_PROMPT_CHARS = 5_500   # ~1375 tokens at 4 chars/token — comfortably under 1500

def _build_prompt(issue: Issue, graph: ArchGraph, root: Path | None) -> str:
    parts: list[str] = [
        "Analyze this architecture bottleneck. Return JSON only — no prose, no markdown.\n",
        f"Issue:    {issue.type}",
        f"Severity: {issue.severity}",
        f"Affected: {', '.join(issue.affected[:6])}",
        "",
        _graph_context(issue, graph),
    ]

    snippet = _code_snippet(issue.description, root) if root else ""
    if snippet:
        parts += ["", snippet]

    parts += [
        "",
        "Respond with exactly this JSON shape:",
        '{"bottleneck_type":"...","severity":"low|medium|high|critical",',
        ' "explanation":"2-3 sentences","fix":"one specific actionable step","confidence":0.0}',
    ]

    prompt = "\n".join(parts)

    if len(prompt) > _MAX_PROMPT_CHARS:
        prompt = prompt[:_MAX_PROMPT_CHARS] + "\n...[truncated]"

    return prompt


def _graph_context(issue: Issue, graph: ArchGraph) -> str:
    affected = set(issue.affected)
    nodes    = [n for n in graph.nodes if n.id in affected]
    edges    = [e for e in graph.edges if e.source in affected or e.target in affected][:8]

    lines = ["Architecture context:"]
    for n in nodes:
        lines.append(f"  {n.label} [{n.type}]")
    for e in edges:
        lines.append(f"  {e.source} --[{e.type}]--> {e.target}")
    return "\n".join(lines)


_FILE_LINE_RE = re.compile(r"at ([\w./\\-]+\.\w+):(\d+)")

def _code_snippet(description: str, root: Path) -> str:
    """Extract the relevant source lines referenced in an issue description."""
    m = _FILE_LINE_RE.search(description)
    if not m:
        return ""

    rel, lineno = m.group(1), int(m.group(2))
    fpath = root / rel.replace("\\", "/")

    try:
        lines = fpath.read_text(encoding="utf-8", errors="ignore").splitlines()
        start = max(0, lineno - 2)
        end   = min(len(lines), lineno + 20)
        body  = "\n".join(lines[start:end])
        return f"Code ({rel} lines {start + 1}–{end}):\n```\n{body}\n```"
    except OSError:
        return ""


# ── LLM backends ──────────────────────────────────────────────────────────────

def _call_llm(prompt: str, cfg: LLMConfig) -> str:
    if cfg.provider == "ollama":
        return _call_ollama(prompt, cfg)
    return _call_openai_compat(prompt, cfg)


def _call_ollama(prompt: str, cfg: LLMConfig) -> str:
    resp = httpx.post(
        f"{cfg.base_url}/api/chat",
        json={
            "model": cfg.model,
            "messages": [{"role": "user", "content": prompt}],
            "format": "json",
            "stream": False,
            "keep_alive": "10m",
            "options": {
                "num_ctx":    4096,
                "num_predict": cfg.max_tokens,
                "num_thread": 4,
                "num_batch":  128,
                "temperature": 0.1,
            },
        },
        timeout=cfg.timeout,
    )
    if resp.is_error:
        raise ValueError(f"Ollama {resp.status_code}: {resp.text[:300]}")
    return resp.json()["message"]["content"].strip()


def _call_openai_compat(prompt: str, cfg: LLMConfig) -> str:
    resp = httpx.post(
        f"{cfg.base_url}/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {cfg.api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": cfg.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": cfg.max_tokens,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        },
        timeout=cfg.timeout,
    )
    if resp.is_error:
        raise ValueError(f"API {resp.status_code}: {resp.text[:300]}")
    return resp.json()["choices"][0]["message"]["content"].strip()


# ── Response parser ────────────────────────────────────────────────────────────

_JSON_BLOCK_RE = re.compile(r"\{.*?\}", re.DOTALL)


def _parse_response(raw: str) -> dict:
    text = raw.strip()

    # Direct parse (model outputted clean JSON)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Extract first JSON block from mixed output
    m = _JSON_BLOCK_RE.search(text)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Unparseable LLM response: {text[:200]!r}")
