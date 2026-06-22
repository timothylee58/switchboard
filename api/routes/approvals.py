"""
api/routes/approvals.py

Resumes a graph paused at governance.hitl's interrupt() with a human's
approval decision. This is the endpoint the Next.js console (v2) would
call when someone clicks Approve/Reject on a pending DeployAgent or
CodeAgent proposal.
"""

from __future__ import annotations

from fastapi import APIRouter
from langgraph.types import Command
from pydantic import BaseModel

router = APIRouter()


class ApprovalResolution(BaseModel):
    thread_id: str
    approved: bool
    resolved_by: str


@router.post("/resolve")
async def resolve_approval(res: ApprovalResolution):
    from api.main import compiled_graph

    config = {"configurable": {"thread_id": res.thread_id}}
    result = compiled_graph.invoke(
        Command(resume={"approved": res.approved, "resolved_by": res.resolved_by}),
        config=config,
    )
    return {
        "thread_id": res.thread_id,
        "approved": res.approved,
        "resumed": True,
        "final_agent": result.get("current_agent"),
    }
