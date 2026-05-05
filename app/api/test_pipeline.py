"""
Run from app/api/ with the venv active:
    python test_pipeline.py

Tests each stage independently so you can see exactly where it breaks.
"""

import json
import sys

SAMPLE_TREE = """\
app/
  api/
    main.py
    requirements.txt
  web/
    src/
      app/
        page.tsx
"""

SAMPLE_FILES = {
    "app/api/main.py": """\
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/users")
def get_users():
    return []
""",
    "app/web/src/app/page.tsx": """\
export default function Home() {
  return <main><h1>Hello</h1></main>;
}
""",
}


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print("="*60)


def dump(label: str, data: dict):
    print(f"\n--- {label} ---")
    print(json.dumps(data, indent=2))


# ── 1. Ollama connectivity ──────────────────────────────────────
section("1. Ollama connectivity")
try:
    import httpx
    from core.config import settings
    r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=10)
    r.raise_for_status()
    models = [m["name"] for m in r.json().get("models", [])]
    print(f"OK  Ollama is reachable at {settings.ollama_base_url}")
    print(f"    Available models: {models}")
    for required in ("llama3", "deepseek-coder"):
        found = any(required in m for m in models)
        status = "OK " if found else "MISSING"
        print(f"    [{status}] {required}")
except Exception as e:
    print(f"FAIL  Cannot reach Ollama: {e}")
    sys.exit(1)


# ── 2. Repo Analyzer ────────────────────────────────────────────
section("2. Repo Analyzer (deepseek-coder)")
try:
    from agents.repo_analyzer import analyze_repo
    file_contents = "\n\n".join(f"### {p}\n{c}" for p, c in SAMPLE_FILES.items())
    result = analyze_repo(SAMPLE_TREE, file_contents)
    dump("repo_analysis", result)
    print("\nOK  Repo Analyzer passed")
except Exception as e:
    print(f"\nFAIL  {type(e).__name__}: {e}")
    sys.exit(1)


# ── 3. System Designer ──────────────────────────────────────────
section("3. System Designer (llama3)")
try:
    from agents.system_designer import design_system
    design = design_system(result)
    dump("system_design", design)
    print("\nOK  System Designer passed")
except Exception as e:
    print(f"\nFAIL  {type(e).__name__}: {e}")
    sys.exit(1)


# ── 4. Bottleneck Detector ──────────────────────────────────────
section("4. Bottleneck Detector (llama3)")
try:
    from agents.bottleneck_detector import detect_bottlenecks
    bottlenecks = detect_bottlenecks(design)
    dump("bottlenecks", bottlenecks)
    print("\nOK  Bottleneck Detector passed")
except Exception as e:
    print(f"\nFAIL  {type(e).__name__}: {e}")
    sys.exit(1)


# ── 5. Diagram Generator ────────────────────────────────────────
section("5. Diagram Generator (deterministic)")
try:
    from agents.diagram_generator import generate_diagram
    diagram = generate_diagram(design, bottlenecks)
    dump("diagram", diagram)
    print("\nOK  Diagram Generator passed")
except Exception as e:
    print(f"\nFAIL  {type(e).__name__}: {e}")
    sys.exit(1)


section("ALL STAGES PASSED")
print("The full pipeline is working.\n")
