import type { RawDiagram, RawNode, RawEdge, RawGroup, ViewId } from "./types";

export interface TransformedView {
  nodes: RawNode[];
  edges: RawEdge[];
  groups: RawGroup[];
  label: string;
  annotations: unknown[];
}

export function transformView(diagrams: RawDiagram[], viewId: ViewId): TransformedView | null {
  const diagram = diagrams.find(d => d.id === viewId);
  if (!diagram) return null;
  const nodes = viewId === "component"
    ? orderNodesByRequestFlow(diagram.nodes, diagram.edges, diagram.annotations ?? [])
    : diagram.nodes;
  return {
    nodes,
    edges: diagram.edges,
    groups: diagram.groups ?? [],
    label: diagram.label,
    annotations: diagram.annotations ?? [],
  };
}

interface RequestFlowSegment {
  edgeId: string;
  reverse?: boolean;
}

interface RequestFlowAnnotation {
  kind?: string;
  segments?: RequestFlowSegment[];
}

function orderNodesByRequestFlow(nodes: RawNode[], edges: RawEdge[], annotations: unknown[]): RawNode[] {
  if (!annotations.length || nodes.length <= 2) return nodes;

  const edgeById = new Map(edges.map((edge) => [edge.id, edge]));
  const rankByNode = new Map<string, number>();
  const countByNode = new Map<string, number>();

  annotations.forEach((annotation) => {
    if (!annotation || typeof annotation !== "object") return;
    const candidate = annotation as RequestFlowAnnotation;
    if (candidate.kind !== "request_flow" || !Array.isArray(candidate.segments)) return;

    let step = 0;
    candidate.segments.forEach((segment) => {
      const edge = edgeById.get(segment.edgeId);
      if (!edge) return;
      const sourceId = segment.reverse ? edge.target : edge.source;
      const targetId = segment.reverse ? edge.source : edge.target;

      for (const nodeId of [sourceId, targetId]) {
        const currentRank = rankByNode.get(nodeId);
        if (currentRank === undefined || step < currentRank) {
          rankByNode.set(nodeId, step);
        }
        countByNode.set(nodeId, (countByNode.get(nodeId) ?? 0) + 1);
        step += 1;
      }
    });
  });

  const severityScore = (severity?: RawNode["severity"]) => {
    if (severity === "high") return 0;
    if (severity === "medium") return 1;
    if (severity === "low") return 2;
    return 3;
  };

  return [...nodes].sort((a, b) => {
    const rankA = rankByNode.get(a.id) ?? Number.POSITIVE_INFINITY;
    const rankB = rankByNode.get(b.id) ?? Number.POSITIVE_INFINITY;
    if (rankA !== rankB) return rankA - rankB;

    const countA = countByNode.get(a.id) ?? 0;
    const countB = countByNode.get(b.id) ?? 0;
    if (countA !== countB) return countB - countA;

    const severityA = severityScore(a.severity ?? undefined);
    const severityB = severityScore(b.severity ?? undefined);
    if (severityA !== severityB) return severityA - severityB;

    return a.label.localeCompare(b.label);
  });
}
