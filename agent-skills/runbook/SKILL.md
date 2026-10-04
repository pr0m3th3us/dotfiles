---
name: runbook
description: "Turns a multi-step goal into an executable runbook: a phased, priority-coded HTML checklist with time/cost budgets, verification gates, dependencies, and a gotchas appendix. Use whenever someone is setting up, installing, configuring, migrating, provisioning, onboarding, or standing up anything multi-step (dev environment, toolchain, pipeline, home lab, service, account/access setup), or asks for a plan, checklist, step-by-step, or walkthrough — including \"help me get X working\", \"move from A to B\", \"where do I start with X\". Triggers even on a single question if answering means hours/days of sequential work. Skip for one-off commands, pure explanation, or anything Claude can just do directly. Also use for /runbook list (a board of the repo's runbooks by progress), /runbook next, start, tick, or when someone asks which runbooks are active, how far one has got, or what to do next in one."
---

# Runbook

A runbook is what you build when the work is too long to hold in a chat, too
sequential to hand over as prose, and too likely to break halfway for a plan
that assumes success. It is a checklist someone actually ticks, on their own
machine, over hours or days — often coming back to it across sessions and
across devices.

Two things make it worth the effort over just answering. It **survives contact
with reality**: verification gates catch a broken phase before three more get
built on top of it, and the gotchas section is where hard-won debugging goes so
the next person doesn't rediscover it. And it **carries state**: progress is
saved, so the work can be paused, resumed, and picked up later.

## The shape of the work

Intake → clarify → propose approaches → runbook → offer to execute in tandem.

Do not skip to the runbook. A runbook built on a vague goal will be confidently
wrong in ways that cost hours, because every step after the wrong one inherits
the mistake. The interview is not politeness; it is where determinism comes from.

## 1. Intake

Ask for these four things if they aren't already clear. Take whatever the person
gives, however loose — turning vague into deterministic is your job, not theirs.

| Input | What you're really after |
|---|---|
| **Goal** | The end state, stated so completion is checkable. "Faster dev environment" is a wish; "development happens in Linux, on this Windows machine, for Java and Node projects" is a goal. |
| **Current state** | What exists today: OS and versions, what's installed, what's already working, what they've already tried and how it failed. Half of all steps are decided here. |
| **Rough approach** | Their instinct for how to get there. Often vague or partly wrong — that's expected and useful, because correcting it early is cheaper than correcting it in step 30. |
| **Preferences and constraints** | Budget (minimizing cost is usually a yes — ask, don't assume), time available, whether this is one-shot or has a long-term maintenance tail, hard restrictions (corporate policy, existing tooling they won't abandon, hardware limits). |

## 2. Clarify — and only ask what changes the runbook

Every question should be one where different answers produce a *different
document*. "Which Java version?" changes step contents. "What's your favourite
editor?" usually doesn't. Ask in batches, not one at a time, and prefer offering
concrete options with honest trade-offs over open questions — people choose
better from a menu than from a blank page, and a menu proves you understand the
domain.

Research before asking. If the domain has moved since your training data —
versions, pricing, whether a product still exists on a platform — check. Arriving
with "OrbStack has no Windows build, so here are the three real options" is worth
more than a question that assumes it does. **Wrong facts in a runbook are worse
than missing ones**, because the person will run the commands.

Watch for the things people don't know to tell you:

- **Platform assumptions that don't hold.** A tool they named may not exist on
  their OS, or may behave differently there.
- **Blast radius.** What breaks elsewhere if this succeeds? Existing backups,
  scheduled jobs, other machines, teammates.
- **The thing after the thing.** They asked to install it; do they also need it
  to survive a reboot, run unattended, or work on a second machine?
- **Reversibility.** Which steps are hard to undo. Those deserve a warning and
  sometimes a snapshot step before them.

## 3. Propose approaches before writing steps

Give two or three real routes with honest trade-offs, say which you'd pick and
why, then let them choose. This is the moment to surface cost, lock-in,
maintenance burden and licensing — cheaper here than as a surprise in step 22.
Use a comparison table; it makes the trade-off legible in a way prose doesn't.

Be honest about what you don't know and about the weaknesses of your own
recommendation. A runbook that hides a known fragility is setting up a
frustrating evening.

## 4. Build the runbook

Read `references/runbook-spec.md` for the content contract — the full data
schema, priority levels, dependency notation, verification patterns, gotchas —
before authoring.

**You author data. You never author markup.** The runbook is three layers, and
keeping them apart is what makes the format reusable rather than a
one-off HTML file that has to be rewritten every time:

| Layer | File | Written by |
|---|---|---|
| **Data** | `<name>-rb-data.json` | You, per runbook. This is the whole job. |
| **State** | `<name>-progress.json` | The reader, by ticking boxes. |
| **Presentation** | `assets/runbook-template.html` | Nobody. It is a fixed scaffold. |

The scaffold is deliberately dumb: it reads the two JSON blocks and renders
whatever it finds. Substituting different data into the same scaffold produces a
different runbook with no edits to the HTML, and that property is worth
protecting, because the moment content leaks into the markup the next runbook
starts from a copy-paste of the last one.

So build it with the script rather than by hand:

```bash
python3 scripts/build_runbook.py --data my-rb-data.json --validate-only
python3 scripts/build_runbook.py --data my-rb-data.json \
                                 --state my-progress.json \
                                 --out My-Runbook.html
python3 scripts/build_runbook.py --data my-rb-data.json \
                                 --out My-Runbook.html \
                                 --pdf My-Runbook.pdf --booklet
python3 scripts/verify_runbook.py My-Runbook.html
```

`build_runbook.py` validates the data, injects both JSON blocks into a copy of
the scaffold and sets the title. It refuses to build on a structural error — a
missing `kind` or `do`, a duplicate step id, a `dependsOn` pointing nowhere, a
table row that does not match its header — and warns about things worth a second
look, like a phase with no verification gate or ticks referencing steps that no
longer exist.

When `--pdf` and `--booklet` are passed, `build_runbook.py` uses headless Chromium
to render the page using A4 print geometry, formats high-density print spreads,
preserves physical pen-tickable checkboxes (`[ ]`), and verifies that the document
page count is a multiple of 4 for Adobe/printer booklet mode.

Two rules keep the separation honest:

- **Never hand-edit the JSON inside a built HTML file.** Edit the `.json`,
  rebuild, re-verify. Editing in place is how a data block ends up holding
  something that is not JSON, at which point the page renders nothing at all and
  the source gives no hint why.
- **Never fork the scaffold for one runbook.** If a runbook needs something the
  scaffold cannot render, that is a change to the scaffold and to the spec,
  applied once, for everyone — not a local variant. A per-runbook renderer is
  the failure this structure exists to prevent.

Keep the `.json` files alongside the HTML when you deliver, so the next revision
is a data edit and a rebuild rather than an excavation.

### What the scaffold already does

You do not need to build any of this — it is what the data buys you. Knowing it
is there tells you which fields are worth filling in:

- **A `do` band on every step**, labelled by `kind`, directly under the title and
  above the rationale, with the non-action kinds coloured down. This is the field
  readers depend on most: it answers "am I supposed to act here?" without
  expanding anything. The spec's *Kind and do* section is the contract.
- **Badges**: the `[pX.Y]` id in mono, priority as a word (Mandatory /
  Recommended / Optional, never a bare number), the kind, who may run it
  (`Agent`, or `Human · <reason>`), the environment (`where`), the time
  estimate, and cost where a step incurs one.
- **Dependency chips that recompute on every tick**: `needs p1.4` while that step
  is unticked, `after p1.4` once it is.
- **Verification gates**, per step and per phase, with command and pass condition.
- **Progress**: overall count and percentage, time remaining, and a per-phase bar.
- **Filters**: search, phase, priority, environment, hide-completed, and "only
  steps I must act on".
- **Copy buttons**, a theme toggle, and a print stylesheet that formats compact
  A4 print spreads, keeps pen-tickable square checkboxes visible, prevents orphan
  headers, and expands detail regions.
- **Persistence**, in two layers, because a file on disk cannot rewrite itself:
  every tick writes `{done, updatedAt}` to `localStorage` under
  `runbook:<data.id>`, and on load whichever of that and the embedded `rb-state`
  is newer wins. **Save updated copy** downloads a fresh HTML file with the
  current ticks baked into its `rb-state`, and progress can be exported and
  imported as JSON. A `beforeunload` warning fires when ticks are not yet in a
  saved copy.

Be accurate about the limits when you hand it over: `localStorage` on a
`file://` page works in Chrome, Edge and Firefox but can be blocked in Safari,
and it never travels between machines. The saved copy is the durable, portable
artefact — say so rather than implying automatic sync.

### Delivering it

Send the file with SendUserFile, and write it into a connected folder when the
session has one. Publishing the same page as an Artifact as well is worth
offering when they want a link to open from any machine — declare
`capabilities: {artifact: {}}` there so the published copy persists its own
state — but the file is the deliverable, because it outlives the conversation
and can be kept anywhere.

Set `theme.accent` in the data to a hue that suits the subject — the default
slate-blue is deliberately neutral, and a runbook for a different domain should
not look identical to the last one. Keep it a single accent; the priority and
status colours are already spoken for.

### Who runs each step

Every `action` step declares `executor`: `agent` if an agent can do it and prove
it worked with no human in the loop, `human` (with a `humanReason`) if not. The
spec's *Executor* section is the rule, and `build_runbook.py` enforces the
checkable half of it: an `agent` step must carry a `verify` with `code` and
`expect`, cost nothing, and name no person in `where`. Decide it per step while
you write it, not afterwards, because the answer changes how the step is
written. A step that needs a person partway through is two steps. A step with
no way to check the result by command gets one, or becomes `human`.

When unsure, choose `human`. A wrongly delegated step runs unattended; a wrongly
held one costs a person a minute.

### Sizing

Phases should be things a person can finish in one sitting — roughly 10–45
minutes each. A phase with two steps probably belongs inside its neighbour; a
phase with twenty is really three phases. If the whole runbook exceeds about
four hours, say so plainly and mark a sensible stopping point, because a person
who runs out of energy mid-phase and comes back to a half-verified system is in
a worse position than one who stopped at a gate.

For a genuinely large build, deviating towards longer phases is allowed if you
say why — but every phase must still end somewhere it is safe to stop.

### Estimates

Time and cost estimates are aggregated in the header, so they need to be
defensible rather than decorative. Estimate the *unhurried* time including
reading, and note when a step is mostly waiting (a long download) rather than
attention — people plan differently around the two. For cost, put the amount on
the step that incurs it, and say what the free path costs in effort instead.

Optionally add `claudeTokens` per phase to estimate what working through it
*with* Claude costs — a separate card, because it measures the conversation
rather than the setup, and only applies to phases done in tandem. The spec has
calibration figures. Keep these honest: they are order-of-magnitude, one bad
debugging session dwarfs several clean phases, and a confidently wrong number is
worse than none. Leave it off phases you have no basis for.

## 5. Offer tandem execution

The runbook is a deliverable, not a dismissal. Once it's built, offer to work
through it together — you give the step, they report what happened, you adjust
the next step based on reality rather than assumption. Setup work is where plans
meet friction, and the corrections belong in the runbook, not just in the
conversation.

Let them decide the mode. Some people want the doc and quiet; some want a hand
on every step; most want tandem for the risky phases and solo for the rest.
Suggest tandem for phases where a wrong answer is expensive to undo.

## 5b. Run a phase with subagents

When asked to start, run or continue a phase, do not do its steps yourself. The
steps marked `agent` go to step-runner subagents that work in the background and
tick their own progress, so the phase costs you a few lines of context instead of
every command and its output. You decide, dispatch and report. The runner's own
rules are in `references/step-runner.md`; do not read it, and do not run
`runbook brief`.

1. **Plan.** `runbook plan <name> [phase]`. Each phase prints a `RUN` line (the
   agent steps to hand over, with the exact `steps=` string), a `TICK` line
   (steps with nothing to execute: run the command it prints), and a `STOP` line
   (the step that ends the run, and why: `human (approval)`, `needs p1.4`,
   `unclassified`). `WAIT` means an earlier phase is not finished.
2. **Dispatch.** Start one `runbook-step-runner` subagent per `RUN` line, all at
   once and in the background, each with only the line's
   `runbook=<name> steps=... [gate=...]`. In Claude Code that is the Agent tool
   with `subagent_type: runbook-step-runner`. In agy it is `invoke_subagent`
   with the subagent of that name. Parallel runs are only ever separate phases
   (a parallel phase, or phases whose `dependsOn` are met): steps inside a phase
   are sequential, so one phase is one run. If two phases would change the same
   file or system, send one and wait.
3. **Wait.** Say what you started in one line, then stop. Do not poll or read the
   runners' work.
4. **Report.** Each runner replies with a short `RESULT` block. Pass it on as it
   is. When runs have finished, `runbook build <name>` once (the runners tick
   with `--no-build`), then `runbook plan <name> <phase>` again.
5. **Stop at the human step.** A `STOP human` line is the answer: tell the person
   which step, why it is theirs (`humanReason`), and what to do (`plan --json`
   carries the step's `do`). Do not do it for them and do not skip it. When they
   say it is done, `runbook tick` it and plan again.
6. **`BLOCKED` or `FAIL`.** Show the reason and do not redispatch the same run.
   If the runner hit a gate the author missed, the step is mislabelled: propose
   `executor: human` with a `humanReason` in the data file, and rebuild. If it
   failed verification, that is a real failure: fix the runbook (section 6),
   not just the moment.
7. **`unclassified`.** A step with no `executor` is never dispatched. Offer to
   classify the runbook's steps with the spec's rule, and let the person approve
   them before the data file changes.

Prerequisite: a background subagent cannot ask for permission. Anything the
harness has not already allowed (a shell command, a file write, an MCP tool)
surfaces in the main session as an approval prompt, or is denied. Allow the
commands a phase uses before dispatching, or the runner will stop on its first
blocked tool.

## 6. Keep it current as reality intrudes

When something fails during execution, fix the runbook, not just the moment. A
failure that cost thirty minutes to diagnose belongs in the gotchas table with
its symptom, cause, and fix, so it costs nobody thirty minutes again. If the
cause was a step *you* wrote, correct that step and say so plainly.

To reissue a runbook after changes:

1. **Get their current progress first.** Ask them to hit *Export progress (JSON)*
   and send you that file, or send the HTML they have been ticking — their ticks
   are data you do not have. If you were sent the HTML, pull the state out of its
   `rb-state` block.
2. Edit the `.json`, never the built HTML.
3. Rebuild with their progress as `--state`, and say which ticks you reset and
   why — resetting a tick silently is worse than leaving a stale one. The build
   script warns when the state references steps that no longer exist, which is
   exactly the case worth mentioning to them.

**Append new steps at the end of a phase rather than inserting them mid-phase**
where you can — step ids are how progress is tracked, and renumbering makes
someone's ticks land on the wrong rows. If a step genuinely belongs in the
middle, give it a new id (`p3.4b`) rather than shifting the ones after it.

### Verify before handing it over

```bash
python3 scripts/verify_runbook.py My-Runbook.html
```

This opens the real file in headless Chromium and checks that it renders with a
clean console, that every step in the data reached the DOM exactly once, that
embedded ticks show in the checkboxes and the counter, that ticking updates the
counter and both progress bars, that dependency chips flip, that the filters
narrow correctly, that the save-copy round trip reopens with the same steps and
ticks, and that nothing overflows at 390px.

Run it every time and report the result. A runbook that fails to render is a
worse outcome than a plain markdown list, and the failure is invisible from the
source — the data looks fine right up until the page is blank.

It needs `pip install playwright && python3 -m playwright install chromium`. If
the browser cannot be installed in this environment, say so plainly when handing
over rather than implying the file was checked.

## Where the runbook lives afterwards

The file is the working copy. If the session is attached to a project, also
write a short companion doc there — the decisions and why, the open questions,
and where the file lives — so a future session picks up the reasoning and not
just the checklist. For a long runbook, mirror the step text as markdown in the
project too: it lets a fresh chat answer "I'm stuck on p3.1" by retrieving one
step instead of loading the whole plan.

## Tracking runbooks in a repo: `runbook list`

In a git repo, a runbook's ticks are recorded in `<name>-progress.json` beside its
`<name>-rb-data.json`, in the `rb-state` shape, and committed. A runbook is **in
flight** once that file exists. `scripts/runbook.mjs` reads every runbook in the
repo (and, in a stratadoc repo, every folder under the runbooks layer, checklist
or not) and is on the PATH as `runbook`:

| Command | Does |
|---|---|
| `runbook list` | A board, drawn like `pin list`: columns IN FLIGHT, NOT STARTED, REFERENCE (a doc with no checklist), DONE; `--all` adds RETIRED. Each card shows progress and the current phase, `?` the ready steps of others and `>` your next ready step (whose is "yours": `--me`, `$RUNBOOK_ME`, else the first word of `git config user.name`, matched against the step's `where`). `STALE` means no ticks saved in three days. `--table` and `--json` for scripts. |
| `runbook next <name> [--mine\|--agent\|--human]` | Every ready step (unticked, dependencies met): id, `executor` and `where`, title, what to do. |
| `runbook plan <name> [phase] [--json]` | What can be handed to subagents: per phase, the run of `agent` steps from its first unticked step and the step that stops it. Section 5b. |
| `runbook brief <name> <id>... [--gate <phase>]` | Steps written out in full, for the runner doing them. Not for the main agent. |
| `runbook build <name>` | Rebuilds `<name>.html` from the ticks, after `tick --no-build`. |
| `runbook start <name>` | Creates the progress file, moving the runbook to IN FLIGHT. |
| `runbook tick <name> <id>...` / `untick` | Records ticks and rebuilds `<name>.html` from them, so the file, the page and the board agree. Ticks take a lock, so runners can tick at the same moment; `--no-build` skips the rebuild. |

`/runbook list` means the same: run it and show the board as printed, inside a
code block, without reflowing it. Record a step only when the person said it is
done, or with the evidence the step's own gate asks for. Ticks made in a browser
reach the repo only when the person exports them over the progress file or tells
you which steps are done.

## Reference files

- `references/runbook-spec.md` — the data contract, and the single source of
  truth for it: top-level fields, phase and step schema, `kind` and `do`,
  priority levels, dependencies, verification gates, gotchas, Claude budget.
  Read before authoring.
- `assets/rb-data.sample.json` — a complete, valid runbook exercising every field
  in the contract. Copy its shape; replace its content wholesale.
- `assets/rb-state.sample.json` — the state shape: `{"done":{...},"updatedAt":n}`.
- `assets/runbook-template.html` — the presentation scaffold. Reusable, content
  free, and not to be forked per runbook.
- `references/step-runner.md` — what a step-runner subagent does and says; the
  single source for the Claude and agy agent definitions.
- `scripts/runbook.mjs` — the board and tick helper above (`runbook` on the PATH).
- `scripts/build_runbook.py` — validates data, injects data + state into the
  scaffold, and optionally exports print/booklet PDFs (`--pdf`, `--booklet`).
- `scripts/verify_runbook.py` — opens a built runbook in headless Chromium and
  checks it actually works. Run before handing anything over.