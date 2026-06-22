"use client";

import { useCallback, useRef, useState } from "react";
import { streamChat } from "@/lib/api";
import { HitlApprovalCard } from "./HitlApprovalCard";
import { RoutingBadge } from "./RoutingBadge";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  agentName?: string;
}

interface PendingApproval {
  threadId: string;
  agentName: string;
}

let threadSeq = 0;

export function ChatWindow() {
  const [threadId, setThreadId] = useState(() => `thread-${Date.now()}`);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [pendingApproval, setPendingApproval] = useState<PendingApproval | null>(null);
  const [lastAgent, setLastAgent] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  function newThread() {
    abortRef.current?.abort();
    threadSeq++;
    setThreadId(`thread-${Date.now()}-${threadSeq}`);
    setMessages([]);
    setPendingApproval(null);
    setLastAgent(null);
  }

  async function send() {
    const text = input.trim();
    if (!text || streaming) return;

    setInput("");
    setStreaming(true);
    setPendingApproval(null);

    const userMsg: Message = { id: `u-${Date.now()}`, role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);

    abortRef.current = new AbortController();

    // Accumulate assistant reply chunks
    let assistantContent = "";
    let detectedAgent: string | null = null;
    const assistantId = `a-${Date.now()}`;

    // Insert a placeholder assistant message
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: "assistant", content: "…", agentName: undefined },
    ]);

    try {
      await streamChat(
        threadId,
        text,
        {},
        (line) => {
          if (line === "[DONE]") return;

          try {
            const parsed = JSON.parse(line);

            // HITL pause event
            if (parsed.type === "hitl_paused") {
              setPendingApproval({ threadId, agentName: detectedAgent ?? "agent" });
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: "⏸ Paused — awaiting approval", agentName: detectedAgent ?? undefined }
                    : m,
                ),
              );
              return;
            }

            // Normal stream event: { nodeName: { current_agent, last_message } }
            for (const [nodeName, nodeState] of Object.entries(
              parsed as Record<string, { current_agent: string | null; last_message: string | null }>,
            )) {
              if (nodeName === "supervisor") continue;
              const msg = nodeState.last_message;
              const agent = nodeState.current_agent ?? nodeName;
              if (msg) {
                assistantContent = msg;
                detectedAgent = agent;
                setLastAgent(agent);
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? { ...m, content: assistantContent, agentName: agent }
                      : m,
                  ),
                );
                scrollToBottom();
              }
            }
          } catch {
            // non-JSON line — skip
          }
        },
        abortRef.current.signal,
      );
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: "Error connecting to backend." } : m,
          ),
        );
      }
    } finally {
      setStreaming(false);
      scrollToBottom();
    }
  }

  function handleApprovalResolved(approved: boolean) {
    setPendingApproval(null);
    const note = approved ? "✓ Action approved and executed." : "✗ Action rejected — no changes made.";
    setMessages((prev) => [
      ...prev,
      { id: `sys-${Date.now()}`, role: "assistant", content: note },
    ]);
    scrollToBottom();
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[var(--border)] flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold">Chat</span>
          <span className="text-xs font-mono text-[var(--muted)]">{threadId}</span>
          {lastAgent && <RoutingBadge agentName={lastAgent} />}
        </div>
        <button
          onClick={newThread}
          className="text-xs text-[var(--muted)] hover:text-[var(--text)] transition-colors px-2 py-1 rounded border border-[var(--border)] hover:border-[var(--accent)]"
        >
          New thread
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto scrollbar-thin p-4 space-y-3">
        {messages.length === 0 && (
          <p className="text-center text-[var(--muted)] text-sm mt-12">
            Send a message to start a thread.
          </p>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col gap-1 ${msg.role === "user" ? "items-end" : "items-start"}`}
          >
            {msg.agentName && (
              <div className="mb-0.5">
                <RoutingBadge agentName={msg.agentName} />
              </div>
            )}
            <div
              className={`max-w-[80%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-[var(--accent)] text-white"
                  : "bg-[var(--surface)] text-[var(--text)] border border-[var(--border)]"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}

        {/* HITL approval card */}
        {pendingApproval && (
          <HitlApprovalCard
            threadId={pendingApproval.threadId}
            agentName={pendingApproval.agentName}
            onResolved={handleApprovalResolved}
          />
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-4 py-3 border-t border-[var(--border)]">
        <div className="flex gap-2">
          <input
            className="flex-1 bg-[var(--surface)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--text)] placeholder:text-[var(--muted)] focus:outline-none focus:border-[var(--accent)] transition-colors"
            placeholder={streaming ? "Streaming…" : "Send a message…"}
            value={input}
            disabled={streaming || !!pendingApproval}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
          />
          <button
            onClick={send}
            disabled={streaming || !input.trim() || !!pendingApproval}
            className="px-4 py-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] text-white text-sm font-medium disabled:opacity-40 transition-colors"
          >
            {streaming ? "…" : "Send"}
          </button>
        </div>
        <p className="text-[var(--muted)] text-xs mt-1.5">
          Try: &quot;There&apos;s a bug, the app crashes on login&quot; · &quot;Is the build
          passing?&quot; · &quot;Deploy the latest build to production&quot;
        </p>
      </div>
    </div>
  );
}
