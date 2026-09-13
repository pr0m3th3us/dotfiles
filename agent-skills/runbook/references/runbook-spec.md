# Runbook content contract

This file is the single source of truth for the **data** layer. It describes the
JSON you write into an `rb-data.json` file. The scaffold
(`assets/runbook-template.html`) does the layout, the aggregation, the
dependency chips and the state persistence; you supply only the content.

Three files, three jobs, and they stay separate:

| Layer | File | Who writes it |
|---|---|---|
| **Data** | `<name>-rb-data.json` | You, per runbook. This document is its contract. |
| **State** | `<name>-progress.json` | The reader, by ticking boxes. `{"done":{"p1.2":true},"updatedAt":0}` |
| **Presentation** | `assets/runbook-template.html` | Nobody, per runbook. It is a reusable scaffold. |

They are combined by `scripts/build_runbook.py`, which validates the data,
injects both JSON blocks into a copy of the scaffold, and writes the deliverable:

```bash
python3 scripts/build_runbook.py --data my-rb-data.json \
                                 --state my-progress.json \
                                 --out My-Runbook.html
```

**Never hand-edit the JSON blocks inside a built HTML file.** That is how the
two layers get welded back together, and it is how a data block ends up holding
something that is not JSON — at which point the page renders nothing at all.
Edit the `.json`, rebuild, re-verify.

Anything in this contract that the scaffold does not render is a bug in the
scaffold, not a licence to add markup to a runbook.

## Contents

- [Top level](#top-level)
- [Phases](#phases)
- [Steps](#steps)
- [Kind and do](#kind-and-do)
- [Priority levels](#priority-levels)
- [Dependencies and parallelism](#dependencies-and-parallelism)
- [Verification](#verification)
- [Gotchas](#gotchas)
- [Writing the prose](#writing-the-prose)
- [Worked example](#worked-example)

---

## Top level

```json
{
  "id": "wsl2-dev-env",
  "title": "WSL2 Dev Runbook",
  "subject": "Windows 11 → Ubuntu on WSL2",
  "summary": "One or two sentences: what this builds and how to work through it.",
  "currency": "USD",
  "theme": { "accent": "#7a2f6e" },
  "chips": [{ "label": "Distro", "value": "Ubuntu 24.04 LTS" }],
  "leads": [],
  "phases": [],
  "completion": null,
  "gotchas": [],
  "outOfScope": null,
  "footer": "Ubuntu 24.04 LTS on WSL2 · drafted 25 August 2026."
}
```

`id` keys the local progress store — make it stable and specific, because
changing it orphans someone's ticks. `chips` are the at-a-glance decisions
(distro, engine, editor); keep to six or fewer, and write each as
`{"label": …, "value": …}`. `currency` drives cost formatting and must be one of
`USD`, `INR`, `EUR`, `GBP`, `AUD`, `CAD`, `JPY` — anything else renders amounts
with no symbol. `theme.accent` is a single hex colour; the priority and status
colours are already spoken for, so do not try to theme those.

The scaffold appends its own chips for step count, action count, total time and
total spend, so do not duplicate those in `chips`.

`leads` are the things someone must understand *before* step one — a correction
to a false assumption they arrived with, or the one rule the whole runbook hangs
on. Two at most; this is not an introduction, it is a short list of things that
would otherwise cause an expensive mistake in phase 3.

```json
"leads": [{
  "title": "Two decisions worth knowing before you start",
  "body": ["<strong>OrbStack has no Windows build.</strong> …"],
  "items": []
}]
```

Prose fields accept inline HTML (`<strong>`, `<em>`, `<code class="inl">`,
`<a>`). Titles and labels are escaped — write those as plain text.

## Phases

```json
{
  "id": "p2",
  "num": "02",
  "title": "Tune the VM",
  "titleText": "Tune the VM",
  "intent": "One line on what this phase achieves and why it comes here.",
  "parallel": false,
  "dependsOn": ["p1"],
  "claudeTokens": 25000,
  "claudeMode": "tandem",
  "steps": [],
  "verification": { "title": "…", "code": "…", "expect": "…" }
}
```

Number from `00`, and use `00` for pre-flight — the checks that establish
whether the work can proceed at all. A pre-flight phase is not optional
ceremony: hardware virtualisation disabled in the BIOS, an unsupported OS
version, or a full disk will each waste an hour if discovered in phase 4.

`titleText` is the plain-text form used in the sidebar; supply it when `title`
contains markup.

`parallel: true` means the phase can be worked at the same time as others rather
than strictly after the previous one — the renderer labels it so the person can
plan. Steps *within* a phase are always sequential; that is the contract, and it
is why cross-phase dependencies are declared per step.

## Steps

```json
{
  "id": "p2.1",
  "title": "Write <code class=\"inl\">.wslconfig</code>",
  "kind": "action",
  "do": "Create the file below and paste the four settings in. Restart WSL afterwards.",
  "priority": 3,
  "minutes": 5,
  "where": "Windows",
  "cost": { "amount": 0, "note": "" },
  "dependsOn": ["p1.3"],
  "why": "Short: what this does and why it matters here.",
  "commands": [{ "caption": "C:\\Users\\<you>\\.wslconfig", "code": "…" }],
  "notes": ["Follow-up detail, caveats, what a good result looks like."],
  "callouts": [{ "kind": "warn", "title": "Trade-off", "body": ["…"] }],
  "table": { "head": ["Setting", "What it buys you"], "rows": [["…", "…"]] },
  "verify": { "code": "…", "expect": "…" }
}
```

`id`, `title`, `kind` and `do` are required on every step; the build script
refuses to build without them. Everything else is optional.

Ids are `p<phase>.<n>`, and they are the progress keys — stable ids matter more
than tidy ones. Use `p3.4b` for something inserted later rather than renumbering.

A `table`'s rows must each have as many cells as `head`, or the build fails —
a ragged table is the kind of thing nobody notices until a reader is staring at
a shifted column mid-deploy.

## Kind and do

These two are the ones readers depend on most, which is why they are required.
People routinely reach a context or record step and cannot tell whether they are
supposed to *act*. Every step therefore declares both.

`kind` is one of:

| `kind` | Means | Band reads |
|---|---|---|
| `action` | They must execute something | Do this |
| `decide` | A judgement call they must make and write down | Decide this |
| `info` | Context only, nothing to execute | For reference only |
| `done` | Already completed, recorded so the picture is whole | Nothing to do |
| `blocked` | Real work that cannot start until something external exists | Blocked — nothing to do yet |

`do` is one or two sentences in the imperative naming exactly what to do — or,
for the non-action kinds, stating plainly that there is nothing to execute and
why the step is here at all. The scaffold renders it as a labelled band directly
under the title, *above* the rationale, and colours the non-action kinds down
rather than up. Everything else — `why`, commands, notes, tables, callouts,
`verify` — sits in a collapsible region below, so the band and the badges must
carry the step on their own.

The `only steps I must act on` filter keeps `action` and `decide`. A runbook
where everything is `action` gives that filter nothing to do, which is a sign
the `info` and `done` steps were mislabelled rather than that none exist.

`where` is the execution context badge — `Windows`, `Ubuntu`, `PowerShell`,
`Docker Desktop`, `Google Ads`, `Browser`. It answers "where am I typing this?",
which is the single most common source of confusion in cross-platform work.

`why` earns its place: a step someone understands is a step they can adapt when
their situation differs slightly, and a step they can debug when it fails. One
or two sentences. Skip it only when the title is self-evidently complete.

`cost.amount` is a number in the runbook's currency; `cost.note` qualifies it
("/month", "one-off", "free tier then $X"). Omit `cost` entirely for free steps
— zero is the default and does not need saying.

`callouts` take `kind` of `warn` (a trap, a trade-off, a thing that will bite),
`info` (context that explains a choice), or `good` (a confirmation, a shortcut
worth knowing).

## Priority levels

| Level | Renders as | Means |
|---|---|---|
| `3` | Mandatory (red) | Later steps genuinely depend on it. Skipping breaks something downstream. |
| `2` | Recommended (orange) | Real value, but the runbook completes without it. Quality-of-life, hardening, ergonomics. |
| `1` | Optional (yellow) | Nice to have, personal taste, or only relevant to some setups. |

The header aggregates mandatory-only time separately, so someone short on time
can see the minimum viable path. This only works if you are disciplined: mark 3
when it is genuinely load-bearing, not when it is merely a good idea. An
all-mandatory runbook communicates nothing.

## Dependencies and parallelism

Within a phase, order is the dependency; declare nothing. The build script warns
about a same-phase `dependsOn` because it adds a chip that says what the reading
order already said.

Across phases, declare it: `"dependsOn": ["p2.4"]` on the dependent step. The
scaffold renders a live chip reading `needs p2.4` while that step is unticked,
flipping to `after p2.4` once it is, and outlines the step until then. It does
*not* disable the checkbox — someone working deliberately out of order needs to
be told, not stopped. A `dependsOn` pointing at an id that does not exist is a
build error, because that chip would never clear.

Declare a dependency only where one genuinely exists. Over-declaring serialises
work that could have run in parallel, which is the whole reason for tracking
this. Phase-level `dependsOn` expresses the coarse ordering; step-level
`dependsOn` expresses the specific "this one line needs that one thing".

## Verification

Two levels, and both matter more than they look.

**Step-level `verify`** — for steps where success is not self-evident. A
command plus what a pass looks like. Skip it when the step's own output is the
proof.

**Phase-level `verification`** — the gate. Before moving on, confirm this phase
actually worked. This is the highest-value part of the whole format: without
gates, a broken phase 2 is discovered somewhere in phase 6, and the debugging
starts from the wrong place.

```json
"verification": {
  "title": "Confirm the toolchain resolves before building anything on it.",
  "code": "java -version && mvn -v && node -v && python -V",
  "expect": "Four version strings. If <code class=\"inl\">JAVA_HOME</code> is empty, mise didn't activate — check your shell rc."
}
```

Write `expect` as what a *pass* looks like, and where useful what the common
failure looks like and what it means. "It should work" is not a gate.

Not every phase can be verified by a command — a phase about creating accounts
or configuring a web console is verified by looking at a screen. Say what to
look at and what a correct state looks like. A human-verifiable gate is still a
gate.

**`completion`** is the same shape, for the whole runbook: the one check that
says the goal was actually achieved. Where the domain allows, make it a single
script that prints every relevant version and status, so the answer is a glance
rather than an audit.

## Estimating the Claude side

Optional, and separate from the time and money budget because it measures
something different: the cost of the *conversation*, not the setup. It only
applies if the person works through the runbook in tandem; steps they run solo
cost nothing.

Put `claudeTokens` on each phase you expect to need help with, plus an optional
`claudeMode` describing how you'd expect to work it ("tandem", "solo, ask if
stuck", "solo"). Phases with no `claudeTokens` are left out of the card, and if
no phase declares one the card doesn't render at all.

```json
"claudeBudget": {
  "title": "Working through this with Claude",
  "note": "Override the default caveat here if the runbook needs a specific one.",
  "ratePerMTok": 1200
}
```

`ratePerMTok` is optional and expressed in the runbook's `currency`; supply it
only if the person has given you a rate they actually pay. Without it the card
shows tokens alone, which is the honest default.

Rough calibration, per phase, for tandem work:

| Interaction | Order of magnitude |
|---|---|
| A phase you mostly narrate — Claude gives steps, person confirms | 10–25k |
| A phase with real back-and-forth — pasted output, small corrections | 25–60k |
| A phase where something breaks and gets debugged | 60–200k+ |

Be honest in the note that these are order-of-magnitude figures. A single
stubborn failure can cost more than several clean phases, and pretending
otherwise makes the number worse than useless — it makes it misleading. If you
have no basis for an estimate in an unfamiliar domain, leave `claudeTokens` off
those phases rather than inventing a figure.

## Gotchas

```json
"gotchas": [
  { "symptom": "Everything is slow; installs take minutes",
    "cause": "Repo lives on the mounted Windows filesystem",
    "fix": "Move it to the Linux filesystem. Non-negotiable." }
]
```

Symptom first, because that is what someone has in hand when they come looking.
Seed it from what you know of the domain's real failure modes, and **grow it
during execution** — every problem hit while working through the runbook belongs
here afterwards, phrased as the symptom the person actually saw.

`outOfScope` is the companion: what deliberately stays outside this runbook and
why. It prevents the well-meaning follow-up question and stops scope creep from
looking like an oversight. It takes `title`, `body` (an array of paragraphs) and
`items` (an array of list entries).

```json
"outOfScope": {
  "title": "Deliberately not in this runbook",
  "body": ["Why these are excluded and when to come back to them."],
  "items": ["Monitoring — needs a running service to watch first."]
}
```

## Writing the prose

- **Name the platform in the step, not just the phase.** People jump into the
  middle of a runbook.
- **One action per step.** If the title needs an "and", it is two steps.
- **Say what a good result looks like.** A step that ends with output nobody can
  interpret has not finished.
- **Explain trade-offs at the point of choosing**, not in a preamble nobody
  rereads.
- **Be honest about fragility.** If a step is known to be flaky, say so and say
  what to do about it. The person will find out either way; the only variable is
  whether they find out from you.
- **Write the commands so they can be pasted.** Multi-line blocks should run as
  a unit; if a command needs editing first, say exactly what to change.

## Worked example

A single step carrying most of the features:

```json
{
  "id": "p5.1",
  "title": "Get a current git — optional",
  "kind": "action",
  "do": "Add the git-core PPA and upgrade git. If the PPA fights you, keep the stock version and move on.",
  "priority": 1,
  "minutes": 5,
  "where": "Ubuntu",
  "why": "The distro's git lags upstream by a year or two. Nice to have, not load-bearing — if it fights you, take the stock version and move on.",
  "commands": [{ "code": "sudo add-apt-repository -y ppa:git-core/ppa\nsudo apt update && sudo apt install -y git" }],
  "callouts": [{
    "kind": "warn",
    "title": "If this times out",
    "body": ["<code class=\"inl\">add-apt-repository</code> queries a remote API before writing anything, so a timeout here means that one host is unreachable — not that apt is broken."]
  }],
  "verify": { "code": "git --version", "expect": "2.43 or newer." }
}
```

A complete, structurally valid runbook exercising every field in this contract
lives in `assets/rb-data.sample.json`, with matching ticks in
`assets/rb-state.sample.json`. Read it when the shape of something is unclear,
and copy from it rather than inventing a variant — but replace the content
wholesale. It is a shape to fill, not a runbook to adapt.

## Build and verify

```bash
# 1. check the data before wiring it up
python3 scripts/build_runbook.py --data my-rb-data.json --validate-only

# 2. build the deliverable
python3 scripts/build_runbook.py --data my-rb-data.json \
                                 --state my-progress.json \
                                 --out My-Runbook.html

# 3. prove it actually works in a browser
python3 scripts/verify_runbook.py My-Runbook.html
```

`verify_runbook.py` opens the real file in headless Chromium and checks that it
renders, that the console is clean, that every step in the data reached the DOM
exactly once, that embedded ticks show up in the checkboxes and the counter,
that ticking updates the counter and both progress bars, that dependency chips
flip, that the filters narrow correctly, that the save-copy round trip reopens
with the same steps and the same ticks, and that nothing overflows at 390px.

Run it on every runbook before handing it over. A runbook that fails to render
is a worse outcome than a plain markdown list, and the failure is invisible from
the source.
