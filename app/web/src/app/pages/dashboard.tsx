"use client";

import { motion, AnimatePresence } from "motion/react";
import { useState, useRef, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { Search, Plus, GitBranch, Trash2, Edit3, Bell, ChevronRight, LayoutGrid, Code, Settings as SettingsIcon, Home, LogOut } from "lucide-react";
import { toast } from "sonner";
import { AddRepositoryModal } from "@/components/AddRepositoryModal";
import { ActivityPage } from "./ActivityPage";
import { RepositoryDetail } from "./RepositoryDetail";
import { SettingsPage } from "./SettingsPage";
import { TeamsPage } from "./TeamsPage";
import { useAuth } from "@/components/AuthProvider";

interface Repository {
  id: string;
  name: string;
  url: string;
  lastUpdated?: string | null;
  componentsCount: number;
}

interface Activity {
  id: string;
  type: "update" | "alert" | "task";
  message: string;
  timestamp: string;
  severity: "low" | "medium" | "high" | "critical";
  repository: string;
}

interface RepoAlert {
  id: string;
  type: "update" | "alert" | "task";
  message: string;
  severity: "low" | "medium" | "high" | "critical";
  repository: string;
  analyzed_at: string;
  confidence?: number;
}

interface AlertsResponse {
  alerts: RepoAlert[];
}

type ViewPerspective = "system-context" | "conceptual" | "component" | "operational";
type RepositoryView = "context" | "conceptual" | "component" | "operational";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function relativeTime(input?: string): string {
  if (!input) return "Just now";
  const target = new Date(input).getTime();
  if (Number.isNaN(target)) return "Just now";
  const diffMinutes = Math.max(0, Math.floor((Date.now() - target) / 60000));
  if (diffMinutes < 1) return "Just now";
  if (diffMinutes < 60) return `${diffMinutes} minute${diffMinutes === 1 ? "" : "s"} ago`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? "" : "s"} ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays} day${diffDays === 1 ? "" : "s"} ago`;
}

function mapPerspectiveToRepositoryView(perspective: ViewPerspective): RepositoryView {
  switch (perspective) {
    case "system-context":
      return "context";
    case "conceptual":
      return "conceptual";
    case "operational":
      return "operational";
    default:
      return "component";
  }
}

function mapRepositoryViewToPerspective(view: RepositoryView): ViewPerspective {
  switch (view) {
    case "context":
      return "system-context";
    case "conceptual":
      return "conceptual";
    case "operational":
      return "operational";
    default:
      return "component";
  }
}

function normalizeLastUpdated(input?: string | null): string | null {
  if (!input) return null;
  const parsed = new Date(input);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toLocaleDateString();
}

export function Dashboard() {
  const { supabase, user, session, loading: authLoading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const fullName = user?.user_metadata?.full_name ?? user?.user_metadata?.name ?? user?.user_metadata?.user_name ?? user?.email ?? "User";
  const initials = fullName
    ?.split(" ")
    .map((n: string) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase() ?? "?";

  const accessToken = (session as { access_token?: string } | null)?.access_token ?? "";
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [reposLoading, setReposLoading] = useState(false);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [alertsLoading, setAlertsLoading] = useState(false);

  const upsertRepository = (repo: Repository) => {
    setRepositories((prev) => {
      const existing = prev.some((item) => item.id === repo.id);
      if (!existing) {
        return [repo, ...prev];
      }
      return prev.map((item) => item.id === repo.id ? { ...item, ...repo } : item);
    });
    setSelectedRepo((prev) => prev && prev.id === repo.id ? { ...prev, ...repo } : prev);
  };

  useEffect(() => {
    if (!accessToken) return;
    setReposLoading(true);
    fetch(`${API_BASE}/repos`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((data: Array<{ id: string; name: string; url: string; lastUpdated: string; componentsCount: number }>) => {
        setRepositories(
          data.map((r) => ({
            id: String(r.id),
            name: r.name,
            url: r.url,
            lastUpdated: normalizeLastUpdated(r.lastUpdated),
            componentsCount: r.componentsCount ?? 0,
          }))
        );
      })
      .catch((err: Error) => {
        if (err.message === "401") {
          toast.error("Session expired — please sign in again");
        } else {
          toast.error("Failed to load repositories");
        }
      })
      .finally(() => setReposLoading(false));
  }, [accessToken]);

  useEffect(() => {
    if (!accessToken) {
      setActivities([]);
      return;
    }

    let cancelled = false;

    async function loadRecentAlerts() {
      setAlertsLoading(true);

      try {
        const res = await fetch(`${API_BASE}/repos/alerts?limit=3`, {
          headers: { Authorization: `Bearer ${accessToken}` },
        });
        if (!res.ok) {
          throw new Error("Failed to load recent alerts");
        }

        const data = (await res.json()) as AlertsResponse;
        const nextActivities = (data.alerts ?? []).slice(0, 3).map((alert) => ({
          id: alert.id,
          type: alert.type,
          message: alert.message,
          timestamp: relativeTime(alert.analyzed_at),
          severity: alert.severity,
          repository: alert.repository,
        }));

        if (!cancelled) {
          setActivities(nextActivities);
        }
      } catch {
        if (!cancelled) {
          setActivities([]);
        }
      } finally {
        if (!cancelled) {
          setAlertsLoading(false);
        }
      }
    }

    void loadRecentAlerts();
    return () => {
      cancelled = true;
    };
  }, [accessToken, repositories.length]);

  const [searchQuery, setSearchQuery] = useState("");
  const [perspective, setPerspective] = useState<ViewPerspective>("component");
  const [showAddModal, setShowAddModal] = useState(false);
  const [subView, setSubView] = useState<"repository" | "settings" | null>(null);
  const [selectedRepo, setSelectedRepo] = useState<Repository | null>(null);

  // Derive the top-level view from the URL; subView overlays on top without changing the URL
  const urlView = pathname === "/activity" ? "activity"
                : pathname === "/teams"    ? "teams"
                : "dashboard";
  const currentView = subView ?? urlView;

  // Reset sub-views when the URL changes (e.g. browser back while viewing a repo)
  useEffect(() => {
    Promise.resolve().then(() => {
      setSubView(null);
      setSelectedRepo(null);
    });
  }, [pathname]);

  const handleLogout = async () => {
    if (supabase) {
      await supabase.auth.signOut();
    }
    router.replace("/");
  };
  const [showUserDropdown, setShowUserDropdown] = useState(false);
  const [showNotificationsDropdown, setShowNotificationsDropdown] = useState(false);
  const userDropdownRef = useRef<HTMLDivElement>(null);
  const notificationsDropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (userDropdownRef.current && !userDropdownRef.current.contains(event.target as Node)) {
        setShowUserDropdown(false);
      }
      if (notificationsDropdownRef.current && !notificationsDropdownRef.current.contains(event.target as Node)) {
        setShowNotificationsDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleAddRepository = (repo: Repository) => {
    upsertRepository(repo);
    toast.success(`${repo.name} added`, {
      description: "Your architecture diagram is being generated",
    });
  };

  const handleEditRepository = async (repo: Repository) => {
    const nextName = window.prompt("Rename repository", repo.name)?.trim();
    if (!nextName || nextName === repo.name) {
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/repos/${repo.id}`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ name: nextName }),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      upsertRepository({
        id: String(data.id),
        name: data.name,
        url: data.url,
        lastUpdated: normalizeLastUpdated(data.lastUpdated),
        componentsCount: data.componentsCount ?? 0,
      });
      toast.success("Repository renamed");
    } catch {
      toast.error("Failed to rename repository");
    }
  };

  const handleDeleteRepository = async (id: string) => {
    setRepositories((prev) => prev.filter((r) => r.id !== id));
    try {
      const res = await fetch(`${API_BASE}/repos/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!res.ok) throw new Error();
      toast.success("Repository removed");
    } catch {
      toast.error("Failed to remove repository");
      setRepositories((prev) => [...prev]);
    }
  };

  const filteredRepositories = repositories.filter(repo =>
    repo.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const perspectiveConfig = {
    "system-context": { label: "System Context", description: "High-level view", icon: Home },
    conceptual: { label: "Conceptual", description: "Business view", icon: LayoutGrid },
    component: { label: "Component", description: "Developer view", icon: Code },
    operational: { label: "Operational", description: "DevOps view", icon: SettingsIcon },
  };

  const breadcrumbs =
    currentView === "activity" ? ["Home", "Alerts"] :
    currentView === "settings" ? ["Home", "Settings"] :
    currentView === "teams"    ? ["Home", "Teams"] :
    currentView === "repository" && selectedRepo ? ["Home", "Repositories", selectedRepo.name] :
    ["Home", "Repositories"];

  return (
    <>
    {showAddModal && (
      <AddRepositoryModal
        onClose={() => setShowAddModal(false)}
        onAdd={handleAddRepository}
      />
    )}
    <div className="min-h-screen bg-[#0a0a0f] text-white">
      {/* Navbar */}
      <nav className="border-b border-white/10 bg-[#0f0f15]/80 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-[1800px] mx-auto px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-12">
            <h1 className="text-xl tracking-tight">DynoDocs</h1>
            <div className="hidden md:flex gap-8 text-[13px]">
              <Link
                href="/diagrams"
                className={`transition-colors ${currentView === "dashboard" ? "text-white" : "text-white/60 hover:text-white"}`}
              >Diagrams</Link>
              <Link
                href="/activity"
                className={`transition-colors ${currentView === "activity" ? "text-white" : "text-white/60 hover:text-white"}`}
              >Alerts</Link>
              <Link
                href="/teams"
                className={`transition-colors ${currentView === "teams" ? "text-white" : "text-white/60 hover:text-white"}`}
              >Teams</Link>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div ref={notificationsDropdownRef} className="relative">
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => setShowNotificationsDropdown(!showNotificationsDropdown)}
                className="relative p-2 hover:bg-white/5 rounded-full transition-colors"
              >
                <Bell className="w-5 h-5 text-white/60" />
              </motion.button>

              <AnimatePresence>
                {showNotificationsDropdown && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 10 }}
                    className="absolute right-0 top-full mt-2 w-80 border border-white/10 bg-[#0f0f15] shadow-xl z-50"
                  >
                    <div className="p-4 border-b border-white/10">
                      <h3 className="text-[14px]">Notifications</h3>
                      <p className="text-[11px] text-white/50 mt-1">You’re all caught up</p>
                    </div>
                    <div className="p-6 text-center text-[12px] text-white/45">
                      No notifications yet.
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            <div ref={userDropdownRef} className="relative">
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => setShowUserDropdown(!showUserDropdown)}
                      className="w-10 h-10 rounded-full bg-linear-to-br from-blue-500 to-purple-600 flex items-center justify-center text-[14px] font-medium"
              >
                {initials}
              </motion.button>

              <AnimatePresence>
                {showUserDropdown && (
                  <motion.div
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 10 }}
                    className="absolute right-0 top-full mt-2 w-48 border border-white/10 bg-[#0f0f15] shadow-xl z-50"
                  >
                    <div className="p-3 border-b border-white/10">
                      <p className="text-[13px]">{fullName}</p>
                      <p className="text-[11px] text-white/50">{user?.email ?? ""}</p>
                    </div>
                    <button
                      onClick={() => { setShowUserDropdown(false); setSubView("settings"); }}
                      className="w-full px-4 py-3 flex items-center gap-2 text-[13px] text-white/80 hover:bg-white/5 transition-colors border-b border-white/5"
                    >
                      <SettingsIcon className="w-4 h-4" />
                      Settings
                    </button>
                    <button
                      onClick={() => { setShowUserDropdown(false); handleLogout(); }}
                      className="w-full px-4 py-3 flex items-center gap-2 text-[13px] text-white/80 hover:bg-white/5 transition-colors"
                    >
                      <LogOut className="w-4 h-4" />
                      Logout
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </div>
      </nav>

      {/* Breadcrumbs */}
      <div className="border-b border-white/5 bg-[#0f0f15]/40">
        <div className="max-w-[1800px] mx-auto px-8 py-3">
          <div className="flex items-center gap-2 text-[12px]">
            {breadcrumbs.map((crumb, index) => (
              <div key={index} className="flex items-center gap-2">
                {index > 0 && <ChevronRight className="w-3 h-3 text-white/30" />}
                <span className={index === breadcrumbs.length - 1 ? "text-white" : "text-white/50"}>
                  {crumb}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Sub-pages */}
      {currentView === "activity" && <ActivityPage />}
      {currentView === "settings" && <SettingsPage onBack={() => setSubView(null)} />}
      {currentView === "teams" && <TeamsPage onBack={() => router.push("/diagrams")} />}
      {currentView === "repository" && selectedRepo && (
        <RepositoryDetail
          repository={selectedRepo}
          initialView={mapPerspectiveToRepositoryView(perspective)}
          onViewChange={(view) => setPerspective(mapRepositoryViewToPerspective(view))}
          onRepositoryUpdate={upsertRepository}
        />
      )}

      {/* Dashboard Main Content */}
      {currentView === "dashboard" && <div className="max-w-[1800px] mx-auto px-8 py-12">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column - Repositories */}
          <div className="lg:col-span-2 space-y-6">
            <div className="flex items-center justify-between mb-8">
              <div>
                <h2 className="text-[clamp(1.8rem,3vw,2.5rem)] mb-2 leading-tight">Your Diagrams</h2>
                <p className="text-[14px] text-white/60">
                  {reposLoading ? "Loading…" : `${repositories.length} ${repositories.length === 1 ? "repository" : "repositories"} mapped`}
                </p>
              </div>

              <motion.button
                whileHover={{ scale: 1.02, backgroundColor: "rgba(255, 255, 255, 1)" }}
                whileTap={{ scale: 0.98 }}
                onClick={() => setShowAddModal(true)}
                className="px-6 py-3 bg-white text-black uppercase text-[11px] tracking-[0.15em] transition-all flex items-center gap-2"
              >
                <Plus className="w-4 h-4" />
                Add Repository
              </motion.button>
            </div>

            {/* Multi-Perspective Switcher */}
            <div className="border border-white/10 bg-[#0f0f15]/60 p-6 mb-6">
              <div className="text-[11px] uppercase tracking-[0.15em] text-white/60 mb-4">
                View Perspective
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {(Object.keys(perspectiveConfig) as ViewPerspective[]).map((key) => {
                  const config = perspectiveConfig[key];
                  const Icon = config.icon;
                  return (
                    <motion.button
                      key={key}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={() => setPerspective(key)}
                      className={`p-4 border transition-all ${
                        perspective === key
                          ? "border-blue-500 bg-blue-500/10"
                          : "border-white/10 bg-white/5 hover:bg-white/10"
                      }`}
                    >
                      <Icon className={`w-5 h-5 mb-2 ${perspective === key ? "text-blue-400" : "text-white/60"}`} />
                      <div className={`text-[12px] mb-1 ${perspective === key ? "text-white" : "text-white/70"}`}>
                        {config.label}
                      </div>
                      <div className="text-[10px] text-white/40">{config.description}</div>
                    </motion.button>
                  );
                })}
              </div>
            </div>

            {/* Search */}
            <div className="relative mb-6">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search repositories..."
                className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/10 focus:border-white/30 focus:outline-none transition-colors text-[14px] text-white placeholder:text-white/30"
              />
            </div>

            {/* Repository List */}
            <div className="space-y-4">
              {(authLoading || reposLoading) ? (
                <div className="border border-white/10 bg-[#0f0f15]/60 p-12 text-center">
                  <p className="text-white/50">Loading repositories…</p>
                </div>
              ) : filteredRepositories.length === 0 ? (
                <div className="border border-white/10 bg-[#0f0f15]/60 p-12 text-center">
                  <p className="text-white/50 mb-2">No repositories yet</p>
                  <p className="text-white/30 text-[12px]">Click &ldquo;Add Repository&rdquo; to get started</p>
                </div>
              ) : (
                filteredRepositories.map((repo) => (
                  <motion.div
                    key={repo.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    whileHover={{ backgroundColor: "rgba(255, 255, 255, 0.03)" }}
                    onClick={() => { setSelectedRepo(repo); setSubView("repository"); }}
                    className="border border-white/10 bg-[#0f0f15]/60 p-6 transition-all group cursor-pointer"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <GitBranch className="w-4 h-4 text-blue-400" />
                          <h3 className="text-[18px]">{repo.name}</h3>
                        </div>
                        <p className="text-[13px] text-white/50 mb-3">{repo.url}</p>
                        <div className="flex items-center gap-6 text-[12px] text-white/40">
                          {repo.lastUpdated ? <span>Updated {repo.lastUpdated}</span> : null}
                        </div>
                      </div>

                      <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <motion.button
                          whileHover={{ scale: 1.1 }}
                          whileTap={{ scale: 0.9 }}
                          onClick={(e) => { e.stopPropagation(); handleEditRepository(repo); }}
                          className="p-2 hover:bg-white/10 rounded transition-colors"
                        >
                          <Edit3 className="w-4 h-4 text-white/60" />
                        </motion.button>
                        <motion.button
                          whileHover={{ scale: 1.1 }}
                          whileTap={{ scale: 0.9 }}
                          onClick={(e) => { e.stopPropagation(); handleDeleteRepository(repo.id); }}
                          className="p-2 hover:bg-red-500/20 rounded transition-colors"
                        >
                          <Trash2 className="w-4 h-4 text-red-400/60" />
                        </motion.button>
                      </div>
                    </div>
                  </motion.div>
                ))
              )}
            </div>
          </div>

          {/* Right Column - Recent Alerts */}
          <div className="space-y-6">
            <div>
              <h3 className="text-[18px] mb-2 flex items-center gap-2">
                <Bell className="w-4 h-4 text-blue-400" />
                Recent Alerts
              </h3>
              <p className="text-[12px] text-white/50 mb-6">Top 3 alerts across all of your repositories</p>
            </div>

            <div className="space-y-3">
              {alertsLoading ? (
                <div className="border border-white/10 bg-[#0f0f15]/40 px-4 py-6 text-[12px] text-white/45 flex items-center gap-3">
                  <Bell className="w-4 h-4 text-blue-400 animate-pulse" />
                  Collecting alerts from your repositories...
                </div>
              ) : activities.length === 0 ? (
                <div className="border border-white/10 bg-[#0f0f15]/40 px-4 py-6 text-[12px] text-white/45">
                  No recent alerts found across your repositories.
                </div>
              ) : activities.map((activity) => (
                <motion.div
                  key={activity.id}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  className={`border-l-2 pl-4 py-3 transition-colors ${
                    activity.severity === "critical"
                      ? "border-red-500/50 bg-red-500/5 hover:bg-red-500/10"
                      : activity.severity === "high" || activity.severity === "medium"
                      ? "border-yellow-500/50 bg-yellow-500/5 hover:bg-yellow-500/10"
                      : "border-blue-500/30 bg-[#0f0f15]/40 hover:bg-[#0f0f15]/60"
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className={`w-2 h-2 rounded-full mt-1.5 ${
                      activity.severity === "critical" ? "bg-red-500" :
                      activity.severity === "high" || activity.severity === "medium" ? "bg-yellow-500" :
                      "bg-blue-500"
                    }`} />
                    <div className="flex-1">
                      <p className="text-[13px] text-white/80 mb-1">{activity.message}</p>
                      <div className="flex items-center gap-3 text-[11px] text-white/40">
                        <span>{activity.repository}</span>
                        <span>{activity.timestamp}</span>
                      </div>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>

            <Link
              href="/activity"
              className="block w-full py-3 border border-white/10 text-[12px] text-white/60 hover:bg-white/5 hover:text-white transition-all uppercase tracking-[0.15em] text-center"
            >
              View All Alerts
            </Link>
          </div>
        </div>
      </div>}
    </div>
    </>
  );
}
