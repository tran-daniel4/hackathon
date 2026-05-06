"use client";

import { useMemo } from "react";
import { AnimatePresence } from "motion/react";
import { transformView } from "./viewTransformer";
import { computeLayout } from "./layoutEngine";
import { DiagramNode } from "./DiagramNode";
import { DiagramEdge } from "./DiagramEdge";
import type { RawDiagram, ViewId } from "./types";

interface ArchDiagramProps {
  diagrams: RawDiagram[];
  viewId: ViewId;
}

// Color palette per group id — fill, border, title text
const GROUP_PALETTE: Record<string, { fill: string; stroke: string; title: string }> = {
  // ── Static analysis groups ─────────────────────────────────────────────────
  frontend:          { fill: "rgba(59,130,246,0.06)",   stroke: "rgba(59,130,246,0.28)",   title: "#3b82f6" },
  gateway:           { fill: "rgba(6,182,212,0.06)",    stroke: "rgba(6,182,212,0.28)",    title: "#06b6d4" },
  core:              { fill: "rgba(99,102,241,0.06)",   stroke: "rgba(99,102,241,0.28)",   title: "#818cf8" },
  supporting:        { fill: "rgba(168,85,247,0.06)",   stroke: "rgba(168,85,247,0.28)",   title: "#a855f7" },
  external:          { fill: "rgba(107,114,128,0.05)",  stroke: "rgba(107,114,128,0.22)",  title: "#9ca3af" },
  data:              { fill: "rgba(234,179,8,0.06)",    stroke: "rgba(234,179,8,0.28)",    title: "#eab308" },
  // ── LLM conceptual view groups ────────────────────────────────────────────
  users:             { fill: "rgba(59,130,246,0.06)",   stroke: "rgba(59,130,246,0.28)",   title: "#3b82f6" },
  capabilities:      { fill: "rgba(99,102,241,0.06)",   stroke: "rgba(99,102,241,0.28)",   title: "#818cf8" },
  external_partners: { fill: "rgba(107,114,128,0.05)",  stroke: "rgba(107,114,128,0.22)",  title: "#9ca3af" },
  gaps:              { fill: "rgba(239,68,68,0.05)",    stroke: "rgba(239,68,68,0.22)",    title: "#f87171" },
  // ── LLM system context groups ─────────────────────────────────────────────
  actors:            { fill: "rgba(59,130,246,0.06)",   stroke: "rgba(59,130,246,0.28)",   title: "#3b82f6" },
  system:            { fill: "rgba(99,102,241,0.06)",   stroke: "rgba(99,102,241,0.28)",   title: "#818cf8" },
  partners:          { fill: "rgba(107,114,128,0.05)",  stroke: "rgba(107,114,128,0.22)",  title: "#9ca3af" },
  identity:          { fill: "rgba(249,115,22,0.05)",   stroke: "rgba(249,115,22,0.22)",   title: "#fb923c" },
  // ── LLM operational view groups ───────────────────────────────────────────
  cicd:              { fill: "rgba(34,197,94,0.05)",    stroke: "rgba(34,197,94,0.22)",    title: "#4ade80" },
  runtime:           { fill: "rgba(6,182,212,0.06)",    stroke: "rgba(6,182,212,0.28)",    title: "#06b6d4" },
  services:          { fill: "rgba(99,102,241,0.06)",   stroke: "rgba(99,102,241,0.28)",   title: "#818cf8" },
  observability:     { fill: "rgba(234,179,8,0.06)",    stroke: "rgba(234,179,8,0.28)",    title: "#eab308" },
};

const DYNAMIC_ACCENTS: ReadonlyArray<[string, string, string]> = [
  ["#f472b6", "rgba(244,114,182,0.06)", "rgba(244,114,182,0.28)"],
  ["#34d399", "rgba(52,211,153,0.06)",  "rgba(52,211,153,0.28)"],
  ["#fb923c", "rgba(251,146,60,0.06)",  "rgba(251,146,60,0.28)"],
  ["#60a5fa", "rgba(96,165,250,0.06)",  "rgba(96,165,250,0.28)"],
  ["#c084fc", "rgba(192,132,252,0.06)", "rgba(192,132,252,0.28)"],
  ["#2dd4bf", "rgba(45,212,191,0.06)",  "rgba(45,212,191,0.28)"],
  ["#fbbf24", "rgba(251,191,36,0.06)",  "rgba(251,191,36,0.28)"],
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
  const view = useMemo(() => transformView(diagrams, viewId), [diagrams, viewId]);
  const layout = useMemo(() => {
    if (!view || view.nodes.length === 0) return null;
    return computeLayout(view.nodes, view.edges, view.groups);
  }, [view]);

  if (!layout) {
    return (
      <div className="flex items-center justify-center h-64 text-white/30 text-[13px]">
        No diagram data for this view
      </div>
    );
  }

  const svgH = Math.max(layout.height, 420);

  return (
    <div
      style={{
        width: "100%",
        overflowX: "auto",
        overflowY: "hidden",
        background: "radial-gradient(ellipse at 40% 30%, #0e0e28 0%, #080812 70%)",
        borderRadius: 8,
        minHeight: 420,
      }}
    >
      <div
        style={{
          position: "relative",
          width: Math.max(layout.width, 100),
          height: svgH,
          minWidth: "100%",
          backgroundImage:
            "radial-gradient(circle, rgba(255,255,255,0.035) 1px, transparent 1px)",
          backgroundSize: "28px 28px",
        }}
      >
        {/* SVG layer — group containers + edges render behind nodes */}
        <svg
          width={Math.max(layout.width, 100)}
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
          </defs>

          {/* Group containers — colored zones behind nodes */}
          {layout.groups.map(group => {
            const p = getGroupPalette(group.id);
            return (
              <g key={group.id}>
                {/* Outer glow halo */}
                <rect
                  x={group.x - 2}
                  y={group.y - 2}
                  width={group.width + 4}
                  height={group.height + 4}
                  rx={12}
                  fill="none"
                  stroke={p.stroke}
                  strokeWidth={0.5}
                  strokeOpacity={0.4}
                />
                {/* Main container */}
                <rect
                  x={group.x}
                  y={group.y}
                  width={group.width}
                  height={group.height}
                  rx={10}
                  fill={p.fill}
                  stroke={p.stroke}
                  strokeWidth={1}
                />
                {/* Top accent bar */}
                <rect
                  x={group.x}
                  y={group.y}
                  width={group.width}
                  height={2}
                  rx={10}
                  fill={p.stroke}
                  fillOpacity={0.6}
                />
                {/* Group label */}
                <text
                  x={group.x + group.width / 2}
                  y={group.y + 20}
                  textAnchor="middle"
                  fill={p.title}
                  fontSize={9}
                  fontWeight={700}
                  letterSpacing="0.13em"
                >
                  {group.label.toUpperCase()}
                </text>
              </g>
            );
          })}

          {/* Edges */}
          {layout.edges.map(edge => (
            <DiagramEdge key={edge.id} edge={edge} />
          ))}
        </svg>

        {/* HTML layer — node cards */}
        <AnimatePresence>
          {layout.nodes.map(node => (
            <DiagramNode key={node.id} node={node} />
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
