---
name: visual
description: "Make an infographic style illustrated editorial explainer grounded in factual data: a one-file HTML page (and printable A4 PDF) of hero illustrations, annotated cutaways, 3D exploded views, scroll stories and charts, for a reader starting from nothing. Use when the user types /visual, or asks for a visual, explainer, infographic, illustrated page, brochure or printable summary of something. Also /visual list (every visual with what it shows) and /visual update <slug>."
---

# visual

Every visual is an **infographic style illustrated editorial explainer grounded in factual data**. Think of a
printed course brochure crossed with DK's *How Technology Works*: someone with near-zero memory of the topic
picks it up, wants to keep reading, and leaves with a clear picture in their mind. Say that target verbatim in
your plan.

Four goals rank equally. Each is a gate in step 8.

1. **Render fidelity.** Sharp text and fonts; nothing clipped, overlapping or broken at any size.
2. **Visual richness.** Subject-specific illustration with light, shade, depth and detail, on the level of DK.
3. **Communication.** The pieces come together into one clear picture in the reader's mind.
4. **Grounded in fact.** True to its sources in substance. Simplify, round and use analogy freely, and label
   what is drawn to explain. Grounded is the bar; exhaustive precision is not.

A visual lives in `docs/visuals/<slug>/` (`visuals/` if there is no `docs/`), with an index in the folder's `README.md`:

```text
<slug>.html       the page: one file, works offline. The default.
<slug>.pdf        the A4 version, when asked for (or use the page's Print button)
<slug>.vis.json   the content, the only prose anyone edits
art/              the illustrations and the script that drew them
README.md         regenerated on publish
```

You author data and art, never page markup. `assets/visual-template.html` draws every visual. `scripts/visual.py`
builds, checks and publishes; run it as `V` (`python3 <this skill's folder>/scripts/visual.py`). `W` is a work
folder outside the repo: the session's scratchpad if there is one, else `/tmp/visual/<slug>`. A capability the
template lacks becomes a template change, made once for every visual.

## Commands

| Command | Does |
| --- | --- |
| `/visual [topic hint] [--pdf]` | A new visual. HTML by default; `--pdf` also publishes the A4 PDF. |
| `/visual update <slug> [what changed]` | Edit the data or art, rebuild, republish in the same formats. |
| `/visual list [--all]` | Run `V list` (`--all`: `V list --projects ~/projects`). Show the output as printed, in a code block. |

## House rules

| Area | Default |
| --- | --- |
| Reading experience | The main conclusion in 30 seconds; the reasoning in a few minutes. |
| Page purpose | One main question and one clear takeaway per spread. |
| Text budget | 120–180 words per main A4 page; review anything over 220. Appendices can be denser. |
| Typography | A4 body 11.5–12.5 pt, captions at least 10 pt. Add pages before shrinking text. |
| Explanatory visuals | One substantial focal visual per main spread, unless something simpler truly works better. |
| Visual allocation | Roughly 40–60% of the main content area in meaningful visuals. Text in decorative cards counts for nothing. |
| Paragraphs | Short. The first useful visual comes before any long introduction. |
| Variety | Alternate annotated illustrations, comparisons, process views and worked examples. |
| Consistency | One type scale, spacing system, palette, stroke weight and illustration treatment. |
| Evidence | Separate observed, reported, inferred and unknown with status badges. Give usable source links. |
| Honesty | No invented chart data or "confidence percentages". No illustration presented as a real screenshot. |
| Export | Selectable text, vector art where possible, every rendered page inspected. |

Treat the numbers as signals. Record a justified exception and move on; never pad a graphic to hit a quota.

## `/visual [topic]`: the steps

### 1. Name the topic

Pick one topic and a slug, and name them in the first line of your reply. Run `V list`; if a visual on this topic exists, this is an update.

### 2. Gather the facts

Read what the page will state, starting from files the conversation named. In a repo with `stratadoc.yaml`, use
`docs/README.md`, the nodes on the topic and `docs/00-facts/facts.json`. Prefer the newest decision. Every file you
rely on goes in `sources`, with a readable title. Done when you can state the conclusion and each number from a
source you read; an unknown that matters is written as `TBD` beside the claim it affects.

### 3. Find the big idea

Decide who reads it, the one question it answers, and its 30-second conclusion. Then find the **big idea**: one
concrete visual metaphor that carries the conclusion and titles the page (a machine with missing parts; a judging
panel with empty seats). Done when the title and hero picture would make a stranger curious.

### 4. Direct the art

Read [references/art-direction.md](references/art-direction.md). Choose a preset, a reference to draw from, and the
scene sequence. Done when you can name what each spread borrows and from whom.

### 5. Storyboard

Plan three to seven spreads. For each: question, headline (the takeaway as a statement), layout, scene, focal art,
and this sentence: "This visual helps the reader understand ___ by showing ___." Vary layouts and scenes. Show the
plan in at most twelve lines and go on building unless the user asked to approve it first.

### 6. Draw the art

Draw the hardest illustration first and look at it before drawing the rest. Compose scenes in a short script,
`W/art/draw.py`, using `assets/art_kit.py` and saving to `W/art/`; it travels with the visual for the next update. Done when each focal image passes the removal test: take it away and
understanding suffers.

### 7. Write the data

Read [references/schema.md](references/schema.md). Write `W/<slug>.vis.json`, with `updated` and `updated_by`. Keep a
short `claims` list for the headline numbers and any contested claim: claim, source, status. Let pictures and notes
carry the explanation. Run `V validate W/<slug>.vis.json` until it has no errors.

### 8. Build and look: at most five attempts

```bash
V build W/<slug>.vis.json --work W --attempt N
```

It writes the HTML and PDF, `W/shots/` (each spread at desktop, tablet and phone, plus `live-*` frames as a reader
scrolls), `W/pages/` (each PDF page), `W/<slug>.txt` (all visible text, including text in the art), a table of words
and graphics per A4 page, and a report: **MUST FIX** (render errors, overlaps, clipping, near-invisible text, spills,
sideways scroll), **JUDGE** (small type, low contrast, budgets, repetition, sparse art) and **LANGUAGE**.

Each attempt: fix every MUST FIX; fix each JUDGE item or say why it is fine; look at every shot and page as an art
director; read `W/<slug>.txt` as the cold reader; rebuild if anything needs fixing. Repair the art, data or template
and rebuild. Pass all four gates:

- **Fidelity:** no MUST FIX. At desktop, phone and A4, nothing clipped, crowded or misaligned, and animations read well in the `live-*` frames.
- **Richness:** the shots look like a published explainer, with recognisable subject-specific art. A wall of cards or plain boxes fails.
- **Communication:** the scan test passes: headlines, pictures and captions alone recover the argument. Notes sit beside what they describe.
- **Grounded:** nothing misleads, and drawn material is labelled `illustrative`.

After a fifth failed attempt, publish with `--accept-failures` and say what still fails.

### 9. Independent review: one reviewer, one pass

Hand one reviewer subagent on a different model (the Agent tool, with `model` set) the `W/shots/` images, `W/pages/`,
`W/<slug>.txt`, the `sources` files, a one-line topic and the four gates. It rewrites nothing and returns located
fixes under **FIDELITY**, **RICHNESS**, **COMMUNICATION** and **MISLEADING** (a claim the sources contradict, or a reader taking
away something false; simplification is fine). Fix what you agree with and rebuild once. In the reply, say what it
found and what you left. With no subagent tool, say so.

### 10. Publish

```bash
V publish W/<slug>.vis.json --work W                 # or --format both for HTML and A4 PDF
```

Run it from inside the repo the visual belongs to. It refuses a build whose data, art or template has since changed,
copies the checked output, data and art into the folder, deletes output from an earlier build, and updates the
index. Run the repo's own doc checks if it has them (`npm run check`). Leave files uncommitted for the user.

For a claude.ai page too: publish `W/<slug>.html`, put the link in `shared_link`, and run `V publish` again.

### 11. Reply

A few lines: the big idea, the saved path, spreads and attempts, what the reviewer found, your defaults, and anything `TBD` or unverified.

## `/visual update <slug>`

Read `<visuals>/<slug>/<slug>.vis.json` and the sources that changed. Edit data or art in place, set `updated`, then
steps 8 to 11, building to `W` with the JSON where it sits. A `visual/1` file or hand-made HTML gets re-storyboarded
as `visual/2` from step 3; say so in the reply (git keeps the old copy).
