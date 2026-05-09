"use client";

import type { EdgeLayout } from "./types";

interface DiagramEdgeProps {
  edge: EdgeLayout;
  isRequestPath?: boolean;
  requestFlowWeight?: number;
  suppressLabel?: boolean;
}

export function DiagramEdge({
  edge,
  isRequestPath = false,
  requestFlowWeight = 0,
  suppressLabel = false,
}: DiagramEdgeProps) {
  const { d, color, label, labelX, labelY, confidence } = edge;
  const isInferred = confidence === "inferred";
  const effectiveLabel = suppressLabel ? undefined : label;
  const labelW = effectiveLabel ? Math.max(effectiveLabel.length * 5.4 + 14, 34) : 0;
  const baseOpacity = isRequestPath ? 0.56 : isInferred ? 0.1 : 0.16;
  const glowOpacity = isRequestPath ? 0.2 : 0.06;
  const strokeWidth = isRequestPath ? 2 + Math.min(requestFlowWeight, 3) * 0.22 : 1.35;
  const glowWidth = isRequestPath ? 3.1 : 2;

  return (
    <g>
      <path
        d={d}
        stroke={color}
        strokeWidth={strokeWidth}
        strokeOpacity={baseOpacity}
        fill="none"
        strokeLinecap="round"
      />

      <path
        d={d}
        stroke={color}
        strokeWidth={glowWidth}
        strokeOpacity={glowOpacity}
        fill="none"
        strokeLinecap="round"
        filter="url(#arch-edgeglow)"
      />

      {effectiveLabel && (
        <g>
          <rect
            x={labelX - labelW / 2}
            y={labelY - 8}
            width={labelW}
            height={15}
            rx={4}
            fill="#0c0c1e"
            fillOpacity={isRequestPath ? 0.96 : 0.86}
            stroke={color}
            strokeOpacity={isRequestPath ? 0.34 : 0.18}
            strokeWidth={0.8}
          />
          <text
            x={labelX}
            y={labelY + 1}
            textAnchor="middle"
            dominantBaseline="middle"
            fill={isRequestPath ? "rgba(255,255,255,0.7)" : "rgba(255,255,255,0.42)"}
            fontSize={8.5}
            fontFamily="inherit"
            letterSpacing="0.04em"
          >
            {effectiveLabel}
          </text>
        </g>
      )}

      {isInferred && !suppressLabel && (
        <g>
          <rect
            x={labelX - 26}
            y={labelY + 10}
            width={52}
            height={13}
            rx={3}
            fill="rgba(168,85,247,0.1)"
            stroke="rgba(168,85,247,0.22)"
            strokeWidth={0.7}
          />
          <text
            x={labelX}
            y={labelY + 17}
            textAnchor="middle"
            dominantBaseline="middle"
            fill="rgba(168,85,247,0.62)"
            fontSize={7.4}
            fontFamily="inherit"
            fontStyle="italic"
            letterSpacing="0.05em"
          >
            inferred
          </text>
        </g>
      )}
    </g>
  );
}
