#!/usr/bin/env python3
"""Build, check, publish and list visuals: illustrated one-file pages made from a data JSON.

The scaffold (assets/visual-template.html) is presentation only. A visual's content lives in
<slug>.vis.json; this script is the only thing that puts the two together, so authoring a visual
never means writing markup.

    visual.py validate <data.json>
    visual.py build    <data.json> [--work DIR] [--no-pdf] [--attempt N]
    visual.py publish  <data.json> --format pdf|html [--dir DIR] [--work DIR]
    visual.py list     [--dir DIR] [--projects ROOT] [--json]

`build` writes the HTML (and the PDF, page images, text dump and a report) into the work folder,
never into the repo. `publish` gives each visual its own folder, <visuals>/<slug>/, holding the
chosen format, the data JSON and a generated README; removes the other format; and upserts the
visuals index row.

Exit codes: 0 clean, 1 errors to fix, 2 a tool is missing or the browser failed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL_DIR / "assets" / "visual-template.html"
SCHEMA = "visual/1"
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TONES = {"accent", "good", "warn", "amber", "violet", "muted"}
CHARTS = {"bar", "column", "line", "stacked"}
MAX_SERIES = 5
# A4 in points, and the @page margins of the scaffold (14mm sides and top, 16mm bottom).
MM = 72 / 25.4
MARGIN = {"top": 14 * MM, "right": 14 * MM, "bottom": 16 * MM, "left": 14 * MM}
CONTENT_PX = round((210 - 28) / 25.4 * 96)  # content width in CSS px at 96 dpi
PAGE_DPI = 100

BLOCK_REQUIRED = {
    "text": ["text"], "list": ["items"], "callout": ["text"], "cards": ["items"],
    "stats": ["items"], "flow": ["steps"], "table": ["columns", "rows"],
    "chart": ["chart", "labels", "series"], "diagram": ["nodes"], "svg": ["svg"],
    "tree": ["root"], "timeline": ["items"], "compare": ["options"], "glossary": ["items"],
    "split": ["left", "right"],
}
NUMERIC_BLOCKS = {"chart", "stats"}
# Upper-case words that never need spelling out.
COMMON_CAPS = {"A4", "PDF", "HTML", "JSON", "URL", "OK", "AM", "PM", "EXAMPLE", "TBD", "ID", "I", "UK", "US",
               "INR", "USD", "FAQ", "CEO", "IT", "TV", "PIN", "RECOMMENDED", "NOT", "NEVER", "ONLY",
               "SAMPLE", "DRAFT", "PROPOSED", "ACCEPTED", "REJECTED", "LIVE", "DONE", "NEW", "STOP", "GO"}


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


def strings(node, skip=("svg", "slug", "id", "theme", "sources", "type", "tone", "mark", "chart",
                        "from", "to", "nodes", "updated", "updated_by", "shared_link", "schema",
                        "allow_terms", "draws_on")):
    """Every reader-facing string in the data, for the language pass."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for x in node:
            yield from strings(x, skip)
    elif isinstance(node, dict):
        for k, v in node.items():
            if k not in skip:
                yield from strings(v, skip)


# --------------------------------------------------------------------------- #
# validate
# --------------------------------------------------------------------------- #

def validate(data: dict, base: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warns: list[str] = []
    if data.get("schema") != SCHEMA:
        errors.append(f'top: "schema" must be "{SCHEMA}"')
    for f in ("slug", "title", "shows", "sections"):
        if not data.get(f):
            errors.append(f'top: "{f}" is required')
    if data.get("slug") and not SLUG_RE.match(data["slug"]):
        errors.append(f'top: slug {data["slug"]!r} must be kebab-case')
    if len(str(data.get("shows", ""))) > 220:
        warns.append('top: "shows" is long for an index cell; aim for one line (under 220 characters)')
    if not data.get("sources"):
        warns.append('top: no "sources": a reader cannot tell what the page draws on')
    root = repo_root(base)
    for s in data.get("sources") or []:
        p = str(s).split("#")[0].split(" ")[0]
        if "/" in p and not (root / p).exists() and not (base / p).exists():
            warns.append(f"top: source {p!r} does not exist in the repo")
    accent = (data.get("theme") or {}).get("accent")
    if accent and not re.match(r"^#[0-9a-fA-F]{6}$", accent):
        errors.append("theme.accent must be a #rrggbb colour")

    secs = data.get("sections") or []
    if len(secs) > 9:
        warns.append(f"top: {len(secs)} sections; more than 9 usually means two visuals")
    for i, s in enumerate(secs, 1):
        where = f"section {i}"
        if not s.get("title"):
            errors.append(f"{where}: title is required")
        if not s.get("takeaway"):
            warns.append(f"{where}: no takeaway; say the one thing the reader should leave with")
        if not s.get("blocks"):
            errors.append(f"{where}: needs at least one block")
        visual = 0
        for j, b in enumerate(s.get("blocks") or [], 1):
            visual += check_block(b, f"{where} block {j}", errors, warns)
        if s.get("blocks") and not visual:
            warns.append(f"{where}: text only; add a picture (chart, diagram, flow, cards, table) if one helps")
    return errors, warns


def check_block(b: dict, where: str, errors: list[str], warns: list[str]) -> int:
    """Validate one block; return 1 if it is a visual element rather than plain text."""
    t = b.get("type") if isinstance(b, dict) else None
    if t not in BLOCK_REQUIRED:
        errors.append(f"{where}: unknown type {t!r} (known: {', '.join(sorted(BLOCK_REQUIRED))})")
        return 0
    where = f"{where} ({t})"
    for f in BLOCK_REQUIRED[t]:
        if b.get(f) in (None, "", []):
            errors.append(f"{where}: {f!r} is required")
    if b.get("tone") and b["tone"] not in TONES:
        errors.append(f"{where}: tone {b['tone']!r} not in {sorted(TONES)}")
    for it in (b.get("items") or []) if isinstance(b.get("items"), list) else []:
        if isinstance(it, dict) and it.get("tone") and it["tone"] not in TONES:
            errors.append(f"{where}: item tone {it['tone']!r} not in {sorted(TONES)}")
    if t in NUMERIC_BLOCKS and not b.get("source") and not b.get("example") \
            and not all(isinstance(i, dict) and i.get("example") for i in b.get("items") or [{}]):
        warns.append(f"{where}: numbers with no \"source\" and not marked \"example\": true")
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
            if n.get("tone") and n["tone"] not in TONES:
                errors.append(f"{where}: node tone {n['tone']!r} not in {sorted(TONES)}")
        cols = max([n.get("col", 1) for n in b.get("nodes") or [{}]] or [1])
        if isinstance(cols, int) and cols > 5:
            warns.append(f"{where}: {cols} columns of nodes; labels get narrow past 4")
        for e in b.get("edges") or []:
            if e.get("from") not in ids or e.get("to") not in ids:
                errors.append(f"{where}: edge {e.get('from')}→{e.get('to')} names a missing node")
        for g in b.get("groups") or []:
            for nid in g.get("nodes") or []:
                if nid not in ids:
                    errors.append(f"{where}: group {g.get('label')!r} names missing node {nid!r}")
    elif t == "svg":
        svg = str(b.get("svg", ""))
        if "<svg" not in svg or "viewBox" not in svg:
            errors.append(f"{where}: needs a whole <svg> with a viewBox")
        if re.search(r"<script|on\w+=|<foreignObject", svg, re.I):
            errors.append(f"{where}: no scripts, event handlers or foreignObject in an svg")
        if not b.get("alt"):
            warns.append(f"{where}: no alt text describing the picture")
    elif t == "flow":
        for s in b.get("steps") or []:
            if s.get("mark") and s["mark"] not in {"gate", "done", "stop"}:
                errors.append(f"{where}: step mark {s['mark']!r} must be gate, done or stop")
    elif t == "split":
        for side in ("left", "right"):
            for k, x in enumerate(b.get(side) or [], 1):
                check_block(x, f"{where} {side} {k}", errors, warns)
    return 0 if t in {"text", "list", "callout"} else 1


# --------------------------------------------------------------------------- #
# language pass (plain English)
# --------------------------------------------------------------------------- #

def language(data: dict) -> list[str]:
    notes: list[str] = []
    text = "\n".join(strings(data))
    plain = re.sub(r"`[^`]*`", " ", text)
    plain = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", plain)
    plain = re.sub(r"[*_]", "", plain)
    for sent in re.split(r"(?<=[.!?])\s+|\n", plain):
        words = re.findall(r"[A-Za-z0-9'’-]+", sent)
        if len(words) > 28:
            notes.append(f"long sentence ({len(words)} words): {sent.strip()[:90]}…")
    for m in re.finditer(r"\b(\w+)\s+\1\b", plain, re.I):
        if not m.group(1).isdigit():
            notes.append(f"repeated word: {m.group(0)!r}")
    defined = set(data.get("allow_terms") or [])
    for b in iter_blocks(data):
        if b.get("type") == "glossary":
            defined |= {re.sub(r"[^A-Za-z0-9]", "", str(i.get("term", ""))) for i in b.get("items") or []}
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
    else:
        notes.append("no /usr/share/dict/words; spelling is checked by the read-through only")
    long_words = sorted({w for w in re.findall(r"\b[a-z]{14,}\b", plain)})
    if long_words:
        notes.append("long words, is there a plainer one: " + ", ".join(long_words[:15]))
    return notes


def iter_blocks(data: dict):
    for s in data.get("sections") or []:
        stack = list(s.get("blocks") or [])
        while stack:
            b = stack.pop()
            if isinstance(b, dict):
                yield b
                if b.get("type") == "split":
                    stack += list(b.get("left") or []) + list(b.get("right") or [])


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #

def render_html(data: dict) -> str:
    tpl = TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False, indent=1).replace("</", "<\\/")
    title = re.sub(r"[*`_]", "", str(data.get("title", "Visual")))
    title = title.replace("&", "&amp;").replace("<", "&lt;")
    return tpl.replace("__VIS_TITLE__", title).replace("__VIS_DATA__", payload)


DOM_CHECK = r"""
() => {
  const out = {errors: (window.__visErrors || []).slice(), overflow: [], svgText: [], fonts: {}};
  const root = document.getElementById('vis-root');
  const R = root.getBoundingClientRect();
  const name = e => e.tagName.toLowerCase() + (e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\s+/).join('.') : '');
  const snip = e => (e.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 60);
  for (const e of root.querySelectorAll('*')) {
    if (e.closest('svg') && e.tagName.toLowerCase() !== 'svg') continue;
    const r = e.getBoundingClientRect();
    if (r.width && (r.right > R.right + 1 || r.left < R.left - 1))
      out.overflow.push(`${name(e)} sticks out of the page by ${Math.round(Math.max(r.right - R.right, R.left - r.left))}px: "${snip(e)}"`);
    else if (e.scrollWidth > e.clientWidth + 2 && getComputedStyle(e).overflowX !== 'visible')
      out.overflow.push(`${name(e)} has hidden content (needs a scrollbar): "${snip(e)}"`);
  }
  for (const svg of root.querySelectorAll('svg')) {
    const vb = svg.viewBox && svg.viewBox.baseVal;
    for (const t of svg.querySelectorAll('text')) {
      let b; try { b = t.getBBox(); } catch (e) { continue; }
      if (vb && vb.width && (b.x < vb.x - 1 || b.x + b.width > vb.x + vb.width + 1 || b.y < vb.y - 1 || b.y + b.height > vb.y + vb.height + 1))
        out.svgText.push(`text cut off at the picture's edge: "${t.textContent.slice(0, 50)}"`);
      const g = t.parentNode, box = g && g.querySelector && g.querySelector(':scope > rect.nbox');
      if (box) {
        const r = box.getBBox();
        if (b.x < r.x + 2 || b.x + b.width > r.x + r.width - 2)
          out.svgText.push(`label wider than its box: "${t.textContent.slice(0, 50)}"`);
      }
    }
  }
  for (const f of document.fonts) if (!(f.family.replace(/"/g, '') in out.fonts) || f.status === 'loaded')
    out.fonts[f.family.replace(/"/g, '')] = f.status === 'loaded';
  return out;
}
"""


def build(data_path: Path, work: str | None, pdf: bool, attempt: int) -> int:
    data = load_json(data_path)
    errors, warns = validate(data, data_path.parent)
    w = work_dir(data, work)
    slug = data.get("slug", "untitled")
    print(f"visual build: {slug}" + (f"  attempt {attempt} of 5" if pdf else ""))
    if errors:
        print("ERRORS in the data (fix the JSON, then build again):")
        for e in errors:
            print(f"  - {e}")
        return 1
    html_path = w / f"{slug}.html"
    html_path.write_text(render_html(data), encoding="utf-8")
    print(f"html   {html_path}")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("error: needs playwright (pip install playwright && python3 -m playwright install chromium)")
        return 2

    mech: list[str] = []      # must fix
    judge: list[str] = list(warns)
    console: list[str] = []
    pdf_path = w / f"{slug}.pdf"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": CONTENT_PX, "height": 1100})
            page.on("console", lambda m: console.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: console.append(str(e)))
            page.goto(html_path.as_uri(), wait_until="networkidle", timeout=30000)
            page.wait_for_function("document.documentElement.dataset.rendered === '1'", timeout=10000)
            page.evaluate("document.fonts.ready")
            page.emulate_media(media="print")
            dom = page.evaluate(DOM_CHECK)
            if pdf:
                page.pdf(path=str(pdf_path), prefer_css_page_size=True, print_background=True)
            # a phone-width pass: the HTML copy must also read on a phone
            page.emulate_media(media="screen")
            page.set_viewport_size({"width": 390, "height": 900})
            narrow = page.evaluate("document.documentElement.scrollWidth")
            browser.close()
    except Exception as e:
        print(f"error: the browser failed: {e}")
        return 2

    mech += [f"render: {e}" for e in dom["errors"]]
    mech += [f"console: {c}" for c in console if "fonts.g" not in c]
    mech += [f"layout: {o}" for o in dom["overflow"][:12]]
    mech += [f"picture: {o}" for o in dom["svgText"][:12]]
    if narrow > 392:
        judge.append(f"phone width: the page scrolls sideways at 390px (content is {narrow}px wide)")
    missing = [f for f, ok in dom["fonts"].items() if not ok]
    if missing:
        judge.append("web fonts did not load (offline?), fallbacks used: " + ", ".join(missing)
                     + "; fine to keep, the page just looks plainer")

    pages_note = ""
    if pdf:
        try:
            import pymupdf
        except ImportError:
            print("error: needs pymupdf for the PDF checks (pip install pymupdf)")
            return 2
        pm, pj, pages_note = check_pdf(pdf_path, w, pymupdf)
        mech += pm
        judge += pj

    txt_path = w / f"{slug}.txt"
    txt_path.write_text("\n".join(strings(data)), encoding="utf-8")
    lang = language(data)

    if pdf:
        print(f"pdf    {pdf_path}  {pages_note}")
    print(f"text   {txt_path}  (every reader-facing sentence, for the read-through)")
    sections = [("MUST FIX (mechanical)", mech), ("JUDGE (warnings)", judge), ("LANGUAGE (plain English)", lang)]
    for head, items in sections:
        if items:
            print(head + ":")
            for x in items:
                print(f"  - {x}")
    report = {"slug": slug, "attempt": attempt, "pdf": pdf, "must_fix": mech, "judge": judge, "language": lang}
    (w / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("RESULT: " + ("FIX the must-fix items, rebuild" if mech else
                        "mechanically clean; now look at the changed pages and do the read-through"))
    return 1 if mech else 0


def check_pdf(pdf_path: Path, w: Path, fitz) -> tuple[list[str], list[str], str]:
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
    for i, pg in enumerate(doc, 1):
        rect = pg.rect
        if abs(rect.width - 595.3) > 2 or abs(rect.height - 841.9) > 2:
            mech.append(f"page {i}: not A4 ({rect.width:.0f}x{rect.height:.0f}pt)")
        box = fitz.Rect(rect.x0 + MARGIN["left"] - 2, rect.y0 + MARGIN["top"] - 2,
                        rect.x1 - MARGIN["right"] + 2, rect.y1 - MARGIN["bottom"] + 2)
        blocks = [b for b in pg.get_text("blocks") if b[4].strip()]
        drawings = [d["rect"] for d in pg.get_drawings()
                    if d["rect"].width * d["rect"].height < 0.9 * rect.width * rect.height]
        for b in blocks:
            r = fitz.Rect(b[:4])
            if not box.contains(r):
                mech.append(f"page {i}: text in the margin: {b[4].strip()[:50]!r}")
        for r in drawings:
            if not box.contains(r) and r.width > 1 and r.height > 1:
                mech.append(f"page {i}: a border or shape runs into the margin at y={r.y0:.0f}pt")
                break
        if not blocks and not drawings:
            mech.append(f"page {i}: blank page")
            continue
        ys = sorted([(b[1], b[3]) for b in blocks] + [(r.y0, r.y1) for r in drawings])
        bottom = max(y1 for _, y1 in ys)
        usable = box.height
        if i == len(doc) and len(doc) > 1 and (bottom - box.y0) / usable < 0.15:
            judge.append(f"page {i}: last page is almost empty; tighten earlier content or let it run")
        cur = ys[0][1]
        for y0, y1 in ys[1:]:
            if y0 - cur > 0.3 * usable:
                judge.append(f"page {i}: a gap of {int((y0 - cur) / usable * 100)}% of the page "
                             "(a block too big to fit was pushed down); shrink it or move it")
            cur = max(cur, y1)
        if i < len(doc) and (box.y1 - bottom) > 0.3 * usable:
            judge.append(f"page {i}: bottom {int((box.y1 - bottom) / usable * 100)}% is empty; "
                         "the next block did not fit")
        spans = [s for b in pg.get_text("dict")["blocks"] for ln in b.get("lines", []) for s in ln["spans"]
                 if s["text"].strip()]
        if spans and i < len(doc):
            last = max(spans, key=lambda s: s["bbox"][3])
            if last["size"] >= 13.5:
                judge.append(f"page {i}: heading {last['text'].strip()[:40]!r} is stranded at the foot of the page")
        pix = pg.get_pixmap(dpi=PAGE_DPI)
        png = pages_dir / f"p{i}.png"
        pix.save(str(png))
        h = hashlib.sha1(pix.samples).hexdigest()
        new[str(i)] = h
        if old.get(str(i)) != h:
            changed.append(png.name)
    hash_file.write_text(json.dumps(new))
    note = f"{len(doc)} page{'s' if len(doc) != 1 else ''}, A4"
    print(f"pages  {pages_dir}/  look at: {', '.join(changed) if changed else 'none changed since last attempt'}")
    return mech, judge, note


# --------------------------------------------------------------------------- #
# publish and index
# --------------------------------------------------------------------------- #

INDEX_HEAD = ["Page", "Shows", "Draws on", "Shared link", "Updated"]


def index_row(data: dict, fname: str) -> str:
    draws = data.get("draws_on") or ", ".join(
        f"`{Path(str(s).split('#')[0]).name}`" for s in data.get("sources") or []) or "—"
    link = f"[claude.ai]({data['shared_link']})" if data.get("shared_link") else "—"
    cells = [f"[{data['title']}]({fname})", str(data["shows"]), draws, link, str(data.get("updated", ""))]
    return "| " + " | ".join(c.replace("|", "\\|").replace("\n", " ") for c in cells) + " |"


def upsert_index(vdir: Path, data: dict, fname: str) -> str:
    readme = vdir / "README.md"
    slug = data["slug"]
    row = index_row(data, fname)
    if not readme.exists():
        readme.write_text(
            "# visuals\n\nIllustrated pages that explain one topic in a single view, for reading instead of the "
            "notes behind them. Each has its own folder, `<slug>/`, with a PDF (or a one-file HTML page) built "
            "by the `visual` skill from the `<slug>.vis.json` beside it, and a README; edit the JSON and "
            "rebuild, never the output.\n\n"
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
    # append after the last row of the first table whose header starts with "Page"
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


def publish(data_path: Path, fmt: str, vdir: str | None, work: str | None) -> int:
    data = load_json(data_path)
    errors, _ = validate(data, data_path.parent)
    if errors:
        print("error: the data has errors; run build first")
        return 1
    slug = data["slug"]
    w = work_dir(data, work)
    out_dir = Path(vdir) if vdir else default_dir(Path.cwd())  # the repo you are in, not where the JSON sits
    out_dir.mkdir(parents=True, exist_ok=True)
    src = w / f"{slug}.{fmt}"
    if fmt == "html":
        src.write_text(render_html(data), encoding="utf-8")  # always fresh from the data
    if not src.exists():
        print(f"error: {src} not found; run build first")
        return 1
    folder = out_dir / slug
    folder.mkdir(exist_ok=True)
    dest = folder / f"{slug}.{fmt}"
    shutil.copyfile(src, dest)
    other_fmt = "html" if fmt == "pdf" else "pdf"
    for old in (folder / f"{slug}.{other_fmt}", out_dir / f"{slug}.pdf", out_dir / f"{slug}.html"):
        if old.exists():
            old.unlink()
            print(f"removed {old} (replaced by {dest.relative_to(out_dir)})")
    data_dest = folder / f"{slug}.vis.json"
    if data_path.resolve() != data_dest.resolve():
        shutil.copyfile(data_path, data_dest)
    flat = out_dir / f"{slug}.vis.json"
    if flat.exists() and flat.resolve() != data_path.resolve():
        flat.unlink()
    (folder / "README.md").write_text(folder_readme(data, dest.name), encoding="utf-8")
    how = upsert_index(out_dir, data, f"{slug}/{dest.name}")
    print(f"saved  {dest}\ndata   {data_dest}\nreadme {folder / 'README.md'}\n"
          f"index  {out_dir / 'README.md'} ({how} the row for {slug})")
    return 0


def folder_readme(data: dict, fname: str) -> str:
    """A short guide to one visual, regenerated on every publish from its data."""
    import textwrap
    fill = lambda t: textwrap.fill(str(t), width=100, break_on_hyphens=False, break_long_words=False)
    lede = data.get("lede") or []
    lede = lede if isinstance(lede, list) else [lede]
    out = [f"# {data['title']}", "", fill(f"Open [{fname}]({fname}). It shows {lowerfirst(str(data['shows']))}."), ""]
    out += [fill(p) + "\n" for p in lede]
    out += ["## What each section says", ""]
    for i, sec in enumerate(data.get("sections") or [], 1):
        line = f"{i}. **{sec.get('title', '')}**" + (f": {sec['takeaway']}" if sec.get("takeaway") else "")
        out.append(textwrap.fill(line, width=100, subsequent_indent="   ", break_on_hyphens=False,
                                 break_long_words=False))
    out.append("")
    if data.get("sources"):
        out += ["## Draws on", ""] + [f"- `{x}`" for x in data["sources"]] + [""]
    out += ["## Changing it", "",
            fill(f"Edit `{data['slug']}.vis.json` and rebuild with the `visual` skill (`/visual update "
                 f"{data['slug']}`). This README, the {Path(fname).suffix.lstrip('.').upper()} and the index "
                 f"row are regenerated from the JSON, so never edit them by hand."
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
    unlisted = sorted(p.relative_to(vdir).as_posix() for p in found
                      if p.suffix in (".pdf", ".html") and p.relative_to(vdir).as_posix() not in listed)
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
    pb.add_argument("--format", choices=["pdf", "html"], required=True)
    pb.add_argument("--dir")
    pb.add_argument("--work")
    ls = sub.add_parser("list")
    ls.add_argument("--dir")
    ls.add_argument("--projects")
    ls.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.cmd == "validate":
        p = Path(a.data)
        errors, warns = validate(load_json(p), p.parent)
        for e in errors:
            print(f"ERROR  {e}")
        for x in warns:
            print(f"warn   {x}")
        print("valid" if not errors else f"{len(errors)} error(s)")
        return 1 if errors else 0
    if a.cmd == "build":
        return build(Path(a.data), a.work, not a.no_pdf, a.attempt)
    if a.cmd == "publish":
        return publish(Path(a.data), a.format, a.dir, a.work)
    if a.cmd == "list":
        return cmd_list(a.dir, a.projects, a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
