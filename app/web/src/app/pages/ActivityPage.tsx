import { motion, AnimatePresence } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  Info,
  AlertTriangle,
  ChevronDown,
  Filter,
  Loader2,
  Search,
} from "lucide-react";
import { useAuth } from "@/components/AuthProvider";

interface Repository {
  id: string;
  name: string;
  url: string;
}

interface BottleneckFinding {
  id: string;
  title: string;
  risk_type?: string;
  severity: "low" | "medium" | "high" | "critical";
  confidence?: number;
  why?: string;
  impact?: string;
}

interface AnalyzeResponse {
  bottlenecks: {
    findings?: BottleneckFinding[];
  };
  analysis_debug?: {
    repo?: {
      analyzed_at?: string;
    };
  };
}

interface Activity {
  id: string;
  type: "update" | "alert" | "task";
  severity: "low" | "medium" | "high" | "critical";
  message: string;
  repository: string;
  timestamp: string;
  details?: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const FILTER_OPTIONS = [
  { value: "all", label: "All Alerts" },
  { value: "critical", label: "Critical" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

function isGitHubUrl(url?: string | null): boolean {
  if (!url) return false;
  try {
    const parsed = new URL(url);
    return parsed.hostname === "github.com" || parsed.hostname === "www.github.com";
  } catch {
    return false;
  }
}

function relativeTime(input?: string): string {
  if (!input) return "Just now";
  const target = new Date(input).getTime();
  if (Number.isNaN(target)) return "Just now";

  const diffMs = Date.now() - target;
  const diffMinutes = Math.max(0, Math.floor(diffMs / 60000));
  if (diffMinutes < 1) return "Just now";
  if (diffMinutes < 60) return `${diffMinutes} minute${diffMinutes === 1 ? "" : "s"} ago`;

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? "" : "s"} ago`;

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays} day${diffDays === 1 ? "" : "s"} ago`;
}

function severityRank(severity: Activity["severity"]): number {
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

function activityTypeForSeverity(severity: Activity["severity"]): Activity["type"] {
  if (severity === "critical" || severity === "high") return "alert";
  if (severity === "medium") return "task";
  return "update";
}

function buildDetails(finding: BottleneckFinding): string | undefined {
  const detailParts = [finding.why?.trim(), finding.impact?.trim()].filter(Boolean);
  if (detailParts.length === 0) return undefined;
  return detailParts.join(" ");
}

export function ActivityPage() {
  const { session, githubToken } = useAuth();
  const [filterType, setFilterType] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [filterOpen, setFilterOpen] = useState(false);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const filterRef = useRef<HTMLDivElement>(null);

  const accessToken = (session as { access_token?: string } | null)?.access_token ?? "";

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (filterRef.current && !filterRef.current.contains(e.target as Node)) {
        setFilterOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (!accessToken) return;

    let cancelled = false;

    async function loadActivities() {
      setLoading(true);
      setError("");

      try {
        const reposRes = await fetch(`${API_BASE}/repos`, {
          headers: { Authorization: `Bearer ${accessToken}` },
        });
        if (!reposRes.ok) throw new Error("Failed to load repositories");

        const repos = (await reposRes.json()) as Repository[];
        const githubRepos = repos.filter((repo) => isGitHubUrl(repo.url));

        if (githubRepos.length === 0) {
          if (!cancelled) setActivities([]);
          return;
        }

        const results = await Promise.allSettled(
          githubRepos.map(async (repo) => {
            const analyzeRes = await fetch(`${API_BASE}/analyze`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                repo_url: repo.url,
                github_token: githubToken ?? undefined,
              }),
            });

            if (!analyzeRes.ok) {
              throw new Error(`Failed to analyze ${repo.name}`);
            }

            const data = (await analyzeRes.json()) as AnalyzeResponse;
            const analyzedAt = data.analysis_debug?.repo?.analyzed_at;

            return (data.bottlenecks.findings ?? []).map((finding) => ({
              id: `${repo.id}-${finding.id}`,
              type: activityTypeForSeverity(finding.severity),
              severity: finding.severity,
              message: finding.title,
              repository: repo.name,
              timestamp: relativeTime(analyzedAt),
              details: buildDetails(finding),
              confidence: finding.confidence ?? 0,
            }));
          }),
        );

        const nextActivities = results
          .flatMap((result) => (result.status === "fulfilled" ? result.value : []))
          .sort((a, b) => {
            const severityDiff = severityRank(a.severity) - severityRank(b.severity);
            if (severityDiff !== 0) return severityDiff;
            return (b.confidence ?? 0) - (a.confidence ?? 0);
          })
          .map(({ id, type, severity, message, repository, timestamp, details }) => ({
            id,
            type,
            severity,
            message,
            repository,
            timestamp,
            details,
          }));

        if (!cancelled) {
          setActivities(nextActivities);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load activity");
          setActivities([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadActivities();
    return () => {
      cancelled = true;
    };
  }, [accessToken, githubToken]);

  const filteredActivities = useMemo(
    () =>
      activities.filter((activity) => {
        const matchesType = filterType === "all" || activity.severity === filterType;
        const matchesSearch =
          searchQuery === "" ||
          activity.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
          activity.repository.toLowerCase().includes(searchQuery.toLowerCase()) ||
          activity.details?.toLowerCase().includes(searchQuery.toLowerCase());
        return matchesType && matchesSearch;
      }),
    [activities, filterType, searchQuery],
  );

  const getIcon = (severity: Activity["severity"]) => {
    switch (severity) {
      case "critical":
        return <AlertCircle className="w-5 h-5 text-red-400" />;
      case "high":
        return <AlertCircle className="w-5 h-5 text-orange-400" />;
      case "medium":
        return <AlertTriangle className="w-5 h-5 text-yellow-400" />;
      default:
        return <Info className="w-5 h-5 text-blue-400" />;
    }
  };

  const getBorderColor = (severity: Activity["severity"]) => {
    switch (severity) {
      case "critical":
        return "border-red-500/50";
      case "high":
        return "border-orange-500/50";
      case "medium":
        return "border-yellow-500/50";
      default:
        return "border-blue-500/30";
    }
  };

  const getBgColor = (severity: Activity["severity"]) => {
    switch (severity) {
      case "critical":
        return "bg-red-500/5 hover:bg-red-500/10";
      case "high":
        return "bg-orange-500/5 hover:bg-orange-500/10";
      case "medium":
        return "bg-yellow-500/5 hover:bg-yellow-500/10";
      default:
        return "bg-blue-500/5 hover:bg-blue-500/10";
    }
  };

  const stats = [
    { label: "Total Alerts", value: activities.length },
    { label: "Critical", value: activities.filter((a) => a.severity === "critical").length },
    { label: "High", value: activities.filter((a) => a.severity === "high").length },
    { label: "Repositories", value: new Set(activities.map((a) => a.repository)).size },
  ];

  return (
    <div className="bg-[#0a0a0f] text-white">
      <div className="max-w-[1400px] mx-auto px-8 py-12">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {stats.map((stat) => (
            <div key={stat.label} className="border border-white/10 bg-[#0f0f15]/60 p-6">
              <p className="text-[11px] text-white/50 mb-2 uppercase tracking-wider">{stat.label}</p>
              <p className="text-[32px]">{stat.value}</p>
            </div>
          ))}
        </div>

        <div className="flex flex-col md:flex-row gap-4 mb-8">
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search alerts..."
              className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/10 focus:border-white/30 focus:outline-none transition-colors text-[14px] text-white placeholder:text-white/30"
            />
          </div>

          <div ref={filterRef} className="relative">
            <button
              onClick={() => setFilterOpen((o) => !o)}
              className="flex items-center gap-2 border border-white/10 bg-white/5 px-4 py-3 text-[14px] text-white hover:bg-white/10 transition-colors min-w-[160px] justify-between"
            >
              <span className="flex items-center gap-2">
                <Filter className="w-4 h-4 text-white/40" />
                {FILTER_OPTIONS.find((o) => o.value === filterType)?.label}
              </span>
              <ChevronDown className={`w-4 h-4 text-white/40 transition-transform ${filterOpen ? "rotate-180" : ""}`} />
            </button>

            <AnimatePresence>
              {filterOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.15 }}
                  className="absolute right-0 top-full mt-1 w-full border border-white/10 bg-[#0f0f15] z-50"
                >
                  {FILTER_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => {
                        setFilterType(opt.value);
                        setFilterOpen(false);
                      }}
                      className={`w-full text-left px-4 py-3 text-[13px] transition-colors hover:bg-white/5 ${filterType === opt.value ? "text-white" : "text-white/50"}`}
                    >
                      {opt.label}
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        <div className="space-y-3">
          {loading ? (
            <div className="border border-white/10 bg-[#0f0f15]/60 p-12 text-center flex flex-col items-center gap-3">
              <Loader2 className="w-6 h-6 text-blue-400 animate-spin" />
              <p className="text-white/60">Analyzing repositories and collecting bottlenecks…</p>
            </div>
          ) : error ? (
            <div className="border border-white/10 bg-[#0f0f15]/60 p-12 text-center">
              <p className="text-red-400 mb-2">Failed to load repository alerts</p>
              <p className="text-white/40 text-[12px]">{error}</p>
            </div>
          ) : filteredActivities.length === 0 ? (
            <div className="border border-white/10 bg-[#0f0f15]/60 p-12 text-center">
              <p className="text-white/50">
                {activities.length === 0
                  ? "No bottlenecks found across your analyzable repositories"
                  : "No alerts found"}
              </p>
            </div>
          ) : (
            filteredActivities.map((activity, idx) => (
              <motion.div
                key={activity.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.03 }}
                className={`border-l-2 ${getBorderColor(activity.severity)} ${getBgColor(activity.severity)} transition-all`}
              >
                <div className="p-6">
                  <div className="flex items-start gap-4">
                    {getIcon(activity.severity)}
                    <div className="flex-1">
                      <div className="flex items-start justify-between mb-2">
                        <h3 className="text-[15px] text-white/90">{activity.message}</h3>
                        <span className="text-[11px] text-white/40 whitespace-nowrap ml-4">
                          {activity.timestamp}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-[12px] text-white/50 mb-2">
                        <span className="px-2 py-1 bg-white/5 border border-white/10 text-[10px] uppercase tracking-wider">
                          {activity.repository}
                        </span>
                        <span className="uppercase tracking-wider">{activity.type}</span>
                        <span className="uppercase tracking-wider">{activity.severity}</span>
                      </div>
                      {activity.details && (
                        <p className="text-[13px] text-white/60 mt-3 border-t border-white/5 pt-3">
                          {activity.details}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              </motion.div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
