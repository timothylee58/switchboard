"""
api/main.py

This file contains the ONLY import of a specific domain package in the
entire codebase outside agents/{domain}/ itself. Swapping verticals means
changing this one line — `import agents.devtools.agent` becomes
`import agents.sme_ops.agent`, nothing else changes.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.memory import MemorySaver

# vvv THE ONE DOMAIN-SPECIFIC IMPORT IN THE ENTIRE APP vvv
import agents.devtools.agent  # noqa: F401 — import triggers self-registration
import agents.devtools.tools  # noqa: F401
# ^^^ swap these two lines to point at a different agents/{domain}/ package ^^^

from core.graph_builder import build_graph

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("switchboard.api")

app = FastAPI(title="Switchboard", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# MemorySaver is dev-only — swap for a Redis/Postgres checkpointer in
# production so interrupted (HITL-paused) graphs survive a process restart.
checkpointer = MemorySaver()
compiled_graph = build_graph(checkpointer=checkpointer)


@app.get("/health")
def health():
    return {"status": "ok"}


from api.routes import approvals, audit, chat  # noqa: E402 — after app/graph init

app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(approvals.router, prefix="/approvals", tags=["approvals"])
app.include_router(audit.router, prefix="/audit", tags=["audit"])
