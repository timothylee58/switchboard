"""
agents/_template/schemas.py

Each domain defines its OWN Pydantic model for what it expects to find
inside AgentState.domain_context. Core never sees this type — domain code
validates at ITS boundary by constructing/parsing this model from the
untyped dict.

COPY THIS FILE when starting a new domain — rename TemplateDomainContext
and adjust fields to match your domain's actual data shape.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class TemplateDomainContext(BaseModel):
    """Example shape. Replace fields with whatever your domain actually needs."""

    request_subject: str | None = None
    extra: dict[str, Any] = {}

    @classmethod
    def from_state_dict(cls, raw: dict[str, Any]) -> "TemplateDomainContext":
        """Tolerant parse — unknown keys go into `extra` rather than
        raising, so other agents writing to domain_context don't break
        this domain's parsing."""
        known_fields = set(cls.model_fields.keys()) - {"extra"}
        known = {k: v for k, v in raw.items() if k in known_fields}
        extra = {k: v for k, v in raw.items() if k not in known_fields}
        return cls(**known, extra=extra)
