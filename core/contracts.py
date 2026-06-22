"""
core/contracts.py

Protocol interfaces. core/ only ever calls methods on these protocols —
it never imports a concrete domain class. This is what makes the
"if domain == X" branch architecturally impossible at the core level:
there's nowhere to put it, because core only ever holds a reference typed
as SpecialistAgent, never FinanceAgent or DeployAgent directly.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from core.state import AgentState, RiskLevel


@runtime_checkable
class BaseTool(Protocol):
    """Contract every domain tool implements."""

    name: str
    description: str

    def run(self, **kwargs: Any) -> Any:
        """Execute the tool. Raise on failure — governance.audit wraps this
        to log both success and failure paths."""
        ...


@runtime_checkable
class SpecialistAgent(Protocol):
    """
    Contract every domain agent implements.

    name/description are used by the supervisor for routing — description
    should be written as if explaining to a router "what kind of request
    should come to me," since that's effectively how it's used (today as
    a heuristic; swappable for an embedding-similarity router later without
    changing this contract).
    """

    name: str
    description: str

    def can_handle(self, state: AgentState) -> float:
        """
        Return a confidence score in [0.0, 1.0] for whether this agent
        should handle the current state. The supervisor calls this across
        every registered agent and routes to the highest score.

        Returning 0.0 means "definitely not me" — agents should be honest
        here rather than always returning a high score; over-claiming
        confidence degrades routing quality for the whole system.
        """
        ...

    def execute(self, state: AgentState) -> AgentState:
        """
        Perform the agent's work and return the updated state.
        Do NOT call governance directly from here — the registry wraps
        every execute() call with audit logging and guardrail checks,
        so domain code stays free of cross-cutting concerns.
        """
        ...

    def required_tools(self) -> list[str]:
        """Names of tools this agent needs, used for capability checks
        and for the eval harness to verify tool availability before a run."""
        ...

    def risk_level(self, state: AgentState) -> RiskLevel:
        """
        Risk classification for the action this agent is about to take,
        given current state. HIGH always triggers governance.hitl's
        interrupt gate before execute() is called — this is enforced by
        the graph builder, not by convention, so a domain package cannot
        accidentally skip it.
        """
        ...
