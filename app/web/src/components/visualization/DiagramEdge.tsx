"use client";

import type { EdgeLayout } from "./types";

interface DiagramEdgeProps {
  edge: EdgeLayout;
}

export function DiagramEdge({ edge }: DiagramEdgeProps) {
  const { d, color, isAsync, label, labelX, labelY, confidence } = edge;
  const isInferred = confidence === "inferred";
  const dashArray = isInferred ? "3 9" : isAsync ? "5 10" : "8 8";
  const animName = isAsync ? "arch-flow-async" : "arch-flow-sync";
  const animDur = isAsync ? "2.2s" : "1.5s";
  const labelW = label ? Math.max(label.length * 5.5 + 12, 28) : 0;
  const hypothesisPillW = 62;

  return (
    <g>
      {/* Ghost trail */}
      <path
        d={d}
        stroke={color}
        strokeWidth={1.5}
        strokeOpacity={isInferred ? 0.08 : 0.18}
        fill="none"
        strokeLinecap="round"
      />

      {/* Animated flow dashes */}
      <path
        d={d}
        stroke={color}
        strokeWidth={2.2}
        fill="none"
        strokeLinecap="round"
        strokeDasharray={dashArray}
        filter="url(#arch-edgeglow)"
        style={{ animation: `${animName} ${animDur} linear infinite` }}
      />

      {/* Edge label pill */}
      {label && (
        <g>
          <rect
            x={labelX - labelW / 2}
            y={labelY - 8}
            width={labelW}
            height={15}
            rx={4}
            fill="#0c0c1e"
            fillOpacity={0.88}
            stroke={color}
            strokeOpacity={0.25}
            strokeWidth={0.8}
          />
          <text
            x={labelX}
            y={labelY + 1}
            textAnchor="middle"
            dominantBaseline="middle"
            fill="rgba(255,255,255,0.45)"
            fontSize={8.5}
            fontFamily="inherit"
            letterSpacing="0.04em"
          >
            {label}
          </text>
        </g>
      )}

      {/* Hypothesis pill — shown below the label for inferred edges */}
      {isInferred && (
        <g>
          <rect
            x={labelX - hypothesisPillW / 2}
            y={labelY + 10}
            width={hypothesisPillW}
            height={13}
            rx={3}
            fill="rgba(168,85,247,0.12)"
            stroke="rgba(168,85,247,0.30)"
            strokeWidth={0.7}
          />
          <text
            x={labelX}
            y={labelY + 17}
            textAnchor="middle"
            dominantBaseline="middle"
            fill="rgba(168,85,247,0.65)"
            fontSize={7.5}
            fontFamily="inherit"
            fontStyle="italic"
            letterSpacing="0.05em"
          >
            hypothesis
          </text>
        </g>
      )}
    </g>
  );
}
