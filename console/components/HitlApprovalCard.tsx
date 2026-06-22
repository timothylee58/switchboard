"use client";

import { useState } from "react";
import { resolveApproval } from "@/lib/api";

interface Props {
  threadId: string;
  agentName: string;
  onResolved: (approved: boolean) => void;
}

export function HitlApprovalCard({ threadId, agentName, onResolved }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handle(approved: boolean) {
    setLoading(true);
    setError(null);
    try {
      await resolveApproval(threadId, approved, "console_user");
      onResolved(approved);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Resolution failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="my-3 rounded-lg border border-amber-700 bg-amber-950/40 p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-amber-400 text-sm font-semibold">⏸ Approval Required</span>
        <span className="text-amber-600 text-xs font-mono">{agentName}</span>
      </div>
      <p className="text-amber-200 text-sm mb-4">
        This action requires human approval before it executes. Review and decide:
      </p>
      {error && <p className="text-red-400 text-xs mb-3">{error}</p>}
      <div className="flex gap-3">
        <button
          onClick={() => handle(true)}
          disabled={loading}
          className="px-4 py-1.5 rounded bg-green-700 hover:bg-green-600 text-white text-sm font-medium disabled:opacity-50 transition-colors"
        >
          {loading ? "…" : "Approve"}
        </button>
        <button
          onClick={() => handle(false)}
          disabled={loading}
          className="px-4 py-1.5 rounded bg-red-800 hover:bg-red-700 text-white text-sm font-medium disabled:opacity-50 transition-colors"
        >
          {loading ? "…" : "Reject"}
        </button>
      </div>
    </div>
  );
}
