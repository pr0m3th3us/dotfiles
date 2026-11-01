"""Art for the sample visual. Run from this folder: python3 draw.py"""
import math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from art_kit import *


def wave(x, y, w, amp, cycles, cls, width=5, phase=0, dash=None):
    pts = []
    for i in range(121):
        t = i / 120
        pts.append(f"{x + w * t:.1f} {y + amp * math.sin(t * cycles * 2 * math.pi + phase):.1f}")
    return f'<path d="M{" L".join(pts)}" class="none {cls}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"' + (f' stroke-dasharray="{dash}"' if dash else "") + "/>"


def headphones(cx, cy, s=1):
    o = [soft_shadow(cx, cy + 300 * s, 300 * s, 34 * s)]
    o.append(f'<path d="M{cx - 220 * s} {cy + 40 * s} C{cx - 240 * s} {cy - 300 * s} {cx + 240 * s} {cy - 300 * s} {cx + 220 * s} {cy + 40 * s}" fill="none" class="s-accent-d" stroke-width="{46 * s}" stroke-linecap="round"/>')
    o.append(f'<path d="M{cx - 220 * s} {cy + 40 * s} C{cx - 240 * s} {cy - 300 * s} {cx + 240 * s} {cy - 300 * s} {cx + 220 * s} {cy + 40 * s}" fill="none" class="s-accent" stroke-width="{30 * s}" stroke-linecap="round"/>')
    for side in (-1, 1):
        x = cx + side * 225 * s
        o += [rect(x - 92 * s, cy - 10 * s, 184 * s, 250 * s, "f-night2", rx=70 * s), rect(x - 78 * s, cy + 4 * s, 156 * s, 222 * s, "f-accent", rx=60 * s),
              rect(x - 78 * s, cy + 4 * s, 62 * s, 222 * s, "f-accent-l", rx=40 * s, opacity=".45"), circle(x, cy + 115 * s, 46 * s, "f-accent-d"), circle(x - 12 * s, cy + 100 * s, 18 * s, "f-accent-l", opacity=".7"),
              rect(x - 28 * s, cy + 196 * s, 56 * s, 10 * s, "f-amber", rx=5 * s)]
    return "".join(o)


def cover():
    c = Canvas(1000, 800)
    c.add(group(circle(180, 180, 90, "f-sky-l", opacity=".5"), circle(860, 560, 130, "f-amber-l", opacity=".4"), depth=.2))
    c.add(group(wave(0, 620, 1000, 46, 7, "s-warn", 7), wave(0, 620, 1000, 46, 7, "s-sky", 7, math.pi, "12 10"), depth=.5))
    c.add(group(headphones(500, 300, 1), depth=.9))
    c.save("art/cover.svg")


def cancel():
    c = Canvas(1000, 640)
    rows = [(110, "Outside noise", "s-warn", 0, 1, "f-warn-d"), (290, "The opposite wave", "s-sky", math.pi, 2, "f-sky-d")]
    for y, name, cls, ph, step, tone in rows:
        c.add(group(label(20, y - 62, name, 34, 700, "start", display=True), wave(20, y, 960, 40, 5, cls, 8, ph), step=step))
    c.add(group(label(20, 420, "What reaches your ear", 34, 700, "start", display=True), line(20, 480, 980, 480, "s-good", 8), wave(20, 480, 960, 6, 5, "s-good", 3), step=3))
    c.add(group(rect(330, 540, 340, 76, "f-good-d", rx=38), label(500, 592, "Near silence", 42, 700, display=True, cls="f-white"), step=4))
    c.save("art/cancel.svg")


def cabin():
    c = Canvas(1600, 900)
    c.add(rect(0, 0, 1600, 900, "f-night"), rect(0, 640, 1600, 260, "f-night2"))
    for i in range(7):
        x = 110 + i * 220
        c.add(rect(x, 180, 120, 170, "f-sky-d", rx=52), rect(x + 10, 192, 100, 146, "f-sky-l", rx=46, opacity=".7"), cloud(x + 30, 290, .26, "grey"))
    for i in range(6):
        x = 170 + i * 250
        c.add(rect(x, 400, 160, 340, "f-accent-d", rx=26), rect(x, 400, 56, 340, "f-accent", rx=20), rect(x + 26, 370, 108, 66, "f-grey-l", rx=16))
    c.save("art/cabin.svg")


def passive():
    c = Canvas(520, 380)
    c.add(rect(250, 60, 60, 260, "f-grey", rx=14), rect(250, 60, 22, 260, "f-grey-l", rx=10), wave(10, 130, 240, 44, 3, "s-warn", 6), wave(310, 130, 200, 14, 3, "s-warn", 4))
    c.add(wave(10, 250, 240, 18, 9, "s-amber", 5), wave(310, 250, 200, 2, 9, "s-amber", 3))
    c.add(label(130, 60, "Bass", 32, 700), label(130, 322, "Voices", 32, 700))
    c.save("art/passive.svg")


def active():
    c = Canvas(520, 380)
    c.add(circle(280, 190, 70, "f-sky"), circle(262, 172, 34, "f-sky-l", opacity=".6"), wave(10, 130, 200, 44, 3, "s-warn", 6), wave(350, 130, 160, 3, 3, "s-warn", 3))
    c.add(wave(10, 250, 200, 18, 9, "s-amber", 5), wave(350, 250, 160, 14, 9, "s-amber", 4))
    c.add(label(280, 202, "Chip", 34, 700), label(110, 60, "Bass", 32, 700), label(110, 322, "Voices", 32, 700))
    c.save("art/active.svg")


for f in (cover, cancel, cabin, passive, active):
    f()
