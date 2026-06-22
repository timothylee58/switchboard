"""
core/state.py

The single shared state schema for the entire graph. This file must NEVER
import anything from agents/{domain}/ — that import is what the architecture
boundary test (tests/test_architecture_boundary.py) checks for on every CI run.

domain_context is the one deliberate escape hatch: an untyped dict that core
passes through without inspecting. Each domain package defines its own
Pydantic model for what goes inside it and validates at ITS boundary, not here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

# LangGraph's checkpointer serializes state via msgpack and, by default,
# refuses unregistered custom types (a forward-compat safety check, soon
# to be enforced strictly). RoutingDecision/ApprovalRequest are stored as
# plain dicts in state instead of Pydantic instances so checkpointing
# "just works" without an allowlist — see .model_dump() usage below.


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"  # always routes through HITL gate, no exceptions


class RoutingDecision(BaseModel):
    """One entry in the audit trail. Supervisor appends one of these per hop.

    Always store via .model_dump() into AgentState.routing_history — the
    list is typed as list[dict] in AgentState precisely so the
    checkpointer never has to serialize a custom class."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    to_agent: str
    confidence: float
    reason: str


class ApprovalRequest(BaseModel):
    """Populated when a node calls governance.hitl.request_approval().

    Same rule as RoutingDecision: stored in AgentState as a plain dict
    (via .model_dump()), reconstructed with ApprovalRequest(**d) when a
    typed view is needed."""

    requested_by: str
    action_summary: str
    risk_level: RiskLevel
    payload: dict[str, Any]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved: bool = False
    approved: bool | None = None
    resolved_by: str | None = None


class AgentState(TypedDict):
    """
    The graph's shared state. Every node reads and writes this object.

    Fields:
        messages: conversation history, LangGraph's add_messages reducer
                  handles merging across nodes automatically.
        current_agent: name of the specialist currently holding control.
        routing_history: full audit trail of supervisor decisions, stored
                  as plain dicts (RoutingDecision.model_dump()) so the
                  LangGraph checkpointer can msgpack-serialize state
                  without needing a custom-type allowlist. Reconstruct
                  with RoutingDecision(**d) when you need typed access.
        pending_approval: dict form of ApprovalRequest, or None when no
                  HITL gate is active. Same plain-dict rule as above —
                  checkpointer needs to persist this across a real pause.
        domain_context: the ONLY field a domain package may freely write to.
                  Core never reads its internal shape, only passes it along.
    """

    messages: Annotated[list[BaseMessage], add_messages]
    current_agent: str
    routing_history: list[dict[str, Any]]
    pending_approval: dict[str, Any] | None
    domain_context: dict[str, Any]
