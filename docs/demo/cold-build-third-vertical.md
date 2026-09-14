# Cold Build — Recording a Third Vertical From Scratch

> The third and most important recording. [`console-demo-devtools.md`](console-demo-devtools.md)
> and [`console-demo-sme-ops.md`](console-demo-sme-ops.md) show a built thing working. This one
> builds a new thing on camera, against a clock, and ends on a diff that either supports the
> repo's central claim or refutes it.

**Target length:** 12–18 minutes raw, cut to 6–8
**Proves:** that the orchestration/domain boundary is *adoptable*, not just *expressible*

---

## 0. The honesty problem — read this before anything else

Two pre-built verticals prove the pattern can be expressed. They do not prove it can be
*adopted*, because a skeptic's first thought is that `devtools` and `sme_ops` were designed
alongside `core/` and fit it for that reason. That objection is correct, unanswerable from the
existing repo, and fatal to the pitch.

The only thing that answers it is building a vertical that did **not** exist when `core/` was
written, in one sitting, with the mistakes left in.

Which creates the problem this script has to solve: **the more thoroughly I script this, the
less it proves.** A cold build with every keystroke pre-planned is theatre, and it will read as
theatre — the tell is that nothing ever surprises the presenter.

So this document deliberately scripts the *scaffolding* and refuses to script the *thinking*:

| Pre-plan it | Leave it live |
|---|---|
| Environment, terminal layout, timer | The agent names and responsibilities |
| Which domain you'll build | Every `can_handle()` heuristic |
| The closing receipt commands | Which agent gets `always_gate = True` |
| The narration *themes* below | The eval cases |
| An abort protocol | Debugging whatever doesn't route right first try |

If you catch yourself rehearsing the right-hand column, stop. You are making the recording
worthless in order to make it smoother.

---

## 1. Choosing the domain

Three criteria, in priority order:

1. **You can speak it fluently without notes.** You have to invent routing heuristics out loud.
   A domain you'd need to look up is a domain that will produce long silences on camera.
2. **It is structurally different from the two that exist** — not just different nouns. This is
   the one most people get wrong. A `tenant_support` vertical with maintenance / policy /
   billing / escalation agents is `sme_ops` with the words changed, and a sharp viewer will say
   so. Differ in *shape*: a different agent count, a second HIGH-risk agent, or a delegation
   that triggers on something other than a keyword.
3. **It has an obvious irreversible action** that earns an HITL gate without explanation.

**Recommended: `logistics`.**

```
track_agent      "where is my shipment"           LOW
route_agent      ETA and routing questions         LOW
exception_agent  damaged / lost / delayed claims   LOW
dispatch_agent   recall or reroute a vehicle       HIGH  ← always_gate
```

It wins on criterion 2 for a specific reason worth saying out loud while you build it: in
`devtools`, `triage_agent` hands off because it saw the word *"build"* in the user's text. Here,
`track_agent` can hand off to `exception_agent` because of **what its tool returned** — a
shipment status of `delayed` or `damaged` — not because of anything the user typed. Same
`request_handoff()` call, triggered by data rather than keywords. That demonstrates the
delegation mechanism generalises past string matching, which neither existing vertical shows.

Alternatives if logistics isn't yours: `clinic_ops` (booking / triage / records, with
prescription actions gated) or `school_admin` (enrolment / policy / fees, with disciplinary
actions gated). Apply the same three criteria.

---

## 2. Pre-flight

```bash
cd switchboard/
git checkout master && git pull
git status                 # must be clean — the closing shot depends on it
python -m pytest tests/ -q # baseline; note the number out loud later
```

- **Start from clean `master`.** The entire receipt depends on it. Verify on camera.
- **Do not create a branch.** Working directly on a clean tree is what makes `git add -A` at the
  end a complete and honest account of everything you did.
- **Visible timer** in frame — phone stopwatch is fine. It is doing real work here: the claim is
  about elapsed time, so the viewer needs to see it run unbroken.
- **One terminal, one editor.** No pre-opened files, no pre-typed buffers.
- Have `agents/devtools/agent.py` closed. You may open it *on camera* to crib the shape — that's
  honest and shows what a real adopter does.

---

## 3. The recording

### Segment A — The claim, and the clock (0:00–1:00)

Show clean `git status` and the passing baseline. Then state the claim plainly, so the rest of
the video can be judged against it:

> "Switchboard claims a new vertical costs you one package under `agents/` and three edited
> lines, and touches nothing in the orchestration core. I'm going to build a vertical that
> didn't exist when that core was written, starting now, and at the end I'll show you the diff.
> If `core/` or `governance/` appears in it, the claim is wrong and you'll see that too."

Start the timer. Do not stop it again until Segment F.

### Segment B — Scaffold (1:00–2:00)

```bash
python -m scripts.new_vertical logistics --activate
python -m pytest tests/ -q
```

Two things to point out, briefly — don't linger, the interesting part is next:

- It passes immediately. The generated eval file asserts that an agent which hasn't been told
  what it handles routes to `__unhandled__` — true right now, and it stops you pushing a red
  build before you've written a line.
- It registered `logistics` in the boundary test's `suspicious_tokens` for you. That's the step
  that fails silently when done by hand, which is why it isn't done by hand.

### Segment C — Design the agents, out loud (2:00–5:00)

Open `agents/logistics/agent.py`. Think on camera. This is the segment that carries the video —
the viewer is watching whether the framework gets in your way, so let them see you meet it
cold.

Narrate the decisions the Protocol actually forces:

> "Four agents. `can_handle` returns a confidence, so I have to decide what 'where's my
> shipment' scores versus 'why is it late' — those overlap, and the supervisor just takes the
> higher one. `dispatch_agent` recalls a vehicle, so that's `always_gate = True` and I don't
> write any approval logic for it — the graph builder reads the attribute and wires the gate."

Write the classes. Keyword heuristics are fine and you should say so: `can_handle()` is a seam,
and the production-upgrade table in the README already commits to swapping keywords for
embedding similarity behind an unchanged signature.

### Segment D — Tools and the data-driven handoff (5:00–9:00)

Write `tools.py` — mock returns are fine and expected at this stage. Then the moment worth
building the whole recording around, in `track_agent.execute()`:

> "Here's the part that isn't a copy of the other verticals. `track_agent` calls its tool, gets
> back a status, and *if that status is `delayed`*, it hands off to `exception_agent`. The user
> never said the word 'delayed'. This handoff is triggered by data, not by text — and it's the
> same one-line `request_handoff()` call, because the supervisor doesn't care why an agent wants
> to move the task, only that it asked instead of acting."

### Segment E — Eval cases and the first honest failure (9:00–13:00)

Replace the generated placeholder case with real ones — one per routing decision you want held
in place, including one that should route nowhere.

```bash
python -m pytest tests/eval/test_logistics_decisions.py -q -s
```

**When a case fails here, keep it in the cut.** This is not damage control; it is the most
valuable thirty seconds in the video. A cold build where the first eval run comes back at 80%
and you read the failure, see two agents' keywords overlapping, adjust a score, and re-run is
doing three things a clean run cannot:

- proving the run was genuinely unrehearsed
- demonstrating the eval harness catching a real routing mistake, which is what it's *for*
- showing the debug loop is short

Narrate it as the system working:

> "Two agents both claimed that one. That's the eval gate doing its job — it caught a routing
> collision before it ever reached a user."

### Segment F — The receipt (13:00–15:00)

Stop the timer on camera. Read the elapsed time aloud. Then:

```bash
python -m pytest tests/ -q
```

Now the shot the whole recording exists for. **Run exactly these two commands** — see the
warning below:

```bash
git add -A
git diff --cached --stat
```

```
 agents/logistics/__init__.py             |  0
 agents/logistics/agent.py                | ~200 +++++++++++++++
 agents/logistics/prompts.py              |  11 ++
 agents/logistics/schemas.py              |  32 ++
 agents/logistics/tools.py                | ~60 ++++
 api/main.py                              |   4 +-
 tests/eval/test_logistics_decisions.py   | ~90 ++++++
 tests/test_architecture_boundary.py      |   2 +-
```

> ⚠️ **Do not run a bare `git diff --stat`.** Newly scaffolded files are untracked, so it shows
> only the two modified files and hides the entire package you just built — the opposite of your
> claim, on camera, at the worst possible moment. Verified: bare `git diff --stat` reports
> `2 files changed`. You must stage first and use `--cached`.

Then the second half, which is the actual proof:

```bash
git diff --cached --stat -- core/ governance/
```

It prints **nothing**. Let the empty line sit there for a beat.

> "That's every change I made inside the orchestration core and the governance layer, across a
> vertical that didn't exist twenty minutes ago. Two edited lines in an import, one token in a
> test, and one new package. Everything else — the router, the audit trail, the approval gate —
> I inherited, and CI stops me forking it by accident."

### Segment G — Optional: run it (15:00–17:00)

```bash
uvicorn api.main:app --reload   # already pointed at logistics by --activate
```

Open the console and send two messages: one that routes, and one that hits `dispatch_agent`'s
gate. The approval card appearing for an agent that has existed for fifteen minutes, with no
approval code written for it, lands harder than any diff.

---

## 4. When it goes wrong

Distinguish two cases, because they need opposite responses.

**A bug in your new vertical** — wrong routing, a typo, a tool returning the wrong shape.
**Keep recording.** This is the video working as intended. Fix it live.

**A bug in the framework** — something in `core/` or `governance/` genuinely can't express what
your domain needs. **Also keep recording**, and say so out loud. If the scaffold has a real
limitation, a recording that surfaces it honestly is worth more than a polished one that hides
it, and it's a better portfolio artifact than a clean run: it shows you can tell the difference
between your bug and your framework's. Note it, work around it on camera, and fix it in a
follow-up PR that you can then link under the video.

**Abort only if** you lose more than ~4 minutes to environment trouble (deps, ports, a broken
venv). That's not the story, it's noise. Cut, fix off-camera, restart from Segment A with a
fresh `git reset --hard origin/master`.

Do not restart because the build was "messy." Messy is the evidence.

---

## 5. After the recording

```bash
git reset --hard origin/master   # discard, if the vertical was only for the video
```

Or keep it: a third vertical in the repo strengthens the claim permanently, and it already has
a passing eval gate. If you keep it, open it as its own PR so the diff stays legible as the
receipt it is.

**For the video description**, the three numbers worth stating: elapsed build time, total lines
added, and `0` lines changed in `core/` and `governance/`. The third is the only one that
matters, and it's the only one a viewer can verify themselves by cloning the repo.
