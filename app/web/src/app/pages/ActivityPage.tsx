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

interface RepoAlert {
  id: string;
  type: "update" | "alert" | "task";
  severity: "low" | "medium" | "high" | "critical";
  message: string;
  repository: string;
  analyzed_at: string;
  details?: string;
}

interface AlertsResponse {
  alerts: RepoAlert[];
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

export function ActivityPage() {
  const { session } = useAuth();
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
        const alertsRes = await fetch(`${API_BASE}/repos/alerts`, {
          headers: { Authorization: `Bearer ${accessToken}` },
        });
        if (!alertsRes.ok) throw new Error("Failed to load repository alerts");

        const data = (await alertsRes.json()) as AlertsResponse;
        const nextActivities = (data.alerts ?? []).map((alert) => ({
          id: alert.id,
          type: alert.type,
          severity: alert.severity,
          message: alert.message,
          repository: alert.repository,
          timestamp: relativeTime(alert.analyzed_at),
          details: alert.details,
        }));

        if (!cancelled) {
          setActivities(nextActivities);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load alerts");
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
  }, [accessToken]);

  const filteredActivities = useMemo(
    () =>
      activities.filter((activity) => {
        const matchesType = filterType === "all" || activity.severity === filterType;
        const lowerSearch = searchQuery.toLowerCase();
        const matchesSearch =
          searchQuery === "" ||
          activity.message.toLowerCase().includes(lowerSearch) ||
          activity.repository.toLowerCase().includes(lowerSearch) ||
          activity.details?.toLowerCase().includes(lowerSearch);
        return matchesType && matchesSearch;
      }),
    [activities, filterType, searchQuery],
  );

  const getIcon = (severity: Activity["severity"]) => {
    switch (severity) {
      case "critical":
        return <AlertCircle className="h-5 w-5 text-red-400" />;
      case "high":
        return <AlertCircle className="h-5 w-5 text-orange-400" />;
      case "medium":
        return <AlertTriangle className="h-5 w-5 text-yellow-400" />;
      default:
        return <Info className="h-5 w-5 text-blue-400" />;
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
      <div className="mx-auto max-w-[1400px] px-8 py-12">
        <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-4">
          {stats.map((stat) => (
            <div key={stat.label} className="border border-white/10 bg-[#0f0f15]/60 p-6">
              <p className="mb-2 text-[11px] uppercase tracking-wider text-white/50">{stat.label}</p>
              <p className="text-[32px]">{stat.value}</p>
            </div>
          ))}
        </div>

        <div className="mb-8 flex flex-col gap-4 md:flex-row">
          <div className="relative flex-1">
            <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search alerts..."
              className="w-full border border-white/10 bg-white/5 py-3 pl-12 pr-4 text-[14px] text-white placeholder:text-white/30 transition-colors focus:border-white/30 focus:outline-none"
            />
          </div>

          <div ref={filterRef} className="relative">
            <button
              onClick={() => setFilterOpen((o) => !o)}
              className="flex min-w-[160px] items-center justify-between gap-2 border border-white/10 bg-white/5 px-4 py-3 text-[14px] text-white transition-colors hover:bg-white/10"
            >
              <span className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-white/40" />
                {FILTER_OPTIONS.find((o) => o.value === filterType)?.label}
              </span>
              <ChevronDown className={`h-4 w-4 text-white/40 transition-transform ${filterOpen ? "rotate-180" : ""}`} />
            </button>

            <AnimatePresence>
              {filterOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  transition={{ duration: 0.15 }}
                  className="absolute right-0 top-full z-50 mt-1 w-full border border-white/10 bg-[#0f0f15]"
                >
                  {FILTER_OPTIONS.map((opt) => (
                    <button
                      key={opt.value}
                      onClick={() => {
                        setFilterType(opt.value);
                        setFilterOpen(false);
                      }}
                      className={`w-full px-4 py-3 text-left text-[13px] transition-colors hover:bg-white/5 ${filterType === opt.value ? "text-white" : "text-white/50"}`}
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
            <div className="flex flex-col items-center gap-3 border border-white/10 bg-[#0f0f15]/60 p-12 text-center">
              <Loader2 className="h-6 w-6 animate-spin text-blue-400" />
              <p className="text-white/60">Loading saved repository alerts...</p>
            </div>
          ) : error ? (
            <div className="border border-white/10 bg-[#0f0f15]/60 p-12 text-center">
              <p className="mb-2 text-red-400">Failed to load repository alerts</p>
              <p className="text-[12px] text-white/40">{error}</p>
            </div>
          ) : filteredActivities.length === 0 ? (
            <div className="border border-white/10 bg-[#0f0f15]/60 p-12 text-center">
              <p className="text-white/50">
                {activities.length === 0
                  ? "No saved alerts found across your repositories"
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
                className={`border-l-2 transition-all ${getBorderColor(activity.severity)} ${getBgColor(activity.severity)}`}
              >
                <div className="p-6">
                  <div className="flex items-start gap-4">
                    {getIcon(activity.severity)}
                    <div className="flex-1">
                      <div className="mb-2 flex items-start justify-between">
                        <h3 className="text-[15px] text-white/90">{activity.message}</h3>
                        <span className="ml-4 whitespace-nowrap text-[11px] text-white/40">
                          {activity.timestamp}
                        </span>
                      </div>
                      <div className="mb-2 flex items-center gap-4 text-[12px] text-white/50">
                        <span className="border border-white/10 bg-white/5 px-2 py-1 text-[10px] uppercase tracking-wider">
                          {activity.repository}
                        </span>
                        <span className="uppercase tracking-wider">{activity.type}</span>
                        <span className="uppercase tracking-wider">{activity.severity}</span>
                      </div>
                      {activity.details && (
                        <p className="mt-3 border-t border-white/5 pt-3 text-[13px] text-white/60">
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
