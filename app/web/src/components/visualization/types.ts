export type NodeType = "frontend" | "backend" | "database" | "cache" | "queue" | "worker" | "external";
export type LayerType = "presentation" | "application" | "data" | "external" | "infra";
export type SeverityType = "high" | "medium" | "low";
export type ViewId = "system_context" | "conceptual" | "component" | "operational";

export interface RawGroup {
  id: string;
  label: string;
  type?: string;
}

export interface RawNode {
  id: string;
  label: string;
  type: NodeType;
  layer?: LayerType;
  group?: string;
  severity?: SeverityType | null;
  description?: string;
}

export interface RawEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  confidence?: "verified" | "inferred";
}

export interface RawDiagram {
  id: ViewId;
  label: string;
  nodes: RawNode[];
  edges: RawEdge[];
  groups?: RawGroup[];
  annotations?: unknown[];
}

// 2D layout output — nodes with computed pixel positions
export interface NodeLayout extends RawNode {
  x: number;
  y: number;
  width: number;
  height: number;
}

// 2D layout output — group containers with computed pixel positions
export interface GroupLayout {
  id: string;
  label: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

// 2D layout output — edges with computed SVG path
export interface EdgeLayout {
  id: string;
  source: string;
  target: string;
  label?: string;
  isAsync: boolean;
  d: string;
  color: string;
  labelX: number;
  labelY: number;
  confidence?: "verified" | "inferred";
}

export interface DiagramLayout {
  nodes: NodeLayout[];
  edges: EdgeLayout[];
  groups: GroupLayout[];
  width: number;
  height: number;
}
