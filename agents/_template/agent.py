"""
agents/_template/agent.py

Reference implementation of core.contracts.SpecialistAgent. Copy this
whole agents/_template/ folder to agents/{your_domain}/, rename the
class, and implement can_handle/execute/required_tools/risk_level for
real.

WORKFLOW FOR ADDING A NEW DOMAIN:
  1. cp -r agents/_template agents/{new_domain}
  2. Rename TemplateAgent -> {Domain}Agent, adjust name/description
  3. Implement schemas.py with your real domain_context shape
  4. Implement tools.py with real tools, register with ToolRegistry
  5. Write can_handle() — a cheap heuristic is fine to start (keyword
     match, intent classifier call, etc.) — confidence score in [0, 1]
  6. Implement execute() — your actual agent logic
  7. Set always_gate=True if this agent should ALWAYS require human
     approval (e.g. anything that mutates production state)
  8. In api/main.py (or wherever the entrypoint lives), import your new
     package — that single import line is the only place outside
     agents/{new_domain}/ that changes
  9. core/ and governance/ require ZERO changes — the boundary test in
     tests/test_architecture_boundary.py will fail the build if that's
     not true
"""

from __future__ import annotations

from core.registry import AgentRegistry
from core.state import AgentState, RiskLevel

from .schemas import TemplateDomainContext


class TemplateAgent:
    name = "template_agent"
    description = (
        "Replace with a clear description of what kinds of requests this "
        "agent should handle — the supervisor's routing quality depends "
        "on this being accurate and specific, not generic."
    )

    # Structural risk declaration — used by graph_builder at BUILD time to
    # decide whether to wire an HITL gate node in front of this agent.
    # True = every invocation pauses for approval, no exceptions.
    always_gate: bool = False

    def can_handle(self, state: AgentState) -> float:
        # Replace with real heuristic / classifier call. Returning a flat
        # 0.0 here means this template agent never actually claims a
        # request — intentional, so copying the template without editing
        # can_handle() can't silently start routing real traffic to it.
        return 0.0

    def execute(self, state: AgentState) -> AgentState:
        ctx = TemplateDomainContext.from_state_dict(state.get("domain_context", {}))
        # Replace with real logic. ctx is your typed, validated view into
        # domain_context — core never sees TemplateDomainContext directly.
        return state

    def required_tools(self) -> list[str]:
        return ["template_example_tool"]

    def risk_level(self, state: AgentState) -> RiskLevel:
        return RiskLevel.LOW


AgentRegistry.register(TemplateAgent())
