# visual/2: the data contract

A visual is one JSON file, `<slug>.vis.json`, plus art files beside it. `V validate` enforces this.
`assets/sample/` uses every layout and block, with the art script that drew it. Copy its shapes. It is a
component demo, so take the art standard from `art-direction.md`.

`visual/1` files (`sections` with `title`, `takeaway`, `blocks`) still build, as stacked `flow` spreads.

## Top level

| Field | Required | What it is |
| --- | --- | --- |
| `schema` | yes | `"visual/2"`. |
| `slug` | yes | Kebab-case name of the folder and files. Names the topic. |
| `title` | yes | The big idea, two to seven words. Page title and index link. |
| `shows` | yes | One line for the index: what a reader finds here. Under 220 characters. |
| `spreads` | yes | Three to seven main spreads. |
| `cover` | yes | `scene`, `fx`, `art`, `thirty_seconds` (up to three lines: the whole conclusion), `over` (art fills the screen behind the title; draw it with the focus on the right and leave the left clear, as the checks cannot see art under text). |
| `kicker`, `deck`, `status` | no | Line above the title; one or two sentences under it; a pill for something not final. |
| `theme` | no | `preset` (`atlas` `cosmos` `press` `system`), `accent` (`#rrggbb`). |
| `sources` | warned | `{title, path, url, note}`, or a repo path. Shown with titles and links in the closing section. |
| `glossary` | no | `[{term, meaning}]`. Shown on the closing page. Every piece of jargon a cold reader would stumble on. |
| `limits` | no | What was not checked or run, as a list. Shown on the closing page, and repeated beside any claim it changes. |
| `claims` | no | `{claim, source, status}`, never rendered: the headline numbers and contested claims, kept for the next update. |
| `draws_on`, `updated`, `updated_by`, `shared_link`, `footer` | no | Index cell override; `YYYY-MM-DD`; `claude`, `agy`, `fable` or `pramit`; claude.ai link; one closing line. |
| `allow_terms` | no | Short forms the reader knows, so the language check stops flagging them. |
| `number_sections` | no | `false` hides spread numbers. |

## Spread

Common fields: `id`, `chapter`, `question` (the one question), `headline` (the takeaway as a statement), `text` (a
string or list, short), `layout`, `scene` (`paper` `tint` `night` `accent` `sky`), `fx` (`stars` `aurora` `grid` `rays`
`dots`), `punch` (one bold closing line), `blocks` (supporting blocks), `appendix` (not a main page: no budgets),
`flowing` (may run over several A4 pages; appendix only).

| `layout` | Extra fields | What it is |
| --- | --- | --- |
| `cutaway` | `art` | Headline, then the art large, with notes around it. The DK plate. |
| `feature` | `art`, `flip` | Text on one side, art on the other. |
| `panels` | `panels: [{title, text, art}]`, `columns`, `arrows` | Two to five illustrated stages. |
| `duel` | `sides: [{title, text, art}]`, `vs` | Two matched drawings. |
| `scrolly` | `art`, `steps: [{title, text, explode}]` | Sticky art that changes as steps scroll by. |
| `stage` | `art`, `flip` | Full-bleed scene with text on a card. Keep the art's focus away from the card. |
| `flow` | `blocks` | Stacked blocks. For appendices. |

## Art

`art` is a graphic block. With no `type` it is an `svg`. All graphic blocks take:

| Field | What it is |
| --- | --- |
| `file` | Path relative to the JSON (`art/x.svg`, or an image or video). Read in at build; copied on publish. |
| `alt` | What the picture shows. |
| `status` | `observed` `reported` `inferred` `illustrative` `unknown` `example`. Drawn as a badge. Use `illustrative` for anything drawn to explain, `example` for made-up numbers. |
| `caption`, `source`, `title` | Under or above the picture. |
| `notes` | Annotations; see below. |
| `pan`, `pan_width` | On a phone, keep the drawing large and let it scroll sideways. |
| `frame` | `true` puts it on a card. Usually leave it off. |

**Notes** are the main way to explain a picture: `{at: [x, y], title, text, side, status}`, with `at` in the art's viewBox units
(for `model3d`, `on: "<box id>"` instead). `side` is optional. They become leader lines beside the art, rows on narrow pages and
numbered pins on phones. Keep to about six, each under fifteen words. Anchor on the object's edge so the dot
does not cover a label.

### Graphic blocks

| type | Fields | Use it to |
| --- | --- | --- |
| `svg` | `file` or `svg` (whole `<svg>` with a viewBox). No scripts. | Any authored illustration. See the classes below. |
| `model3d` | `boxes: [{id, x, y, z, w, d, h, tone, level, ghost, top_label, label_at: [u, v], label_size, slats, marks: [[u0, v0, u1, v1]]}]`, `yaw`, `pitch`, `explode`, `width`, `height`, `guides` | A real 3D exploded view: explodes on scroll, turns with the pointer, prints sharp. `level` is the floor; `ghost` draws dashed for something absent; `marks` draw lines on the top face, in fractions of it. A thin wide box makes a floor plate. |
| `chart` | `chart` (`bar` `column` `line` `stacked`), `labels`, `series: [{name, values}]`, `unit`, `prefix`, `max`, `percent`, `table` | Compare amounts, show change, show shares. Five series at most. Values at or above zero. |
| `pictogram` | `rows: [{label, value, tone}]`, `unit_value`, `unit_label`, `per_row`, `mark` (`square` `circle`), `unit`, `prefix` | Count made visible. One mark = `unit_value`. |
| `bubbles` | `items: [{label, value, tone}]`, `height`, `unit`, `prefix` | Sizes compared by area. |
| `diagram` | `nodes: [{id, label, sub, col, row, tone, filled}]`, `edges: [{from, to, label, dashed, both, animate}]`, `groups: [{label, nodes, tone}]`, `row_height` | A quick system map. Straight arrows; author an `svg` for anything finer. |
| `image` | `file` or `src`, `alt` | A photo, generated image or GIF. |
| `video` | `file` or `src`, `poster_file` | A short muted loop. The poster prints. |

`chart`, `stats`, `pictogram` and `bubbles` carry `source` or `status`. An unmeasured value is `TBD`, in text or a table.

### Classes inside an svg

- **Fills:** `f-<tone>`, `f-<tone>-l`, `f-<tone>-d`, for tones `accent good warn amber violet sky rose grey`. Also `f-fg f-bg f-sub f-card f-rule f-soft f-white f-night f-night2`, `none`, and `light` (18% fill).
- **Strokes:** `s-<tone>`, `s-accent-d`, `s-accent-l`, `s-good-d`, `s-warn-d`, `s-amber-d`, and `s-fg s-sub s-rule s-bg s-white`.
- **Gradients:** `fill="url(#vg-shadow)"`, `#vg-glow`, `#vg-sheen`, `#vg-shade`, `#vg-beam`. Pattern: `#vp-hatch`.
- **Motion, static in print:** `m-flow` (dashes move along a path), `m-spin`, `m-float`, `m-pulse`, `m-twinkle`.
- **Attributes:** `data-depth="0.2"`–`"1.2"` on a `<g>` for parallax; `data-step="2"` to reveal it at that `scrolly` step.
- **Hard-coded colours** are fine when the subject demands them, such as a brand or a real material.

## Supporting blocks

Any block may carry `source`. `tone` is one of `accent good warn amber violet sky rose muted`. Text fields take `**bold**`,
`*italic*`, `` `code` `` and `[label](url)`, as a string or a list of paragraphs.

| type | Fields | Use it to |
| --- | --- | --- |
| `text` | `text` | Say what a picture cannot. Two short paragraphs at most. |
| `list` | `items`, `ordered` | A few parallel points. |
| `callout` | `text`, `title`, `kind` (`note warn good example`), `tone`, `status` | One thing the reader must not miss. |
| `factfile` | `title`, `items` | A brochure-style highlight box. |
| `quote` | `text`, `by` | One line at reading-across-the-room size. |
| `cards` | `items: [{tag, title, text, tone, file}]`, `columns` | Short parallel parts, each with a small drawing (`file`, or inline `svg`). |
| `stats` | `items: [{value, label, note, tone, status}]`, `source` | Two to four headline numbers. |
| `flow` | `steps: [{title, who, text, mark}]`, `direction` | Plain steps. `mark`: `gate`, `done`, `stop`. |
| `table` | `columns`, `rows`, `numeric`, `key_column`, `title`, `caption`, `status` | Exact values. Six columns at most. |
| `tree` | `root: [{label, note, mono, children}]` | What contains what. |
| `timeline` | `items: [{when, title, text, tone}]` | Dated events. |
| `compare` | `options: [{name, text, pros, cons, verdict, pick, pick_label}]` | Options side by side. |
| `glossary` | `items: [{term, meaning}]` | Terms a cold reader needs. |
| `split` | `left: [blocks]`, `right: [blocks]` | Two short blocks side by side. |
