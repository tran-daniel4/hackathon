"use client";

import { motion, AnimatePresence } from "motion/react";
import { useState } from "react";
import { Users, Plus, Trash2, Mail, Crown, X, ChevronRight } from "lucide-react";
import { FaGithub } from "react-icons/fa";
import { toast } from "sonner";

interface Member {
  id: string;
  name: string;
  email: string;
  github: string;
  role: "owner" | "admin" | "member";
}

interface Team {
  id: string;
  name: string;
  description: string;
  members: Member[];
}

interface TeamsPageProps {
  onBack: () => void;
}

const ROLE_COLOR = { owner: "text-yellow-400", admin: "text-blue-400", member: "text-white/50" } as const;

export function TeamsPage({ onBack: _onBack }: TeamsPageProps) {
  const [teams, setTeams] = useState<Team[]>([
    {
      id: "1",
      name: "Platform Engineering",
      description: "Core infrastructure and architecture owners",
      members: [
        { id: "1", name: "You", email: "you@company.com", github: "you", role: "owner" },
        { id: "2", name: "Sarah Chen", email: "sarah@company.com", github: "sarahchen", role: "admin" },
        { id: "3", name: "Mike Johnson", email: "mike@company.com", github: "mikej", role: "member" },
      ],
    },
  ]);

  const [selectedTeam, setSelectedTeam] = useState<Team | null>(teams[0] ?? null);
  const [showCreateTeam, setShowCreateTeam] = useState(false);
  const [showInvite, setShowInvite] = useState(false);

  const [newTeamName, setNewTeamName] = useState("");
  const [newTeamDesc, setNewTeamDesc] = useState("");
  const [inviteValue, setInviteValue] = useState("");
  const [inviteRole, setInviteRole] = useState<"admin" | "member">("member");

  const handleCreateTeam = () => {
    if (!newTeamName.trim()) {
      toast.error("Team name is required");
      return;
    }
    const team: Team = {
      id: Date.now().toString(),
      name: newTeamName.trim(),
      description: newTeamDesc.trim(),
      members: [{ id: Date.now().toString(), name: "You", email: "you@company.com", github: "you", role: "owner" }],
    };
    setTeams(prev => [...prev, team]);
    setSelectedTeam(team);
    setNewTeamName("");
    setNewTeamDesc("");
    setShowCreateTeam(false);
    toast.success(`Team "${team.name}" created`);
  };

  const handleInvite = () => {
    if (!inviteValue.trim()) {
      toast.error("Enter an email or GitHub username");
      return;
    }
    if (!selectedTeam) return;

    const isEmail = inviteValue.includes("@");
    const newMember: Member = {
      id: Date.now().toString(),
      name: isEmail ? inviteValue.split("@")[0] : inviteValue,
      email: isEmail ? inviteValue : `${inviteValue}@github`,
      github: isEmail ? "" : inviteValue,
      role: inviteRole,
    };

    const updated = { ...selectedTeam, members: [...selectedTeam.members, newMember] };
    setTeams(prev => prev.map(t => t.id === selectedTeam.id ? updated : t));
    setSelectedTeam(updated);
    setInviteValue("");
    setShowInvite(false);
    toast.success(`Invite sent to ${inviteValue}`);
  };

  const handleRemoveMember = (memberId: string) => {
    if (!selectedTeam) return;
    const member = selectedTeam.members.find(m => m.id === memberId);
    if (member?.role === "owner") {
      toast.error("Cannot remove the team owner");
      return;
    }
    const updated = { ...selectedTeam, members: selectedTeam.members.filter(m => m.id !== memberId) };
    setTeams(prev => prev.map(t => t.id === selectedTeam.id ? updated : t));
    setSelectedTeam(updated);
    toast.success("Member removed");
  };

  const handleChangeRole = (memberId: string, role: Member["role"]) => {
    if (!selectedTeam) return;
    const updated = {
      ...selectedTeam,
      members: selectedTeam.members.map(m => m.id === memberId ? { ...m, role } : m),
    };
    setTeams(prev => prev.map(t => t.id === selectedTeam.id ? updated : t));
    setSelectedTeam(updated);
  };

  const handleDeleteTeam = (teamId: string) => {
    const team = teams.find(t => t.id === teamId);
    const owner = team?.members.find(m => m.role === "owner");
    if (owner?.name !== "You") {
      toast.error("Only the team owner can delete a team");
      return;
    }
    setTeams(prev => prev.filter(t => t.id !== teamId));
    setSelectedTeam(teams.find(t => t.id !== teamId) ?? null);
    toast.success(`Team "${team?.name}" deleted`);
  };

  return (
    <div className="max-w-450 mx-auto px-8 py-12">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

        {/* Left — Team List */}
        <div className="space-y-4">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-[18px] flex items-center gap-2">
              <Users className="w-4 h-4 text-blue-400" />
              Your Teams
            </h2>
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={() => setShowCreateTeam(true)}
              className="p-2 border border-white/10 hover:bg-white/5 transition-colors"
            >
              <Plus className="w-4 h-4" />
            </motion.button>
          </div>

          {teams.length === 0 && !showCreateTeam && (
            <div className="border border-dashed border-white/10 p-8 text-center">
              <p className="text-[13px] text-white/40 mb-3">No teams yet</p>
              <button
                onClick={() => setShowCreateTeam(true)}
                className="text-[12px] text-blue-400 hover:text-blue-300 transition-colors uppercase tracking-[0.15em]"
              >
                Create your first team
              </button>
            </div>
          )}

          {/* Create Team Form */}
          <AnimatePresence>
            {showCreateTeam && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="border border-blue-500/30 bg-blue-500/5 p-5 space-y-3"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[12px] uppercase tracking-[0.15em] text-white/60">New Team</span>
                  <button onClick={() => setShowCreateTeam(false)}>
                    <X className="w-4 h-4 text-white/40 hover:text-white transition-colors" />
                  </button>
                </div>
                <input
                  autoFocus
                  type="text"
                  value={newTeamName}
                  onChange={e => setNewTeamName(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && handleCreateTeam()}
                  placeholder="Team name"
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 focus:border-white/30 focus:outline-none text-[14px] text-white placeholder:text-white/30"
                />
                <input
                  type="text"
                  value={newTeamDesc}
                  onChange={e => setNewTeamDesc(e.target.value)}
                  placeholder="Description (optional)"
                  className="w-full px-3 py-2 bg-white/5 border border-white/10 focus:border-white/30 focus:outline-none text-[13px] text-white placeholder:text-white/30"
                />
                <button
                  onClick={handleCreateTeam}
                  className="w-full py-2 bg-white text-black uppercase text-[11px] tracking-[0.15em] hover:bg-white/90 transition-colors"
                >
                  Create Team
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          {teams.map(team => (
            <motion.div
              key={team.id}
              whileHover={{ backgroundColor: "rgba(255,255,255,0.03)" }}
              onClick={() => setSelectedTeam(team)}
              className={`border p-5 cursor-pointer transition-all ${
                selectedTeam?.id === team.id
                  ? "border-blue-500/50 bg-blue-500/5"
                  : "border-white/10 bg-[#0f0f15]/60"
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <h3 className="text-[15px] mb-1 truncate">{team.name}</h3>
                  {team.description && (
                    <p className="text-[12px] text-white/50 truncate mb-2">{team.description}</p>
                  )}
                  <p className="text-[11px] text-white/40">
                    {team.members.length} {team.members.length === 1 ? "member" : "members"}
                  </p>
                </div>
                <ChevronRight className={`w-4 h-4 mt-1 shrink-0 transition-colors ${selectedTeam?.id === team.id ? "text-blue-400" : "text-white/20"}`} />
              </div>
            </motion.div>
          ))}
        </div>

        {/* Right — Team Detail */}
        <div className="lg:col-span-2">
          {!selectedTeam ? (
            <div className="border border-dashed border-white/10 h-48 flex items-center justify-center">
              <p className="text-[13px] text-white/30">Select a team to manage it</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Team Header */}
              <div className="border border-white/10 bg-[#0f0f15]/60 p-6">
                <div className="flex items-start justify-between mb-1">
                  <h2 className="text-[22px]">{selectedTeam.name}</h2>
                  <button
                    onClick={() => handleDeleteTeam(selectedTeam.id)}
                    className="p-2 hover:bg-red-500/10 transition-colors group"
                  >
                    <Trash2 className="w-4 h-4 text-white/20 group-hover:text-red-400 transition-colors" />
                  </button>
                </div>
                {selectedTeam.description && (
                  <p className="text-[13px] text-white/50">{selectedTeam.description}</p>
                )}
              </div>

              {/* Members */}
              <div className="border border-white/10 bg-[#0f0f15]/60 p-6">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="text-[16px]">Members <span className="text-white/40 text-[13px] ml-2">{selectedTeam.members.length}</span></h3>
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => setShowInvite(true)}
                    className="flex items-center gap-2 px-4 py-2 border border-white/10 hover:bg-white/5 transition-colors text-[12px] uppercase tracking-[0.15em]"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Invite
                  </motion.button>
                </div>

                {/* Invite Form */}
                <AnimatePresence>
                  {showInvite && (
                    <motion.div
                      initial={{ opacity: 0, y: -8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -8 }}
                      className="border border-white/10 bg-white/2 p-4 mb-5 space-y-3"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] uppercase tracking-[0.15em] text-white/60">Invite Member</span>
                        <button onClick={() => setShowInvite(false)}>
                          <X className="w-4 h-4 text-white/40 hover:text-white transition-colors" />
                        </button>
                      </div>
                      <div className="flex gap-3">
                        <div className="relative flex-1">
                          <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
                          <input
                            autoFocus
                            type="text"
                            value={inviteValue}
                            onChange={e => setInviteValue(e.target.value)}
                            onKeyDown={e => e.key === "Enter" && handleInvite()}
                            placeholder="Email or GitHub username"
                            className="w-full pl-10 pr-3 py-2.5 bg-white/5 border border-white/10 focus:border-white/30 focus:outline-none text-[13px] text-white placeholder:text-white/30"
                          />
                        </div>
                        <select
                          value={inviteRole}
                          onChange={e => setInviteRole(e.target.value as "admin" | "member")}
                          className="px-3 py-2.5 bg-white/5 border border-white/10 focus:border-white/30 focus:outline-none text-[13px] text-white"
                        >
                          <option value="member">Member</option>
                          <option value="admin">Admin</option>
                        </select>
                      </div>
                      <button
                        onClick={handleInvite}
                        className="w-full py-2 bg-white text-black uppercase text-[11px] tracking-[0.15em] hover:bg-white/90 transition-colors"
                      >
                        Send Invite
                      </button>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Member List */}
                <div className="space-y-2">
                  {selectedTeam.members.map(member => {
                    return (
                      <motion.div
                        key={member.id}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        className="flex items-center justify-between py-3 border-b border-white/5 last:border-0 group"
                      >
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-[12px] font-medium shrink-0">
                            {member.name.slice(0, 2).toUpperCase()}
                          </div>
                          <div>
                            <p className="text-[14px]">{member.name}</p>
                            <div className="flex items-center gap-3 mt-0.5">
                              {member.email && !member.email.endsWith("@github") && (
                                <span className="text-[11px] text-white/40 flex items-center gap-1">
                                  <Mail className="w-3 h-3" />{member.email}
                                </span>
                              )}
                              {member.github && (
                                <span className="text-[11px] text-white/40 flex items-center gap-1">
                                  <FaGithub className="w-3 h-3" />{member.github}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>

                        <div className="flex items-center gap-3">
                          {member.role === "owner" ? (
                            <span className={`flex items-center gap-1 text-[11px] uppercase tracking-widest ${ROLE_COLOR.owner}`}>
                              <Crown className="w-3 h-3" />Owner
                            </span>
                          ) : (
                            <select
                              value={member.role}
                              onChange={e => handleChangeRole(member.id, e.target.value as Member["role"])}
                              className={`bg-transparent border-none focus:outline-none text-[11px] uppercase tracking-widest cursor-pointer ${ROLE_COLOR[member.role]}`}
                            >
                              <option value="admin">Admin</option>
                              <option value="member">Member</option>
                            </select>
                          )}
                          {member.role !== "owner" && (
                            <button
                              onClick={() => handleRemoveMember(member.id)}
                              className="opacity-0 group-hover:opacity-100 transition-opacity p-1 hover:bg-red-500/10"
                            >
                              <X className="w-3.5 h-3.5 text-white/30 hover:text-red-400 transition-colors" />
                            </button>
                          )}
                        </div>
                      </motion.div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
