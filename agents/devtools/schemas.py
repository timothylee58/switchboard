"""
agents/devtools/schemas.py

Typed view into domain_context for the internal dev-tools vertical.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class DevToolsContext(BaseModel):
    issue_id: str | None = None
    repo: str | None = None
    build_id: str | None = None
    proposed_action_summary: str | None = None
    proposed_action_payload: dict[str, Any] = {}
    extra: dict[str, Any] = {}

    @classmethod
    def from_state_dict(cls, raw: dict[str, Any]) -> "DevToolsContext":
        known_fields = set(cls.model_fields.keys()) - {"extra"}
        known = {k: v for k, v in raw.items() if k in known_fields}
        extra = {k: v for k, v in raw.items() if k not in known_fields}
        return cls(**known, extra=extra)


Severity = Literal["low", "medium", "high", "critical"]
