"use client";

import { motion } from "motion/react";
import { useState } from "react";
import { User, Bell, Shield, Users, Mail } from "lucide-react";
import { FaGithub } from "react-icons/fa";
import { toast } from "sonner";

interface SettingsPageProps {
  onBack: () => void;
}

export function SettingsPage({ onBack: _onBack }: SettingsPageProps) {
  void _onBack;
  const [activeTab, setActiveTab] = useState<"profile" | "notifications" | "teams" | "security">("profile");

  const [profileData, setProfileData] = useState({
    name: "",
    email: "",
    github: "",
    company: "",
  });

  const [notificationSettings, setNotificationSettings] = useState({
    emailNotifications: true,
    teamUpdates: true,
    systemAlerts: true,
    weeklyDigest: false,
  });

  const handleSaveProfile = () => {
    toast.success("Profile updated successfully");
  };

  const handleSaveNotifications = () => {
    toast.success("Notification preferences saved");
  };

  const tabs = [
    { id: "profile",       label: "Profile",       icon: User },
    { id: "notifications", label: "Notifications", icon: Bell },
    { id: "teams",         label: "Teams",         icon: Users },
    { id: "security",      label: "Security",      icon: Shield },
  ] as const;

  return (
    <div className="max-w-350 mx-auto px-8 py-12">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
        {/* Sidebar */}
        <div className="space-y-2">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full px-4 py-3 flex items-center gap-3 text-left transition-all ${
                  activeTab === tab.id
                    ? "bg-white/10 border-l-2 border-blue-500"
                    : "hover:bg-white/5 border-l-2 border-transparent"
                }`}
              >
                <Icon className="w-4 h-4" />
                <span className="text-[14px]">{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Main Content */}
        <div className="md:col-span-3">
          {activeTab === "profile" && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="border border-white/10 bg-[#0f0f15]/60 p-8"
            >
              <h2 className="text-[20px] mb-6">Profile Information</h2>
              <div className="space-y-5">
                <div>
                  <label className="block text-[11px] uppercase tracking-[0.15em] text-white/60 mb-2">
                    Full Name
                  </label>
                  <input
                    type="text"
                    value={profileData.name}
                    onChange={(e) => setProfileData({ ...profileData, name: e.target.value })}
                    className="w-full px-4 py-3 bg-white/5 border border-white/10 focus:border-white/30 focus:outline-none transition-colors text-[14px] text-white placeholder:text-white/30"
                    placeholder="John Doe"
                  />
                </div>

                <div>
                  <label className="block text-[11px] uppercase tracking-[0.15em] text-white/60 mb-2">
                    Email Address
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                    <input
                      type="email"
                      value={profileData.email}
                      onChange={(e) => setProfileData({ ...profileData, email: e.target.value })}
                      className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/10 focus:border-white/30 focus:outline-none transition-colors text-[14px] text-white placeholder:text-white/30"
                      placeholder="you@company.com"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] uppercase tracking-[0.15em] text-white/60 mb-2">
                    GitHub Username
                  </label>
                  <div className="relative">
                    <FaGithub className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                    <input
                      type="text"
                      value={profileData.github}
                      onChange={(e) => setProfileData({ ...profileData, github: e.target.value })}
                      className="w-full pl-12 pr-4 py-3 bg-white/5 border border-white/10 focus:border-white/30 focus:outline-none transition-colors text-[14px] text-white placeholder:text-white/30"
                      placeholder="johndoe"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] uppercase tracking-[0.15em] text-white/60 mb-2">
                    Company
                  </label>
                  <input
                    type="text"
                    value={profileData.company}
                    onChange={(e) => setProfileData({ ...profileData, company: e.target.value })}
                    className="w-full px-4 py-3 bg-white/5 border border-white/10 focus:border-white/30 focus:outline-none transition-colors text-[14px] text-white placeholder:text-white/30"
                    placeholder="Acme Inc."
                  />
                </div>

                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={handleSaveProfile}
                  className="px-8 py-3 bg-white text-black uppercase text-[11px] tracking-[0.15em] hover:bg-white/90 transition-colors"
                >
                  Save Changes
                </motion.button>
              </div>
            </motion.div>
          )}

          {activeTab === "notifications" && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="border border-white/10 bg-[#0f0f15]/60 p-8"
            >
              <h2 className="text-[20px] mb-6">Notification Preferences</h2>
              <div className="space-y-6">
                {(Object.entries(notificationSettings) as [keyof typeof notificationSettings, boolean][]).map(([key, value]) => (
                  <div key={key} className="flex items-center justify-between py-3 border-b border-white/5">
                    <div>
                      <p className="text-[14px] mb-1">
                        {key.replace(/([A-Z])/g, " $1").replace(/^./, (s) => s.toUpperCase())}
                      </p>
                      <p className="text-[12px] text-white/50">
                        {key === "emailNotifications" && "Receive email notifications for updates"}
                        {key === "teamUpdates" && "Get notified when team members make changes"}
                        {key === "systemAlerts" && "Receive alerts for system issues"}
                        {key === "weeklyDigest" && "Weekly summary of activity"}
                      </p>
                    </div>
                    <button
                      onClick={() => setNotificationSettings({ ...notificationSettings, [key]: !value })}
                      className={`relative w-12 h-6 rounded-full transition-colors ${value ? "bg-blue-500" : "bg-white/20"}`}
                    >
                      <motion.div
                        animate={{ x: value ? 24 : 0 }}
                        className="absolute top-1 left-1 w-4 h-4 bg-white rounded-full"
                      />
                    </button>
                  </div>
                ))}

                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={handleSaveNotifications}
                  className="px-8 py-3 bg-white text-black uppercase text-[11px] tracking-[0.15em] hover:bg-white/90 transition-colors mt-6"
                >
                  Save Preferences
                </motion.button>
              </div>
            </motion.div>
          )}

          {activeTab === "teams" && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="border border-white/10 bg-[#0f0f15]/60 p-8"
            >
              <h2 className="text-[20px] mb-2">Team Settings</h2>
              <p className="text-[13px] text-white/60 mb-6">Manage your teams and collaborators</p>
              <p className="text-[14px] text-white/70">
                Team management features are coming soon. You will be able to create teams, invite members by email or GitHub username, and manage repository access.
              </p>
            </motion.div>
          )}

          {activeTab === "security" && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="border border-white/10 bg-[#0f0f15]/60 p-8"
            >
              <h2 className="text-[20px] mb-6">Security</h2>
              <div className="space-y-6">
                <div>
                  <h3 className="text-[14px] mb-3">Change Password</h3>
                  <div className="space-y-4">
                    <input
                      type="password"
                      placeholder="Current password"
                      className="w-full px-4 py-3 bg-white/5 border border-white/10 focus:border-white/30 focus:outline-none transition-colors text-[14px] text-white placeholder:text-white/30"
                    />
                    <input
                      type="password"
                      placeholder="New password"
                      className="w-full px-4 py-3 bg-white/5 border border-white/10 focus:border-white/30 focus:outline-none transition-colors text-[14px] text-white placeholder:text-white/30"
                    />
                    <input
                      type="password"
                      placeholder="Confirm new password"
                      className="w-full px-4 py-3 bg-white/5 border border-white/10 focus:border-white/30 focus:outline-none transition-colors text-[14px] text-white placeholder:text-white/30"
                    />
                  </div>
                </div>

                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => toast.success("Password updated successfully")}
                  className="px-8 py-3 bg-white text-black uppercase text-[11px] tracking-[0.15em] hover:bg-white/90 transition-colors"
                >
                  Update Password
                </motion.button>
              </div>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  );
}
