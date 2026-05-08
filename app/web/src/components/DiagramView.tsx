"use client";

import { useEffect, useRef, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Edge,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { AlertCircle, FolderOpen, Loader2, RefreshCw } from "lucide-react";
import { FaGithub } from "react-icons/fa";

import type { RawDiagram } from "@/components/visualization/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const TYPE_COLOR: Record<string, string> = {
  frontend: "#3b82f6",
  backend: "#06b6d4",
  database: "#eab308",
  cache: "#f97316",
  queue: "#a855f7",
  worker: "#22c55e",
  external: "#6b7280",
};

const SEV_COLOR: Record<string, string> = {
  high: "#ef4444",
  medium: "#f97316",
  low: "#eab308",
};

const NODE_W = 220;
const NODE_H = 80;
const COL_GAP = 60;
const ROW_GAP = 80;

const TEXT_EXTS = new Set([
  "py", "js", "ts", "tsx", "jsx", "go", "java", "rb", "php", "cs", "cpp", "c", "h", "rs",
  "swift", "kt", "json", "yaml", "yml", "toml", "html", "css", "scss", "sql", "sh", "md", "txt", "env",
  "csproj", "fsproj", "vbproj", "sln", "props", "targets", "cshtml", "razor",
]);
const SKIP_DIRS = new Set(["node_modules", ".git", ".venv", "__pycache__", "dist", "build", ".next"]);
const PRIORITY_NAMES = new Set([
  "package.json", "requirements.txt", "go.mod", "go.sum", "Cargo.toml", "pom.xml",
  "build.gradle", "pyproject.toml", "setup.py", "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
  "main.py", "app.py", "server.py", "index.ts", "index.js", "server.ts", "server.js",
  "manage.py", "wsgi.py", "asgi.py", "main.go", "main.ts", "main.js",
  "Program.cs", "Startup.cs", "appsettings.json", "appsettings.Development.json",
  "Directory.Packages.props", "Directory.Build.props", "Directory.Build.targets",
  ".env.example", "terraform.tf", "infra.tf",
]);

type GraphEvidence = {
  id: string;
  kind: string;
  file_path: string;
  start_line?: number | null;
  end_line?: number | null;
  excerpt?: string;
};

type GraphNode = {
  id: string;
  type: string;
  name: string;
  language?: string | null;
  framework?: string | null;
  tags?: string[];
};

type GraphEdge = {
  id: string;
  src: string;
  dst: string;
  kind: string;
  label?: string | null;
  confidence?: "verified" | "inferred" | null;
};

type GraphApi = {
  id: string;
  component_id: string;
  method: string;
  path: string;
};

type GraphWarning = {
  code: string;
  message: string;
  file_path?: string | null;
};

interface DiagramNode {
  id: string;
  label: string;
  type?: string;
  layer?: string;
  severity?: string | null;
}

interface DiagramEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
}

interface AnalyzeResult {
  diagram: { nodes: DiagramNode[]; edges: DiagramEdge[]; annotations: unknown[] };
  diagrams?: RawDiagram[];
  bottlenecks: { issues?: Array<{ title?: string; severity?: string; summary?: string }> };
  system_design: unknown;
  repo_analysis: {
    services: string[];
    languages: string[];
    frameworks: string[];
    databases: string[];
    external_calls: string[];
  };
  graph_facts: {
    repo: { name: string; url?: string | null; branch?: string | null; commit_sha?: string | null };
    nodes: GraphNode[];
    edges: GraphEdge[];
    apis: GraphApi[];
    evidence: GraphEvidence[];
    warnings: GraphWarning[];
  };
  analysis_debug: {
    source: "upload" | "github";
    repo: { name: string; url?: string | null; branch?: string | null; commit_sha?: string | null };
    summary: {
      input_file_count: number;
      service_count: number;
      framework_count: number;
      api_count: number;
      node_count: number;
      edge_count: number;
      warning_count: number;
    };
  };
}

interface DiagramViewProps {
  onDiagrams?: (diagrams: RawDiagram[]) => void;
  repositoryName?: string;
  repositoryUrl?: string;
  githubToken?: string | null;
}

function isPriority(path: string): boolean {
  const fname = path.split("/").pop() ?? "";
  return PRIORITY_NAMES.has(fname);
}

function shouldInclude(path: string): boolean {
  const parts = path.split("/");
  if (parts.some((part) => SKIP_DIRS.has(part))) return false;
  const ext = path.split(".").pop()?.toLowerCase() ?? "";
  return TEXT_EXTS.has(ext);
}

function isGitHubRepoUrl(url?: string | null): boolean {
  if (!url) return false;
  try {
    const parsed = new URL(url);
    return ["github.com", "www.github.com"].includes(parsed.hostname.toLowerCase());
  } catch {
    return false;
  }
}

function readFileText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

function toFlowNodes(dnodes: DiagramNode[]): Node[] {
  const groups: Record<string, DiagramNode[]> = {};
  dnodes.forEach((node) => {
    (groups[node.layer || ""] ??= []).push(node);
  });

  const pos: Record<string, { x: number; y: number }> = {};
  Object.values(groups).forEach((layerNodes, rowIdx) => {
    layerNodes.forEach((node, colIdx) => {
      pos[node.id] = { x: colIdx * (NODE_W + COL_GAP), y: rowIdx * (NODE_H + ROW_GAP) };
    });
  });

  return dnodes.map((node) => {
    const borderColor = node.severity
      ? SEV_COLOR[node.severity]
      : (TYPE_COLOR[node.type ?? ""] ?? "#374151");

    return {
      id: node.id,
      position: pos[node.id] ?? { x: 0, y: 0 },
      data: {
        label: (
          <div style={{ lineHeight: 1.4 }}>
            <div style={{ fontSize: 13 }}>{node.label}</div>
            <div style={{ fontSize: 10, opacity: 0.5, textTransform: "uppercase", letterSpacing: "0.08em", marginTop: 3 }}>
              {node.type}
            </div>
            {node.severity && (
              <div style={{ fontSize: 9, color: SEV_COLOR[node.severity], marginTop: 4, textTransform: "uppercase", letterSpacing: "0.08em" }}>
                ! {node.severity}
              </div>
            )}
          </div>
        ),
      },
      style: {
        background: "#0f0f15",
        color: "#fff",
        border: `1.5px solid ${borderColor}`,
        borderRadius: 0,
        padding: "10px 14px",
        width: NODE_W,
        fontFamily: "inherit",
      },
    };
  });
}

function toFlowEdges(dedges: DiagramEdge[]): Edge[] {
  return dedges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label: edge.label || undefined,
    style: { stroke: "rgba(255,255,255,0.2)" },
    labelStyle: { fill: "rgba(255,255,255,0.5)", fontSize: 10 },
    labelBgStyle: { fill: "#0a0a0f" },
    labelBgPadding: [4, 2] as [number, number],
  }));
}

async function postAnalyze(payload: Record<string, unknown>): Promise<AnalyzeResult> {
  const res = await fetch(`${API_URL}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail ?? res.statusText);
  }

  return res.json();
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="border border-white/10 bg-white/[0.03] px-3 py-2 min-w-[140px]">
      <div className="text-[10px] uppercase tracking-[0.16em] text-white/35">{label}</div>
      <div className="text-[13px] text-white/80 mt-1 break-all">{value}</div>
    </div>
  );
}

export function DiagramView({
  onDiagrams,
  repositoryName,
  repositoryUrl,
  githubToken,
}: DiagramViewProps = {}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const autoStarted = useRef(false);

  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error" | "empty">("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState<AnalyzeResult | null>(null);

  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  const canAnalyzeGitHub = isGitHubRepoUrl(repositoryUrl);

  useEffect(() => {
    if (!result) return;
    setNodes(toFlowNodes(result.diagram.nodes));
    setEdges(toFlowEdges(result.diagram.edges));
  }, [result, setNodes, setEdges]);

  useEffect(() => {
    if (!canAnalyzeGitHub || autoStarted.current || status !== "idle") return;
    autoStarted.current = true;
    const timer = window.setTimeout(() => {
      if (!repositoryUrl) return;
      setStatus("loading");
      setError("");
      void (async () => {
        try {
          const json = await postAnalyze({
            repo_url: repositoryUrl,
            github_token: githubToken || undefined,
          });
          setResult(json);
          if (onDiagrams && json.diagrams) onDiagrams(json.diagrams);
          setStatus("done");
        } catch (err) {
          setError(err instanceof Error ? err.message : String(err));
          setStatus("error");
        }
      })();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [canAnalyzeGitHub, githubToken, onDiagrams, repositoryUrl, status]);

  async function handleGithubAnalysis() {
    if (!repositoryUrl) return;
    setStatus("loading");
    setError("");

    try {
      const json = await postAnalyze({
        repo_url: repositoryUrl,
        github_token: githubToken || undefined,
      });
      setResult(json);
      if (onDiagrams && json.diagrams) onDiagrams(json.diagrams);
      setStatus("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setStatus("error");
    }
  }

  const handleFiles = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const fileList = e.target.files;
    if (!fileList || fileList.length === 0) return;

    setStatus("loading");
    setError("");

    try {
      const allPaths = Array.from(fileList).map((file) => file.webkitRelativePath);
      const included = Array.from(fileList).filter((file) => shouldInclude(file.webkitRelativePath));

      if (included.length === 0) {
        setStatus("empty");
        return;
      }

      const files: Record<string, string> = {};
      let totalSize = 0;
      const MAX = 1_500_000;
      const PER_FILE = 80_000;

      const sorted = [...included].sort(
        (a, b) => Number(isPriority(b.webkitRelativePath)) - Number(isPriority(a.webkitRelativePath)),
      );

      for (const file of sorted) {
        if (totalSize >= MAX) break;
        const text = await readFileText(file);
        const chunk = text.slice(0, Math.min(PER_FILE, MAX - totalSize));
        files[file.webkitRelativePath] = chunk;
        totalSize += chunk.length;
      }

      const json = await postAnalyze({
        file_tree: allPaths.join("\n"),
        files,
      });
      setResult(json);
      if (onDiagrams && json.diagrams) onDiagrams(json.diagrams);
      setStatus("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setStatus("error");
    }
  };

  const reset = () => {
    autoStarted.current = true;
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

        {canAnalyzeGitHub && (
          <button
            onClick={() => void handleGithubAnalysis()}
            className="flex items-center gap-2 px-6 py-3 border border-white/20 bg-white text-black hover:bg-white/90 transition-colors text-[13px] uppercase tracking-[0.15em]"
          >
            <FaGithub className="w-4 h-4" />
            Analyze {repositoryName || "saved repo"} from GitHub
          </button>
        )}

        <button
          onClick={() => fileRef.current?.click()}
          className="flex items-center gap-2 px-6 py-3 border border-white/20 bg-white/5 hover:bg-white/10 transition-colors text-[13px] uppercase tracking-[0.15em]"
        >
          <FolderOpen className="w-4 h-4" />
          Select project folder to analyze
        </button>

        <p className="text-[11px] text-white/30 max-w-xl text-center">
          {canAnalyzeGitHub
            ? "Saved GitHub repos can be analyzed server-side, or you can upload a local folder for comparison."
            : "Files are sent only to your backend. Nothing goes to third-party analysis services from the browser upload step."}
        </p>
      </div>
    );
  }

  if (status === "loading") {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3">
        <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
        <div className="text-[13px] text-white/60">Running analysis pipeline...</div>
        <div className="text-[11px] text-white/30">Repo Analyzer {"->"} System Designer {"->"} Bottleneck Detector</div>
      </div>
    );
  }

  if (status === "empty") {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-3 border border-dashed border-white/10 bg-white/[0.01]">
        <AlertCircle className="w-5 h-5 text-white/20" />
        <div className="text-[11px] uppercase tracking-[0.2em] text-white/30">No source files found</div>
        <div className="text-[11px] text-white/20">Make sure the folder contains code files like .py, .ts, .js, .go, .java, or .cs</div>
        <button
          onClick={reset}
          className="mt-2 px-4 py-2 border border-white/10 text-[11px] uppercase tracking-[0.15em] text-white/40 hover:bg-white/5 hover:text-white/70 transition-colors"
        >
          Try a different folder
        </button>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <AlertCircle className="w-8 h-8 text-red-400" />
        <div className="text-[13px] text-red-400">Analysis failed</div>
        <div className="text-[11px] text-white/40 max-w-md text-center break-all">{error}</div>
        <div className="flex gap-3">
          {canAnalyzeGitHub && (
            <button
              onClick={() => void handleGithubAnalysis()}
              className="px-4 py-2 border border-white/20 text-[11px] uppercase tracking-[0.15em] hover:bg-white/5 transition-colors"
            >
              Retry GitHub analysis
            </button>
          )}
          <button
            onClick={reset}
            className="px-4 py-2 border border-white/20 text-[11px] uppercase tracking-[0.15em] hover:bg-white/5 transition-colors"
          >
            Start over
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="text-[11px] uppercase tracking-[0.16em] text-white/35">
          {result?.analysis_debug.source === "github" ? "Server-side GitHub analysis" : "Browser upload analysis"}
        </div>
        <button
          onClick={reset}
          className="inline-flex items-center gap-2 text-[11px] text-white/40 hover:text-white/70 transition-colors uppercase tracking-[0.15em]"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Analyze different project
        </button>
      </div>

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
            nodeColor={(node) => {
              const orig = result?.diagram.nodes.find((x) => x.id === node.id);
              return orig?.severity ? SEV_COLOR[orig.severity] : (TYPE_COLOR[orig?.type ?? ""] ?? "#374151");
            }}
            style={{ background: "#0f0f15", border: "1px solid rgba(255,255,255,0.1)" }}
          />
        </ReactFlow>
      </div>

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

      {result && (
        <details className="border border-white/10 bg-white/[0.02]">
          <summary className="cursor-pointer px-4 py-3 text-[12px] uppercase tracking-[0.16em] text-white/70">
            Analysis Debug
          </summary>

          <div className="border-t border-white/10 p-4 space-y-5">
            <div className="flex flex-wrap gap-3">
              <Stat label="Repo" value={result.analysis_debug.repo.name} />
              <Stat label="Source" value={result.analysis_debug.source} />
              <Stat label="Files" value={result.analysis_debug.summary.input_file_count} />
              <Stat label="Services" value={result.analysis_debug.summary.service_count} />
              <Stat label="Frameworks" value={result.analysis_debug.summary.framework_count} />
              <Stat label="APIs" value={result.analysis_debug.summary.api_count} />
              <Stat label="Nodes" value={result.analysis_debug.summary.node_count} />
              <Stat label="Edges" value={result.analysis_debug.summary.edge_count} />
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
              <div className="border border-white/10 bg-black/20 p-4">
                <div className="text-[11px] uppercase tracking-[0.16em] text-white/40 mb-3">Detected repo facts</div>
                <div className="space-y-3 text-[12px] text-white/75">
                  <div>
                    <div className="text-white/35 mb-1">Services</div>
                    <div>{result.repo_analysis.services.join(", ") || "None"}</div>
                  </div>
                  <div>
                    <div className="text-white/35 mb-1">Frameworks</div>
                    <div>{result.repo_analysis.frameworks.join(", ") || "None"}</div>
                  </div>
                  <div>
                    <div className="text-white/35 mb-1">Languages</div>
                    <div>{result.repo_analysis.languages.join(", ") || "None"}</div>
                  </div>
                  <div>
                    <div className="text-white/35 mb-1">Datastores</div>
                    <div>{result.repo_analysis.databases.join(", ") || "None"}</div>
                  </div>
                  <div>
                    <div className="text-white/35 mb-1">External calls</div>
                    <div>{result.repo_analysis.external_calls.join(", ") || "None"}</div>
                  </div>
                </div>
              </div>

              <div className="border border-white/10 bg-black/20 p-4">
                <div className="text-[11px] uppercase tracking-[0.16em] text-white/40 mb-3">Structured graph facts</div>
                <div className="space-y-3 text-[12px] text-white/75">
                  <div>
                    <div className="text-white/35 mb-1">APIs</div>
                    <div className="space-y-1">
                      {result.graph_facts.apis.slice(0, 8).map((api) => (
                        <div key={api.id}>{api.component_id} {"->"} {api.method} {api.path}</div>
                      ))}
                      {result.graph_facts.apis.length === 0 && <div>None</div>}
                    </div>
                  </div>
                  <div>
                    <div className="text-white/35 mb-1">Nodes</div>
                    <div className="space-y-1">
                      {result.graph_facts.nodes.slice(0, 8).map((node) => (
                        <div key={node.id}>{node.name} ({node.type})</div>
                      ))}
                      {result.graph_facts.nodes.length === 0 && <div>None</div>}
                    </div>
                  </div>
                  <div>
                    <div className="text-white/35 mb-1">Warnings</div>
                    <div className="space-y-1">
                      {result.graph_facts.warnings.slice(0, 6).map((warning) => (
                        <div key={`${warning.code}-${warning.message}`}>{warning.code}: {warning.message}</div>
                      ))}
                      {result.graph_facts.warnings.length === 0 && <div>None</div>}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <details className="border border-white/10 bg-black/20">
              <summary className="cursor-pointer px-4 py-3 text-[11px] uppercase tracking-[0.16em] text-white/45">
                Raw analysis JSON
              </summary>
              <pre className="max-h-[420px] overflow-auto p-4 text-[11px] leading-5 text-white/70 whitespace-pre-wrap">
                {JSON.stringify(
                  {
                    analysis_debug: result.analysis_debug,
                    repo_analysis: result.repo_analysis,
                    graph_facts: result.graph_facts,
                    bottlenecks: result.bottlenecks,
                  },
                  null,
                  2,
                )}
              </pre>
            </details>
          </div>
        </details>
      )}
    </div>
  );
}
