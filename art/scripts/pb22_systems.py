# Executed inside build_pb22_detail.py after pb22_structure.py: the aircraft systems that fill the structure the way
# the stock aircraft do, colour-coded so a broken-open part reads at a glance: fuel cells (tan rubber), fuel lines
# (red-brown), hydraulics (yellow), wiring looms (off-white), oxygen (green), fire bottles (red), avionics (dark boxes),
# plus the engine internals (compressor, combustor, turbine, afterburner and their plumbing).
# Every piece is built in a scratch mesh first and only kept if it intersects nothing already in the model (skin,
# structure, ducts, other systems) and sits inside the skin, so nothing can poke out or clip; rejects are printed.
import math
from mathutils import Vector
from mathutils.bvhtree import BVHTree

SYS_LOG = {'kept': 0, 'rejected': []}


def _bvh_of(bm):
    bm.verts.ensure_lookup_table(); bm.faces.ensure_lookup_table(); bm.verts.index_update()
    return BVHTree.FromPolygons([v.co.copy() for v in bm.verts], [[v.index for v in f.verts] for f in bm.faces], epsilon=0.0)


FACE_INFO = []


def _world_tris(skin_only=False):
    vs, fs = [], []
    for p in PARTS.values():
        bm = p.mb.bm; bm.verts.ensure_lookup_table(); bm.verts.index_update()
        base = len(vs)
        vs.extend(v.co.copy() for v in bm.verts)
        for f in bm.faces:
            if skin_only and f.material_index not in (SKIN, GLASS): continue
            fs.append([base + v.index for v in f.verts])
            if not skin_only: FACE_INFO.append((p.name, f.material_index, f.calc_center_median().copy()))
    return BVHTree.FromPolygons(vs, fs, epsilon=0.0)


# every moving part is in its rest pose here (gear down, doors shut, wings at 20 deg), so the volumes that something
# swings into later (weapon bay, wheel wells, intake ducts, crew compartment, the glove slot the wing sweeps into) are
# kept clear by hand
def _keep_out(p):
    d = dd_of(p); ax = abs(p.x)
    if in_bay(p) or in_nosewell(p) or in_duct(p): return True
    if 5.0 <= d <= 10.05 and p.z > 2.0 and ax < 1.0: return True                  # crew compartment
    if BAY_DD[0] - 0.3 <= d <= BAY_DD[1] + 0.3 and 1.9 <= ax <= 4.6 and p.z < 2.29: return True   # main wheel wells
    if math.hypot(ax - PIVOT[0], d - PIVOT[1]) < 1.3 and abs(p.z - GLOVE_Z) < 0.4: return 'glove'
    return False


ALL_BVH = None
SKIN_BVH = None
KEPT = []


def fits(build, name, where, allow_glove=False):
    """Build into a scratch mesh; keep (build again into the part `where`) only if it is clear of everything."""
    global ALL_BVH, SKIN_BVH
    if ALL_BVH is None:
        ALL_BVH = _world_tris(); SKIN_BVH = _world_tris(True)
    tmp = MeshBuilder(); build(tmp)
    bm = tmp.bm
    if not bm.verts: tmp.bm.free(); return False
    why = None
    for v in bm.verts:
        k = _keep_out(v.co)
        if k is True or (k == 'glove' and where.startswith('wingroot')): why = f'keep-out at d{dd_of(v.co):.2f},x{v.co.x:.2f},z{v.co.z:.2f}'; break
    c = sum((v.co for v in bm.verts), Vector()) / len(bm.verts)
    if why is None:
        # skin above and below the centre (three origins, so a door seam on the centre line does not count as open air)
        os_ = [c, c + Vector((0.2, 0, 0)), c - Vector((0.2, 0, 0)), c + Vector((0, 0.2, 0)), c - Vector((0, 0.2, 0))]
        up = any(SKIN_BVH.ray_cast(o, Vector((0, 0, 1)))[0] is not None for o in os_)
        dn = any(ALL_BVH.ray_cast(o, Vector((0, 0, -1)))[0] is not None for o in os_)   # skin, or a well roof under the glove
        if not (up and dn): why = 'outside skin (%s)' % ('no skin above' if not up else 'no skin below')
    if why is None:
        b = _bvh_of(bm)
        ov = b.overlap(ALL_BVH)
        if ov:
            hit = {}
            for _, j in ov[:200]:
                n_, mi, cc = FACE_INFO[j]; hit.setdefault((n_, mi), cc)
            why = 'clips ' + ', '.join(f'{n_}/{MATS[mi].name[5:]}@d{dd_of(cc):.2f},x{cc.x:.2f},z{cc.z:.2f}' for (n_, mi), cc in list(hit.items())[:3])
        else:
            for k in KEPT:
                if b.overlap(k): why = 'clips system'; break
    if why:
        SYS_LOG['rejected'].append(f'{name}: {why}'); tmp.bm.free(); return False
    KEPT.append(_bvh_of(bm)); tmp.bm.free()
    build(PARTS[where].mb)
    SYS_LOG['kept'] += 1
    return True


def place(build, name, where, allow_glove=False, shrink=None):
    """fits(), and if it is refused, retries with the build shrunk step by step (shrink(k) -> build) before giving up."""
    if fits(build, name, where, allow_glove): return True
    if shrink:
        first = SYS_LOG['rejected'].pop()
        for k in range(1, 5):
            if fits(shrink(k), f'{name}~{k}', where, allow_glove): return True
            last = SYS_LOG['rejected'].pop()
        SYS_LOG['rejected'].append(first + ' | smallest: ' + last.split(': ', 1)[1])
    return False


def _closed_add(mb, fn):
    n0 = _fv(mb); fn(mb); _closed(mb, n0)


# ---------------------------------------------------------------- generic pieces
def bottle(mb, a, b, r, mat, neck=True):
    """Pressure bottle: capsule from a to b with a valve neck at b."""
    a, b = Vector(a), Vector(b); ax = (b - a).normalized(); L = (b - a).length
    pts = [a, a + ax * r * 0.35, a + ax * r, b - ax * r, b - ax * r * 0.35, b]
    rad = [0.0, r * 0.80, r, r, r * 0.80, r * 0.35]
    _closed_add(mb, lambda m: tube(m, pts, rad, N=14, mat=mat, caps=True))
    if neck:
        _closed_add(mb, lambda m: cyl(m, b, b + ax * 0.06, r * 0.22, N=8, mat=DARK))


def pipe(mb, pts, r, mat):
    _closed_add(mb, lambda m: tube(m, [Vector(p) for p in pts], r, N=6, mat=mat, caps=True))


def clamp_box(mb, c, size, mat=MECH):
    _closed_add(mb, lambda m: rbox(m, c, size, min(size) * 0.2, mat))


def actuator(mb, a, b, r=0.045):
    """Hydraulic actuator: barrel (mech) over the first 60 %, chrome-dark rod, end eyes, two yellow hoses on the barrel."""
    a, b = Vector(a), Vector(b); m_ = a.lerp(b, 0.6)
    _closed_add(mb, lambda m: cyl(m, a, m_, r, N=12, mat=MECH))
    _closed_add(mb, lambda m: cyl(m, m_, b, r * 0.45, N=8, mat=DARK))
    for p in (a, b):
        _closed_add(mb, lambda m, p=p: cyl(m, p - Vector((r * 0.9, 0, 0)), p + Vector((r * 0.9, 0, 0)), r * 0.7, N=8, mat=MECH))


def avionics_box(mb, c, size, face):
    """Line-replaceable unit: dark box, lighter front panel with two connectors (wire colour) and a handle."""
    cx, cy, cz = c; sx, sy, sz = size
    _closed_add(mb, lambda m: rbox(m, c, size, 0.012, INT))
    fy = cy + face * (sy / 2 + 0.006)
    _closed_add(mb, lambda m: rbox(m, (cx, fy, cz), (sx * 0.9, 0.012, sz * 0.9), 0.004, MECH))
    for dx in (-sx * 0.22, sx * 0.22):
        _closed_add(mb, lambda m, dx=dx: cyl(m, (cx + dx, fy, cz - sz * 0.15), (cx + dx, fy + face * 0.035, cz - sz * 0.15), min(sx, sz) * 0.12, N=8, mat=WIRE))
    _closed_add(mb, lambda m: rbox(m, (cx, fy + face * 0.02, cz + sz * 0.28), (sx * 0.5, 0.02, 0.018), 0.004, DARK))


def bladder(mb, rings):
    """Rubber fuel cell from section rings (soft-edged loft, end caps)."""
    _closed_add(mb, lambda m: loft(m, rings, True, True, FUELC, smooth=True))


def _arc(d, z_floor, off, n=14):
    """Upper fuselage section above z_floor, inset `off` from the skin, as n points right -> left."""
    ths = [math.radians(a) for a in range(-90, 271, 2)]
    pts = [BODY.point(d, th, -off) for th in ths]
    up = [(th, p) for th, p in zip(ths, pts) if p.z >= z_floor]
    t0, t1 = up[0][0], up[-1][0]
    return [BODY.point(d, t0 + (t1 - t0) * k / (n - 1), -off) for k in range(n)]


def upper_cell_ring(d, z_floor, off, x_low=None, z_step=None, notch=(0.40, 3.24)):
    """Fuel-cell section filling the upper fuselage: the skin arc above z_floor, closed by a flat floor; with x_low, a
    narrower keel drops to z_step between |x| < x_low (the space between the ducts above the bay roof). The arc is held
    down to notch[1] over |x| < notch[0], under the root of the dorsal spine that reaches into the deck."""
    arc = _arc(d, z_floor, off)
    if notch:
        arc = [Vector((p.x, p.y, min(p.z, notch[1]))) if abs(p.x) < notch[0] else p for p in arc]
    xr, xl = arc[0].x, arc[-1].x
    y = Y(d)
    floor = []
    if x_low is not None:
        floor = [Vector((-x_low, y, z_floor)), Vector((-x_low, y, z_step)), Vector((x_low, y, z_step)), Vector((x_low, y, z_floor))]
    return arc + [Vector((xl, y, z_floor))] + floor + [Vector((xr, y, z_floor))]


def duct_top(d0, d1):
    """Highest point of the intake duct box over d0..d1 (in_duct's own box), the floor for the cells above the ducts."""
    ds = [st[0] for st in DUCT]; top = 0.0
    for k in range(21):
        d = d0 + (d1 - d0) * k / 20
        if d < ds[0] or d > ds[-1]: continue
        i = max(j for j in range(len(ds) - 1) if ds[j] <= d) if d < ds[-1] else len(ds) - 2
        t = (d - ds[i]) / (ds[i + 1] - ds[i])
        zc = DUCT[i][2] + (DUCT[i + 1][2] - DUCT[i][2]) * t; H = DUCT[i][4] + (DUCT[i + 1][4] - DUCT[i][4]) * t
        top = max(top, zc + H + 0.04)
    return top


# ================================================================ FUSELAGE fuel cells, crossfeed, looms, hydraulics
fus = 'fuselage'
# four cells in two groups (either side of the wing carry-through), a service gap with the transfer pump and crossfeed
# pipe between the two cells of each group; cells sit 0.17 m in from the skin so the looms run in the band outside them
CELLS = ((15.75, 17.35), (17.75, 19.42), (22.80, 23.85), (24.25, 25.30))
for d0, d1 in CELLS:
    zf = max(duct_top(d0, d1) + 0.03, 3.10)
    def cell(m, d0=d0, d1=d1, zf=zf, f=0.0):
        ds = [d0, d0 + 0.08, (d0 + d1) / 2, d1 - 0.08, d1]
        rings = []
        for k, d in enumerate(ds):
            ins = 0.21 if k in (0, 4) else 0.17
            rings.append(upper_cell_ring(d, zf + f, ins + f, x_low=0.96 - f, z_step=2.94 + f))
        bladder(m, rings)
    place(cell, f'fuel cell d{d0}', fus, shrink=lambda k, d0=d0, d1=d1, zf=zf: (lambda m: cell(m, d0, d1, zf, 0.03 * k)))
for dg in (17.55, 24.05):
    place(lambda m, dg=dg: _closed_add(m, lambda mm: cyl(mm, (0, Y(dg), 3.02), (0, Y(dg), 3.22), 0.09, N=14, mat=MECH)), f'transfer pump d{dg}', fus)
    place(lambda m, dg=dg: pipe(m, [(-0.95, Y(dg), 3.12), (-0.12, Y(dg), 3.12)], 0.035, FUELL), f'crossfeed L d{dg}', fus)
    place(lambda m, dg=dg: pipe(m, [(0.12, Y(dg), 3.12), (0.95, Y(dg), 3.12)], 0.035, FUELL), f'crossfeed R d{dg}', fus)
    for s_ in (1, -1):
        place(lambda m, dg=dg, s_=s_: pipe(m, [(s_ * 0.45, Y(dg + 0.17), 3.30), (s_ * 0.45, Y(dg), 3.30), (s_ * 0.45, Y(dg - 0.17), 3.30)], 0.03, FUELL),
              f'cell link {s_} d{dg}', fus)
# wiring looms in the band between the cells and the frames
for s_ in (1, -1):
    for th_deg in (50, 62):
        th = math.radians(90 - s_ * (90 - th_deg))
        for a, b in ((15.70, 19.45), (22.75, 25.35)):
            pts = [BODY.point(d, th, -0.135) for d in (a, (a + b) / 2, b)]
            place(lambda m, pts=pts: pipe(m, pts, 0.022, WIRE), f'loom {s_} {th_deg} d{a}', fus)
# two hydraulic systems along the outside of each bay sill, below the duct floor
for s_ in (1, -1):
    for k, dx in enumerate((1.19, 1.25)):
        run = [(s_ * dx, Y(15.1), 1.42), (s_ * dx, Y(24.4), 1.42)]
        place(lambda m, run=run: pipe(m, run, 0.016, HYD), f'hyd sill {s_}{k}', fus,
              shrink=lambda k_, run=run: (lambda m: pipe(m, [(p[0], p[1], p[2] + 0.02 * k_) for p in run], 0.014, HYD)))

# ================================================================ FORWARD FUSELAGE: fuel cell over the avionics racks, O2 bottles
fF = 'fuselage_F'
def fcell(m, f=0.0):
    rings = [upper_cell_ring(d, 3.28 + f, (0.14 if d in (10.32, 12.40) else 0.10) + f) for d in (10.32, 10.40, 11.36, 12.32, 12.40)]
    bladder(m, rings)
place(fcell, 'fuel cell fwd', fF, shrink=lambda k: (lambda m: fcell(m, 0.03 * k)))
for s in (1, -1):
    for k, dd in enumerate((10.45, 11.05)):
        place(lambda m, s=s, dd=dd: bottle(m, (s * 0.66, Y(dd), 1.62), (s * 0.66, Y(dd + 0.48), 1.62), 0.10, OXY), f'O2 bottle {s}{k}', fF,
              shrink=lambda k_, s=s, dd=dd: (lambda m: bottle(m, (s * (0.66 - 0.04 * k_), Y(dd), 1.62 + 0.03 * k_), (s * (0.66 - 0.04 * k_), Y(dd + 0.45), 1.62 + 0.03 * k_), 0.10 - 0.012 * k_, OXY)))
    place(lambda m, s=s: pipe(m, [(s * 0.66, Y(11.60), 1.62), (s * 0.70, Y(11.9), 1.80), (s * 0.70, Y(12.45), 1.80)], 0.012, OXY), f'O2 line {s}', fF)

# ================================================================ COCKPIT / CREW SECTION: avionics bays under the floor and ahead of the crew
for s in (1, -1):
    for k, dd in enumerate((5.4, 6.1, 6.8, 7.5, 8.2, 8.9, 9.55)):
        where = 'cockpit' if dd < 7.0 else 'fuselage_FF'
        place(lambda m, s=s, dd=dd: avionics_box(m, (s * 0.30, Y(dd), 1.78), (0.40, 0.52, 0.34), -s if False else 1),
              f'underfloor LRU {s}{k}', where,
              shrink=lambda k_, s=s, dd=dd: (lambda m: avionics_box(m, (s * 0.30, Y(dd), 1.80 + 0.01 * k_), (0.40 - 0.05 * k_, 0.50, 0.30 - 0.04 * k_), 1)))
# forward equipment bay behind the radar bulkhead: radar transmitter / processor stack and its waveguide
for k, (dd, zz, sz) in enumerate(((3.62, 2.05, (0.55, 0.40, 0.34)), (3.62, 2.45, (0.50, 0.40, 0.32)), (4.15, 2.10, (0.60, 0.42, 0.40)), (4.15, 2.55, (0.44, 0.42, 0.30)))):
    place(lambda m, dd=dd, zz=zz, sz=sz: avionics_box(m, (0, Y(dd), zz), sz, 1), f'radar LRU {k}', 'cockpit',
          shrink=lambda k_, dd=dd, zz=zz, sz=sz: (lambda m: avionics_box(m, (0, Y(dd), zz), (sz[0] - 0.06 * k_, sz[1], sz[2] - 0.04 * k_), 1)))
place(lambda m: pipe(m, [(0.38, Y(3.40), 2.40), (0.38, Y(3.90), 2.45), (0.36, Y(4.6), 2.40)], 0.03, MECH), 'waveguide', 'cockpit')

# ================================================================ NOSE: radar electronics behind the array
nm_ = 'nose'
for k, dx in enumerate((-0.40, 0.40)):
    place(lambda m, dx=dx: avionics_box(m, (dx, Y(3.05), 2.33), (0.16, 0.20, 0.24), 1), f'radar rx {k}', nm_,
          shrink=lambda k_, dx=dx: (lambda m: avionics_box(m, (dx * (1 - 0.06 * k_), Y(3.05), 2.33), (0.16 - 0.02 * k_, 0.20, 0.24 - 0.03 * k_), 1)))
place(lambda m: pipe(m, [(0.0, Y(2.85), 2.62), (0.12, Y(3.05), 2.70), (0.12, Y(3.25), 2.70)], 0.022, WIRE), 'radar cable', nm_)

# ================================================================ GEAR PODS: fuel cell behind the wheel well, hydraulics to the gear
for side, s in (('R', 1), ('L', -1)):
    gb = f'gearbay_{side}'
    def pcell(m, s=s, f=0.0):
        rings = []
        for d in (23.05, 23.15, 23.85, 24.55, 24.65):
            e = 0.06 if d in (23.05, 24.65) else 0.0
            x0, x1, z0, z1 = 2.40 + e + f, 3.45 - e - f, 1.55 + e + f, 1.92 - e - f
            rings.append([Vector((s * x, Y(d), z)) for x, z in ((x1, z0), (x1, z1), (x0, z1), (x0, z0))])
        bladder(m, rings)
    place(pcell, f'pod fuel {side}', gb, shrink=lambda k, s=s: (lambda m: pcell(m, s, 0.04 * k)))
    for k, dx in enumerate((0.0, 0.06)):
        run = [(s * (2.70 + dx), Y(25.4), 1.99), (s * (2.70 + dx), Y(22.95), 1.99)]
        place(lambda m, run=run: pipe(m, run, 0.016, HYD), f'pod hyd {side}{k}', gb,
              shrink=lambda k_, run=run: (lambda m: pipe(m, [(p[0], p[1], p[2] - 0.03 * k_) for p in run], 0.015, HYD)))
    # gear accumulator (yellow sphere-ended bottle)
    place(lambda m, s=s: bottle(m, (s * 3.40, Y(23.2), 2.05), (s * 3.40, Y(23.65), 2.05), 0.07, HYD), f'pod accumulator {side}', gb,
          shrink=lambda k, s=s: (lambda m: bottle(m, (s * 3.40, Y(23.2), 2.05 - 0.02 * k), (s * 3.40, Y(23.6), 2.05 - 0.02 * k), 0.07 - 0.01 * k, HYD)))

# ================================================================ WINGS: fuel bladders between the spars, actuators, lines, looms
RIBS1 = [4.75 + 0.6 * k for k in range(11)] + [W_SPLIT - 0.05]
RIBS2 = [W_SPLIT + 0.05, 11.35, 11.95, 12.55, W_TIP - 0.06]
for side, s in (('R', 1), ('L', -1)):
    for wname, ribs in ((f'wing1_{side}', RIBS1), (f'wing2_{side}', RIBS2)):
        for a, b in zip(ribs, ribs[1:]):
            if a < 5.3: continue                       # pivot lug and root fitting
            def wcell(m, a=a, b=b, f=0.0):
                cs = [0.19 + f + (0.58 - 2 * f - 0.19) * j / 7 for j in range(8)]
                rings = []
                for x in (a + 0.04, a + 0.07, b - 0.07, b - 0.04):
                    ins = 0.034 if x in (a + 0.04, b - 0.04) else 0.022
                    top = [chord_pt(s, x, c, 1) - Vector((0, 0, ins + f * 0.3)) for c in cs]
                    bot = [chord_pt(s, x, c, -1) + Vector((0, 0, ins + f * 0.3)) for c in reversed(cs)]
                    rings.append(top + bot)
                bladder(m, rings)
            place(wcell, f'{wname} cell {a:.2f}', wname, shrink=lambda k, a=a, b=b: (lambda m: wcell(m, a, b, 0.02 * k)))
    # behind the rear spar (c 0.62 .. 0.72): a hydraulic pair at mid-depth, flap actuators below it, spoiler actuators above;
    # a wiring loom just behind the front spar
    def mid(x, c, dz=0.0): return (chord_pt(s, x, c, 1) + chord_pt(s, x, c, -1)) / 2 + Vector((0, 0, dz))
    for wname, x0, x1 in ((f'wing1_{side}', 5.5, W_SPLIT - 0.12), (f'wing2_{side}', W_SPLIT + 0.12, 12.9)):
        for k, dz in enumerate((0.014, -0.014)):
            pts = [mid(x, 0.635, dz) for x in (x0, (x0 + x1) / 2, x1)]
            place(lambda m, pts=pts: pipe(m, pts, 0.010, HYD), f'{wname} hyd {k}', wname)
        pts = [mid(x, 0.135) for x in (x0, (x0 + x1) / 2, x1)]
        place(lambda m, pts=pts: pipe(m, pts, 0.012, WIRE), f'{wname} loom', wname,
              shrink=lambda k, pts=pts: (lambda m: pipe(m, pts, 0.012 - 0.002 * k, WIRE)))
    w1 = f'wing1_{side}'
    for xa in (7.0, 9.2):
        a_ = chord_pt(s, xa, 0.655, -1) + Vector((0, 0, 0.035)); b_ = chord_pt(s, xa, 0.71, -1) + Vector((0, 0, 0.035))
        place(lambda m, a_=a_, b_=b_: actuator(m, a_, b_, 0.018), f'{w1} flap act {xa}', w1,
              shrink=lambda k, a_=a_, b_=b_: (lambda m: actuator(m, a_ + Vector((0, 0, 0.004 * k)), b_ + Vector((0, 0, 0.004 * k)), 0.018 - 0.002 * k)))
    for xa in (7.4, 9.9):
        a_ = chord_pt(s, xa, 0.655, 1) - Vector((0, 0, 0.035)); b_ = chord_pt(s, xa, 0.71, 1) - Vector((0, 0, 0.035))
        place(lambda m, a_=a_, b_=b_: actuator(m, a_, b_, 0.016), f'{w1} spoiler act {xa}', w1,
              shrink=lambda k, a_=a_, b_=b_: (lambda m: actuator(m, a_ - Vector((0, 0, 0.004 * k)), b_ - Vector((0, 0, 0.004 * k)), 0.016 - 0.002 * k)))
    pts = [mid(x, 0.30) for x in (W_TIP + 0.03, 13.45)]
    place(lambda m, pts=pts: pipe(m, pts, 0.010, WIRE), f'wingtip_{side} cable', f'wingtip_{side}')

# ================================================================ GLOVE: hydraulic accumulators and lines between the glove ribs
for side, s in (('R', 1), ('L', -1)):
    gm_ = f'wingroot_{side}'
    for k, (xb, d0) in enumerate(((2.50, 20.0), (3.10, 20.2))):
        place(lambda m, xb=xb, d0=d0: bottle(m, (s * xb, Y(d0), 2.42), (s * xb, Y(d0 + 0.6), 2.42), 0.07, HYD), f'glove accumulator {side}{k}', gm_,
              shrink=lambda k_, xb=xb, d0=d0: (lambda m: bottle(m, (s * xb, Y(d0), 2.42), (s * xb, Y(d0 + 0.5), 2.42), 0.07 - 0.01 * k_, HYD)))
        for j, dx in enumerate((-0.12, 0.12)):
            run = [(s * (xb + dx), Y(d0 + 0.7), 2.40), (s * (xb + dx), Y(d0 + 1.6), 2.40)]
            place(lambda m, run=run: pipe(m, run, 0.012, HYD), f'glove line {side}{k}{j}', gm_)

# ================================================================ REAR FUSELAGE: keel, fire bottles, hydraulic bay between the engines
fR_ = 'fuselage_R'
place(lambda m: _closed_add(m, lambda mm: rbox(mm, (0, Y(28.3), 1.62), (0.16, 5.4, 0.10), 0.01, MECH)), 'keel beam', fR_,
      shrink=lambda k: (lambda m: _closed_add(m, lambda mm: rbox(mm, (0, Y(28.3), 1.62 + 0.04 * k), (0.12, 5.0, 0.08), 0.01, MECH))))
for k, dd in enumerate((26.2, 26.9)):
    place(lambda m, dd=dd: bottle(m, (0, Y(dd), 2.05), (0, Y(dd + 0.5), 2.05), 0.09, RED), f'fire bottle {k}', fR_,
          shrink=lambda k_, dd=dd: (lambda m: bottle(m, (0, Y(dd), 2.05), (0, Y(dd + 0.45), 2.05), 0.09 - 0.015 * k_, RED)))
place(lambda m: bottle(m, (0, Y(28.0), 2.05), (0, Y(28.8), 2.05), 0.10, HYD), 'hyd reservoir', fR_,
      shrink=lambda k: (lambda m: bottle(m, (0, Y(28.0), 2.05), (0, Y(28.7), 2.05), 0.10 - 0.015 * k, HYD)))
for s in (1, -1):
    run = [(s * 0.07, Y(26.3), 2.35), (s * 0.08, Y(28.0), 2.40), (s * 0.08, Y(29.6), 2.30)]
    place(lambda m, run=run: pipe(m, run, 0.012, RED), f'extinguisher line {s}', fR_)
    for k, dz in enumerate((0.0, 0.05)):
        run = [(s * 0.12, Y(25.7), 1.76 + dz), (s * 0.12, Y(29.4), 1.76 + dz), (s * 0.40, Y(29.9), 1.70 + dz)]
        place(lambda m, run=run: pipe(m, run, 0.013, HYD), f'elevator hyd {s}{k}', fR_,
              shrink=lambda k_, run=run: (lambda m: pipe(m, [(p[0], p[1], p[2] + 0.04 * k_) for p in run], 0.012, HYD)))

# ================================================================ TAIL: rudder actuators and lines up the fin
tm_ = 'tail'
for k, z in enumerate((5.0, 6.1)):
    le, te = fin_le(z), fin_te(z)
    ch = te - le
    a_ = Vector((0, Y(le + ch * 0.50), z)); b_ = Vector((0, Y(le + ch * 0.63), z))
    place(lambda m, a_=a_, b_=b_: actuator(m, a_, b_, 0.022), f'rudder act {k}', tm_,
          shrink=lambda k_, a_=a_, b_=b_: (lambda m: actuator(m, a_, b_, 0.022 - 0.004 * k_)))


# ================================================================ ENGINES: compressor, combustor, turbine and afterburner detail
for side, s, num in (('L', -1, 1), ('R', 1, 3)):
    xc, zc = s * 0.74, 2.40
    eb = f'engine_body_{side}'
    ring = lambda d, r, N=32: [Vector((xc + r * math.cos(2 * math.pi * k / N), Y(d), zc + r * math.sin(2 * math.pi * k / N))) for k in range(N)]
    bl = [(xc + s * 0.30, Y(28.0), zc + 0.40), (xc + s * 0.10, Y(28.4), zc + 0.50), (xc - s * 0.18, Y(29.0), zc + 0.47)]
    place(lambda m, bl=bl: pipe(m, bl, 0.035, MECH), f'{eb} bleed duct', eb,
          shrink=lambda k, bl=bl: (lambda m: pipe(m, [(p[0], p[1], p[2] - 0.03 * k) for p in bl], 0.035 - 0.005 * k, MECH)))
    place(lambda m: bottle(m, (xc + s * 0.30, Y(27.3), zc - 0.40), (xc + s * 0.30, Y(27.85), zc - 0.40), 0.09, MECH), f'{eb} oil tank', eb,
          shrink=lambda k: (lambda m: bottle(m, (xc + s * 0.28, Y(27.3), zc - 0.40 + 0.02 * k), (xc + s * 0.28, Y(27.8), zc - 0.40 + 0.02 * k), 0.09 - 0.015 * k, MECH)))
    place(lambda m: avionics_box(m, (xc + s * 0.60, Y(29.2), zc + 0.05), (0.08, 0.14, 0.10), 1), f'{eb} igniter', eb,
          shrink=lambda k: (lambda m: avionics_box(m, (xc + s * (0.60 - 0.01 * k), Y(29.2), zc + 0.05), (0.07, 0.12, 0.09), 1)))

print('systems kept', SYS_LOG['kept'], 'rejected', len(SYS_LOG['rejected']))
for r in SYS_LOG['rejected']: print('  reject', r)
