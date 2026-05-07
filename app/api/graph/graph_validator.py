from graph.models import GraphFacts, WarningFact


class GraphValidator:
    def validate(self, facts: GraphFacts) -> list[WarningFact]:
        warnings: list[WarningFact] = []
        node_ids = {n.id for n in facts.nodes}
        evidence_ids = {e.id for e in facts.evidence}

        # Dangling edges
        for edge in facts.edges:
            if edge.src not in node_ids:
                warnings.append(WarningFact(
                    code="DANGLING_EDGE",
                    message=f"Edge '{edge.id}' src '{edge.src}' references unknown node",
                ))
            if edge.dst not in node_ids:
                warnings.append(WarningFact(
                    code="DANGLING_EDGE",
                    message=f"Edge '{edge.id}' dst '{edge.dst}' references unknown node",
                ))

        # Dangling evidence refs
        all_facts_with_evidence = (
            list(facts.nodes)
            + list(facts.edges)
            + list(facts.apis)
            + list(facts.data_resources)
            + list(facts.messaging)
        )
        for fact in all_facts_with_evidence:
            for eid in fact.evidence_ids:
                if eid not in evidence_ids:
                    warnings.append(WarningFact(
                        code="DANGLING_EVIDENCE_REF",
                        message=f"Fact '{getattr(fact, 'id', '?')}' references unknown evidence '{eid}'",
                    ))

        # Duplicate IDs (safety net)
        for collection, label in [
            (facts.nodes, "node"),
            (facts.edges, "edge"),
            (facts.apis, "api"),
            (facts.data_resources, "data_resource"),
            (facts.messaging, "messaging"),
        ]:
            seen: set[str] = set()
            for item in collection:
                if item.id in seen:
                    warnings.append(WarningFact(
                        code="DUPLICATE_ID",
                        message=f"Duplicate {label} ID '{item.id}'",
                    ))
                seen.add(item.id)

        return warnings
