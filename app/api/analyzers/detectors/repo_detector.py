import re
import uuid
from collections import Counter

from analyzers.base import Analyzer
from analyzers.file_index import FileIndex
from graph.models import GraphFactPatch, NodeFact, Evidence, WarningFact, make_node_id


_LANG_MAP: dict[str, str] = {
    ".py": "Python",    ".js": "JavaScript", ".ts": "TypeScript",
    ".jsx": "JavaScript", ".tsx": "TypeScript", ".java": "Java",
    ".go": "Go",        ".rb": "Ruby",       ".php": "PHP",
    ".cs": "C#",        ".rs": "Rust",       ".cpp": "C++",
    ".c": "C",          ".kt": "Kotlin",     ".swift": "Swift",
    ".scala": "Scala",  ".ex": "Elixir",     ".exs": "Elixir",
    ".clj": "Clojure",  ".hs": "Haskell",
}

_DEP_FILENAMES = {
    "requirements.txt", "package.json", "pom.xml", "go.mod",
    "Gemfile", "composer.json", "Cargo.toml", "build.gradle",
    "pyproject.toml", "Pipfile",
}

_FRAMEWORKS: list[tuple[str, list[tuple[str, str]]]] = [
    ("FastAPI",         [("requirements.txt", "fastapi"), ("pyproject.toml", "fastapi")]),
    ("Django",          [("requirements.txt", "django"), ("manage.py", "")]),
    ("Flask",           [("requirements.txt", "flask")]),
    ("Celery",          [("requirements.txt", "celery")]),
    ("LangChain",       [("requirements.txt", "langchain")]),
    ("LangGraph",       [("requirements.txt", "langgraph")]),
    ("Express",         [("package.json", '"express"')]),
    ("Next.js",         [("package.json", '"next"')]),
    ("React",           [("package.json", '"react"')]),
    ("Vue.js",          [("package.json", '"vue"')]),
    ("NestJS",          [("package.json", '"@nestjs/core"')]),
    ("Fastify",         [("package.json", '"fastify"')]),
    ("Angular",         [("package.json", '"@angular/core"')]),
    ("Spring Boot",     [("pom.xml", "spring-boot-starter"), ("build.gradle", "spring-boot")]),
    ("Ruby on Rails",   [("Gemfile", "rails")]),
    ("Laravel",         [("composer.json", '"laravel/framework"')]),
    ("Prisma",          [("package.json", '"prisma"')]),
    ("SQLAlchemy",      [("requirements.txt", "sqlalchemy"), ("pyproject.toml", "sqlalchemy")]),
]

_CONTAINER_DIRS = {"services", "apps", "packages", "modules", "microservices"}

_ENTRY_FILES = {
    "main.py", "app.py", "server.py", "wsgi.py", "asgi.py",
    "index.js", "index.ts", "server.js", "server.ts", "app.js",
    "Main.java", "Application.java", "main.go", "main.rb",
}

_CICD_PATTERNS: list[tuple[str, str]] = [
    ("github_actions", ".github/workflows/"),
    ("gitlab_ci",      ".gitlab-ci.yml"),
    ("jenkins",        "jenkinsfile"),
    ("circleci",       ".circleci/"),
    ("travis",         ".travis.yml"),
    ("azure_devops",   "azure-pipelines.yml"),
]


def _ev_tmp() -> str:
    return f"ev_tmp_{uuid.uuid4().hex[:8]}"


def _basename(path: str) -> str:
    return path.replace("\\", "/").rsplit("/", 1)[-1]


def _parts(path: str) -> list[str]:
    return [p for p in path.replace("\\", "/").split("/") if p]


class RepoDetector(Analyzer):
    def supports(self, file_index: FileIndex) -> bool:
        return True

    def analyze(self, file_index: FileIndex) -> GraphFactPatch:
        patch = GraphFactPatch()

        # Detect service directories
        service_dirs = self._detect_service_dirs(file_index)

        # Detect languages per service
        lang_by_service: dict[str, Counter] = {s: Counter() for s in service_dirs}
        lang_evidence: dict[str, tuple[str, str]] = {}  # lang → (file_path, ext)
        for path in file_index.paths:
            ext = "." + path.rsplit(".", 1)[-1].lower() if "." in _basename(path) else ""
            lang = _LANG_MAP.get(ext)
            if not lang:
                continue
            svc = self._file_to_service(path, service_dirs)
            if svc:
                lang_by_service[svc][lang] += 1
            if lang not in lang_evidence:
                lang_evidence[lang] = (path, ext)

        # Detect frameworks per service
        framework_by_service: dict[str, list[tuple[str, str, str]]] = {s: [] for s in service_dirs}
        for framework, checks in _FRAMEWORKS:
            for filename, needle in checks:
                for path in file_index.find_by_name(filename):
                    content = file_index.get_content(path) or ""
                    if needle and needle.lower() not in content.lower():
                        continue
                    svc = self._file_to_service(path, service_dirs)
                    if svc:
                        framework_by_service[svc].append((framework, path, needle))
                    break

        # Build NodeFacts for each service
        for svc_name in service_dirs:
            node_id = make_node_id(svc_name)
            ev_ids: list[str] = []
            tags: list[str] = []

            lang_counter = lang_by_service[svc_name]
            dominant_lang = lang_counter.most_common(1)[0][0] if lang_counter else None
            if dominant_lang and dominant_lang in lang_evidence:
                ev_path, ev_ext = lang_evidence[dominant_lang]
                ev_id = _ev_tmp()
                patch.evidence.append(Evidence(
                    id=ev_id,
                    kind="file",
                    file_path=ev_path,
                    excerpt=f"{ev_ext} source file detected",
                ))
                ev_ids.append(ev_id)

            frameworks = framework_by_service[svc_name]
            dominant_fw = frameworks[0][0] if frameworks else None
            fw_path = frameworks[0][1] if frameworks else None
            fw_needle = frameworks[0][2] if frameworks else None
            if dominant_fw and fw_path:
                # Find the matching line for better evidence
                excerpt = fw_needle if fw_needle else dominant_fw
                if fw_needle:
                    content = file_index.get_content(fw_path) or ""
                    for lineno, line in enumerate(content.splitlines(), 1):
                        if fw_needle.lower() in line.lower():
                            ev_id = _ev_tmp()
                            patch.evidence.append(Evidence(
                                id=ev_id,
                                kind="manifest",
                                file_path=fw_path,
                                start_line=lineno,
                                end_line=lineno,
                                excerpt=line.strip()[:120],
                            ))
                            ev_ids.append(ev_id)
                            break

            # Determine node type: frontend if framework is React/Vue/Angular/Next.js
            _frontend_frameworks = {"React", "Vue.js", "Angular", "Next.js"}
            node_type = "client" if dominant_fw in _frontend_frameworks else "service"

            # Add framework as tag
            if dominant_fw:
                tags.append(dominant_fw)

            patch.nodes.append(NodeFact(
                id=node_id,
                type=node_type,
                name=svc_name,
                language=dominant_lang,
                framework=dominant_fw,
                tags=tags,
                confidence="inferred",
                evidence_ids=ev_ids,
            ))

        # README summary as an informational warning (so it's surfaced)
        readme = self._extract_readme(file_index)
        if readme:
            patch.warnings.append(WarningFact(
                code="README_SUMMARY",
                message=readme[:300],
            ))

        # CI/CD detection as informational warnings
        for platform, pattern in _CICD_PATTERNS:
            matches = [p for p in file_index.paths if pattern in p.replace("\\", "/").lower()]
            if matches:
                patch.warnings.append(WarningFact(
                    code="CICD_DETECTED",
                    message=f"CI/CD platform detected: {platform}",
                    file_path=matches[0],
                ))

        return patch

    def _detect_service_dirs(self, file_index: FileIndex) -> list[str]:
        services: set[str] = set()
        for path in file_index.paths:
            parts = _parts(path)
            if len(parts) >= 2 and parts[0].lower() in _CONTAINER_DIRS:
                services.add(parts[1])
                continue
            if len(parts) >= 2:
                top = parts[0]
                base = _basename(path)
                if base in _DEP_FILENAMES or base in _ENTRY_FILES:
                    services.add(top)
        if not services:
            # Flat repo: treat top-level dir (or "repo") as the single service
            all_parts = [_parts(p) for p in file_index.paths if _parts(p)]
            if all_parts:
                root = all_parts[0][0]
                services.add(root)
        return sorted(services)

    def _file_to_service(self, path: str, service_dirs: list[str]) -> str | None:
        parts = _parts(path)
        if not parts:
            return None
        if len(parts) >= 2 and parts[0].lower() in _CONTAINER_DIRS:
            return parts[1] if parts[1] in service_dirs else None
        if parts[0] in service_dirs:
            return parts[0]
        # Single-service repo: assign to the only service
        if len(service_dirs) == 1:
            return service_dirs[0]
        return None

    def _extract_readme(self, file_index: FileIndex) -> str:
        for path in file_index.paths:
            base = _basename(path).lower()
            parts = _parts(path)
            if len(parts) <= 2 and base.startswith("readme"):
                content = file_index.get_content(path) or ""
                lines = [l for l in content.splitlines() if not l.strip().startswith("#")]
                prose = " ".join(" ".join(l.split()) for l in lines if l.strip())
                return prose[:600]
        return ""
