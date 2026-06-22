"""
api/routes/chat.py

SSE endpoint that invokes the compiled graph. Each thread_id maps to a
LangGraph checkpointer thread — this is what lets a HITL-interrupted
conversation be resumed later via api/routes/approvals.py using the same
thread_id.
"""

from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langgraph.errors import GraphInterrupt
from pydantic import BaseModel

router = APIRouter()


class ChatRequest(BaseModel):
    thread_id: str
    message: str
    domain_context: dict = {}


@router.post("/stream")
async def chat_stream(req: ChatRequest):
    from api.main import compiled_graph  # local import: avoid circular import at module load

    config = {"configurable": {"thread_id": req.thread_id}}
    initial_state = {
        "messages": [HumanMessage(content=req.message)],
        "current_agent": "supervisor",
        "routing_history": [],
        "pending_approval": None,
        "domain_context": req.domain_context,
    }

    def event_stream():
        try:
            for event in compiled_graph.stream(initial_state, config=config):
                yield f"data: {json.dumps(_serialize_event(event))}\n\n"
        except GraphInterrupt as interrupt_payload:
            # Graph paused at an HITL gate — surface the approval request
            # to the client so it can prompt a human, then call
            # /approvals/resolve with the same thread_id once decided.
            yield f"data: {json.dumps({'type': 'hitl_paused', 'detail': str(interrupt_payload)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _serialize_event(event: dict) -> dict:
    """Best-effort JSON-safe serialization of a LangGraph stream event."""
    safe = {}
    for node_name, node_state in event.items():
        messages = node_state.get("messages", []) if isinstance(node_state, dict) else []
        safe[node_name] = {
            "current_agent": node_state.get("current_agent") if isinstance(node_state, dict) else None,
            "last_message": getattr(messages[-1], "content", None) if messages else None,
        }
    return safe
