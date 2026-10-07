---
name: visual
description: "Make an illustrated page (a 'visual') that explains one topic to a reader who was not in the conversation: charts, block diagrams, flows, tables and illustrations with plain-English text, built from a data JSON into one file, printed to an A4 PDF and checked page by page, then listed in the repo's visuals index. Use when the user types /visual, or asks for a visual, an explainer, an illustrated page, a one-pager, a printable summary or a PDF explainer of something discussed. Also /visual list (every visual knowledge hub with what each shows) and /visual update <slug>."
---

# visual

A visual is one printable page set (usually one to five A4 pages) that explains **one topic** to a
reader with no context: what it is, how it works, what was decided and why. It is a picture first,
with short text around the pictures. A repo's visuals live under one folder (`docs/visuals/` if
`docs/` exists, else `visuals/`) with an index table in its `README.md`. Each visual has a folder of
its own name, as runbooks do:

```text
docs/visuals/<slug>/
  <slug>.pdf         the page (or <slug>.html when the PDF could not be made clean)
  <slug>.vis.json    the content; the only file anyone edits
  README.md          what the page is about, section by section; regenerated on publish
```

**You author data, never markup.** Three layers, as in the runbook skill:

| Layer | File | Written by |
| --- | --- | --- |
| Content | `<slug>.vis.json` (contract: `references/schema.md`) | You, per visual |
| Presentation | `assets/visual-template.html` | Nobody; fixed for every visual |
| Build, check, publish, list | `scripts/visual.py` | Nobody; run it |

Do not read the template or the script: the schema and the commands below are all you need. If a
visual needs something the scaffold cannot draw, use an `svg` block, or propose a scaffold change
(made once, for every visual). Never hand-edit a built HTML or PDF.

`V` below means `python3 <this skill's folder>/scripts/visual.py`. `W` is a work folder outside the
repo: the session's scratchpad if there is one, else `/tmp/visual/<slug>`.

## Commands

| Command | Does |
| --- | --- |
| `/visual [topic hint] [--html]` | A new visual. PDF by default; `--html` skips the PDF and saves one HTML file. |
| `/visual update <slug> [what changed]` | Edit `<slug>.vis.json`, rebuild, republish in the same format. |
| `/visual list [--all]` | Run `V list` (`--all`: `V list --projects ~/projects`). Show the output as printed, in a code block. |

## Rules for every visual

1. **One topic.** If the conversation covers several, pick the most likely one and name it in the
   first line of your reply, so a wrong guess is caught at once. Ask only if nothing points to a topic.
2. **A cold reader.** Every section must make sense to someone who never saw the conversation. No
   "as discussed", no labels invented in the chat, no unexplained short forms.
3. **Plain English.** Short sentences (under 25 words), common words, active voice. Spell out a short
   form the first time, or put it in a `glossary` block.
4. **No invented numbers.** Every number comes from a source you read, or carries `example: true`
   (drawn with an EXAMPLE badge). An unmeasured value is `TBD`, not a guess.
5. **The data file is the source.** It stays in the visual's folder so the next change is a data edit.
   The repo's Markdown docs stay the source of truth for what the page says; list them in `sources`.
6. **No commit or push.** Leave files in the working tree.

## `/visual [topic]`: the steps

### 1. Read the conversation

Name the topic in one phrase and pick a slug. Note what the conversation already settled: decisions,
numbers, names, open questions. Run `V list` to see if a visual on this topic exists; if one does,
this is an update to it, not a new page (say so and switch to `/visual update`).

### 2. Gather the documents

Read what the page will state, and no more. Start from files the conversation named. In a repo with
`stratadoc.yaml`, use the docs map (`docs/README.md`), the nodes on the topic, and one level of their
`upstream`; take registered values from `docs/00-facts/facts.json`. Search (`grep -ril <term> docs/`)
for terms the topic turns on. Prefer the newest decision: an accepted ADR beats a proposal; a later
run-history entry beats an earlier one. Every file you rely on goes in `sources`.

### 3. Settle what the page must contain

Write down, for yourself: who reads it, the one question it answers, and what the reader should
know or be able to decide after reading. Fill gaps from the documents. If something the page needs
is in neither the conversation nor the documents, and a wrong guess would mislead, ask once (each
question with your default answer); otherwise write `TBD` and carry on.

### 4. Plan the sections and pictures

Three to seven sections, in the order a reader needs them (usually: what it is, how it works, the
rules or numbers, what happens next). For each: a title, the **takeaway** (one sentence the reader
leaves with), and the blocks, at least one of them a picture. Use the "Picking the picture" table in
`references/schema.md`. Show the plan in chat in at most twelve lines, as your default, and go on
building unless the user asked to approve the plan first.

### 5. Write the data

Read `references/schema.md` once. Write `W/<slug>.vis.json` (for an update, edit the file in the
visual's folder). Keep text short: a section is mostly its pictures. Set `updated`, `updated_by`.
Run `V validate W/<slug>.vis.json` and fix every error.

### 6. Build and check: at most five attempts

```bash
V build W/<slug>.vis.json --work W --attempt N        # add --no-pdf for an HTML-only visual
```

It writes `W/<slug>.html`, the PDF, one PNG per page in `W/pages/`, the page text in `W/<slug>.txt`,
and prints a report: **MUST FIX** (render errors, anything wider than the page, text or borders in the
margin, labels wider than their box, blank pages), **JUDGE** (big gaps, a heading stranded at the
foot of a page, a near-empty last page, missing sources, numbers without a source) and **LANGUAGE**
(long sentences, unexplained short forms, repeated words, odd spellings when a dictionary exists).

Each attempt:

1. Fix every MUST FIX item in the data. Fix a JUDGE item unless you can say why it is fine.
2. **Look at every page the report lists as changed** (read the PNGs). Check margins, alignment,
   overlaps, cut-off labels, broken borders, awkward page breaks, pictures that do not match the text.
3. On the first attempt, and after any text change, **read `W/<slug>.txt` as the cold reader**: does
   each section make sense alone; is the English simple; any spelling mistakes; any short form not
   spelled out; does each takeaway follow from its section.
4. If anything needs fixing, edit the data and build again with `--attempt N+1`. Fixes for layout:
   shorten labels, drop a table column, split a big block in two, move a block to another section,
   set `break_before` on a section. Never fix the PDF itself.

Stop as soon as an attempt is clean on all three counts. **Pass** means no MUST FIX items, no JUDGE
items you could not justify, and your own page review and read-through found nothing. After the fifth
failed attempt, stop and save the HTML instead (step 7), and say what still fails.

### 7. Publish

```bash
V publish W/<slug>.vis.json --format pdf     # or --format html (asked for, or the PDF failed)
```

Run it from inside the repo the visual belongs to: the visuals folder is found from the current
directory, not from where the JSON sits.

It copies the output into `<visuals>/<slug>/` (`--dir` sets `<visuals>`), keeps `<slug>.vis.json` there,
writes the folder's `README.md` from the data, deletes the other format's file (the HTML is transient
once the PDF passes), and adds or updates the visual's row in `<visuals>/README.md`. In a repo with its own doc checks (for
example `npm run lint:docs` in a stratadoc repo), run them, since the index is a doc.

If the page is also to be shared as a claude.ai page: publish the HTML from `W/<slug>.html`, put the
link in `shared_link`, and run `V publish` again so the index carries it.

### 8. Reply

A few lines: the topic, the saved path, pages and attempts used, the defaults you took, anything you
could not verify or left `TBD`.

## `/visual update <slug>`

Read `<visuals>/<slug>/<slug>.vis.json` and the sources that changed. Edit the data, set `updated`,
then steps 6 to 8 with the format the visual already has. A visual with no `.vis.json` (hand-made
HTML) is converted: read the HTML once, write its content as a `.vis.json`, then build and publish.
Publishing a PDF replaces the hand-made HTML file and its hand-written README; say so in the reply
(git keeps the old copy).
