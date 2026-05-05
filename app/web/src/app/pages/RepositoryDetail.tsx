"use client";

import { motion } from "motion/react";
import { useState } from "react";
import { Activity, LayoutGrid, Code, Settings as SettingsIcon, AlertCircle, TrendingUp, Layers } from "lucide-react";
import { DiagramView } from "@/components/DiagramView";

interface Repository {
  id: string;
  name: string;
  url: string;
  lastUpdated: string;
  componentsCount: number;
}

interface RepositoryDetailProps {
  repository: Repository;
}

type ArchitectureView = "context" | "conceptual" | "component" | "operational";

export function RepositoryDetail({ repository }: RepositoryDetailProps) {
  const [currentView, setCurrentView] = useState<ArchitectureView>("component");

  const recentActivity = [
    { id: "1", type: "update",  message: "API endpoint /users optimized",                  time: "5 min ago",  severity: "info" },
    { id: "2", type: "alert",   message: "Database connection pool at 85% capacity",        time: "15 min ago", severity: "warning" },
    { id: "3", type: "update",  message: "Cache layer updated to Redis 7.0",                time: "1 hour ago", severity: "info" },
    { id: "4", type: "alert",   message: "Payment gateway response time increased",         time: "2 hours ago",severity: "critical" },
    { id: "5", type: "update",  message: "New microservice deployed: notification-service", time: "3 hours ago",severity: "info" },
  ];

  const systemMetrics = [
    { label: "Active Services",    value: "12",    trend: "+2" },
    { label: "API Requests/min",   value: "2.4K",  trend: "+12%" },
    { label: "Avg Response Time",  value: "145ms", trend: "-8%" },
    { label: "Error Rate",         value: "0.03%", trend: "-15%" },
  ];

  const views = {
    context:     { label: "System Context", description: "High-level view",               icon: Layers },
    conceptual:  { label: "Conceptual",     description: "Business-level system overview", icon: LayoutGrid },
    component:   { label: "Component",      description: "Developer architecture view",   icon: Code },
    operational: { label: "Operational",    description: "DevOps infrastructure view",    icon: SettingsIcon },
  };

  const renderArchitectureDiagram = () => {
    if (currentView === "context") {
      return (
        <div className="space-y-6">
          <div className="border border-white/10 bg-[#0f0f15]/60 p-12 text-center">
            <h4 className="text-[16px] mb-4">System Context Diagram</h4>
            <p className="text-[13px] text-white/60 mb-8">
              2.5D visualization with animated data flow showing bottlenecks and system interactions
            </p>
            <div className="grid grid-cols-3 gap-8">
              {["External Users", repository.name, "External Services"].map((entity, idx) => (
                <motion.div
                  key={entity}
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: idx * 0.15 }}
                  className="border border-cyan-500/30 bg-cyan-500/5 p-8"
                >
                  <h5 className="text-[14px] mb-2">{entity}</h5>
                  <div className="w-full h-px bg-linear-to-r from-transparent via-cyan-500 to-transparent mt-4" />
                </motion.div>
              ))}
            </div>
          </div>
        </div>
      );
    }

    if (currentView === "conceptual") {
      return (
        <div className="space-y-6">
          <div className="grid grid-cols-3 gap-6">
            {["User Interface", "Business Logic", "Data Storage"].map((layer, idx) => (
              <motion.div
                key={layer}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.1 }}
                className="border border-blue-500/30 bg-blue-500/5 p-6 text-center"
              >
                <h4 className="text-[14px] mb-2">{layer}</h4>
                <p className="text-[11px] text-white/50">Layer {idx + 1}</p>
              </motion.div>
            ))}
          </div>
          <div className="border border-white/10 bg-[#0f0f15]/60 p-8 text-center">
            <p className="text-[13px] text-white/60">High-level business flow visualization</p>
          </div>
        </div>
      );
    }

    if (currentView === "component") {
      return <DiagramView />;
    }

    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-6">
          {["Load Balancer", "Container Cluster", "Database Cluster", "Monitoring"].map((infra, idx) => (
            <motion.div
              key={infra}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.1 }}
              className="border border-purple-500/30 bg-purple-500/5 p-6"
            >
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-[14px]">{infra}</h4>
                <div className="w-2 h-2 bg-green-500 rounded-full" />
              </div>
              <div className="space-y-2 text-[11px] text-white/50">
                <div className="flex justify-between"><span>CPU</span><span>42%</span></div>
                <div className="flex justify-between"><span>Memory</span><span>58%</span></div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    );
  };

  return (
    <div className="bg-[#0a0a0f] text-white">
      <div className="max-w-[1800px] mx-auto px-8 py-12">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main — Architecture View */}
          <div className="lg:col-span-2 space-y-6">
            <div className="border border-white/10 bg-[#0f0f15]/60 p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-[18px]">System Architecture</h2>
                <div className="text-[11px] text-white/50 uppercase tracking-[0.15em]">
                  {repository.componentsCount} Components
                </div>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
                {(Object.keys(views) as ArchitectureView[]).map((viewKey) => {
                  const view = views[viewKey];
                  const Icon = view.icon;
                  return (
                    <motion.button
                      key={viewKey}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      onClick={() => setCurrentView(viewKey)}
                      className={`p-4 border transition-all ${
                        currentView === viewKey
                          ? "border-blue-500 bg-blue-500/10"
                          : "border-white/10 bg-white/5 hover:bg-white/10"
                      }`}
                    >
                      <Icon className={`w-5 h-5 mb-2 mx-auto ${currentView === viewKey ? "text-blue-400" : "text-white/60"}`} />
                      <div className={`text-[12px] mb-1 ${currentView === viewKey ? "text-white" : "text-white/70"}`}>
                        {view.label}
                      </div>
                      <div className="text-[10px] text-white/40">{view.description}</div>
                    </motion.button>
                  );
                })}
              </div>

              <div className="border border-white/10 bg-black/20 p-8">
                {renderArchitectureDiagram()}
              </div>
            </div>

            {/* System Metrics */}
            <div className="border border-white/10 bg-[#0f0f15]/60 p-6">
              <h3 className="text-[16px] mb-6 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-green-400" />
                System Metrics
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                {systemMetrics.map((metric) => (
                  <div key={metric.label} className="border border-white/10 bg-white/5 p-4">
                    <p className="text-[11px] text-white/50 mb-2 uppercase tracking-wider">{metric.label}</p>
                    <div className="flex items-baseline gap-2">
                      <span className="text-[24px]">{metric.value}</span>
                      <span className={`text-[11px] ${metric.trend.startsWith('+') ? 'text-green-400' : 'text-blue-400'}`}>
                        {metric.trend}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Sidebar — Recent Activity */}
          <div className="space-y-6">
            <div className="border border-white/10 bg-[#0f0f15]/60 p-6">
              <h3 className="text-[16px] mb-2 flex items-center gap-2">
                <Activity className="w-4 h-4 text-blue-400" />
                Recent Activity
              </h3>
              <p className="text-[11px] text-white/50 mb-6">System updates and alerts</p>

              <div className="space-y-3">
                {recentActivity.map((activity) => (
                  <motion.div
                    key={activity.id}
                    initial={{ opacity: 0, x: 20 }}
                    animate={{ opacity: 1, x: 0 }}
                    className={`border-l-2 pl-4 py-3 ${
                      activity.severity === "critical"
                        ? "border-red-500/50 bg-red-500/5"
                        : activity.severity === "warning"
                        ? "border-yellow-500/50 bg-yellow-500/5"
                        : "border-blue-500/30 bg-blue-500/5"
                    }`}
                  >
                    <div className="flex items-start gap-3">
                      {activity.severity === "critical" || activity.severity === "warning" ? (
                        <AlertCircle className={`w-4 h-4 mt-0.5 ${
                          activity.severity === "critical" ? "text-red-400" : "text-yellow-400"
                        }`} />
                      ) : (
                        <div className="w-2 h-2 bg-blue-500 rounded-full mt-1.5" />
                      )}
                      <div className="flex-1">
                        <p className="text-[13px] text-white/80 mb-1">{activity.message}</p>
                        <p className="text-[11px] text-white/40">{activity.time}</p>
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
