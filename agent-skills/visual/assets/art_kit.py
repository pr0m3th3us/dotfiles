"""Art kit: vector illustration helpers for visual explainers.

Write a short script at art/draw.py in the work folder, run from there, compose a scene from these parts and
your own shapes, and save it to art/<name>.svg. Point the data at it with {"type": "svg", "file": "art/<name>.svg"}.

    import sys; sys.path.insert(0, "<skill>/assets")
    from art_kit import *
    c = Canvas(900, 620)
    c.add(soft_shadow(450, 560, 300, 40), iso_box(450, 420, 200, 200, 90, "accent"), label(450, 200, "Hello"))
    c.save("art/hello.svg")

Every colour comes from the page's palette through a tone name: accent good warn amber violet sky rose grey.
Each tone has three steps (`-l`, plain, `-d`): light for lit faces, plain for the main face, dark for shade.
"""

from __future__ import annotations

import math
from pathlib import Path

ISO = (math.cos(math.radians(30)), math.sin(math.radians(30)))


def _f(n: float) -> str:
    return f"{n:.1f}".rstrip("0").rstrip(".")


def _pts(points) -> str:
    return " ".join(f"{_f(x)},{_f(y)}" for x, y in points)


def _attrs(kw: dict) -> str:
    out = []
    for k, v in kw.items():
        if v is None:
            continue
        out.append(f'{k.rstrip("_").replace("_", "-")}="{v}"')
    return (" " + " ".join(out)) if out else ""


class Canvas:
    """A scene with a viewBox. Parts are added back to front."""

    def __init__(self, w: float, h: float):
        self.w, self.h, self.parts = w, h, []

    def add(self, *parts: str) -> "Canvas":
        self.parts.extend(parts)
        return self

    def svg(self) -> str:
        return (f'<svg viewBox="0 0 {_f(self.w)} {_f(self.h)}" xmlns="http://www.w3.org/2000/svg">'
                + "".join(self.parts) + "</svg>")

    def save(self, path: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.svg(), encoding="utf-8")


# ---- primitives ----------------------------------------------------------------

def rect(x, y, w, h, cls="f-accent", rx=0, **kw) -> str:
    return f'<rect x="{_f(x)}" y="{_f(y)}" width="{_f(w)}" height="{_f(h)}" rx="{_f(rx)}" class="{cls}"{_attrs(kw)}/>'


def circle(x, y, r, cls="f-accent", **kw) -> str:
    return f'<circle cx="{_f(x)}" cy="{_f(y)}" r="{_f(r)}" class="{cls}"{_attrs(kw)}/>'


def ellipse(x, y, rx, ry, cls="f-accent", **kw) -> str:
    return f'<ellipse cx="{_f(x)}" cy="{_f(y)}" rx="{_f(rx)}" ry="{_f(ry)}" class="{cls}"{_attrs(kw)}/>'


def poly(points, cls="f-accent", **kw) -> str:
    return f'<polygon points="{_pts(points)}" class="{cls}"{_attrs(kw)}/>'


def path(d, cls="none s-fg", width=2, **kw) -> str:
    return f'<path d="{d}" class="{cls}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"{_attrs(kw)}/>'


def line(x1, y1, x2, y2, cls="s-fg", width=2, **kw) -> str:
    return (f'<line x1="{_f(x1)}" y1="{_f(y1)}" x2="{_f(x2)}" y2="{_f(y2)}" class="{cls}" '
            f'stroke-width="{width}" stroke-linecap="round"{_attrs(kw)}/>')


def label(x, y, text, size=18, weight=700, anchor="middle", cls=None, display=False) -> str:
    """Real text in the art. Keep it to one to four words; explanations belong in notes."""
    style = f"font-size:{size}px;font-weight:{weight}" + (";font-family:var(--display)" if display else "")
    c = f' class="{cls}"' if cls else ""
    safe = str(text).replace("&", "&amp;").replace("<", "&lt;")
    return f'<text x="{_f(x)}" y="{_f(y)}" text-anchor="{anchor}" style="{style}"{c}>{safe}</text>'


def group(*parts, depth=None, step=None, cls=None, transform=None) -> str:
    """data-depth makes a parallax plane in the HTML; data-step reveals it at that scrolly step."""
    a = _attrs({"data_depth": depth, "data_step": step, "class_": cls, "transform": transform})
    return f"<g{a}>" + "".join(parts) + "</g>"


def soft_shadow(x, y, rx, ry, opacity=1) -> str:
    """A vector ground shadow. SVG filters print as low-resolution bitmaps; use this instead."""
    return f'<ellipse cx="{_f(x)}" cy="{_f(y)}" rx="{_f(rx)}" ry="{_f(ry)}" fill="url(#vg-shadow)" opacity="{opacity}"/>'


def glow(x, y, r, opacity=.6) -> str:
    return f'<circle cx="{_f(x)}" cy="{_f(y)}" r="{_f(r)}" fill="url(#vg-glow)" opacity="{opacity}"/>'


def flow_path(d, cls="s-accent", width=3) -> str:
    """A line with data moving along it in the HTML; a dashed line in print."""
    return path(d, f"none {cls} m-flow", width)


# ---- isometric: the projection behind cutaways and exploded views ---------------

def iso(x, y, z=0, ox=0, oy=0) -> tuple[float, float]:
    """World (x right-back, y left-back, z up) to screen, at the true 30-degree isometric angle."""
    return ox + (x - y) * ISO[0], oy + (x + y) * ISO[1] - z


def iso_box(cx, cy, w, d, h, tone="accent", ghost=False, inset=True) -> str:
    """A shaded box whose ground-front corner sits at (cx, cy) on screen."""
    top = [iso(0, 0, h), iso(-w, 0, h), iso(-w, -d, h), iso(0, -d, h)]
    left = [iso(0, 0, h), iso(-w, 0, h), iso(-w, 0, 0), iso(0, 0, 0)]
    right = [iso(0, 0, h), iso(0, -d, h), iso(0, -d, 0), iso(0, 0, 0)]
    shift = lambda ps: [(x + cx, y + cy) for x, y in ps]
    top, left, right = shift(top), shift(left), shift(right)
    if ghost:
        s = 'stroke="var(--tone-on)" stroke-width="2" stroke-dasharray="7 6" fill="var(--fg)" fill-opacity="'
        return (f'<polygon points="{_pts(left)}" {s}.05"/><polygon points="{_pts(right)}" {s}.03"/>'
                f'<polygon points="{_pts(top)}" {s}.1"/>')
    edge = 'stroke="rgba(0,0,0,.2)" stroke-width="1" stroke-linejoin="round"'
    out = (f'<polygon points="{_pts(left)}" class="f-{tone}" {edge}/>'
           f'<polygon points="{_pts(right)}" class="f-{tone}-d" {edge}/>'
           f'<polygon points="{_pts(top)}" class="f-{tone}-l" {edge}/>')
    if inset:
        k = .1
        ins = [iso(-w * k, -d * k, h), iso(-w * (1 - k), -d * k, h), iso(-w * (1 - k), -d * (1 - k), h), iso(-w * k, -d * (1 - k), h)]
        out += f'<polygon points="{_pts(shift(ins))}" fill="none" stroke="#fff" stroke-opacity=".55" stroke-width="1.5"/>'
    return out


# ---- objects: drawn with three-tone shading, so they read as things, not boxes ------

def filmstrip(x, y, n, fw=56, fh=74, analysed=None, tone="accent", base="grey", gap=8) -> str:
    """A strip of n frames. `analysed` is a set of indexes drawn lit; the rest stay dim."""
    analysed = set(range(n)) if analysed is None else set(analysed)
    w = n * (fw + gap) + gap
    out = [rect(x, y, w, fh + 44, "f-night2", rx=8)]
    step = 20
    for i in range(int(w // step)):
        out.append(rect(x + 6 + i * step, y + 7, 10, 9, "f-white", rx=2, opacity=".82"))
        out.append(rect(x + 6 + i * step, y + fh + 28, 10, 9, "f-white", rx=2, opacity=".82"))
    for i in range(n):
        fx = x + gap + i * (fw + gap)
        if i in analysed:
            out.append(rect(fx, y + 22, fw, fh, f"f-{tone}-l", rx=3))
            out.append(poly([(fx, y + 22 + fh), (fx + fw * .45, y + 22 + fh * .45), (fx + fw, y + 22 + fh)], f"f-{tone}"))
            out.append(circle(fx + fw * .72, y + 22 + fh * .26, fw * .1, "f-white"))
        else:
            out.append(rect(fx, y + 22, fw, fh, f"f-{base}-d", rx=3, opacity=".55"))
    return "".join(out)


def document(x, y, w=90, h=116, tone="accent", lines=5) -> str:
    fold = w * .24
    body = [(x, y), (x + w - fold, y), (x + w, y + fold), (x + w, y + h), (x, y + h)]
    out = [soft_shadow(x + w / 2, y + h + 4, w * .62, 11), poly(body, "f-white", stroke="rgba(0,0,0,.18)", stroke_width="1"),
           poly([(x + w - fold, y), (x + w, y + fold), (x + w - fold, y + fold)], f"f-{tone}-l")]
    out.append(rect(x + w * .12, y + h * .13, w * .42, h * .08, f"f-{tone}", rx=2))
    for i in range(lines):
        out.append(rect(x + w * .12, y + h * (.3 + i * .12), w * (.76 if i % 3 else .6), h * .045, "f-grey-l", rx=1.5))
    return "".join(out)


def laptop(x, y, w=240, tone="accent", screen=None) -> str:
    h = w * .62
    out = [soft_shadow(x + w / 2, y + h + w * .07, w * .66, w * .06),
           rect(x + w * .04, y, w * .92, h, "f-night2", rx=10),
           rect(x + w * .07, y + h * .05, w * .86, h * .86, f"f-{tone}-d", rx=3)]
    if screen:
        out.append(screen)
    out += [poly([(x, y + h), (x + w, y + h), (x + w * 1.04, y + h + w * .05), (x - w * .04, y + h + w * .05)], "f-grey-l"),
            rect(x + w * .4, y + h, w * .2, w * .018, "f-grey", rx=2)]
    return "".join(out)


def gear(x, y, r, tone="amber", teeth=10, spin=False) -> str:
    pts = []
    for i in range(teeth * 4):
        a = 2 * math.pi * i / (teeth * 4)
        rr = r if i % 4 in (0, 1) else r * .78
        pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
    cls = f"f-{tone}" + (" m-spin" if spin else "")
    return (f'<g class="{"m-spin" if spin else ""}"><polygon points="{_pts(pts)}" class="f-{tone}" stroke="rgba(0,0,0,.2)"/>'
            + circle(x, y, r * .58, f"f-{tone}-l") + circle(x, y, r * .26, f"f-{tone}-d") + "</g>")


def cloud(x, y, s=1, tone="sky") -> str:
    return (circle(x, y, 34 * s, f"f-{tone}-l") + circle(x + 44 * s, y - 16 * s, 44 * s, f"f-{tone}-l")
            + circle(x + 96 * s, y, 32 * s, f"f-{tone}-l") + rect(x - 34 * s, y, 162 * s, 34 * s, f"f-{tone}-l", rx=17 * s))


def person(x, y, s=1, tone="accent", skin="amber") -> str:
    """A simple flat figure, standing. x, y is the point between the feet."""
    return (soft_shadow(x, y + 2 * s, 30 * s, 7 * s)
            + rect(x - 14 * s, y - 40 * s, 12 * s, 40 * s, "f-night2", rx=5 * s) + rect(x + 2 * s, y - 40 * s, 12 * s, 40 * s, "f-night2", rx=5 * s)
            + rect(x - 18 * s, y - 88 * s, 36 * s, 54 * s, f"f-{tone}", rx=12 * s)
            + rect(x - 18 * s, y - 88 * s, 13 * s, 54 * s, f"f-{tone}-l", rx=6 * s)
            + circle(x, y - 106 * s, 16 * s, f"f-{skin}-l"))


def magnifier(x, y, r=46, tone="accent", tilt=38) -> str:
    a = math.radians(tilt)
    hx, hy = x + r * math.cos(a), y + r * math.sin(a)
    ex, ey = x + r * 2.1 * math.cos(a), y + r * 2.1 * math.sin(a)
    return (line(hx, hy, ex, ey, "s-fg", r * .24) + circle(x, y, r, "f-white", opacity=".22")
            + f'<circle cx="{_f(x)}" cy="{_f(y)}" r="{_f(r)}" fill="none" class="s-{tone}" stroke-width="{_f(r * .17)}"/>'
            + path(f"M{_f(x - r * .55)} {_f(y - r * .2)} A{_f(r * .6)} {_f(r * .6)} 0 0 1 {_f(x - r * .1)} {_f(y - r * .58)}", "none s-white", r * .08))


def server(x, y, w=110, units=4, tone="sky") -> str:
    u = 30
    out = [soft_shadow(x + w / 2, y + units * u + 4, w * .62, 12)]
    for i in range(units):
        yy = y + i * u
        out.append(rect(x, yy, w, u - 3, "f-night2", rx=4))
        out.append(rect(x + 8, yy + 8, w * .46, 10, f"f-{tone}-d", rx=2))
        out.append(circle(x + w - 14, yy + 13, 4, "f-good m-twinkle"))
        out.append(circle(x + w - 28, yy + 13, 4, f"f-{tone}-l"))
    return "".join(out)


def checkmark(x, y, r=22, tone="good") -> str:
    return circle(x, y, r, f"f-{tone}") + path(f"M{_f(x - r * .45)} {_f(y)} L{_f(x - r * .1)} {_f(y + r * .36)} L{_f(x + r * .5)} {_f(y - r * .36)}", "none s-white", r * .2)


def crossmark(x, y, r=22, tone="warn") -> str:
    k = r * .4
    return circle(x, y, r, f"f-{tone}") + line(x - k, y - k, x + k, y + k, "s-white", r * .2) + line(x + k, y - k, x - k, y + k, "s-white", r * .2)


def tree(x, y, s=1, tone="good") -> str:
    """A conifer standing at x, y."""
    return (ellipse(x, y + 2 * s, 20 * s, 5 * s, "f-night2", opacity=".35") + rect(x - 3.5 * s, y - 16 * s, 7 * s, 18 * s, "f-grey-d")
            + poly([(x - 21 * s, y - 12 * s), (x, y - 44 * s), (x + 21 * s, y - 12 * s)], f"f-{tone}-d")
            + poly([(x - 16 * s, y - 30 * s), (x, y - 58 * s), (x + 16 * s, y - 30 * s)], f"f-{tone}")
            + poly([(x, y - 58 * s), (x + 16 * s, y - 30 * s), (x, y - 30 * s)], f"f-{tone}-d", opacity=".5"))


def signpost(x, y, text, tone="accent", size=26, w=None, h=None) -> str:
    """A post with a board and real text on it; the board grows to fit the words."""
    w = w or (len(text) * size * .6 + 26)
    h = h or size * 1.7
    return (rect(x - 4, y - h - 42, 8, h + 44, "f-grey-d", rx=2) + rect(x - w / 2 + 3, y - h - 56 + 4, w, h, "f-night2", rx=7, opacity=".4")
            + rect(x - w / 2, y - h - 56, w, h, f"f-{tone}-d", rx=7) + rect(x - w / 2, y - h - 56, w, h * .22, f"f-{tone}", rx=5)
            + f'<text x="{_f(x)}" y="{_f(y - h - 56 + h * .7)}" text-anchor="middle" style="font-size:{size}px;font-weight:700;fill:#fff;font-family:var(--display)">{text}</text>')


def road(x0, y0, x1, y1, w0, w1, cls="f-grey-d", bend=0) -> str:
    """A tapering road from a wide near end to a narrow far end, curved by `bend`."""
    mx, my = (x0 + x1) / 2 + bend, (y0 + y1) / 2
    d = (f"M{_f(x0 - w0)} {_f(y0)} Q{_f(mx - (w0 + w1) / 2)} {_f(my)} {_f(x1 - w1)} {_f(y1)} "
         f"L{_f(x1 + w1)} {_f(y1)} Q{_f(mx + (w0 + w1) / 2)} {_f(my)} {_f(x0 + w0)} {_f(y0)} Z")
    return f'<path d="{d}" class="{cls}"/>'
