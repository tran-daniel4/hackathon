import type {
  DiagramLayout,
  EdgeLayout,
  GroupLayout,
  NodeLayout,
  RawEdge,
  RawGroup,
  RawNode,
} from "./types";

const MIN_NODE_W = 172;
const MAX_NODE_W = 300;
const NODE_GAP_Y = 16;
const NODE_HARD_MIN = 92;
const GRP_PAD_X = 20;
const GRP_PAD_TOP = 46;
const GRP_PAD_BOT = 20;
const GRP_GAP = 36;
const COL_GAP = 96;
const ROW_GAP = 22;
const PAD = 42;
const MIN_HEIGHT = 420;

const LAYER_ORDER = ["presentation", "external", "application", "data", "infra"];
const ASYNC_RE = /event|async|publish|subscribe|queue|emit/i;

const EDGE_COLORS: Record<string, string> = {
  frontend: "#3b82f6",
  backend: "#06b6d4",
  database: "#eab308",
  cache: "#f97316",
  queue: "#a855f7",
  worker: "#22c55e",
  external: "#94a3b8",
};

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function longestTokenLength(text: string): number {
  return text
    .split(/\s+/)
    .reduce((max, token) => Math.max(max, token.length), 0);
}

function estimateWrappedLines(text: string | undefined, charsPerLine: number): number {
  if (!text) return 0;
  const normalized = text.replace(/\s+/g, " ").trim();
  if (!normalized) return 0;

  let lines = 0;
  for (const paragraph of normalized.split("\n")) {
    const words = paragraph.split(/\s+/).filter(Boolean);
    if (words.length === 0) {
      lines += 1;
      continue;
    }

    let current = 0;
    for (const word of words) {
      if (current === 0) {
        current = word.length;
        continue;
      }
      if (current + 1 + word.length <= charsPerLine) {
        current += 1 + word.length;
      } else {
        lines += 1;
        current = word.length;
      }
    }
    if (current > 0) lines += 1;
  }
  return Math.max(lines, 1);
}

function measureNode(node: RawNode): Pick<NodeLayout, "width" | "height"> {
  const label = node.label.trim();
  const description = node.description?.trim() ?? "";
  const longestWord = Math.max(longestTokenLength(label), longestTokenLength(description));
  const contentWidth = Math.max(
    MIN_NODE_W,
    118 + label.length * 3.6,
    description ? 188 + Math.min(description.length * 0.55, 92) : 0,
    longestWord * 8.4 + 76,
  );
  const width = clamp(Math.ceil(contentWidth), MIN_NODE_W, MAX_NODE_W);
  const labelLines = estimateWrappedLines(label, Math.max(14, Math.floor((width - 76) / 7.1)));
  const descriptionLines = estimateWrappedLines(description, Math.max(18, Math.floor((width - 30) / 6.2)));

  const iconRowHeight = Math.max(34, labelLines * 16 + 8);
  const footerHeight = 18;
  const descriptionHeight = descriptionLines > 0 ? descriptionLines * 13 + 10 : 0;
  const height = Math.max(NODE_HARD_MIN, 20 + iconRowHeight + footerHeight + descriptionHeight + 12);

  return { width, height };
}

function getColumnKey(node: RawNode): string {
  return node.group ?? node.layer ?? node.type ?? "application";
}

function distributedOffset(index: number, count: number, spacing: number): number {
  if (count <= 1) return 0;
  return (index - (count - 1) / 2) * spacing;
}

function cubicGeometry(
  src: NodeLayout,
  tgt: NodeLayout,
  sourceIndex: number,
  sourceCount: number,
  targetIndex: number,
  targetCount: number,
) {
  const horizontal = Math.abs(src.x - tgt.x) >= Math.abs(src.y - tgt.y);

  if (horizontal) {
    const srcOnLeft = src.x <= tgt.x;
    const sx = srcOnLeft ? src.x + src.width : src.x;
    const tx = srcOnLeft ? tgt.x : tgt.x + tgt.width;
    const sy = src.y + src.height / 2 + distributedOffset(sourceIndex, sourceCount, 14);
    const ty = tgt.y + tgt.height / 2 + distributedOffset(targetIndex, targetCount, 14);
    const dx = tx - sx;
    const bend = Math.max(56, Math.abs(dx) * 0.34);
    const lane = distributedOffset(sourceIndex, sourceCount, 18) * 0.5 + distributedOffset(targetIndex, targetCount, 18) * 0.35;
    const c1x = sx + (srcOnLeft ? bend : -bend);
    const c2x = tx - (srcOnLeft ? bend : -bend);
    const c1y = sy + lane;
    const c2y = ty - lane;
    return { sx, sy, c1x, c1y, c2x, c2y, tx, ty };
  }

  const srcOnTop = src.y <= tgt.y;
  const sy = srcOnTop ? src.y + src.height : src.y;
  const ty = srcOnTop ? tgt.y : tgt.y + tgt.height;
  const sx = src.x + src.width / 2 + distributedOffset(sourceIndex, sourceCount, 18);
  const tx = tgt.x + tgt.width / 2 + distributedOffset(targetIndex, targetCount, 18);
  const dy = ty - sy;
  const bend = Math.max(48, Math.abs(dy) * 0.34);
  const lane = distributedOffset(sourceIndex, sourceCount, 12) * 0.45 + distributedOffset(targetIndex, targetCount, 12) * 0.3;
  const c1x = sx + lane;
  const c2x = tx - lane;
  const c1y = sy + (srcOnTop ? bend : -bend);
  const c2y = ty - (srcOnTop ? bend : -bend);
  return { sx, sy, c1x, c1y, c2x, c2y, tx, ty };
}

function cubicPath(points: ReturnType<typeof cubicGeometry>): string {
  return `M ${points.sx},${points.sy} C ${points.c1x},${points.c1y} ${points.c2x},${points.c2y} ${points.tx},${points.ty}`;
}

function edgeLabelPos(points: ReturnType<typeof cubicGeometry>) {
  const t = 0.5;
  const inv = 1 - t;
  const x =
    inv * inv * inv * points.sx +
    3 * inv * inv * t * points.c1x +
    3 * inv * t * t * points.c2x +
    t * t * t * points.tx;
  const y =
    inv * inv * inv * points.sy +
    3 * inv * inv * t * points.c1y +
    3 * inv * t * t * points.c2y +
    t * t * t * points.ty;
  return { labelX: x, labelY: y };
}

export function computeLayout(nodes: RawNode[], rawEdges: RawEdge[], rawGroups?: RawGroup[]): DiagramLayout {
  if (nodes.length === 0) return { nodes: [], edges: [], groups: [], width: 0, height: 0 };

  const hasGroups = rawGroups && rawGroups.length > 0;
  return hasGroups ? computeGroupedLayout(nodes, rawEdges, rawGroups!) : computeLayerLayout(nodes, rawEdges);
}

function computeGroupedLayout(nodes: RawNode[], rawEdges: RawEdge[], rawGroups: RawGroup[]): DiagramLayout {
  const groupDefs = new Map(rawGroups.map((group) => [group.id, group]));
  const measured = new Map(nodes.map((node) => [node.id, { ...measureNode(node) }]));

  const columnOrder: string[] = rawGroups.map((group) => group.id);
  for (const node of nodes) {
    const key = getColumnKey(node);
    if (!columnOrder.includes(key)) columnOrder.push(key);
  }

  const columns = new Map<string, RawNode[]>(columnOrder.map((key) => [key, []]));
  for (const node of nodes) {
    columns.get(getColumnKey(node))!.push(node);
  }

  const activeColumns = columnOrder.filter((key) => (columns.get(key)?.length ?? 0) > 0);
  const columnWidths = new Map<string, number>();
  const columnHeights = new Map<string, number>();

  for (const key of activeColumns) {
    const columnNodes = columns.get(key)!;
    const innerWidth = Math.max(...columnNodes.map((node) => measured.get(node.id)!.width));
    const stackedHeight = columnNodes.reduce((sum, node, index) => {
      const size = measured.get(node.id)!;
      return sum + size.height + (index > 0 ? NODE_GAP_Y : 0);
    }, 0);
    columnWidths.set(key, innerWidth + GRP_PAD_X * 2);
    columnHeights.set(key, GRP_PAD_TOP + stackedHeight + GRP_PAD_BOT);
  }

  const maxH = Math.max(...activeColumns.map((key) => columnHeights.get(key)!), MIN_HEIGHT - PAD * 2);
  const canvasH = PAD * 2 + maxH;
  const canvasW =
    PAD * 2 +
    activeColumns.reduce((sum, key) => sum + columnWidths.get(key)!, 0) +
    Math.max(0, activeColumns.length - 1) * GRP_GAP;

  const positionedNodes: NodeLayout[] = [];
  const groupLayouts: GroupLayout[] = [];
  const posMap = new Map<string, NodeLayout>();

  let cursorX = PAD;
  for (const key of activeColumns) {
    const containerW = columnWidths.get(key)!;
    const containerH = columnHeights.get(key)!;
    const containerY = (canvasH - containerH) / 2;
    const group = groupDefs.get(key);

    groupLayouts.push({
      id: key,
      label: group?.label ?? key,
      x: cursorX,
      y: containerY,
      width: containerW,
      height: containerH,
    });

    let cursorY = containerY + GRP_PAD_TOP;
    const innerWidth = containerW - GRP_PAD_X * 2;
    for (const node of columns.get(key)!) {
      const size = measured.get(node.id)!;
      const positioned: NodeLayout = {
        ...node,
        x: cursorX + GRP_PAD_X + (innerWidth - size.width) / 2,
        y: cursorY,
        width: size.width,
        height: size.height,
      };
      posMap.set(node.id, positioned);
      positionedNodes.push(positioned);
      cursorY += size.height + NODE_GAP_Y;
    }

    cursorX += containerW + GRP_GAP;
  }

  return {
    nodes: positionedNodes,
    edges: buildEdges(rawEdges, posMap),
    groups: groupLayouts,
    width: canvasW,
    height: canvasH,
  };
}

function computeLayerLayout(nodes: RawNode[], rawEdges: RawEdge[]): DiagramLayout {
  const measured = new Map(nodes.map((node) => [node.id, { ...measureNode(node) }]));
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

  const columnWidths = new Map<string, number>();
  let maxColumnHeight = 0;
  for (const layer of sortedLayers) {
    const layerNodes = layerGroups.get(layer)!;
    const width = Math.max(...layerNodes.map((node) => measured.get(node.id)!.width));
    const height = layerNodes.reduce((sum, node, index) => {
      const size = measured.get(node.id)!;
      return sum + size.height + (index > 0 ? ROW_GAP : 0);
    }, 0);
    columnWidths.set(layer, width);
    maxColumnHeight = Math.max(maxColumnHeight, height);
  }

  const canvasH = Math.max(PAD * 2 + maxColumnHeight, MIN_HEIGHT);
  const canvasW =
    PAD * 2 +
    sortedLayers.reduce((sum, layer) => sum + columnWidths.get(layer)!, 0) +
    Math.max(0, sortedLayers.length - 1) * COL_GAP;

  const positionedNodes: NodeLayout[] = [];
  const posMap = new Map<string, NodeLayout>();
  let cursorX = PAD;

  for (const layer of sortedLayers) {
    const layerNodes = layerGroups.get(layer)!;
    const columnWidth = columnWidths.get(layer)!;
    const totalHeight = layerNodes.reduce((sum, node, index) => {
      const size = measured.get(node.id)!;
      return sum + size.height + (index > 0 ? ROW_GAP : 0);
    }, 0);
    let cursorY = (canvasH - totalHeight) / 2;

    for (const node of layerNodes) {
      const size = measured.get(node.id)!;
      const positioned: NodeLayout = {
        ...node,
        x: cursorX + (columnWidth - size.width) / 2,
        y: cursorY,
        width: size.width,
        height: size.height,
      };
      posMap.set(node.id, positioned);
      positionedNodes.push(positioned);
      cursorY += size.height + ROW_GAP;
    }

    cursorX += columnWidth + COL_GAP;
  }

  return {
    nodes: positionedNodes,
    edges: buildEdges(rawEdges, posMap),
    groups: [],
    width: canvasW,
    height: canvasH,
  };
}

function buildEdges(rawEdges: RawEdge[], posMap: Map<string, NodeLayout>): EdgeLayout[] {
  const validEdges = rawEdges.filter((edge) => posMap.has(edge.source) && posMap.has(edge.target));
  const sourceBuckets = new Map<string, RawEdge[]>();
  const targetBuckets = new Map<string, RawEdge[]>();

  for (const edge of validEdges) {
    if (!sourceBuckets.has(edge.source)) sourceBuckets.set(edge.source, []);
    if (!targetBuckets.has(edge.target)) targetBuckets.set(edge.target, []);
    sourceBuckets.get(edge.source)!.push(edge);
    targetBuckets.get(edge.target)!.push(edge);
  }

  return validEdges.map((edge) => {
    const src = posMap.get(edge.source)!;
    const tgt = posMap.get(edge.target)!;
    const sourceGroup = sourceBuckets.get(edge.source)!;
    const targetGroup = targetBuckets.get(edge.target)!;
    const sourceIndex = sourceGroup.findIndex((candidate) => candidate.id === edge.id);
    const targetIndex = targetGroup.findIndex((candidate) => candidate.id === edge.id);
    const points = cubicGeometry(src, tgt, sourceIndex, sourceGroup.length, targetIndex, targetGroup.length);
    const label = edge.label?.trim() || undefined;
    const { labelX, labelY } = edgeLabelPos(points);

    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label,
      isAsync: ASYNC_RE.test(label ?? ""),
      d: cubicPath(points),
      color: EDGE_COLORS[src.type] ?? "#94a3b8",
      labelX,
      labelY,
      confidence: edge.confidence,
      ...points,
      sourceSeverity: src.severity ?? null,
      targetSeverity: tgt.severity ?? null,
    };
  });
}
