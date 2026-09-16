#!/usr/bin/env python3
"""Build a runbook HTML file by injecting rb-data and rb-state into the scaffold.

The scaffold (assets/runbook-template.html) is presentation only and never
changes per runbook. The content lives in a data JSON file, the ticks live in a
state JSON file, and this script is the only thing that puts them together — so
authoring a runbook never means editing markup.

    python3 scripts/build_runbook.py --data my-rb-data.json --out My-Runbook.html
    python3 scripts/build_runbook.py --data my-rb-data.json --state progress.json --out My-Runbook.html
    python3 scripts/build_runbook.py --data my-rb-data.json --out My-Runbook.html --pdf My-Runbook.pdf --booklet
    python3 scripts/build_runbook.py --data my-rb-data.json --validate-only

Validation runs on every build. Structural problems (a missing step id, a
dependency pointing at a step that does not exist, a bad `kind`) are errors and
stop the build; smells that a human should look at are warnings and do not.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "runbook-template.html"

VALID_KINDS = {"action", "decide", "info", "done", "blocked"}
VALID_PRIORITIES = {1, 2, 3}
VALID_CALLOUT_KINDS = {"warn", "info", "good"}


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #

def validate(data: dict, state: dict) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Errors mean the page would render wrong."""
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(data, dict):
        return ["rb-data must be a JSON object"], []

    for field in ("id", "title"):
        if not data.get(field):
            errors.append(f"top level: `{field}` is required")

    if data.get("currency") and data["currency"] not in {
        "USD", "INR", "EUR", "GBP", "AUD", "CAD", "JPY"
    }:
        warnings.append(
            f"top level: currency {data['currency']!r} has no symbol in the renderer; "
            "amounts will show unprefixed"
        )

    phases = data.get("phases") or []
    if not phases:
        warnings.append("top level: no phases — the page will render an empty checklist")

    step_ids: dict[str, str] = {}   # step id -> phase id
    phase_ids: set[str] = set()
    all_deps: list[tuple[str, str]] = []

    for pi, p in enumerate(phases):
        where = f"phase[{pi}]"
        pid = p.get("id")
        if not pid:
            errors.append(f"{where}: missing `id`")
        elif pid in phase_ids:
            errors.append(f"{where}: duplicate phase id {pid!r}")
        else:
            phase_ids.add(pid)
        if not p.get("num"):
            warnings.append(f"{where} ({pid}): missing `num` — the phase header will read 'PHASE '")
        if not (p.get("title") or p.get("titleText")):
            errors.append(f"{where} ({pid}): missing `title`")
        if not p.get("verification"):
            warnings.append(
                f"{where} ({pid}): no phase `verification` gate — a broken phase will be "
                "discovered several phases later"
            )

        steps = p.get("steps") or []
        if not steps:
            warnings.append(f"{where} ({pid}): no steps")

        for si, s in enumerate(steps):
            sw = f"phase[{pi}].step[{si}]"
            sid = s.get("id")
            if not sid:
                errors.append(f"{sw}: missing `id` — ids are the progress keys")
                continue
            if sid in step_ids:
                errors.append(f"{sw}: duplicate step id {sid!r}")
            step_ids[sid] = pid

            if not s.get("title"):
                errors.append(f"{sw} ({sid}): missing `title`")

            kind = s.get("kind")
            if kind is None:
                errors.append(
                    f"{sw} ({sid}): missing `kind` — readers cannot tell whether to act"
                )
            elif kind not in VALID_KINDS:
                errors.append(
                    f"{sw} ({sid}): kind {kind!r} is not one of {sorted(VALID_KINDS)}"
                )

            if not s.get("do"):
                errors.append(
                    f"{sw} ({sid}): missing `do` — every step must say plainly what to do, "
                    "or that there is nothing to do"
                )

            pri = s.get("priority")
            if pri is None:
                warnings.append(f"{sw} ({sid}): no `priority`; defaults to 2 (Recommended)")
            elif pri not in VALID_PRIORITIES:
                errors.append(f"{sw} ({sid}): priority must be 1, 2 or 3, got {pri!r}")

            if "minutes" not in s:
                warnings.append(f"{sw} ({sid}): no `minutes`; it contributes nothing to the budget")

            cost = s.get("cost")
            if cost is not None and not isinstance(cost.get("amount"), (int, float)):
                errors.append(f"{sw} ({sid}): cost.amount must be a number")

            for c in s.get("callouts") or []:
                if c.get("kind") and c["kind"] not in VALID_CALLOUT_KINDS:
                    warnings.append(
                        f"{sw} ({sid}): callout kind {c['kind']!r} unknown, renders as info"
                    )

            t = s.get("table")
            if t:
                head_len = len(t.get("head") or [])
                for ri, row in enumerate(t.get("rows") or []):
                    if head_len and len(row) != head_len:
                        errors.append(
                            f"{sw} ({sid}): table row {ri} has {len(row)} cells, "
                            f"header has {head_len}"
                        )

            for dep in s.get("dependsOn") or []:
                all_deps.append((sid, dep))

    for sid, dep in all_deps:
        if dep not in step_ids:
            errors.append(
                f"step {sid}: dependsOn {dep!r} does not match any step id — "
                "the chip would never clear"
            )
        elif step_ids[dep] == step_ids[sid]:
            warnings.append(
                f"step {sid}: dependsOn {dep!r} is in the same phase; steps within a "
                "phase are already sequential"
            )

    for p in phases:
        for dep in p.get("dependsOn") or []:
            if dep not in phase_ids:
                errors.append(f"phase {p.get('id')}: dependsOn {dep!r} is not a phase id")

    # state must line up with data, or someone's ticks land nowhere
    done = (state or {}).get("done") or {}
    if not isinstance(done, dict):
        errors.append("rb-state: `done` must be an object of {stepId: true}")
    else:
        orphans = [k for k in done if k not in step_ids]
        if orphans:
            warnings.append(
                f"rb-state: {len(orphans)} tick(s) reference steps that no longer exist "
                f"({', '.join(sorted(orphans)[:6])}{'…' if len(orphans) > 6 else ''})"
            )
    if state is not None and "updatedAt" not in (state or {}):
        warnings.append("rb-state: no `updatedAt`; a stale browser copy will silently win")

    return errors, warnings


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #

def _json_for_html(obj) -> str:
    """Compact JSON safe to sit inside a <script> element."""
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    # A literal </script> inside the JSON would close the block early.
    return text.replace("</", "<\\/")


def _replace_block(html: str, block_id: str, payload: str) -> str:
    pattern = re.compile(
        r'(<script id="' + re.escape(block_id) + r'" type="application/json">)(.*?)(</script>)',
        re.S,
    )
    if not pattern.search(html):
        raise SystemExit(f"Template has no <script id=\"{block_id}\"> block.")
    return pattern.sub(lambda m: m.group(1) + "\n" + payload + "\n" + m.group(3), html, count=1)


def build(data: dict, state: dict, template: Path) -> str:
    html = template.read_text(encoding="utf-8")
    html = _replace_block(html, "rb-data", _json_for_html(data))
    html = _replace_block(html, "rb-state", _json_for_html(state))
    title = re.sub(r"<[^>]+>", "", str(data.get("title") or "Runbook"))
    html = re.sub(
        r"<title>.*?</title>",
        "<title>" + title.replace("&", "&amp;").replace("<", "&lt;") + "</title>",
        html,
        count=1,
        flags=re.S,
    )
    return html


def export_pdf(html_path: Path, pdf_path: Path, booklet: bool = False) -> int:
    """Render the built HTML file to PDF via headless Chromium."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(
            "error: PDF export requires playwright (pip install playwright && python3 -m playwright install chromium)",
            file=sys.stderr,
        )
        return 1

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
        page.emulate_media(media="print")
        page.wait_for_timeout(500)

        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            prefer_css_page_size=True,
        )
        browser.close()

    page_count = None
    try:
        import pymupdf as fitz
        doc = fitz.open(str(pdf_path))
        page_count = len(doc)
        doc.close()
    except Exception:
        try:
            import fitz
            doc = fitz.open(str(pdf_path))
            page_count = len(doc)
            doc.close()
        except Exception:
            pass

    msg = f"wrote {pdf_path}"
    if page_count is not None:
        msg += f" ({page_count} pages"
        if booklet:
            if page_count % 4 == 0:
                msg += ", perfect multiple of 4 for booklet printing"
            else:
                rem = 4 - (page_count % 4)
                msg += f", warning: not a multiple of 4 — booklet mode will add {rem} blank page(s)"
        msg += ")"
    print(msg)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="rb-data JSON file (the runbook content)")
    ap.add_argument("--state", default=None, help="rb-state JSON file (ticks); defaults to empty")
    ap.add_argument("--out", default=None, help="output HTML path")
    ap.add_argument("--pdf", default=None, help="output PDF path (rendered via headless Chromium)")
    ap.add_argument("--booklet", action="store_true", help="enable booklet mode (A4 print layout, multiple-of-4 page check)")
    ap.add_argument("--template", default=str(DEFAULT_TEMPLATE), help="scaffold to inject into")
    ap.add_argument("--validate-only", action="store_true", help="check the data and stop")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = ap.parse_args()

    data = json.loads(Path(args.data).read_text(encoding="utf-8"))
    state = (
        json.loads(Path(args.state).read_text(encoding="utf-8"))
        if args.state
        else {"done": {}, "updatedAt": 0}
    )
    state.setdefault("done", {})
    state.setdefault("updatedAt", 0)

    errors, warnings = validate(data, state)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    if errors or (args.strict and warnings):
        print(f"\n{len(errors)} error(s), {len(warnings)} warning(s) — not building.", file=sys.stderr)
        return 1

    n_steps = sum(len(p.get("steps") or []) for p in data.get("phases") or [])
    if args.validate_only:
        print(f"ok: {len(data.get('phases') or [])} phases, {n_steps} steps, {len(warnings)} warning(s)")
        return 0

    if not args.out and not args.pdf:
        print("error: --out or --pdf is required unless --validate-only", file=sys.stderr)
        return 1

    html = build(data, state, Path(args.template))

    temp_html: Path | None = None
    if args.out:
        out_html_path = Path(args.out)
        out_html_path.write_text(html, encoding="utf-8")
        print(
            f"wrote {args.out} — {len(data.get('phases') or [])} phases, {n_steps} steps, "
            f"{len(state['done'])} ticked, {len(warnings)} warning(s)"
        )
    else:
        import tempfile
        t = tempfile.NamedTemporaryFile("w", suffix=".html", delete=False, encoding="utf-8")
        t.write(html)
        t.close()
        temp_html = Path(t.name)
        out_html_path = temp_html

    if args.pdf:
        pdf_res = export_pdf(out_html_path, Path(args.pdf), booklet=args.booklet)
        if temp_html:
            temp_html.unlink(missing_ok=True)
        if pdf_res != 0:
            return pdf_res

    return 0


if __name__ == "__main__":
    sys.exit(main())
