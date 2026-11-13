#!/usr/bin/env python3
"""Build the SVG artwork for the profile README.

Every piece of text is shaped with HarfBuzz and written out as outlines, so the
page looks the same on any machine (an SVG shown through <img> cannot load
fonts). Each drawing is written twice, for GitHub's light and dark themes.

    pip install fonttools uharfbuzz
    python scripts/build.py

Fonts: Junicode and Geist (both open licences), looked up in FONT_DIRS.
"""
from __future__ import annotations

import math
import os
import random
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(os.environ.get("OUT_DIR", ROOT / "assets"))
# FREEZE=6 renders every animation stopped at 6 s, for checking a still frame
FREEZE = os.environ.get("FREEZE")
FONT_DIRS = [ROOT / "fonts", Path.home() / "Library" / "Fonts"]


# ----------------------------------------------------------------- type

def _num(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


GLYPHS: dict[str, str] = {}  # id -> outline in font units, for the file being built


class Face:
    count = 0

    def __init__(self, filename: str):
        self.key = "abcdefgh"[Face.count]
        Face.count += 1
        path = next(d / filename for d in FONT_DIRS if (d / filename).exists())
        self.tt = TTFont(str(path))
        self.glyphs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.upm = self.tt["head"].unitsPerEm
        self.hb = hb.Font(hb.Face(path.read_bytes()))

    def shape(self, s):
        buf = hb.Buffer()
        buf.add_str(s)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, {})
        return buf

    def width(self, s, size, tracking=0.0):
        n = self.shape(s).glyph_positions
        return sum(p.x_advance for p in n) * size / self.upm + tracking * (len(n) - 1)

    def set(self, s, size, x, y, fill, anchor="start", tracking=0.0, extra=""):
        """Return (svg, width) for `s` set at `size` px with its baseline at (x, y)."""
        buf = self.shape(s)
        k = size / self.upm
        width = self.width(s, size, tracking)
        x -= {"start": 0, "middle": width / 2, "end": width}[anchor]
        uses, cx = [], 0.0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            name = self.order[info.codepoint]
            gid = f"{self.key}{info.codepoint:x}"
            if gid not in GLYPHS:
                pen = SVGPathPen(self.glyphs, ntos=_num)
                self.glyphs[name].draw(pen)
                GLYPHS[gid] = pen.getCommands()
            if GLYPHS[gid]:
                gx, gy = cx + pos.x_offset, pos.y_offset
                uses.append(f'<use href="#{gid}"' + (f' x="{_num(gx)}"' if gx else "") + (f' y="{_num(gy)}"' if gy else "") + "/>")
            cx += pos.x_advance + tracking / k
        m = f"matrix({k:.5f} 0 0 {-k:.5f} {_num(x)} {_num(y)})"
        return f'<g{extra}><g transform="{m}" fill="{fill}">{"".join(uses)}</g></g>', width


SERIF = Face("Junicode-Regular.ttf")
ITALIC = Face("Junicode-Italic.ttf")
BOLD = Face("Junicode-Bold.ttf")
SANS = Face("Geist-Medium.otf")
SANS_R = Face("Geist-Regular.otf")


def T(face, s, size, x, y, fill, anchor="start", tracking=0.0, extra=""):
    return face.set(s, size, x, y, fill, anchor, tracking, extra)[0]


def caps(s, size, x, y, fill, anchor="start", tracking=None, extra=""):
    return T(SANS, s.upper(), size, x, y, fill, anchor, size * 0.22 if tracking is None else tracking, extra)


def run(pieces, x, y):
    """Set several (face, text, size, fill) pieces one after another on a line."""
    out = []
    for face, s, size, fill in pieces:
        piece, w = face.set(s, size, x, y, fill)
        out.append(piece)
        x += w
    return "".join(out)


# --------------------------------------------------------------- themes

THEMES = {
    "light": dict(
        ink="#1d1b18", sub="#6f675b", rule="#d9d1c1", brass="#9a7836", iris="#6a58b0",
        card="#faf7f0", edge="#e6dece", blade="#f3ecdd", glass="#f1e9d8", glass_o="0.5", shine="#ffffff",
        shine_o="1", petal="#f4d6d1", petal_edge="#c98f8a", moon="#e6cc7c", cream="#f3e6cc",
    ),
    "dark": dict(
        ink="#ebe4d5", sub="#9d9688", rule="#343a46", brass="#d2ae68", iris="#a898e6",
        card="#141921", edge="#2a303b", blade="#1a1f2a", glass="#dfe8ff", glass_o="0.04", shine="#ffffff",
        shine_o="0.28", petal="#f6dcd7", petal_edge="#d9a09a", moon="#f0dfae", cream="#efe2c8",
    ),
}

NIGHT_TOP, NIGHT_LOW = "#27325e", "#0c1228"
GOLD, SAGE, SAGE_D, WATER, PINK, TEAL = "#f2c35b", "#8aa587", "#6c8f70", "#8fb3c7", "#e3a9a2", "#6fb0ad"

MOTION_OFF = "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"


def svg(w, h, body, css="", defs="", label="", top=0):
    if FREEZE and css:
        css += f"*{{animation-play-state:paused!important;animation-delay:-{FREEZE}s!important}}"
    style = f"<style>{css}{MOTION_OFF}</style>" if css else ""
    defs += "".join(f'<path id="{k}" d="{d}"/>' for k, d in GLYPHS.items())
    GLYPHS.clear()
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 {top} {w} {h - top}" width="{w}" height="{h - top}" '
        f'role="img" aria-label="{label}">{style}<defs>{defs}</defs>{body}</svg>\n'
    )


# ----------------------------------------------------------------- hero

def hero(t):
    W, H = 880, 340
    cx, cy, R, N = 712, 160, 112, 8
    rnd = random.Random(7)

    # left: the wall text
    x = 36
    text = [
        caps("Permanent collection  ·  Open daily  ·  Admission free", 10.5, x + 2, 92, t["sub"], extra=' class="r r1"'),
        T(SERIF, "Iris Zhou", 88, x - 4, 188, t["ink"], extra=' class="r r2"'),
        T(ITALIC, "A Cabinet of Small Worlds", 39, x, 242, t["brass"], extra=' class="r r3"'),
    ]

    # right: an iris diaphragm opening onto a night
    stars = []
    for i in range(46):
        a, d = rnd.uniform(0, math.tau), R * math.sqrt(rnd.uniform(0.02, 1))
        sx, sy = cx + d * math.cos(a), cy + d * math.sin(a) * 0.92 - 8
        if sy > cy + 52:
            continue
        r = rnd.choice([0.7, 0.8, 1.0, 1.0, 1.3, 1.7])
        stars.append(
            f'<circle class="s" style="animation-delay:-{rnd.uniform(0, 4):.1f}s" cx="{sx:.1f}" cy="{sy:.1f}" r="{r}" fill="#fff6dc"/>'
        )
    mx, my = cx - 10, cy - 14
    sky = (
        f'<circle cx="{cx}" cy="{cy}" r="{R}" fill="url(#night)"/>' + "".join(stars)
        + f'<path d="M{mx + 6},{my - 15}a16,16 0 1 0 9,27a13,13 0 1 1 -9,-27z" fill="#f6e7b4"/>'
        # a hill, a tree and one lit window
        + f'<path d="M{cx - R},{cy + R}V{cy + 78}C{cx - 60},{cy + 52} {cx + 30},{cy + 50} {cx + R},{cy + 84}V{cy + R}z" fill="#070b1a"/>'
        + f'<path d="M{cx + 22},{cy + 58}v-13l9,-8l9,8v13z" fill="#070b1a"/>'
        + f'<rect class="s" x="{cx + 28.5}" y="{cy + 47}" width="5" height="6" fill="{GOLD}"/>'
        + f'<path d="M{cx - 46},{cy + 66}v-20" stroke="#070b1a" stroke-width="2.4"/><circle cx="{cx - 46}" cy="{cy + 40}" r="11" fill="#070b1a"/>'
    )

    # Eight blades, each turning on a rivet on the ring. All of them are the same
    # colour, so the fills can overlap in any order; what makes an iris read as an
    # iris is that every blade's edge runs from its rivet and slips under the next
    # blade. So each edge is drawn inside the *next* blade's moving frame, clipped
    # to the outside of that blade, then turned back (.bi) into its own frame.
    step = 360 / N
    fill = f'<path d="M{-3 * R},0H{R}V{3 * R}H{-3 * R}z" fill="{t["blade"]}"/>'
    edge = (
        f'<rect x="{-3 * R}" y="0" width="{4 * R}" height="7" fill="url(#lip)"/>'
        f'<path d="M{-3 * R},0H{R}" stroke="{t["brass"]}" stroke-width="1.1"/>'
    )
    blades = "".join(
        f'<g transform="rotate({k * step}) translate({R},0)"><g class="b">{fill}</g></g>' for k in range(N)
    ) + "".join(
        f'<g transform="rotate({(k + 1) * step}) translate({R},0)"><g class="b"><g clip-path="url(#under)"><g class="bi">'
        f'<g transform="translate({-R},0) rotate({-step}) translate({R},0)"><g class="b">{edge}</g></g>'
        "</g></g></g></g>"
        for k in range(N)
    )

    ticks = "".join(
        f'<path d="M0,{-(R + 4)}V{-(R + (11 if i % 6 == 0 else 8))}" transform="rotate({i * 5})" '
        f'stroke="{t["brass"]}" stroke-width="{1.1 if i % 6 == 0 else 0.7}" opacity="{1 if i % 6 == 0 else 0.6}"/>'
        for i in range(72)
    )
    rivets = "".join(
        f'<circle r="1.9" cx="{R * math.cos(k * math.tau / N):.2f}" cy="{R * math.sin(k * math.tau / N):.2f}" fill="{t["brass"]}"/>'
        for k in range(N)
    )
    device = (
        f'<g clip-path="url(#ring)">{sky}<g transform="translate({cx},{cy})">{blades}</g></g>'
        f'<g transform="translate({cx},{cy})" fill="none">'
        f'<circle r="{R}" stroke="{t["brass"]}" stroke-width="1.4"/>'
        f'<circle r="{R + 15}" stroke="{t["brass"]}" stroke-width="0.8" opacity="0.7"/>{ticks}{rivets}</g>'
        + T(ITALIC, "Fig. 1.  An iris, opening.", 13.5, cx, cy + R + 44, t["sub"], "middle")
    )

    defs = (
        f'<clipPath id="ring"><circle cx="{cx}" cy="{cy}" r="{R}"/></clipPath>'
        f'<clipPath id="under"><rect x="{-3 * R}" y="{-3 * R}" width="{6 * R}" height="{3 * R}"/></clipPath>'
        f'<radialGradient id="night" cx="42%" cy="34%" r="80%"><stop offset="0" stop-color="{NIGHT_TOP}"/>'
        f'<stop offset="1" stop-color="{NIGHT_LOW}"/></radialGradient>'
        '<linearGradient id="lip" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#000" stop-opacity="0.16"/>'
        '<stop offset="1" stop-color="#000" stop-opacity="0"/></linearGradient>'
    )
    css = (
        ".b{animation:iris 18s cubic-bezier(.65,0,.3,1) infinite}"
        "@keyframes iris{0%,100%{transform:rotate(-21deg)}38%,80%{transform:rotate(-57deg)}}"
        ".bi{animation:irisb 18s cubic-bezier(.65,0,.3,1) infinite}"
        "@keyframes irisb{0%,100%{transform:rotate(21deg)}38%,80%{transform:rotate(57deg)}}"
        ".s{animation:tw 3.6s ease-in-out infinite}@keyframes tw{0%,100%{opacity:1}50%{opacity:.25}}"
        ".r{animation:rise 1.1s cubic-bezier(.2,.7,.2,1) both}.r2{animation-delay:.12s}.r3{animation-delay:.28s}.r4{animation-delay:.44s}"
        "@keyframes rise{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}"
    )
    return svg(W, H, "".join(text) + device, css, defs, "Iris Zhou. A Cabinet of Small Worlds.")


# ----------------------------------------------------------- wall label

PROVENANCE = [
    ("2026–", "Xiaohongshu", "tech brand, on loan"),
    ("2026", "Zhongyan Tech", "AI product"),
    ("2025", "Xinhua · Liaowang Institute", "product operations"),
    ("2025", "Shanghai Media Group · ShanghaiEye", "overseas content"),
]
FORMATION = [
    ("2023–27", "Wuhan University", "Chinese literature, communication minor"),
    ("2025–26", "Université Paris Nanterre", "exchange"),
]


def label(t):
    """A museum wall label: one narrow column, so it still reads on a phone."""
    W, H = 560, 606
    lx, rx, tx = 44, W - 44, 118
    b = [f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="3" fill="{t["card"]}" stroke="{t["edge"]}"/>']

    b.append(T(BOLD, "Iris Zhou", 27, lx, 68, t["ink"]))
    b.append(caps("Acc. no. 2027.06", 8.5, rx, 61, t["sub"], "end"))
    b.append(T(SERIF, "Wuhan University, class of 2027", 15.5, lx, 93, t["sub"]))
    b.append(run([(ITALIC, "A Cabinet of Small Worlds, ", 20, t["ink"]), (SERIF, "2025–ongoing", 20, t["ink"])], lx, 140))
    for i, line in enumerate([
        "Language, product judgment, three.js, and long conversations",
        "with AI. Dimensions variable.",
    ]):
        assert SERIF.width(line, 15.5) <= rx - lx, line
        b.append(T(SERIF, line, 15.5, lx, 167 + i * 23, t["sub"]))

    y = 240
    for title, rows in (("Provenance", PROVENANCE), ("Formation", FORMATION)):
        b.append(caps(title, 9.5, lx, y, t["brass"]))
        y += 31
        for year, org, what in rows:
            b.append(T(SERIF, year, 15, lx, y, t["sub"]))
            org_svg, ow = SERIF.set(org, 16.5, tx, y, t["ink"])
            what_svg, ww = ITALIC.set(what, 14.5, rx, y, t["sub"], "end")
            x0, x1 = tx + ow + 10, rx - ww - 10
            assert x1 - x0 > 12, org
            b.append(org_svg + what_svg + f'<rect x="{x0:.1f}" y="{y - 4.5}" width="{x1 - x0:.1f}" height="1" fill="{t["edge"]}"/>')
            y += 30
        y += 16

    b.append(f'<rect x="{lx}" y="{y - 14}" width="40" height="1.2" fill="{t["brass"]}"/>')
    for i, line in enumerate([
        "Currently on loan to Xiaohongshu. Seeking a permanent home",
        "from summer 2027, in AI product, brand or communications.",
    ]):
        assert ITALIC.width(line, 16.5) <= rx - lx, line
        b.append(T(ITALIC, line, 16.5, lx, y + 20 + i * 25, t["ink"]))
    assert y + 45 + 44 <= H, y
    return svg(W, H, "".join(b), label="Wall label for Iris Zhou: provenance and formation.")


# ------------------------------------------------------- section rules

def rule(t, title, line):
    W, H = 880, 92
    w = SANS.width(title.upper(), 10, 2.6)
    gap, c = w / 2 + 22, W / 2
    body = (
        caps(title, 10, c, 44, t["brass"], "middle", 2.6)
        + f'<rect x="{c - gap - 120}" y="40" width="120" height="1" fill="{t["rule"]}"/>'
        + f'<rect x="{c + gap}" y="40" width="120" height="1" fill="{t["rule"]}"/>'
        + T(ITALIC, line, 15.5, c, 72, t["sub"], "middle")
    )
    return svg(W, H, body, label=title)


def colophon(t):
    W, H = 880, 70
    body = (
        f'<rect x="{W / 2 - 24}" y="14" width="48" height="1.2" fill="{t["brass"]}"/>'
        + T(ITALIC, "Set in Junicode and Geist. Drawn as SVG, without a line of JavaScript.", 14, W / 2, 48, t["sub"], "middle")
    )
    return svg(W, H, body, label="Colophon")


# ----------------------------------------------------------- bell jars

def jar(t, no, title, medium, world, css="", defs=""):
    W, H = 280, 326
    ink = t["ink"]
    glass = (
        f'<path d="M72,236V124a68,68 0 0 1 136,0V236z" fill="{t["glass"]}" fill-opacity="{t["glass_o"]}"/>'
    )
    frame = (
        f'<path d="M84,214V128a56,56 0 0 1 18,-41" fill="none" stroke="{t["shine"]}" stroke-opacity="{t["shine_o"]}" stroke-width="2.2" stroke-linecap="round"/>'
        f'<path d="M72,236V124a68,68 0 0 1 136,0V236" fill="none" stroke="{ink}" stroke-opacity="0.72" stroke-width="1.3"/>'
        f'<circle cx="140" cy="47" r="7.5" fill="{t["glass"]}" fill-opacity="{t["glass_o"]}" stroke="{ink}" stroke-opacity="0.72" stroke-width="1.3"/>'
        # turned wooden base
        f'<path d="M52,236v8a88,9 0 0 0 176,0v-8" fill="{t["brass"]}" fill-opacity="0.22" stroke="{t["brass"]}" stroke-width="1.2"/>'
        f'<ellipse cx="140" cy="236" rx="88" ry="9" fill="{t["brass"]}" fill-opacity="0.12" stroke="{t["brass"]}" stroke-width="1.2"/>'
    )
    text = (
        caps(f"No. {no:02d}", 9, 140, 276, t["brass"], "middle", 2.2)
        + T(ITALIC, title, 21, 140, 300, ink, "middle")
        + T(SANS_R, medium, 10.5, 140, 319, t["sub"], "middle", 0.25)
    )
    base_css = ".tw{animation:tw 3.2s ease-in-out infinite}@keyframes tw{0%,100%{opacity:1}50%{opacity:.2}}"
    return svg(W, H, glass + f'<g clip-path="url(#in)">{world}</g>' + frame + text, base_css + css,
               '<clipPath id="in"><path d="M73,236V124a67,67 0 0 1 134,0V236z"/></clipPath>' + defs, f"{title}: {medium}", top=30)


def w_island(t):
    world = (
        f'<ellipse cx="140" cy="226" rx="60" ry="7.5" fill="{WATER}" fill-opacity="0.55"/>'
        f'<path class="wv" d="M92,227q5,-3 10,0t10,0M166,229q5,-3 10,0t10,0" fill="none" stroke="{WATER}" stroke-width="1.2" stroke-linecap="round"/>'
        '<g class="bob">'
        f'<path d="M98,226C104,192 176,190 182,226z" fill="{SAGE}"/>'
        f'<path d="M154,206V180" stroke="#7a5c3e" stroke-width="2.2" stroke-linecap="round"/>'
        f'<circle cx="154" cy="172" r="11" fill="{SAGE_D}"/><circle cx="146" cy="179" r="7.5" fill="{SAGE_D}"/><circle cx="162" cy="179" r="7.5" fill="{SAGE_D}"/>'
        f'<path d="M116,207v-10l8,-7l8,7v10z" fill="{t["cream"]}" stroke="{t["ink"]}" stroke-opacity="0.5" stroke-width="0.8"/>'
        f'<rect class="tw" x="122" y="199" width="4" height="5" fill="{GOLD}"/>'
        f'<g class="ball"><path d="M124,190C122,178 127,170 126,160" fill="none" stroke="{t["ink"]}" stroke-opacity="0.45" stroke-width="0.7"/>'
        f'<ellipse cx="126" cy="152" rx="6.5" ry="8" fill="{PINK}"/></g>'
        "</g>"
        + "".join(
            f'<circle class="tw" style="animation-delay:-{d}s" cx="{x}" cy="{y}" r="1.5" fill="{GOLD}"/>'
            for x, y, d in [(104, 150, 0.4), (176, 136, 1.7), (164, 104, 2.5), (112, 112, 1.1)]
        )
    )
    css = (
        ".bob{animation:bob 5s ease-in-out infinite}@keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-3px)}}"
        ".ball{animation:sway 4s ease-in-out infinite;transform-origin:124px 190px}@keyframes sway{0%,100%{transform:rotate(-5deg)}50%{transform:rotate(6deg)}}"
        ".wv{animation:wv 3s ease-in-out infinite}@keyframes wv{0%,100%{transform:translateX(-2px)}50%{transform:translateX(2px)}}"
    )
    return world, css, ""


def w_birthday(t):
    rnd = random.Random(3)
    confetti = "".join(
        f'<rect class="cf" style="animation-delay:-{rnd.uniform(0, 7):.1f}s" x="{rnd.randint(84, 196)}" y="62" width="3.2" height="3.2" '
        f'rx="{rnd.choice([0, 1.6])}" fill="{rnd.choice([GOLD, PINK, t["iris"], TEAL])}"/>'
        for _ in range(11)
    )
    world = (
        confetti
        + f'<ellipse cx="140" cy="227" rx="44" ry="5" fill="none" stroke="{t["ink"]}" stroke-opacity="0.55" stroke-width="1"/>'
        f'<rect x="106" y="196" width="68" height="30" rx="4" fill="{t["cream"]}" stroke="{t["ink"]}" stroke-opacity="0.45" stroke-width="0.8"/>'
        f'<path d="M106,202v-2a4,4 0 0 1 4,-4h60a4,4 0 0 1 4,4v2q-5.6,7 -11.3,0t-11.3,0t-11.3,0t-11.3,0t-11.3,0t-11.5,0z" fill="{PINK}"/>'
        f'<rect x="119" y="172" width="42" height="24" rx="4" fill="{PINK}" stroke="{t["ink"]}" stroke-opacity="0.35" stroke-width="0.8"/>'
        f'<path d="M119,178v-2a4,4 0 0 1 4,-4h34a4,4 0 0 1 4,4v2q-5.2,6 -10.5,0t-10.5,0t-10.5,0t-10.5,0z" fill="{t["cream"]}"/>'
        f'<rect x="138" y="154" width="4" height="18" rx="1" fill="{t["iris"]}"/>'
        f'<circle class="glow" cx="140" cy="146" r="13" fill="{GOLD}" fill-opacity="0.22"/>'
        f'<path class="fl" d="M140,138c4,5 5,8 5,10a5,5 0 0 1 -10,0c0,-2 1,-5 5,-10z" fill="{GOLD}"/>'
    )
    css = (
        ".fl{animation:fl 1.4s ease-in-out infinite;transform-origin:140px 152px}"
        "@keyframes fl{0%,100%{transform:scale(1,1) rotate(-3deg)}40%{transform:scale(.9,1.12) rotate(3deg)}70%{transform:scale(1.06,.94) rotate(-1deg)}}"
        ".glow{animation:tw 2.8s ease-in-out infinite}"
        ".cf{animation:cf 7s linear infinite}@keyframes cf{0%{transform:translate(0,-10px) rotate(0);opacity:0}8%{opacity:1}"
        "80%{opacity:1}100%{transform:translate(8px,160px) rotate(300deg);opacity:0}}"
    )
    return world, css, ""


def w_globe(t):
    br = t["brass"]
    c = (140, 160)
    pt = lambda r, a: (c[0] + r * math.cos(math.radians(a)), c[1] + r * math.sin(math.radians(a)))
    a0, a1 = pt(43, -110), pt(43, 100)
    n0, n1, s0, s1 = pt(34, -110), pt(43, -110), pt(34, 70), pt(43, 70)
    cities = [(128, 146, 0), (150, 150, 1.1), (141, 166, 2.2), (124, 170, 3.3), (156, 174, 4.4)]
    world = (
        f'<circle cx="140" cy="160" r="34" fill="{br}" fill-opacity="0.16"/>'
        f'<g transform="rotate(-20 140 160)" fill="none" stroke="{br}">'
        '<ellipse cx="140" cy="160" rx="34" ry="8" stroke-width="0.8"/>'
        '<ellipse cx="140" cy="143" rx="29.4" ry="6" stroke-width="0.6" opacity="0.7"/>'
        '<ellipse cx="140" cy="177" rx="29.4" ry="6" stroke-width="0.6" opacity="0.7"/>'
        + "".join(f'<ellipse class="mer" style="animation-delay:-{i * 3}s" cx="140" cy="160" rx="34" ry="34" stroke-width="0.8"/>' for i in range(3))
        + "</g>"
        f'<circle cx="140" cy="160" r="34" fill="none" stroke="{br}" stroke-width="1.5"/>'
        + "".join(f'<circle class="city" style="animation-delay:{d}s" cx="{x}" cy="{y}" r="2" fill="{GOLD}"/>' for x, y, d in cities)
        + f'<path d="M{a0[0]:.1f},{a0[1]:.1f}A43,43 0 1 1 {a1[0]:.1f},{a1[1]:.1f}" fill="none" stroke="{br}" stroke-width="2.2" stroke-linecap="round"/>'
        f'<path d="M{n0[0]:.1f},{n0[1]:.1f}L{n1[0]:.1f},{n1[1]:.1f}M{s0[0]:.1f},{s0[1]:.1f}L{s1[0]:.1f},{s1[1]:.1f}" stroke="{br}" stroke-width="1.6"/>'
        f'<path d="M140,203v18" stroke="{br}" stroke-width="2.6"/>'
        f'<path d="M116,228q24,-12 48,0z" fill="{br}"/>'
    )
    steps = "".join(f"{i * 100 / 16:.2f}%{{transform:scaleX({math.cos(math.pi * i / 16):.3f})}}" for i in range(17))
    css = (
        f".mer{{animation:mer 9s linear infinite;transform-box:fill-box;transform-origin:center}}@keyframes mer{{{steps}}}"
        ".city{animation:city 6.6s ease-in-out infinite;opacity:.18}@keyframes city{0%,8%{opacity:.18}16%,70%{opacity:1}100%{opacity:.18}}"
    )
    return world, css, ""


def w_blossom(t):
    def flower(x, y, s, rot=0):
        petals = "".join(
            f'<ellipse cx="0" cy="-5.2" rx="3.6" ry="5" transform="rotate({i * 72})" fill="{t["petal"]}" stroke="{t["petal_edge"]}" stroke-width="0.5"/>'
            for i in range(5)
        )
        return f'<g transform="translate({x},{y}) rotate({rot}) scale({s})">{petals}<circle r="2" fill="#c9705f"/></g>'

    twig = "#6e5a44" if t is THEMES["light"] else "#a08b72"
    world = (
        f'<circle cx="140" cy="150" r="52" fill="{TEAL}" fill-opacity="0.28"/>'
        f'<path d="M112,236C118,196 150,186 152,150C153,132 164,118 176,106M139,190C128,172 112,166 102,150M151,160C166,156 176,160 188,150M152,146C144,130 134,124 128,108" '
        f'fill="none" stroke="{twig}" stroke-width="2.2" stroke-linecap="round"/>'
        + flower(176, 104, 1.15, 10) + flower(102, 148, 1.05, -20) + flower(188, 149, 0.95, 30)
        + flower(128, 106, 1.0, 5) + flower(150, 168, 0.8, 50) + flower(131, 180, 0.72, -10) + flower(160, 128, 0.7, 20)
        + "".join(
            f'<ellipse class="pt" style="animation-delay:-{d}s" cx="{x}" cy="{y}" rx="2.6" ry="3.8" fill="{t["petal"]}" stroke="{t["petal_edge"]}" stroke-width="0.4"/>'
            for x, y, d in [(170, 112, 0), (110, 152, 2.6), (184, 156, 5.1)]
        )
    )
    css = (
        ".pt{animation:pt 7.8s ease-in infinite;transform-box:fill-box;transform-origin:center}"
        "@keyframes pt{0%{transform:translate(0,0) rotate(0);opacity:0}10%{opacity:1}"
        "50%{transform:translate(-12px,48px) rotate(140deg)}85%{opacity:1}100%{transform:translate(4px,98px) rotate(300deg);opacity:0}}"
    )
    return world, css, ""


def w_mist(t):
    heart = "M140,172c-9,-8 -15,-13 -15,-20a7.5,7.5 0 0 1 15,-4a7.5,7.5 0 0 1 15,4c0,7 -6,12 -15,20z"
    world = (
        f'<rect x="102" y="106" width="76" height="110" fill="url(#out)"/>'
        f'<circle cx="122" cy="188" r="7" fill="{GOLD}" fill-opacity="0.5"/><circle cx="158" cy="176" r="5" fill="{PINK}" fill-opacity="0.5"/>'
        f'<circle cx="146" cy="200" r="4" fill="{GOLD}" fill-opacity="0.4"/><circle cx="160" cy="128" r="1.2" fill="#fff"/><circle cx="118" cy="122" r="1" fill="#fff"/>'
        '<g mask="url(#wipe)"><rect class="fog" x="102" y="106" width="76" height="110" fill="#e4ebef"/></g>'
        '<ellipse class="drop" cx="140" cy="174" rx="1.8" ry="2.6" fill="#f4f8fa"/>'
        f'<rect x="102" y="106" width="76" height="110" fill="none" stroke="{t["ink"]}" stroke-opacity="0.8" stroke-width="2"/>'
        f'<path d="M94,217.5H186" stroke="{t["ink"]}" stroke-opacity="0.8" stroke-width="3" stroke-linecap="round"/>'
    )
    defs = (
        f'<linearGradient id="out" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1b2547"/><stop offset="1" stop-color="#33406b"/></linearGradient>'
        f'<mask id="wipe"><rect x="96" y="100" width="88" height="122" fill="#fff"/>'
        f'<path d="{heart}" fill="none" stroke="#000" stroke-width="4.2" stroke-linecap="round" stroke-linejoin="round"/></mask>'
    )
    css = (
        ".fog{animation:fog 9s ease-in-out infinite}@keyframes fog{0%,100%{opacity:.5}45%,60%{opacity:.86}}"
        ".drop{animation:drop 9s ease-in infinite}@keyframes drop{0%,30%{transform:translateY(0);opacity:0}36%{opacity:.9}"
        "48%{transform:translateY(7px)}60%{transform:translateY(9px)}82%{transform:translateY(36px);opacity:.9}90%,100%{transform:translateY(40px);opacity:0}}"
    )
    return world, css, defs


def w_moon(t):
    world = (
        f'<circle cx="140" cy="132" r="30" fill="none" stroke="{t["brass"]}" stroke-width="0.7" opacity="0.55"/>'
        f'<circle cx="140" cy="132" r="30" fill="{t["moon"]}" mask="url(#phase)"/>'
        + "".join(
            f'<circle class="tw" style="animation-delay:-{d}s" cx="{x}" cy="{y}" r="{r}" fill="{t["brass"]}"/>'
            for x, y, r, d in [(96, 104, 1.4, 0.2), (186, 96, 1.2, 1.4), (182, 168, 1.5, 2.3), (100, 176, 1.1, 0.9), (150, 80, 1.0, 1.9)]
        )
        + f'<path d="M140,214V172" stroke="{t["ink"]}" stroke-opacity="0.3" stroke-width="0.8" stroke-dasharray="1 4" stroke-linecap="round"/>'
        f'<ellipse cx="140" cy="230" rx="7" ry="1.6" fill="{t["ink"]}" fill-opacity="0.18"/>'
        f'<circle class="dot" cx="140" cy="224" r="4.6" fill="{t["ink"]}"/>'
    )
    defs = (
        '<mask id="phase"><rect x="100" y="92" width="80" height="80" fill="#fff"/>'
        '<circle cy="132" r="33" fill="#000"><animate attributeName="cx" values="74;206" dur="14s" repeatCount="indefinite"/></circle></mask>'
    )
    css = (
        ".dot{animation:hop 3.5s cubic-bezier(.3,0,.3,1) infinite}"
        "@keyframes hop{0%,58%,100%{transform:translateY(0)}72%{transform:translateY(-13px)}84%{transform:translateY(0)}90%{transform:translateY(-4px)}96%{transform:translateY(0)}}"
    )
    return world, css, defs


def w_park(t):
    br, ink = t["brass"], t["ink"]
    c, r = (140, 148), 44
    cab = [PINK, GOLD, TEAL, t["iris"]]
    wheel = (
        f'<circle cx="{c[0]}" cy="{c[1]}" r="{r}" fill="none" stroke="{br}" stroke-width="1.6"/>'
        f'<circle cx="{c[0]}" cy="{c[1]}" r="{r - 9}" fill="none" stroke="{br}" stroke-width="0.7" opacity="0.7"/>'
        + "".join(
            f'<path d="M{c[0]},{c[1]}L{c[0] + r * math.cos(i * math.pi / 4):.1f},{c[1] + r * math.sin(i * math.pi / 4):.1f}" stroke="{br}" stroke-width="0.8"/>'
            for i in range(8)
        )
        + "".join(
            f'<circle cx="{c[0] + r * math.cos(i * math.pi / 4):.1f}" cy="{c[1] + r * math.sin(i * math.pi / 4):.1f}" r="5" fill="{cab[i % 4]}" stroke="{ink}" stroke-opacity="0.35" stroke-width="0.6"/>'
            for i in range(8)
        )
    )
    world = (
        f'<ellipse cx="140" cy="230" rx="62" ry="6" fill="{SAGE}" fill-opacity="0.8"/>'
        f'<path d="M92,228l9,-22l9,22zM96,214l5,-13l5,13z" fill="{SAGE_D}"/><path d="M176,228l7,-17l7,17z" fill="{SAGE_D}"/>'
        f'<path d="M140,148L120,229M140,148L160,229" stroke="{ink}" stroke-opacity="0.7" stroke-width="1.6" stroke-linecap="round"/>'
        f'<g class="wheel">{wheel}</g>'
        f'<circle cx="140" cy="148" r="4" fill="{br}"/>'
        + "".join(
            f'<circle class="tw" style="animation-delay:-{d}s" cx="{x}" cy="{y}" r="1.4" fill="{GOLD}"/>'
            for x, y, d in [(98, 96, 0.3), (184, 104, 1.6), (150, 82, 2.4)]
        )
    )
    css = ".wheel{animation:wheel 40s linear infinite;transform-origin:140px 148px}@keyframes wheel{to{transform:rotate(360deg)}}"
    return world, css, ""


def w_bloom(t):
    ink = t["ink"]
    o = (150, 150)
    cols = [PINK, GOLD, t["iris"], TEAL]
    petals = "".join(
        f'<ellipse cx="{o[0]}" cy="{o[1] - 13}" rx="4.6" ry="9" transform="rotate({i * 45} {o[0]} {o[1]})" fill="{cols[i % 2]}" fill-opacity="0.92"/>'
        for i in range(8)
    )
    rnd = random.Random(11)
    dots = ""
    for ring, (n, dist, size) in enumerate([(12, 30, 2.1), (16, 42, 1.6), (14, 54, 1.2)]):
        for i in range(n):
            a = i * math.tau / n + ring * 0.3 + rnd.uniform(-0.12, 0.12)
            d = dist + rnd.uniform(-3, 3)
            dots += (
                f'<circle class="pd d{ring}" cx="{o[0] + d * math.cos(a):.1f}" cy="{o[1] + d * math.sin(a):.1f}" r="{size}" fill="{rnd.choice(cols)}"/>'
            )
    world = (
        # the photograph the bloom grows out of
        f'<g transform="rotate(-5 140 160)"><rect x="104" y="114" width="72" height="88" rx="2" fill="{t["cream"]}" stroke="{ink}" stroke-opacity="0.45" stroke-width="0.8"/>'
        f'<rect x="110" y="120" width="60" height="60" fill="{TEAL}" fill-opacity="0.55"/>'
        f'<path d="M110,180v-16q14,-12 26,-2t34,-8v26z" fill="{SAGE_D}" fill-opacity="0.8"/></g>'
        f'<g class="bl">{dots}<g class="core">{petals}<circle cx="{o[0]}" cy="{o[1]}" r="4" fill="{GOLD}"/></g></g>'
    )
    css = (
        f".bl{{transform-origin:{o[0]}px {o[1]}px;animation:bl 9s cubic-bezier(.2,.7,.2,1) infinite}}"
        "@keyframes bl{0%{transform:scale(.05);opacity:0}8%{opacity:1}45%,82%{transform:scale(1);opacity:1}100%{transform:scale(1.12);opacity:0}}"
        f".core{{transform-origin:{o[0]}px {o[1]}px;animation:core 9s ease-in-out infinite}}@keyframes core{{0%{{transform:rotate(-40deg)}}45%,100%{{transform:rotate(0)}}}}"
        ".pd{animation:tw 2.6s ease-in-out infinite}.d1{animation-delay:-.9s}.d2{animation-delay:-1.7s}"
    )
    return world, css, ""


def w_shigu(t):
    ink = "#2a2520"  # the cards are paper in both themes
    card = f'fill="{t["cream"]}" stroke="{ink}" stroke-opacity="0.5" stroke-width="0.8"'
    stroke = f'fill="none" stroke="{ink}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"'
    world = (
        f'<rect x="108" y="108" width="68" height="90" rx="5" transform="rotate(7 142 153)" {card}/>'
        f'<rect x="106" y="108" width="68" height="90" rx="5" transform="rotate(-3 140 153)" {card}/>'
        '<g transform="rotate(-3 140 153)">'
        # the mountain as it was cut into bone, then as it is written now
        f'<path class="old" d="M119,178L128,152L134,166L140,134L146,166L152,152L161,178z" {stroke}/>'
        f'<path class="now" d="M140,134V176M122,152V176H158V152" {stroke}/>'
        f'<circle cx="162" cy="120" r="3" fill="#b5483a"/>'
        "</g>"
        + "".join(
            f'<circle class="rep" style="animation-delay:{i * 0.5}s" cx="{116 + i * 12}" cy="216" r="2.6" fill="{t["brass"]}"/>' for i in range(5)
        )
    )
    css = (
        ".old{animation:old 8s ease-in-out infinite}.now{animation:now 8s ease-in-out infinite}"
        "@keyframes old{0%,38%{opacity:1}50%,88%{opacity:0}100%{opacity:1}}@keyframes now{0%,38%{opacity:0}50%,88%{opacity:1}100%{opacity:0}}"
        ".rep{animation:rep 8s ease-in-out infinite;opacity:.25}@keyframes rep{0%,5%{opacity:.25}12%,80%{opacity:1}95%,100%{opacity:.25}}"
    )
    return world, css, ""


# slug, title, medium, drawing, where the jar leads
JARS = [
    ("island", "An Island for You", "three.js, tide, small things to celebrate", w_island, "https://island-for-you.vercel.app"),
    ("birthday", "Birthday Stays Open", "a 3D room, weather, AI doodles", w_birthday, "https://birthday-stays-open.vercel.app"),
    ("wonderpark", "Idea Wonderpark", "a low-poly park of ideas and photographs", w_park, "https://wonderpark-publiccp4hwz.vercel.app"),
    ("footprints", "Footprints", "brass, WebGL, the places you have been", w_globe, "https://footprints-globe.vercel.app"),
    ("blossom", "Tearable Almond Blossom", "linen, Verlet cloth, Van Gogh", w_blossom, "https://tearable-almond-blossom.vercel.app"),
    ("mistpane", "Mistpane", "glass, breath, a fingertip", w_mist, "https://mistpane.vercel.app"),
    ("moons", "1001 Moons", "one full stop, drawn and scored live", w_moon, "https://1001moons.vercel.app"),
    ("bloom", "Bloom", "a photograph, particles, one chosen point", w_bloom, "https://bloom1-kappa.vercel.app"),
    ("shigu", "Shigu", "oracle bones, flashcards, spaced repetition", w_shigu, "https://learn-ancient-character.vercel.app"),
]


def readme_shelf():
    """The jar rows of README.md, three to a row; main() keeps them in step with JARS."""
    rows = []
    for i in range(0, len(JARS), 3):
        cells = [
            f'<a href="{url}"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/jar-{slug}-dark.svg">'
            f'<img src="assets/jar-{slug}-light.svg" width="31%" alt="No. {n:02d}, {title}: {medium}"></picture></a>'
            for n, (slug, title, medium, _, url) in enumerate(JARS[i:i + 3], i + 1)
        ]
        rows.append("<p>\n" + "\n".join(cells) + "\n</p>")
    return "\n".join(rows)


def main():
    OUT.mkdir(exist_ok=True)
    for name, t in THEMES.items():
        files = {
            "hero": hero(t),
            "label": label(t),
            "on-view": rule(t, "On view", "Nine small worlds, each kept under glass. Pick one and step in."),
            "colophon": colophon(t),
        }
        for i, (slug, title, medium, fn, _) in enumerate(JARS, 1):
            world, css, defs = fn(t)
            files[f"jar-{slug}"] = jar(t, i, title, medium, world, css, defs)
        for key, data in files.items():
            (OUT / f"{key}-{name}.svg").write_text(data, encoding="utf-8")
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    start, end = "<!-- shelf -->", "<!-- /shelf -->"
    head, rest = text.split(start)
    readme.write_text(head + start + "\n" + readme_shelf() + "\n" + end + rest.split(end)[1], encoding="utf-8")
    sizes = sorted((p.stat().st_size, p.name) for p in OUT.glob("*.svg"))
    print(f"{len(sizes)} files, {sum(s for s, _ in sizes) / 1024:.0f} KB total, largest {sizes[-1][1]} {sizes[-1][0] / 1024:.0f} KB")


if __name__ == "__main__":
    main()
