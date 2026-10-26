"""Faction insignia of the PB-22 liveries (stock style: every faction livery is its own texture with the markings
painted in, and the AircraftParameters livery entry names the faction).
PB22_FACTION = bdf | pala picks the set; unset or 'none' paints no insignia.
  tail       large roundel upright on both sides of the fin, on the fixed fin ahead of the rudder hinge,
             below the formation light strip
  wings      medium roundel on the top of the starboard wing and the bottom of the port wing, top of the
             roundel toward the nose (the roundel spans the slat, wing box, spoiler and flap like stock markings)
Matte Grey and Low-Level Camo get the full-colour roundels; Maritime Blue gets low-vis ones
(light grey over the dark blue top surfaces, dark grey under the light belly).
Images: ../../logos (fan redraws of the Boscali Defense Force and PALA roundels)."""
import os
import numpy as np
from PIL import Image
from tex_feat import Decal

FACTION = os.environ.get('PB22_FACTION', 'none')
LOGOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'logos')
FIN = ['rudder_L', 'rudder_L_visible']
WING_R = ['wing1_R', 'slat_R_visible', 'spoiler_R_visible', 'flap_R_visible']
WING_L = ['wing1_L', 'slat_L_visible', 'spoiler_L_visible', 'flap_L_visible']

# size (height of the tail roundel, width of the wing roundel, m) and position per faction
SET = {
    'bdf':  dict(img='bdf_roundel_color_2048.png', top='bdf_roundel_lowvis_grey_1024.png', low='bdf_roundel_lowvis_dark_1024.png',
                 tail_h=1.45, tail_d=29.44, tail_z=5.60, wing_w=1.70),
    'pala': dict(img='pala_roundel_color_2048.png', top='pala_roundel_lowvis_grey_1024.png', low='pala_roundel_lowvis_dark_1024.png',
                 tail_h=1.60, tail_d=29.44, tail_z=5.60, wing_w=1.15),
}
# 2026-10-25: centred between the panel lines, main structure only (no control surfaces)
#   tail: halfway between the fin's two spanwise major lines (fin chord 0.15 and 0.68) at the roundel's centre height, z 5.6
#   wings: halfway between the front and rear spar lines (wing chord 0.15 and 0.56) at span 8.1, the middle of a rib bay
WING_AX, WING_D = 8.10, 22.76        # rest pose, 20 deg sweep
WEAR = 0.30                          # darkening of a roundel's paint along the panel lines and rivets under it (faded by wear)


class WornDecal(Decal):
    """Decal painted over the panel lines: where the engraving (grooves, rivets) runs under the roundel the line shows
    through faded, so the paint reads as applied over the skin and worn in."""
    def paint(self, P, N, L, I):
        before = L.col[I].copy()
        super().paint(P, N, L, I)
        a = np.abs(L.col[I] - before).max(1) > 1e-4               # texels the roundel painted
        if not a.any(): return
        J = I[a]
        g = np.clip(-L.hneg[0, J] / 0.15, 0, 1)                     # engraving depth: minor lines reach about -0.16, major -1
        L.col[J] *= (1 - WEAR * g)[:, None]


def _worn(dc):
    dc.__class__ = WornDecal
    return dc


def _img(name):
    return Image.open(os.path.join(LOGOS, name)).convert('RGBA')


def marks(livery, ST):
    if FACTION not in SET: return []
    f = SET[FACTION]
    lowvis = livery == 'maritime'
    top = _img(f['top'] if lowvis else f['img'])
    bot = _img(f['low'] if lowvis else f['img'])
    op = 0.92 if lowvis else 1.0
    F = []
    for s in (1, -1):
        F.append(_worn(ST.place_side(top, f['tail_d'], f['tail_z'], s, f['tail_h'], FIN, xr=(0.0, 0.35), op=op)))
    F.append(_worn(ST.place_top(top, WING_D, WING_AX, 2.17, f['wing_w'], WING_R, op=op, tol=0.3)))
    F.append(_worn(ST.place_top(bot, WING_D, -WING_AX, 2.05, f['wing_w'], WING_L, op=op, down=True, tol=0.3)))
    return F
