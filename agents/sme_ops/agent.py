"""
agents/sme_ops/agent.py

Four specialists for the SME-operations vertical:

  SupportAgent    — opens/triages incoming support tickets.   risk: LOW,  no gate
  PolicyAgent     — answers policy / procedure questions.      risk: LOW,  no gate
  BillingAgent    — handles invoice / billing queries.         risk: LOW,  no gate
  EscalationAgent — proposes escalation to human/senior team.  risk: HIGH, always_gate=True

This file imports only from core.* and .* (own package) — zero changes to
core/ or governance/ were required to add this vertical, which is exactly
the claim tests/test_architecture_boundary.py enforces at the CI level.
"""

from __future__ import annotations

from core.registry import AgentRegistry
from core.state import AgentState, RiskLevel
from core.supervisor import request_handoff

from .schemas import SmeOpsContext
from .tools import (
    GetInvoiceTool,
    OpenTicketTool,
    PolicyLookupTool,
    ProposeEscalationTool,
    SearchTicketsTool,
)


class SupportAgent:
    name = "support_agent"
    description = (
        "Handles incoming customer support tickets: opens a ticket, "
        "classifies its priority, and checks for similar existing issues. "
        "Route here for 'not working', 'broken', 'error', 'complaint', "
        "or any general customer problem report."
    )
    always_gate = False

    def can_handle(self, state: AgentState) -> float:
        last = _last_user_text(state).lower()
        # Yield to EscalationAgent when explicit escalation language is present.
        if any(w in last for w in ["escalate", "manager", "legal", "lawsuit"]):
            return 0.0
        if any(w in last for w in ["ticket", "complaint", "not working", "broken", "problem"]):
            return 0.8
        if "issue" in last or "error" in last:
            return 0.55
        return 0.0

    def execute(self, state: AgentState) -> AgentState:
        ctx = SmeOpsContext.from_state_dict(state.get("domain_context", {}))
        text = _last_user_text(state)

        result = OpenTicketTool().run(description=text)
        dupes = SearchTicketsTool().run(query=text)

        summary = (
            f"Ticket {result['ticket_id']} opened — priority: {result['priority']}, "
            f"similar issues found: {len(dupes['matches'])}."
        )
        new_state = _append_assistant_message(state, summary)

        # If the issue looks billing-related, hand off to BillingAgent.
        if any(w in text.lower() for w in ["invoice", "charge", "payment", "subscription"]):
            return request_handoff(new_state, target_agent_name="billing_agent")
        return new_state

    def required_tools(self) -> list[str]:
        return ["open_ticket", "search_tickets"]

    def risk_level(self, state: AgentState) -> RiskLevel:
        return RiskLevel.LOW


class PolicyAgent:
    name = "policy_agent"
    description = (
        "Answers questions about company policies, procedures, and SOPs. "
        "Route here for 'what is the process for', 'policy on', "
        "'how do I', or 'guidelines for' questions."
    )
    always_gate = False

    def can_handle(self, state: AgentState) -> float:
        last = _last_user_text(state).lower()
        if any(w in last for w in ["policy", "procedure", "sop", "guideline", "handbook"]):
            return 0.85
        if "how do i" in last or "what is the process" in last:
            return 0.7
        return 0.0

    def execute(self, state: AgentState) -> AgentState:
        ctx = SmeOpsContext.from_state_dict(state.get("domain_context", {}))
        topic = ctx.policy_topic or _last_user_text(state)

        result = PolicyLookupTool().run(topic=topic)
        summary = f"Policy ({result['source']}): {result['excerpt']}"
        return _append_assistant_message(state, summary)

    def required_tools(self) -> list[str]:
        return ["policy_lookup"]

    def risk_level(self, state: AgentState) -> RiskLevel:
        return RiskLevel.LOW


class BillingAgent:
    name = "billing_agent"
    description = (
        "Handles billing, invoice, subscription, and payment queries. "
        "Route here for 'invoice', 'billing', 'charge', 'refund', "
        "or 'subscription' questions."
    )
    always_gate = False

    def can_handle(self, state: AgentState) -> float:
        last = _last_user_text(state).lower()
        if any(w in last for w in ["invoice", "billing", "charge", "refund", "subscription", "payment"]):
            return 0.85
        return 0.0

    def execute(self, state: AgentState) -> AgentState:
        ctx = SmeOpsContext.from_state_dict(state.get("domain_context", {}))

        result = GetInvoiceTool().run(
            customer_id=ctx.customer_id,
            billing_reference=ctx.billing_reference,
        )
        summary = (
            f"Invoice for customer {result['customer_id']}: "
            f"{result['amount']} — status: {result['status']}, due: {result['due_date']}."
        )
        return _append_assistant_message(state, summary)

    def required_tools(self) -> list[str]:
        return ["get_invoice"]

    def risk_level(self, state: AgentState) -> RiskLevel:
        return RiskLevel.LOW


class EscalationAgent:
    name = "escalation_agent"
    description = (
        "Proposes escalating a case to a senior team member or human manager. "
        "Route here for 'escalate', 'speak to a manager', 'legal', or "
        "'urgent' requests. NEVER escalates without human approval."
    )
    always_gate = True

    def can_handle(self, state: AgentState) -> float:
        last = _last_user_text(state).lower()
        if any(w in last for w in ["escalate", "manager", "legal", "lawsuit", "ceo"]):
            return 0.9
        if "urgent" in last and any(w in last for w in ["human", "person", "someone"]):
            return 0.75
        return 0.0

    def execute(self, state: AgentState) -> AgentState:
        ctx = SmeOpsContext.from_state_dict(state.get("domain_context", {}))
        proposal = ProposeEscalationTool().run(
            ticket_id=ctx.ticket_id,
            reason=ctx.proposed_action_summary or _last_user_text(state),
        )
        summary = f"Escalation approved and staged: {proposal['proposal']}"
        return _append_assistant_message(state, summary)

    def required_tools(self) -> list[str]:
        return ["propose_escalation"]

    def risk_level(self, state: AgentState) -> RiskLevel:
        return RiskLevel.HIGH


def _last_user_text(state: AgentState) -> str:
    for msg in reversed(state.get("messages", [])):
        content = getattr(msg, "content", "")
        if isinstance(content, str) and content:
            return content
    return ""


def _append_assistant_message(state: AgentState, text: str) -> AgentState:
    from langchain_core.messages import AIMessage

    return {**state, "messages": state["messages"] + [AIMessage(content=text)]}


for agent in (SupportAgent(), PolicyAgent(), BillingAgent(), EscalationAgent()):
    AgentRegistry.register(agent)
