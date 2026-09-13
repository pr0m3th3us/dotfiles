#!/usr/bin/env python3
"""Open a built runbook in a headless browser and check it actually works.

A runbook that fails to render is a worse outcome than a plain markdown list,
and the failure is invisible from the source: a stray character in the data
block, a step id that collides, a table row that does not match its header. This
opens the real file in Chromium and exercises the parts a reader depends on.

    python3 scripts/verify_runbook.py My-Runbook.html

Checks, in order:
  1. The page renders and the console is clean.
  2. Every step in rb-data appears in the DOM, once.
  3. Ticks embedded in rb-state are reflected in the checkboxes and the counter.
  4. Ticking a box updates the counter, the progress bar and the phase bar.
  5. Dependency chips flip from "needs X" to "after X" when X is ticked.
  6. Filters narrow the list and the "only steps I must act on" filter matches
     the action/decide steps in the data.
  7. The save-copy round trip produces a file that reopens with the same step
     count and the same ticks.
  8. No horizontal overflow at 390px.

Requires: pip install playwright && python3 -m playwright install chromium
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sys.exit("playwright is not installed: pip install playwright && python3 -m playwright install chromium")

PASS, FAIL = "  ok   ", "  FAIL "
results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> bool:
    results.append((ok, label))
    print((PASS if ok else FAIL) + label + (f" — {detail}" if detail and not ok else ""))
    return ok


def extract_block(html: str, block_id: str) -> dict:
    m = re.search(
        r'<script id="' + block_id + r'" type="application/json">(.*?)</script>', html, re.S
    )
    if not m:
        sys.exit(f"No {block_id} block in the file.")
    return json.loads(m.group(1).replace("<\\/", "</"))


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = Path(sys.argv[1]).resolve()
    html = path.read_text(encoding="utf-8")
    data = extract_block(html, "rb-data")
    state = extract_block(html, "rb-state")

    steps = [s for p in data.get("phases") or [] for s in p.get("steps") or []]
    step_ids = [s["id"] for s in steps]
    actionable = [s["id"] for s in steps if s.get("kind", "action") in ("action", "decide")]
    ticked = sorted(k for k in (state.get("done") or {}) if k in set(step_ids))

    print(f"\n{path.name}: {len(data.get('phases') or [])} phases, {len(steps)} steps, "
          f"{len(ticked)} ticked in rb-state\n")

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(path.as_uri())
        page.wait_for_selector(".step, .fatal", timeout=15000)

        # 1. renders, console clean
        check(page.locator(".fatal").count() == 0, "page renders without a fatal data error")
        check(not errors, "console is clean", "; ".join(errors[:3]))

        # 2. every step present exactly once
        rendered = page.eval_on_selector_all(".step", "els => els.map(e => e.dataset.id)")
        check(len(rendered) == len(step_ids), "every step in the data is rendered",
              f"data has {len(step_ids)}, DOM has {len(rendered)}")
        check(len(set(rendered)) == len(rendered), "no duplicate step ids in the DOM")
        missing = set(step_ids) - set(rendered)
        check(not missing, "no step is missing from the DOM", f"missing: {sorted(missing)[:5]}")

        # every step shows a do-band and badges
        check(page.locator(".step .do").count() == len(step_ids), "every step has a 'do' band")
        check(page.locator(".step .badges").count() == len(step_ids), "every step has a badge row")

        # 3. embedded state is reflected
        checked = page.eval_on_selector_all(
            "[data-check]", "els => els.filter(e => e.checked).map(e => e.dataset.check)"
        )
        check(sorted(checked) == ticked, "embedded rb-state ticks are applied",
              f"expected {ticked}, got {sorted(checked)}")
        counter = page.inner_text("#progtext")
        check(counter.startswith(f"{len(ticked)} of {len(step_ids)}"),
              "progress counter matches the embedded state", counter)

        # 4. ticking updates the counter and the bars
        untouched = next((i for i in step_ids if i not in set(ticked)), None)
        if untouched:
            page.click(f'[data-check="{untouched}"]')
            page.wait_for_timeout(120)
            after = page.inner_text("#progtext")
            check(after.startswith(f"{len(ticked)+1} of {len(step_ids)}"),
                  "ticking a box increments the counter", after)
            width = page.eval_on_selector("#progbar", "e => e.style.width")
            check(width not in ("", "0%"), "the progress bar advances", f"width={width!r}")
            phase_of = next(p for p in data["phases"] for s in p.get("steps") or []
                            if s["id"] == untouched)
            pbar = page.eval_on_selector(f'[data-pbar="{phase_of["id"]}"]', "e => e.style.width")
            check(pbar not in ("", "0%"), "the phase bar advances", f"width={pbar!r}")
            page.click(f'[data-check="{untouched}"]')  # restore
            page.wait_for_timeout(120)

        # 5. dependency chips flip
        dep_step = next((s for s in steps if s.get("dependsOn")), None)
        if dep_step:
            dep = dep_step["dependsOn"][0]
            sel = f'.step[data-id="{dep_step["id"]}"] .b-dep[data-dep="{dep}"]'
            was_done = dep in (state.get("done") or {})
            if not was_done:
                check(page.inner_text(sel).strip().startswith("needs"),
                      f"unmet dependency renders as 'needs {dep}'", page.inner_text(sel))
                page.click(f'[data-check="{dep}"]')
                page.wait_for_timeout(120)
                check(page.inner_text(sel).strip().startswith("after"),
                      f"dependency chip flips to 'after {dep}' when it is ticked",
                      page.inner_text(sel))
                page.click(f'[data-check="{dep}"]')
                page.wait_for_timeout(120)
        else:
            check(True, "no dependsOn in this runbook — chip check skipped")

        # 6. filters
        visible = lambda: page.locator(".step:not(.hidden)").count()
        page.check("#f-actions")
        page.wait_for_timeout(120)
        check(visible() == len(actionable),
              "'only steps I must act on' matches the action/decide steps",
              f"expected {len(actionable)}, showing {visible()}")
        page.uncheck("#f-actions")
        page.wait_for_timeout(120)
        check(visible() == len(step_ids), "clearing the filter restores every step")

        first_phase = data["phases"][0]
        page.select_option("#f-phase", first_phase["id"])
        page.wait_for_timeout(120)
        check(visible() == len(first_phase.get("steps") or []),
              "the phase filter narrows to that phase's steps",
              f"expected {len(first_phase.get('steps') or [])}, showing {visible()}")
        page.select_option("#f-phase", "")
        page.wait_for_timeout(120)

        page.fill("#q", "zzzzz-no-such-step-zzzzz")
        page.wait_for_timeout(150)
        check(visible() == 0 and "No steps match" in page.inner_text("#emptymsg"),
              "a search with no matches shows the empty message")
        page.fill("#q", "")
        page.wait_for_timeout(150)

        # 7. save-copy round trip
        target = step_ids[-1]
        if target in (state.get("done") or {}):
            page.click(f'[data-check="{target}"]')  # untick so the set changes
            page.wait_for_timeout(100)
        page.click(f'[data-check="{target}"]')
        page.wait_for_timeout(120)
        expect_ticks = sorted(page.eval_on_selector_all(
            "[data-check]", "els => els.filter(e => e.checked).map(e => e.dataset.check)"))
        with page.expect_download(timeout=15000) as dl:
            page.click("#btn-save")
        saved = Path(tempfile.mkdtemp()) / "saved.html"
        dl.value.save_as(saved)
        check(saved.stat().st_size > 1000, "save-copy produces a non-trivial file",
              f"{saved.stat().st_size} bytes")

        ctx2 = browser.new_context(viewport={"width": 1280, "height": 900})
        p2 = ctx2.new_page()          # fresh context: no localStorage carry-over
        err2: list[str] = []
        p2.on("pageerror", lambda e: err2.append(str(e)))
        p2.goto(saved.as_uri())
        p2.wait_for_selector(".step, .fatal", timeout=15000)
        check(p2.locator(".fatal").count() == 0 and not err2,
              "the saved copy reopens without errors", "; ".join(err2[:2]))
        check(p2.locator(".step").count() == len(step_ids),
              "the saved copy has the same step count",
              f"{p2.locator('.step').count()} vs {len(step_ids)}")
        reopened = sorted(p2.eval_on_selector_all(
            "[data-check]", "els => els.filter(e => e.checked).map(e => e.dataset.check)"))
        check(reopened == expect_ticks, "the saved copy reopens with the same ticks",
              f"expected {expect_ticks}, got {reopened}")
        ctx2.close()

        # 8. no horizontal overflow on a narrow phone
        ctx3 = browser.new_context(viewport={"width": 390, "height": 844})
        p3 = ctx3.new_page()
        p3.goto(path.as_uri())
        p3.wait_for_selector(".step", timeout=15000)
        p3.click("#btn-expand")       # worst case: everything open
        p3.wait_for_timeout(250)
        overflow = p3.evaluate(
            "() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
        check(overflow <= 0, "no horizontal overflow at 390px with all details expanded",
              f"overflows by {overflow}px")
        ctx3.close()

        browser.close()

    failed = [label for ok, label in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("failed: " + "; ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
