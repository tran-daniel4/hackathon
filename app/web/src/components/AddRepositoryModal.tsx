"use client";

import { motion, AnimatePresence } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { useSession } from "next-auth/react";
import { Check, X, FolderOpen, Star } from "lucide-react";
import { FaGithub } from "react-icons/fa";
import { toast } from "sonner";

interface Repository {
  id: string;
  name: string;
  url: string;
  lastUpdated: string;
  componentsCount: number;
}

interface GitHubRepo {
  id: number;
  name: string;
  full_name: string;
  html_url: string;
  pushed_at: string;
  private: boolean;
  description: string | null;
  language: string | null;
  stargazers_count: number;
  owner: { type: "User" | "Organization" };
}

interface AddRepositoryModalProps {
  onClose: () => void;
  onAdd: (repo: Repository) => void;
}

export function AddRepositoryModal({ onClose, onAdd }: AddRepositoryModalProps) {
  const { data: session } = useSession();
  const githubToken = (session as typeof session & { githubAccessToken?: string })?.githubAccessToken;
  const hasGithub = !!githubToken;

  const [githubRepos, setGithubRepos] = useState<GitHubRepo[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [search, setSearch] = useState("");
  const folderInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!hasGithub) return;
    setIsLoading(true);
    fetch("https://api.github.com/user/repos?sort=pushed&per_page=100&affiliation=owner", {
      headers: { Authorization: `Bearer ${githubToken}`, Accept: "application/vnd.github+json" },
    })
      .then((r) => {
        if (!r.ok) throw new Error("GitHub API error");
        return r.json();
      })
      .then(setGithubRepos)
      .catch(() => toast.error("Failed to fetch GitHub repositories"))
      .finally(() => setIsLoading(false));
  }, [hasGithub, githubToken]);

  const handleToggle = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleConfirm = () => {
    filteredRepos
      .filter((r) => selectedIds.has(r.id))
      .forEach((repo) => {
        onAdd({
          id: String(repo.id),
          name: repo.name,
          url: repo.full_name,
          lastUpdated: new Date(repo.pushed_at).toLocaleDateString(),
          componentsCount: 0,
        });
      });
    onClose();
  };

  const handleFolderSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    const folderName = files[0].webkitRelativePath.split("/")[0];
    onAdd({
      id: `local-${Date.now()}`,
      name: folderName,
      url: folderName,
      lastUpdated: "just now",
      componentsCount: 0,
    });
    onClose();
  };

  const filteredRepos = githubRepos.filter(
    (r) =>
      r.owner.type === "User" &&
r.full_name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <>
      {/* Backdrop */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        onClick={onClose}
        className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50"
      />

      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-8">
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ duration: 0.2 }}
          className="bg-[#0f0f15] border border-white/10 max-w-4xl w-full max-h-[80vh] flex flex-col text-white"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="relative border-b border-white/10 px-6 py-4 flex items-center justify-between shrink-0">
            <button
              onClick={() => folderInputRef.current?.click()}
              className="flex items-center gap-2 px-4 py-2 border border-white/20 bg-white/5 hover:bg-white/10 transition-colors text-[11px] uppercase tracking-[0.15em] text-white/70 hover:text-white"
            >
              <FolderOpen className="w-4 h-4" />
              Upload Local Project
            </button>
            <input
              ref={folderInputRef}
              type="file"
              className="hidden"
              onChange={handleFolderSelect}
              {...{ webkitdirectory: "" }}
            />

            <h2 className="absolute left-1/2 -translate-x-1/2 text-[18px] pointer-events-none">
              Add Repositories
            </h2>

            <button onClick={onClose} className="p-2 hover:bg-white/10 rounded transition-colors">
              <X className="w-5 h-5 text-white/60" />
            </button>
          </div>

          {/* Search */}
          {hasGithub && (
            <div className="px-6 py-3 border-b border-white/10 shrink-0">
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search repositories..."
                className="w-full bg-white/5 border border-white/10 px-3 py-2 text-[13px] text-white placeholder:text-white/30 focus:outline-none focus:border-white/30 transition-colors"
              />
            </div>
          )}

          {/* Content */}
          <div className="flex-1 overflow-y-auto p-6">
            {hasGithub ? (
              <>
                <div className="flex items-center gap-2 mb-2">
                  <FaGithub className="w-5 h-5 text-white/60" />
                  <h3 className="text-[14px] text-white/80">Your GitHub Repositories</h3>
                </div>
                <p className="text-[12px] text-white/50 mb-5">
                  Select repositories to analyze and generate architecture diagrams
                </p>

                {isLoading ? (
                  <div className="text-center py-12 text-[13px] text-white/40">
                    Loading repositories…
                  </div>
                ) : filteredRepos.length === 0 ? (
                  <div className="text-center py-12 text-[13px] text-white/40">
                    {search ? "No repositories match your search" : "No repositories found"}
                  </div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {filteredRepos.map((repo) => {
                      const isSelected = selectedIds.has(repo.id);
                      return (
                        <motion.button
                          key={repo.id}
                          whileHover={{ scale: 1.02 }}
                          whileTap={{ scale: 0.98 }}
                          onClick={() => handleToggle(repo.id)}
                          className={`relative p-5 border text-left transition-all ${
                            isSelected
                              ? "border-blue-500 bg-blue-500/10"
                              : "border-white/10 bg-white/5 hover:bg-white/10"
                          }`}
                        >
                          <div className="flex items-start justify-between mb-3">
                            <div className="flex-1 min-w-0">
                              <h4 className="text-[15px] mb-0.5 truncate">{repo.name}</h4>
                              <p className="text-[11px] text-white/40 truncate">{repo.full_name}</p>
                            </div>

                            <AnimatePresence>
                              {isSelected && (
                                <motion.div
                                  initial={{ scale: 0 }}
                                  animate={{ scale: 1 }}
                                  exit={{ scale: 0 }}
                                  className="w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center shrink-0 ml-3"
                                >
                                  <Check className="w-3.5 h-3.5 text-white" />
                                </motion.div>
                              )}
                            </AnimatePresence>
                          </div>

                          <p className="text-[12px] text-white/60 mb-3 line-clamp-2 min-h-10">
                            {repo.description || <span className="text-white/30 italic">No description</span>}
                          </p>

                          <div className="flex items-center gap-4 text-[11px] text-white/40">
                            {repo.language && <span>{repo.language}</span>}
                            {repo.private && (
                              <span className="uppercase tracking-[0.08em]">Private</span>
                            )}
                            <span className="flex items-center gap-1 ml-auto">
                              <Star className="w-3 h-3" />
                              {repo.stargazers_count}
                            </span>
                          </div>
                        </motion.button>
                      );
                    })}
                  </div>
                )}
              </>
            ) : (
              <div className="flex flex-col items-center justify-center h-full py-12 text-center">
                <FolderOpen className="w-10 h-10 text-white/20 mb-4" />
                <p className="text-[14px] text-white/60 mb-2">No GitHub account connected</p>
                <p className="text-[12px] text-white/40">
                  Use the button above to add a local project path or URL
                </p>
              </div>
            )}
          </div>

          {/* Footer */}
          <AnimatePresence>
            {selectedIds.size > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 10 }}
                className="border-t border-white/10 px-6 py-4 flex items-center justify-between shrink-0"
              >
                <p className="text-[13px] text-white/70">
                  {selectedIds.size} {selectedIds.size === 1 ? "repository" : "repositories"} selected
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={onClose}
                    className="px-5 py-2.5 border border-white/20 hover:bg-white/5 transition-colors text-[11px] uppercase tracking-[0.15em]"
                  >
                    Cancel
                  </button>
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    onClick={handleConfirm}
                    className="px-5 py-2.5 bg-white text-black hover:bg-white/90 transition-colors text-[11px] uppercase tracking-[0.15em]"
                  >
                    Add Selected
                  </motion.button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </div>
    </>
  );
}
