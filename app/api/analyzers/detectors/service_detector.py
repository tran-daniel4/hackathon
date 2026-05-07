import re
import uuid

from analyzers.base import Analyzer
from analyzers.file_index import FileIndex
from graph.models import GraphFactPatch, NodeFact, Evidence, make_node_id


def _ev_tmp() -> str:
    return f"ev_tmp_{uuid.uuid4().hex[:8]}"


def _basename(path: str) -> str:
    return path.replace("\\", "/").rsplit("/", 1)[-1]


def _parent_dir(path: str) -> str:
    parts = path.replace("\\", "/").rsplit("/", 1)
    return parts[0] if len(parts) > 1 else ""


class ServiceDetector(Analyzer):
    """Detects services from docker-compose.yml and Dockerfiles."""

    def supports(self, file_index: FileIndex) -> bool:
        return bool(
            file_index.find_by_name("docker-compose.yml")
            or file_index.find_by_name("docker-compose.yaml")
            or file_index.find_by_pattern("*/Dockerfile")
        )

    def analyze(self, file_index: FileIndex) -> GraphFactPatch:
        patch = GraphFactPatch()
        seen_ids: set[str] = set()

        # docker-compose.yml
        for compose_path in (
            file_index.find_by_name("docker-compose.yml")
            + file_index.find_by_name("docker-compose.yaml")
        ):
            content = file_index.get_content(compose_path) or ""
            self._parse_compose(content, compose_path, patch, seen_ids)

        # Dockerfiles in subdirectories
        for dockerfile_path in file_index.find_by_pattern("*/Dockerfile"):
            parent = _parent_dir(dockerfile_path)
            svc_name = parent.rsplit("/", 1)[-1] if "/" in parent else parent
            if not svc_name:
                continue
            node_id = make_node_id(svc_name)
            if node_id in seen_ids:
                continue
            seen_ids.add(node_id)
            ev_id = _ev_tmp()
            patch.evidence.append(Evidence(
                id=ev_id,
                kind="file",
                file_path=dockerfile_path,
                excerpt=f"Dockerfile found in directory '{svc_name}'",
            ))
            patch.nodes.append(NodeFact(
                id=node_id,
                type="service",
                name=svc_name,
                tags=["docker"],
                confidence="verified",
                evidence_ids=[ev_id],
            ))

        return patch

    def _parse_compose(
        self,
        content: str,
        compose_path: str,
        patch: GraphFactPatch,
        seen_ids: set[str],
    ) -> None:
        try:
            import yaml  # PyYAML is in requirements.txt
            data = yaml.safe_load(content)
        except Exception:
            return

        services = data.get("services") if isinstance(data, dict) else None
        if not isinstance(services, dict):
            return

        lines = content.splitlines()

        for svc_name, svc_cfg in services.items():
            node_id = make_node_id(str(svc_name))
            if node_id in seen_ids:
                continue
            seen_ids.add(node_id)

            # Find the line number for evidence
            svc_line = next(
                (i + 1 for i, l in enumerate(lines) if re.match(rf"^\s+{re.escape(str(svc_name))}\s*:", l)),
                None,
            )

            ev_id = _ev_tmp()
            patch.evidence.append(Evidence(
                id=ev_id,
                kind="file",
                file_path=compose_path,
                start_line=svc_line,
                end_line=svc_line,
                excerpt=f"  {svc_name}:",
            ))

            # Determine if it's a worker
            node_type: str = "service"
            command = ""
            if isinstance(svc_cfg, dict):
                cmd = svc_cfg.get("command", "")
                command = str(cmd).lower() if cmd else ""
            if any(kw in command for kw in ("celery", "worker", "consumer")):
                node_type = "worker"

            patch.nodes.append(NodeFact(
                id=node_id,
                type=node_type,  # type: ignore[arg-type]
                name=str(svc_name),
                tags=["docker"],
                confidence="verified",
                evidence_ids=[ev_id],
            ))
