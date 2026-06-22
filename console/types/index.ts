export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  agentName?: string;
  timestamp: number;
}

export interface RoutingEvent {
  currentAgent: string | null;
  lastMessage: string | null;
  nodeName: string;
}

export interface HitlPausedEvent {
  type: "hitl_paused";
  detail: string;
}

export interface StreamEvent {
  [nodeName: string]: {
    current_agent: string | null;
    last_message: string | null;
  };
}

export interface AuditEvent {
  id: string;
  timestamp: string;
  agent_name: string;
  event_type: string;
  detail: string;
}

export interface AuditLogResponse {
  count: number;
  events: AuditEvent[];
}

export interface ApprovalRequest {
  threadId: string;
  agentName: string;
  summary: string;
}
