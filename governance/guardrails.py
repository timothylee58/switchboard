"""
governance/guardrails.py

Boundary validation that wraps every specialist node — sits OUTSIDE
domain logic so swapping industries never requires touching safety code.

This is intentionally a minimal, extensible skeleton: real deployments
plug in a proper PII/secrets scanner (e.g. Presidio) at the marked
extension points rather than the regex placeholder below.
"""

from __future__ import annotations

import functools
import logging
import re
from typing import Callable

from core.state import AgentState

logger = logging.getLogger("switchboard.guardrails")

# Placeholder pattern set — replace with a real PII/secrets scanner in production.
_SECRET_LIKE_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),       # API-key-shaped strings
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
]


class GuardrailViolation(Exception):
    """Raised when input or output fails a guardrail check. The graph
    builder lets this propagate — it's treated the same as any other
    node failure by the audit decorator (logged, not silently swallowed)."""


def _scan_for_secrets(text: str) -> list[str]:
    hits = []
    for pattern in _SECRET_LIKE_PATTERNS:
        if pattern.search(text):
            hits.append(pattern.pattern)
    return hits


def _validate_input(state: AgentState, agent_name: str) -> None:
    messages = state.get("messages", [])
    for msg in messages[-3:]:  # only scan recent turns — cost control
        content = getattr(msg, "content", "")
        if isinstance(content, str):
            hits = _scan_for_secrets(content)
            if hits:
                raise GuardrailViolation(
                    f"[{agent_name}] input contains secret-like content: {hits}"
                )


def _validate_output(state: AgentState, agent_name: str) -> None:
    messages = state.get("messages", [])
    if not messages:
        return
    last = messages[-1]
    content = getattr(last, "content", "")
    if isinstance(content, str):
        hits = _scan_for_secrets(content)
        if hits:
            raise GuardrailViolation(
                f"[{agent_name}] output contains secret-like content: {hits}"
            )


def guarded(agent_name: str) -> Callable:
    """Decorator factory. Validates state before AND after the wrapped
    node runs. Stack this OUTSIDE @audited so a guardrail rejection is
    still captured as an execute_error audit event."""

    def decorator(fn: Callable[[AgentState], AgentState]) -> Callable[[AgentState], AgentState]:
        @functools.wraps(fn)
        def wrapper(state: AgentState) -> AgentState:
            _validate_input(state, agent_name)
            result = fn(state)
            _validate_output(result, agent_name)
            return result

        return wrapper

    return decorator
