"""
tests/test_supervisor_routing.py

Unit tests for core/supervisor.py using a fake in-test agent — NOT the
real devtools agents. This keeps these tests genuinely domain-agnostic,
proving the supervisor mechanics (selection, handoff, audit trail) work
independent of any specific vertical.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

from core.contracts import SpecialistAgent
from core.registry import AgentRegistry
from core.state import RiskLevel
from core.supervisor import request_handoff, select_agent, supervisor_node


class _FakeAgent:
    """Minimal SpecialistAgent for testing supervisor mechanics in isolation."""

    def __init__(self, name: str, confidence: float, gate: bool = False):
        self.name = name
        self.description = f"fake agent {name}"
        self._confidence = confidence
        self.always_gate = gate

    def can_handle(self, state) -> float:
        return self._confidence

    def execute(self, state):
        return state

    def required_tools(self) -> list[str]:
        return []

    def risk_level(self, state) -> RiskLevel:
        return RiskLevel.HIGH if self.always_gate else RiskLevel.LOW


def _base_state(text: str = "hello") -> dict:
    return {
        "messages": [HumanMessage(content=text)],
        "current_agent": "supervisor",
        "routing_history": [],
        "pending_approval": None,
        "domain_context": {},
    }


@pytest.fixture(autouse=True)
def _clean_registry():
    AgentRegistry.clear()
    yield
    AgentRegistry.clear()


def test_select_agent_picks_highest_confidence():
    AgentRegistry.register(_FakeAgent("low", 0.2))
    AgentRegistry.register(_FakeAgent("high", 0.9))
    AgentRegistry.register(_FakeAgent("mid", 0.5))

    agent, confidence, _ = select_agent(_base_state())

    assert agent.name == "high"
    assert confidence == 0.9


def test_select_agent_returns_none_when_all_zero():
    AgentRegistry.register(_FakeAgent("a", 0.0))
    AgentRegistry.register(_FakeAgent("b", 0.0))

    agent, confidence, reason = select_agent(_base_state())

    assert agent is None
    assert confidence == 0.0


def test_select_agent_with_empty_registry():
    agent, confidence, reason = select_agent(_base_state())
    assert agent is None
    assert "no agents registered" in reason


def test_supervisor_node_records_routing_history():
    AgentRegistry.register(_FakeAgent("worker", 0.7))

    result = supervisor_node(_base_state())

    assert result["current_agent"] == "worker"
    assert len(result["routing_history"]) == 1
    assert result["routing_history"][0]["to_agent"] == "worker"
    assert result["routing_history"][0]["confidence"] == 0.7


def test_supervisor_node_unhandled_when_no_agent_claims():
    AgentRegistry.register(_FakeAgent("worker", 0.0))

    result = supervisor_node(_base_state())

    assert result["current_agent"] == "__unhandled__"


def test_supervisor_honors_delegated_handoff():
    AgentRegistry.register(_FakeAgent("agent_a", 0.9))
    AgentRegistry.register(_FakeAgent("agent_b", 0.1))

    state = _base_state()
    state["current_agent"] = "agent_a"
    state = request_handoff(state, target_agent_name="agent_b")

    result = supervisor_node(state)

    # Handoff request should route to agent_b even though agent_a scores
    # higher via can_handle() — delegation is honored over re-scoring.
    assert result["current_agent"] == "agent_b"
    assert result["routing_history"][0]["confidence"] == 1.0
    assert "delegated handoff" in result["routing_history"][0]["reason"]


def test_handoff_to_unknown_agent_falls_back_to_scoring():
    AgentRegistry.register(_FakeAgent("real_agent", 0.6))

    state = _base_state()
    state = request_handoff(state, target_agent_name="nonexistent_agent")

    result = supervisor_node(state)

    # Unknown handoff target should not crash — falls back to normal scoring.
    assert result["current_agent"] == "real_agent"
