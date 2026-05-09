"use client";

import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { GitBranch, Pencil, X } from "lucide-react";

interface Repository {
  id: string;
  name: string;
  url: string;
  lastUpdated?: string | null;
  componentsCount: number;
}

interface EditRepositoryModalProps {
  repository: Repository;
  onClose: () => void;
  onSave: (name: string) => Promise<void> | void;
}

export function EditRepositoryModal({ repository, onClose, onSave }: EditRepositoryModalProps) {
  const [name, setName] = useState(repository.name);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setName(repository.name);
  }, [repository.name]);

  const handleSubmit = async () => {
    const trimmed = name.trim();
    if (!trimmed || trimmed === repository.name) {
      onClose();
      return;
    }

    setSaving(true);
    try {
      await onSave(trimmed);
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        onClick={onClose}
        className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm"
      />

      <div className="fixed inset-0 z-50 flex items-center justify-center p-8">
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ duration: 0.2 }}
          className="flex w-full max-w-2xl flex-col border border-white/10 bg-[#0f0f15] text-white"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/5">
                <Pencil className="h-4 w-4 text-blue-400" />
              </div>
              <div>
                <h2 className="text-[18px]">Edit Repository Name</h2>
                <p className="text-[12px] text-white/45">This changes the display name in DynoDocs only.</p>
              </div>
            </div>

            <button onClick={onClose} className="rounded p-2 transition-colors hover:bg-white/10">
              <X className="h-5 w-5 text-white/60" />
            </button>
          </div>

          <div className="space-y-6 px-6 py-6">
            <div className="space-y-2">
              <label className="block text-[11px] uppercase tracking-[0.15em] text-white/60">
                Repository Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    void handleSubmit();
                  }
                }}
                className="w-full border border-white/10 bg-white/5 px-4 py-3 text-[14px] text-white placeholder:text-white/30 transition-colors focus:border-white/30 focus:outline-none"
                placeholder="Repository name"
                autoFocus
              />
            </div>

            <div className="border border-white/10 bg-white/5 p-4">
              <div className="mb-2 flex items-center gap-2 text-[12px] text-white/60">
                <GitBranch className="h-4 w-4 text-blue-400" />
                Source Repository
              </div>
              <p className="break-all text-[13px] text-white/75">{repository.url}</p>
            </div>
          </div>

          <div className="flex items-center justify-between border-t border-white/10 px-6 py-4">
            <p className="text-[12px] text-white/40">The linked GitHub repository will not be renamed.</p>
            <div className="flex gap-3">
              <button
                onClick={onClose}
                className="border border-white/20 px-5 py-2.5 text-[11px] uppercase tracking-[0.15em] transition-colors hover:bg-white/5"
              >
                Cancel
              </button>
              <motion.button
                whileHover={saving ? {} : { scale: 1.02 }}
                whileTap={saving ? {} : { scale: 0.98 }}
                onClick={() => void handleSubmit()}
                disabled={saving}
                className="bg-white px-5 py-2.5 text-[11px] uppercase tracking-[0.15em] text-black transition-colors hover:bg-white/90 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {saving ? "Saving..." : "Save Changes"}
              </motion.button>
            </div>
          </div>
        </motion.div>
      </div>
    </>
  );
}
