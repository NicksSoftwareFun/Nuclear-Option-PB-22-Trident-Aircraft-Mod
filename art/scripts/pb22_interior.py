# Executed inside build_pb22_detail.py (shares its namespace), just before FINALIZE: modelled machinery inside the
# weapon bay, the main gear wells and the nose wheel well. Everything is extra geometry
# on the hull part that owns the cavity (stock aircraft do the same: wells and bays are extra submeshes of the hull
# parts, always rendered, hidden by the closed doors). Materials: MECH (structure, actuators), DARK (pipes, recesses).
import math
from mathutils import Vector

BAY_CEIL = 2.80                       # weapon-bay roof (deepened from 2.40 so a 2 x 3 AGM-99 stack fits)
BAY_D0, BAY_D1 = BAYS[0][0] - BAYS[0][1] / 2, BAYS[1][0] + BAYS[1][1] / 2
BAY_X = 1.0
BAY_FLOOR = 1.33                      # door hinge line / belly skin at the bay edge


def frange(a, b, step):
    n = int(math.floor((b - a) / step + 1e-6))
    return [a + step * k for k in range(n + 1)]


def pipe_run(mb, pts, r, mat=DARK, N=8):
    tube(mb, [Vector(p) for p in pts], r, N=N, mat=mat)


def clamp_blocks(mb, x, z, d0, d1, step, mat=MECH):
    for dd in frange(d0 + 0.2, d1 - 0.2, step):
        rbox(mb, (x, Y(dd), z), (0.04, 0.035, 0.07), 0.006, mat)


# ---------------------------------------------------------------- weapon bay (fuselage, one cavity under both door pairs)
fb = PARTS['fuselage'].mb
L = BAY_D1 - BAY_D0
# roof frames every 0.6 m with a lightening-hole web, and two keel beams carrying the hardpoint rails
for dd in frange(BAY_D0 + 0.30, BAY_D1 - 0.30, 0.60):
    rbox(fb, (0, Y(dd), BAY_CEIL - 0.05), (2 * BAY_X - 0.04, 0.05, 0.10), 0.008, MECH)
for xk in (-0.80, 0.80):                # outboard of the AGM-99 x6 columns (x +-0.40, r 0.20, fins to 0.70)
    rbox(fb, (xk, Y((BAY_D0 + BAY_D1) / 2), BAY_CEIL - 0.07), (0.12, L - 0.10, 0.14), 0.01, MECH)
    clamp_blocks(fb, xk, BAY_CEIL - 0.17, BAY_D0, BAY_D1, 0.9)
# centre rail with sway-brace pads under the forward, combined and rear hardpoints
rbox(fb, (0, Y((BAY_D0 + BAY_D1) / 2), BAY_CEIL - 0.05), (0.10, L - 0.6, 0.08), 0.01, MECH)
for dc in (BAYS[0][0], (BAY_D0 + BAY_D1) / 2, BAYS[1][0]):
    for dx in (-0.12, 0.12):
        rbox(fb, (dx, Y(dc), BAY_CEIL - 0.13), (0.08, 0.30, 0.06), 0.008, MECH)
# side-wall frames (vertical ribs) and a stringer at mid height
for s_ in (1, -1):
    xw = s_ * (BAY_X - 0.02)
    for dd in frange(BAY_D0 + 0.30, BAY_D1 - 0.30, 0.60):
        rbox(fb, (xw, Y(dd), (BAY_FLOOR + BAY_CEIL) / 2 + 0.02), (0.04, 0.045, BAY_CEIL - BAY_FLOOR - 0.06), 0.006, MECH)
    rbox(fb, (s_ * (BAY_X - 0.035), Y((BAY_D0 + BAY_D1) / 2), 2.10), (0.03, L - 0.08, 0.05), 0.006, MECH)
    # hydraulic and electrical runs along the upper wall, with clamp blocks at every frame
    for k, zz in enumerate((2.52, 2.58, 2.64)):
        pipe_run(fb, [(s_ * (BAY_X - 0.06), Y(BAY_D0 + 0.08), zz), (s_ * (BAY_X - 0.06), Y(BAY_D1 - 0.08), zz)], 0.014 if k < 2 else 0.022)
    clamp_blocks(fb, s_ * (BAY_X - 0.06), 2.58, BAY_D0, BAY_D1, 0.6)
    # door actuators: a cylinder from the wall bracket down to the hinge line, two per door
    for dc, ln in BAYS:
        for dd in (dc - ln / 4, dc + ln / 4):
            top = Vector((s_ * (BAY_X - 0.10), Y(dd), 1.95)); bot = Vector((s_ * (BAY_X - 0.02), Y(dd + 0.25), BAY_FLOOR + 0.10))
            rbox(fb, (top.x, top.y, top.z + 0.06), (0.08, 0.10, 0.10), 0.008, MECH)
            cyl(fb, top, top.lerp(bot, 0.6), 0.035, N=10, mat=MECH)
            cyl(fb, top.lerp(bot, 0.55), bot, 0.018, N=8, mat=MECH)
# forward bulkhead plate (the boolean leaves the front of the cavity open into the hollow forward fuselage)
rbox(fb, (0, Y(BAY_D0 + 0.012), (BAY_FLOOR + BAY_CEIL) / 2), (2 * BAY_X, 0.02, BAY_CEIL - BAY_FLOOR + 0.04), 0.004, MECH)
# end bulkheads: stiffener ladders
for dd in (BAY_D0 + 0.03, BAY_D1 - 0.03):
    for xx in (-0.6, -0.2, 0.2, 0.6):
        rbox(fb, (xx, Y(dd), (BAY_FLOOR + BAY_CEIL) / 2 + 0.02), (0.05, 0.04, BAY_CEIL - BAY_FLOOR - 0.08), 0.006, MECH)

# ---------------------------------------------------------------- main gear wells (gearbay_L/R)
for side, s in (('R', 1), ('L', -1)):
    gm = PARTS[f'gearbay_{side}'].mb
    x0, x1 = 2.12, 4.50
    # 0.9.4: the well roof is the fairing's flat top (bay cavity to z 2.08), so the roof
    # detail hugs it; the stowed outboard wheels come up to z 2.055, the actuator to 2.077 at x 2.66
    zt = 2.08
    for dd in frange(BAY_DD[0] + 0.25, BAY_DD[1] - 0.25, 0.55):           # roof ribs across the well
        rbox(gm, (s * (x0 + x1) / 2, Y(dd), zt - 0.01), (x1 - x0 - 0.06, 0.04, 0.02), 0.004, MECH)
    for xx in (2.58,):                                                    # longitudinal roof beam (inboard; the stowed wheels sit outboard)
        rbox(gm, (s * xx, Y((BAY_DD[0] + BAY_DD[1]) / 2), zt - 0.02), (0.06, BAY_DD[1] - BAY_DD[0] - 0.08, 0.04), 0.006, MECH)
    # brake and hydraulic lines along the roof from the forward wall to the leg trunnion
    for k, dx in enumerate((0.0, 0.05, 0.10)):
        pipe_run(gm, [(s * (3.43 + dx), Y(BAY_DD[0] + 0.05), zt - 0.025), (s * (3.43 + dx), Y(20.4), zt - 0.025),
                      (s * (GEAR_T[0] + 0.25 + dx), Y(20.7), GEAR_T[2] + 0.30)], 0.013 if k < 2 else 0.02)
    # door uplocks near the hinge
    rbox(gm, (s * 4.45, Y(20.3), zt - 0.03), (0.06, 0.10, 0.06), 0.006, MECH)
    rbox(gm, (s * 4.45, Y(22.0), zt - 0.03), (0.06, 0.10, 0.06), 0.006, MECH)
    # wall stiffeners on the fore and aft walls
    for dd in (BAY_DD[0] + 0.02, BAY_DD[1] - 0.02):
        for xx in (2.5, 3.1, 3.7, 4.2):
            rbox(gm, (s * xx, Y(dd), (FAIR_Z + zt) / 2), (0.04, 0.03, zt - FAIR_Z - 0.12), 0.005, MECH)

# ---------------------------------------------------------------- nose wheel well (fuselage_F, d 10.15-12.58, x +-0.42)
nm_ = PARTS['fuselage_F'].mb
for dd in frange(10.4, 12.4, 0.40):
    rbox(nm_, (0, Y(dd), 2.30), (0.80, 0.035, 0.07), 0.006, MECH)
for s_ in (1, -1):
    for k, zz in enumerate((2.05, 2.12)):
        pipe_run(nm_, [(s_ * 0.38, Y(10.25), zz), (s_ * 0.38, Y(12.45), zz)], 0.012 if k == 0 else 0.018)
    clamp_blocks(nm_, s_ * 0.38, 2.09, 10.15, 12.58, 0.5)
rbox(nm_, (0, Y(12.2), 2.24), (0.14, 0.14, 0.12), 0.01, MECH)          # nose-gear uplock
cyl(nm_, (0, Y(12.2), 2.17), (0, Y(12.2) + 0.06, 2.12), 0.025, N=8, mat=DARK)

# (the engine faces moved to the real fan at the end of the full intake duct: pb22_structure.py)
