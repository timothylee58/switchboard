"use client";

interface Props {
  agentName: string;
  confidence?: number;
}

const AGENT_COLORS: Record<string, string> = {
  triage_agent: "bg-blue-900 text-blue-300 border-blue-700",
  ci_agent: "bg-purple-900 text-purple-300 border-purple-700",
  deploy_agent: "bg-orange-900 text-orange-300 border-orange-700",
  code_agent: "bg-cyan-900 text-cyan-300 border-cyan-700",
  support_agent: "bg-green-900 text-green-300 border-green-700",
  policy_agent: "bg-teal-900 text-teal-300 border-teal-700",
  billing_agent: "bg-yellow-900 text-yellow-300 border-yellow-700",
  escalation_agent: "bg-red-900 text-red-300 border-red-700",
  supervisor: "bg-gray-800 text-gray-400 border-gray-600",
  __unhandled__: "bg-gray-900 text-gray-500 border-gray-700",
};

export function RoutingBadge({ agentName, confidence }: Props) {
  const colorClass =
    AGENT_COLORS[agentName] ?? "bg-indigo-900 text-indigo-300 border-indigo-700";

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-mono border ${colorClass}`}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-70" />
      {agentName}
      {confidence !== undefined && (
        <span className="opacity-60 ml-1">{Math.round(confidence * 100)}%</span>
      )}
    </span>
  );
}
