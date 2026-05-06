"""
Run from app/api/ with the venv active:
    python test_real_repo.py /path/to/your/test/repo

Walks the given directory, feeds real files through the full pipeline,
and prints every stage's output.
"""

import json
import sys
import os

SKIP_DIRS = {"node_modules", ".git", ".venv", "__pycache__", "dist", "build", ".next", ".mypy_cache"}
TEXT_EXTS  = {
    "py","js","ts","tsx","jsx","go","java","rb","php","cs","cpp","c","h","rs",
    "swift","kt","json","yaml","yml","toml","html","css","scss","sql","sh","md","txt",
}
MAX_BYTES = 50_000


def should_include(rel_path: str) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    if any(p in SKIP_DIRS for p in parts):
        return False
    ext = rel_path.rsplit(".", 1)[-1].lower() if "." in rel_path else ""
    return ext in TEXT_EXTS


def load_repo(root: str) -> tuple[str, str]:
    tree_lines: list[str] = []
    file_contents: list[str] = []
    total = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        rel_dir = os.path.relpath(dirpath, root).replace("\\", "/")
        prefix  = "" if rel_dir == "." else rel_dir + "/"

        for fname in filenames:
            rel_path = prefix + fname
            tree_lines.append(rel_path)

            if total >= MAX_BYTES or not should_include(rel_path):
                continue

            abs_path = os.path.join(dirpath, fname)
            try:
                text = open(abs_path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue

            chunk = text[: MAX_BYTES - total]
            file_contents.append(f"### {rel_path}\n{chunk}")
            total += len(chunk)

    return "\n".join(tree_lines), "\n\n".join(file_contents)


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print("=" * 60)


def dump(label: str, data: dict):
    print(f"\n--- {label} ---")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_real_repo.py <path-to-repo>")
        sys.exit(1)

    repo_path = sys.argv[1]
    if not os.path.isdir(repo_path):
        print(f"Not a directory: {repo_path}")
        sys.exit(1)

    section(f"Loading repo: {repo_path}")
    file_tree, file_contents = load_repo(repo_path)
    num_files = file_contents.count("### ")
    num_chars  = len(file_contents)
    print(f"  Files sent  : {num_files}")
    print(f"  Content size: {num_chars:,} chars ({num_chars/1000:.1f} KB)")

    section("1. Repo Analyzer (deepseek-coder)")
    from agents.repo_analyzer import analyze_repo
    repo_analysis = analyze_repo(file_tree, file_contents)
    dump("repo_analysis", repo_analysis)

    section("2. System Designer (llama3)")
    from agents.system_designer import design_system
    system_design = design_system(repo_analysis)
    dump("system_design", system_design)

    section("3. Bottleneck Detector (llama3)")
    from agents.bottleneck_detector import detect_bottlenecks
    bottlenecks = detect_bottlenecks(system_design)
    dump("bottlenecks", bottlenecks)

    section("4. Diagram Generator (deterministic)")
    from agents.diagram_generator import generate_diagram
    diagram = generate_diagram(system_design, bottlenecks)
    dump("diagram", diagram)

    section("DONE")
    print(f"  Nodes      : {len(diagram['nodes'])}")
    print(f"  Edges      : {len(diagram['edges'])}")
    print(f"  Bottlenecks: {len(diagram['annotations'])}\n")
