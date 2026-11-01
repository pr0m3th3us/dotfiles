#!/usr/bin/env python3
"""Build, check, publish and list visuals: infographic style illustrated editorial explainers.

The template (assets/visual-template.html) is presentation only. A visual's content lives in
<slug>.vis.json plus any art files beside it; this script is the only thing that puts them together.

    visual.py validate <data.json>
    visual.py build    <data.json> [--work DIR] [--no-pdf] [--attempt N]
    visual.py publish  <data.json> [--format html|pdf|both] [--dir DIR] [--work DIR] [--accept-failures]
    visual.py list     [--dir DIR] [--projects ROOT] [--json]

`build` writes the one-file HTML, the A4 PDF, screenshots at desktop, tablet and phone widths, the rendered
text and a report into the work folder, never into the repo. `publish` copies exactly what was built and
checked into <visuals>/<slug>/, with the data, its art files and a generated README, and upserts the index.

Exit codes: 0 clean, 1 errors to fix, 2 a tool is missing or the browser failed.
"""

from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import mimetypes
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

VERSION = "2.0.0"
SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL_DIR / "assets" / "visual-template.html"
FONTS = SKILL_DIR / "assets" / "fonts"
SCHEMAS = {"visual/1", "visual/2"}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TONES = {"accent", "good", "warn", "amber", "violet", "sky", "rose", "muted"}
STATUSES = {"observed", "reported", "inferred", "illustrative", "unknown", "example"}
CHARTS = {"bar", "column", "line", "stacked"}
PRESETS = {"atlas": "bricolage-700", "cosmos": "outfit-700", "press": "fraunces-700", "system": "bricolage-700"}
FAMILY = {"bricolage-700": "Bricolage Grotesque", "outfit-700": "Outfit", "fraunces-700": "Fraunces"}
SCENES = {"paper", "tint", "night", "accent", "sky"}
EFFECTS = {"none", "stars", "aurora", "grid", "rays", "dots"}
LAYOUTS = {"feature", "cutaway", "duel", "panels", "scrolly", "stage", "flow"}
MAX_SERIES = 5
PAGE_DPI = 110
VIEWPORTS = {"desktop": (1440, 900), "tablet": (820, 1100), "phone": (390, 844)}
A4_PX = (794, 1123)
# house rules for a main A4 page
WORDS_AIM, WORDS_REVIEW = (120, 180), 220
GRAPHIC_AIM = (40, 60)

BLOCK_REQUIRED = {
    "text": ["text"], "list": ["items"], "callout": ["text"], "cards": ["items"],
    "stats": ["items"], "flow": ["steps"], "table": ["columns", "rows"],
    "chart": ["chart", "labels", "series"], "diagram": ["nodes"], "svg": ["svg"],
    "tree": ["root"], "timeline": ["items"], "compare": ["options"], "glossary": ["items"],
    "split": ["left", "right"], "model3d": ["boxes"], "image": ["src"], "video": ["src"],
    "pictogram": ["rows"], "bubbles": ["items"], "factfile": ["items"], "quote": ["text"],
}
GRAPHICS = {"chart", "diagram", "svg", "model3d", "image", "video", "pictogram", "bubbles"}
NUMERIC_BLOCKS = {"chart", "stats", "pictogram", "bubbles"}
COMMON_CAPS = {"A4", "PDF", "HTML", "JSON", "URL", "OK", "AM", "PM", "EXAMPLE", "TBD", "ID", "I", "UK", "US",
               "INR", "USD", "FAQ", "CEO", "IT", "TV", "PIN", "RECOMMENDED", "NOT", "NEVER", "ONLY", "GB", "MB", "KB",
               "SAMPLE", "DRAFT", "PROPOSED", "ACCEPTED", "REJECTED", "LIVE", "DONE", "NEW", "STOP", "GO", "SVG", "3D", "2D"}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"error: {path} is not valid JSON: {e}")
    except FileNotFoundError:
        sys.exit(f"error: {path} not found")


def repo_root(start: Path) -> Path:
    try:
        out = subprocess.run(["git", "-C", str(start), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, check=True).stdout.strip()
        return Path(out)
    except Exception:
        return start


def default_dir(start: Path) -> Path:
    root = repo_root(start)
    for cand in (root / "docs" / "visuals", root / "visuals"):
        if cand.is_dir():
            return cand
    return root / ("docs/visuals" if (root / "docs").is_dir() else "visuals")


def work_dir(data: dict, given: str | None) -> Path:
    w = Path(given) if given else Path(tempfile.gettempdir()) / "visual" / data.get("slug", "untitled")
    w.mkdir(parents=True, exist_ok=True)
    return w


def spreads_of(data: dict) -> list[dict]:
    return data.get("spreads") or data.get("sections") or []


def source_path(s) -> str:
    return str(s.get("path") or "") if isinstance(s, dict) else str(s)


def source_name(s) -> str:
    if isinstance(s, dict):
        return str(s.get("title") or Path(str(s.get("path") or s.get("url") or "")).name)
    return f"`{Path(str(s).split('#')[0]).name}`"


def art_objects(node):
    """Every art-like dict in the data: anything holding a `file` reference."""
    if isinstance(node, dict):
        if "file" in node or "poster_file" in node:
            yield node
        for v in node.values():
            yield from art_objects(v)
    elif isinstance(node, list):
        for v in node:
            yield from art_objects(v)


def resolve(data: dict, base: Path) -> tuple[dict, list[str], list[str]]:
    """Return a copy of the data with art files read in, plus the files used and any errors."""
    out = copy.deepcopy(data)
    files, errs = [], []
    for d in art_objects(out):
        for key, target in (("file", None), ("poster_file", "poster")):
            rel = d.get(key)
            if not rel:
                continue
            p = base / rel
            if not p.exists():
                errs.append(f"art file not found: {rel}")
                continue
            files.append(rel)
            if p.suffix.lower() == ".svg" and key == "file":
                text = p.read_text(encoding="utf-8")
                d["svg"] = text[text.index("<svg"):] if "<svg" in text else text
            else:
                mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
                uri = f"data:{mime};base64,{base64.b64encode(p.read_bytes()).decode()}"
                d[target or "src"] = uri
    return out, sorted(set(files)), errs


# --------------------------------------------------------------------------- #
# validate
# --------------------------------------------------------------------------- #

def validate(data: dict, base: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warns: list[str] = []
    if data.get("schema") not in SCHEMAS:
        errors.append('top: "schema" must be "visual/2"')
    for f in ("slug", "title", "shows"):
        if not data.get(f):
            errors.append(f'top: "{f}" is required')
    if not spreads_of(data):
        errors.append('top: "spreads" is required')
    if data.get("slug") and not SLUG_RE.match(data["slug"]):
        errors.append(f'top: slug {data["slug"]!r} must be kebab-case')
    if len(str(data.get("shows", ""))) > 220:
        warns.append('top: "shows" is long for an index cell; aim for one line (under 220 characters)')
    if not data.get("sources"):
        warns.append('top: no "sources": a reader cannot tell where the page comes from')
    roots = {repo_root(base), repo_root(Path.cwd()), base}
    for s in data.get("sources") or []:
        p = source_path(s).split("#")[0].split(" ")[0]
        if p and "/" in p and ":" not in p and not any((r / p).exists() for r in roots):
            warns.append(f"top: source {p!r} does not exist in the repo")
    theme = data.get("theme") or {}
    accent = theme.get("accent")
    if accent and not re.match(r"^#[0-9a-fA-F]{6}$", accent):
        errors.append("theme.accent must be a #rrggbb colour")
    if theme.get("preset") and theme["preset"] not in PRESETS:
        errors.append(f"theme.preset must be one of {sorted(PRESETS)}")

    v2 = data.get("schema") == "visual/2"
    cover = data.get("cover") or {}
    if v2:
        if not cover.get("art"):
            warns.append("cover: no hero art; the first screen is what makes someone want to read on")
        if not cover.get("thirty_seconds"):
            warns.append("cover: no thirty_seconds; a cold reader should get the conclusion from the first screen")
        if cover.get("art"):
            check_block({"type": "svg", **cover["art"]} if "type" not in cover["art"] else cover["art"],
                        "cover art", errors, warns, resolved=False)
        check_scene(cover, "cover", errors)
    secs = spreads_of(data)
    main = [s for s in secs if not s.get("appendix")]
    if len(main) > 9:
        warns.append(f"top: {len(main)} spreads; more than 9 usually means two visuals")
    for i, s in enumerate(secs, 1):
        where = f"spread {i}"
        if not (s.get("headline") or s.get("title")):
            errors.append(f"{where}: headline is required")
        check_scene(s, where, errors)
        layout = s.get("layout") or "flow"
        if layout not in LAYOUTS:
            errors.append(f"{where}: layout {layout!r} not in {sorted(LAYOUTS)}")
        if layout in {"feature", "cutaway", "stage", "scrolly"} and not s.get("art"):
            errors.append(f"{where}: layout {layout} needs art")
        if layout == "panels" and not s.get("panels"):
            errors.append(f"{where}: layout panels needs panels")
        if layout == "duel" and len(s.get("sides") or []) < 2:
            errors.append(f"{where}: layout duel needs two sides")
        if layout == "scrolly" and not s.get("steps"):
            errors.append(f"{where}: layout scrolly needs steps")
        if v2 and not s.get("appendix") and not s.get("question"):
            warns.append(f"{where}: no question; each main page answers one question")
        visual = 0
        arts = []
        if s.get("art"):
            arts.append(s["art"])
        arts += [p["art"] for p in s.get("panels") or [] if p.get("art")]
        arts += [p["art"] for p in s.get("sides") or [] if p.get("art")]
        for j, a in enumerate(arts, 1):
            visual += check_block({"type": "svg", **a} if "type" not in a else a, f"{where} art {j}", errors, warns, resolved=False)
        for j, b in enumerate(s.get("blocks") or [], 1):
            visual += check_block(b, f"{where} block {j}", errors, warns, resolved=False)
        if not visual and not s.get("appendix"):
            warns.append(f"{where}: no focal visual; cards, tables, stats and panels of text do not count")
    return errors, warns


def check_scene(s: dict, where: str, errors: list[str]) -> None:
    if s.get("scene") and s["scene"] not in SCENES:
        errors.append(f"{where}: scene {s['scene']!r} not in {sorted(SCENES)}")
    if s.get("fx") and s["fx"] not in EFFECTS:
        errors.append(f"{where}: fx {s['fx']!r} not in {sorted(EFFECTS)}")


def check_block(b: dict, where: str, errors: list[str], warns: list[str], resolved: bool = True) -> int:
    """Validate one block; return 1 if it is a meaningful graphic rather than arranged text."""
    t = b.get("type") if isinstance(b, dict) else None
    if t not in BLOCK_REQUIRED:
        errors.append(f"{where}: unknown type {t!r} (known: {', '.join(sorted(BLOCK_REQUIRED))})")
        return 0
    where = f"{where} ({t})"
    has_file = bool(b.get("file"))
    for f in BLOCK_REQUIRED[t]:
        if b.get(f) in (None, "", []) and not (has_file and f in {"svg", "src"}):
            errors.append(f"{where}: {f!r} is required")
    if b.get("tone") and b["tone"] not in TONES:
        errors.append(f"{where}: tone {b['tone']!r} not in {sorted(TONES)}")
    if b.get("status") and b["status"] not in STATUSES:
        errors.append(f"{where}: status {b['status']!r} not in {sorted(STATUSES)}")
    for it in (b.get("items") or []) if isinstance(b.get("items"), list) else []:
        if isinstance(it, dict) and it.get("tone") and it["tone"] not in TONES:
            errors.append(f"{where}: item tone {it['tone']!r} not in {sorted(TONES)}")
    marked = b.get("source") or b.get("example") or b.get("status")
    if t in NUMERIC_BLOCKS and not marked \
            and not all(isinstance(i, dict) and (i.get("example") or i.get("status")) for i in b.get("items") or [{}]):
        warns.append(f"{where}: numbers with no \"source\" or \"status\"")
    if t == "chart":
        if b.get("chart") not in CHARTS:
            errors.append(f"{where}: chart must be one of {sorted(CHARTS)}")
        n = len(b.get("labels") or [])
        series = b.get("series") or []
        if len(series) > MAX_SERIES:
            errors.append(f"{where}: {len(series)} series; at most {MAX_SERIES} (fold the rest into 'Other')")
        if len(series) > 1 and any(not s.get("name") for s in series):
            errors.append(f"{where}: every series needs a name when there are two or more")
        for s in series:
            vals = s.get("values") or []
            if len(vals) != n:
                errors.append(f"{where}: series {s.get('name', '?')!r} has {len(vals)} values for {n} labels")
            if any(not isinstance(v, (int, float)) for v in vals):
                errors.append(f"{where}: series {s.get('name', '?')!r} values must be numbers")
            elif any(v < 0 for v in vals):
                errors.append(f"{where}: series {s.get('name', '?')!r} has negative values, which these charts cannot draw; author an svg")
        if b.get("chart") == "column" and n > 14:
            warns.append(f"{where}: {n} columns will crowd the labels; use a bar chart")
    elif t == "table":
        cols = len(b.get("columns") or [])
        for k, r in enumerate(b.get("rows") or [], 1):
            if not isinstance(r, list) or len(r) != cols:
                errors.append(f"{where}: row {k} has {len(r) if isinstance(r, list) else '?'} cells for {cols} columns")
        if cols > 6:
            warns.append(f"{where}: {cols} columns may not fit an A4 page width")
    elif t == "diagram":
        ids = [n.get("id") for n in b.get("nodes") or []]
        if len(ids) != len(set(ids)) or None in ids:
            errors.append(f"{where}: node ids must be present and unique")
        seen = set()
        for n in b.get("nodes") or []:
            c, r = n.get("col"), n.get("row")
            if not (isinstance(c, int) and isinstance(r, int) and c >= 1 and r >= 1):
                errors.append(f"{where}: node {n.get('id')!r} needs integer col and row, from 1")
            elif (c, r) in seen:
                errors.append(f"{where}: two nodes share col {c}, row {r}")
            seen.add((c, r))
        for e in b.get("edges") or []:
            if e.get("from") not in ids or e.get("to") not in ids:
                errors.append(f"{where}: edge {e.get('from')}→{e.get('to')} names a missing node")
        for g in b.get("groups") or []:
            for nid in g.get("nodes") or []:
                if nid not in ids:
                    errors.append(f"{where}: group {g.get('label')!r} names missing node {nid!r}")
    elif t == "svg":
        svg = str(b.get("svg", ""))
        if not has_file and ("<svg" not in svg or "viewBox" not in svg):
            errors.append(f"{where}: needs a whole <svg> with a viewBox")
        if re.search(r"<script|\son\w+=|<foreignObject", svg, re.I):
            errors.append(f"{where}: no scripts, event handlers or foreignObject in an svg")
    elif t == "model3d":
        ids = {x.get("id") for x in b.get("boxes") or []}
        for n in b.get("notes") or []:
            if n.get("on") and n["on"] not in ids:
                errors.append(f"{where}: note points at missing box {n['on']!r}")
    elif t == "flow":
        for s in b.get("steps") or []:
            if s.get("mark") and s["mark"] not in {"gate", "done", "stop"}:
                errors.append(f"{where}: step mark {s['mark']!r} must be gate, done or stop")
    elif t == "split":
        got = 0
        for side in ("left", "right"):
            for k, x in enumerate(b.get(side) or [], 1):
                got += check_block(x, f"{where} {side} {k}", errors, warns, resolved)
        return 1 if got else 0
    if t in GRAPHICS and not b.get("alt") and t != "chart":
        warns.append(f"{where}: no alt text describing the picture")
    return 1 if t in GRAPHICS else 0


# --------------------------------------------------------------------------- #
# language pass, on the text a reader actually sees (including text in art)
# --------------------------------------------------------------------------- #

def language(lines: list[str], data: dict) -> list[str]:
    notes: list[str] = []
    plain = "\n".join(lines)
    for sent in re.split(r"(?<=[.!?])\s+|\n", plain):
        words = re.findall(r"[A-Za-z0-9'’-]+", sent)
        if len(words) > 28:
            notes.append(f"long sentence ({len(words)} words): {sent.strip()[:90]}…")
    for m in re.finditer(r"\b([A-Za-z]+)[ \t]+\1\b", plain, re.I):
        notes.append(f"repeated word: {m.group(0)!r}")
    defined = set(data.get("allow_terms") or [])

    def walk(n):
        if isinstance(n, dict):
            if n.get("type") == "glossary":
                for i in n.get("items") or []:
                    defined.add(re.sub(r"[^A-Za-z0-9]", "", str(i.get("term", ""))))
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)
    walk(data.get("spreads") or data.get("sections") or [])
    for i in data.get("glossary") or []:
        defined.add(re.sub(r"[^A-Za-z0-9]", "", str(i.get("term", ""))))
    defined |= set(re.findall(r"\(([A-Z][A-Z0-9]{1,6})s?\)", plain))
    prose = "\n".join(x for x in plain.splitlines() if x != x.upper())
    caps = sorted({w for w in re.findall(r"\b[A-Z][A-Z0-9]{1,6}s?\b", prose)
                   if w.rstrip("s") not in COMMON_CAPS | defined and not w.isdigit()})
    if caps:
        notes.append("abbreviations never spelled out on the page (spell out once, or add to a glossary "
                     "block or allow_terms): " + ", ".join(caps[:25]))
    dict_path = Path("/usr/share/dict/words")
    if dict_path.exists():
        vocab = {w.strip().lower() for w in dict_path.read_text(errors="ignore").splitlines()}
        odd = set()
        for w in re.findall(r"(?<![\w'`-])[a-z][a-z]{3,}(?![\w'`-])", plain):
            base = w
            for suf in ("ing", "ed", "es", "s", "ly", "er"):
                if w not in vocab and w.endswith(suf) and w[: -len(suf)] in vocab:
                    base = w[: -len(suf)]
            if base not in vocab and w not in vocab:
                odd.add(w)
        if odd:
            notes.append("words not in the dictionary, check spelling: " + ", ".join(sorted(odd)[:30]))
    return notes


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #

def font_css(preset: str) -> str:
    faces = [(PRESETS.get(preset, "bricolage-700"), None, 700, "normal"),
             ("figtree-400", "Figtree", 400, "normal"),
             ("figtree-600", "Figtree", 600, "normal"),
             ("figtree-400i", "Figtree", 400, "italic")]
    css = []
    for fname, family, weight, style in faces:
        p = FONTS / f"{fname}.woff2"
        if not p.exists():
            continue
        fam = family or FAMILY[fname]
        b64 = base64.b64encode(p.read_bytes()).decode()
        css.append(f'@font-face{{font-family:"{fam}";font-weight:{weight};font-style:{style};font-display:block;'
                   f'src:url(data:font/woff2;base64,{b64}) format("woff2")}}')
    return "\n".join(css)


def render_html(data: dict) -> str:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False, indent=0).replace("</", "<\\/")
    title = re.sub(r"[*`_]", "", str(data.get("title", "Visual")))
    title = title.replace("&", "&amp;").replace("<", "&lt;")
    preset = (data.get("theme") or {}).get("preset") or "atlas"
    return (tpl.replace("/*__VIS_FONTS__*/", font_css(preset))
            .replace("__VIS_TITLE__", title).replace("__VIS_DATA__", payload))


DOM_CHECK = r"""
(mode) => {
  const root = document.getElementById('vis-root');
  const out = {mode, errors: (window.__visErrors || []).slice(), must: [], judge: [], spreads: [], texts: [],
               scrollW: document.documentElement.scrollWidth, vw: document.documentElement.clientWidth};
  const cv = document.createElement('canvas'); cv.width = cv.height = 1;
  const cx = cv.getContext('2d', {willReadFrequently: true}), cache = {};
  const rgba = c => { if (c in cache) return cache[c]; cx.clearRect(0,0,1,1); cx.fillStyle = '#000'; cx.fillStyle = c; cx.fillRect(0,0,1,1);
    const d = cx.getImageData(0,0,1,1).data; return cache[c] = [d[0], d[1], d[2], d[3] / 255]; };
  const LIM = {desktop: {html: 13, svg: 11}, tablet: {html: 13, svg: 10}, phone: {html: 13, svg: 10}, print: {html: 13.2, svg: 10.6}}[mode];
  const pageH = 296.7 * 96 / 25.4;
  const unit = mode === 'print' ? v => (v * .75).toFixed(1) + ' pt' : v => v.toFixed(1) + ' px';
  const snip = s => s.trim().replace(/\s+/g, ' ').slice(0, 46);
  const hit = (a, b) => { const w = Math.min(a.right, b.right) - Math.max(a.left, b.left), h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top); return w > 0 && h > 0 ? w * h : 0; };
  const area = r => Math.max(1, r.width * r.height);
  const blockOf = e => { while (e && e !== root && getComputedStyle(e).display.startsWith('inline')) e = e.parentElement; return e; };
  document.querySelectorAll('.spread[data-spread]').forEach(sp => {
    const id = sp.getAttribute('data-spread'), name = id === '0' ? 'cover' : id === 'end' ? 'sources' : 'spread ' + id;
    const appendix = sp.hasAttribute('data-appendix');
    const items = [];
    const w = document.createTreeWalker(sp, NodeFilter.SHOW_TEXT);
    while (w.nextNode()) {
      const n = w.currentNode, p = n.parentElement;
      if (!n.textContent.trim() || p.closest('svg,title,.fx,[data-furniture],.folio,details.numbers:not([open]),style,script')) continue;
      const rg = document.createRange(); rg.selectNodeContents(n);
      const rects = [...rg.getClientRects()].filter(r => r.width > 0 && r.height > 0);
      if (!rects.length) continue;
      const cs = getComputedStyle(p);
      if (cs.visibility === 'hidden' || +cs.opacity < .05) continue;
      items.push({el: p, block: blockOf(p), rects, size: parseFloat(cs.fontSize), color: cs.color, txt: n.textContent, svg: false});
    }
    sp.querySelectorAll('svg text').forEach(t => {
      if (t.closest('.leaders,.fx') || !t.textContent.trim()) return;
      const r = t.getBoundingClientRect(); if (!r.width) return;
      const cs = getComputedStyle(t), m = t.getScreenCTM();
      const op = (() => { let a = 1, e = t; while (e && e.tagName.toLowerCase() !== 'svg') { a *= +getComputedStyle(e).opacity; e = e.parentElement; } return a; })();
      if (op < .05) return;
      items.push({el: t, block: t, rects: [r], size: parseFloat(cs.fontSize) * Math.hypot(m.a, m.b), color: cs.fill, txt: t.textContent, svg: true,
                  skew: !!t.closest('.m3-box')});
    });
    // type size
    let smallH = null, smallS = null;
    items.forEach(i => { if (i.svg) { if (i.size < LIM.svg && !i.skew && (!smallS || i.size < smallS.size)) smallS = i; }
      else if (i.size < (i.el.closest('.badge,.lb,.chap,.tag,.c-kicker,.no,.pin,th,code') ? 10 : LIM.html) && (!smallH || i.size < smallH.size)) smallH = i; });
    if (smallH) out.judge.push(`${mode} ${name}: text at ${unit(smallH.size)}: "${snip(smallH.txt)}"`);
    if (smallS) out.judge.push(`${mode} ${name}: label in the art at ${unit(smallS.size)}: "${snip(smallS.txt)}"; make it bigger, or move it into a note`);
    // overlaps: two pieces of text on top of each other
    const flat = []; items.forEach((i, k) => { if (!i.skew) i.rects.forEach(r => flat.push({r, k})); });
    const seen = new Set();
    for (let a = 0; a < flat.length && out.must.length < 40; a++) for (let b = a + 1; b < flat.length; b++) {
      const A = items[flat[a].k], B = items[flat[b].k];
      if (flat[a].k === flat[b].k || A.block === B.block || A.block.contains(B.block) || B.block.contains(A.block)) continue;
      const ov = hit(flat[a].r, flat[b].r);
      if (ov > 8 && ov > .12 * Math.min(area(flat[a].r), area(flat[b].r))) {
        const key = flat[a].k + '/' + flat[b].k; if (seen.has(key)) continue; seen.add(key);
        out.must.push(`${mode} ${name}: text overlaps text: "${snip(A.txt)}" and "${snip(B.txt)}"`);
      }
    }
    // clipping
    items.forEach(i => {
      if (i.svg) {
        const s = i.el.ownerSVGElement, sr = s.getBoundingClientRect(), r = i.rects[0];
        if (!i.skew && !s.closest('.fx') && getComputedStyle(s).overflow !== 'visible' && (r.right > sr.right + 1 || r.left < sr.left - 1 || r.top < sr.top - 1 || r.bottom > sr.bottom + 1))
          out.must.push(`${mode} ${name}: text cut off at the edge of the art: "${snip(i.txt)}"`);
        if (!i.skew) { const c = {x: (r.left + r.right) / 2, y: (r.top + r.bottom) / 2}; let box = null;
          s.querySelectorAll('rect').forEach(q => { const b = q.getBoundingClientRect(); if (b.width >= .6 * r.width && b.width * b.height < .5 * area(sr) && b.left <= c.x && b.right >= c.x && b.top <= c.y && b.bottom >= c.y && (!box || b.width * b.height < box.width * box.height)) box = b; });
          if (box && (r.left < box.left - 2 || r.right > box.right + 2)) out.judge.push(`${mode} ${name}: label wider than the shape behind it: "${snip(i.txt)}"`); }
      } else {
        for (let a = i.el.parentElement; a && a !== document.body; a = a.parentElement) {
          const o = getComputedStyle(a); if (o.overflowX === 'visible' && o.overflowY === 'visible') continue;
          if (o.overflowX === 'auto' || o.overflowX === 'scroll') break;
          const ar = a.getBoundingClientRect();
          if (i.rects.some(r => r.right > ar.right + 1 || r.left < ar.left - 1 || (r.bottom > ar.bottom + 1 && mode !== 'print'))) { out.must.push(`${mode} ${name}: text clipped by its container: "${snip(i.txt)}"`); break; }
        }
        if (i.rects.some(r => r.right > out.vw + 1 || r.left < -1) && !i.el.closest('.pan,.tablewrap')) out.must.push(`${mode} ${name}: text runs off the screen: "${snip(i.txt)}"`);
      }
    });
    // leaders must reach something: pins and notes must stay inside the spread
    // graphic share of the content box, on a raster so overlaps count once
    const pg = sp.querySelector('.page') || sp, cs = getComputedStyle(pg);
    const sr = sp.getBoundingClientRect();
    const px = parseFloat(cs.paddingLeft), py = parseFloat(cs.paddingTop);
    const box = {left: sr.left + px, right: sr.right - px, top: sr.top + py, bottom: sr.bottom - py};
    const figs = [...sp.querySelectorAll('figure[data-figure] .a-stage svg, figure[data-figure] .a-stage img, figure[data-figure] .a-stage video, .card .ic svg')]
      .filter(e => !e.closest('.leaders')).map(e => e.getBoundingClientRect()).filter(r => r.width > 0);
    let on = 0; const N = 60;
    for (let gx = 0; gx < N; gx++) for (let gy = 0; gy < N; gy++) {
      const X = box.left + (gx + .5) / N * (box.right - box.left), Y = box.top + (gy + .5) / N * (box.bottom - box.top);
      if (figs.some(r => r.left <= X && r.right >= X && r.top <= Y && r.bottom >= Y)) on++;
    }
    // richness signal for authored art
    const art = [...sp.querySelectorAll('figure[data-figure] .a-stage svg:not([data-gen])')].map(s => ({
      shapes: s.querySelectorAll('rect,circle,ellipse,polygon,path,line,polyline').length,
      tones: new Set([...s.querySelectorAll('[class*="f-"]')].map(e => (String(e.getAttribute('class')).match(/f-(accent|good|warn|amber|violet|sky|rose|grey)/) || [])[1]).filter(Boolean)).size,
      depth: s.querySelectorAll('[class*="-l"],[class*="-d"],[fill^="url("]').length,
    }));
    const words = items.reduce((n, i) => n + (i.txt.match(/[^\s]+/g) || []).length, 0);
    out.spreads.push({id, name, appendix, words, graphic: Math.round(on / (N * N) * 100), figures: figs.length, art,
      height: sp.scrollHeight, overflowPage: mode === 'print' && !appendix ? sp.scrollHeight > pageH + 2 : false,
      layout: [...sp.classList].filter(c => c.startsWith('layout-')).join('').replace('layout-', ''),
      scene: ([...sp.classList].filter(c => c.startsWith('scene-'))[0] || '').replace('scene-', '')});
    items.forEach(i => { const r = i.rects[0], c = rgba(i.color);
      out.texts.push({s: name, sid: id, t: snip(i.txt), full: i.txt.trim().replace(/\s+/g, ' '), x0: r.left - sr.left, y0: r.top - sr.top, x1: r.right - sr.left, y1: r.bottom - sr.top, color: c, size: i.size, svg: i.svg, skew: !!i.skew, inset: !!i.el.closest('.badge')});
    });
  });
  if (out.scrollW > out.vw + 1) out.must.push(`${mode}: the page scrolls sideways (${out.scrollW}px wide at ${out.vw}px)`);
  root.querySelectorAll('.note').forEach(n => { const r = n.getBoundingClientRect(); if (r.width && r.width < 90 && mode !== 'phone') out.judge.push(`${mode}: a note is only ${Math.round(r.width)}px wide: "${snip(n.textContent)}"`); });
  return out;
}
"""


def lum(c) -> float:
    def f(v):
        v = v / 255
        return v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4
    return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2])


def shot_name(mode: str, sid: str) -> str:
    return f"{mode}-{'00' if sid == '0' else 'end' if sid == 'end' else sid.zfill(2)}.png"


def contrast_issues(shots: Path, m: dict, fitz) -> tuple[list[str], list[str]]:
    """Sample the real pixels around each piece of text, so gradients and art behind it count."""
    must, judge, seen = [], [], set()
    maps: dict[str, object] = {}
    for t in m["texts"]:
        col = t["color"]
        if t["skew"] or col[3] < .3:
            continue
        if t["sid"] not in maps:
            maps[t["sid"]] = fitz.Pixmap(str(shots / shot_name(m["mode"], t["sid"])))
        pix = maps[t["sid"]]
        W, H = pix.width, pix.height
        pts = []
        x0, x1, y0, y1 = t["x0"], t["x1"], t["y0"], t["y1"]
        if not t.get("inset"):  # a badge's own border would read as its background
            for fx in (.05, .35, .65, .95):
                xx = x0 + (x1 - x0) * fx
                pts += [(xx, y0 - 2), (xx, y1 + 2)]
        pts += [(x0 - 3, (y0 + y1) / 2), (x1 + 3, (y0 + y1) / 2)]
        px = [pix.pixel(int(x), int(y))[:3] for x, y in pts if 0 <= x < W and 0 <= y < H]
        if not px:
            continue
        ranks = sorted(lum(p) for p in px)
        bg = statistics.median(ranks)
        fg = lum([col[i] * col[3] + (statistics.median(p[i] for p in px)) * (1 - col[3]) for i in range(3)])
        ratio = (max(fg, bg) + .05) / (min(fg, bg) + .05)
        large = t["size"] >= 24
        key = (t["s"], t["t"])
        if key in seen:
            continue
        if ratio < 2.2:
            seen.add(key)
            must.append(f"{m['mode']} {t['s']}: text nearly invisible (contrast {ratio:.1f}:1): \"{t['t']}\"")
        elif ratio < (3 if large else 4.5) and not t["svg"]:
            seen.add(key)
            judge.append(f"{m['mode']} {t['s']}: low contrast ({ratio:.1f}:1): \"{t['t']}\"")
        elif ratio < 3 and t["svg"]:
            seen.add(key)
            judge.append(f"{m['mode']} {t['s']}: label low contrast ({ratio:.1f}:1): \"{t['t']}\"")
    return must, judge[:14]


def richness(data: dict, m: dict) -> list[str]:
    """House rules for the print direction and the art direction overall. Signals, not quotas."""
    notes = []
    main = [s for s in m["spreads"] if not s["appendix"] and s["id"] != "end"]
    layouts = [s["layout"] for s in main if s["id"] != "0"]
    for a, b, c in zip(layouts, layouts[1:], layouts[2:]):
        if a and a == b == c:
            notes.append(f"three {a} spreads in a row; vary the composition")
            break
    if len(layouts) >= 4 and len(set(layouts)) < 3:
        notes.append(f"only {len(set(layouts))} layouts across {len(layouts)} spreads; the page will feel repetitive")
    if len({s["scene"] for s in main}) < 2:
        notes.append("every spread has the same scene; light some differently for rhythm")
    for s in main:
        if s["id"] != "0":
            if s["words"] > WORDS_REVIEW:
                notes.append(f"{s['name']}: {s['words']} words on the page (aim {WORDS_AIM[0]}-{WORDS_AIM[1]}, review over {WORDS_REVIEW}); cut, or add a page")
            if s["graphic"] < 30:
                notes.append(f"{s['name']}: graphics fill {s['graphic']}% of the page (aim {GRAPHIC_AIM[0]}-{GRAPHIC_AIM[1]}%)")
        sparse = [a for a in s["art"] if a["shapes"] < 18]
        if s["id"] != "0" and s["art"] and len(sparse) == len(s["art"]):
            notes.append(f"{s['name']}: the art has few shapes ({sparse[0]['shapes']}); add the detail that makes it read as a real thing")
        flat = [a for a in s["art"] if a["shapes"] >= 18 and a["depth"] == 0]
        if flat:
            notes.append(f"{s['name']}: the art is flat, with no light or shade steps; use the -l and -d tones")
    return notes


def build(data_path: Path, work: str | None, pdf: bool, attempt: int) -> int:
    raw = load_json(data_path)
    base = data_path.parent
    errors, warns = validate(raw, base)
    data, files, ref_errs = resolve(raw, base)
    errors += ref_errs
    w = work_dir(raw, work)
    slug = raw.get("slug", "untitled")
    print(f"visual build: {slug}  attempt {attempt} of 5")
    if errors:
        print("ERRORS in the data (fix the JSON, then build again):")
        for e in errors:
            print(f"  - {e}")
        return 1
    html = render_html(data)
    html_path = w / f"{slug}.html"
    html_path.write_text(html, encoding="utf-8")
    size_mb = len(html.encode()) / 1e6
    print(f"html   {html_path}  ({size_mb:.1f} MB)")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("error: needs playwright (pip install playwright && python3 -m playwright install chromium)")
        return 2
    try:
        import pymupdf
    except ImportError:
        print("error: needs pymupdf for the checks (pip install pymupdf)")
        return 2

    must: list[str] = []
    judge: list[str] = list(warns)
    if size_mb > 12:
        judge.append(f"the HTML is {size_mb:.1f} MB; compress images or videos")
    console: list[str] = []
    shots = w / "shots"
    if shots.exists():
        shutil.rmtree(shots)
    shots.mkdir(parents=True)
    pdf_path = w / f"{slug}.pdf"
    measures: dict[str, dict] = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": VIEWPORTS["desktop"][0], "height": VIEWPORTS["desktop"][1]})
            page.on("console", lambda m: console.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: console.append(str(e)))
            page.goto(html_path.as_uri(), wait_until="load", timeout=45000)
            page.wait_for_function("document.documentElement.dataset.rendered === '1'", timeout=15000)
            page.evaluate("document.fonts.ready")
            for mode, (vw, vh) in VIEWPORTS.items():
                page.set_viewport_size({"width": vw, "height": vh})
                page.evaluate("window.__visPrepare('freeze')")
                page.wait_for_timeout(60)
                measures[mode] = page.evaluate(DOM_CHECK, mode)
                for sp in page.query_selector_all(".spread[data-spread]"):
                    sp.screenshot(path=str(shots / shot_name(mode, sp.get_attribute("data-spread"))))
                c_must, c_judge = contrast_issues(shots, measures[mode], pymupdf)
                must += c_must
                judge += c_judge
            # print direction
            page.set_viewport_size({"width": A4_PX[0], "height": A4_PX[1]})
            page.emulate_media(media="print")
            page.evaluate("window.__visPrepare('print')")
            page.wait_for_timeout(80)
            measures["print"] = page.evaluate(DOM_CHECK, "print")
            for sp in page.query_selector_all(".spread[data-spread]"):
                sp.screenshot(path=str(shots / shot_name("print", sp.get_attribute("data-spread"))))
            c_must, c_judge = contrast_issues(shots, measures["print"], pymupdf)
            must += c_must
            judge += c_judge
            for f in shots.glob("print-*.png"):
                f.unlink()
            if pdf:
                page.pdf(path=str(pdf_path), prefer_css_page_size=True, print_background=True)
            page.emulate_media(media="screen")
            # the live page, as a reader scrolls it: what the frozen shots cannot show
            for mode in ("desktop", "phone"):
                vw, vh = VIEWPORTS[mode]
                live = browser.new_page(viewport={"width": vw, "height": vh}, has_touch=mode == "phone")
                live.on("pageerror", lambda e: console.append(str(e)))
                live.goto(html_path.as_uri(), wait_until="load", timeout=45000)
                live.wait_for_function("document.documentElement.dataset.rendered === '1'", timeout=15000)
                live.wait_for_timeout(900)
                total = live.evaluate("document.documentElement.scrollHeight")
                frames = min(28, int(total / (vh * .85)) + 1)
                for k in range(frames):
                    y = min(total - vh, int(k * (total - vh) / max(frames - 1, 1)))
                    live.evaluate(f"window.scrollTo({{top:{y},behavior:'instant'}})")
                    live.wait_for_timeout(720)
                    live.screenshot(path=str(shots / f"live-{mode}-{k + 1:02d}.png"))
                live.close()
            browser.close()
    except Exception as e:
        print(f"error: the browser failed: {e}")
        return 2

    for mode, m in measures.items():
        must += [f"render: {e}" for e in m["errors"] if mode == "desktop"]
        must += m["must"]
        judge += m["judge"]
        must += [f"print {s['name']}: does not fit one A4 page ({s['height']}px of {round(296.7 * 96 / 25.4)}px); split it or cut text"
                 for s in m["spreads"] if s["overflowPage"]]
    must += [f"console: {c}" for c in sorted(set(console))]
    must = list(dict.fromkeys(must))
    judge = list(dict.fromkeys(judge))

    if raw.get("schema") == "visual/2":
        judge += richness(raw, measures["print"])
    else:
        judge.append("this is a visual/1 file: it renders, but as a stacked report. Re-storyboard it as visual/2 spreads")

    pages_note = ""
    if pdf:
        pm, pj, pages_note = check_pdf(pdf_path, w, pymupdf, measures["print"])
        must += pm
        judge += pj

    txt_path = w / f"{slug}.txt"
    lines, cur = [], None
    for t in measures["print"]["texts"]:
        if t["s"] != cur:
            cur = t["s"]
            lines.append(f"\n[{cur}]")
        lines.append(t["full"])
    txt_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    lang = language([ln for ln in lines if not ln.startswith("\n[")], raw)

    if pdf:
        print(f"pdf    {pdf_path}  {pages_note}")
    print(f"shots  {shots}/  desktop-NN, tablet-NN, phone-NN per spread; live-desktop-NN, live-phone-NN as scrolled")
    print(f"text   {txt_path}  (everything a reader sees, including text in the art)")
    print("page   words   graphics  layout     scene   (A4: aim 120-180 words, 40-60% graphics)")
    for s in measures["print"]["spreads"]:
        print(f"  {s['name']:<10}{s['words']:>4}   {s['graphic']:>4}%    {s['layout'] or '-':<10} {s['scene']}")
    for head, items in (("MUST FIX (fidelity)", must), ("JUDGE (richness, reading, evidence)", judge), ("LANGUAGE (plain English)", lang)):
        if items:
            print(head + ":")
            for x in items:
                print(f"  - {x}")
    report = {"slug": slug, "attempt": attempt, "pdf": pdf, "must_fix": must, "judge": judge, "language": lang, "version": VERSION,
              "html_sha1": hashlib.sha1(html.encode()).hexdigest(),
              "pdf_sha1": hashlib.sha1(pdf_path.read_bytes()).hexdigest() if pdf and pdf_path.exists() else None,
              "spreads": measures["print"]["spreads"]}
    (w / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("RESULT: " + ("FIX the must-fix items, rebuild" if must else
                        "mechanically clean; now look at every shot and PDF page as the art director"))
    return 1 if must else 0


def check_pdf(pdf_path: Path, w: Path, fitz, printed: dict) -> tuple[list[str], list[str], str]:
    mech: list[str] = []
    judge: list[str] = []
    doc = fitz.open(str(pdf_path))
    pages_dir = w / "pages"
    pages_dir.mkdir(exist_ok=True)
    hash_file = w / "page-hashes.json"
    old = json.loads(hash_file.read_text()) if hash_file.exists() else {}
    new, changed = {}, []
    for f in pages_dir.glob("p*.png"):
        f.unlink()
    margin = 6 * 72 / 25.4
    type3 = set()
    for i, pg in enumerate(doc, 1):
        rect = pg.rect
        if abs(rect.width - 595.3) > 2 or abs(rect.height - 841.9) > 2:
            mech.append(f"page {i}: not A4 ({rect.width:.0f}x{rect.height:.0f}pt)")
        box = fitz.Rect(rect.x0 + margin, rect.y0 + margin, rect.x1 - margin, rect.y1 - margin)
        blocks = [b for b in pg.get_text("blocks") if b[4].strip()]
        for b in blocks:
            if not box.contains(fitz.Rect(b[:4])):
                mech.append(f"page {i}: text too near the paper edge: {b[4].strip()[:50]!r}")
        if not blocks and not pg.get_drawings() and not pg.get_images():
            mech.append(f"page {i}: blank page")
        if len(pg.get_text().split()) < 3 and i > 1 and not pg.get_images():
            mech.append(f"page {i}: almost blank, likely a spill from the page before")
        for f in pg.get_fonts():
            if f[2] == "Type3":
                type3.add(f[3])
        if pg.get_images():
            big = [im for im in pg.get_image_info() if (im["bbox"][2] - im["bbox"][0]) > 120]
            if big:
                judge.append(f"page {i}: {len(big)} bitmap(s) in the PDF, so that part will not stay sharp when zoomed")
        pix = pg.get_pixmap(dpi=PAGE_DPI)
        png = pages_dir / f"p{i}.png"
        pix.save(str(png))
        h = hashlib.sha1(pix.samples).hexdigest()
        new[str(i)] = h
        if old.get(str(i)) != h:
            changed.append(png.name)
    if type3:
        judge.append("fonts embedded as Type 3 in the PDF: " + ", ".join(sorted(type3)[:4]))
    hash_file.write_text(json.dumps(new))
    note = f"{len(doc)} page{'s' if len(doc) != 1 else ''}, A4"
    print(f"pages  {pages_dir}/  changed: {', '.join(changed) if changed else 'none since last attempt'}")
    return mech, judge, note


# --------------------------------------------------------------------------- #
# publish and index
# --------------------------------------------------------------------------- #

INDEX_HEAD = ["Page", "Shows", "Draws on", "Shared link", "Updated"]


def index_row(data: dict, fname: str) -> str:
    draws = data.get("draws_on") or ", ".join(source_name(s) for s in data.get("sources") or []) or "—"
    link = f"[claude.ai]({data['shared_link']})" if data.get("shared_link") else "—"
    cells = [f"[{data['title']}]({fname})", str(data["shows"]), draws, link, str(data.get("updated", ""))]
    return "| " + " | ".join(c.replace("|", "\\|").replace("\n", " ") for c in cells) + " |"


def upsert_index(vdir: Path, data: dict, fname: str) -> str:
    readme = vdir / "README.md"
    slug = data["slug"]
    row = index_row(data, fname)
    if not readme.exists():
        readme.write_text(
            "# visuals\n\nInfographic style illustrated editorial explainers: each explains one topic to a reader "
            "starting from nothing. Each has its own folder, `<slug>/`, with a one-file HTML page (and sometimes an "
            "A4 PDF) built by the `visual` skill from the `<slug>.vis.json` and art beside it, and a README; edit "
            "the data and rebuild, never the output.\n\n"
            + "| " + " | ".join(INDEX_HEAD) + " |\n| " + " | ".join("---" for _ in INDEX_HEAD) + " |\n"
            + row + "\n", encoding="utf-8")
        return "created"
    lines = readme.read_text(encoding="utf-8").splitlines()
    pat = re.compile(r"^\|\s*\[[^\]]*\]\((?:" + re.escape(slug) + r"/)?" + re.escape(slug) + r"\.(?:pdf|html)\)")
    for k, ln in enumerate(lines):
        if pat.match(ln):
            lines[k] = row
            readme.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return "updated"
    start = next((k for k, ln in enumerate(lines) if re.match(r"^\|\s*Page\s*\|", ln)), None)
    if start is None:
        lines += ["", "| " + " | ".join(INDEX_HEAD) + " |", "| " + " | ".join("---" for _ in INDEX_HEAD) + " |", row]
    else:
        end = start
        while end + 1 < len(lines) and lines[end + 1].startswith("|"):
            end += 1
        lines.insert(end + 1, row)
    readme.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return "added"


def publish(data_path: Path, fmt: str, vdir: str | None, work: str | None, accept: bool) -> int:
    data = load_json(data_path)
    base = data_path.parent
    errors, _ = validate(data, base)
    resolved, files, ref_errs = resolve(data, base)
    errors += ref_errs
    if errors:
        print("error: the data has errors; run build first")
        return 1
    slug = data["slug"]
    w = work_dir(data, work)
    report_path = w / "report.json"
    if not report_path.exists():
        print(f"error: no build report in {w}; run build first")
        return 1
    report = json.loads(report_path.read_text())
    if report.get("html_sha1") != hashlib.sha1(render_html(resolved).encode()).hexdigest():
        print("error: the data, art or template changed since the last build; run build again")
        return 1
    if report.get("must_fix") and not accept:
        print(f"error: the last build has {len(report['must_fix'])} must-fix item(s); fix them, or pass --accept-failures and say so in the reply")
        return 1
    wanted = ["html", "pdf"] if fmt == "both" else [fmt]
    out_dir = Path(vdir) if vdir else default_dir(Path.cwd())  # the repo you are in, not where the JSON sits
    out_dir.mkdir(parents=True, exist_ok=True)
    folder = out_dir / slug
    folder.mkdir(exist_ok=True)
    saved = []
    for f in wanted:
        src = w / f"{slug}.{f}"
        if not src.exists():
            print(f"error: {src} not found; run build first")
            return 1
        if f == "pdf" and report.get("pdf_sha1") != hashlib.sha1(src.read_bytes()).hexdigest():
            print("error: the PDF does not match the last build; run build again")
            return 1
        shutil.copyfile(src, folder / src.name)
        saved.append(folder / src.name)
    # one source, one set of outputs: a file from an earlier build is stale, so it goes
    for other in {"html", "pdf"} - set(wanted):
        for old in (folder / f"{slug}.{other}", out_dir / f"{slug}.{other}"):
            if old.exists():
                old.unlink()
                print(f"removed {old} (stale: not from this build)")
    data_dest = folder / f"{slug}.vis.json"
    if data_path.resolve() != data_dest.resolve():
        shutil.copyfile(data_path, data_dest)
    for rel in files:
        dest = folder / rel
        if (base / rel).resolve() != dest.resolve():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(base / rel, dest)
    # the art folder travels whole, so the script that drew it is there for the next update
    if (base / "art").is_dir() and (base / "art").resolve() != (folder / "art").resolve():
        shutil.copytree(base / "art", folder / "art", dirs_exist_ok=True)
    main = saved[0]
    (folder / "README.md").write_text(folder_readme(data, main.name), encoding="utf-8")
    how = upsert_index(out_dir, data, f"{slug}/{main.name}")
    for s in saved:
        print(f"saved  {s}")
    print(f"data   {data_dest}\nreadme {folder / 'README.md'}\nindex  {out_dir / 'README.md'} ({how} the row for {slug})")
    return 0


def folder_readme(data: dict, fname: str) -> str:
    """A short guide to one visual, regenerated on every publish from its data."""
    import textwrap
    fill = lambda t: textwrap.fill(str(t), width=100, break_on_hyphens=False, break_long_words=False)
    lede = data.get("deck") or data.get("lede") or []
    lede = lede if isinstance(lede, list) else [lede]
    out = [f"# {data['title']}", "", fill(f"Open [{fname}]({fname}). It shows {lowerfirst(str(data['shows']))}."), ""]
    out += [fill(p) + "\n" for p in lede]
    out += ["## What each spread says", ""]
    for i, sec in enumerate(spreads_of(data), 1):
        title = sec.get("headline") or sec.get("title") or ""
        extra = sec.get("question") or sec.get("takeaway")
        line = f"{i}. **{title}**" + (f": {extra}" if extra else "")
        out.append(textwrap.fill(line, width=100, subsequent_indent="   ", break_on_hyphens=False, break_long_words=False))
    out.append("")
    if data.get("sources"):
        out += ["## Draws on", ""]
        for x in data["sources"]:
            if isinstance(x, dict):
                bits = [x.get("title") or "", f"`{x['path']}`" if x.get("path") else "", x.get("url") or ""]
                out.append("- " + " ".join(b for b in bits if b))
            else:
                out.append(f"- `{x}`")
        out.append("")
    out += ["## Changing it", "",
            fill(f"Edit `{data['slug']}.vis.json` or its art files and rebuild with the `visual` skill (`/visual update "
                 f"{data['slug']}`). This README, the {Path(fname).suffix.lstrip('.').upper()} and the index "
                 f"row are regenerated, so never edit them by hand."
                 + (f" Updated {data['updated']}" + (f" by {data['updated_by']}" if data.get("updated_by") else "")
                    + "." if data.get("updated") else "")), ""]
    return "\n".join(out)


def lowerfirst(t: str) -> str:
    return t[:1].lower() + t[1:] if t[:2] != t[:2].upper() else t


# --------------------------------------------------------------------------- #
# list
# --------------------------------------------------------------------------- #

def read_index(vdir: Path) -> list[dict]:
    readme = vdir / "README.md"
    rows = []
    if not readme.exists():
        return rows
    for ln in readme.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*\[([^\]]+)\]\(([^)]+)\)\s*\|(.*)\|\s*$", ln)
        if not m:
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", m.group(3))]
        cells += [""] * (4 - len(cells))
        link = re.search(r"\((https?://[^)]+)\)", cells[2])
        rows.append({"title": m.group(1), "file": m.group(2), "shows": cells[0], "draws_on": cells[1],
                     "link": link.group(1) if link else "", "updated": cells[3]})
    return rows


def list_dir(vdir: Path) -> dict:
    rows = read_index(vdir)
    listed = {r["file"] for r in rows}
    for r in rows:
        f = vdir / r["file"]
        r["format"] = f.suffix.lstrip(".").upper()
        r["exists"] = f.exists()
        r["source"] = "vis.json" if (f.parent / f"{f.stem}.vis.json").exists() else "hand-made"
    found = [p for p in vdir.glob("*.*")] + [p for p in vdir.glob("*/*.*")] if vdir.is_dir() else []
    siblings = {Path(x).with_suffix(s).as_posix() for x in listed for s in (".pdf", ".html")}
    unlisted = sorted(p.relative_to(vdir).as_posix() for p in found
                      if p.suffix in (".pdf", ".html") and p.relative_to(vdir).as_posix() not in siblings)
    return {"dir": str(vdir), "visuals": rows, "unlisted": unlisted}


def wrap_text(s: str, width: int, indent: str) -> str:
    import textwrap
    return textwrap.fill(s, width=width, initial_indent=indent, subsequent_indent=indent)


def cmd_list(vdir: str | None, projects: str | None, as_json: bool) -> int:
    dirs: list[Path] = []
    if projects:
        for p in sorted(Path(projects).expanduser().iterdir()):
            for cand in (p / "docs" / "visuals", p / "visuals"):
                if (cand / "README.md").exists():
                    dirs.append(cand)
    else:
        dirs.append(Path(vdir) if vdir else default_dir(Path.cwd()))
    hubs = [list_dir(d) for d in dirs]
    if as_json:
        print(json.dumps(hubs, indent=1))
        return 0
    total = sum(len(h["visuals"]) for h in hubs)
    print(f"VISUAL KNOWLEDGE HUBS · {total} visual{'s' if total != 1 else ''}")
    for h in hubs:
        home = Path.home()
        d = h["dir"].replace(str(home), "~")
        print(f"\n{d}/")
        if not h["visuals"]:
            print("  (none yet)")
        for r in h["visuals"]:
            flag = "" if r["exists"] else "  MISSING FILE"
            print(f"  ● {r['title']}  [{r['format']} · {r['source']} · {r['updated'] or 'no date'}]{flag}")
            print(f"    {r['file']}")
            print(wrap_text("shows: " + re.sub(r"`", "", r["shows"]), 96, "    "))
            if r["draws_on"] and r["draws_on"] != "—":
                print(wrap_text("draws on: " + re.sub(r"`", "", r["draws_on"]), 96, "    "))
            if r["link"]:
                print(f"    link: {r['link']}")
        for u in h["unlisted"]:
            print(f"  ○ {u}  NOT IN THE INDEX")
    return 0


# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate")
    v.add_argument("data")
    b = sub.add_parser("build")
    b.add_argument("data")
    b.add_argument("--work")
    b.add_argument("--no-pdf", action="store_true")
    b.add_argument("--attempt", type=int, default=1)
    pb = sub.add_parser("publish")
    pb.add_argument("data")
    pb.add_argument("--format", choices=["html", "pdf", "both"], default="html")
    pb.add_argument("--dir")
    pb.add_argument("--work")
    pb.add_argument("--accept-failures", action="store_true")
    ls = sub.add_parser("list")
    ls.add_argument("--dir")
    ls.add_argument("--projects")
    ls.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.cmd == "validate":
        p = Path(a.data)
        data = load_json(p)
        errors, warns = validate(data, p.parent)
        errors += resolve(data, p.parent)[2]
        for e in errors:
            print(f"ERROR  {e}")
        for x in warns:
            print(f"warn   {x}")
        print("valid" if not errors else f"{len(errors)} error(s)")
        return 1 if errors else 0
    if a.cmd == "build":
        return build(Path(a.data), a.work, not a.no_pdf, a.attempt)
    if a.cmd == "publish":
        return publish(Path(a.data), a.format, a.dir, a.work, a.accept_failures)
    if a.cmd == "list":
        return cmd_list(a.dir, a.projects, a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
