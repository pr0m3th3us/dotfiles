# visual/1: the data contract

A visual is one JSON file, `<slug>.vis.json`. The scaffold draws whatever it holds; `visual.py validate`
enforces this contract. `assets/sample.vis.json` uses every block type: copy its shape, replace its content.

## Top level

| Field | Required | What it is |
| --- | --- | --- |
| `schema` | yes | Always `"visual/1"`. |
| `slug` | yes | Kebab-case name of the visual's folder and files: `<slug>/<slug>.pdf`, `<slug>/<slug>.vis.json`. Names the topic, not the format. |
| `title` | yes | The page title, and the link text in the index. Two to six words. |
| `shows` | yes | One line for the index's Shows column: the topics a reader finds here. Under 220 characters. |
| `sections` | yes | Three to seven sections (nine is the hard ceiling). |
| `kicker` | no | Small line above the title: scope or audience (`MAAC Ameerpet · Google Ads`). |
| `status` | no | Pill under the title, for a page about something not yet final (`PROPOSED · awaiting approval`). |
| `lede` | no | One to three sentences, or a list of paragraphs: what the page is and why it matters. |
| `sources` | no, warned | Repo paths the page draws on. Rendered at the foot; basenames go in the index. |
| `draws_on` | no | Override for the index's Draws on cell when basenames read badly (`ADR-0012, ADR-0013`). |
| `updated`, `updated_by` | no | `YYYY-MM-DD`, and `claude`, `agy`, `fable` or `pramit`. |
| `shared_link` | no | The claude.ai link if the page is also published there; goes in the index. |
| `theme.accent` | no | One `#rrggbb` accent that suits the subject. Status colours are fixed. |
| `allow_terms` | no | Short forms the reader already knows, so the language check stops flagging them. |
| `number_sections` | no | `false` hides the section numbers. |
| `footer` | no | One extra line at the foot. |

## Section

`{ "id", "title", "takeaway", "blocks": [...], "break_before" }`

- `title`: what the section is about, as a reader would say it (`How a campaign goes live`).
- `takeaway`: the one sentence the reader should leave with. Drawn as a bar under the heading. Write
  it as a statement, not a topic (`The den has its own budget, so it never goes dark.`).
- `blocks`: at least one; one picture or more per section, with short text around it.
- `break_before: true` starts the section on a new printed page. Use only to fix a bad break.

## Inline text

Every text field takes `**bold**`, `*italic*`, `` `code` `` and `[label](url)`. No HTML. A text field
may be a string or a list of strings (paragraphs).

## Blocks

Every block has `type`. Any block may carry `source` (shown as "Source: …" under it).
`tone` is one of `accent`, `good`, `warn`, `amber`, `violet`, `muted`.

| type | Fields | Use it to |
| --- | --- | --- |
| `text` | `text` | Say what a picture cannot. Keep it to two short paragraphs. |
| `list` | `items`, `ordered` | A few parallel points. More than seven: use cards or a table. |
| `callout` | `text`, `title`, `kind` (`note` `warn` `good` `example`), `tone` | One thing the reader must not miss. |
| `cards` | `items: [{tag, title, text, tone}]`, `columns` | Rules, principles, or parts with a short explanation each. |
| `stats` | `items: [{value, label, note, tone, example}]`, `source` | Two to four headline numbers. |
| `flow` | `steps: [{title, who, text, mark}]`, `direction` (`row`, `column`) | Steps in order. `mark`: `gate` (a check or approval), `done` (the end state), `stop`. Steps are numbered for you. |
| `table` | `columns`, `rows` (lists of cells), `numeric` (column indexes), `key_column`, `title`, `caption` | Exact values to look up. Six columns at most for A4. |
| `chart` | `chart` (`bar` `column` `line` `stacked`), `labels`, `series: [{name, values}]`, `title`, `unit`, `prefix`, `max`, `percent`, `caption`, `example` | Compare amounts (`bar` for long labels or many items, `column` for up to 12 short ones), change over time (`line`), parts of a whole (`stacked`, 100% unless `percent: false`). Five series at most. |
| `diagram` | `nodes: [{id, label, sub, col, row, tone, filled}]`, `edges: [{from, to, label, dashed, both}]`, `groups: [{label, nodes, tone}]`, `title`, `caption`, `row_height` | Parts and how they connect. You place nodes on a grid (col and row from 1); edges are straight arrows. Four columns at most; keep labels under 28 characters and `sub` under 34. |
| `tree` | `root: [{label, note, mono, children}]` | What contains what: a file's shape, an account structure. |
| `timeline` | `items: [{when, title, text, tone}]` | Dated events or a sequence in time. |
| `compare` | `options: [{name, text, pros, cons, verdict, pick}]` | Options side by side; `pick: true` marks the recommendation. |
| `glossary` | `items: [{term, meaning}]` | Terms a cold reader needs. Also stops the language check flagging them. |
| `split` | `left: [blocks]`, `right: [blocks]` | Two short blocks side by side (a list beside a chart). Not for long content. |
| `svg` | `svg`, `alt`, `title`, `caption`, `example` | An illustration no other block can draw (rings, a map, a gauge). Must have a `viewBox`, best 680 wide. No scripts. Colour with the scaffold's classes: fills `f-accent f-good f-warn f-amber f-violet f-soft f-panel`, strokes `s-accent s-good s-warn s-amber s-violet s-line s-muted`, plus `light` (15% fill) and `none`; `<text class="sm">` for small muted text. Never hard-code a colour. |

## Numbers

`chart` and `stats` must carry `source` or `example: true`. An `example` number is drawn with an
**EXAMPLE** badge. A number nobody has measured is not a chart at all: write `TBD` in a table or text
and say when it will be measured.

## Picking the picture

| The reader needs to see | Block |
| --- | --- |
| an order of steps, who does each, where it stops for a check | `flow` |
| parts and the arrows between them | `diagram` |
| how big things are against each other | `chart` bar or column |
| a trend | `chart` line |
| shares of a whole | `chart` stacked |
| a few numbers that matter most | `stats` |
| a choice, with a recommendation | `compare` |
| exact values to look up | `table` |
| a nested structure | `tree` |
| what happened when | `timeline` |
| a spatial or physical idea (zones, layers, a funnel) | `svg` |
