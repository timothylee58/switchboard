"""
governance/hitl.py

Human-in-the-loop gate built on LangGraph's native interrupt() primitive,
not a custom polling flag. This is the detail that makes the HITL claim
credible: state is persisted via the checkpointer when execution pauses,
so approval can arrive seconds or days later without losing context —
the process can even restart in between.

Flow:
  1. graph_builder inserts a "{agent}__hitl_gate" node before any agent
     with always_gate=True.
  2. hitl_interrupt_node() calls LangGraph's interrupt(), which halts
     the graph and persists state via the configured checkpointer.
  3. A human calls api/routes/approvals.py, which resumes the graph
     with a Command(resume=...) carrying the approval decision.
  4. If approved, execution proceeds to the specialist node. If rejected,
     the request is recorded and the graph short-circuits to END.
"""

from __future__ import annotations

import logging
from typing import Callable

from langgraph.types import interrupt

from core.state import AgentState, ApprovalRequest, RiskLevel

logger = logging.getLogger("switchboard.hitl")


def request_approval(
    state: AgentState,
    agent_name: str,
    action_summary: str,
    payload: dict,
    risk_level: RiskLevel = RiskLevel.HIGH,
) -> AgentState:
    """Helper a specialist agent calls (typically from a gate node, not
    from execute() itself) to populate the pending_approval field before
    the graph interrupts. Stored as a plain dict (not the ApprovalRequest
    instance) so the LangGraph checkpointer can msgpack-serialize it
    across a real pause without a custom-type allowlist."""
    approval = ApprovalRequest(
        requested_by=agent_name,
        action_summary=action_summary,
        risk_level=risk_level,
        payload=payload,
    )
    return {**state, "pending_approval": approval.model_dump(mode="json")}


def hitl_interrupt_node(agent_name: str) -> Callable[[AgentState], AgentState]:
    """
    Factory returning a node function for the given agent's HITL gate.

    interrupt() raises a special control-flow exception that LangGraph
    catches; on next invocation with a resume Command, execution
    continues from this exact point with the resume value available.
    """

    def node(state: AgentState) -> AgentState:
        existing = state.get("pending_approval")
        if existing is not None and existing.get("resolved"):
            # Already resolved (graph resumed after approval) — pass through.
            if not existing.get("approved"):
                logger.info("HITL gate for '%s' rejected — halting", agent_name)
                raise PermissionError(
                    f"Action '{existing.get('action_summary')}' was rejected by "
                    f"{existing.get('resolved_by') or 'reviewer'}"
                )
            return state

        # First pass through this node: populate the approval request and pause.
        action_summary = state.get("domain_context", {}).get(
            "proposed_action_summary", f"{agent_name} requesting approval"
        )
        payload = state.get("domain_context", {}).get("proposed_action_payload", {})

        staged = request_approval(
            state,
            agent_name=agent_name,
            action_summary=action_summary,
            payload=payload,
        )

        logger.info("HITL gate engaged for '%s': %s", agent_name, action_summary)

        # Halts here; resumes with whatever value the approver's
        # Command(resume=...) carries when api/routes/approvals.py acts.
        resume_value = interrupt(
            {
                "agent": agent_name,
                "action_summary": action_summary,
                "payload": payload,
            }
        )

        approved = bool(resume_value.get("approved", False))
        resolved_by = resume_value.get("resolved_by", "unknown")

        resolved_approval = {
            **staged["pending_approval"],
            "resolved": True,
            "approved": approved,
            "resolved_by": resolved_by,
        }

        if not approved:
            logger.info("HITL gate for '%s' rejected by %s", agent_name, resolved_by)
            raise PermissionError(
                f"Action '{action_summary}' was rejected by {resolved_by}"
            )

        return {**staged, "pending_approval": resolved_approval}

    return node
