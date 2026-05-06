import type { RawDiagram, RawNode, RawEdge, RawGroup, ViewId } from "./types";

export interface TransformedView {
  nodes: RawNode[];
  edges: RawEdge[];
  groups: RawGroup[];
  label: string;
}

export function transformView(diagrams: RawDiagram[], viewId: ViewId): TransformedView | null {
  const diagram = diagrams.find(d => d.id === viewId);
  if (!diagram) return null;
  return {
    nodes: diagram.nodes,
    edges: diagram.edges,
    groups: diagram.groups ?? [],
    label: diagram.label,
  };
}
