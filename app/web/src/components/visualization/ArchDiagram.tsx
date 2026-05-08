"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { AlertCircle } from "lucide-react";
import { transformView } from "./viewTransformer";
import { computeLayout } from "./layoutEngine";
import { DiagramNode } from "./DiagramNode";
import { DiagramEdge } from "./DiagramEdge";
import type { EdgeLayout, RawDiagram, ViewId } from "./types";

interface ArchDiagramProps {
  diagrams: RawDiagram[];
  viewId: ViewId;
}

interface OrbState {
  id: string;
  flowIndex: number;
  segmentIndex: number;
  progress: number;
  isBottleneck: boolean;
}

interface RequestFlowSegment {
  edgeId: string;
  reverse: boolean;
}

interface RequestFlowAnnotation {
  kind: "request_flow";
  flowId?: string;
  label?: string;
  componentId?: string;
  routeId?: string;
  bottleneck?: boolean;
  segments: RequestFlowSegment[];
}

const GROUP_PALETTE: Record<string, { fill: string; stroke: string; title: string }> = {
  frontend: { fill: "rgba(59,130,246,0.06)", stroke: "rgba(59,130,246,0.28)", title: "#3b82f6" },
  gateway: { fill: "rgba(6,182,212,0.06)", stroke: "rgba(6,182,212,0.28)", title: "#06b6d4" },
  core: { fill: "rgba(99,102,241,0.06)", stroke: "rgba(99,102,241,0.28)", title: "#818cf8" },
  supporting: { fill: "rgba(168,85,247,0.06)", stroke: "rgba(168,85,247,0.28)", title: "#a855f7" },
  external: { fill: "rgba(107,114,128,0.05)", stroke: "rgba(107,114,128,0.22)", title: "#9ca3af" },
  data: { fill: "rgba(234,179,8,0.06)", stroke: "rgba(234,179,8,0.28)", title: "#eab308" },
  users: { fill: "rgba(59,130,246,0.06)", stroke: "rgba(59,130,246,0.28)", title: "#3b82f6" },
  capabilities: { fill: "rgba(99,102,241,0.06)", stroke: "rgba(99,102,241,0.28)", title: "#818cf8" },
  external_partners: { fill: "rgba(107,114,128,0.05)", stroke: "rgba(107,114,128,0.22)", title: "#9ca3af" },
  gaps: { fill: "rgba(239,68,68,0.05)", stroke: "rgba(239,68,68,0.22)", title: "#f87171" },
  actors: { fill: "rgba(59,130,246,0.06)", stroke: "rgba(59,130,246,0.28)", title: "#3b82f6" },
  system: { fill: "rgba(99,102,241,0.06)", stroke: "rgba(99,102,241,0.28)", title: "#818cf8" },
  partners: { fill: "rgba(107,114,128,0.05)", stroke: "rgba(107,114,128,0.22)", title: "#9ca3af" },
  identity: { fill: "rgba(249,115,22,0.05)", stroke: "rgba(249,115,22,0.22)", title: "#fb923c" },
  cicd: { fill: "rgba(34,197,94,0.05)", stroke: "rgba(34,197,94,0.22)", title: "#4ade80" },
  runtime: { fill: "rgba(6,182,212,0.06)", stroke: "rgba(6,182,212,0.28)", title: "#06b6d4" },
  services: { fill: "rgba(99,102,241,0.06)", stroke: "rgba(99,102,241,0.28)", title: "#818cf8" },
  observability: { fill: "rgba(234,179,8,0.06)", stroke: "rgba(234,179,8,0.28)", title: "#eab308" },
};

const DYNAMIC_ACCENTS: ReadonlyArray<[string, string, string]> = [
  ["#f472b6", "rgba(244,114,182,0.06)", "rgba(244,114,182,0.28)"],
  ["#34d399", "rgba(52,211,153,0.06)", "rgba(52,211,153,0.28)"],
  ["#fb923c", "rgba(251,146,60,0.06)", "rgba(251,146,60,0.28)"],
  ["#60a5fa", "rgba(96,165,250,0.06)", "rgba(96,165,250,0.28)"],
  ["#c084fc", "rgba(192,132,252,0.06)", "rgba(192,132,252,0.28)"],
  ["#2dd4bf", "rgba(45,212,191,0.06)", "rgba(45,212,191,0.28)"],
  ["#fbbf24", "rgba(251,191,36,0.06)", "rgba(251,191,36,0.28)"],
  ["#f87171", "rgba(248,113,113,0.06)", "rgba(248,113,113,0.28)"],
];

function getGroupPalette(groupId: string): { fill: string; stroke: string; title: string } {
  if (groupId in GROUP_PALETTE) return GROUP_PALETTE[groupId];
  let hash = 0;
  for (let i = 0; i < groupId.length; i++) {
    hash = (hash * 31 + groupId.charCodeAt(i)) & 0xffff;
  }
  const [title, fill, stroke] = DYNAMIC_ACCENTS[hash % DYNAMIC_ACCENTS.length];
  return { fill, stroke, title };
}

export function ArchDiagram({ diagrams, viewId }: ArchDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(0);
  const [orbs, setOrbs] = useState<OrbState[]>([]);

  const view = useMemo(() => transformView(diagrams, viewId), [diagrams, viewId]);
  const layout = useMemo(() => {
    if (!view || view.nodes.length === 0) return null;
    return computeLayout(view.nodes, view.edges, view.groups);
  }, [view]);
  const activeLayout = layout ?? { nodes: [], edges: [], groups: [], width: 0, height: 0 };

  useEffect(() => {
    if (!containerRef.current) return;
    const element = containerRef.current;
    const update = () => setContainerWidth(element.clientWidth);
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const svgH = Math.max(activeLayout.height, 420);
  const availableWidth = Math.max(containerWidth - 6, 1);
  const scale = activeLayout.width > 0 ? Math.min(1, availableWidth / activeLayout.width) : 1;
  const scaledHeight = Math.max(svgH * scale, 420);
  const edgeMap = useMemo(() => new Map(activeLayout.edges.map((edge) => [edge.id, edge])), [activeLayout.edges]);
  const requestFlows = useMemo(
    () => parseRequestFlows(view?.annotations ?? [], edgeMap),
    [edgeMap, view?.annotations],
  );
  const requestFlowEdgeWeights = useMemo(() => {
    const counts = new Map<string, number>();
    requestFlows.forEach((flow) => {
      flow.segments.forEach((segment) => {
        counts.set(segment.edgeId, (counts.get(segment.edgeId) ?? 0) + 1);
      });
    });
    return counts;
  }, [requestFlows]);

  const traversal = useMemo(() => {
    const outgoing = new Map<string, EdgeLayout[]>();
    const incomingCount = new Map<string, number>();
    const lengths = new Map<string, number>();

    for (const node of activeLayout.nodes) {
      incomingCount.set(node.id, 0);
    }

    for (const edge of activeLayout.edges) {
      if (!outgoing.has(edge.source)) outgoing.set(edge.source, []);
      outgoing.get(edge.source)!.push(edge);
      incomingCount.set(edge.target, (incomingCount.get(edge.target) ?? 0) + 1);
      lengths.set(edge.id, approximateBezierLength(edge));
    }

    for (const edges of outgoing.values()) {
      edges.sort((a, b) => {
        const aTarget = activeLayout.nodes.find((node) => node.id === a.target);
        const bTarget = activeLayout.nodes.find((node) => node.id === b.target);
        return (aTarget?.y ?? 0) - (bTarget?.y ?? 0);
      });
    }

    const candidateStarts = activeLayout.nodes
      .filter((node) => (incomingCount.get(node.id) ?? 0) === 0)
      .sort((a, b) => a.x - b.x || a.y - b.y);

    const preferredStarts = candidateStarts.filter((node) => node.type === "frontend" || node.type === "external");
    const rootNodes = preferredStarts.length > 0 ? preferredStarts : candidateStarts;
    const startEdges = rootNodes.flatMap((node) => outgoing.get(node.id) ?? []);

    const fallbackFlows = (startEdges.length > 0 ? startEdges : activeLayout.edges.slice(0, 1))
      .slice(0, Math.min(2, startEdges.length || activeLayout.edges.length || 0))
      .map((edge, index) => ({
        id: `fallback-${index}`,
        label: edge.label || edge.id,
        bottleneck: edge.sourceSeverity === "high" || edge.targetSeverity === "high",
        segments: buildFallbackSegments(edge, outgoing, 5),
      }))
      .filter((flow) => flow.segments.length > 0);

    return { lengths, fallbackFlows };
  }, [activeLayout.edges, activeLayout.nodes]);

  useEffect(() => {
    const activeFlows = requestFlows.length > 0 ? requestFlows : traversal.fallbackFlows;
    if (activeFlows.length === 0) {
      setOrbs([]);
      return;
    }

    let orbCounter = 0;
    const spawnFromFlows = (flows: typeof activeFlows) =>
      flows.map((flow, index) => ({
        id: `orb-${viewId}-${orbCounter++}`,
        flowIndex: index,
        segmentIndex: 0,
        progress: 0,
        isBottleneck: flow.bottleneck,
      }));

    setOrbs(spawnFromFlows(activeFlows.slice(0, Math.min(2, activeFlows.length))));

    const interval = window.setInterval(() => {
      setOrbs((previous) => {
        const next: OrbState[] = [];

        for (const orb of previous) {
          const flow = activeFlows[orb.flowIndex];
          const segment = flow?.segments[orb.segmentIndex];
          const edge = segment ? edgeMap.get(segment.edgeId) : null;
          if (!edge) continue;

          const length = traversal.lengths.get(edge.id) ?? 200;
          const segmentBottleneck = orb.isBottleneck || edge.sourceSeverity === "high" || edge.targetSeverity === "high";
          const pixelsPerTick = segmentBottleneck ? 4.2 : 6.8;
          const nextProgress = orb.progress + pixelsPerTick / Math.max(length, 60);

          if (nextProgress >= 1) {
            const nextSegmentIndex = orb.segmentIndex + 1;
            if (!flow || nextSegmentIndex >= flow.segments.length) {
              continue;
            }
            next.push({
              id: `orb-${viewId}-${orbCounter++}`,
              flowIndex: orb.flowIndex,
              segmentIndex: nextSegmentIndex,
              progress: 0,
              isBottleneck: flow.bottleneck,
            });
            continue;
          }

          next.push({ ...orb, progress: nextProgress });
        }

        if (next.length === 0) {
          return spawnFromFlows(activeFlows.slice(0, Math.min(2, activeFlows.length)));
        }
        return next;
      });
    }, 30);

    return () => window.clearInterval(interval);
  }, [edgeMap, requestFlows, traversal, viewId]);

  if (!layout) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3 border border-dashed border-white/10 bg-white/[0.01]">
        <AlertCircle className="w-5 h-5 text-white/20" />
        <div className="text-[11px] uppercase tracking-[0.2em] text-white/30">
          {view?.label ?? "This view"} could not be generated
        </div>
        <div className="text-[11px] text-white/20">Re-analyze the repository to retry</div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      style={{
        width: "100%",
        overflow: "hidden",
        background: "radial-gradient(ellipse at 40% 30%, #0e0e28 0%, #080812 70%)",
        borderRadius: 8,
        minHeight: scaledHeight,
      }}
    >
      <div
        style={{
          position: "relative",
          width: "100%",
          height: scaledHeight,
        }}
      >
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: activeLayout.width,
            height: svgH,
            transform: `scale(${scale})`,
            transformOrigin: "top left",
            backgroundImage: "radial-gradient(circle, rgba(255,255,255,0.035) 1px, transparent 1px)",
            backgroundSize: "28px 28px",
          }}
        >
          <svg
            width={activeLayout.width}
            height={svgH}
            style={{ position: "absolute", inset: 0, pointerEvents: "none", overflow: "visible" }}
          >
            <defs>
              <filter id="arch-edgeglow" x="-60%" y="-60%" width="220%" height="220%">
                <feGaussianBlur stdDeviation="2.5" result="blur" />
                <feMerge>
                  <feMergeNode in="blur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>

              <filter id="glow-red" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="4" result="coloredBlur" />
                <feMerge>
                  <feMergeNode in="coloredBlur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>

              <filter id="glow-blue" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="3" result="coloredBlur" />
                <feMerge>
                  <feMergeNode in="coloredBlur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {activeLayout.groups.map((group) => {
              const palette = getGroupPalette(group.id);
              return (
                <g key={group.id}>
                  <rect
                    x={group.x - 2}
                    y={group.y - 2}
                    width={group.width + 4}
                    height={group.height + 4}
                    rx={12}
                    fill="none"
                    stroke={palette.stroke}
                    strokeWidth={0.5}
                    strokeOpacity={0.4}
                  />
                  <rect
                    x={group.x}
                    y={group.y}
                    width={group.width}
                    height={group.height}
                    rx={10}
                    fill={palette.fill}
                    stroke={palette.stroke}
                    strokeWidth={1}
                  />
                  <rect
                    x={group.x}
                    y={group.y}
                    width={group.width}
                    height={2}
                    rx={10}
                    fill={palette.stroke}
                    fillOpacity={0.6}
                  />
                  <text
                    x={group.x + group.width / 2}
                    y={group.y + 20}
                    textAnchor="middle"
                    fill={palette.title}
                    fontSize={9}
                    fontWeight={700}
                    letterSpacing="0.13em"
                  >
                    {group.label.toUpperCase()}
                  </text>
                </g>
              );
            })}

            {activeLayout.edges.map((edge) => (
              <DiagramEdge
                key={edge.id}
                edge={edge}
                isRequestPath={requestFlowEdgeWeights.has(edge.id)}
                requestFlowWeight={requestFlowEdgeWeights.get(edge.id) ?? 0}
                suppressLabel={requestFlows.length > 0 && !requestFlowEdgeWeights.has(edge.id)}
              />
            ))}

            {orbs.map((orb) => {
              const flow = (requestFlows.length > 0 ? requestFlows : traversal.fallbackFlows)[orb.flowIndex];
              const segment = flow?.segments[orb.segmentIndex];
              const edge = segment ? edgeMap.get(segment.edgeId) : null;
              if (!edge) return null;
              const position = pointOnBezier(edge, segment.reverse ? 1 - orb.progress : orb.progress);
              const segmentBottleneck = orb.isBottleneck || edge.sourceSeverity === "high" || edge.targetSeverity === "high";
              const fill = segmentBottleneck ? "#ef4444" : edge.isAsync ? "#22c55e" : "#60a5fa";
              const radius = segmentBottleneck ? 6.4 : edge.isAsync ? 5.3 : 4.8;

              return (
                <motion.circle
                  key={orb.id}
                  cx={position.x}
                  cy={position.y}
                  r={radius}
                  fill={fill}
                  filter={segmentBottleneck ? "url(#glow-red)" : "url(#glow-blue)"}
                  animate={{
                    opacity: segmentBottleneck ? [0.72, 1, 0.72] : [0.88, 1, 0.88],
                  }}
                  transition={{
                    duration: segmentBottleneck ? 1.5 : 0.8,
                    repeat: Infinity,
                    ease: "easeInOut",
                  }}
                />
              );
            })}
          </svg>

          <AnimatePresence>
            {activeLayout.nodes.map((node) => (
              <DiagramNode key={node.id} node={node} />
            ))}
          </AnimatePresence>

          {requestFlows.length > 0 && (
            <div
              style={{
                position: "absolute",
                right: 18,
                bottom: 18,
                width: 248,
                border: "1px solid rgba(255,255,255,0.08)",
                background: "rgba(8,8,18,0.84)",
                boxShadow: "0 8px 30px rgba(0,0,0,0.35)",
                backdropFilter: "blur(10px)",
                borderRadius: 10,
                padding: "10px 12px",
              }}
            >
              <div
                style={{
                  fontSize: 10,
                  fontWeight: 700,
                  letterSpacing: "0.14em",
                  textTransform: "uppercase",
                  color: "rgba(255,255,255,0.42)",
                  marginBottom: 8,
                }}
              >
                Active Request Paths
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 7 }}>
                {requestFlows.slice(0, 3).map((flow) => (
                  <div key={flow.id} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                    <span
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: 999,
                        marginTop: 4,
                        background: flow.bottleneck ? "#ef4444" : "#60a5fa",
                        boxShadow: `0 0 12px ${flow.bottleneck ? "#ef444499" : "#60a5fa99"}`,
                        flexShrink: 0,
                      }}
                    />
                    <div
                      style={{
                        fontSize: 10,
                        lineHeight: 1.45,
                        color: "rgba(255,255,255,0.72)",
                        letterSpacing: "0.01em",
                      }}
                    >
                      {flow.label}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function pointOnBezier(edge: EdgeLayout, t: number): { x: number; y: number } {
  const inv = 1 - t;
  return {
    x:
      inv * inv * inv * edge.sx +
      3 * inv * inv * t * edge.c1x +
      3 * inv * t * t * edge.c2x +
      t * t * t * edge.tx,
    y:
      inv * inv * inv * edge.sy +
      3 * inv * inv * t * edge.c1y +
      3 * inv * t * t * edge.c2y +
      t * t * t * edge.ty,
  };
}

function approximateBezierLength(edge: EdgeLayout): number {
  let length = 0;
  let previous = pointOnBezier(edge, 0);
  const steps = 18;

  for (let index = 1; index <= steps; index += 1) {
    const point = pointOnBezier(edge, index / steps);
    length += Math.hypot(point.x - previous.x, point.y - previous.y);
    previous = point;
  }

  return length;
}

function parseRequestFlows(
  annotations: unknown[],
  edgeMap: Map<string, EdgeLayout>,
): Array<{ id: string; label: string; bottleneck: boolean; segments: RequestFlowSegment[] }> {
  const flows: Array<{ id: string; label: string; bottleneck: boolean; segments: RequestFlowSegment[] }> = [];

  annotations.forEach((annotation, index) => {
    if (!annotation || typeof annotation !== "object") return;
    const candidate = annotation as Partial<RequestFlowAnnotation>;
    if (candidate.kind !== "request_flow" || !Array.isArray(candidate.segments)) return;

    const segments = candidate.segments
      .filter((segment): segment is RequestFlowSegment => Boolean(segment?.edgeId) && edgeMap.has(segment.edgeId))
      .map((segment) => ({
        edgeId: segment.edgeId,
        reverse: Boolean(segment.reverse),
      }));

    if (segments.length === 0) return;

    flows.push({
      id: candidate.flowId ?? `flow-${index}`,
      label: candidate.label ?? `Request flow ${index + 1}`,
      bottleneck: Boolean(candidate.bottleneck),
      segments,
    });
  });

  return flows;
}

function buildFallbackSegments(
  startEdge: EdgeLayout,
  outgoing: Map<string, EdgeLayout[]>,
  maxDepth: number,
): RequestFlowSegment[] {
  const segments: RequestFlowSegment[] = [{ edgeId: startEdge.id, reverse: false }];
  let currentEdge = startEdge;
  let depth = 0;

  while (depth < maxDepth) {
    const nextEdges = outgoing.get(currentEdge.target) ?? [];
    if (nextEdges.length === 0) break;

    const preferred = nextEdges[0];
    segments.push({ edgeId: preferred.id, reverse: false });
    currentEdge = preferred;
    depth += 1;
  }

  return segments;
}
