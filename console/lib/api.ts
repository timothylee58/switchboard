const API_BASE =
  typeof window !== "undefined"
    ? "/api"
    : (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000");

export type SseCallback = (line: string) => void;

export async function streamChat(
  threadId: string,
  message: string,
  domainContext: Record<string, unknown>,
  onLine: SseCallback,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ thread_id: threadId, message, domain_context: domainContext }),
    signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`Chat stream failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        onLine(line.slice(6).trim());
      }
    }
  }
}

export async function resolveApproval(
  threadId: string,
  approved: boolean,
  resolvedBy: string,
): Promise<{ final_agent: string }> {
  const res = await fetch(`${API_BASE}/approvals/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ thread_id: threadId, approved, resolved_by: resolvedBy }),
  });
  if (!res.ok) throw new Error(`Approval failed: ${res.status}`);
  return res.json();
}

export async function fetchAuditLog(): Promise<{ count: number; events: unknown[] }> {
  const res = await fetch(`${API_BASE}/audit`);
  if (!res.ok) throw new Error(`Audit fetch failed: ${res.status}`);
  return res.json();
}
