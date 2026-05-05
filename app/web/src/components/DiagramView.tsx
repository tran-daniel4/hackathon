"use client";

import { useRef, useState, useEffect } from "react";
import {
  ReactFlow, Background, Controls, MiniMap,
  useNodesState, useEdgesState,
  type Node, type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { FolderOpen, Loader2, AlertCircle } from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TYPE_COLOR: Record<string, string> = {
  frontend:  "#3b82f6",
  backend:   "#06b6d4",
  database:  "#eab308",
  cache:     "#f97316",
  queue:     "#a855f7",
  worker:    "#22c55e",
  external:  "#6b7280",
};

const SEV_COLOR: Record<string, string> = {
  high:   "#ef4444",
  medium: "#f97316",
  low:    "#eab308",
};

const NODE_W  = 220;
const NODE_H  = 80;
const COL_GAP = 60;
const ROW_GAP = 80;

const TEXT_EXTS = new Set([
  "py","js","ts","tsx","jsx","go","java","rb","php","cs","cpp","c","h","rs",
  "swift","kt","json","yaml","yml","toml","html","css","scss","sql","sh","md","txt","env",
]);
const SKIP_DIRS = new Set(["node_modules",".git",".venv","__pycache__","dist","build",".next"]);

function shouldInclude(path: string): boolean {
  const parts = path.split("/");
  if (parts.some(p => SKIP_DIRS.has(p))) return false;
  const ext = path.split(".").pop()?.toLowerCase() ?? "";
  return TEXT_EXTS.has(ext);
}

function readFileText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload  = () => resolve(r.result as string);
    r.onerror = () => reject(r.error);
    r.readAsText(file);
  });
}

interface DiagramNode { id: string; label: string; type?: string; layer?: string; severity?: string | null; }
interface DiagramEdge { id: string; source: string; target: string; label?: string; }
interface AnalyzeResult {
  diagram: { nodes: DiagramNode[]; edges: DiagramEdge[]; annotations: unknown[] };
  bottlenecks: unknown; system_design: unknown; repo_analysis: unknown;
}

function toFlowNodes(dnodes: DiagramNode[]): Node[] {
  // Group by layer to compute row positions
  const groups: Record<string, DiagramNode[]> = {};
  dnodes.forEach(n => { (groups[n.layer || ""] ??= []).push(n); });

  const pos: Record<string, { x: number; y: number }> = {};
  Object.values(groups).forEach((layerNodes, rowIdx) => {
    layerNodes.forEach((n, colIdx) => {
      pos[n.id] = { x: colIdx * (NODE_W + COL_GAP), y: rowIdx * (NODE_H + ROW_GAP) };
    });
  });

  return dnodes.map(n => {
    const borderColor = n.severity
      ? SEV_COLOR[n.severity]
      : (TYPE_COLOR[n.type ?? ""] ?? "#374151");
    return {
      id: n.id,
      position: pos[n.id] ?? { x: 0, y: 0 },
      data: {
        label: (
          <div style={{ lineHeight: 1.4 }}>
            <div style={{ fontSize: 13 }}>{n.label}</div>
            <div style={{ fontSize: 10, opacity: 0.5, textTransform: "uppercase", letterSpacing: "0.08em", marginTop: 3 }}>
              {n.type}
            </div>
            {n.severity && (
              <div style={{ fontSize: 9, color: SEV_COLOR[n.severity], marginTop: 4, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                ⚠ {n.severity}
              </div>
            )}
          </div>
        ),
      },
      style: {
        background: "#0f0f15", color: "#fff",
        border: `1.5px solid ${borderColor}`,
        borderRadius: 0, padding: "10px 14px",
        width: NODE_W, fontFamily: "inherit",
      },
    };
  });
}

function toFlowEdges(dedges: DiagramEdge[]): Edge[] {
  return dedges.map(e => ({
    id: e.id, source: e.source, target: e.target,
    label: e.label || undefined,
    style: { stroke: "rgba(255,255,255,0.2)" },
    labelStyle: { fill: "rgba(255,255,255,0.5)", fontSize: 10 },
    labelBgStyle: { fill: "#0a0a0f" },
    labelBgPadding: [4, 2] as [number, number],
  }));
}

export function DiagramView() {
  const fileRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [error,  setError]  = useState("");
  const [result, setResult] = useState<AnalyzeResult | null>(null);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  useEffect(() => {
    if (!result) return;
    setNodes(toFlowNodes(result.diagram.nodes));
    setEdges(toFlowEdges(result.diagram.edges));
  }, [result, setNodes, setEdges]);

  const handleFiles = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;

    setStatus("loading");
    setError("");

    try {
      const allPaths  = Array.from(fileList).map(f => f.webkitRelativePath);
      const fileTree  = allPaths.join("\n");
      const included  = Array.from(fileList).filter(f => shouldInclude(f.webkitRelativePath));

      const files: Record<string, string> = {};
      let totalSize = 0;
      const MAX = 200_000;

      for (const file of included) {
        if (totalSize >= MAX) break;
        const text = await readFileText(file);
        const chunk = text.slice(0, MAX - totalSize);
        files[file.webkitRelativePath] = chunk;
        totalSize += chunk.length;
      }

      const res = await fetch(`${API_URL}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_tree: fileTree, files }),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(body.detail ?? res.statusText);
      }

      setResult(await res.json());
      setStatus("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setStatus("error");
    }
  };

  const reset = () => {
    setStatus("idle");
    setError("");
    setResult(null);
    setNodes([]);
    setEdges([]);
    if (fileRef.current) fileRef.current.value = "";
  };

  if (status === "idle") {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4 border border-dashed border-white/20 bg-white/[0.01]">
        <input
          ref={fileRef}
          type="file"
          className="hidden"
          onChange={handleFiles}
          {...{ webkitdirectory: "" }}
        />
        <button
          onClick={() => fileRef.current?.click()}
          className="flex items-center gap-2 px-6 py-3 border border-white/20 bg-white/5 hover:bg-white/10 transition-colors text-[13px] uppercase tracking-[0.15em]"
        >
          <FolderOpen className="w-4 h-4" />
          Select project folder to analyze
        </button>
        <p className="text-[11px] text-white/30">Files are sent only to your backend — nothing goes to third parties</p>
      </div>
    );
  }

  if (status === "loading") {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3">
        <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
        <div className="text-[13px] text-white/60">Running analysis pipeline…</div>
        <div className="text-[11px] text-white/30">Repo Analyzer → System Designer → Bottleneck Detector</div>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <AlertCircle className="w-8 h-8 text-red-400" />
        <div className="text-[13px] text-red-400">Analysis failed</div>
        <div className="text-[11px] text-white/40 max-w-md text-center break-all">{error}</div>
        <button onClick={reset} className="px-4 py-2 border border-white/20 text-[11px] uppercase tracking-[0.15em] hover:bg-white/5 transition-colors">
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div style={{ height: 500, background: "#080810" }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          nodesConnectable={false}
          colorMode="dark"
        >
          <Background color="#ffffff10" gap={20} />
          <Controls />
          <MiniMap
            nodeColor={n => {
              const orig = result!.diagram.nodes.find(x => x.id === n.id);
              return orig?.severity ? SEV_COLOR[orig.severity] : (TYPE_COLOR[orig?.type ?? ""] ?? "#374151");
            }}
            style={{ background: "#0f0f15", border: "1px solid rgba(255,255,255,0.1)" }}
          />
        </ReactFlow>
      </div>

      {/* Type + severity legend */}
      <div className="flex items-center gap-6 flex-wrap text-[11px] text-white/50">
        {Object.entries(TYPE_COLOR).map(([type, color]) => (
          <span key={type} className="flex items-center gap-1.5">
            <span style={{ width: 8, height: 8, background: color, display: "inline-block" }} />
            {type}
          </span>
        ))}
        <span className="text-white/20">|</span>
        {Object.entries(SEV_COLOR).map(([sev, color]) => (
          <span key={sev} className="flex items-center gap-1.5">
            <span style={{ width: 8, height: 8, background: color, display: "inline-block" }} />
            {sev} bottleneck
          </span>
        ))}
      </div>

      <button onClick={reset} className="self-start text-[11px] text-white/40 hover:text-white/70 transition-colors uppercase tracking-[0.15em] underline underline-offset-2">
        Analyze different project
      </button>
    </div>
  );
}
