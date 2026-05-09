"use client";

import { motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import {
  Activity,
  AlertCircle,
  Code,
  Layers,
  LayoutGrid,
  Loader2,
  Settings as SettingsIcon,
} from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import type { RawDiagram, ViewId } from "@/components/visualization/types";

const ArchDiagram = dynamic(
  () => import("@/components/visualization/ArchDiagram").then((m) => ({ default: m.ArchDiagram })),
  { ssr: false },
);

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Repository {
  id: string;
  name: string;
  url: string;
  lastUpdated?: string | null;
  componentsCount: number;
}

interface RepositoryDetailProps {
  repository: Repository;
  initialView?: ArchitectureView;
  onViewChange?: (view: ArchitectureView) => void;
  onRepositoryUpdate?: (repository: Repository) => void;
}

interface RepositoryFinding {
  id: string;
  title: string;
  severity: "low" | "medium" | "high" | "critical";
  confidence?: number;
  why?: string;
}

interface AnalysisSnapshotResponse {
  analyzed_at?: string;
  diagrams?: RawDiagram[];
  repository?: {
    id: string;
    name: string;
    url: string;
    componentsCount: number;
    lastUpdated?: string;
  };
  bottlenecks?: {
    findings?: RepositoryFinding[];
  };
}

type ArchitectureView = "context" | "conceptual" | "component" | "operational";

const VIEW_ID_MAP: Record<ArchitectureView, ViewId> = {
  context: "system_context",
  conceptual: "conceptual",
  component: "component",
  operational: "operational",
};

function isGitHubUrl(url?: string | null): boolean {
  if (!url) return false;
  try {
    const { hostname } = new URL(url);
    return hostname === "github.com" || hostname === "www.github.com";
  } catch {
    return false;
  }
}

function relativeTime(input?: string): string {
  if (!input) return "Latest analysis";
  const target = new Date(input).getTime();
  if (Number.isNaN(target)) return "Latest analysis";
  const diffMinutes = Math.max(0, Math.floor((Date.now() - target) / 60000));
  if (diffMinutes < 1) return "Just now";
  if (diffMinutes < 60) return `${diffMinutes} minute${diffMinutes === 1 ? "" : "s"} ago`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? "" : "s"} ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays} day${diffDays === 1 ? "" : "s"} ago`;
}

function severityRank(severity: RepositoryFinding["severity"]): number {
  switch (severity) {
    case "critical":
      return 0;
    case "high":
      return 1;
    case "medium":
      return 2;
    default:
      return 3;
  }
}

function normalizeRepositorySnapshot(repository: AnalysisSnapshotResponse["repository"]): Repository | null {
  if (!repository) return null;
  const parsedDate = repository.lastUpdated ? new Date(repository.lastUpdated) : null;
  return {
    id: repository.id,
    name: repository.name,
    url: repository.url,
    componentsCount: repository.componentsCount ?? 0,
    lastUpdated: parsedDate && !Number.isNaN(parsedDate.getTime()) ? parsedDate.toLocaleDateString() : null,
  };
}

export function RepositoryDetail({
  repository,
  initialView = "component",
  onViewChange,
  onRepositoryUpdate,
}: RepositoryDetailProps) {
  const { session, githubToken } = useAuth();
  const [currentView, setCurrentView] = useState<ArchitectureView>(initialView);
  const [diagrams, setDiagrams] = useState<RawDiagram[] | null>(null);
  const [recentAlerts, setRecentAlerts] = useState<Array<{
    id: string;
    message: string;
    time: string;
    severity: "low" | "medium" | "high" | "critical";
    details?: string;
  }>>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "done" | "error">("idle");
  const [error, setError] = useState("");
  const hasStarted = useRef(false);

  const accessToken = (session as { access_token?: string } | null)?.access_token ?? "";
  const isGitHub = isGitHubUrl(repository.url);

  const applySnapshot = useCallback((data: AnalysisSnapshotResponse) => {
    if (data.diagrams?.length) {
      setDiagrams(data.diagrams);
    }
    const updatedRepository = normalizeRepositorySnapshot(data.repository);
    if (updatedRepository) {
      onRepositoryUpdate?.(updatedRepository);
    }

    setRecentAlerts(
      (data.bottlenecks?.findings ?? [])
        .slice()
        .sort((a, b) => {
          const diff = severityRank(a.severity) - severityRank(b.severity);
          if (diff !== 0) return diff;
          return (b.confidence ?? 0) - (a.confidence ?? 0);
        })
        .slice(0, 5)
        .map((finding) => ({
          id: finding.id,
          message: finding.title,
          time: relativeTime(data.analyzed_at),
          severity: finding.severity,
          details: finding.why,
        })),
    );
  }, [onRepositoryUpdate]);

  useEffect(() => {
    setCurrentView(initialView);
  }, [initialView]);

  const handleViewChange = useCallback((view: ArchitectureView) => {
    setCurrentView(view);
    onViewChange?.(view);
  }, [onViewChange]);

  const loadLatestAnalysis = useCallback(async (): Promise<boolean> => {
    if (!accessToken) {
      return false;
    }

    try {
      const res = await fetch(`${API_BASE}/repos/${repository.id}/analysis/latest`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });

      if (res.status === 404) {
        return false;
      }
      if (!res.ok) {
        const body = (await res.json()) as { detail?: string };
        throw new Error(body.detail ?? res.statusText);
      }

      applySnapshot((await res.json()) as AnalysisSnapshotResponse);
      setStatus("done");
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
      setStatus("error");
      return false;
    }
  }, [accessToken, applySnapshot, repository.id]);

  const syncAnalysis = useCallback(async (background = false) => {
    if (!accessToken) {
      return;
    }

    if (!background) {
      setStatus("loading");
      setError("");
      setDiagrams(null);
      setRecentAlerts([]);
    }

    try {
      const res = await fetch(`${API_BASE}/repos/${repository.id}/analysis/sync`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          github_token: githubToken ?? undefined,
        }),
      });

      if (!res.ok) {
        const body = (await res.json()) as { detail?: string };
        throw new Error(body.detail ?? res.statusText);
      }

      applySnapshot((await res.json()) as AnalysisSnapshotResponse);
      setStatus("done");
    } catch (err) {
      if (!background) {
        setError(err instanceof Error ? err.message : "Analysis failed");
        setStatus("error");
      }
    }
  }, [accessToken, applySnapshot, githubToken, repository.id]);

  useEffect(() => {
    if (!isGitHub || !accessToken || hasStarted.current) return;
    hasStarted.current = true;

    void (async () => {
      setStatus("loading");
      setError("");
      const hasSnapshot = await loadLatestAnalysis();
      if (hasSnapshot) {
        void syncAnalysis(true);
        return;
      }
      await syncAnalysis(false);
    })();
  }, [accessToken, isGitHub, loadLatestAnalysis, syncAnalysis]);

  const views = {
    context: { label: "System Context", description: "High-level view", icon: Layers },
    conceptual: { label: "Conceptual", description: "Business-level system overview", icon: LayoutGrid },
    component: { label: "Component", description: "Developer architecture view", icon: Code },
    operational: { label: "Operational", description: "DevOps infrastructure view", icon: SettingsIcon },
  };

  const renderDiagramArea = () => {
    if (status === "loading") {
      return (
        <div className="flex h-64 flex-col items-center justify-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-blue-400" />
          <div className="text-[13px] text-white/60">Loading saved architecture analysis...</div>
          <div className="text-[11px] text-white/30">Reading latest snapshot -&gt; Checking for repository updates</div>
        </div>
      );
    }

    if (status === "error") {
      return (
        <div className="flex h-64 flex-col items-center justify-center gap-4">
          <AlertCircle className="h-8 w-8 text-red-400" />
          <div className="text-[13px] text-red-400">Analysis failed</div>
          <div className="max-w-md break-all text-center text-[11px] text-white/40">{error}</div>
          <button
            onClick={() => {
              hasStarted.current = true;
              void syncAnalysis(false);
            }}
            className="border border-white/20 px-4 py-2 text-[11px] uppercase tracking-[0.15em] transition-colors hover:bg-white/5"
          >
            Retry
          </button>
        </div>
      );
    }

    if (diagrams && diagrams.length > 0) {
      return <ArchDiagram diagrams={diagrams} viewId={VIEW_ID_MAP[currentView]} />;
    }

    if (!isGitHub) {
      return (
        <div className="flex h-64 items-center justify-center border border-dashed border-white/10 text-[13px] text-white/40">
          Diagram generation is only supported for GitHub repositories
        </div>
      );
    }

    return (
      <div className="flex h-64 items-center justify-center border border-dashed border-white/10 text-[13px] text-white/40">
        No diagram data available
      </div>
    );
  };

  return (
    <div className="bg-[#0a0a0f] text-white">
      <div className="mx-auto max-w-450 px-8 py-12">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
          <div className="space-y-6 lg:col-span-2">
            <div className="bg-[#0f0f15]/60 p-6 border border-white/10">
              <div className="mb-6 flex items-center justify-between">
                <h2 className="text-[18px]">System Architecture</h2>
              </div>

              <div className="mb-8 grid grid-cols-2 gap-3 md:grid-cols-4">
                {(Object.keys(views) as ArchitectureView[]).map((viewKey) => {
                  const view = views[viewKey];
                  const Icon = view.icon;
                  return (
                    <motion.button
                      key={viewKey}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={() => handleViewChange(viewKey)}
                      className={`border p-4 transition-all ${
                        currentView === viewKey
                          ? "border-blue-500 bg-blue-500/10"
                          : "border-white/10 bg-white/5 hover:bg-white/10"
                      }`}
                    >
                      <Icon className={`mx-auto mb-2 h-5 w-5 ${currentView === viewKey ? "text-blue-400" : "text-white/60"}`} />
                      <div className={`mb-1 text-[12px] ${currentView === viewKey ? "text-white" : "text-white/70"}`}>
                        {view.label}
                      </div>
                      <div className="text-[10px] text-white/40">{view.description}</div>
                    </motion.button>
                  );
                })}
              </div>

              <div className="border border-white/10 bg-black/20 p-8">
                {renderDiagramArea()}
              </div>
            </div>
          </div>

          <div className="space-y-6">
            <div className="border border-white/10 bg-[#0f0f15]/60 p-6">
              <h3 className="mb-2 flex items-center gap-2 text-[16px]">
                <Activity className="h-4 w-4 text-blue-400" />
                Recent Alerts
              </h3>
              <p className="mb-6 text-[11px] text-white/50">Top findings from the latest repository analysis</p>

              <div className="space-y-3">
                {recentAlerts.length === 0 ? (
                  <div className="border border-white/10 bg-white/5 px-4 py-6 text-[12px] text-white/45">
                    {status === "loading"
                      ? "Collecting recent alerts from saved analysis..."
                      : "No recent alerts found for this repository."}
                  </div>
                ) : recentAlerts.map((activity) => (
                  <motion.div
                    key={activity.id}
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    className={`border-l-2 py-3 pl-4 ${
                      activity.severity === "critical"
                        ? "border-red-500/50 bg-red-500/5"
                        : activity.severity === "high" || activity.severity === "medium"
                          ? "border-yellow-500/50 bg-yellow-500/5"
                          : "border-blue-500/30 bg-blue-500/5"
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      {activity.severity === "critical" || activity.severity === "high" || activity.severity === "medium" ? (
                        <AlertCircle className={`mt-0.5 h-4 w-4 ${activity.severity === "critical" ? "text-red-400" : "text-yellow-400"}`} />
                      ) : (
                        <div className="mt-1.5 h-2 w-2 rounded-full bg-blue-500" />
                      )}
                      <div className="flex-1">
                        <p className="mb-1 text-[13px] text-white/80">{activity.message}</p>
                        <p className="text-[11px] text-white/40">{activity.time}</p>
                        {activity.details && (
                          <p className="mt-2 text-[11px] text-white/45">{activity.details}</p>
                        )}
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
