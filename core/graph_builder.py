"""
core/graph_builder.py

Assembles the runnable LangGraph StateGraph from whatever agents are
currently in AgentRegistry. This file is what makes "adding a domain is
additive" literally true: it iterates AgentRegistry.all() and wires nodes
generically — it never names a specific agent.

Every specialist node is wrapped by governance (audit + guardrails) before
being added to the graph, and HIGH-risk agents get an interrupt node
inserted ahead of them automatically (core/supervisor.agent_risk_requires_hitl).
"""

from __future__ import annotations

import logging

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from core.contracts import SpecialistAgent
from core.registry import AgentRegistry
from core.state import AgentState
from core.supervisor import agent_risk_requires_hitl, supervisor_node
from governance.audit import audited
from governance.guardrails import guarded
from governance.hitl import hitl_interrupt_node

logger = logging.getLogger("switchboard.graph_builder")

SUPERVISOR_NODE = "supervisor"
UNHANDLED_NODE = "__unhandled__"


def _make_specialist_node(agent: SpecialistAgent):
    """Wrap an agent's execute() with guardrails (input/output validation)
    and audit logging (before/after event emission). Domain code in
    agent.execute() never has to call either of these itself."""

    @guarded(agent_name=agent.name)
    @audited(agent_name=agent.name)
    def node(state: AgentState) -> AgentState:
        return agent.execute(state)

    return node


def _route_from_supervisor(state: AgentState) -> str:
    current = state.get("current_agent", UNHANDLED_NODE)
    if current == UNHANDLED_NODE:
        return UNHANDLED_NODE
    return current


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    """
    Build and compile the StateGraph. Call this AFTER all domain agents
    have self-registered (i.e. after importing the chosen domain package).
    """
    graph = StateGraph(AgentState)
    graph.add_node(SUPERVISOR_NODE, supervisor_node)
    graph.add_node(UNHANDLED_NODE, lambda state: state)  # terminal: no agent claimed the request

    agents = AgentRegistry.all()
    if not agents:
        logger.warning(
            "build_graph() called with zero registered agents — "
            "did you forget to import a domain package?"
        )

    routing_map: dict[str, str] = {UNHANDLED_NODE: UNHANDLED_NODE}

    for agent in agents:
        node_name = agent.name
        specialist_node = _make_specialist_node(agent)

        if agent_risk_requires_hitl_static(agent):
            # HIGH-risk agents: interrupt node sits between supervisor and
            # the specialist. Graph pauses here until governance.hitl
            # resolves the approval, then proceeds to the specialist node.
            gate_name = f"{node_name}__hitl_gate"
            graph.add_node(gate_name, hitl_interrupt_node(agent_name=node_name))
            graph.add_node(node_name, specialist_node)
            graph.add_edge(gate_name, node_name)
            graph.add_edge(node_name, END)
            routing_map[node_name] = gate_name
        else:
            graph.add_node(node_name, specialist_node)
            graph.add_edge(node_name, END)
            routing_map[node_name] = node_name

    graph.add_conditional_edges(SUPERVISOR_NODE, _route_from_supervisor, routing_map)
    graph.add_edge(UNHANDLED_NODE, END)
    graph.set_entry_point(SUPERVISOR_NODE)

    return graph.compile(checkpointer=checkpointer)


def agent_risk_requires_hitl_static(agent: SpecialistAgent) -> bool:
    """
    Graph topology (which nodes exist, whether an HITL gate node is wired
    in front of a specialist) must be decided once, at build time — but
    risk_level() takes `state`, which doesn't exist yet at build time.

    Resolution: an agent that EVER requires HITL for ANY state must
    declare it structurally, not just per-call. Domain agents expose this
    via a class-level `always_gate: bool` attribute (see agents/_template).
    Per-call risk (core/supervisor.agent_risk_requires_hitl) is used at
    runtime by the gate node itself to decide whether to actually pause,
    so a gated agent can still fast-path low-risk calls through approved=True.
    """
    return getattr(agent, "always_gate", False)
