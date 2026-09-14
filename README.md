# Switchboard

**Domain-agnostic agentic orchestration with production-grade governance baked into the architecture.**

Built as both a flagship portfolio project and a reusable scaffold: fork it, swap the domain layer, ship a new vertical without touching orchestration code.

---

## The core idea

Most "AI agent" templates fail one of two ways: either they're too abstract to prove anything, or they're so domain-baked you can't tell what's reusable. Switchboard separates orchestration from domain knowledge **architecturally**, not just by folder convention — and a CI test enforces the boundary on every PR.

```
┌──────────────────────────────────────────────────────────────────┐
│  DOMAIN LAYER  (swappable — one agents/{domain}/ package)        │
│  Agents implement SpecialistAgent Protocol · Tools implement      │
│  BaseTool Protocol · Registration on import (zero config)         │
└───────────────────────────┬──────────────────────────────────────┘
                             │ implements Protocol only
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  ORCHESTRATION CORE  (never changes per domain)                   │
│  Supervisor → scores can_handle() → routes to highest agent       │
│  Agents request_handoff() → supervisor performs hop (single gate)│
└───────────────────────────┬──────────────────────────────────────┘
                             │ wraps every node call
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  GOVERNANCE LAYER  (transparent to domain packages)              │
│  Audit log · Input/output guardrails · Human-in-the-loop gates   │
│  Routing eval harness · Architecture boundary enforcement (CI)    │
└──────────────────────────────────────────────────────────────────┘
```

**The rule that keeps this honest:** a new domain only ever requires adding files under `agents/{domain}/` — zero changes to `core/` or `governance/`. `tests/test_architecture_boundary.py` AST-parses both packages and **fails the CI build** if any domain name appears in either.

---

## Project layout

```
switchboard/
├── core/
│   ├── contracts.py          # SpecialistAgent + BaseTool Protocol definitions
│   ├── registry.py           # AgentRegistry + ToolRegistry (import-triggered)
│   ├── state.py              # AgentState TypedDict, RiskLevel enum, RoutingDecision
│   ├── supervisor.py         # Scoring router + request_handoff() helper
│   └── graph_builder.py      # LangGraph StateGraph builder — wires HITL gates generically
│
├── governance/
│   ├── audit.py              # @audited decorator — start/success/error events
│   ├── guardrails.py         # @guarded decorator — input/output secret scanning
│   ├── hitl.py               # LangGraph interrupt() gate node
│   └── eval_harness.py       # run_routing_eval() — scores routing accuracy at 80% gate
│
├── agents/
│   ├── _template/            # Copy this to start a new vertical (step-by-step docstring)
│   │   ├── agent.py
│   │   ├── schemas.py
│   │   ├── tools.py
│   │   └── prompts.py
│   ├── devtools/             # Demo vertical #1 — internal developer tools
│   │   ├── agent.py          # TriageAgent, CIAgent, DeployAgent, CodeAgent
│   │   ├── schemas.py        # DevToolsContext(BaseModel)
│   │   └── tools.py          # 6 mock tools
│   └── sme_ops/              # Demo vertical #2 — SME business operations support
│       ├── agent.py          # SupportAgent, PolicyAgent, BillingAgent, EscalationAgent
│       ├── schemas.py        # SmeOpsContext(BaseModel)
│       └── tools.py          # 5 mock tools
│
├── api/
│   ├── main.py               # FastAPI app — THE ONE domain import lives here
│   └── routes/
│       ├── chat.py           # POST /chat/stream — SSE streaming endpoint
│       ├── approvals.py      # POST /approvals/resolve — HITL resume endpoint
│       └── audit.py          # GET /audit — audit log query endpoint
│
├── console/                  # Next.js 15 operator console
│   ├── app/                  # App Router pages
│   ├── components/
│   │   ├── ChatWindow.tsx    # SSE streaming chat UI
│   │   ├── HitlApprovalCard.tsx  # Approve/Reject UI for HITL-paused threads
│   │   ├── AuditLog.tsx      # Live audit log sidebar
│   │   └── RoutingBadge.tsx  # Per-agent colour-coded routing indicator
│   ├── lib/api.ts            # streamChat(), resolveApproval(), fetchAuditLog()
│   └── types/index.ts        # Shared TypeScript types
│
├── scripts/
│   └── new_vertical.py       # Scaffolds a vertical from _template in one command
│
├── docs/
│   └── demo/                 # Scene-by-scene scripts for recording the console
│
└── tests/
    ├── test_architecture_boundary.py   # THE boundary enforcement test — AST-based
    ├── test_supervisor_routing.py       # Supervisor unit tests (domain-agnostic)
    ├── test_hitl_interrupt_resume.py     # HITL pause/approve/reject tests
    ├── test_new_vertical_scaffold.py     # Scaffolder output validity tests
    └── eval/
        ├── test_agent_decisions.py       # devtools routing accuracy (80% gate)
        └── test_sme_ops_decisions.py     # sme_ops routing accuracy (80% gate)
```

---

## Architecture deep-dive

### Orchestration pattern: supervisor-with-delegation

The supervisor is the **single routing chokepoint**:

- Every message enters `supervisor_node()`, which scores all registered agents via `can_handle()` and routes to the highest scorer.
- Specialist agents can signal they need another agent via `request_handoff(state, target_agent_name)` — they never import or call sibling agents directly.
- The supervisor honors handoff requests but **still performs the actual hop itself**, so governance hooks stay centralized.

This trades pure-swarm flexibility (agents calling each other freely) for governability — every routing decision passes through one place where audit, guardrails, and HITL can hook in.

```python
# core/supervisor.py — the router
def supervisor_node(state: AgentState) -> AgentState:
    # 1. Check for agent-initiated handoff first
    requested_handoff = domain_context.pop("needs_handoff", None)
    if requested_handoff:
        target = AgentRegistry.get(requested_handoff)
        # supervisor performs the hop, not the requesting agent
        return {**state, "current_agent": target.name, ...}

    # 2. Score every registered agent and pick the highest
    agent, confidence, reason = select_agent(state)
    return {**state, "current_agent": agent.name, ...}
```

### SpecialistAgent Protocol

Every domain agent implements four methods — no base class, just a structural protocol:

```python
class SpecialistAgent(Protocol):
    name: str
    description: str

    def can_handle(self, state: AgentState) -> float:
        """Confidence 0.0–1.0. Supervisor picks the highest scorer."""
        ...

    def execute(self, state: AgentState) -> AgentState:
        """Do the work. Governance wraps this automatically — no audit code here."""
        ...

    def required_tools(self) -> list[str]:
        """Tool names this agent needs — used by the eval harness."""
        ...

    def risk_level(self, state: AgentState) -> RiskLevel:
        """HIGH always triggers an HITL gate before execute() runs."""
        ...
```

### Human-in-the-loop, for real

HITL uses LangGraph's native `interrupt()` + `MemorySaver` checkpointer:

- Agents declare `always_gate = True` structurally on the class.
- `core/graph_builder.py` inspects every registered agent at build time and wires a `{name}__hitl_gate` node **before** the agent node for `always_gate=True` agents.
- The gate node calls `langgraph.interrupt()` — this is not a custom polling flag. State is durably checkpointed when execution pauses. Approval can arrive seconds or days later.

```python
# core/graph_builder.py (simplified)
for agent in AgentRegistry.all():
    if getattr(agent, "always_gate", False):
        graph.add_node(f"{agent.name}__hitl_gate", hitl_gate_node)
        graph.add_edge(f"{agent.name}__hitl_gate", agent.name)
    else:
        graph.add_edge("supervisor", agent.name)
```

**Verified behavior** (`tests/test_hitl_interrupt_resume.py`):

| Test | Outcome |
|------|---------|
| Gated agent called | `GraphInterrupt` raised before `execute()` runs |
| `approved=True` resume | `execute()` runs, returns updated state |
| `approved=False` resume | `PermissionError` — action never happens |
| Non-gated LOW-risk agent | Gate node never inserted, no overhead |

### Governance decorators

Both decorators live in `governance/` and are applied by `graph_builder.py` — domain packages never touch them:

```python
# governance/audit.py — emits start/success/error events
@audited("deploy_agent")
def execute(state):
    ...

# governance/guardrails.py — scans input + output for secret-like patterns
@guarded("deploy_agent")
@audited("deploy_agent")
def execute(state):
    ...
```

`@guarded` wraps `@audited` so guardrail violations are captured as `execute_error` audit events — failures are logged, never swallowed.

### Architecture boundary enforcement

`tests/test_architecture_boundary.py` AST-parses every `.py` file under `core/` and `governance/`:

- Fails if any domain package name (`devtools`, `sme_ops`, `support`, …) appears in an import.
- Fails if any `if domain == "X"` conditional is present.
- Domain names are added to the suspect list in the test file (one line) when a new vertical is added.

This test runs on every PR via `.github/workflows/core-ci.yml`.

---

## Demo verticals

### Vertical #1 — Internal dev-tools (`agents/devtools/`)

| Agent | Responsibility | Risk | HITL gate |
|-------|---------------|------|-----------|
| `TriageAgent` | Classify severity, check for duplicate issues | LOW | No |
| `CIAgent` | Fetch build status, summarize CI failures | LOW | No |
| `DeployAgent` | Propose deploy / rollback actions | HIGH | **Always** |
| `CodeAgent` | Propose patches / draft PRs | HIGH | **Always** |

`DeployAgent` and `CodeAgent` never execute a mutation directly — `execute()` stages a proposal into `domain_context`; the real action only runs after a human approves via `/approvals/resolve`.

**Handoff example:** If `TriageAgent.execute()` detects a build-related issue, it calls `request_handoff(state, "ci_agent")` — `CIAgent` handles the next hop without the two agents importing each other.

### Vertical #2 — SME business operations (`agents/sme_ops/`)

Built to prove the zero-core-changes claim. Zero lines changed in `core/` or `governance/`:

| Agent | Responsibility | Risk | HITL gate |
|-------|---------------|------|-----------|
| `SupportAgent` | Handle ticket/complaint routing | LOW | No |
| `PolicyAgent` | Look up SOPs, guidelines, handbooks | LOW | No |
| `BillingAgent` | Invoice lookups, refund queries | LOW | No |
| `EscalationAgent` | Legal/CEO/manager escalations | HIGH | **Always** |

**What it took to add this vertical:**
1. Copy `agents/_template/` → `agents/sme_ops/`
2. Implement 4 agents + 5 tools
3. Change **two import lines** in `api/main.py`:
   ```python
   # Before (devtools)
   import agents.devtools.agent
   import agents.devtools.tools

   # After (sme_ops)
   import agents.sme_ops.agent
   import agents.sme_ops.tools
   ```
4. Done. All 17 tests pass. Architecture boundary test stays green.

---

## Operator console (Next.js 15)

`console/` is a dark-themed operator dashboard that wires to the FastAPI backend via SSE.

**Features:**
- **Streaming chat** — `POST /chat/stream` events are read via `ReadableStream` and accumulated into the assistant message in real time.
- **HITL approval UI** — when the backend emits a `hitl_paused` event, `HitlApprovalCard` surfaces with Approve / Reject buttons. The chat input is disabled until the human decides.
- **Routing badge** — colour-coded per-agent indicator shows which specialist handled the last message.
- **Live audit log** — sidebar polls `/audit` every 5s and displays events in reverse-chronological order.
- **Thread management** — "New thread" button generates a fresh `thread_id`, clearing history and any pending approval state.

```
┌──────────────────────────────────────────────────────┐
│  S Switchboard  v0.1                                  │
│  Domain-agnostic agentic orchestration               │
├─────────────────┬────────────────────────────────────│
│  Active agents  │  Chat                              │
│  triage  LOW    │  [User message]                    │
│  ci      LOW    │  [triage_agent] Triaged:           │
│  deploy  HIGH ⛔ │    severity=high, dupes=0          │
│  code    HIGH ⛔ │                                    │
│                 │  ⏸ Paused — awaiting approval      │
│  Audit log      │  ┌────────────────────────────┐    │
│  execute_start  │  │ ⚠ Human approval required  │    │
│  execute_success│  │ deploy_agent                │    │
│  execute_start  │  │ [Approve] [Reject]          │    │
│                 │  └────────────────────────────┘    │
└─────────────────┴────────────────────────────────────┘
```

### Recorded demo scripts

Two scene-by-scene scripts for recording the console end to end — setup commands, exact
messages to type, what each one is expected to route to and why, and the narration beats
that make the architecture visible rather than asserted:

| Script | Shows |
|--------|-------|
| [`docs/demo/console-demo-devtools.md`](docs/demo/console-demo-devtools.md) | Supervisor routing across `triage_agent` / `ci_agent`, a mid-turn `request_handoff()` delegation, the `deploy_agent` HITL gate (approve + reject takes), and the live audit log filling up |
| [`docs/demo/console-demo-sme-ops.md`](docs/demo/console-demo-sme-ops.md) | The same console and the same supervisor after swapping one import — `support_agent` → `billing_agent` delegation and the `escalation_agent` gate, proving the orchestration layer is domain-blind |
| [`docs/demo/cold-build-third-vertical.md`](docs/demo/cold-build-third-vertical.md) | Building a *third* vertical from scratch on camera, against a clock, ending on a diff that shows zero lines changed in `core/` and `governance/` |

Record the first two back to back and the cut writes itself: vertical #1 → the one-line swap →
vertical #2. The third is a different kind of recording — the first two show a built thing
working, which proves the pattern is *expressible*; the cold build proves it is *adoptable*,
which is the claim a reader actually has to take on trust otherwise.

---

## Routing eval harness

`governance/eval_harness.py` provides `run_routing_eval()` — a lightweight accuracy gate that runs in CI:

```python
cases = [
    EvalCase(input="Build is failing on main", expected_agent="ci_agent"),
    EvalCase(input="Deploy the release to production", expected_agent="deploy_agent"),
    # ...
]
result = run_routing_eval(cases, compiled_graph)
assert result.accuracy >= 0.80  # CI gate
```

Each vertical ships its own eval set under `tests/eval/`. The 80% accuracy threshold gates every PR.

---

## Adding a new vertical

```bash
python -m scripts.new_vertical {your_domain}
```

That copies `agents/_template/`, renames every identifier, writes a routing eval file that
passes on arrival, and registers the domain with the boundary test. Add `--activate` to point
`api/main.py` at it, or `--dry-run` to see what it would write. Then implement the agents:

1. Implement `can_handle`, `execute`, `required_tools`, `risk_level` for each agent.
2. Set `always_gate = True` on any agent whose actions require human approval.
3. At the bottom of the file, register every agent:
   ```python
   for agent in (AgentA(), AgentB(), ...):
       AgentRegistry.register(agent)
   ```
4. Create matching tools in `tools.py`, registering each via `ToolRegistry.register()`.
5. Create a domain context schema in `schemas.py` (optional but recommended).
6. Replace the generated case in `tests/eval/test_{your_domain}_decisions.py` with real
   routing cases as you implement `can_handle()`.

Steps the scaffolder already handled for you — worth knowing it did them, because skipping
either by hand fails *silently*: it swapped the domain import in `api/main.py` (with
`--activate`), and it added your domain to `suspicious_tokens` in
`tests/test_architecture_boundary.py`. Without that second one, your new domain's name is the
one name the boundary test never checks for in `core/`.

That's it. `core/` and `governance/` stay untouched. The boundary test will tell you immediately if anything leaks.

### What a vertical actually costs

The claim above is cheap to make, so here is the receipt — every line that exists because
`sme_ops` exists, measured against everything it did *not* have to touch:

| | Files | Lines |
|---|---|---|
| `agents/sme_ops/` (4 agents, 5 tools, 1 context schema) | 4 | 308 |
| `tests/eval/test_sme_ops_decisions.py` (routing accuracy set) | 1 | 101 |
| `api/main.py` — the domain import | 1 | **2** |
| `tests/test_architecture_boundary.py` — one token in `suspicious_tokens` | 1 | **1** |
| **`core/` + `governance/` — orchestration, routing, audit, guardrails, HITL** | **0** | **0 of 856** |

A whole working vertical is ~400 lines you write plus 3 lines you edit. The 856 lines of
orchestration and governance underneath it are the part you inherit for free — and the part
CI stops you from accidentally forking.

For a worked example of the swap itself, [`docs/demo/console-demo-sme-ops.md`](docs/demo/console-demo-sme-ops.md)
walks through pointing the running app at a different vertical, including which parts of the
console are genuinely domain-agnostic and which are still hardcoded demo scaffolding.

---

## API reference

### `POST /chat/stream`

Send a message. Returns a `text/event-stream` of LangGraph node events.

```json
// Request
{
  "thread_id": "thread-abc123",
  "message": "The app is crashing on login",
  "domain_context": {}
}
```

```
// Response (SSE)
data: {"triage_agent": {"current_agent": "triage_agent", "last_message": "Triaged: severity=critical, duplicates_found=0."}}

data: {"type": "hitl_paused", "detail": "..."}  // only for HIGH-risk agents

data: [DONE]
```

### `POST /approvals/resolve`

Resume a HITL-paused thread.

```json
// Request
{
  "thread_id": "thread-abc123",
  "approved": true,
  "resolved_by": "timothy@example.com"
}
```

```json
// Response
{"status": "resumed", "thread_id": "thread-abc123", "approved": true}
```

### `GET /audit`

Fetch the in-memory audit log.

```json
// Response
{
  "events": [
    {
      "agent_name": "triage_agent",
      "event_type": "execute_success",
      "timestamp": "2026-06-22T07:05:01.234Z",
      "duration_ms": 12.4,
      "message_count": 2
    }
  ]
}
```

---

## Running locally

### Backend (FastAPI)

```bash
cd switchboard/

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn api.main:app --reload
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

### Console (Next.js)

```bash
cd switchboard/console/

npm install
npm run dev
# → http://localhost:3001
```

The console proxies `/api/*` to `http://localhost:8000` via `next.config.ts` rewrites — no CORS configuration required during development.

### Docker

```bash
docker compose up --build
```

---

## Testing

```bash
# Full suite
python -m pytest tests/ -v

# Architecture boundary check only
python -m pytest tests/test_architecture_boundary.py -v

# HITL interrupt/resume tests
python -m pytest tests/test_hitl_interrupt_resume.py -v

# Routing eval (devtools)
python -m pytest tests/eval/test_agent_decisions.py -v

# Routing eval (sme_ops)
python -m pytest tests/eval/test_sme_ops_decisions.py -v
```

Current suite: **17/17 passing** across boundary enforcement, supervisor routing, HITL behavior, and two eval gates.

---

## CI/CD

Two GitHub Actions workflows run on every PR:

| Workflow | Trigger | Checks |
|----------|---------|--------|
| `core-ci.yml` | PR / push to `main` | Boundary test · Supervisor unit tests · HITL tests |
| `eval-gate.yml` | PR / push to `main` | devtools routing accuracy ≥ 80% |

---

## Production upgrade path

| Concern | Current (dev) | Production swap |
|---------|--------------|-----------------|
| HITL state persistence | `MemorySaver` (in-process) | Redis / Postgres `AsyncCheckpointer` — paused threads survive restarts |
| Audit log | In-memory `list` | `AuditEvent.persist()` → Supabase `audit_log` table |
| Secret scanning | Regex placeholder | Presidio / custom PII scanner at `guardrails.py` extension points |
| Multi-tenancy | Single graph | RLS on audit table, per-org agent registry isolation |
| LLM routing | Keyword `can_handle()` | Embedding-similarity scorer (same `SpecialistAgent.can_handle()` signature, no protocol change) |
| CORS | `allow_origins=["*"]` | Restrict to frontend origin(s) |

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Orchestration | [LangGraph](https://github.com/langchain-ai/langgraph) 0.2+ |
| API | FastAPI 0.115+ · Uvicorn · Server-Sent Events |
| State | LangGraph `StateGraph` + `MemorySaver` checkpointer |
| Validation | Pydantic v2 |
| Console | Next.js 15 (App Router) · TypeScript · Tailwind CSS |
| Tests | pytest 8.3+ · pytest-asyncio |
| CI | GitHub Actions |

---

## Status

**v1 — complete.** Core orchestration, governance layer, HITL with durable checkpointing, and two verified verticals (devtools + sme_ops) all tested. Next.js operator console built and verified.

**v2 scope** (not yet started): Redis checkpointer for production HITL persistence, Supabase audit persistence, Presidio guardrails, multi-tenant RLS, embedding-based routing upgrade.
