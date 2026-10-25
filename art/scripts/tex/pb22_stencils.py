"""Original stencils for the PB-22 skin, drawn with PIL (DejaVu Sans), returned as tex_feat.Decal features.
All are small, English, low-contrast (dark grey on the base grey); red / yellow only on the tiny warning marks."""
import os, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from tex_feat import Decal

FONT_DIRS = ['/usr/share/fonts/truetype/dejavu', '/usr/share/fonts/TTF', 'C:/Windows/Fonts']
STENCIL = (46, 49, 51)
RED = (138, 43, 36)
YELLOW = (184, 149, 46)


STENCIL_FONT = None          # set by use_palette(): the painted liveries letter everything with a stencil face


def use_palette(pal):
    """Switch the module colours (and the lettering face) to a livery palette."""
    global STENCIL, RED, YELLOW, STENCIL_FONT
    STENCIL, RED, YELLOW = pal['stencil'], pal['red'], pal['warn']
    f = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'fonts', 'AllertaStencil-Regular.ttf')
    STENCIL_FONT = f if os.path.exists(f) else None


def _font(px, bold=True):
    if STENCIL_FONT: return ImageFont.truetype(STENCIL_FONT, px)
    for dname in FONT_DIRS:
        for f in (('DejaVuSans-Bold.ttf', 'DejaVuSansCondensed-Bold.ttf') if bold else ('DejaVuSans.ttf',)):
            p = os.path.join(dname, f)
            if os.path.exists(p): return ImageFont.truetype(p, px)
    return ImageFont.load_default()


def text_img(text, col, px=96, bold=True, pad=4):
    f = _font(px, bold)
    l, t, r, b = f.getbbox(text)
    im = Image.new('RGBA', (r - l + 2 * pad, b - t + 2 * pad), col + (0,))
    ImageDraw.Draw(im).text((pad - l, pad - t), text, font=f, fill=col + (255,))
    return im


def _side_axes(side):
    # right = toward the nose on the right side, toward the tail on the left side (text reads from outside)
    return (0.0, 1.0 * side, 0.0), (0.0, 0.0, 1.0), (float(side), 0.0, 0.0)


def place_side(im, d, z, side, height, parts, xr=(0.3, 3.0), op=1.0):
    w = height * im.width / im.height
    R, U, Fc = _side_axes(side)
    lo, hi = xr
    box = {'x': (lo, hi) if side > 0 else (-hi, -lo)}
    return Decal(im, (d, 0.0, z), R, U, (w, height), parts, facing=Fc, tol=3.5, opacity=op, box=box)


def place_top(im, d, x, z, width, parts, op=1.0, down=False, tol=0.4, rot_deg=0.0):
    h = width * im.height / im.width
    a = math.radians(rot_deg)
    R = (math.cos(a), -math.sin(a), 0.0); U = (math.sin(a), math.cos(a), 0.0)       # up = forward
    if down:
        R = (-R[0], -R[1], 0.0)
        return Decal(im, (d, x, z if z is not None else 1.4), R, U, (width, h), parts, facing=(0, 0, -1), tol=tol if z is not None else 2.0, opacity=op)
    return Decal(im, (d, x, z), R, U, (width, h), parts, facing=(0, 0, 1), tol=tol, opacity=op)


# ------------------------------------------------------------------ the stencils of DETAIL_PLAN 3.5
def text_side(text, d, zc, side, height, parts, col=None, op=0.85, weight='bold', xr=(0.3, 3.0)):
    col = STENCIL if col is None else col
    return place_side(text_img(text, col, bold=(weight == 'bold')), d, zc, side, height, parts, xr, op)


def nostep(d, x, z, parts, size=0.05, text='NO STEP'):
    im = text_img(text, STENCIL, px=80)
    return place_top(im, d, x, z, size * im.width / im.height, parts, op=0.8, tol=0.5)


def _tri(px, fill, edge, inner=None):
    im = Image.new('RGBA', (px, px), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    pts = [(px / 2, px * 0.06), (px * 0.96, px * 0.92), (px * 0.04, px * 0.92)]
    dr.polygon(pts, fill=edge + (255,))
    k = px * 0.09
    pts2 = [(px / 2, px * 0.06 + 2.2 * k), (px * 0.96 - 1.9 * k, px * 0.92 - k), (px * 0.04 + 1.9 * k, px * 0.92 - k)]
    dr.polygon(pts2, fill=fill + (255,))
    return im, dr


def eject_triangle(d, x, z, size, parts):
    """Ejection-seat warning triangle (yellow with a dark border and a small seat glyph) on each hatch."""
    im, dr = _tri(128, YELLOW, (30, 30, 30))
    dr.rectangle((56, 50, 72, 86), fill=(30, 30, 30, 255)); dr.rectangle((50, 80, 78, 92), fill=(30, 30, 30, 255))
    dr.polygon([(64, 34), (74, 48), (54, 48)], fill=(30, 30, 30, 255))
    return place_top(im, d, x, z, size, parts, op=0.9, tol=0.6)


def rescue(d, z, side, parts):
    """External canopy-release marker: small red arrow pointing down at the release panel + RESCUE."""
    # 0.4.9: RESCUE lettering dropped (unreadable at 2K); the red arrow alone marks the release panel
    W, H = 60, 60
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    dr.polygon([(10, 4), (50, 4), (50, 28), (60, 28), (30, H - 4), (0, 28), (10, 28)], fill=RED + (255,))
    return place_side(im, d, z, side, 0.09, parts, xr=(0.2, 1.2), op=0.85)


def intake_danger(d, z, side, parts):
    """Intake danger marking: red chevron pointing forward + DANGER / INTAKE, outer flank (I6)."""
    t1 = text_img('DANGER', RED, px=56); t2 = text_img('INTAKE', STENCIL, px=44)
    W = 420; H = 170
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    # chevron: points toward the nose. Right side: image right = nose; left side: image left = nose
    if side > 0:
        dr.line([(150, 12), (200, 85), (150, 158)], fill=RED + (255,), width=16)
        dr.line([(196, 12), (246, 85), (196, 158)], fill=RED + (255,), width=16)
        x0 = 262
    else:
        dr.line([(270, 12), (220, 85), (270, 158)], fill=RED + (255,), width=16)
        dr.line([(224, 12), (174, 85), (224, 158)], fill=RED + (255,), width=16)
        x0 = 6
    s = 150 / max(t1.width, t2.width)
    t1 = t1.resize((int(t1.width * s), int(t1.height * s))); t2 = t2.resize((int(t2.width * s), int(t2.height * s)))
    # text dropped: unreadable at game texture size, the chevron alone carries the warning
    return place_side(im, d, z, side, 0.20, parts, xr=(1.6, 2.3), op=0.85)


def earth(d, z, side, parts):
    im = Image.new('RGBA', (96, 96), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    dr.ellipse((6, 6, 90, 90), outline=STENCIL + (255,), width=7)
    dr.line([(48, 18), (48, 50)], fill=STENCIL + (255,), width=7)
    for k, w in enumerate((30, 20, 10)):
        dr.line([(48 - w, 52 + k * 11), (48 + w, 52 + k * 11)], fill=STENCIL + (255,), width=6)
    return place_side(im, d, z, side, 0.10, parts, xr=(0.5, 2.3), op=0.85)


def jack(d, x, z, parts):
    """Jacking-point marker under the belly: dark triangle pointing at the point plus JACK."""
    # 0.4.9: JACK lettering dropped (unreadable at 2K); the triangle alone marks the point
    W, H = 98, 88
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    dr.polygon([(W / 2 - 40, 4), (W / 2 + 40, 4), (W / 2, 80)], outline=STENCIL + (255,), width=8)
    return place_top(im, d, x, z, 0.16 * W / 98, parts, op=0.85, down=True)


def radiation(d, z, side, xs, parts):
    """Radiation-hazard triangle on each EW canoe (E8)."""
    im, dr = _tri(128, YELLOW, (30, 30, 30))
    c = (64, 78)
    for k in range(3):
        a0 = -90 + k * 120 - 30
        dr.pieslice((c[0] - 26, c[1] - 26, c[0] + 26, c[1] + 26), a0, a0 + 60, fill=(30, 30, 30, 255))
    dr.ellipse((c[0] - 6, c[1] - 6, c[0] + 6, c[1] + 6), fill=(30, 30, 30, 255))
    R, U, Fc = _side_axes(side)
    return Decal(im, (d, side * xs, z), R, U, (0.14, 0.14), parts, facing=Fc, tol=0.3, opacity=0.9,
                 box={'x': (0.45, 0.9) if side > 0 else (-0.9, -0.45)})
