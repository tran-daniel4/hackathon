import type { RawNode, RawEdge, RawGroup, NodeLayout, EdgeLayout, GroupLayout, DiagramLayout } from "./types";

const NODE_W = 164;
const NODE_H = 90;
// Group container padding
const GRP_PAD_X  = 20;   // horizontal padding inside container
const GRP_PAD_TOP = 44;  // vertical padding at top (room for title)
const GRP_PAD_BOT = 20;  // vertical padding at bottom
const GRP_GAP    = 28;   // horizontal gap between group containers
// Legacy layer-based constants (used when no groups provided)
const COL_GAP    = 88;
const ROW_GAP    = 18;
const PAD        = 48;
const MIN_HEIGHT = 420;

const LAYER_ORDER = ["presentation", "external", "application", "data", "infra"];

const ASYNC_RE = /event|async|publish|subscribe|queue|emit/i;

const EDGE_COLORS: Record<string, string> = {
  frontend: "#3b82f6",
  backend:  "#06b6d4",
  database: "#eab308",
  cache:    "#f97316",
  queue:    "#a855f7",
  worker:   "#22c55e",
  external: "#6b7280",
};

function getColumnKey(node: RawNode): string {
  return node.group ?? node.layer ?? node.type ?? "application";
}

function cubicPath(sx: number, sy: number, tx: number, ty: number): string {
  const dx = tx - sx;
  if (Math.abs(dx) > 24) {
    const cp1x = sx + dx * 0.45;
    const cp2x = tx - dx * 0.45;
    return `M ${sx},${sy} C ${cp1x},${sy} ${cp2x},${ty} ${tx},${ty}`;
  }
  const offset = 60;
  return `M ${sx},${sy} C ${sx + offset},${sy} ${tx + offset},${ty} ${tx},${ty}`;
}

function anchors(src: NodeLayout, tgt: NodeLayout) {
  const threshold = 24;
  if (src.x < tgt.x - threshold) {
    return { sx: src.x + NODE_W, sy: src.y + NODE_H / 2, tx: tgt.x, ty: tgt.y + NODE_H / 2 };
  }
  if (src.x > tgt.x + threshold) {
    return { sx: src.x, sy: src.y + NODE_H / 2, tx: tgt.x + NODE_W, ty: tgt.y + NODE_H / 2 };
  }
  const below = src.y < tgt.y;
  return {
    sx: src.x + NODE_W * 0.5, sy: src.y + (below ? NODE_H : 0),
    tx: tgt.x + NODE_W * 0.5, ty: tgt.y + (below ? 0 : NODE_H),
  };
}

function edgeLabelPos(sx: number, sy: number, tx: number, ty: number): { labelX: number; labelY: number } {
  // Midpoint of the cubic bezier S-curve is (sx+tx)/2, (sy+ty)/2
  return { labelX: (sx + tx) / 2, labelY: (sy + ty) / 2 };
}

export function computeLayout(nodes: RawNode[], rawEdges: RawEdge[], rawGroups?: RawGroup[]): DiagramLayout {
  if (nodes.length === 0) return { nodes: [], edges: [], groups: [], width: 0, height: 0 };

  const hasGroups = rawGroups && rawGroups.length > 0;

  if (hasGroups) {
    return computeGroupedLayout(nodes, rawEdges, rawGroups!);
  }
  return computeLayerLayout(nodes, rawEdges);
}

// ── Group-based column layout ─────────────────────────────────────────────────

function computeGroupedLayout(nodes: RawNode[], rawEdges: RawEdge[], rawGroups: RawGroup[]): DiagramLayout {
  const groupDefs = new Map(rawGroups.map(g => [g.id, g]));

  // Build ordered column list from group definitions
  const columnOrder: string[] = rawGroups.map(g => g.id);
  // Append any nodes whose column key isn't in the group list
  for (const node of nodes) {
    const key = getColumnKey(node);
    if (!columnOrder.includes(key)) columnOrder.push(key);
  }

  // Assign nodes to columns
  const columns = new Map<string, RawNode[]>(columnOrder.map(k => [k, []]));
  for (const node of nodes) {
    const key = getColumnKey(node);
    columns.get(key)!.push(node);
  }

  // Drop empty columns
  const activeColumns = columnOrder.filter(k => (columns.get(k)?.length ?? 0) > 0);

  // Container dimensions
  const containerW = NODE_W + 2 * GRP_PAD_X;
  const containerH = (colKey: string) => {
    const count = columns.get(colKey)!.length;
    return GRP_PAD_TOP + count * NODE_H + Math.max(0, count - 1) * 14 + GRP_PAD_BOT;
  };

  const maxH = Math.max(...activeColumns.map(containerH), MIN_HEIGHT - PAD * 2);
  const canvasH = PAD * 2 + maxH;
  const canvasW = PAD * 2 + activeColumns.length * containerW + Math.max(0, activeColumns.length - 1) * GRP_GAP;

  const posMap = new Map<string, NodeLayout>();
  const positionedNodes: NodeLayout[] = [];
  const groupLayouts: GroupLayout[] = [];

  activeColumns.forEach((colKey, colIdx) => {
    const colNodes = columns.get(colKey)!;
    const cH = containerH(colKey);
    const containerX = PAD + colIdx * (containerW + GRP_GAP);
    const containerY = (canvasH - cH) / 2;

    const groupDef = groupDefs.get(colKey);
    groupLayouts.push({
      id: colKey,
      label: groupDef?.label ?? colKey,
      x: containerX,
      y: containerY,
      width: containerW,
      height: cH,
    });

    colNodes.forEach((node, rowIdx) => {
      const nl: NodeLayout = {
        ...node,
        x: containerX + GRP_PAD_X,
        y: containerY + GRP_PAD_TOP + rowIdx * (NODE_H + 14),
        width: NODE_W,
        height: NODE_H,
      };
      posMap.set(node.id, nl);
      positionedNodes.push(nl);
    });
  });

  const positionedEdges = buildEdges(rawEdges, posMap);
  return { nodes: positionedNodes, edges: positionedEdges, groups: groupLayouts, width: canvasW, height: canvasH };
}

// ── Legacy layer-based column layout (no groups) ──────────────────────────────

function computeLayerLayout(nodes: RawNode[], rawEdges: RawEdge[]): DiagramLayout {
  const layerGroups = new Map<string, RawNode[]>();
  for (const node of nodes) {
    const key = node.layer ?? node.type ?? "application";
    if (!layerGroups.has(key)) layerGroups.set(key, []);
    layerGroups.get(key)!.push(node);
  }

  const sortedLayers = [...layerGroups.keys()].sort((a, b) => {
    const ai = LAYER_ORDER.indexOf(a);
    const bi = LAYER_ORDER.indexOf(b);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  const maxCount = Math.max(...sortedLayers.map(l => layerGroups.get(l)!.length));
  const rawH = PAD * 2 + maxCount * NODE_H + Math.max(0, maxCount - 1) * ROW_GAP;
  const canvasH = Math.max(rawH, MIN_HEIGHT);
  const canvasW = PAD * 2 + sortedLayers.length * NODE_W + Math.max(0, sortedLayers.length - 1) * COL_GAP;

  const posMap = new Map<string, NodeLayout>();
  const positionedNodes: NodeLayout[] = [];

  sortedLayers.forEach((layer, colIdx) => {
    const layerNodes = layerGroups.get(layer)!;
    const colX = PAD + colIdx * (NODE_W + COL_GAP);
    const totalH = layerNodes.length * NODE_H + Math.max(0, layerNodes.length - 1) * ROW_GAP;
    const startY = (canvasH - totalH) / 2;

    layerNodes.forEach((node, rowIdx) => {
      const nl: NodeLayout = {
        ...node,
        x: colX,
        y: startY + rowIdx * (NODE_H + ROW_GAP),
        width: NODE_W,
        height: NODE_H,
      };
      posMap.set(node.id, nl);
      positionedNodes.push(nl);
    });
  });

  const positionedEdges = buildEdges(rawEdges, posMap);
  return { nodes: positionedNodes, edges: positionedEdges, groups: [], width: canvasW, height: canvasH };
}

// ── Shared edge builder ───────────────────────────────────────────────────────

function buildEdges(rawEdges: RawEdge[], posMap: Map<string, NodeLayout>): EdgeLayout[] {
  return rawEdges
    .filter(e => posMap.has(e.source) && posMap.has(e.target))
    .map(e => {
      const src = posMap.get(e.source)!;
      const tgt = posMap.get(e.target)!;
      const { sx, sy, tx, ty } = anchors(src, tgt);
      const { labelX, labelY } = edgeLabelPos(sx, sy, tx, ty);
      return {
        id: e.id,
        source: e.source,
        target: e.target,
        label: e.label,
        isAsync: ASYNC_RE.test(e.label ?? ""),
        d: cubicPath(sx, sy, tx, ty),
        color: EDGE_COLORS[src.type] ?? "#6b7280",
        labelX,
        labelY,
        confidence: e.confidence,
      };
    });
}
