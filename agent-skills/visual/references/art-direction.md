# Art direction

The target is an **infographic style illustrated editorial explainer**. A page of boxes, cards and tables is a
report, however tidy. A reader should recognise the subject from the pictures before reading a word.

## What to borrow, and from whom

| Reference | Take this | Reach for it with |
| --- | --- | --- |
| **DK, *How Technology Works*** | The cutaway: one object opened up, every part labelled with a leader line, on a clean plate. Shaded, solid things. | `cutaway` with notes; `model3d` |
| **SCMP, Adolfo Arranz, *City of Anarchy*** | One huge, obsessively detailed drawing to explore. Scale and human figures for size. | `cutaway` with `pan: true`, tall art, people for scale |
| **Kurzgesagt** | Saturated flat vector on deep backgrounds, glow, gradients, charming characters, cosmic scale. | preset `cosmos`, scenes `night` and `sky`, fx `stars` |
| **The Pudding** | The story unfolds as you scroll; the chart changes with each sentence. | `scrolly` with `data-step` |
| **Reuters Graphics** | Restraint: real data, direct labels, one strong annotated graphic, serious type. | preset `press`, `chart` with notes |
| **Visual Capitalist** | A poster you can read from across the room: big hero, big numbers, strong ranked data. | `feature`, `bubbles`, `stats` |
| **Information is Beautiful** | A clever encoding that makes a comparison obvious. Colour with meaning. | `pictogram`, `bubbles`, `duel` |
| **ByteByteGo** | Crisp system diagrams, friendly icons, data visibly moving along arrows. | preset `system`, `diagram`, `.m-flow` paths |

## The principles behind the choices

| Principle | In practice |
| --- | --- |
| **Coherence** (Mayer) | Everything teaches, orients or gives useful context. Decoration competing with the explanation goes. |
| **Signaling** | The takeaway and evidence status are visible at once, through hierarchy, labels and selective emphasis. |
| **Spatial contiguity** | Explanations sit beside the exact part they describe. Use notes with leader lines over a distant paragraph. |
| **Information design** | Proximity, alignment, grouping and a clear reading order. Similar treatments mean similar things. |
| **Chart choice** | The relationship picks the chart (comparison, change, distribution), not novelty. |
| **Accessibility** | Contrast, real text, alternatives for meaningful images, logical reading order. |

## Picking the picture

| The reader needs to understand | Draw | Layout |
| --- | --- | --- |
| parts and how they fit | an annotated cutaway or exploded `model3d` | `cutaway` |
| a sequence, cause and effect | illustrated stages | `panels` |
| something that builds up in stages | one picture revealed step by step | `scrolly` |
| a loop or branches | an authored diagram with `.m-flow` paths | `cutaway` |
| before and after, this or that | matched drawings on the same axes | `duel` |
| an abstract idea | a concrete analogy (say where it stops being true) | `feature` |
| a real numeric comparison | `chart`, `bubbles`, `pictogram` | `feature` |
| a mood, a setting, scale | a full-bleed scene | `stage` |
| a choice | a road, doors or a map, with the pick lit up | `cutaway` |
| exact values to look up | a compact `table`, beside the main picture | any, as support |

Cards, tables, stats and fact files are support. Every main spread still needs its own focal art.

## Drawing like DK and Kurzgesagt

Use `assets/art_kit.py` as a start, then add shapes of your own until it reads as the real thing.

- **Things, not boxes.** Give objects their true silhouette and the small details that make them recognisable: rivets, vents, gauges, cables.
- **Three-tone shading.** Each tone has `-l` for lit faces, plain for the main face and `-d` for shade. Light comes from the top left, on every object.
- **Ground it.** Add `soft_shadow`. An object in a void looks pasted on.
- **Dissolve the edges.** Art with a hard rectangular background looks like a pasted card. Make a diorama, an island or a cutaway that sits directly on the page's scene.
- **Show the actual subject.** A stranger should be able to picture the thing being explained: its real shape, format and output.
- **Draw the key numbers.** A headline number gets a dial, a scale or a count of marks, on top of any digits. Compare two numbers only if they measure the same thing.
- **Put the verdict beside the object.** A stamp or label sits next to what it judges, so the object stays visible.
- **Check what the metaphor implies.** Read each picture literally and ask what a stranger concludes; redraw it if that is false.
- **Add a human or a character** for scale and warmth.
- **Make the metaphor physical.** Missing parts become dashed ghost bays. A narrow template becomes a stamping press that only makes one shape.
- **Depth layers.** Group the scene into planes with `group(..., depth=.2)` (far) to `depth=1.2` (near). The HTML moves them at different speeds.
- **Keep vectors sharp.** Use `soft_shadow` and `glow`. SVG filters print as bitmaps.
- **Keep text in the art short and big.** One to four words at 26+ units on a 1000-wide viewBox, 14+ on a small one. Explanations go in `notes`. Set size with `style="font-size:…"` or the kit's `label`.
- **Reuse motifs** across spreads so the page feels like one world.

Raster art (`image`, including GIFs, and `video`) is welcome when an image tool or supplied asset is available. Keep
critical labels and chart geometry out of it, and record its origin and licence in `sources`. Label any generated
image `illustrative`.

## Two directions, one source

Design both on purpose. The template carries out the differences; you check them in `W/shots/` and `W/pages/`.

| | HTML (the default) | A4 PDF |
| --- | --- | --- |
| Space | Full-bleed bands up to very wide screens; art fills the first screen | Exactly one full-bleed page per spread |
| Motion | Parallax planes, scroll stories, 3D that turns and explodes, flowing lines, twinkling stars, drifting aurora | The settled final state of each, all steps shown |
| Notes | Rails either side on wide screens, rows on tablets, numbered pins plus a legend on phones | Rows above and below the art (rails for tall art) |
| Scrolly | Sticky art with steps passing beside it (above them on a phone) | Art with all steps in a grid below |
| Big drawings | Pan sideways on a phone with `pan: true` | Fit to the page |
| Type | Fluid, 17–20 px body | 12 pt body, 10 pt captions |
| Charts | Redrawn to the width available, with tooltips and a numbers table | Static, sharp vectors |
| Backgrounds | `stars`, `aurora`, `grid`, `rays`, `dots` | The same, quieter; dark scenes print full-bleed |

Things to design for:

- **The first screen** at desktop should show a headline and the start of the art, and the cover should show the whole hero.
- **On a phone** the picture is small: rely on pins and big labels, and give a dense drawing `pan: true`.
- **In print**, each spread must fit its page. The template shrinks art to fit but never text; if it can't fit, split the spread.

## Presets and scenes

| Preset | Look | Suits |
| --- | --- | --- |
| `atlas` | Warm paper, saturated plates, grotesque headlines | Default: how things work, brochures |
| `cosmos` | Deep navy, neon, geometric headlines | Science, big ideas, anything playful |
| `press` | White newsprint, serif headlines, restrained red | Serious data, money, reporting |
| `system` | Crisp white, friendly blues | Software and architecture |

Scenes light each spread: `paper`, `tint`, `night`, `accent`, `sky`. Change scene between spreads, the way a magazine
changes spreads. Use `accent` once or twice for impact. Effects sit behind one or two spreads, usually the cover and a
dark one; on a spread with notes or tight text, prefer none.

## Words

Headlines state the takeaway ("The instructions shipped. The engine did not."), never the topic ("Repository contents").
Use short sentences, active voice and common words; explain a term the moment you use it, and list jargon in `glossary`.
Set up each spread's question on an earlier one. State the scope of a finding where it appears ("in the repo", "we read it,
we ran nothing"). The cover's `thirty_seconds` gives the whole conclusion in three lines.
