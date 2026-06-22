"""
governance/audit.py

Decorator-based audit logging. Wraps SpecialistAgent.execute() so every
domain package gets full audit coverage for free — zero audit code
written inside agents/{domain}/.

In-memory list for now (eval/demo friendly); swap _sink for a Supabase
insert in production (see AuditEvent.persist() stub below).
"""

from __future__ import annotations

import functools
import logging
import time
from datetime import UTC, datetime
from typing import Any, Callable

from pydantic import BaseModel, Field

from core.state import AgentState

logger = logging.getLogger("switchboard.audit")


class AuditEvent(BaseModel):
    agent_name: str
    event_type: str  # "execute_start" | "execute_success" | "execute_error"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    duration_ms: float | None = None
    error: str | None = None
    # Deliberately NOT storing full message content by default — PII risk.
    # Store message count / hash instead; opt into full payloads per-deployment.
    message_count: int = 0

    def persist(self) -> None:
        """
        TODO(production): replace with a Supabase insert into audit_log.
        Kept synchronous + simple here so the core demo has zero infra
        dependency; swap this single method when wiring real persistence.
        """
        _sink.append(self)


_sink: list[AuditEvent] = []  # in-memory store; query via get_audit_log()


def get_audit_log() -> list[AuditEvent]:
    return list(_sink)


def clear_audit_log() -> None:
    """Test-only."""
    _sink.clear()


def audited(agent_name: str) -> Callable:
    """
    Decorator factory. Emits a start event, runs the wrapped node, emits
    a success or error event, and re-raises on failure (audit logs the
    failure but does NOT swallow it — guardrails/callers decide recovery).
    """

    def decorator(fn: Callable[[AgentState], AgentState]) -> Callable[[AgentState], AgentState]:
        @functools.wraps(fn)
        def wrapper(state: AgentState) -> AgentState:
            start = time.perf_counter()
            AuditEvent(
                agent_name=agent_name,
                event_type="execute_start",
                message_count=len(state.get("messages", [])),
            ).persist()

            try:
                result = fn(state)
                AuditEvent(
                    agent_name=agent_name,
                    event_type="execute_success",
                    duration_ms=(time.perf_counter() - start) * 1000,
                    message_count=len(result.get("messages", [])),
                ).persist()
                return result
            except Exception as exc:  # noqa: BLE001 — intentionally broad: audit ALL failures
                AuditEvent(
                    agent_name=agent_name,
                    event_type="execute_error",
                    duration_ms=(time.perf_counter() - start) * 1000,
                    error=str(exc),
                ).persist()
                logger.exception("Agent '%s' execute() failed", agent_name)
                raise

        return wrapper

    return decorator
