"""
governance/eval_harness.py

v1 scope: scores supervisor ROUTING decisions against a labeled test set
("did it pick the right specialist"), not full RAGAS faithfulness scoring.

This reuses the pattern from NakTahu AI's RAGAS-in-CI gate, generalized
to the agentic-specific question: routing correctness, not RAG quality.
Full RAGAS-style multi-metric scoring (faithfulness, relevancy, recall)
is v2 scope once a second vertical exists to test generalization against.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.registry import AgentRegistry
from core.state import AgentState


@dataclass
class RoutingTestCase:
    description: str
    state: AgentState
    expected_agent: str


@dataclass
class RoutingEvalResult:
    total: int
    correct: int
    failures: list[str]

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


def run_routing_eval(cases: list[RoutingTestCase], threshold: float = 0.8) -> RoutingEvalResult:
    """
    Scores supervisor.select_agent() against labeled cases. Intended to be
    called from tests/eval/test_agent_decisions.py and gated in CI
    (.github/workflows/eval-gate.yml) — a PR that drops routing accuracy
    below `threshold` fails the build, mirroring the RAGAS faithfulness
    gate from NakTahu AI.
    """
    from core.supervisor import select_agent  # local import: avoid core->eval coupling at module load

    failures: list[str] = []
    correct = 0

    for case in cases:
        agent, confidence, _ = select_agent(case.state)
        picked = agent.name if agent else "__unhandled__"
        if picked == case.expected_agent:
            correct += 1
        else:
            failures.append(
                f"{case.description}: expected '{case.expected_agent}', "
                f"got '{picked}' (confidence={confidence:.2f})"
            )

    return RoutingEvalResult(total=len(cases), correct=correct, failures=failures)


def assert_eval_gate(result: RoutingEvalResult, threshold: float = 0.8) -> None:
    """Call from CI test — raises AssertionError with readable diagnostics
    on failure, which is what shows up in the GitHub Actions log."""
    if result.accuracy < threshold:
        detail = "\n".join(f"  - {f}" for f in result.failures)
        raise AssertionError(
            f"Routing accuracy {result.accuracy:.0%} below threshold {threshold:.0%}\n"
            f"Failures:\n{detail}"
        )
