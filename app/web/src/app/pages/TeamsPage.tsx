"use client";

import { motion, AnimatePresence } from "motion/react";
import { useState, useEffect } from "react";
import { Users, Plus, Trash2, X, ChevronRight, ChevronDown, Search } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/components/AuthProvider";
import { buildApiUrl } from "@/lib/api";

interface ApiProfile {
  id: string;
  email: string;
  full_name: string;
  created_at: string;
}

interface ApiMember {
  team_id: string;
  profile_id: string;
  role: string;
  created_at: string;
  email: string | null;
  full_name: string | null;
}

interface ApiTeam {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

interface ApiTeamWithMembers extends ApiTeam {
  members: ApiMember[];
}

const ROLE_COLOR: Record<string, string> = {
  admin: "text-blue-400",
  member: "text-white/50",
};

interface TeamsPageProps {
  onBack: () => void;
}

export function TeamsPage({ onBack: _onBack }: TeamsPageProps) {
  void _onBack;
  const { session, user } = useAuth();
  const accessToken = (session as { access_token?: string } | null)?.access_token ?? "";
  const currentUserId = user?.id ?? "";

  const [teams, setTeams] = useState<ApiTeam[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<ApiTeamWithMembers | null>(null);
  const [teamsLoading, setTeamsLoading] = useState(false);
  const [teamLoading, setTeamLoading] = useState(false);
  const [showCreateTeam, setShowCreateTeam] = useState(false);
  const [showInvite, setShowInvite] = useState(false);
  const [openRoleDropdown, setOpenRoleDropdown] = useState<string | null>(null);
  const [openInviteRoleDropdown, setOpenInviteRoleDropdown] = useState(false);

  const [newTeamName, setNewTeamName] = useState("");

  // Invite form state
  const [searchQuery, setSearchQuery] = useState("");
  const [inviteRole, setInviteRole] = useState<"admin" | "member">("member");
  const [inviteSearchResults, setInviteSearchResults] = useState<ApiProfile[]>([]);
  const [inviteSearching, setInviteSearching] = useState(false);
  const [inviteSelected, setInviteSelected] = useState<ApiProfile | null>(null);

  const resetInviteForm = () => {
    setSearchQuery("");
    setInviteRole("member");
    setInviteSearchResults([]);
    setInviteSelected(null);
  };

  const loadTeamDetail = (team: ApiTeam) => {
    setTeamLoading(true);
    fetch(buildApiUrl(`/teams/${team.id}`), {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((data: ApiTeamWithMembers) => setSelectedTeam(data))
      .catch(() => toast.error("Failed to load team details"))
      .finally(() => setTeamLoading(false));
  };

  useEffect(() => {
    if (!accessToken) return;
    setTeamsLoading(true);
    fetch(buildApiUrl("/teams"), {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((data: ApiTeam[]) => {
        setTeams(data);
        if (data.length > 0) loadTeamDetail(data[0]);
      })
      .catch((err: Error) => {
        if (err.message === "401") toast.error("Session expired — please sign in again");
        else toast.error("Failed to load teams");
      })
      .finally(() => setTeamsLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accessToken]);

  const handleCreateTeam = () => {
    if (!newTeamName.trim()) {
      toast.error("Team name is required");
      return;
    }
    fetch(buildApiUrl("/teams"), {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" },
      body: JSON.stringify({ name: newTeamName.trim() }),
    })
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((team: ApiTeam) => {
        setTeams((prev) => [team, ...prev]);
        loadTeamDetail(team);
        setNewTeamName("");
        setShowCreateTeam(false);
        toast.success(`Team "${team.name}" created`);
      })
      .catch(() => toast.error("Failed to create team"));
  };

  const handleSearchProfiles = () => {
    if (searchQuery.trim().length < 3) {
      toast.error("Enter at least 3 characters to search");
      return;
    }
    setInviteSearching(true);
    setInviteSelected(null);
    fetch(buildApiUrl(`/profiles/search?q=${encodeURIComponent(searchQuery.trim())}`), {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((data: ApiProfile[]) => {
        setInviteSearchResults(data);
        if (data.length === 0) toast.error("No users found with that email");
      })
      .catch(() => toast.error("Search failed"))
      .finally(() => setInviteSearching(false));
  };

  const handleAddMember = () => {
    if (!inviteSelected) {
      toast.error("Select a user from the search results first");
      return;
    }
    if (!selectedTeam) return;
    fetch(buildApiUrl(`/teams/${selectedTeam.id}/members`), {
      method: "POST",
      headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id: inviteSelected.id, role: inviteRole }),
    })
      .then((r) => {
        if (r.status === 409) throw new Error("already_member");
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((member: ApiMember) => {
        const enriched: ApiMember = { ...member, email: inviteSelected.email, full_name: inviteSelected.full_name };
        setSelectedTeam((prev) => prev ? { ...prev, members: [...prev.members, enriched] } : prev);
        resetInviteForm();
        setShowInvite(false);
        toast.success(`${inviteSelected.full_name} added to the team`);
      })
      .catch((err: Error) => {
        if (err.message === "already_member") toast.error("That user is already a member");
        else toast.error("Failed to add member");
      });
  };

  const handleChangeRole = (profileId: string, newRole: "admin" | "member") => {
    if (!selectedTeam) return;
    fetch(buildApiUrl(`/teams/${selectedTeam.id}/members/${profileId}`), {
      method: "PATCH",
      headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" },
      body: JSON.stringify({ role: newRole }),
    })
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((updated: ApiMember) => {
        setSelectedTeam((prev) => {
          if (!prev) return prev;
          const members = prev.members.map((m) => {
            if (m.profile_id === profileId) return { ...m, role: updated.role };
            if (updated.role === "admin" && m.role === "admin") return { ...m, role: "member" };
            return m;
          });
          return { ...prev, members };
        });
      })
      .catch(() => toast.error("Failed to update role"));
  };

  const handleRemoveMember = (profileId: string) => {
    if (!selectedTeam) return;
    fetch(buildApiUrl(`/teams/${selectedTeam.id}/members/${profileId}`), {
      method: "DELETE",
      headers: { Authorization: `Bearer ${accessToken}` },
    })
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        setSelectedTeam((prev) =>
          prev ? { ...prev, members: prev.members.filter((m) => m.profile_id !== profileId) } : prev
        );
        toast.success("Member removed");
      })
      .catch(() => toast.error("Failed to remove member"));
  };

  const handleDeleteTeam = (teamId: string) => {
    const team = teams.find((t) => t.id === teamId);
    fetch(buildApiUrl(`/teams/${teamId}`), {
      method: "DELETE",
      headers: { Authorization: `Bearer ${accessToken}` },
    })
      .then((r) => {
        if (r.status === 403) throw new Error("403");
        if (!r.ok) throw new Error(`${r.status}`);
        const remaining = teams.filter((t) => t.id !== teamId);
        setTeams(remaining);
        if (remaining.length > 0) loadTeamDetail(remaining[0]);
        else setSelectedTeam(null);
        toast.success(`Team "${team?.name}" deleted`);
      })
      .catch((err: Error) => {
        if (err.message === "403") toast.error("You must be a member to delete this team");
        else toast.error("Failed to delete team");
      });
  };

  const isCurrentUserAdmin = selectedTeam?.members.some(
    (m) => m.profile_id === currentUserId && m.role === "admin"
  ) ?? false;

  const memberDisplayName = (member: ApiMember) =>
    member.profile_id === currentUserId ? (`${member.full_name} (You)` || `${member.profile_id.slice(0, 8)}… (You)`) : (member.full_name || `${member.profile_id.slice(0, 8)}…`);

  const memberInitials = (member: ApiMember) => {
    if (member.full_name) return member.full_name.slice(0, 2).toUpperCase();
    return member.profile_id.slice(0, 2).toUpperCase();
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

          {!teamsLoading && teams.length === 0 && !showCreateTeam && (
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

          {teamsLoading && (
            <p className="text-[13px] text-white/30 px-1">Loading teams…</p>
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
              onClick={() => loadTeamDetail(team)}
              className={`border p-5 cursor-pointer transition-all ${
                selectedTeam?.id === team.id
                  ? "border-blue-500/50 bg-blue-500/5"
                  : "border-white/10 bg-[#0f0f15]/60"
              }`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <h3 className="text-[15px] mb-1 truncate">{team.name}</h3>
                  <p className="text-[11px] text-white/40">
                    {new Date(team.created_at).toLocaleDateString()}
                  </p>
                </div>
                <ChevronRight className={`w-4 h-4 mt-1 shrink-0 transition-colors ${selectedTeam?.id === team.id ? "text-blue-400" : "text-white/20"}`} />
              </div>
            </motion.div>
          ))}
        </div>

        {/* Right — Team Detail */}
        <div className="lg:col-span-2">
          {teamLoading ? (
            <div className="border border-white/10 h-48 flex items-center justify-center">
              <p className="text-[13px] text-white/30">Loading…</p>
            </div>
          ) : !selectedTeam ? (
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
              </div>

              {/* Members */}
              <div className="border border-white/10 bg-[#0f0f15]/60 p-6">
                <div className="flex items-center justify-between mb-6">
                  <h3 className="text-[16px]">Members <span className="text-white/40 text-[13px] ml-2">{selectedTeam.members.length}</span></h3>
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={() => { resetInviteForm(); setShowInvite(true); }}
                    className="flex items-center gap-2 px-4 py-2 border border-white/10 hover:bg-white/5 transition-colors text-[12px] uppercase tracking-[0.15em]"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Add Member
                  </motion.button>
                </div>

                {/* Add Member Form */}
                <AnimatePresence>
                  {showInvite && (
                    <motion.div
                      initial={{ opacity: 0, y: -8 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -8 }}
                      className="border border-white/10 bg-white/2 p-4 mb-5 space-y-3"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] uppercase tracking-[0.15em] text-white/60">Add Member</span>
                        <button onClick={() => setShowInvite(false)}>
                          <X className="w-4 h-4 text-white/40 hover:text-white transition-colors" />
                        </button>
                      </div>

                      {/* User search */}
                      <div className="flex gap-2">
                        <input
                          autoFocus
                          type="text"
                          value={searchQuery}
                          onChange={e => { setSearchQuery(e.target.value); setInviteSearchResults([]); setInviteSelected(null); }}
                          onKeyDown={e => e.key === "Enter" && handleSearchProfiles()}
                          placeholder="Search by name or email"
                          className="flex-1 px-3 py-2.5 bg-white/5 border border-white/10 focus:border-white/30 focus:outline-none text-[13px] text-white placeholder:text-white/30"
                        />
                        <button
                          onClick={handleSearchProfiles}
                          disabled={inviteSearching}
                          className="px-3 py-2.5 border border-white/10 hover:bg-white/5 transition-colors disabled:opacity-40"
                        >
                          <Search className="w-4 h-4 text-white/60" />
                        </button>
                      </div>

                      {/* Search results */}
                      {inviteSearchResults.length > 0 && (
                        <div className="border border-white/10 divide-y divide-white/5">
                          {inviteSearchResults.map((profile) => (
                            <button
                              key={profile.id}
                              onClick={() => { setInviteSelected(profile); setInviteSearchResults([]); }}
                              className={`w-full text-left px-3 py-2.5 hover:bg-white/5 transition-colors ${inviteSelected?.id === profile.id ? "bg-blue-500/10" : ""}`}
                            >
                              <p className="text-[13px] text-white">{profile.full_name}</p>
                              <p className="text-[11px] text-white/40">{profile.email}</p>
                            </button>
                          ))}
                        </div>
                      )}

                      {/* Selected user confirmation */}
                      {inviteSelected && (
                        <div className="flex items-center justify-between px-3 py-2 bg-blue-500/10 border border-blue-500/20">
                          <div>
                            <p className="text-[13px] text-white">{inviteSelected.full_name}</p>
                            <p className="text-[11px] text-white/40">{inviteSelected.email}</p>
                          </div>
                          <button onClick={() => setInviteSelected(null)}>
                            <X className="w-3.5 h-3.5 text-white/30 hover:text-white transition-colors" />
                          </button>
                        </div>
                      )}

                      <div className="flex gap-3">
                        <div className="relative">
                          {openInviteRoleDropdown && (
                            <div className="fixed inset-0 z-10" onClick={() => setOpenInviteRoleDropdown(false)} />
                          )}
                          <button
                            onClick={() => setOpenInviteRoleDropdown(prev => !prev)}
                            className="flex items-center gap-1 px-3 py-2 bg-white/5 border border-white/10 text-[13px] text-white min-w-[7rem]"
                          >
                            <span className="flex-1 text-left capitalize">{inviteRole}</span>
                            <ChevronDown className="w-3.5 h-3.5 opacity-50 shrink-0" />
                          </button>
                          {openInviteRoleDropdown && (
                            <div className="absolute left-0 top-full mt-1 z-20 bg-[#0f0f15] border border-white/10 min-w-[7rem]">
                              {(["member", "admin"] as const).map(role => (
                                <button
                                  key={role}
                                  onClick={() => { setInviteRole(role); setOpenInviteRoleDropdown(false); }}
                                  className={`w-full text-left px-3 py-2 text-[13px] capitalize hover:bg-white/5 transition-colors ${inviteRole === role ? "bg-white/5 text-white" : "text-white/60"}`}
                                >
                                  {role}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                        <button
                          onClick={handleAddMember}
                          disabled={!inviteSelected}
                          className="flex-1 py-2 bg-white text-black uppercase text-[11px] tracking-[0.15em] hover:bg-white/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                          Add Member
                        </button>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Member List */}
                <div className="space-y-2">
                  {selectedTeam.members.map(member => (
                    <motion.div
                      key={member.profile_id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="flex items-center justify-between py-3 border-b border-white/5 last:border-0 group"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-white/10 flex items-center justify-center text-[12px] font-medium shrink-0">
                          {memberInitials(member)}
                        </div>
                        <div>
                          <p className="text-[14px]">{memberDisplayName(member)}</p>
                          <p className="text-[11px] text-white/30 mt-0.5">{member.email ?? member.profile_id}</p>
                        </div>
                      </div>

                      <div className="flex items-center gap-3">
                        {member.profile_id === currentUserId || !isCurrentUserAdmin ? (
                          <span className={`text-[11px] uppercase tracking-widest ${ROLE_COLOR[member.role] ?? "text-white/50"}`}>
                            {member.role}
                          </span>
                        ) : (
                          <div className="relative">
                            {openRoleDropdown === member.profile_id && (
                              <div className="fixed inset-0 z-10" onClick={() => setOpenRoleDropdown(null)} />
                            )}
                            <button
                              onClick={() => setOpenRoleDropdown(prev => prev === member.profile_id ? null : member.profile_id)}
                              className={`flex items-center gap-1 text-[11px] uppercase tracking-widest cursor-pointer ${ROLE_COLOR[member.role] ?? "text-white/50"}`}
                            >
                              {member.role}
                              <ChevronDown className="w-3 h-3 opacity-50" />
                            </button>
                            {openRoleDropdown === member.profile_id && (
                              <div className="absolute right-0 top-full mt-1 z-20 bg-[#0f0f15] border border-white/10 min-w-[7rem]">
                                {(["admin", "member"] as const).map(role => (
                                  <button
                                    key={role}
                                    onClick={() => { handleChangeRole(member.profile_id, role); setOpenRoleDropdown(null); }}
                                    className={`w-full text-left px-3 py-2 text-[11px] uppercase tracking-widest hover:bg-white/5 transition-colors ${ROLE_COLOR[role] ?? "text-white/50"} ${member.role === role ? "bg-white/5" : ""}`}
                                  >
                                    {role}
                                  </button>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                        {isCurrentUserAdmin && member.profile_id !== currentUserId && (
                          <button
                            onClick={() => handleRemoveMember(member.profile_id)}
                            className="p-1 hover:bg-red-500/10 transition-opacity opacity-0 group-hover:opacity-100"
                          >
                            <X className="w-3.5 h-3.5 text-white/30 hover:text-red-400 transition-colors" />
                          </button>
                        )}
                      </div>
                    </motion.div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
