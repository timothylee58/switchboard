"""
tests/eval/test_sme_ops_decisions.py

Routing-accuracy eval gate for the SME-operations vertical.
Mirrors tests/eval/test_agent_decisions.py exactly — same harness,
different domain package imported.

This file's existence is the architectural proof: adding a second
vertical required adding ONE file here and TWO import lines in
api/main.py. core/ and governance/ were not touched.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

import agents.sme_ops.agent  # noqa: F401 — self-registers on import
import agents.sme_ops.tools  # noqa: F401
from core.registry import AgentRegistry
from governance.eval_harness import RoutingTestCase, assert_eval_gate, run_routing_eval


def _state_for(text: str) -> dict:
    return {
        "messages": [HumanMessage(content=text)],
        "current_agent": "supervisor",
        "routing_history": [],
        "pending_approval": None,
        "domain_context": {},
    }


SME_OPS_ROUTING_CASES = [
    RoutingTestCase(
        description="broken product routes to support",
        state=_state_for("The product is broken and not working for our team"),
        expected_agent="support_agent",
    ),
    RoutingTestCase(
        description="complaint routes to support",
        state=_state_for("I want to file a complaint about the service"),
        expected_agent="support_agent",
    ),
    RoutingTestCase(
        description="policy question routes to policy agent",
        state=_state_for("What is the policy on remote work?"),
        expected_agent="policy_agent",
    ),
    RoutingTestCase(
        description="SOP question routes to policy agent",
        state=_state_for("What is the SOP for onboarding new customers?"),
        expected_agent="policy_agent",
    ),
    RoutingTestCase(
        description="invoice query routes to billing",
        state=_state_for("Can you pull up my latest invoice?"),
        expected_agent="billing_agent",
    ),
    RoutingTestCase(
        description="refund request routes to billing",
        state=_state_for("I need a refund for my subscription"),
        expected_agent="billing_agent",
    ),
    RoutingTestCase(
        description="escalation request routes to escalation agent",
        state=_state_for("I need to escalate this to a manager immediately"),
        expected_agent="escalation_agent",
    ),
    RoutingTestCase(
        description="legal threat routes to escalation",
        state=_state_for("This is unacceptable, I will pursue legal action"),
        expected_agent="escalation_agent",
    ),
    RoutingTestCase(
        description="ambiguous greeting has no owner",
        state=_state_for("hello"),
        expected_agent="__unhandled__",
    ),
]


@pytest.fixture(autouse=True)
def _ensure_sme_ops_registered():
    names = {a.name for a in AgentRegistry.all()}
    required = {"support_agent", "policy_agent", "billing_agent", "escalation_agent"}
    assert required.issubset(names), f"Missing registered agents: {required - names}"


def test_sme_ops_routing_accuracy_gate():
    result = run_routing_eval(SME_OPS_ROUTING_CASES, threshold=0.8)
    assert_eval_gate(result, threshold=0.8)


def test_sme_ops_routing_accuracy_is_reported():
    result = run_routing_eval(SME_OPS_ROUTING_CASES, threshold=0.0)
    print(f"\nSME-ops routing accuracy: {result.accuracy:.0%} ({result.correct}/{result.total})")
    if result.failures:
        print("Failures:")
        for f in result.failures:
            print(f"  - {f}")
