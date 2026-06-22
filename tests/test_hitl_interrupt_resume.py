"""
tests/test_hitl_interrupt_resume.py

Codifies the pause/resume/reject HITL behavior verified manually during
development. Uses a fake always-gated agent — domain-agnostic, same
reasoning as test_supervisor_routing.py.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from core.graph_builder import build_graph
from core.registry import AgentRegistry
from core.state import RiskLevel


class _GatedFakeAgent:
    name = "gated_fake"
    description = "always-gated fake agent for HITL testing"
    always_gate = True

    def can_handle(self, state) -> float:
        return 0.9

    def execute(self, state):
        from langchain_core.messages import AIMessage

        return {**state, "messages": state["messages"] + [AIMessage(content="executed")]}

    def required_tools(self) -> list[str]:
        return []

    def risk_level(self, state) -> RiskLevel:
        return RiskLevel.HIGH


def _base_state(text: str = "do the risky thing") -> dict:
    return {
        "messages": [HumanMessage(content=text)],
        "current_agent": "supervisor",
        "routing_history": [],
        "pending_approval": None,
        "domain_context": {"proposed_action_summary": "risky action"},
    }


@pytest.fixture(autouse=True)
def _clean_registry():
    AgentRegistry.clear()
    yield
    AgentRegistry.clear()


@pytest.fixture
def graph_and_checkpointer():
    AgentRegistry.register(_GatedFakeAgent())
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer=checkpointer)
    return graph, checkpointer


def test_gated_agent_pauses_before_executing(graph_and_checkpointer):
    graph, _ = graph_and_checkpointer
    config = {"configurable": {"thread_id": "hitl-pause-test"}}

    result = graph.invoke(_base_state(), config=config)

    snapshot = graph.get_state(config)
    assert snapshot.next == ("gated_fake__hitl_gate",)
    assert "executed" not in result["messages"][-1].content
    assert "__interrupt__" in result


def test_approving_resumes_and_executes(graph_and_checkpointer):
    graph, _ = graph_and_checkpointer
    config = {"configurable": {"thread_id": "hitl-approve-test"}}

    graph.invoke(_base_state(), config=config)
    final = graph.invoke(
        Command(resume={"approved": True, "resolved_by": "test_user"}), config=config
    )

    assert final["current_agent"] == "gated_fake"
    assert final["messages"][-1].content == "executed"
    assert final["pending_approval"]["approved"] is True
    assert final["pending_approval"]["resolved_by"] == "test_user"


def test_rejecting_halts_without_executing(graph_and_checkpointer):
    graph, _ = graph_and_checkpointer
    config = {"configurable": {"thread_id": "hitl-reject-test"}}

    graph.invoke(_base_state(), config=config)

    with pytest.raises(PermissionError, match="rejected"):
        graph.invoke(
            Command(resume={"approved": False, "resolved_by": "test_user"}), config=config
        )


def test_low_risk_agent_skips_hitl_gate():
    """A non-gated agent should reach execute() in a single invoke(),
    no interrupt, no resume needed."""

    class _UngatedFakeAgent(_GatedFakeAgent):
        name = "ungated_fake"
        always_gate = False

        def risk_level(self, state) -> RiskLevel:
            return RiskLevel.LOW

    AgentRegistry.register(_UngatedFakeAgent())
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer=checkpointer)
    config = {"configurable": {"thread_id": "no-gate-test"}}

    result = graph.invoke(_base_state(), config=config)

    assert result["messages"][-1].content == "executed"
    assert "__interrupt__" not in result
