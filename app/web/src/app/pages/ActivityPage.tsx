import { motion } from "motion/react";
import { useState } from "react";
import { AlertCircle, Info, AlertTriangle, CheckCircle, Filter, Search } from "lucide-react";

interface Activity {
  id: string;
  type: "update" | "alert" | "task" | "success";
  severity: "info" | "warning" | "critical" | "success";
  message: string;
  repository: string;
  timestamp: string;
  details?: string;
}

export function ActivityPage() {
  const [filterType, setFilterType] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  const activities: Activity[] = [
    {
      id: "1",
      type: "alert",
      severity: "critical",
      message: "Database connection pool at 95% capacity",
      repository: "main-api",
      timestamp: "2 minutes ago",
      details: "Primary database connection pool is reaching critical levels. Consider scaling up."
    },
    {
      id: "2",
      type: "update",
      severity: "info",
      message: "API endpoint /users optimized",
      repository: "main-api",
      timestamp: "15 minutes ago",
      details: "Response time improved by 35%"
    },
    {
      id: "3",
      type: "alert",
      severity: "warning",
      message: "High memory usage in payment-service",
      repository: "payment-service",
      timestamp: "45 minutes ago",
      details: "Memory usage at 78%. Monitor for potential memory leaks."
    },
    {
      id: "4",
      type: "success",
      severity: "success",
      message: "Load balancer configuration updated successfully",
      repository: "frontend-app",
      timestamp: "1 hour ago",
      details: "Traffic distribution optimized across 3 instances"
    },
    {
      id: "5",
      type: "update",
      severity: "info",
      message: "New microservice deployed",
      repository: "notification-service",
      timestamp: "2 hours ago",
      details: "Notification service v2.1.0 deployed to production"
    },
    {
      id: "6",
      type: "task",
      severity: "warning",
      message: "Bottleneck detected in queue processing",
      repository: "payment-service",
      timestamp: "3 hours ago",
      details: "Job queue processing time increased by 120%"
    },
    {
      id: "7",
      type: "alert",
      severity: "critical",
      message: "API Gateway experiencing high latency",
      repository: "main-api",
      timestamp: "4 hours ago",
      details: "P95 latency increased to 2.5s"
    },
    {
      id: "8",
      type: "update",
      severity: "info",
      message: "Cache hit rate improved",
      repository: "main-api",
      timestamp: "5 hours ago",
      details: "Redis cache optimization resulted in 87% hit rate"
    },
    {
      id: "9",
      type: "success",
      severity: "success",
      message: "Database migration completed",
      repository: "payment-service",
      timestamp: "6 hours ago",
      details: "Schema migration completed without downtime"
    },
    {
      id: "10",
      type: "alert",
      severity: "warning",
      message: "Increased error rate in authentication",
      repository: "main-api",
      timestamp: "8 hours ago",
      details: "Auth error rate at 0.8%, investigate token validation"
    },
  ];

  const filteredActivities = activities.filter((activity) => {
    const matchesType = filterType === "all" || activity.severity === filterType;
    const matchesSearch =
      searchQuery === "" ||
      activity.message.toLowerCase().includes(searchQuery.toLowerCase()) ||
      activity.repository.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesType && matchesSearch;
  });

  const getIcon = (severity: string) => {
    switch (severity) {
      case "critical":
        return <AlertCircle className="w-5 h-5 text-red-400" />;
      case "warning":
        return <AlertTriangle className="w-5 h-5 text-yellow-400" />;
      case "success":
        return <CheckCircle className="w-5 h-5 text-green-400" />;
      default:
        return <Info className="w-5 h-5 text-blue-400" />;
    }
  };

  const getBorderColor = (severity: string) => {
    switch (severity) {
      case "critical": return "border-red-500/50";
      case "warning":  return "border-yellow-500/50";
      case "success":  return "border-green-500/50";
      default:         return "border-blue-500/30";
    }
  };

  const getBgColor = (severity: string) => {
    switch (severity) {
      case "critical": return "bg-red-500/5 hover:bg-red-500/10";
      case "warning":  return "bg-yellow-500/5 hover:bg-yellow-500/10";
      case "success":  return "bg-green-500/5 hover:bg-green-500/10";
      default:         return "bg-blue-500/5 hover:bg-blue-500/10";
    }
  };

  const stats = [
    { label: "Total Events",  value: activities.length },
    { label: "Critical",      value: activities.filter(a => a.severity === "critical").length },
    { label: "Warnings",      value: activities.filter(a => a.severity === "warning").length },
    { label: "Last 24h",      value: activities.length },
  ];

  return (
    <div className="bg-[#0a0a0f] text-white">
      <div className="max-w-[1400px] mx-auto px-8 py-12">
        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {stats.map((stat) => (
            <div key={stat.label} className="border border-white/10 bg-[#0f0f15]/60 p-6">
              <p className="text-[11px] text-white/50 mb-2 uppercase tracking-wider">{stat.label}</p>
              <p className="text-[32px]">{stat.value}</p>
            </div>
          ))}
        </div>

        {/* Filters and Search */}
        <div className="flex flex-col md:flex-row gap-4 mb-8">
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search activities..."
              className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/10 focus:border-white/30 focus:outline-none transition-colors text-[14px] text-white placeholder:text-white/30"
            />
          </div>

          <div className="flex items-center gap-2 border border-white/10 bg-white/5 px-4">
            <Filter className="w-4 h-4 text-white/40" />
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="bg-transparent py-3 text-[14px] text-white focus:outline-none"
            >
              <option value="all">All Events</option>
              <option value="critical">Critical</option>
              <option value="warning">Warnings</option>
              <option value="success">Success</option>
              <option value="info">Info</option>
            </select>
          </div>
        </div>

        {/* Activity List */}
        <div className="space-y-3">
          {filteredActivities.length === 0 ? (
            <div className="border border-white/10 bg-[#0f0f15]/60 p-12 text-center">
              <p className="text-white/50">No activities found</p>
            </div>
          ) : (
            filteredActivities.map((activity, idx) => (
              <motion.div
                key={activity.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.05 }}
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
