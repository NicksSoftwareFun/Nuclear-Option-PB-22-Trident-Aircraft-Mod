# Executed inside build_pb22_detail.py (shares its namespace), after pb22_interior.py and before FINALIZE: the internal
# structure that shows when a part breaks away (stock aircraft carry the same inside every breakable part): fuselage
# frames and longerons, the full intake ducts from the lips to the engine faces, the engines with their fans, DECM
# battery racks behind the crew, the wing-box carry-through, wing and fin spars and ribs, the wing pivots, the nose
# radar and the EW boxes in the tail cone. Materials: MECH (structure, engines), INT (duct lining, battery modules),
# DARK (pipes, cables, flanges).
import math
from mathutils import Vector
from pb22_shapes import thetas, catmull


def _fv(mb):
    mb.bm.faces.ensure_lookup_table()
    return len(mb.bm.faces)


def _closed(mb, n0):
    """Turn the faces added since n0 (one closed piece) outward: reverse them if the signed volume is negative."""
    mb.bm.faces.ensure_lookup_table()
    fs = mb.bm.faces[n0:]
    vol = 0.0
    for f in fs:
        v = [l.vert.co for l in f.loops]
        for k in range(1, len(v) - 1): vol += v[0].dot(v[k].cross(v[k + 1]))
    if vol < 0: bmesh.ops.reverse_faces(mb.bm, faces=list(fs), flip_multires=False)


def _facing(mb, n0, inward_to):
    """Make the faces added since n0 face toward (inward=True) the axis point inward_to(face centre)."""
    mb.bm.faces.ensure_lookup_table()
    fs = mb.bm.faces[n0:]
    score = sum((inward_to(f.calc_center_median()) - f.calc_center_median()).dot(f.normal) for f in fs if f.calc_area() > 1e-8)
    if score < 0: bmesh.ops.reverse_faces(mb.bm, faces=list(fs), flip_multires=False)


def dd_of(p): return 17.0 - p.y


def box(mb, c, size, mat=MECH):
    """Plain six-sided box (12 triangles) for small repeated parts."""
    cx, cy, cz = c; hx, hy, hz = size[0] / 2, size[1] / 2, size[2] / 2
    rings = [[Vector((cx + x, cy + y, cz + z)) for x, z in ((hx, -hz), (hx, hz), (-hx, hz), (-hx, -hz))] for y in (-hy, hy)]
    n0 = _fv(mb); loft(mb, rings, True, True, mat, smooth=False); _closed(mb, n0)


# ================================================================ intake ducts: open all the way from the lips to the fans
# the duct keeps its inner wall outboard of the rear weapon bay (x 1.07) until the bay ends at d 24.55, then turns in
# the first stations ease out of the 1.14 m tall intake mouth (it used to drop to 0.90 in one step, which read as a plate)
DUCT = [(14.6, 1.56, 2.45, 0.43, 0.99, 0.24), (15.5, 1.55, 2.38, 0.425, 0.84, 0.26), (16.5, 1.54, 2.30, 0.42, 0.72, 0.28), (19.0, 1.52, 2.25, 0.42, 0.62, 0.34),
        (22.0, 1.50, 2.25, 0.42, 0.58, 0.38), (24.3, 1.50, 2.30, 0.42, 0.54, 0.40), (24.7, 1.49, 2.31, 0.42, 0.53, 0.42), (25.4, 1.06, 2.38, 0.50, 0.52, 0.48),
        (26.3, 0.74, 2.40, 0.52, 0.52, 0.52)]
FAN_D, FAN_R = 26.32, 0.50
TH32 = thetas(32)
TH64 = thetas(64)


def duct_ring(d, s, off=0.0, N=32):
    ds = [st[0] for st in DUCT]
    i = max(min(next((k for k in range(len(ds) - 1) if d <= ds[k + 1] + 1e-9), len(ds) - 2), len(ds) - 2), 0)
    t = min(max((d - ds[i]) / (ds[i + 1] - ds[i]), 0.0), 1.0)
    par = []
    for j in range(1, 6):
        arr = [st[j] for st in DUCT]
        par.append(catmull(arr[max(i - 1, 0)], arr[i], arr[i + 1], arr[min(i + 2, len(arr) - 1)], t))
    xc, zc, W, H, r = par
    f = prof_rr(W, H, min(r, W - 1e-3, H - 1e-3))
    return [Vector((s * xc + (f(th) + off) * math.cos(th), Y(d), zc + (f(th) + off) * math.sin(th))) for th in ((TH64 if N == 64 else TH32) if off == 0 else TH32)]


# ================================================================ fuselage frames and longerons
def in_bay(p):
    return 13.0 <= dd_of(p) <= 24.6 and abs(p.x) < 1.07 and p.z < 2.90


def in_nosewell(p):
    return 10.1 <= dd_of(p) <= 12.62 and abs(p.x) < 0.48 and p.z < 2.42


def frame(name, d, depth=0.07, width=0.045, step=3, off=0.012, mask=None, mat=MECH):
    """Ring frame hugging the skin (BODY section) at station d; segments inside `mask` are left out."""
    mb = PARTS[name].mb
    po, pi = BODY.ring(d, -off), BODY.ring(d, -(off + depth))
    idx = list(range(0, len(po), step))
    keep = [not (mask and (mask(po[k]) or mask(pi[k]))) for k in idx]
    w = Vector((0, width / 2, 0))
    sec = lambda k: [po[k] + w, po[k] - w, pi[k] - w, pi[k] + w]
    if all(keep):
        n0 = _fv(mb)
        loft(mb, [sec(k) for k in idx] + [sec(idx[0])], False, False, mat, smooth=False)
        _closed(mb, n0)
        return
    n = len(idx)
    start = next(i for i in range(n) if not keep[i])
    run = []
    for j in range(1, n + 1):
        i = (start + j) % n
        if keep[i]: run.append(idx[i])
        if (not keep[i] or j == n) and len(run) >= 2:
            n0 = _fv(mb); loft(mb, [sec(k) for k in run], True, True, mat, smooth=False); _closed(mb, n0)
        if not keep[i]: run = []


def longeron(name, d0, d1, th, size=0.06, off=0.045, mask=None, step=0.45):
    mb = PARTS[name].mb
    n = max(int(math.ceil((d1 - d0) / step)), 1)
    pts = [BODY.point(d0 + (d1 - d0) * k / n, th, -off) for k in range(n + 1)]
    # over the nacelles the outer skin is the flat intake box top (z 3.64), inside the round body line: keep the
    # longeron under it, or it pokes through the skin along the shoulders
    pts = [Vector((p.x, p.y, min(p.z, 3.64 - 0.06 - size * 0.7))) if 14.6 <= Y(0) - p.y <= 26.3 else p for p in pts]
    run = []
    for p in pts + [None]:
        if p is not None and not (mask and mask(p)): run.append(p); continue
        if len(run) >= 2:
            n0 = _fv(mb); tube(mb, run, size * 0.7, N=4, mat=MECH); _closed(mb, n0)
        run = []


# the centre fuselage skin widens into the nacelles between d 12.6 and 14.6 and so crossed the intake mouths: cut it
# out along each duct (just outside the duct lining, inside the intake shell) so the duct is open from the lip back
def _duct_cutter(s):
    xo = s * 1.56; inn = intake_inner(xo)
    def push(r, c, off=0.012):
        return [Vector((c.x + (v.x - c.x) * (1 + off / max(math.hypot(v.x - c.x, v.z - c.z), 1e-6)), v.y,
                        c.z + (v.z - c.z) * (1 + off / max(math.hypot(v.x - c.x, v.z - c.z), 1e-6)))) for v in r]
    c0 = Vector((xo, 0, 2.465)); c1 = Vector((xo, 0, 2.45))
    rings = [push(inn.ring(12.5)[::2], c0), push(inn.ring(13.4, dfun=lambda dd, z: inner_d(13.4, z))[::2], c0)]
    r14 = duct_ring(14.58, s); rings.append(push(r14, c1))
    me = bpy.data.meshes.new('cut_duct'); o = bpy.data.objects.new('cut_duct', me); C_TMP.objects.link(o)
    bm = bmesh.new()
    vs = [[bm.verts.new(v) for v in r] for r in rings]
    n = len(vs[0])
    for a, b in zip(vs, vs[1:]):
        for k in range(n): bm.faces.new((a[k], a[(k + 1) % n], b[(k + 1) % n], b[k]))
    bm.faces.new(vs[0][::-1]); bm.faces.new(vs[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:]); bm.to_mesh(me); bm.free()
    me.materials.append(MATS[INT]); return o
apply_cuts(PARTS['fuselage'], [_duct_cutter(1), _duct_cutter(-1)])
# the boolean keeps the cutter's back cap as a wall across the duct (the nacelle behind it is closed): drop it
_fb = PARTS['fuselage'].mb.bm
bmesh.ops.delete(_fb, geom=[f for f in _fb.faces if abs(dd_of(f.calc_center_median()) - 14.58) < 0.01 and abs(f.normal.y) > 0.9
                            and abs(abs(f.calc_center_median().x) - 1.56) < 0.5], context='FACES')


def in_duct(p):
    d = dd_of(p); ax = abs(p.x)
    if 12.4 <= d <= 14.6: return abs(ax - 1.56) < 0.52 and abs(p.z - 2.465) < 1.19
    if 14.6 < d <= 26.3:
        ds = [st[0] for st in DUCT]; k = max(i for i in range(len(ds) - 1) if ds[i] <= d); t = (d - ds[k]) / (ds[k + 1] - ds[k])
        xc, zc, W, H = [DUCT[k][j] + (DUCT[k + 1][j] - DUCT[k][j]) * t for j in (1, 2, 3, 4)]
        return abs(ax - xc) < W + 0.04 and abs(p.z - zc) < H + 0.04
    return False


FR_MASK = lambda p: in_bay(p) or in_nosewell(p) or in_duct(p)
for d in (10.18, 12.52):
    frame('fuselage_F', d, depth=0.14, width=0.08, mask=FR_MASK)            # heavy frames at the break lines
for d in (10.95, 11.75):
    frame('fuselage_F', d, mask=FR_MASK)
for d in (12.68, 25.42):
    frame('fuselage', d, depth=0.14, width=0.08, mask=FR_MASK)
for k in range(13):
    frame('fuselage', 13.5 + 0.9 * k, mask=FR_MASK)
frame('fuselage_R', 25.58, depth=0.14, width=0.08)
for d in (26.4, 27.3, 28.2, 29.1, 30.0, 30.8):
    frame('fuselage_R', d, depth=0.06)
for th in (math.radians(35), math.radians(145), math.radians(215), math.radians(325)):
    longeron('fuselage_F', 10.15, 12.58, th, mask=FR_MASK)
    longeron('fuselage', 12.62, 25.48, th, mask=FR_MASK)
    longeron('fuselage_R', 25.52, 30.9, th)
# bay sills: heavy longitudinal beams along both edges of the weapon bay opening
fbm = PARTS['fuselage'].mb
for s in (1, -1):
    rbox(fbm, (s * 1.10, Y(18.8), 1.44), (0.10, 11.5, 0.16), 0.012, MECH)


def duct_axis(s):
    def ax(c):
        d = min(max(dd_of(c), DUCT[0][0]), DUCT[-1][0])
        ds = [st[0] for st in DUCT]; i = max(k for k in range(len(ds) - 1) if ds[k] <= d) if d < ds[-1] else len(ds) - 2
        t = (d - ds[i]) / (ds[i + 1] - ds[i])
        return Vector((s * (DUCT[i][1] + (DUCT[i + 1][1] - DUCT[i][1]) * t), c.y, DUCT[i][2] + (DUCT[i + 1][2] - DUCT[i][2]) * t))
    return ax



for side, s in (('R', 1), ('L', -1)):
    xo = s * 1.56
    INN = intake_inner(xo)
    r0 = INN.ring(13.4, dfun=lambda dd, z: inner_d(13.4, z))
    ax = lambda c, s=s: Vector((s * 1.56, c.y, 2.45))
    im = PARTS[f'intake_{side}'].mb
    n0 = _fv(im); loft(im, [r0, duct_ring(14.6, s, N=64)], False, False, INT); _facing(im, n0, ax)
    # and its back face too, so the corners of the lip-to-duct transition never show daylight
    loft(im, [duct_ring(14.6, s, N=64), r0], False, False, INT)
    for name, d0, d1 in (('fuselage', 14.6, REAR_SPLIT), ('fuselage_R', REAR_SPLIT, FAN_D - 0.02)):
        mb = PARTS[name].mb
        n = max(int(math.ceil((d1 - d0) / (0.3 if name == 'fuselage_R' else 0.6))), 1)     # finer where the duct turns in to the fan
        dl = [d0 + (d1 - d0) * k / n for k in range(n + 1)]
        n0 = _fv(mb); loft(mb, [duct_ring(d, s, N=64) for d in dl], False, False, INT); _facing(mb, n0, duct_axis(s))
        # and the back face: where the duct bends in to the fan the axis guess can flip faces, and a culled face shows daylight
        loft(mb, [duct_ring(d, s, N=64) for d in dl[::-1]], False, False, INT)
        if name == 'fuselage_R':
            # close the rounded-square duct end down to the round fan case, so no corner shows into the engine bay
            de = d1; cr = [Vector((s * 0.74 + 0.51 * math.cos(2 * math.pi * k / 64), Y(de), 2.40 + 0.51 * math.sin(2 * math.pi * k / 64))) for k in range(64)]
            dr = duct_ring(de, s, N=64)
            k0 = min(range(64), key=lambda k: (cr[k] - dr[0]).length); cr = cr[k0:] + cr[:k0]
            if (cr[1] - dr[1]).length > (cr[-1] - dr[1]).length: cr = [cr[0]] + cr[1:][::-1]
            loft(mb, [dr, cr], False, False, DARK, simplify=False); loft(mb, [cr, dr], False, False, DARK, simplify=False)
            # and a dark bulkhead just behind the fan face, both sides, wider than the duct: the duct is closed whatever the angle
            bd = [Vector((s * 0.74 + 0.62 * math.cos(2 * math.pi * k / 48), Y(FAN_D + 0.15), 2.40 + 0.62 * math.sin(2 * math.pi * k / 48))) for k in range(48)]
            bc = [Vector((s * 0.74 + 0.002 * math.cos(2 * math.pi * k / 48), Y(FAN_D + 0.15), 2.40 + 0.002 * math.sin(2 * math.pi * k / 48))) for k in range(48)]
            loft(mb, [bc, bd], False, False, DARK, simplify=False); loft(mb, [bd, bc], False, False, DARK, simplify=False)
        # outer face of the duct wall (seen when the fuselage breaks open), with stiffening rings every 0.9 m
        n0 = _fv(mb); loft(mb, [duct_ring(d, s, 0.025) for d in dl], False, False, MECH)   # every station: chords over fewer rings cut through the lining at the bends
        _facing(mb, n0, lambda c, a=duct_axis(s): c + (c - a(c)))
        for k in range(int((d1 - d0) / 1.8)):
            dd = d0 + 0.9 + 1.8 * k
            ring = duct_ring(dd, s, 0.025)
            n0 = _fv(mb); tube(mb, ring + [ring[0]], 0.018, N=4, mat=MECH, caps=False); _closed(mb, n0)


# ================================================================ engines: casing, accessories and mounts, plus a spinning fan
for side, s, num in (('L', -1, 1), ('R', 1, 3)):
    xc, zc = s * 0.74, 2.40
    eb = part(f'engine_body_{side}', origin=(xc, Y(26.0), zc), parent=f'engines_{side}', col=False)
    mb = eb.mb
    ring = lambda d, r, N=32: [Vector((xc + r * math.cos(2 * math.pi * k / N), Y(d), zc + r * math.sin(2 * math.pi * k / N))) for k in range(N)]
    # fan case lining (seen around the fan through the duct) and the outer casing, compressor, combustor, afterburner
    n0 = _fv(mb); loft(mb, [ring(FAN_D - 0.04, 0.525, 40), ring(FAN_D + 0.30, 0.525, 40)], False, False, INT)
    _facing(mb, n0, lambda c: Vector((xc, c.y, zc)))
    loft(mb, [ring(FAN_D + 0.30, 0.525, 40), ring(FAN_D - 0.04, 0.525, 40)], False, False, INT)      # both sides: never a culled gap round the fan
    prof = [(26.28, 0.565), (26.95, 0.565), (27.15, 0.50), (28.1, 0.46), (28.9, 0.44), (29.35, 0.50), (29.55, 0.565), (31.38, 0.575)]
    n0 = _fv(mb); loft(mb, [ring(d, r) for d, r in prof], True, True, MECH); _closed(mb, n0)
    for d, r in ((26.3, 0.575), (26.95, 0.575), (27.6, 0.49), (28.5, 0.455), (29.5, 0.575), (30.4, 0.58), (31.3, 0.585)):
        rr = ring(d, r, 24)
        n0 = _fv(mb); tube(mb, rr + [rr[0]], 0.018, N=4, mat=DARK, caps=False); _closed(mb, n0)
    # accessory gearbox under the compressor, with its drive and pipes running up the side
    rbox(mb, (xc, Y(27.85), zc - 0.56), (0.34, 1.05, 0.20), 0.03, MECH)
    cyl(mb, (xc, Y(27.85), zc - 0.46), (xc, Y(27.85), zc - 0.38), 0.07, N=12, mat=MECH)
    for k, (dx, rr) in enumerate(((0.10, 0.03), (-0.10, 0.025), (0.0, 0.02))):
        tube(mb, [(xc + dx, Y(27.4 + 0.1 * k), zc - 0.50), (xc + dx + s * 0.25, Y(27.9 + 0.2 * k), zc - 0.40),
                  (xc + s * 0.50, Y(28.6 + 0.3 * k), zc - 0.10), (xc + s * 0.47, Y(30.2), zc + 0.12)], rr, N=8, mat=DARK)
    # fuel and oil lines along the top, with clamps
    for dx in (-0.08, 0.0, 0.08):
        tube(mb, [(xc + dx, Y(26.9), zc + 0.60), (xc + dx, Y(28.6), zc + 0.49), (xc + dx, Y(29.6), zc + 0.60), (xc + dx, Y(31.2), zc + 0.62)], 0.016, N=6, mat=DARK)
    # mounts: forward trunnions to the side frame, a rear link to the roof frame
    for dz in (0.18, -0.18):
        rbox(mb, (xc + s * 0.68, Y(27.0), zc + dz), (0.24, 0.12, 0.08), 0.01, MECH)
    rbox(mb, (xc, Y(30.45), zc + 0.68), (0.12, 0.10, 0.22), 0.01, MECH)
    # the fan: its own transform (fan_<side>) so the plugin can spin it with the engine RPM
    fn = part(f'fan_{side}', origin=(xc, Y(FAN_D), zc), parent=f'engines_{side}', col=False)
    fm = fn.mb
    # inlet cone: a long conical spinner leading into the fan (part of the fan, so it turns with it)
    rh = 0.21
    loft(fm, [ring(dd, r, 32) for dd, r in ((FAN_D - 0.62, 0.004), (FAN_D - 0.50, 0.045), (FAN_D - 0.34, 0.10), (FAN_D - 0.18, 0.155),
                                             (FAN_D - 0.06, 0.195), (FAN_D + 0.02, rh), (FAN_D + 0.10, rh))], True, True, MECH)
    for k in range(22):
        a = 2 * math.pi * k / 22
        u = Vector((math.cos(a), 0, math.sin(a))); w = Vector((-math.sin(a), 0, math.cos(a)))
        def blade_pt(r, t, tw):
            return Vector((xc, Y(FAN_D - 0.02), zc)) + u * r + (w * math.cos(tw) + Vector((0, 1, 0)) * math.sin(tw)) * t
        rr_, tws, ch = (rh - 0.01, FAN_R), (math.radians(30), math.radians(62)), 0.10
        outline = [blade_pt(rr_[0], -ch, tws[0]), blade_pt(rr_[0], ch, tws[0]), blade_pt(rr_[1], ch * 1.1, tws[1]), blade_pt(rr_[1], -ch * 1.1, tws[1])]
        nn = (outline[1] - outline[0]).cross(outline[3] - outline[0]).normalized()
        plate(fm, outline, 0.010, nn, MECH)
    # solid engine face behind the blades, across the whole fan case: nothing behind the fan shows through the duct
    n0 = _fv(mb); loft(mb, [ring(FAN_D + 0.13, 0.002, 40), ring(FAN_D + 0.13, 0.53, 40)], False, False, DARK)
    _facing(mb, n0, lambda c: c + Vector((0, 1, 0)))
    # stator vanes and the first compressor disc behind the fan (fixed, on the engine)
    for k in range(30):
        a = 2 * math.pi * (k + 0.5) / 30
        u = Vector((math.cos(a), 0, math.sin(a)))
        c0 = Vector((xc, Y(FAN_D + 0.20), zc))
        plate(mb, [c0 + u * 0.15, c0 + u * 0.515, c0 + u * 0.515 + Vector((0, -0.08, 0)), c0 + u * 0.15 + Vector((0, -0.08, 0))], 0.008,
              u.cross(Vector((0, 1, 0))), DARK)
    cyl(mb, (xc, Y(FAN_D + 0.16), zc), (xc, Y(FAN_D + 0.34), zc), 0.15, N=20, mat=DARK)


# ================================================================ DECM battery racks behind the crew (former avionics racks)
def rack(mb, x0, x1, d0, d1, z0, z1, aisle):
    """Open frame of posts and shelves holding battery modules; terminals and cables face the aisle side (+1 = +x)."""
    W, L = x1 - x0, d1 - d0
    xm = (x0 + x1) / 2
    for xp in (x0 + 0.02, x1 - 0.02):
        for dp in (d0 + 0.02, d1 - 0.02):
            box(mb, (xp, Y(dp), (z0 + z1) / 2), (0.035, 0.035, z1 - z0))
    nsh = max(int((z1 - z0) / 0.30), 1)
    hs = (z1 - z0) / nsh
    for k in range(nsh + 1):
        box(mb, (xm, Y((d0 + d1) / 2), z0 + hs * k), (W, L, 0.02))
    nm = max(int((L - 0.06) / 0.24), 1)
    pitch = (L - 0.06) / nm
    xt = x1 if aisle > 0 else x0
    for k in range(nsh):
        zb = z0 + hs * k + 0.01
        for j in range(nm):
            dc = d0 + 0.03 + pitch * (j + 0.5)
            box(mb, (xm, Y(dc), zb + (hs - 0.05) / 2), (W - 0.06, pitch - 0.04, hs - 0.05), INT)
            box(mb, (xt - aisle * 0.025, Y(dc), zb + hs * 0.65), (0.03, pitch * 0.5, 0.04), DARK)        # terminal block
        # bus cable along each shelf front
        box(mb, (xt + aisle * 0.01, Y((d0 + d1) / 2), zb + hs * 0.80), (0.03, L - 0.1, 0.03), DARK)
    # cooling air duct along the top
    cyl(mb, (xm, Y(d0 + 0.02), z1 + 0.07), (xm, Y(d1 - 0.02), z1 + 0.07), 0.055, N=12, mat=MECH)


fF = PARTS['fuselage_F'].mb
for s in (1, -1):
    lo, hi = sorted((s * 0.50, s * 0.82))
    rack(fF, lo, hi, 10.30, 12.42, 1.88, 3.06, -s)         # cables face the centre aisle above the nose well
rack(fF, -0.40, 0.40, 10.30, 12.42, 2.48, 3.10, 1)
fbm = PARTS['fuselage'].mb
for s in (1, -1):
    lo, hi = sorted((s * 0.10, s * 0.72))
    rack(fbm, lo, hi, 12.78, 15.60, 2.92, 3.20, s)          # over the forward bay, between the ducts (was 0.92 wide x 3.44 high: poked through the top skin, 0.4.5)


# ================================================================ wing-box carry-through over the bay
CT = (19.6, 22.6, 2.93, 3.50, 1.95)
d0, d1, z0, z1, xw = CT
for dw in (d0, d1):
    rbox(fbm, (0, Y(dw), (z0 + z1) / 2), (2 * xw, 0.04, z1 - z0), 0.008, MECH)              # front and rear spar webs
    for xs in [-1.6 + 0.4 * k for k in range(9)]:
        rbox(fbm, (xs, Y(dw + (0.04 if dw == d0 else -0.04)), (z0 + z1) / 2), (0.04, 0.05, z1 - z0 - 0.02), 0.006, MECH)
for zc_ in (z0, z1):
    for dw in (d0, d1):
        rbox(fbm, (0, Y(dw), zc_), (2 * xw, 0.14, 0.05), 0.01, MECH)                         # spar caps
for xr in (-1.25, 0.0, 1.25):
    rbox(fbm, (xr, Y((d0 + d1) / 2), (z0 + z1) / 2), (0.04, d1 - d0, z1 - z0 - 0.02), 0.006, MECH)


# ================================================================ wings: spars, ribs and the pivot lug
def wbox(mb, s, x, c, top_in=0.012):
    return chord_pt(s, x, c, 1) - Vector((0, 0, top_in)), chord_pt(s, x, c, -1) + Vector((0, 0, top_in))


for side, s in (('R', 1), ('L', -1)):
    wm = PARTS[f'wing1_{side}'].mb
    wm2 = PARTS[f'wing2_{side}'].mb
    for mb_, xs in ((wm, [4.35, 5.4, 7.6, 9.5, W_SPLIT - 0.04]), (wm2, [W_SPLIT + 0.04, 12.2, W_TIP - 0.05])):
        for c in (0.15, 0.62):
            e = Vector((0, 0.012, 0))
            rings = []
            for x in xs:
                t, b = wbox(mb_, s, x, c)
                rings.append([t + e, t - e, b - e, b + e])
            n0 = _fv(mb_); loft(mb_, rings, True, True, MECH, smooth=False); _closed(mb_, n0)
    # ribs every 0.6 m, plus heavy closing ribs either side of the outer-panel break (the faces seen when it tears off)
    for x in [4.75 + 0.6 * k for k in range(14)] + [W_SPLIT - 0.05, W_SPLIT + 0.05, W_TIP - 0.06]:
        if x > W_TIP - 0.05: continue
        mb_ = wm if x < W_SPLIT else wm2
        heavy = abs(abs(x - W_SPLIT) - 0.05) < 1e-6 or abs(x - (W_TIP - 0.06)) < 1e-6
        cs = [(0.135 if heavy else 0.15) + ((0.70 if heavy else 0.62) - (0.135 if heavy else 0.15)) * j / 9 for j in range(10)]
        out = [wbox(mb_, s, x, c, 0.004 if heavy else 0.012)[0] for c in cs] + [wbox(mb_, s, x, c, 0.004 if heavy else 0.012)[1] for c in reversed(cs)]
        n0 = _fv(mb_); plate(mb_, out, 0.03 if heavy else 0.014, (1, 0, 0), MECH); _closed(mb_, n0)
    # pivot lug at the wing root (turns with the wing) and the bearing pin
    pv = Vector((s * PIVOT[0], Y(PIVOT[1]), PIVOT[2]))
    cyl(wm, pv - Vector((0, 0, 0.09)), pv + Vector((0, 0, 0.09)), 0.27, N=24, mat=MECH)
    cyl(wm, pv - Vector((0, 0, 0.16)), pv + Vector((0, 0, 0.16)), 0.10, N=16, mat=DARK)
    # glove: spars, ribs (kept clear of the gear-bay recess) and the pivot bearing housing
    gm = PARTS[f'wingroot_{side}'].mb
    st = [(1.85, 0.065), (2.6, 0.068), (3.6, 0.075), (4.6, 0.08), (5.35, 0.085)]
    def gt(x):
        for a, b in zip(st, st[1:]):
            if x <= b[0]: return a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0])
        return st[-1][1]
    def gpt(x, c, side_):
        le = glove_le(x); ch = 24.9 - le
        return Vector((s * x, Y(le + ch * c), GLOVE_Z + side_ * naca_t(c, gt(x)) * ch))
    def grib_ok(x, p):
        return not (2.0 <= x <= 4.2 and BAY_DD[0] - 0.05 <= dd_of(p) <= BAY_DD[1] + 0.05 and p.z < 2.26)
    for x in (2.2, 2.8, 3.4, 4.0, 4.95):
        cs = [0.10 + 0.78 * j / 10 for j in range(11)]
        top = [gpt(x, c, 1) - Vector((0, 0, 0.012)) for c in cs]
        bot = [gpt(x, c, -1) + Vector((0, 0, 0.012)) for c in cs]
        bot = [b if grib_ok(x, b) else Vector((b.x, b.y, max(b.z, 2.26))) for b in bot]
        out = top + list(reversed(bot))
        n0 = _fv(gm); plate(gm, out, 0.014, (1, 0, 0), MECH); _closed(gm, n0)
    for c in (0.10, 0.88):
        e = Vector((0, 0.012, 0)); rings = []
        for x in (1.95, 2.6, 3.6, 4.6, 5.25):
            t = gpt(x, c, 1) - Vector((0, 0, 0.012)); b = gpt(x, c, -1) + Vector((0, 0, 0.012))
            if not grib_ok(x, b): b = Vector((b.x, b.y, max(b.z, 2.26)))
            rings.append([t + e, t - e, b - e, b + e])
        n0 = _fv(gm); loft(gm, rings, True, True, MECH, smooth=False); _closed(gm, n0)
    n0 = _fv(gm); cyl(gm, pv - Vector((0, 0, 0.16)), pv + Vector((0, 0, 0.16)), 0.38, N=28, caps=False, mat=MECH)
    _facing(gm, n0, lambda c, pv=pv: c + (c - Vector((pv.x, pv.y, c.z))))
    for k in range(8):
        a = 2 * math.pi * k / 8
        u = Vector((math.cos(a), math.sin(a), 0))
        rbox(gm, pv + u * 0.50, (0.04, 0.04, 0.30), 0.006, MECH, rot=Matrix.Rotation(a, 3, 'Z'))


# ================================================================ fin spars and ribs (in the fin part, so they go with it when it breaks off)
tm = PARTS['rudder_L'].mb
def fpt(z, c, side_):
    le, te = fin_le(z), fin_te(z)
    ch = te - le
    return Vector((side_ * max(naca_t(c, _fin_t(z)) * ch - 0.010, 0.004), Y(le + ch * c), z))
for z in [4.80 + 0.45 * k for k in range(6)]:
    if z > FIN_TOP - 0.25: break
    cs = [0.10 + 0.55 * j / 8 for j in range(9)]
    out = [fpt(z, c, 1) for c in cs] + [fpt(z, c, -1) for c in reversed(cs)]
    n0 = _fv(tm); plate(tm, out, 0.014, (0, 0, 1), MECH); _closed(tm, n0)
for c in (0.10, 0.65):
    e = Vector((0, 0, 0.012)); rings = []
    for z in (FIN_ROOT_Z + 0.05, 5.6, 6.6, FIN_TOP - 0.20):
        a, b = fpt(z, c, 1), fpt(z, c, -1)
        rings.append([a + e, a - e, b - e, b + e])
    n0 = _fv(tm); loft(tm, rings, True, True, MECH, smooth=False); _closed(tm, n0)
# EW equipment in the tail cone: jammer and receiver boxes on a shelf, with cable runs
tm = PARTS['tail'].mb
rbox(tm, (0, Y(30.2), 2.92), (0.80, 2.6, 0.03), 0.006, MECH)
for dc, sz in ((29.3, (0.60, 0.55, 0.36)), (29.95, (0.60, 0.50, 0.36)), (30.65, (0.55, 0.55, 0.32)), (31.4, (0.46, 0.50, 0.30))):
    rbox(tm, (0, Y(dc), 2.94 + sz[2] / 2), sz, 0.02, INT)
for dx in (-0.20, 0.20):
    tube(tm, [(dx, Y(28.9), 3.42), (dx, Y(31.7), 3.36)], 0.02, N=6, mat=DARK)


# ================================================================ nose: radar antenna on its gimbal and the front bulkhead
nm = PARTS['nose'].mb
rc = Vector((0, Y(2.55), 2.33))
cyl(nm, rc, rc + Vector((0, 0.03, 0)), 0.44, N=40, mat=MECH)                     # flat-plate array
for k in range(5):
    cyl(nm, rc + Vector((0, 0.031, 0)), rc + Vector((0, 0.034, 0)), 0.40 - 0.08 * k, 0.40 - 0.08 * k - 0.02, N=40, caps=False, mat=DARK)
cyl(nm, rc - Vector((0, 0.02, 0)), rc - Vector((0, 0.35, 0)), 0.09, N=16, mat=MECH)   # gimbal drive
rbox(nm, (0, Y(3.05), 2.33), (0.50, 0.25, 0.40), 0.02, MECH)
bh = BODY.ring(3.32, -0.01)[::2]
n0 = _fv(nm); plate(nm, bh, 0.03, (0, 1, 0), MECH); _closed(nm, n0)
