# Switchboard Console — Recorded Demo Script (sme_ops vertical)

> Vertical #2 of two, and the companion to [`console-demo-devtools.md`](console-demo-devtools.md).
> Record that one first — this script assumes the viewer has already seen the dev-tools
> vertical running in the same console.

**Point of this recording:** the README's claim is "swap one import, ship a new vertical" —
this take proves it by showing the *same* console, *same* supervisor, *same* governance
layer, now routing customer-support conversations instead of dev-ops ones. Record this
**after** the devtools take so you can cut "here's vertical #1 → here's the one-line swap →
here's vertical #2" in editing.

---

## 0. The one-line swap (do this on camera, or as your transition cut)

`api/main.py` has exactly one domain-specific import block:

```python
# vvv THE ONE DOMAIN-SPECIFIC IMPORT IN THE ENTIRE APP vvv
import agents.devtools.agent   # noqa: F401 — import triggers self-registration
import agents.devtools.tools   # noqa: F401
# ^^^ swap these two lines to point at a different agents/{domain}/ package ^^^
```

Change it to:

```python
import agents.sme_ops.agent    # noqa: F401
import agents.sme_ops.tools    # noqa: F401
```

**Stop `uvicorn` and restart it** — this isn't hot-reloadable in a way that re-registers
agents cleanly, and `MemorySaver` is in-memory anyway, so a clean restart also gives you a
guaranteed-empty audit log for the new take:

```bash
uvicorn api.main:app --reload
```

**One honest caveat to narrate, not hide:** `console/app/page.tsx`'s sidebar "Active agents"
legend is a hardcoded array of the four **devtools** agent names — it isn't fetched from the
backend. If you don't touch it, the sidebar will still read `triage_agent` / `ci_agent` /
`deploy_agent` / `code_agent` while the chat is actually routing to `support_agent` /
`policy_agent` / `billing_agent` / `escalation_agent`. Two honest options:

- **(Recommended for the recording)** Temporarily edit the array in `console/app/page.tsx`
  to the four sme_ops names/risk levels below, restart `next dev`, and revert the edit after
  recording — it's a demo-only UI label, not orchestration logic:
  ```ts
  { name: "support_agent",    risk: "LOW" },
  { name: "policy_agent",     risk: "LOW" },
  { name: "billing_agent",    risk: "LOW" },
  { name: "escalation_agent", risk: "HIGH ⛔" },
  ```
- **Or** leave it as-is and say on camera: *"The sidebar legend is currently hardcoded to
  the devtools vertical's agent names — that's a console demo-scaffolding gap, not something
  the orchestration core cares about. Watch the routing badges on the actual replies instead;
  those come straight from `current_agent` in graph state."* This is arguably the more
  credible take for a portfolio recording — it shows you know the boundary between "real
  architecture claim" and "unfinished demo chrome."

Pick one before you roll; don't decide mid-recording.

---

## Scene A — Routing across three low-risk agents (0:00–1:30)

**Say:**
> "Same console, same `/chat/stream` endpoint, same `supervisor_node()` — the backend is now
> running `api.main` with one import changed. This is the sme_ops vertical: support tickets,
> policy lookups, billing."

**Type:**
```
The checkout page isn't working
```
→ routes to **support_agent** (`"not working"` → 0.8). Reply opens a ticket and reports a priority + duplicate count.

**Type:**
```
What's the policy on refunds?
```
→ routes to **policy_agent** (`"policy"` → 0.85). Reply is a policy excerpt + source.

**Type:**
```
My invoice charge looks wrong
```
→ routes to **billing_agent** (`"invoice"`/`"charge"` → 0.85). Reply is an invoice lookup (amount, status, due date).

**Say, over the three badges now visible in the thread:**
> "Three different specialists, same scoring mechanism as the dev-tools vertical — nothing in `core/supervisor.py` knows these agent names exist."

---

## Scene B — Mid-task delegation, one message (1:30–2:15)

**Type:**
```
There's a problem with my subscription — the invoice charge is wrong
```

**Say, as it streams:**
> "`support_agent` claims this first — 'problem' is its keyword, not a billing one. But inside
> its own `execute()`, it notices 'invoice'/'charge'/'subscription' in the text and requests a
> handoff to `billing_agent`, the same `request_handoff()` mechanism you saw triage use for CI
> in the dev-tools demo. Watch the badge change mid-reply."

**Point at:** the badge switching from `support_agent`'s ticket-opened summary to `billing_agent`'s invoice lookup, both in the same turn.

*(Rehearse this one off-camera too — like the devtools case, it depends on `support_agent.can_handle()` winning the first score before its `execute()` re-reads the text for billing keywords.)*

---

## Scene C — The HITL gate, different agent, same mechanism (2:15–3:30)

**Type:**
```
I want to escalate this to a manager
```

**Say:**
> "`escalation_agent` is this vertical's HIGH-risk, `always_gate=True` agent — the sme_ops
> equivalent of `deploy_agent`. Same gate node, same `interrupt()`, different domain."

**Beat of silence** as the ⏸ **Approval Required** card appears, labelled `escalation_agent`, input disabled.

**Click Approve.**

**Say, as the resolution posts:**
> "Approved and staged — same `/approvals/resolve` → `Command(resume=...)` round-trip as the
> deploy approval. The graph never cared that this domain has nothing to do with software
> deployment."

**Optional reject take** (new thread first):
```
This needs legal attention, escalate to legal
```
→ click **Reject** → narrate: *"Rejected — no escalation is created, same short-circuit as rejecting a deploy."*

---

## Scene D — Close: the audit log doesn't know or care which vertical (3:30–4:00)

**Pan to the sidebar Audit Log**, now showing `execute_start`/`execute_success` for `support_agent`, `policy_agent`, `billing_agent`, `escalation_agent` in order.

**Say:**
> "Same `@audited` decorator, same in-memory sink, four completely different agent names in
> it than the last recording. That's the whole pitch: fork the repo, write
> `agents/{your_domain}/`, change one import — orchestration and governance don't move."

**End card / cut.**

---

## Cheat sheet (sme_ops)

| Type this | Expect | Why |
|---|---|---|
| `The checkout page isn't working` | Routes to `support_agent` | "not working" keyword, 0.8 |
| `What's the policy on refunds?` | Routes to `policy_agent` | "policy" keyword, 0.85 |
| `My invoice charge looks wrong` | Routes to `billing_agent` | "invoice"/"charge" keyword, 0.85 |
| `There's a problem with my subscription — the invoice charge is wrong` | `support_agent` responds, then self-delegates to `billing_agent` mid-turn | support's "problem" branch wins first score, then its `execute()` sees billing keywords and calls `request_handoff()` |
| `I want to escalate this to a manager` | Pauses on ⏸ **Approval Required** (`escalation_agent`) | "escalate"/"manager" keyword, 0.9, `always_gate=True` |
| `This needs legal attention, escalate to legal` | Also pauses on `escalation_agent` — use for the reject take | "escalate"/"legal" keyword, 0.9 |

**Don't type** `"I have an escalate-worthy broken checkout"`-style blends without rehearsing —
`support_agent.can_handle()` explicitly returns `0.0` the moment it sees `"escalate"`,
`"manager"`, `"legal"`, or `"lawsuit"` in the text, so any escalation language yields
straight to `escalation_agent` instead of routing through support first. That's a
deliberate yield rule worth calling out if you want a sixth beat: *"support_agent scores
zero here on purpose — it's not just picking the smaller number, it's declining to
compete."*

**Reverting after the recording:** switch `api/main.py`'s two import lines back to
`agents.devtools.*`, revert the `page.tsx` sidebar array if you edited it, and restart both
`uvicorn` and `next dev` before doing any other work in the repo.
