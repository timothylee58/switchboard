"""
agents/devtools/agent.py

Four specialists for the internal dev-tools vertical:

  TriageAgent  — classifies/dedupes issues.            risk: LOW,  no gate
  CIAgent      — checks build status, summarizes fails. risk: LOW,  no gate
  DeployAgent  — proposes deploy/rollback actions.       risk: HIGH, always_gate=True
  CodeAgent    — proposes patches/draft PRs.              risk: HIGH, always_gate=True

DeployAgent and CodeAgent NEVER execute their proposed action directly —
execute() only stages a proposal into domain_context; the actual mutating
action would live behind a SEPARATE execution step that only runs after
governance.hitl resolves the approval (wired in core/graph_builder.py).
This split — "propose" vs "execute-after-approval" — is the concrete
mechanism behind the HITL claim, not just a label on the agent.
"""

from __future__ import annotations

from core.registry import AgentRegistry
from core.state import AgentState, RiskLevel
from core.supervisor import request_handoff

from .schemas import DevToolsContext
from .tools import (
    ClassifySeverityTool,
    GetBuildStatusTool,
    GetFailureLogsTool,
    ProposeDeployTool,
    ProposePatchTool,
    SearchIssuesTool,
)


class TriageAgent:
    name = "triage_agent"
    description = (
        "Handles new issue reports: classifies severity, checks for "
        "duplicate issues, summarizes what's known. Route here first "
        "for any bug report, crash, or 'something's broken' message."
    )
    always_gate = False

    def can_handle(self, state: AgentState) -> float:
        last = _last_user_text(state).lower()

        # "fix"/"patch"/"draft pr" signals belong to CodeAgent even when a
        # bug keyword is also present ("fix this bug") — check the more
        # specific competing intent first and yield if it's present.
        if any(w in last for w in ["write a patch", "draft pr", "propose a fix", "fix this"]):
            return 0.0

        if any(w in last for w in ["bug", "crash", "broken", "error report"]):
            return 0.85
        if "issue" in last:
            return 0.6  # weaker signal alone — "issue" is a common word, less specific than "bug"/"crash"
        return 0.0  # no signal: do not claim the request by default

    def execute(self, state: AgentState) -> AgentState:
        ctx = DevToolsContext.from_state_dict(state.get("domain_context", {}))
        text = _last_user_text(state)

        severity = ClassifySeverityTool().run(description=text)["severity"]
        dupes = SearchIssuesTool().run(query=text)["matches"]

        summary = f"Triaged: severity={severity}, duplicates_found={len(dupes)}."

        # If this looks like it needs a build check, delegate to CIAgent
        # via the supervisor rather than calling CIAgent directly.
        new_state = _append_assistant_message(state, summary)
        if "build" in text.lower() or "ci" in text.lower():
            return request_handoff(new_state, target_agent_name="ci_agent")
        return new_state

    def required_tools(self) -> list[str]:
        return ["classify_severity", "search_issues"]

    def risk_level(self, state: AgentState) -> RiskLevel:
        return RiskLevel.LOW


class CIAgent:
    name = "ci_agent"
    description = (
        "Checks CI/build pipeline status and summarizes failures. "
        "Route here for 'is the build passing', 'why did CI fail', "
        "or pipeline status questions."
    )
    always_gate = False

    def can_handle(self, state: AgentState) -> float:
        last = _last_user_text(state).lower()
        if any(w in last for w in ["build", "ci", "pipeline", "deploy status"]):
            return 0.8
        return 0.0

    def execute(self, state: AgentState) -> AgentState:
        ctx = DevToolsContext.from_state_dict(state.get("domain_context", {}))
        build_id = ctx.build_id or "latest"

        status = GetBuildStatusTool().run(build_id=build_id)
        if status["status"] == "failed":
            logs = GetFailureLogsTool().run(build_id=build_id)
            summary = f"Build {build_id} failed at {status['stage']}: {logs['summary']}"
        else:
            summary = f"Build {build_id} status: {status['status']}"

        return _append_assistant_message(state, summary)

    def required_tools(self) -> list[str]:
        return ["get_build_status", "get_failure_logs"]

    def risk_level(self, state: AgentState) -> RiskLevel:
        return RiskLevel.LOW


class DeployAgent:
    name = "deploy_agent"
    description = (
        "Proposes deploy, rollback, or scaling actions. Route here for "
        "'deploy this', 'roll back', 'scale up' requests. NEVER executes "
        "directly — always requires human approval first."
    )
    always_gate = True  # structural: graph_builder wires an HITL gate in front of this node

    def can_handle(self, state: AgentState) -> float:
        last = _last_user_text(state).lower()
        if any(w in last for w in ["deploy", "rollback", "roll back", "scale"]):
            return 0.9
        return 0.0

    def execute(self, state: AgentState) -> AgentState:
        """
        By the time execute() runs, the HITL gate (governance/hitl.py)
        has ALREADY resolved pending_approval=approved for this call —
        graph_builder wires the gate node strictly before this node for
        always_gate=True agents. execute() here only stages the proposal
        and records what was approved; it still doesn't perform a real
        infrastructure mutation in this reference implementation.
        """
        ctx = DevToolsContext.from_state_dict(state.get("domain_context", {}))
        proposal = ProposeDeployTool().run(
            repo=ctx.repo, action=ctx.proposed_action_summary or "deploy"
        )
        summary = f"Deploy action approved and staged: {proposal['proposal']}"
        return _append_assistant_message(state, summary)

    def required_tools(self) -> list[str]:
        return ["propose_deploy"]

    def risk_level(self, state: AgentState) -> RiskLevel:
        return RiskLevel.HIGH


class CodeAgent:
    name = "code_agent"
    description = (
        "Proposes code patches or draft PRs for simple, well-scoped "
        "fixes. Route here for 'fix this bug', 'write a patch' requests. "
        "NEVER merges or executes directly — always requires approval."
    )
    always_gate = True

    def can_handle(self, state: AgentState) -> float:
        last = _last_user_text(state).lower()
        if any(w in last for w in ["fix this", "write a patch", "draft pr", "propose a fix"]):
            return 0.85
        return 0.0

    def execute(self, state: AgentState) -> AgentState:
        ctx = DevToolsContext.from_state_dict(state.get("domain_context", {}))
        proposal = ProposePatchTool().run(
            repo=ctx.repo, issue_id=ctx.issue_id, summary=ctx.proposed_action_summary
        )
        summary = f"Patch proposal approved and staged: {proposal['proposal']}"
        return _append_assistant_message(state, summary)

    def required_tools(self) -> list[str]:
        return ["propose_patch"]

    def risk_level(self, state: AgentState) -> RiskLevel:
        return RiskLevel.HIGH


def _last_user_text(state: AgentState) -> str:
    messages = state.get("messages", [])
    for msg in reversed(messages):
        content = getattr(msg, "content", "")
        if isinstance(content, str) and content:
            return content
    return ""


def _append_assistant_message(state: AgentState, text: str) -> AgentState:
    from langchain_core.messages import AIMessage

    return {**state, "messages": state["messages"] + [AIMessage(content=text)]}


for agent in (TriageAgent(), CIAgent(), DeployAgent(), CodeAgent()):
    AgentRegistry.register(agent)
