"use client";

import { useEffect, useState } from "react";
import { fetchAuditLog } from "@/lib/api";

interface AuditEvent {
  id?: string;
  timestamp?: string;
  agent_name?: string;
  event_type?: string;
  detail?: string;
}

export function AuditLog() {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [count, setCount] = useState(0);

  useEffect(() => {
    async function load() {
      try {
        const data = await fetchAuditLog();
        setCount(data.count);
        setEvents(data.events as AuditEvent[]);
      } catch {
        // silent — audit is supplementary
      }
    }
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-[var(--border)] flex items-center justify-between">
        <span className="text-sm font-semibold text-[var(--text)]">Audit Log</span>
        <span className="text-xs text-[var(--muted)] font-mono">{count} events</span>
      </div>
      <div className="flex-1 overflow-y-auto scrollbar-thin p-3 space-y-2">
        {events.length === 0 ? (
          <p className="text-[var(--muted)] text-xs text-center py-6">No events yet</p>
        ) : (
          [...events].reverse().map((ev, i) => (
            <div
              key={ev.id ?? i}
              className="rounded p-2 border border-[var(--border)] bg-[var(--surface)] text-xs"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-mono text-[var(--accent)]">{ev.agent_name ?? "—"}</span>
                <span className="text-[var(--muted)]">{ev.event_type ?? ""}</span>
              </div>
              {ev.detail && (
                <p className="text-[var(--muted)] truncate">{ev.detail}</p>
              )}
              {ev.timestamp && (
                <p className="text-[var(--muted)] opacity-60 mt-1">
                  {new Date(ev.timestamp).toLocaleTimeString()}
                </p>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
