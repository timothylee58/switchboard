"""
core/supervisor.py

Implements supervisor-with-delegation:
  - Supervisor owns routing decisions and is the single audit chokepoint.
  - Specialist agents can request re-routing mid-task (via domain_context
    signal "needs_handoff"), but the supervisor approves and performs the
    actual re-route in one hop — agents never call each other directly.

This keeps swarm's flexibility (agents aren't rigidly siloed to one path)
without losing supervisor's governance property (every routing decision
passes through one place where guardrails/audit/HITL can hook in).
"""

from __future__ import annotations

import logging

from core.contracts import SpecialistAgent
from core.registry import AgentRegistry
from core.state import AgentState, RiskLevel, RoutingDecision

logger = logging.getLogger("switchboard.supervisor")

HANDOFF_SIGNAL_KEY = "needs_handoff"  # domain_context key agents use to request re-route


def select_agent(state: AgentState) -> tuple[SpecialistAgent | None, float, str]:
    """
    Score every registered agent's can_handle() and pick the highest.
    Returns (agent, confidence, reason). Agent is None if nothing scored > 0.
    """
    candidates = AgentRegistry.all()
    if not candidates:
        return None, 0.0, "no agents registered"

    scored = [(agent, agent.can_handle(state)) for agent in candidates]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    best_agent, best_score = scored[0]

    if best_score <= 0.0:
        return None, 0.0, "no agent claimed confidence > 0"

    reason = f"highest can_handle() score among {len(candidates)} candidates"
    return best_agent, best_score, reason


def supervisor_node(state: AgentState) -> AgentState:
    """
    The supervisor graph node. Decides routing, records the decision in
    routing_history (audit trail), and sets current_agent.

    Checks domain_context for an agent-initiated handoff request first —
    this is the "delegation" half of supervisor-with-delegation. If a
    specialist signaled it needs another agent, the supervisor honors
    that request as a routing input rather than re-scoring from scratch,
    but STILL performs the actual transition itself (single chokepoint
    preserved).
    """
    domain_context = state.get("domain_context", {})
    requested_handoff = domain_context.pop(HANDOFF_SIGNAL_KEY, None)

    if requested_handoff:
        target = AgentRegistry.get(requested_handoff)
        if target is not None:
            decision = RoutingDecision(
                from_agent=state.get("current_agent", "supervisor"),
                to_agent=target.name,
                confidence=1.0,
                reason=f"delegated handoff requested by {state.get('current_agent')}",
            )
            logger.info("Delegated handoff -> %s", target.name)
            return {
                **state,
                "current_agent": target.name,
                "routing_history": state["routing_history"] + [decision.model_dump(mode="json")],
                "domain_context": domain_context,
            }
        logger.warning(
            "Agent requested handoff to unknown agent '%s' — falling back to scoring",
            requested_handoff,
        )

    agent, confidence, reason = select_agent(state)

    if agent is None:
        decision = RoutingDecision(
            from_agent=state.get("current_agent", "supervisor"),
            to_agent="__unhandled__",
            confidence=0.0,
            reason=reason,
        )
        return {
            **state,
            "current_agent": "__unhandled__",
            "routing_history": state["routing_history"] + [decision.model_dump(mode="json")],
        }

    decision = RoutingDecision(
        from_agent=state.get("current_agent", "supervisor"),
        to_agent=agent.name,
        confidence=confidence,
        reason=reason,
    )
    logger.info("Routed -> %s (confidence=%.2f)", agent.name, confidence)
    return {
        **state,
        "current_agent": agent.name,
        "routing_history": state["routing_history"] + [decision.model_dump(mode="json")],
    }


def request_handoff(state: AgentState, target_agent_name: str) -> AgentState:
    """
    Helper a specialist agent calls from within execute() to request the
    supervisor route to a different agent next. Domain code calls this
    instead of importing another agent directly.
    """
    domain_context = dict(state.get("domain_context", {}))
    domain_context[HANDOFF_SIGNAL_KEY] = target_agent_name
    return {**state, "domain_context": domain_context}


def agent_risk_requires_hitl(agent: SpecialistAgent, state: AgentState) -> bool:
    """Graph builder calls this to decide whether to insert an interrupt
    node before executing this agent. HIGH risk is non-negotiable — a
    domain package cannot opt out of the HITL gate for HIGH-risk actions."""
    return agent.risk_level(state) == RiskLevel.HIGH
