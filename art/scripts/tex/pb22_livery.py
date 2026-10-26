"""Painted liveries of the PB-22 skin: Maritime Blue and Low-Level Camo.
base_paint() lays the camouflage base coat on the exterior skin texels before the panel features of pb22_panels.py;
extras() adds the gold trident insignia and the hand-stencilled maintenance markings.
Mechanisms keep the default grey: the weapon bay, the gear wells, the inner faces of the gear doors, the intake ducts
and everything on the mech / dark / interior materials. The nozzles are on their own metal material and are untouched.

Colour references (sRGB):
  Maritime   Su-33 two-tone naval blue over light grey (Hataka AS83 set: Dark Grey-Blue / UN Blue / Faded Blue-Grey,
             radio-transparent parts Traffic White); flat black stencils, crimson warnings.
  Low-Level  Su-25 / Su-24 tactical scheme: sand, light green and grey-green blotches over a light grey-blue belly;
             red stencils, gold warnings."""
import math
import numpy as np
from PIL import Image, ImageDraw

GOLD = (201, 163, 72)

PALETTES = {
    'maritime': dict(top=(60, 80, 108), belly=(128, 134, 139), dielectric=(150, 152, 151),   # light tones matched to stock skin brightness (p90 ~130)
                     stencil=(26, 26, 27), red=(150, 22, 38), warn=(150, 22, 38), gold=GOLD),
    'lowlevel': dict(tan=(142, 128, 97), green=(98, 110, 79), grey=(106, 109, 106), belly=(130, 135, 137),
                     dielectric=(96, 100, 92), stencil=(150, 30, 28), red=(172, 34, 30), warn=(196, 160, 64), gold=GOLD),
}

BODY = ['nose', 'cockpit', 'fuselage_FF', 'fuselage_F', 'fuselage', 'fuselage_R', 'tail']
SIDEBODY = ['intake_R', 'intake_L', 'gearbay_R', 'gearbay_L']
LIFT = ['wing1_R', 'wing1_L', 'wing2_R', 'wing2_L', 'wingtip_R', 'wingtip_L', 'slat_R_visible', 'slat_L_visible',
        'slat2_R_visible', 'slat2_L_visible', 'flap_R_visible', 'flap_L_visible',
        'spoiler_R_visible', 'spoiler_L_visible', 'elevator_R_visible', 'elevator_L_visible', 'wingroot_R', 'wingroot_L']
TOPONLY = ['rudder_L', 'rudder_L_visible', 'hatch_PR', 'hatch_NR', 'hatch_PL', 'hatch_NL']
BELLYONLY = ['glovePylon_R', 'glovePylon_L', 'midPylon_R', 'midPylon_L']
CLOSE_DOORS = ['gearDoor_RO', 'gearDoor_RI', 'gearDoor_LO', 'gearDoor_LI', 'gearDoor_FR', 'gearDoor_FL', 'bayDoor_FR', 'bayDoor_FL', 'bayDoor_RR', 'bayDoor_RL']   # exterior faces down
LEG_DOORS = ['legDoor_R', 'legDoor_L']   # exterior face looks inboard with the gear down (down once the gear folds outboard)


def _c(t): return np.array(t, np.float32) / 255.0


def _sstep(a, b, v):
    t = np.clip((v - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def _idx(M, names):
    ids = [M.names.index(n) for n in names if n in M.names]
    return np.flatnonzero(np.isin(M.pid, ids) & (M.mat == 0))


def _interior(P, N):
    """Texels inside a mechanism: weapon bay, main and nose gear wells."""
    d = 17.0 - P[:, 1]; ax = np.abs(P[:, 0]); z = P[:, 2]
    bay = (d > 13.0) & (d < 24.6) & (ax < 1.03) & (z > 1.36) & (z < 2.85)
    well = (d > 19.25) & (d < 22.55) & (ax > 2.15) & (ax < 4.53) & (z > 1.31) & (z < 2.05)
    nose = (d > 10.1) & (d < 12.65) & (ax < 0.44) & (z > 1.38) & (z < 2.0)
    return bay | well | nose


def _demarcation(M):
    """Height of the top / belly colour break along the body: one third of the way up the side, from the keel
    to the top of the body (capped below the spine and the cockpit hump), smoothed along the length."""
    I = _idx(M, BODY)
    P = M.P[I]
    d = 17.0 - P[:, 1]
    edges = np.arange(0.0, 34.0, 0.25)
    k = np.clip(np.digitize(d, edges) - 1, 0, len(edges) - 2)
    zlo = np.full(len(edges) - 1, np.nan); zhi = np.full(len(edges) - 1, np.nan)
    for b in range(len(edges) - 1):
        zz = P[k == b, 2]
        if len(zz) < 50: continue
        zlo[b] = np.percentile(zz, 1); zhi[b] = min(np.percentile(zz, 99), 3.64)
    dem = zlo + (zhi - zlo) / 3.0
    c = 0.5 * (edges[:-1] + edges[1:])
    ok = ~np.isnan(dem)
    dem = np.interp(c, c[ok], dem[ok])
    w = np.ones(7) / 7.0
    dem = np.convolve(np.pad(dem, 3, mode='edge'), w, 'valid')
    return lambda dd: np.interp(dd, c, dem)


def _camo(P, vnoise):
    """Low-level tri-colour: large soft-edged blotches of tan, green and grey (3D noise, continuous over gaps)."""
    pal = PALETTES['lowlevel']
    n1 = vnoise(P, 2.6, seed=51, octaves=2)
    n2 = vnoise(P, 2.2, seed=52, octaves=2)
    a = _sstep(-0.012, 0.012, n1 - 0.16)            # tan blotches (about a third of the top)
    b = _sstep(-0.012, 0.012, n2 + 0.04)            # green vs grey in the rest
    col = _c(pal['grey'])[None] * (1 - b[:, None]) + _c(pal['green'])[None] * b[:, None]
    return col * (1 - a[:, None]) + _c(pal['tan'])[None] * a[:, None]


def base_paint(M, L, name, vnoise):
    pal = PALETTES[name]
    belly = _c(pal['belly'])
    dem = _demarcation(M)

    def top_col(P):
        if name == 'lowlevel': return _camo(P, vnoise)
        return np.tile(_c(pal['top']), (len(P), 1))

    def paint(I, t, doors=False):
        """t = 1 top colour, 0 belly colour. doors: the gear and bay doors are painted even where they sit inside a well
        or bay volume in the painting pose (the gear-down leg doors hang inside the main wheel well)."""
        if len(I) == 0: return
        P, N = M.P[I], M.N[I]
        keep = np.ones(len(I), bool) if doors else ~_interior(P, N)
        I, P, t = I[keep], P[keep], t[keep]
        L.col[I] = belly[None] * (1 - t[:, None]) + top_col(P) * t[:, None]

    # fuselage, intakes and gear pods: break at the lower third of the side with a gently wavy, lightly feathered edge
    I = np.concatenate([_idx(M, BODY), _idx(M, SIDEBODY)])
    P = M.P[I]
    wave = 0.05 * vnoise(P, 1.4, seed=41, octaves=2)
    t = _sstep(-0.02, 0.02, P[:, 2] - dem(17.0 - P[:, 1]) - wave)
    pod = np.isin(M.pid[I], [M.names.index(n) for n in ('gearbay_R', 'gearbay_L') if n in M.names])
    t = np.where(pod, np.maximum(t, _sstep(0.15, 0.35, M.N[I, 2])), t)     # upper faces of the gear pods
    paint(I, t)
    # wings and tailplanes: upper surfaces top colour, lower surfaces belly colour, break on the leading edge
    I = _idx(M, LIFT)
    paint(I, _sstep(-0.08, 0.08, M.N[I, 2]))
    I = _idx(M, TOPONLY); paint(I, np.ones(len(I), np.float32))
    I = _idx(M, BELLYONLY); paint(I, np.zeros(len(I), np.float32))
    # gear doors: only the exterior face; the inner face stays mechanism grey
    I = _idx(M, CLOSE_DOORS); I = I[M.N[I, 2] < -0.3]; paint(I, np.zeros(len(I), np.float32), doors=True)
    I = _idx(M, LEG_DOORS); I = I[M.N[I, 0] * np.sign(M.P[I, 0]) < -0.3]; paint(I, np.zeros(len(I), np.float32), doors=True)


# ================================================================== insignia and stencils
def trident_img(px=640):
    """Gold trident with a thin dark keyline: three barbed tines on a crossbar, a long handle (about twice the head) and a pommel."""
    W = int(px * 0.62); K = px; H = int(px * 1.55)        # K: head scale; the long handle fills the rest
    big = Image.new('RGBA', (W * 2, H * 2), (0, 0, 0, 0))
    s = 2.0

    def shapes(dr, grow, fill):
        g = grow
        cx = W * s / 2; sw = 0.062 * W * s                     # half shaft width
        # shaft
        dr.rectangle((cx - sw - g, 0.36 * K * s - g, cx + sw + g, (H - 0.07 * K) * s + g), fill=fill)
        # pommel
        dr.ellipse((cx - 2.2 * sw - g, (H - 0.10 * K) * s - g, cx + 2.2 * sw + g, (H - 0.015 * K) * s + g), fill=fill)
        # crossbar: curved up at the ends
        y0 = 0.36 * K * s; t = 0.045 * K * s
        xo = 0.36 * W * s
        dr.polygon([(cx - xo - g, y0 - 0.10 * K * s - g), (cx - xo + 2 * sw + g, y0 - 0.10 * K * s - g),
                    (cx - xo + 2 * sw + g, y0 - 0.02 * K * s), (cx, y0 + 0.02 * K * s - g),
                    (cx + xo - 2 * sw - g, y0 - 0.02 * K * s), (cx + xo - 2 * sw - g, y0 - 0.10 * K * s - g),
                    (cx + xo + g, y0 - 0.10 * K * s - g), (cx + xo + g, y0 + t * 0.6), (cx, y0 + t + 0.03 * K * s + g),
                    (cx - xo - g, y0 + t * 0.6)], fill=fill)
        # tines with barbed heads
        for xc, top in ((cx - xo + sw, 0.10), (cx, 0.03), (cx + xo - sw, 0.10)):
            yt = top * K * s
            dr.rectangle((xc - sw - g, yt + 0.06 * K * s, xc + sw + g, y0), fill=fill)
            dr.polygon([(xc, yt - g * 1.4), (xc + 2.6 * sw + g, yt + 0.11 * K * s + g), (xc + sw * 0.9, yt + 0.085 * K * s),
                        (xc - sw * 0.9, yt + 0.085 * K * s), (xc - 2.6 * sw - g, yt + 0.11 * K * s + g)], fill=fill)

    # keyline = the gold shape dilated by a true distance, so it is the same width everywhere (tine tips included)
    from scipy import ndimage
    shapes(ImageDraw.Draw(big), 0, GOLD + (255,))
    gold = np.asarray(big)[..., 3].astype(np.float32) / 255.0
    dist = ndimage.distance_transform_edt(gold < 0.5)
    key = np.clip(22.5 - dist, 0, 1)                       # 22 px at 2x = 11 px at the 640 px image
    a = np.maximum(key, gold)
    rgb = np.array((24, 22, 18), np.float32) * (1 - gold[..., None]) + np.array(GOLD, np.float32) * gold[..., None]
    out = np.dstack([rgb, a * 255]).round().clip(0, 255).astype(np.uint8)
    return Image.fromarray(out, 'RGBA').resize((W, H), Image.LANCZOS)


def boxed(ST, lines, col, px=64, box=True, pad=14, lw=6):
    """Stencilled text block, lines centred, optional thin frame (a stencilled box has small bridges at its corners)."""
    ims = [ST.text_img(t, col, px=px) for t in lines]
    W = max(i.width for i in ims) + 2 * pad; H = sum(i.height for i in ims) + 2 * pad
    im = Image.new('RGBA', (W, H), col + (0,))
    y = pad
    for i in ims:
        im.alpha_composite(i, ((W - i.width) // 2, y)); y += i.height
    if box:
        dr = ImageDraw.Draw(im); b = lw * 2
        for x0, y0, x1, y1 in ((b, 0, W - b, lw), (b, H - lw, W - b, H), (0, b, lw, H - b), (W - lw, b, W, H - b)):
            dr.rectangle((x0, y0, x1 - 1, y1 - 1), fill=col + (255,))
    return im


def arrow_img(col, px=96, down=True):
    im = Image.new('RGBA', (px, px), col + (0,)); dr = ImageDraw.Draw(im)
    if down:
        dr.polygon([(px * 0.32, 4), (px * 0.68, 4), (px * 0.68, px * 0.5), (px * 0.92, px * 0.5), (px / 2, px - 4),
                    (px * 0.08, px * 0.5), (px * 0.32, px * 0.5)], fill=col + (255,))
    return im


def extras(name, ST, FUSE_FWD, FUSE):
    pal = PALETTES[name]
    S, R, WN = pal['stencil'], pal['red'], pal['warn']
    F = []
    # gold trident insignia on both sides of the nose, below the cockpit glazing
    # lying along the fuselage with the tines toward the nose (image right is forward on the right side, aft on the left)
    tri = trident_img()
    for s in (1, -1):
        im = tri.rotate(-90 if s > 0 else 90, resample=Image.BICUBIC, expand=True)
        F.append(ST.place_side(im, 6.20, 2.58, s, 0.56, FUSE_FWD, xr=(0.3, 1.2), op=1.0))
    # maintenance markings: few, level, one stencil face, large enough to read at texture resolution (0.4.9: >= 0.18 m letters, about 9 texels at 2K)
    for s in (1, -1):
        F.append(ST.place_side(ST.text_img('AVIONICS', S, px=72), 9.20, 1.86, s, 0.28, FUSE_FWD, xr=(0.3, 1.2), op=0.85))
        F.append(ST.place_side(boxed(ST, ['FIRE ACCESS'], R, px=72, pad=18, lw=8), 27.6, 2.30, s, 0.40, FUSE, xr=(0.5, 2.3), op=0.9))
        F.append(ST.place_top(ST.text_img('FUEL', S, px=72), 22.95, s * 6.1, 2.30, 0.90, ['wing1_*', 'slat_*'], op=0.85, tol=0.3))
    F.append(ST.place_side(boxed(ST, ['O2'], S, px=72, pad=18, lw=8), 7.82, 2.40, -1, 0.30, FUSE_FWD, xr=(0.3, 1.2), op=0.85))
    # outer intake skin only (x -2.06); the inboard duct wall and the fuselage inside the duct also face outboard (0.9.1 fix)
    F.append(ST.place_side(ST.text_img('EXT PWR', S, px=72), 13.0, 1.72, -1, 0.26, ['intake_L'], xr=(1.9, 2.3), op=0.85))
    return F
