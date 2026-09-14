# Switchboard Console — Recorded Demo Script (devtools vertical)

> Vertical #1 of two. The companion script, [`console-demo-sme-ops.md`](console-demo-sme-ops.md),
> re-records the same console against the `sme_ops` vertical to demonstrate the
> "swap one import, ship a new vertical" claim. Record this one first.

**Target length:** ~4–5 minutes
**Shows:** supervisor routing, agent-initiated delegation, structural HITL gate, live audit log
**Cast:** you (one voice, one browser tab, one terminal)

---

## 0. Before you hit record

**Terminal 1 — backend**
```bash
cd switchboard/
pip install -r requirements.txt
uvicorn api.main:app --reload
# → http://localhost:8000
```

**Terminal 2 — console**
```bash
cd switchboard/console/
npm install
npm run dev
# → http://localhost:3001
```

**Browser**
- Open `http://localhost:3001` in a fresh tab — a fresh page load gives you a brand-new `thread-<timestamp>` id, which matters for the narration in Scene 1.
- Zoom the browser to ~110–125% so the sidebar text and audit log are legible on a recording.
- Optional second tab: `http://localhost:8000/docs` (Swagger) — only open this for the closing beat, not before.
- Do **one** silent dry run first. `MemorySaver` is in-memory (`api/main.py`) — restarting `uvicorn` wipes all threads and the audit log, so if you flub a take, restart the backend before re-recording rather than trying to hide it with a new thread.

**Layout:** terminal 1 visible in a corner (viewers should see the SSE lines scroll when you send a message — that's the "it's actually streaming, not scripted" proof), console filling the rest of the frame.

---

## Scene 1 — Cold open: what's on screen (0:00–0:30)

**Say, while the cursor rests on the sidebar:**
> "This is Switchboard's operator console — one FastAPI backend behind it, no domain code touching this UI directly. On the left, the four registered agents for this vertical, colour-coded by risk. Two are low-risk, auto-routed. Two are high-risk and structurally gated — you'll see what that means in a minute."

**Action:** hover over `deploy_agent` / `code_agent` in the sidebar legend long enough for the red `HIGH ⛔` tag to register on camera. Point out the empty **Audit Log** panel and its `0 events` counter — you'll return to this at the end so the count going from 0 → N is visible proof, not a claim.

---

## Scene 2 — Turn 1: routing + agent-initiated delegation (0:30–1:45)

**Type into the input** (use the exact placeholder-suggested phrasing — it's tuned to the demo agents' `can_handle()` keywords):

```
There's a bug, the app crashes on login
```

**While it streams, say:**
> "That message never touches a router I wrote by hand for this demo — every registered agent scored it via `can_handle()`, and `triage_agent` won on confidence."

**Point at:** the blue `triage_agent` routing badge appearing above the reply, and the reply text itself (a severity + duplicate-check summary).

**Send a follow-up in the same thread:**

```
Is the build passing?
```

**Say, while pointing at the terminal's scrolling SSE log:**
> "Watch the badge change — this went to `ci_agent`, not because I told it to, but because `ci_agent` scored highest on this message. Same supervisor, same single chokepoint, different specialist."

**Point at:** the purple `ci_agent` badge and its reply (`Build <id> status: ...` or a failure summary).

> This is the plain "supervisor picks the highest scorer twice" version of Scene 2 — safe, always reproducible on camera. If you want the *mid-task delegation* moment from the architecture walkthrough (`triage_agent` seeing "build" in the text and calling `request_handoff()` to `ci_agent` **inside one turn**), send a single message that trips both signals instead of two separate ones, e.g. `"There's a bug — the build looks broken"`. Rehearse this exact phrasing once off-camera first: `TriageAgent.can_handle()` only fires the handoff when its own bug-keyword branch wins the first score *and* the text still contains `"build"` or `"ci"` — small wording changes can tip it to `ci_agent` on the first hop instead, which is a fine result but tells a different (less interesting) story on camera.

---

## Scene 3 — Turn 2: the HITL gate (1:45–3:15)

**Type:**

```
Deploy the latest build to production
```

**Say, right as the message sends:**
> "This one's HIGH risk. Watch — no reply streams in."

**Beat of silence — let the UI actually pause.** The amber **⏸ Approval Required** card appears in place of a normal reply, with `deploy_agent` labelled next to it and the input box disabling itself (you cannot send another message with a pending approval — call that out, it's not a UI accident, it's a real interrupt).

**Say:**
> "This isn't a `setTimeout` for effect. LangGraph's `interrupt()` fired inside `deploy_agent`'s gate node, execution actually stopped, and the state — including this exact pending approval — was checkpointed. I could close this tab, restart the backend tomorrow, and resuming would still work off this same thread id."

**Action:** hover the two buttons — **Approve** (green) / **Reject** (red) — without clicking yet, so both read clearly on camera.

**Click Approve.**

**Say, as the resolution message posts:**
> "Approve calls `/approvals/resolve`, LangGraph resumes the graph with that decision attached, and only *then* does `deploy_agent.execute()` run — it stages a proposal, it doesn't touch real infrastructure in this reference build."

**Point at:** the `✓ Action approved and executed.` system line that appears in the thread.

**Optional second take for the reject path** (either splice in during editing, or do it live in a fresh thread — click **New thread** first so this doesn't chain off the approved deploy):
```
Roll back the deployment
```
→ click **Reject** this time → narrate the `✗ Action rejected — no changes made.` line: *"Reject short-circuits the graph before `execute()` ever runs — the rollback never happens."*

---

## Scene 4 — Proof, not narration: the audit log (3:15–4:00)

**Say, panning to the sidebar:**
> "Everything I just did was auditable without a single log line I wrote by hand."

**Point at:** the **Audit Log** panel's event count, now well above `0`, and scroll it to show `execute_start` / `execute_success` pairs for `triage_agent`, `ci_agent`, and `deploy_agent` in order. (It polls every 5s — if it hasn't refreshed yet on camera, wait a beat rather than cutting.)

**Say:**
> "That came from one decorator, `@audited`, wrapping every agent's `execute()` — none of the domain code you saw route this conversation ever called a logger."

---

## Scene 5 — Close (4:00–4:30, optional)

**Switch to the `http://localhost:8000/docs` tab** and scroll past `/chat/stream`, `/approvals/resolve`, `/audit` without clicking into them.

**Say:**
> "Three endpoints, one graph, zero domain-specific code outside `agents/devtools/`. Swap that one import in `api/main.py` and this same console, same supervisor, same governance layer runs a completely different vertical."

**End card / cut.**

---

## Cheat sheet (message → expected outcome)

| Type this | Expect | Why |
|---|---|---|
| `There's a bug, the app crashes on login` | Routes to `triage_agent` | "bug"/"crash" keyword, score 0.85 |
| `Is the build passing?` | Routes to `ci_agent` | "build" keyword, score 0.8 |
| `There's a bug — the build looks broken` | `triage_agent` responds, then self-delegates to `ci_agent` mid-turn | triage's bug-branch wins scoring, then its `execute()` sees "build" and calls `request_handoff()` |
| `Deploy the latest build to production` | Pauses on ⏸ **Approval Required** (`deploy_agent`) | `always_gate = True`, HIGH risk |
| `Write a patch for this issue` / `draft PR` | Pauses on ⏸ **Approval Required** (`code_agent`) | second HIGH-risk agent, if you want variety |

**If a take goes sideways:** click **New thread** (top-right of the chat header) rather than reloading the page — it resets `messages`/`pendingApproval` state instantly without losing your terminal/backend setup, and gives you a fresh thread id on screen for the next take.
