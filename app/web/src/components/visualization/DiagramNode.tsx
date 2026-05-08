"use client";

import { motion } from "motion/react";
import {
  Monitor, Server, Database, Zap, GitBranch,
  Settings, Globe,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { NodeLayout, NodeType, SeverityType } from "./types";

const TYPE_ICON: Record<NodeType, LucideIcon> = {
  frontend: Monitor,
  backend:  Server,
  database: Database,
  cache:    Zap,
  queue:    GitBranch,
  worker:   Settings,
  external: Globe,
};

const TYPE_COLORS: Record<string, { accent: string; bg: string; border: string }> = {
  frontend: { accent: "#3b82f6", bg: "rgba(59,130,246,0.13)",  border: "rgba(59,130,246,0.38)" },
  backend:  { accent: "#06b6d4", bg: "rgba(6,182,212,0.13)",   border: "rgba(6,182,212,0.38)" },
  database: { accent: "#eab308", bg: "rgba(234,179,8,0.13)",   border: "rgba(234,179,8,0.38)" },
  cache:    { accent: "#f97316", bg: "rgba(249,115,22,0.13)",  border: "rgba(249,115,22,0.38)" },
  queue:    { accent: "#a855f7", bg: "rgba(168,85,247,0.13)",  border: "rgba(168,85,247,0.38)" },
  worker:   { accent: "#22c55e", bg: "rgba(34,197,94,0.13)",   border: "rgba(34,197,94,0.38)" },
  external: { accent: "#6b7280", bg: "rgba(107,114,128,0.10)", border: "rgba(107,114,128,0.28)" },
};

const SEV_COLORS: Record<SeverityType, string> = {
  high:   "#ef4444",
  medium: "#f97316",
  low:    "#eab308",
};

export function DiagramNode({ node }: { node: NodeLayout }) {
  const Icon = TYPE_ICON[node.type] ?? Globe;
  const colors = TYPE_COLORS[node.type] ?? TYPE_COLORS.external;

  return (
    <motion.div
      key={node.id}
      initial={{ opacity: 0, scale: 0.82, x: node.x, y: node.y }}
      animate={{ opacity: 1, scale: 1, x: node.x, y: node.y }}
      exit={{ opacity: 0, scale: 0.82 }}
      transition={{ type: "spring", stiffness: 310, damping: 28, mass: 0.85 }}
      style={{ position: "absolute", top: 0, left: 0, width: node.width }}
    >
      {/* Inner div handles the hover lift independently from position animation */}
      <motion.div
        whileHover={{ y: -4 }}
        transition={{ type: "spring", stiffness: 400, damping: 20 }}
        style={{ cursor: "default" }}
      >
        <div
          style={{
            background: "linear-gradient(145deg, #131326 0%, #0d0d1f 100%)",
            border: `1px solid ${colors.border}`,
            borderRadius: 12,
            padding: "12px 14px",
            boxShadow: [
              "0 4px 24px rgba(0,0,0,0.55)",
              "0 1px 0 rgba(255,255,255,0.05) inset",
              `0 0 0 1px rgba(255,255,255,0.04)`,
              `0 8px 32px ${colors.accent}18`,
            ].join(", "),
            position: "relative",
            overflow: "hidden",
            minHeight: node.height,
          }}
        >
          {/* Coloured top accent stripe */}
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              right: 0,
              height: 2,
              background: `linear-gradient(90deg, ${colors.accent}00, ${colors.accent}, ${colors.accent}00)`,
              borderRadius: "12px 12px 0 0",
            }}
          />

          {/* Icon + label row */}
          <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: 6 }}>
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: 8,
                background: colors.bg,
                border: `1px solid ${colors.border}`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <Icon size={13} color={colors.accent} strokeWidth={2.3} />
            </div>

            <span
              style={{
                fontSize: 12,
                fontWeight: 600,
                color: "#dde2f0",
                letterSpacing: "0.01em",
                lineHeight: 1.35,
                flex: 1,
                whiteSpace: "normal",
                overflowWrap: "anywhere",
                display: "block",
              }}
            >
              {node.label}
            </span>
          </div>

          {/* Type badge + optional severity tag */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6 }}>
            <span
              style={{
                fontSize: 9,
                fontWeight: 700,
                color: colors.accent,
                textTransform: "uppercase",
                letterSpacing: "0.13em",
                opacity: 0.75,
              }}
            >
              {node.type}
            </span>

            {node.severity && (
              <span
                style={{
                  fontSize: 8,
                  fontWeight: 700,
                  color: SEV_COLORS[node.severity],
                  textTransform: "uppercase",
                  letterSpacing: "0.1em",
                  background: `${SEV_COLORS[node.severity]}18`,
                  padding: "2px 6px",
                  borderRadius: 4,
                  border: `1px solid ${SEV_COLORS[node.severity]}35`,
                  whiteSpace: "nowrap",
                }}
              >
                ⚠ {node.severity}
              </span>
            )}
          </div>

          {node.description && (
            <p
              style={{
                margin: "5px 0 0 0",
                fontSize: 10,
                fontWeight: 400,
                color: "rgba(221,226,240,0.55)",
                lineHeight: 1.4,
                whiteSpace: "normal",
                overflowWrap: "anywhere",
                letterSpacing: "0.01em",
              }}
            >
              {node.description}
            </p>
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}
