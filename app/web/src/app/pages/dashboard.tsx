"use client";

import { motion } from "motion/react";
import { useState } from "react";
import { Search, Plus, GitBranch, Trash2, Edit3, Bell, ChevronRight, LayoutGrid, Code, Settings as SettingsIcon } from "lucide-react";
import { toast } from "sonner";

interface Repository {
  id: string;
  name: string;
  url: string;
  lastUpdated: string;
  componentsCount: number;
}

interface Activity {
  id: string;
  type: "update" | "alert" | "task";
  message: string;
  timestamp: string;
}

type ViewPerspective = "conceptual" | "component" | "operational";

interface DashboardProps {
  onLogout?: () => void;
}

export function Dashboard({ onLogout }: DashboardProps) {
  const [repositories, setRepositories] = useState<Repository[]>([
    {
      id: "1",
      name: "main-api",
      url: "github.com/company/main-api",
      lastUpdated: "2 hours ago",
      componentsCount: 12
    },
    {
      id: "2",
      name: "frontend-app",
      url: "github.com/company/frontend-app",
      lastUpdated: "5 hours ago",
      componentsCount: 8
    },
    {
      id: "3",
      name: "payment-service",
      url: "github.com/company/payment-service",
      lastUpdated: "1 day ago",
      componentsCount: 6
    }
  ]);

  const [activities] = useState<Activity[]>([
    { id: "1", type: "update", message: "Database schema updated in main-api", timestamp: "10 min ago" },
    { id: "2", type: "task", message: "New bottleneck detected in payment-service", timestamp: "1 hour ago" },
    { id: "3", type: "alert", message: "High latency detected in API Gateway", timestamp: "3 hours ago" },
  ]);

  const [searchQuery, setSearchQuery] = useState("");
  const [perspective, setPerspective] = useState<ViewPerspective>("component");
  const [breadcrumbs] = useState(["Home", "Repositories"]);

  const handleAddRepository = () => {
    toast.success("Repository added successfully", {
      description: "Your architecture diagram is being generated",
    });
  };

  const handleEditRepository = (repo: Repository) => {
    toast.info(`Editing ${repo.name}`);
  };

  const handleDeleteRepository = (id: string) => {
    setRepositories(repositories.filter(r => r.id !== id));
    toast.success("Repository removed");
  };

  const filteredRepositories = repositories.filter(repo =>
    repo.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const perspectiveConfig = {
    conceptual: { label: "Conceptual", description: "Business view", icon: LayoutGrid },
    component: { label: "Component", description: "Developer view", icon: Code },
    operational: { label: "Operational", description: "DevOps view", icon: SettingsIcon },
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white">
      {/* Navbar */}
      <nav className="border-b border-white/10 bg-[#0f0f15]/80 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-[1800px] mx-auto px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-12">
            <h1 className="text-xl tracking-tight">DynoDocs</h1>
            <div className="hidden md:flex gap-8 text-[13px]">
              <a href="#" className="text-white/60 hover:text-white transition-colors">Diagrams</a>
              <a href="#" className="text-white/60 hover:text-white transition-colors">Activity</a>
              <a href="#" className="text-white/60 hover:text-white transition-colors">Settings</a>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className="relative p-2 hover:bg-white/5 rounded-full transition-colors"
            >
              <Bell className="w-5 h-5 text-white/60" />
              <span className="absolute top-1 right-1 w-2 h-2 bg-blue-500 rounded-full"></span>
            </motion.button>

            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={onLogout}
              className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-[14px] font-medium"
            >
              JD
            </motion.button>
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

      {/* Main Content */}
      <div className="max-w-[1800px] mx-auto px-8 py-12">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column - Repositories */}
          <div className="lg:col-span-2 space-y-6">
            <div className="flex items-center justify-between mb-8">
              <div>
                <h2 className="text-[clamp(1.8rem,3vw,2.5rem)] mb-2 leading-tight">Your Diagrams</h2>
                <p className="text-[14px] text-white/60">
                  {repositories.length} {repositories.length === 1 ? "repository" : "repositories"} mapped
                </p>
              </div>

              <motion.button
                whileHover={{ scale: 1.02, backgroundColor: "rgba(255, 255, 255, 1)" }}
                whileTap={{ scale: 0.98 }}
                onClick={handleAddRepository}
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
              <div className="grid grid-cols-3 gap-3">
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
              {filteredRepositories.length === 0 ? (
                <div className="border border-white/10 bg-[#0f0f15]/60 p-12 text-center">
                  <p className="text-white/50">No repositories found</p>
                </div>
              ) : (
                filteredRepositories.map((repo) => (
                  <motion.div
                    key={repo.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    whileHover={{ backgroundColor: "rgba(255, 255, 255, 0.03)" }}
                    className="border border-white/10 bg-[#0f0f15]/60 p-6 transition-all group"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <GitBranch className="w-4 h-4 text-blue-400" />
                          <h3 className="text-[18px]">{repo.name}</h3>
                        </div>
                        <p className="text-[13px] text-white/50 mb-3">{repo.url}</p>
                        <div className="flex items-center gap-6 text-[12px] text-white/40">
                          <span>{repo.componentsCount} components</span>
                          <span>Updated {repo.lastUpdated}</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <motion.button
                          whileHover={{ scale: 1.1 }}
                          whileTap={{ scale: 0.9 }}
                          onClick={() => handleEditRepository(repo)}
                          className="p-2 hover:bg-white/10 rounded transition-colors"
                        >
                          <Edit3 className="w-4 h-4 text-white/60" />
                        </motion.button>
                        <motion.button
                          whileHover={{ scale: 1.1 }}
                          whileTap={{ scale: 0.9 }}
                          onClick={() => handleDeleteRepository(repo.id)}
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

          {/* Right Column - Activity Feed */}
          <div className="space-y-6">
            <div>
              <h3 className="text-[18px] mb-2 flex items-center gap-2">
                <Bell className="w-4 h-4 text-blue-400" />
                Recent Activity
              </h3>
              <p className="text-[12px] text-white/50 mb-6">Real-time system updates</p>
            </div>

            <div className="space-y-3">
              {activities.map((activity) => (
                <motion.div
                  key={activity.id}
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="border-l-2 border-blue-500/30 pl-4 py-3 bg-[#0f0f15]/40 hover:bg-[#0f0f15]/60 transition-colors"
                >
                  <div className="flex items-start gap-3">
                    <div className={`w-2 h-2 rounded-full mt-1.5 ${
                      activity.type === "alert" ? "bg-red-500" :
                      activity.type === "task" ? "bg-yellow-500" :
                      "bg-blue-500"
                    }`}></div>
                    <div className="flex-1">
                      <p className="text-[13px] text-white/80 mb-1">{activity.message}</p>
                      <p className="text-[11px] text-white/40">{activity.timestamp}</p>
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>

            <button className="w-full py-3 border border-white/10 text-[12px] text-white/60 hover:bg-white/5 hover:text-white transition-all uppercase tracking-[0.15em]">
              View All Activity
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
