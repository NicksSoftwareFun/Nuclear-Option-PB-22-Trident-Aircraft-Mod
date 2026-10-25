"""PB-22 Trident skin spec: every panel line, fastener row, painted area and stencil of the skin atlas.
Read by tex_paint.py. Positions are world metres at rest pose (see DETAIL_PLAN_refs.txt):
  d = metres aft of the nose tip, x = right (+) / left (-), ax = |x| (an entry with ax applies to both sides),
  z = height above the ground. Lifting surfaces use chord fractions measured from the geometry (Planform).
Section numbers (N1, C4, I2 ...) are the item ids of DETAIL_PLAN_refs.txt.

Line weights (texels at 4096 are ~10 mm):
  MAJOR  4 cm wide, depth 1.0, faint albedo darkening, usually with a fastener row   (structural breaks)
  MINOR  2.4 cm wide, depth 0.55, normal map only                                    (skin laps, small panels)
"""
import numpy as np
from tex_feat import (F, Line, Box, Disc, Custom, Union, Inter, Minus, Groove, Fill, Relief, Dots, Decal, Tone, Rivets,
                      Surround, Planform, Centreline, smoothstep, hash01)
import os
import pb22_stencils as ST
import pb22_livery as LV

LIVERY = os.environ.get('PB22_LIVERY', 'grey')      # grey (default skin) | maritime | lowlevel

# ------------------------------------------------------------------ global look
BASE = (83, 92, 95)            # #535C5F matte cool grey (EW1 BDF Matte Gray family)
SMOOTH = 0.45                  # stock mean smoothness
DEPTH_M = 0.0030               # metres of engraving for depth 1.0 (normal-map strength)
DIELECTRIC = (72, 78, 81)      # radome, caps, antenna windows
ANTIGLARE = (46, 49, 51)
WALK = (77, 85, 88)
WALK_EDGE = (46, 49, 51)
MECHGREY = (112, 117, 120)     # spoiler undersides / coves (stock jet_mechanical is lighter and smoother)
LIP_METAL = (124, 130, 133)
SOOT = (42, 41, 40)
STENCIL = (46, 49, 51)
RED = (138, 43, 36)
YELLOW = (184, 149, 46)
WALK_A = 1.0                   # walkway fill opacity (the camouflage liveries keep only the walkway outlines)
if LIVERY != 'grey':
    _pal = LV.PALETTES[LIVERY]
    STENCIL, RED, YELLOW, DIELECTRIC = _pal['stencil'], _pal['red'], _pal['warn'], _pal['dielectric']
    WALK_EDGE = _pal['stencil']; WALK_A = 0.0
    ST.use_palette(_pal)

d, x, ax, z = F('d'), F('x'), F('ax'), F('z')
MAJOR = dict(width=0.040, depth=1.0, dark=0.13)
MEDIUM = dict(width=0.034, depth=0.8, dark=0.085)
MINOR = dict(width=0.026, depth=0.6, dark=0.06)
RIV = Rivets(pitch=0.075, offsets=(0.032,), r=0.012, depth=0.45, dark=0.03)
RIV2 = Rivets(pitch=0.075, offsets=(-0.032, 0.032), r=0.012, depth=0.45, dark=0.03)
RIVIN = Rivets(pitch=0.07, offsets=(-0.03,), r=0.009, depth=0.4, dark=0.025)

# ------------------------------------------------------------------ measured from the geometry at run time
WING = Planform(['wing1_*', 'wing2_*', 'wingtip_*', 'slat_*_visible', 'slat2_*_visible', 'flap_*_visible'], span='ax')
GLOVE = Planform(['wingroot_*'], span='ax')
FIN = Planform(['rudder_L', 'rudder_L_visible'], span='z')
TAILP = Planform(['elevator_*_visible'], span='ax')
NOSECL = Centreline(['nose', 'cockpit', 'fuselage_FF', 'fuselage_F'])
wc, gc, fc, tc = WING.field(), GLOVE.field(), FIN.field(), TAILP.field()

def up(P, N): return N[:, 2] > 0.05
def down(P, N): return N[:, 2] < -0.05
def outboard(t=0.3):
    return lambda P, N: N[:, 0] * np.sign(P[:, 0] + 1e-9) > t
def inboard(t=0.3):
    return lambda P, N: N[:, 0] * np.sign(P[:, 0] + 1e-9) < -t
def both(*fs):
    return lambda P, N: np.logical_and.reduce([f(P, N) for f in fs])

def zc_body(dd):
    """Body centre height: measured on the nose section, 2.45 m on the centre/rear body."""
    a = NOSECL.z(dd) if NOSECL.ok else np.full_like(dd, 2.35)
    return np.where(dd < 12.6, a, 2.45)

def theta_s(R=1.0):
    """Arc coordinate round the body (m at radius R), 0 at the belly centreline, pi*R at the top: spaces fasteners on frames."""
    def f(P):
        dd = 17.0 - P[:, 1]
        return np.arctan2(np.abs(P[:, 0]), zc_body(dd) - P[:, 2]) * R
    return F(f, 'theta')

FUSE_FWD = ['nose', 'cockpit', 'fuselage_FF', 'fuselage_F']
FUSE = ['fuselage', 'fuselage_R']
ALL_FUSE = FUSE_FWD + FUSE + ['cockpit']
WINGP = ['wing1_*', 'wing2_*', 'wingtip_*']


def frame(dd, parts, w=MINOR, riv=None, lim=(), along=None, where=None):
    return Groove(Line(d, dd, lim=lim, along=along or theta_s()), parts, rivets=riv, where=where, **w)

def stringer(zz, parts, d0, d1, w=MINOR, riv=None, where=None):
    return Groove(Line(z, zz, lim=[(d, d0, d1)], along=d), parts, rivets=riv, where=where, **w)

def panel(u, v, ur, vr, parts, r=0.03, w=MINOR, riv=None, where=None, fill=None, tone=0.0):
    s = Box(u, v, ur, vr, r)
    out = [Groove(s, parts, rivets=riv, where=where, **w)]
    if fill: out.insert(0, Fill(s, parts, where=where, **fill))
    if tone: out.insert(0, Fill(s, parts, where=where, mul=1 + tone, soft=0.004))
    return out


def cells_body(P, N):
    """Panel id on the fuselage: frame bay x stringer band x side."""
    dd = 17.0 - P[:, 1]
    fr = np.digitize(dd, [3.4, 4.4, 6.15, 8.0, 10.15, 11.8, 12.6, 14.6, 16.4, 18.2, 20.0, 21.8, 23.6, 25.5, 27.5, 29.0, 30.6, 31.4])
    st = np.digitize(P[:, 2], [1.72, 2.80, 3.25, 3.62])
    c = fr * 64 + st * 4 + (P[:, 0] > 0) * 2 + (N[:, 2] > 0.7)
    # the radome is one moulding: one tone (the stringer planes cut the taper at a shallow angle and aliased into steps)
    return np.where(dd < 4.4, fr * 64, c)

def cells_wing(P, N):
    c = WING.frac(P) if WING.ok else np.zeros(len(P))
    return (np.digitize(np.abs(P[:, 0]), np.arange(4.2, 14.0, 1.2)) * 64 + np.digitize(c, [0.15, 0.36, 0.56, 0.72]) * 4
            + (P[:, 0] > 0) * 2 + (N[:, 2] > 0))

def cells_generic(step=1.0):
    def f(P, N):
        return (np.floor((17 - P[:, 1]) / step) * 977 + np.floor(P[:, 2] / step) * 31 + np.floor(np.abs(P[:, 0]) / step) * 7
                + (P[:, 0] > 0) * 2 + (N[:, 2] > 0)).astype(np.int64)
    return f


# ================================================================== the spec
def features(M):
    S = []
    add = S.extend

    # ---------------------------------------------------------- per-panel tone (+-2.5 % luminance, +-0.03 smoothness)
    add([Tone(cells_body, ALL_FUSE + ['intake_*'], amp=0.03, sm_amp=0.03, seed=1),
         Tone(cells_wing, ['wing1_*', 'wing2_*', 'wingtip_*', 'slat_*', 'slat2_*', 'flap_*', 'spoiler_*'], amp=0.03, sm_amp=0.03, seed=2),
         Tone(cells_generic(1.0), ['wingroot_*', 'gearbay_*', 'rudder_*', 'elevator_*', 'tail*', 'glovePylon_*', 'midPylon_*',
                                    'legDoor_*', 'gearDoor_*', 'bayDoor_*'], amp=0.02, sm_amp=0.03, seed=3)])

    # ---------------------------------------------------------- N1 radome (dielectric) and nose
    def radome_sdf(P, N):
        dd = 17.0 - P[:, 1]
        zc = zc_body(dd)
        r = np.maximum(np.hypot(P[:, 0], P[:, 2] - zc), 0.05)
        phi = np.arctan2(P[:, 2] - zc, np.abs(P[:, 0]))                 # elevation in the section
        phib = np.radians(35 + 50 * smoothstep(1.6, 0.25, dd))          # flank line, rising to the tip
        s1 = dd - 4.40
        s2 = (phi - phib) * r
        k = 0.12                                                        # rounded corner where the ring meets the flank line
        a, b = s1 + k, s2 + k
        return np.sqrt(np.maximum(a, 0) ** 2 + np.maximum(b, 0) ** 2) + np.minimum(np.maximum(a, b), 0) - k
    rad = Custom(radome_sdf, along=lambda P, N: (17 - P[:, 1]) + np.arctan2(P[:, 2] - zc_body(17 - P[:, 1]), np.abs(P[:, 0])),
                 box={'d': (0, 4.6)})
    add([Fill(rad, FUSE_FWD + ['cockpit'], col=DIELECTRIC, soft=0.045, sm=0.47, alpha=1.0 if LIVERY == 'grey' else 0.0),   # liveries paint the radome in camouflage
         Groove(Custom(lambda P, N: (17.0 - P[:, 1]) - 4.40, box={'d': (4.2, 4.6)}),
                FUSE_FWD + ['cockpit'], width=0.022, depth=0.6, dark=0.05, bias=0.004)])   # only the ring seam: the flank seam aliased into beads
    # N3 retractable refuelling-probe door on the metal top strip
    add(panel(d, x, (1.35, 3.30), (-0.08, 0.08), FUSE_FWD, r=0.05, w=MEDIUM, where=up))
    # C6 anti-glare panel ahead of the windscreen
    def antiglare(P, N):
        dd = 17.0 - P[:, 1]
        hw = 0.12 + 0.23 * np.clip((dd - 3.2) / 1.75, 0, 1)
        return np.maximum.reduce([np.abs(P[:, 0]) - hw, 3.2 - dd, dd - 5.0, zc_body(dd) + 0.25 - P[:, 2]])
    add([Fill(Custom(antiglare, box={'d': (3.1, 5.1)}), FUSE_FWD + ['cockpit'], col=ANTIGLARE, soft=0.02, sm=0.30)])
    # N6 static ports and drain holes
    for dd, zz in ((5.35, 2.42), (5.55, 2.42)):
        add([Groove(Disc((dd, s * 0.0, zz), 0.03), FUSE_FWD, width=0.012, depth=0.5, where=outboard()) for s in (1,)])
    add([Groove(Disc((5.45, s * 0.86, 2.42), 0.035, axis=(s, 0, 0)), FUSE_FWD, width=0.014, depth=0.6) for s in (1, -1)])
    add([Fill(Disc((5.45, s * 0.86, 2.42), 0.022, axis=(s, 0, 0)), FUSE_FWD, mul=0.8, soft=0.006) for s in (1, -1)])
    # F2 forward ESM windows (flush dielectric patches)
    for s in (1, -1):
        b = Inter(Box(d, z, (4.60, 5.00), (2.18, 2.32), 0.03), Custom(lambda P, N, s=s: (0.3 - s * P[:, 0])))
        add([Fill(b, FUSE_FWD, col=DIELECTRIC, sm=0.53, soft=0.006, where=outboard(0.2)),
             Groove(b, FUSE_FWD, width=0.02, depth=0.6, where=outboard(0.2))])

    # ---------------------------------------------------------- forward fuselage frames / stringers (F5, 3.2)
    add([frame(7.60, FUSE_FWD + ['cockpit'], MEDIUM, RIV2),          # on the cockpit / cabin part split (was 8.00: read as a double seam); MEDIUM, not MAJOR
         frame(12.60, FUSE_FWD + FUSE, MAJOR, RIV2),
         frame(6.15, FUSE_FWD, MINOR, lim=[(z, 0, 2.95)]),
         frame(10.10, FUSE_FWD, MEDIUM, RIV),            # on the cabin / fuselage_F part split itself (was 10.15: read as a double seam)
         frame(11.80, FUSE_FWD, MINOR),
         frame(3.40, ['nose', 'fuselage_FF'], MINOR, lim=[(z, 2.55, 9)]),
         stringer(2.80, FUSE_FWD, 4.40, 12.6, MINOR),
         stringer(1.75, FUSE_FWD, 4.40, 12.6, MINOR),
         Groove(Line(x, 0.0, lim=[(d, 4.45, 12.55)], along=d), FUSE_FWD, where=down, **MINOR)])
    # 3.3 avionics bay doors (two each side below the hump), oxygen panel (left), nose-well door surround
    for d0, d1 in ((8.95, 9.45), (9.55, 10.05)):
        add(panel(d, z, (d0, d1), (2.02, 2.58), FUSE_FWD, r=0.03, w=MEDIUM, riv=RIVIN, where=outboard(0.4)))
    add(panel(d, z, (7.68, 7.96), (2.02, 2.20), FUSE_FWD + ['cockpit'], r=0.02, w=MINOR, where=both(outboard(0.4), lambda P, N: P[:, 0] < 0)))
    add([Groove(Box(d, x, (10.10, 12.60), (-0.47, 0.47), 0.04), ['fuselage_F', 'fuselage'], where=down, **MEDIUM, rivets=RIVIN)])
    # 1.3 / 3.5 airframe number and type code on the nose behind the radome break (low-vis), both sides
    for s in (1, -1):
        add([ST.text_side('214', d=5.05, zc=2.45, side=s, height=0.34, parts=FUSE_FWD, col=STENCIL, op=0.4, weight='bold'),
             ST.text_side('PB-22', d=7.10, zc=2.05 if LIVERY == 'grey' else 1.80, side=s, height=0.30, parts=FUSE_FWD + ['cockpit'], col=STENCIL, op=0.8)])

    # ---------------------------------------------------------- C4 cockpit: hatches, glazing seals, stencils
    # glazing: dark seal line round every pane, taken from the glass geometry
    add([Surround('PB22_glass', None, ['canopy*', 'cockpit*', 'hatch*', 'window*'], ['cockpit', 'fuselage_FF', 'fuselage_F', 'hatch*'],
                  width=0.022, depth=0.8, offset=0.010, dark=0.10)])
    # 0.4.7 porthole frames: seam where the frame bevel meets the skin, and a ring of 16 bolts on the flat frame face
    for sg_ in (1, -1):
        pc_, pa_ = (6.70, sg_ * 0.806, 3.251), (sg_, 0, 0.036)
        add([Groove(Disc(pc_, 0.207, axis=pa_), ['hatch_P*'], width=0.010, depth=0.6, dark=0.06),
             Groove(Disc(pc_, 0.153, axis=pa_), ['hatch_P*'], width=0.004, depth=0.05,
                    rivets=Rivets(pitch=2 * 3.1416 * 0.153 / 16, offsets=(0.0,), r=0.0075, depth=0.5, dark=0.06))])
    # separate hatch parts: seal groove on the hull round each one (from the geometry, follows the model)
    add([Surround('PB22_skin', None, ['hatch*'], FUSE_FWD, width=0.024, depth=0.9, offset=0.008, dark=0.08)])
    hatches = auto_hatches(M)
    real_hatches = any(n.startswith('hatch') or 'Hatch' in n for n in M.parts)
    for (d0, d1, x0, x1) in hatches:
        b = Box(d, x, (d0, d1), (x0, x1), 0.05)
        # the modelled gull-wing hatches wrap down the side, so a flat roof box drawn over them never meets their real
        # edge and left a second, jagged outline; the Surround above already follows the hatch geometry
        if not real_hatches: add([Groove(b, ['cockpit', 'hatch*', 'fuselage_FF', 'fuselage_F'], width=0.026, depth=0.9, dark=0.08, where=up,
                    rivets=Rivets(pitch=0.07, offsets=(0.03,), r=0.009, depth=0.4, dark=0.03))])
        xo = x1 if abs(x1) > abs(x0) else x0
        add([Groove(Line(x, xo - np.sign(xo) * 0.05, lim=[(d, d0 + 0.08, d1 - 0.08)], along=d), ['cockpit', 'hatch*'], where=up,
                    width=0.016, depth=0.5)])
        xm = (x0 + x1) / 2
        add([ST.eject_triangle(d=d0 + 0.20, x=xm, z=3.7, size=0.12, parts=['cockpit', 'hatch*', 'fuselage_F*'])])
    for s in (1, -1):        # external release (RESCUE) panels on the hump sides, one per crew row
        for dd in ((hatches[0][0] + hatches[0][1]) / 2 if hatches else 7.1, (hatches[-1][0] + hatches[-1][1]) / 2 if hatches else 9.0):
            # below the hatch sills (z 2.73-2.77): at z 2.80-2.95 the hatches covered them and the panel peeked out under the door (0.4.5)
            add(panel(d, z, (dd - 0.05, dd + 0.05), (2.54, 2.60), ['cockpit', 'fuselage_FF', 'fuselage_F'], r=0.01, w=MINOR,
                      where=outboard(0.3), fill=dict(col=YELLOW, sm=0.4, alpha=0.9, soft=0.004)))
            add([ST.rescue(d=dd, z=2.675, side=s, parts=['cockpit', 'fuselage_FF', 'fuselage_F'])])

    # ---------------------------------------------------------- 1.4 intakes
    def lip_e(P):           # metres aft of the raked lip (straight edge from the tip at d 10.0, z 3.15 to the lower lip at d 12.7, z 1.30)
        dd = 17.0 - P[:, 1]
        return dd - (10.0 + 2.7 * np.clip((3.15 - P[:, 2]) / 1.85, 0, 1))
    lip = F(lip_e, 'lip')
    add([Fill(Custom(lambda P, N: lip_e(P) - 0.12, box={'d': (9.9, 12.9)}), 'intake_*', col=LIP_METAL, sm=0.50, mt=0.2, soft=0.008),
         Groove(Line(lip, 0.12, along=z), 'intake_*', **MEDIUM, rivets=Rivets(pitch=0.07, offsets=(0.03,), r=0.009, depth=0.4, dark=0.02)),
         frame(13.20, 'intake_*', MINOR, along=z), frame(13.90, 'intake_*', MINOR, along=z),
         stringer(2.62, 'intake_*', 11.0, 14.6, MINOR, where=outboard(0.5))])
    # I2 auxiliary doors: gap line round the modelled doors (MECH inserts) + spec rectangles as a fallback
    add([Surround('PB22_skin', 'PB22_mech', 'intake_*', 'intake_*', width=0.02, depth=0.8, offset=0.006, dark=0.08)])
    # (no perforated bleed panel: the inner duct wall stays one uniform surface, 2026-10-18)
    # G4 landing-light panels on the intake undersides
    add(panel(d, ax, (13.00, 13.30), (1.47, 1.65), 'intake_*', r=0.03, w=MEDIUM, where=down,
              fill=dict(col=(64, 70, 73), sm=0.55, soft=0.006)))
    # I6 intake danger chevron + text, outer flank ahead of the doors
    for s in (1, -1):
        add([ST.intake_danger(d=11.60, z=2.40, side=s, parts='intake_*')])
    # 3.3 refuel / ground-power panel (right side below the intake) + earthing point
    add(panel(d, z, (12.85, 13.15), (1.42, 1.62), ['intake_R', 'fuselage'], r=0.02, w=MEDIUM, riv=None,
              where=both(outboard(0.3), lambda P, N: P[:, 0] > 0)))
    # 0.4.9: REFUEL lettering dropped (6 cm letters can't be read at 2K, 2026-10-19)
    add([ST.earth(d=13.45, z=1.55, side=1, parts=['intake_R', 'fuselage'])])

    # ---------------------------------------------------------- 1.7 centre fuselage, spine, belly
    for dd in (16.4, 18.2, 20.0, 21.8, 23.6):
        add([frame(dd, FUSE, MINOR)])
    add([frame(14.60, FUSE, MAJOR, RIV2), frame(14.60, 'intake_*', MAJOR, RIV2, along=z),   # one seam where the intakes end (the intake frame was at 14.55: read as a double line) frame(25.50, FUSE, MAJOR, RIV2),
         stringer(3.25, FUSE, 14.6, 31.4, MINOR, where=outboard(0.25)),
         stringer(1.70, FUSE, 12.6, 31.4, MINOR, where=outboard(0.25))])
    # weapon-bay surround (S8): frame line with fasteners just outside each opening
    for dc, ln in ((15.9, 5.7), (21.85, 5.4)):
        add([Groove(Box(d, x, (dc - ln / 2, dc + ln / 2), (-1.0, 1.0), 0.04), FUSE, where=down, width=0.03, depth=0.8, bias=0.05,
                    rivets=Rivets(pitch=0.075, offsets=(0.09,), r=0.010, depth=0.45, dark=0.03))])
    # spine: flank panel row (S1) and top seam
    def spine_h(P):
        dd = 17.0 - P[:, 1]
        u = np.maximum(dd - 24.78, 0.0)
        return (3.64 + (dd - 15.0) * 0.06 + 0.344 * u * u) - P[:, 2]      # = spine_top() in build_pb22_detail.py
    sh = F(spine_h, 'spine_h')
    spine_side = lambda P, N: (np.abs(P[:, 0]) < 0.55) & (P[:, 2] > 3.62) & (np.abs(N[:, 0]) > 0.35)
    k = 0
    dd = 15.6
    while dd < 26.4:
        ln = 0.45 + 0.15 * (k % 3 == 1)
        add(panel(d, sh, (dd, dd + ln), (0.10, 0.36), FUSE, r=0.025, w=MINOR,
                  riv=Rivets(pitch=0.065, offsets=(-0.025,), r=0.008, depth=0.35, dark=0.02), where=spine_side))
        dd += ln + 0.06; k += 1
    add([Groove(Line(x, 0.0, lim=[(d, 15.2, 26.5)], along=d), FUSE, where=lambda P, N: N[:, 2] > 0.6, **MINOR)])
    # spine top walkway (3.4) and GNSS patches (S5)
    add([Fill(Box(d, x, (15.3, 21.5), (-0.13, 0.13), 0.03), FUSE, col=WALK, alpha=WALK_A, soft=0.01, sm=0.32, where=lambda P, N: (N[:, 2] > 0.75) & (P[:, 2] > 3.6)),
         Groove(Box(d, x, (15.3, 21.5), (-0.13, 0.13), 0.03), FUSE, width=0.016, depth=0.3, dark=0.10, where=lambda P, N: (N[:, 2] > 0.75) & (P[:, 2] > 3.6))])
    for dd in (14.6 - 0.35, 22.6):
        c = Disc((dd, 0.0, 3.62 if dd < 15 else 3.64 + (dd - 15) * 0.06 + 0.344 * max(dd - 24.78, 0) ** 2), 0.06)
        add([Fill(c, FUSE, col=DIELECTRIC, sm=0.53, soft=0.006, where=up), Groove(c, FUSE, width=0.016, depth=0.5, where=up)])
    # 3.3 spine fuel access panels (top of the nacelle box beside the spine)
    for dd in np.arange(16.0, 24.1, 1.5):
        add(panel(d, ax, (dd, dd + 0.42), (0.62, 0.92), FUSE, r=0.04, w=MINOR, riv=RIVIN, where=lambda P, N: N[:, 2] > 0.8))
    # E6 dorsal chaff / flare dispensers
    for xc in (1.05, 1.40):
        b = Box(d, ax, (25.84, 26.46), (xc - 0.11, xc + 0.11), 0.015)
        add([Fill(b, FUSE, col=(62, 68, 71), soft=0.006, sm=0.38, where=up),
             Groove(b, FUSE, width=0.022, depth=1.0, dark=0.08, where=up),
             Dots(b, d, ax, pitch=(0.052, 0.052), r=0.019, depth=0.55, col=(52, 57, 60), parts=FUSE, where=up, stagger=False, square=True, inset=0.018)])
    # S8 / 3.5 jacking points
    add([ST.jack(d=12.80, x=0.0, z=None, parts=FUSE_FWD + ['fuselage']),
         ST.jack(d=21.0, x=2.05, z=None, parts=['gearbay_*', 'wingroot_*', 'fuselage']),
         ST.jack(d=21.0, x=-2.05, z=None, parts=['gearbay_*', 'wingroot_*', 'fuselage'])])

    # ---------------------------------------------------------- rear fuselage, engine bays, hot section
    for dd in (27.5, 29.0):
        add([frame(dd, FUSE, MINOR, along=theta_s())])
    add([frame(30.6, FUSE, MEDIUM, RIV)])
    for d0, d1 in ((26.0, 28.2), (28.4, 30.5)):             # S6 engine access doors
        b = Box(d, z, (d0, d1), (1.85, 3.05), 0.06)
        add([Groove(b, FUSE, where=outboard(0.45), **MEDIUM, rivets=RIVIN),
             Groove(Line(z, 3.00, lim=[(d, d0 + 0.08, d1 - 0.08)], along=d), FUSE, where=outboard(0.45), width=0.014, depth=0.45,
                    rivets=Rivets(pitch=0.11, offsets=(-0.025,), r=0.012, depth=0.5))])
        for k in range(3):                                   # latches along the bottom
            dl = d0 + (d1 - d0) * (k + 1) / 4
            add([Groove(Box(d, z, (dl - 0.06, dl + 0.06), (1.90, 1.95), 0.01), FUSE, where=outboard(0.45), width=0.012, depth=0.6)])
    for dd in (27.2, 29.2):                                    # S7 flush NACA inlets
        b = Custom(lambda P, N, dd=dd: naca_sdf(P, dd, 2.75), box={'d': (dd - 0.2, dd + 0.2)})
        add([Relief(b, FUSE, height=-0.9, bevel=0.03, where=outboard(0.45), mul=0.75)])
    for s in (1, -1):                                          # E4 vent louvres on the nacelle undersides
        for k in range(3):
            b = Box(d, x, (29.65 + k * 0.26, 29.83 + k * 0.26), (s * 0.9 - 0.12, s * 0.9 + 0.12), 0.015)
            add([Relief(b, FUSE, height=-0.8, bevel=0.02, where=down, mul=0.7)])
    # E1 hot band round each nozzle (heat-tinted metal), E3 soot
    def hot_sdf(P, N):
        dd = 17.0 - P[:, 1]
        r = np.minimum(np.hypot(P[:, 0] - 0.74, P[:, 2] - 2.40), np.hypot(P[:, 0] + 0.74, P[:, 2] - 2.40))
        return np.maximum(30.8 - dd, r - 0.95)
    def hot_grad(P):
        t = np.clip((17.0 - P[:, 1] - 30.8) / 0.6, 0, 1)
        return t
    hot = Custom(hot_sdf, box={'d': (30.5, 32.2)})
    add([Fill(hot, FUSE + ['tail*'], col=(90, 92, 94), soft=0.12, sm=0.42, mt=0.2, alpha=0.7),
         Fill(hot, FUSE + ['tail*'], col=(66, 66, 66), soft=0.12, alpha=0.35, grad=lambda P: smoothstep(0.15, 0.55, hot_grad(P))),
         Fill(hot, FUSE + ['tail*'], col=(75, 81, 96), soft=0.2, alpha=0.35, grad=lambda P: smoothstep(0.65, 1.0, hot_grad(P))),
         Groove(Line(d, 30.80, lim=[], along=theta_s()), FUSE, where=lambda P, N: hot_sdf(P, N) < 0.1, **MINOR)])
    def soot_sdf(P, N):
        dd = 17.0 - P[:, 1]
        return np.maximum.reduce([31.0 - dd, np.abs(P[:, 0]) - 0.55 - 0.25 * smoothstep(31, 33, dd), P[:, 2] - 2.75])
    add([Fill(Custom(soot_sdf, box={'d': (30.6, 34)}), FUSE + ['tail*'], col=SOOT, soft=0.45, alpha=0.3, sm_add=-0.12),
         Fill(Custom(lambda P, N: np.maximum.reduce([31.2 - (17 - P[:, 1]), np.abs(P[:, 0]) - 1.7]), box={'d': (30.8, 34)}),
              'elevator_*', col=SOOT, soft=0.5, alpha=0.30, sm_add=-0.08, where=down)])
    # S3 APU exhaust soot streak (right fillet flank)
    add([Fill(Custom(lambda P, N: np.maximum(np.hypot(((17 - P[:, 1]) - 26.1 - 0.35) / 2.2, P[:, 2] - 4.30) - 0.12, -P[:, 0]),
                     box={'d': (25.8, 27.4)}), FUSE + ['rudder_L'], col=SOOT, soft=0.25, alpha=0.35, sm_add=-0.08)])

    # ---------------------------------------------------------- 1.5 glove / wing roots
    gl = ['wingroot_*']
    add([Groove(Line(gc, 0.08, lim=[(ax, 1.95, 5.32)], along=ax), gl, **MINOR),
         Groove(Line(gc, 0.15, lim=[(ax, 1.95, 5.32)], along=ax), gl, **MEDIUM, rivets=RIV2),
         Groove(Line(gc, 0.70, lim=[(ax, 1.95, 5.32)], along=ax), gl, **MEDIUM, rivets=RIV),
         Groove(Line(ax, 5.30, along=d), gl, **MEDIUM, rivets=RIV)])
    for xx in (2.6, 3.3, 4.0):
        add([Groove(Line(ax, xx, lim=[(gc, 0.15, 0.70)], along=d), gl, **MINOR)])
    add([Groove(Box(d, ax, (19.55, 23.25), (3.95, 4.95), 0.35), gl, where=up, **MEDIUM, rivets=RIVIN)])     # pivot blister
    # W2 glove walkways
    wk = Box(d, ax, (18.2, 23.3), (2.05, 3.85), 0.06)
    add([Fill(wk, gl, col=WALK, alpha=WALK_A, sm=0.30, soft=0.008, where=up),
         Groove(wk, gl, width=0.022, depth=0.25, dark=0.12, where=up)])
    # W3 sweep index marks
    for k, a in enumerate((20, 30, 45, 65)):
        add([Fill(Box(d, ax, (22.05 + k * 0.25, 22.09 + k * 0.25), (5.02, 5.22), 0.005), gl, col=(150, 156, 158), alpha=0.6,
                  soft=0.004, where=up)])
    # 4.7 glove LE edge band
    add([Fill(Custom(lambda P, N: (GLOVE.frac(P) - 0.03) * GLOVE.chord_len(P)), gl, mul=0.90, soft=0.03)])

    # ---------------------------------------------------------- 1.6 outer wings
    add([Groove(Line(wc, 0.150, lim=[(ax, 4.25, 13.15)], along=ax), WINGP, **MAJOR, rivets=RIV2),
         Groove(Line(wc, 0.560, lim=[(ax, 4.25, 13.15)], along=ax), WINGP, **MAJOR, rivets=RIV2, where=down),
         Groove(Line(wc, 0.560, lim=[(ax, 4.25, 6.17)], along=ax), WINGP, **MAJOR, rivets=RIV2, where=up),
         Groove(Line(wc, 0.560, lim=[(ax, 11.13, 13.15)], along=ax), WINGP, **MAJOR, rivets=RIV2, where=up),
         Groove(Line(wc, 0.360, lim=[(ax, 4.25, 13.15)], along=ax), WINGP, **MINOR),
         Groove(Line(wc, 0.715, lim=[(ax, 4.25, 13.6)], along=ax), WINGP, **MEDIUM),
         Groove(Line(ax, 13.20, along=d), WINGP + ['slat_*', 'slat2_*', 'flap_*'], **MEDIUM, rivets=RIV)])
    for xx in np.arange(4.8, 13.0, 0.6):
        add([Groove(Line(ax, xx, lim=[(wc, 0.15, 0.56)], along=d), WINGP, **MINOR)])
    for k, xx in enumerate(np.arange(5.1, 12.6, 1.2)):        # O5 fuel access panels, lower surface, every other rib bay
        add(panel(ax, wc, (xx + 0.08, xx + 0.52), (0.40, 0.50), WINGP, r=0.06, w=MEDIUM, riv=RIVIN, where=down))
    for xx in (5.9, 8.9, 11.9):                                 # upper-surface fuel filler / inspection discs
        pass
    # 4.7 RAM-style edge band on the slat LE and leading edges
    add([Fill(Custom(lambda P, N: (WING.frac(P) - 0.025) * WING.chord_len(P)), ['slat_*', 'slat2_*'], mul=0.90, soft=0.03)])
    # slats, flaps: chordwise breaks + hinge fittings
    for a, b in ((5.6, 9.4), (9.45, 11.08), (11.12, 13.2)):
        add([Groove(Line(ax, (a + b) / 2, lim=[(wc, 0.0, 0.12)], along=d), ['slat_*', 'slat2_*'], **MINOR)])
    for a, b in ((5.05, 7.60), (7.65, 10.10), (10.15, 12.55)):
        add([Groove(Line(wc, 0.80, lim=[(ax, a + 0.04, b - 0.04)], along=ax), 'flap_*', where=up, **MINOR)])
        for xx in np.linspace(a + 0.25, b - 0.25, 3):          # O2 flap hinge fittings (flap LE + wing cove)
            hb = Box(ax, wc, (xx - 0.03, xx + 0.03), (0.725, 0.775), 0.01)
            add([Relief(hb, 'flap_*', height=0.8, bevel=0.01, mul=0.92),
                 Relief(Box(ax, wc, (xx - 0.035, xx + 0.035), (0.66, 0.72), 0.01), WINGP, height=0.8, bevel=0.01, where=down, mul=0.9)])
    # O1 spoilers: top edge seams, undersides (mechanism), coves
    for a, b in ((6.2, 8.6), (8.7, 11.1)):
        L = b - a
        und = lambda P, N: N[:, 2] < -0.3
        add([Fill(Box(ax, wc, (a - 0.1, b + 0.1), (0.5, 0.8), 0.0), 'spoiler_*', col=MECHGREY, sm=0.55, soft=0.0, where=und),
             Groove(Box(ax, wc, (a, b), (0.56, 0.71), 0.01), 'spoiler_*', where=und, width=0.03, depth=0.8, bias=-0.03)])
        for xx in np.arange(a + 0.25, b - 0.1, 0.5):         # stiffener ribs
            add([Groove(Line(ax, xx, lim=[(wc, 0.575, 0.695)], along=wc), 'spoiler_*', where=und, width=0.04, depth=-1.0, dark=0.05)])
        add([Groove(Line(wc, 0.64, lim=[(ax, a + 0.08, b - 0.08)], along=ax), 'spoiler_*', where=und, width=0.04, depth=-1.0, dark=0.05)])
        for xx in (a + L / 4, a + 3 * L / 4):                  # hinge brackets at the LE
            add([Relief(Box(ax, wc, (xx - 0.035, xx + 0.035), (0.562, 0.598), 0.008), 'spoiler_*', height=1.0, bevel=0.008,
                        where=und, mul=0.88, edge_dark=0.15),
                 Relief(Disc((0, 0, 0), 0.01), 'spoiler_*', height=0.0)])
            add([Fill(Box(ax, wc, (xx - 0.035, xx + 0.035), (0.565, 0.575), 0.004), 'spoiler_*', mul=0.55, soft=0.004, where=und)])
        xm = a + L / 2                                           # actuator rod-end fitting
        add([Relief(Box(ax, wc, (xm - 0.05, xm + 0.05), (0.60, 0.665), 0.012), 'spoiler_*', height=1.1, bevel=0.01, where=und,
                    mul=0.85, edge_dark=0.15),
             Fill(Box(ax, wc, (xm - 0.018, xm + 0.018), (0.62, 0.645), 0.015), 'spoiler_*', mul=0.5, soft=0.006, where=und)])
        # cove on the wing under the spoiler
        cove = Box(ax, wc, (a - 0.02, b + 0.02), (0.555, 0.715), 0.01)
        add([Fill(cove, WINGP, col=MECHGREY, sm=0.55, soft=0.006, where=up),
             Groove(cove, WINGP, width=0.03, depth=0.9, dark=0.12, where=up, bias=0.012)])
        for xx in (a + L / 4, a + 3 * L / 4):
            add([Relief(Box(ax, wc, (xx - 0.04, xx + 0.04), (0.556, 0.585), 0.008), WINGP, height=0.9, bevel=0.008, where=up, mul=0.85)])
        add([Relief(Box(ax, wc, (xm - 0.06, xm + 0.06), (0.58, 0.69), 0.03), WINGP, height=-0.8, bevel=0.015, where=up, mul=0.78),
             Groove(Box(ax, wc, (xm - 0.06, xm + 0.06), (0.58, 0.69), 0.03), WINGP, width=0.016, depth=0.5, where=up)])
        add([Groove(Line(ax, xx, lim=[(wc, 0.56, 0.71)], along=wc), WINGP, where=up, width=0.02, depth=0.4)
             for xx in np.arange(a + 0.5, b - 0.2, 0.5)])
    # O4 wingtip formation-light strip
    add([Fill(Box(ax, wc, (13.25, 13.62), (0.40, 0.44), 0.01), WINGP, col=(110, 120, 105), sm=0.6, soft=0.004, where=up)])

    # ---------------------------------------------------------- 1.8 gear pods
    pods = ['gearbay_*']
    add([Groove(Line(d, dd, along=z), pods, **MINOR) for dd in (18.6, 23.35, 26.0)] +
        [Groove(Line(d, 24.90, along=z), pods, **MEDIUM, rivets=RIV)])
    add([Groove(Line(z, 1.86, lim=[(d, 18.2, 26.6)], along=d), pods, where=outboard(0.6), **MINOR)])
    add([Groove(Box(d, ax, (19.25, 22.55), (2.24, 4.53), 0.04), pods, where=down, width=0.03, depth=0.6, bias=0.06,
                rivets=Rivets(pitch=0.075, offsets=(0.10,), r=0.010, depth=0.45, dark=0.03))])
    for d0, d1, z0, z1 in ((23.45, 24.15, 1.50, 1.80), (25.0, 25.6, 1.48, 1.76)):
        add(panel(d, z, (d0, d1), (z0, z1), pods, r=0.03, w=MEDIUM, riv=RIVIN, where=outboard(0.5)))
    # gear doors: inset fastener frame on the outer face
    add([Groove(Box(d, ax, (19.3, 22.5), (2.3, 4.45), 0.03), 'gearDoor_*', where=down, width=0.012, depth=0.3, bias=-0.03,
                rivets=Rivets(pitch=0.08, offsets=(-0.04,), r=0.009, depth=0.35, dark=0.02))])
    # G2 leg door: stiffener lattice on its inner face
    leg_in = lambda P, N: N[:, 0] * np.sign(P[:, 0]) > 0.5
    for k in range(-4, 5):
        add([Groove(Line(F(lambda P, s=1: (17 - P[:, 1]) + s * P[:, 2]), 0.0 + 20.9 + 1.5 + k * 0.42, along=z), 'legDoor_*',
                    where=leg_in, width=0.03, depth=-0.6),
             Groove(Line(F(lambda P, s=-1: (17 - P[:, 1]) + s * P[:, 2]), 20.9 - 1.5 + k * 0.42, along=z), 'legDoor_*',
                    where=leg_in, width=0.03, depth=-0.6)])
    add([Groove(Box(d, z, (19.32, 22.48), (0.96, 2.06), 0.03), 'legDoor_*', where=leg_in, width=0.05, depth=-0.7, bias=-0.04)])

    # ---------------------------------------------------------- 1.10 fin and rudder
    fn = ['rudder_L']
    add([Groove(Line(fc, 0.15, lim=[(z, 4.0, 7.3)], along=z), fn, **MAJOR, rivets=RIV2),
         Groove(Line(fc, 0.68, lim=[(z, 4.0, 7.3)], along=z), fn, **MAJOR, rivets=RIV2),
         Groove(Line(z, 4.60, lim=[(fc, 0.0, 0.70)], along=d), fn, **MEDIUM),
         Groove(Line(z, 7.25, along=d), fn, **MEDIUM, rivets=RIV)])
    for zz in np.arange(5.05, 7.2, 0.45):
        add([Groove(Line(z, zz, lim=[(fc, 0.15, 0.68)], along=d), fn, **MINOR)])
    for zz in np.arange(3.75, 4.6, 0.22):                      # T4 fillet ladder of small panels
        add([Groove(Line(z, zz, lim=[(fc, 0.08, 0.45)], along=d), fn, **MINOR)])
    add([Groove(Line(fc, 0.30, lim=[(z, 3.7, 4.6)], along=z), fn, **MINOR)])
    # T1 dielectric tip cap and pod tips
    add([Fill(Custom(lambda P, N: 7.25 - P[:, 2], box={'z': (7.1, 8)}), ['rudder_L*'], col=DIELECTRIC, sm=0.53, soft=0.01),
         Fill(Custom(lambda P, N: 33.55 - (17 - P[:, 1]), box={'z': (6.8, 8)}), ['rudder_L*', 'tail*'], col=DIELECTRIC, sm=0.53, soft=0.01)])
    # T2 two-section rudder split with a step; T6 formation light
    rd = ['rudder_L_visible']
    add([Groove(Line(z, 5.90, lim=[(d, 0, 31.70)], along=d), rd, width=0.02, depth=0.8, dark=0.06),
         Groove(Line(z, 5.94, lim=[(d, 31.70, 40)], along=d), rd, width=0.02, depth=0.8, dark=0.06),
         Groove(Line(d, 31.70, lim=[(z, 5.90, 5.94)], along=z), rd, width=0.02, depth=0.8)])
    # formation light strip centred in the fin panels (32-62 % chord), not over the leading edge (2026-10-18)
    add([Fill(Custom(lambda P, N: np.maximum((np.abs(FIN.frac(P) - 0.47) - 0.15) * FIN.chord_len(P), np.abs(P[:, 2] - 6.60) - 0.025), box={'z': (6.5, 6.7)}),
              fn, col=(110, 120, 105), sm=0.6, soft=0.004)])
    add([Fill(Custom(lambda P, N: (FIN.frac(P) - 0.03) * FIN.chord_len(P)), fn, mul=0.90, soft=0.03, box={'z': (3.9, 7.6)})])

    # ---------------------------------------------------------- 1.12 tailplanes
    tp = ['elevator_*']
    add([Groove(Line(tc, 0.15, lim=[(ax, 1.15, 5.0)], along=ax), tp, **MAJOR, rivets=RIV2),
         Groove(Line(tc, 0.65, lim=[(ax, 1.15, 4.9)], along=ax), tp, **MAJOR, rivets=RIV2)])
    for xx in np.arange(1.7, 5.0, 0.5):
        add([Groove(Line(ax, xx, lim=[(tc, 0.15, 0.65)], along=d), tp, **MINOR)])
    add([Groove(Disc((29.9, s * 1.80, 2.12), 0.175, axis=(0, 0, 1)), tp, **MEDIUM,
                rivets=Rivets(pitch=0.07, offsets=(-0.03,), r=0.009, depth=0.4, dark=0.03)) for s in (1, -1)])
    add([Fill(Custom(lambda P, N: (TAILP.frac(P) - 0.03) * TAILP.chord_len(P)), tp, mul=0.90, soft=0.03)])     # H2
    # H3 dark root gap on the fuselage round the tailplane roots
    add([Fill(Custom(lambda P, N: np.hypot(np.abs(P[:, 0]) - 1.15, (P[:, 2] - 2.12) * 1.0) - 0.07, box={'d': (26.8, 32.8)}),
              FUSE, mul=0.80, soft=0.06)])

    # ---------------------------------------------------------- 1.11 / 2 tail cone and EW module
    tl = ['tail*']
    add([Groove(Line(d, 28.0, along=theta_s()), tl + FUSE, **MEDIUM, rivets=RIV),
         Groove(Line(d, 30.60, along=theta_s()), tl, **MINOR)])
    add([Fill(Custom(lambda P, N: 32.58 - (17 - P[:, 1]), box={'d': (32.4, 34.2)}), tl, col=DIELECTRIC, sm=0.53, soft=0.008),
         Groove(Line(d, 32.56, along=theta_s()), tl, width=0.02, depth=0.9, dark=0.06),
         Groove(Line(d, 32.52, along=theta_s()), tl, width=0.014, depth=0.5)])          # 40 mm clamp band
    # E4 bullet: chute doors + dielectric cap; E3 canoe caps; E5 MAWS domes
    add([Fill(Custom(lambda P, N: np.maximum(33.10 - (17 - P[:, 1]), 3.65 - P[:, 2]), box={'d': (32.9, 34)}), tl + ['rudder_L*'],
              col=DIELECTRIC, sm=0.53, soft=0.008)])
    for xx0, xx1 in ((-0.14, 0.0), (0.0, 0.14)):
        add([Groove(Box(d, x, (31.70, 32.90), (xx0, xx1), 0.02), tl + ['rudder_L*'], where=lambda P, N: (N[:, 2] > 0.4) & (P[:, 2] > 3.7),
                    width=0.018, depth=0.7)])
    add([Fill(Custom(lambda P, N: np.maximum(32.93 - (17 - P[:, 1]), np.abs(np.abs(P[:, 0]) - 0.57) - 0.10), box={'d': (32.8, 33.2)}),
              tl, col=DIELECTRIC, sm=0.53, soft=0.008, where=lambda P, N: np.abs(P[:, 0]) > 0.45)])
    for s in (1, -1):
        add([Fill(Disc((31.6, s * 0.34, 3.60), 0.07), tl, col=DIELECTRIC, sm=0.55, soft=0.008, alpha=1.0 if LIVERY == 'grey' else 0.0)])
        add([Fill(Disc((26.5, s * 0.60, 1.45), 0.07), FUSE, col=DIELECTRIC, sm=0.55, soft=0.008)])
        add([Fill(Disc((9.6, s * 0.82, 2.90), 0.06), FUSE_FWD + ['cockpit'], col=DIELECTRIC, sm=0.55, soft=0.008)])
        add([ST.radiation(d=31.6, z=3.30, side=s, xs=0.70, parts=tl)])
    # E2 vent strip on the chin fairing aft face
    add([Dots(Box(x, z, (-0.15, 0.15), (2.99, 3.04), 0.01), x, z, pitch=(0.022, 0.022), r=0.007, depth=0.8, col=(40, 43, 45),
              parts=tl, where=lambda P, N: N[:, 1] < -0.6, stagger=True, box={'d': (32.9, 33.3)})])

    # ---------------------------------------------------------- 3.4 NO STEP stencils (one per surface)
    for s in (1, -1):
        add([ST.nostep(d=24.25, x=s * 9.0, z=2.25, parts='flap_*', size=0.26),
             
             
             ST.nostep(d=30.4, x=s * 3.0, z=2.2, parts='elevator_*', size=0.26),
             ST.nostep(d=22.0, x=s * 4.3, z=2.40, parts='wing1_*', size=0.26)])
    # insignia and hand-stencilled maintenance markings of the painted liveries
    if LIVERY != 'grey':
        add(LV.extras(LIVERY, ST, FUSE_FWD, FUSE))
    return S


def naca_sdf(P, dd, zz):
    """Flush NACA inlet planform in (d, z): narrow at the front, 0.25 m long, 0.10 m wide at the aft lip."""
    u = (17.0 - P[:, 1]) - (dd - 0.125)
    hw = 0.015 + 0.035 * np.clip(u / 0.25, 0, 1) ** 1.5
    return np.maximum.reduce([np.abs(P[:, 2] - zz) - hw, -u, u - 0.25])


def auto_hatches(M):
    """Roof hatches: separate parts named hatch* if the model has them (their footprint from the geometry),
    otherwise four hatches over the seats (two rows, left/right) on the hump roof."""
    out = []
    for n, (I, dd) in M.parts.items():
        if n.startswith('hatch') or 'Hatch' in n:
            P = M.P[I]; N = M.N[I]; m = N[:, 2] > 0.5
            if m.sum() < 50: continue
            P = P[m]
            out.append((float(np.percentile(17 - P[:, 1], 0.5)), float(np.percentile(17 - P[:, 1], 99.5)),
                        float(np.percentile(P[:, 0], 0.5)), float(np.percentile(P[:, 0], 99.5))))
    if out: return sorted(out)
    return [(6.45, 7.55, 0.06, 0.46), (6.45, 7.55, -0.46, -0.06), (8.35, 9.45, 0.06, 0.46), (8.35, 9.45, -0.46, -0.06)]


# ================================================================== whole-skin passes after the features
def base_paint(M, L):
    """Camouflage base coat for the painted liveries (before every feature); the default skin keeps BASE."""
    if LIVERY != 'grey':
        LV.base_paint(M, L, LIVERY, vnoise_ref[0])


vnoise_ref = [None]


def finish(M, L, vnoise):
    P = M.P
    # very soft large-scale tone drift (+-1 %) and smoothness grime (stock: smoothness carries the wear)
    # evaluated per texel: the decimated M.coarse() samples across UV island borders and left stepped bands
    n1 = vnoise(P, 2.5, seed=3, octaves=3)
    L.col *= (1 + 0.010 * n1)[:, None]
    g = vnoise(P, 0.9, seed=5, octaves=4)
    L.sm += 0.035 * g
    # grime: slightly less smooth low on the body and behind the gear / exhaust
    low = smoothstep(2.0, 1.2, P[:, 2])
    L.sm -= 0.03 * low
    # 0.4.0 per-skin dirt in the albedo (the n/m maps are shared, so only colour can differ between liveries)
    if LIVERY == 'lowlevel':        # field-worn: blotchy grime, heavier low on the body
        gd = np.clip(vnoise(P, 0.7, seed=31, octaves=4), 0, 1)
        L.col *= (1 - 0.07 * gd - 0.05 * low)[:, None]
    elif LIVERY == 'maritime':      # salt air: faint rust-brown staining in patches and low on the body
        gd = np.clip(vnoise(P, 0.6, seed=37, octaves=4), 0, 1)
        a = (0.10 * gd + 0.06 * low)[:, None]
        L.col = L.col * (1 - a) + np.array((0.40, 0.22, 0.12), np.float32) * a
    # sparse light scuffs (matte even grey, sparse light scuffs only)
    cell = 0.22
    q = P / cell
    i = np.floor(q).astype(np.int64)
    r = TF_hash(i, 11)
    keep = r < 0.035
    if keep.any():
        f = q - i
        cx = TF_hash(i, 12) * 0.6 + 0.2; cy = TF_hash(i, 13) * 0.6 + 0.2; cz = TF_hash(i, 14) * 0.6 + 0.2
        dd = np.sqrt((f[:, 0] - cx) ** 2 + (f[:, 1] - cy) ** 2 * 0.25 + (f[:, 2] - cz) ** 2) * cell
        sc = smoothstep(0.03, 0.006, dd) * keep
        L.col *= (1 + 0.035 * sc)[:, None]
        L.sm += 0.04 * sc
    L.sm = np.clip(L.sm, 0.2, 0.75)


def TF_hash(i, k):
    from tex_feat import hash01
    return hash01(i[:, 0], i[:, 1], i[:, 2] + k * 7919).astype(np.float32)


def damage(M, L, vnoise, H, e):
    """Damage set: light grey burnt / bare metal (stock idea) with an alpha that grows in soft patches, and a
    crumpled-metal normal that keeps the panel structure."""
    P = M.P
    n1 = vnoise(P, 1.5, seed=21, octaves=3)
    n2 = vnoise(P, 0.6, seed=22, octaves=2)
    burn = np.clip(0.5 + 0.9 * n1 + 0.3 * n2, 0, 1)
    metal = np.array([168, 168, 165], np.float32) / 255
    soot = np.array([58, 56, 54], np.float32) / 255
    heat = np.array([120, 112, 104], np.float32) / 255
    col = metal * (1 - burn[:, None]) + heat * burn[:, None]
    col = col * (1 - np.clip(burn - 0.55, 0, 1)[:, None] * 1.6) + soot * np.clip(burn - 0.55, 0, 1)[:, None] * 1.6
    col *= (1 + 0.02 * n2)[:, None]
    groove = np.clip(-H[0], 0, 1)
    col *= (1 - 0.25 * groove)[:, None]
    al = vnoise(P, 1.2, seed=23, octaves=4)
    alpha = np.clip(0.5 + 0.55 * al, 0, 1)
    db = np.concatenate([np.clip(col, 0, 1), alpha[:, None]], 1)
    # normal: dents (3D noise height field, metres) + the engraved structure, stronger
    _, hd = M.coarse(lambda Q: 0.006 * vnoise(Q, 0.35, seed=31, octaves=3) + 0.0015 * vnoise(Q, 0.08, seed=32, octaves=2), 2)
    gy, gx = np.gradient(hd)
    a0 = gx.ravel()[M.C] * M.ppm; a1 = -gy.ravel()[M.C] * M.ppm
    b0 = b1 = 0.0
    hT = (H[1] - H[2]) / (2 * e) * DEPTH_M * 1.6; hB = (H[3] - H[4]) / (2 * e) * DEPTH_M * 1.6
    n = np.stack([-(a0 + b0) - hT, -(a1 + b1) - hB, np.ones(len(P), np.float32)], 1)
    n /= np.linalg.norm(n, axis=1, keepdims=True)
    return db, n
