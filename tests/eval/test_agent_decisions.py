"""
tests/eval/test_agent_decisions.py

Routing-accuracy eval gate, mirroring the RAGAS-in-CI pattern from
NakTahu AI but scoring supervisor routing decisions instead of RAG
faithfulness. Runs in .github/workflows/eval-gate.yml — a PR that drops
routing accuracy below 0.8 fails the build.

NOTE: this file imports agents.devtools — that's expected and correct.
tests/ is NOT a protected directory in test_architecture_boundary.py;
only core/ and governance/ are forbidden from naming a domain package.
Eval tests are domain-specific by nature (you're scoring real routing
behavior for a real vertical), and a different domain would get its own
tests/eval/test_{domain}_decisions.py alongside this one.
"""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage

import agents.devtools.agent  # noqa: F401 — self-registers on import
import agents.devtools.tools  # noqa: F401
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


DEVTOOLS_ROUTING_CASES = [
    RoutingTestCase(
        description="bug report routes to triage",
        state=_state_for("There's a bug, the app crashes on login"),
        expected_agent="triage_agent",
    ),
    RoutingTestCase(
        description="issue report routes to triage",
        state=_state_for("Got an error report from a customer"),
        expected_agent="triage_agent",
    ),
    RoutingTestCase(
        description="build status question routes to CI",
        state=_state_for("Is the build passing right now?"),
        expected_agent="ci_agent",
    ),
    RoutingTestCase(
        description="pipeline question routes to CI",
        state=_state_for("Why did the pipeline fail?"),
        expected_agent="ci_agent",
    ),
    RoutingTestCase(
        description="deploy request routes to deploy agent",
        state=_state_for("Please deploy the latest build to production"),
        expected_agent="deploy_agent",
    ),
    RoutingTestCase(
        description="rollback request routes to deploy agent",
        state=_state_for("We need to roll back the last release"),
        expected_agent="deploy_agent",
    ),
    RoutingTestCase(
        description="patch request routes to code agent",
        state=_state_for("Can you fix this bug and write a patch?"),
        expected_agent="code_agent",
    ),
    RoutingTestCase(
        description="ambiguous greeting has no clear owner",
        state=_state_for("hey"),
        expected_agent="__unhandled__",
    ),
]


@pytest.fixture(autouse=True)
def _ensure_devtools_registered():
    """Belt-and-suspenders: confirm the domain package actually
    registered its agents before running eval cases, so a routing
    failure can't be silently caused by an empty registry."""
    names = {a.name for a in AgentRegistry.all()}
    required = {"triage_agent", "ci_agent", "deploy_agent", "code_agent"}
    assert required.issubset(names), f"Missing registered agents: {required - names}"


def test_devtools_routing_accuracy_gate():
    """CI gate: fails the build if routing accuracy drops below 80%
    on the labeled case set above."""
    result = run_routing_eval(DEVTOOLS_ROUTING_CASES, threshold=0.8)
    assert_eval_gate(result, threshold=0.8)


def test_devtools_routing_accuracy_is_reported():
    """Non-gating: prints accuracy to the test log even when it passes,
    so a slow drift (e.g. 100% -> 85%) is visible in CI history before
    it ever crosses the gate threshold."""
    result = run_routing_eval(DEVTOOLS_ROUTING_CASES, threshold=0.0)
    print(f"\nRouting accuracy: {result.accuracy:.0%} ({result.correct}/{result.total})")
    if result.failures:
        print("Failures:")
        for f in result.failures:
            print(f"  - {f}")
