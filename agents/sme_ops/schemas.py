"""
agents/sme_ops/schemas.py

Typed view into domain_context for the SME-operations vertical.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class SmeOpsContext(BaseModel):
    ticket_id: str | None = None
    customer_id: str | None = None
    policy_topic: str | None = None
    billing_reference: str | None = None
    proposed_action_summary: str | None = None
    extra: dict[str, Any] = {}

    @classmethod
    def from_state_dict(cls, raw: dict[str, Any]) -> "SmeOpsContext":
        known_fields = set(cls.model_fields.keys()) - {"extra"}
        known = {k: v for k, v in raw.items() if k in known_fields}
        extra = {k: v for k, v in raw.items() if k not in known_fields}
        return cls(**known, extra=extra)


Priority = Literal["low", "medium", "high", "urgent"]
