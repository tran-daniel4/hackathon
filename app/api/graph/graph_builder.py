import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Optional

from graph.models import (
    GraphFactPatch, GraphFacts, RepoMeta,
    NodeFact, EdgeFact, ApiFact, DataResourceFact, MessagingFact, Evidence, WarningFact,
)
from graph.graph_validator import GraphValidator


class GraphBuilder:
    def build(
        self,
        patches: list[GraphFactPatch],
        analysis_id: Optional[str] = None,
        repo_meta: Optional[dict] = None,
    ) -> GraphFacts:
        if analysis_id is None:
            analysis_id = str(uuid.uuid4())

        nodes: OrderedDict[str, NodeFact] = OrderedDict()
        edges: OrderedDict[str, EdgeFact] = OrderedDict()
        apis: OrderedDict[str, ApiFact] = OrderedDict()
        data_resources: OrderedDict[str, DataResourceFact] = OrderedDict()
        messaging: OrderedDict[str, MessagingFact] = OrderedDict()
        raw_evidence: list[Evidence] = []
        warnings: list[WarningFact] = []

        for patch in patches:
            for item in patch.nodes:
                if item.id not in nodes:
                    nodes[item.id] = item
            for item in patch.edges:
                if item.id not in edges:
                    edges[item.id] = item
            for item in patch.apis:
                if item.id not in apis:
                    apis[item.id] = item
            for item in patch.data_resources:
                if item.id not in data_resources:
                    data_resources[item.id] = item
            for item in patch.messaging:
                if item.id not in messaging:
                    messaging[item.id] = item
            raw_evidence.extend(patch.evidence)
            warnings.extend(patch.warnings)

        # Rewrite evidence IDs to stable sequential form and remap references
        id_remap: dict[str, str] = {}
        final_evidence: list[Evidence] = []
        for i, ev in enumerate(raw_evidence, start=1):
            new_id = f"ev_{i:03d}"
            id_remap[ev.id] = new_id
            final_evidence.append(ev.model_copy(update={"id": new_id}))

        def remap_ids(ids: list[str]) -> list[str]:
            return [id_remap.get(eid, eid) for eid in ids]

        remapped_nodes = [n.model_copy(update={"evidence_ids": remap_ids(n.evidence_ids)}) for n in nodes.values()]
        remapped_edges = [e.model_copy(update={"evidence_ids": remap_ids(e.evidence_ids)}) for e in edges.values()]
        remapped_apis = [a.model_copy(update={"evidence_ids": remap_ids(a.evidence_ids)}) for a in apis.values()]
        remapped_dr = [d.model_copy(update={"evidence_ids": remap_ids(d.evidence_ids)}) for d in data_resources.values()]
        remapped_msg = [m.model_copy(update={"evidence_ids": remap_ids(m.evidence_ids)}) for m in messaging.values()]

        repo = RepoMeta(
            name=repo_meta.get("name", "unknown") if repo_meta else "unknown",
            url=repo_meta.get("url") if repo_meta else None,
            branch=repo_meta.get("branch") if repo_meta else None,
            commit_sha=repo_meta.get("commit_sha") if repo_meta else None,
            analyzed_at=repo_meta.get("analyzed_at", datetime.now(timezone.utc).isoformat()) if repo_meta else datetime.now(timezone.utc).isoformat(),
        )

        facts = GraphFacts(
            analysis_id=analysis_id,
            repo=repo,
            nodes=remapped_nodes,
            edges=remapped_edges,
            apis=remapped_apis,
            data_resources=remapped_dr,
            messaging=remapped_msg,
            evidence=final_evidence,
            warnings=warnings,
        )

        validation_warnings = GraphValidator().validate(facts)
        facts.warnings.extend(validation_warnings)

        return facts
