"""api/routes/audit.py — query the in-memory audit log (swap for a real
Supabase-backed query once governance/audit.py persists there)."""

from __future__ import annotations

from fastapi import APIRouter

from governance.audit import get_audit_log

router = APIRouter()


@router.get("/")
async def list_audit_events(agent_name: str | None = None, limit: int = 100):
    events = get_audit_log()
    if agent_name:
        events = [e for e in events if e.agent_name == agent_name]
    return {"count": len(events), "events": [e.model_dump() for e in events[-limit:]]}
