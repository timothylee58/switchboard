import { AuditLog } from "@/components/AuditLog";
import { ChatWindow } from "@/components/ChatWindow";

export default function Home() {
  return (
    <div className="flex h-screen">
      {/* Sidebar — branding + audit log */}
      <aside className="w-72 border-r border-[var(--border)] bg-[var(--surface)] flex flex-col">
        <div className="px-4 py-4 border-b border-[var(--border)]">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-[var(--accent)] flex items-center justify-center text-white text-xs font-bold">
              S
            </div>
            <span className="font-semibold text-sm">Switchboard</span>
            <span className="text-[var(--muted)] text-xs ml-auto">v0.1</span>
          </div>
          <p className="text-[var(--muted)] text-xs mt-2 leading-relaxed">
            Domain-agnostic agentic orchestration with governance baked in.
          </p>
        </div>

        {/* Agent legend */}
        <div className="px-4 py-3 border-b border-[var(--border)]">
          <p className="text-[var(--muted)] text-xs uppercase tracking-wider mb-2">Active agents</p>
          <div className="space-y-1 text-xs font-mono">
            {[
              { name: "triage_agent", risk: "LOW" },
              { name: "ci_agent", risk: "LOW" },
              { name: "deploy_agent", risk: "HIGH ⛔" },
              { name: "code_agent", risk: "HIGH ⛔" },
            ].map((a) => (
              <div key={a.name} className="flex justify-between text-[var(--muted)]">
                <span>{a.name}</span>
                <span className={a.risk.includes("HIGH") ? "text-red-400" : "text-green-500"}>
                  {a.risk}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Audit log */}
        <div className="flex-1 overflow-hidden">
          <AuditLog />
        </div>
      </aside>

      {/* Main chat area */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <ChatWindow />
      </main>
    </div>
  );
}
