"""Shared geometry helpers for the PB-22 Trident build scripts (Blender 5.x / bpy).
Axes: Blender X right, Y forward, Z up. d = metres aft of the nose tip, Y = NOSE_Y - d.
Every generated mesh gets world-scale UVs (1 UV unit = 1 m) so a single pack step can lay all
skin parts out in one atlas at a constant texel density."""
import bpy, bmesh, math
from mathutils import Vector

NOSE_Y = 17.0
def Y(d): return NOSE_Y - d

# ------------------------------------------------------------------ station interpolation
def catmull(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)

def smooth_stations(st, per_seg=4):
    """st: list of tuples of floats (first item is the station position). Catmull-Rom through all
    values, per_seg rings per segment. Keeps the original stations exactly."""
    out = []
    n = len(st)
    for i in range(n - 1):
        p0 = st[max(i - 1, 0)]; p1 = st[i]; p2 = st[i + 1]; p3 = st[min(i + 2, n - 1)]
        for k in range(per_seg):
            t = k / per_seg
            out.append(tuple(catmull(a, b, c, d, t) for a, b, c, d in zip(p0, p1, p2, p3)))
    out.append(tuple(st[-1]))
    return out

# ------------------------------------------------------------------ mesh building
class MeshBuilder:
    """bmesh wrapper that keeps a UV layer and material slots."""
    def __init__(self):
        self.bm = bmesh.new(); self.uv = self.bm.loops.layers.uv.new('UVMap')
    def face(self, verts, uvs=None, mat=0, smooth=True):
        f = self.bm.faces.new(verts); f.material_index = mat; f.smooth = smooth
        if uvs:
            for l, uv in zip(f.loops, uvs): l[self.uv].uv = uv
        return f
    def verts(self, pts): return [self.bm.verts.new(p) for p in pts]

def ring_lengths(ring, closed=True):
    acc = [0.0]
    for i in range(1, len(ring) + (1 if closed else 0)):
        acc.append(acc[-1] + (ring[i % len(ring)] - ring[i - 1]).length)
    return acc

# loft simplification: rings, and points around the rings, that lie within LOFT_TOL of the straight line between their
# kept neighbours are dropped before the faces are built (only for materials in LOFT_MATS). The limit shrinks with the
# loft's size (LOFT_REL) so small tubes and antennas keep their shape.
LOFT_TOL, LOFT_REL, LOFT_MATS = 0.0, 0.01, ()
# internal structure is only seen through battle damage: while INT_TOL is set, every non-skin loft is simplified with
# that coarser limit (LOFT_REL still protects small parts) and cylinders and tubes use N_SCALE times their segments
INT_TOL, INT_SKIP, N_SCALE = 0.0, (), 1.0

def _lerp_dev(pts, a, b, mids):
    """Largest distance from pts[mids] to the segment pts[a]..pts[b]."""
    pa, pb = pts[a], pts[b]; ab = pb - pa; L2 = ab.length_squared
    worst = 0.0
    for m in mids:
        t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, (pts[m] - pa).dot(ab) / L2))
        worst = max(worst, (pts[m] - (pa + ab * t)).length)
    return worst

def _keep_greedy(n, dev, closed):
    """Indices to keep from 0..n-1: extend each span while dev(a, b, mids) stays within the limit."""
    keep = [0]; a = 0
    end = n if closed else n - 1
    b = a + 2
    while b <= end:
        if dev(a, b, range(a + 1, b)):
            b += 1
        else:
            keep.append(b - 1); a = b - 1; b = a + 2
    if not closed and keep[-1] != n - 1: keep.append(n - 1)
    return keep

def simplify_rings(rings, closed=True, columns=True, limit=None):
    if len(rings) < 2: return rings
    allp = [p for r in rings for p in r]
    lo = Vector((min(p.x for p in allp), min(p.y for p in allp), min(p.z for p in allp)))
    hi = Vector((max(p.x for p in allp), max(p.y for p in allp), max(p.z for p in allp)))
    size = sorted((hi - lo)[:])[1]                 # middle extent: the loft's cross-section scale
    tol = min(LOFT_TOL if limit is None else limit, LOFT_REL * size)
    if tol <= 0: return rings
    N = len(rings[0])
    # along the loft: a ring goes when every point of it sits on the line between the same points of its kept neighbours
    def dev_r(a, b, mids): return all(_lerp_dev([r[i] for r in rings], a, b, mids) <= tol for i in range(N))
    keep_r = _keep_greedy(len(rings), dev_r, False)
    rings = [rings[k] for k in keep_r]
    # around the rings: a column goes when it is straight on every ring
    if columns and N > 6:
        ext = [r + [r[0]] if closed else r for r in rings]
        def dev_c(a, b, mids): return all(_lerp_dev(e, a, b, mids) <= tol for e in ext)
        keep_c = _keep_greedy(N, dev_c, closed)
        if len(keep_c) >= 4: rings = [[r[i] for i in keep_c] for r in rings]
    return rings

def loft(mb, rings, cap0=True, cap1=True, mat=0, closed=True, smooth=True, simplify=True):
    """Loft rings (lists of Vector, same count). UV u = arc length around ring 0..perimeter,
    v = distance along the loft (measured on the ring centroids)."""
    # the end rings always stay; points around the ring only go on capped closed bodies, whose ends meet nothing else
    if simplify and LOFT_TOL > 0 and mat in LOFT_MATS: rings = simplify_rings(rings, closed, closed and cap0 and cap1)
    elif simplify and INT_TOL > 0 and mat not in LOFT_MATS and mat not in INT_SKIP:
        rings = simplify_rings(rings, closed, closed and cap0 and cap1, INT_TOL)
    vr = [mb.verts(r) for r in rings]
    N = len(rings[0])
    cents = [sum(r, Vector()) / len(r) for r in rings]
    vpos = [0.0]
    for a, b in zip(cents, cents[1:]): vpos.append(vpos[-1] + (b - a).length)
    us = [ring_lengths(r, closed) for r in rings]
    seg = N if closed else N - 1
    for k in range(len(rings) - 1):
        a, b = vr[k], vr[k + 1]
        for i in range(seg):
            j = (i + 1) % N
            mb.face((a[i], a[j], b[j], b[i]), [(us[k][i], vpos[k]), (us[k][i + 1], vpos[k]), (us[k + 1][i + 1], vpos[k + 1]), (us[k + 1][i], vpos[k + 1])], mat, smooth)
    for cap, ring, verts in ((cap0, rings[0], vr[0]), (cap1, rings[-1], vr[-1])):
        if not cap or not closed: continue
        c = sum(ring, Vector()) / len(ring)
        # planar-ish cap: project on the two longest extents for UVs
        uvs = [((p - c).x + (p - c).y, (p - c).z) for p in ring]
        vs = list(reversed(verts)) if verts is vr[0] else verts
        us_ = list(reversed(uvs)) if verts is vr[0] else uvs
        mb.face(vs, us_, mat, False)
    return vr

def superellipse(a, b, n, N=48, rot=0.0):
    pts = []
    for i in range(N):
        t = 2 * math.pi * i / N + rot
        c, s = math.cos(t), math.sin(t)
        pts.append((a * math.copysign(abs(c) ** (2 / n), c), b * math.copysign(abs(s) ** (2 / n), s)))
    return pts

def body_rings(stations, N=48, xoff=0.0, rake=None, half=None):
    """stations: (d, half_w, half_h, z_centre, n [, x_centre]). Rings in the X-Z plane.
    rake: d offset at the bottom of the FIRST station (raked lips). half: 'R'/'L' keeps one side only."""
    rings = []
    for k, st in enumerate(stations):
        d, a, b, zc, n = st[:5]
        xc = st[5] if len(st) > 5 else 0.0
        r = []
        for (x, z) in superellipse(a, b, n, N, rot=-math.pi / 2):
            dd = d
            if rake and k == 0: dd = d + rake * (b - z) / (2 * b)
            r.append(Vector((xoff + xc + x, Y(dd), zc + z)))
        rings.append(r)
    return rings

# ------------------------------------------------------------------ aerofoil surfaces
def naca_t(x, t):
    return 5 * t * (0.2969 * math.sqrt(max(x, 0)) - 0.1260 * x - 0.3516 * x * x + 0.2843 * x ** 3 - 0.1036 * x ** 4)

def section(t, c0=0.0, c1=1.0, n=14, droop=0.0):
    """Closed profile of the chord slice c0..c1 (fractions), thickness ratio t. Returns list of (u, v):
    upper surface c0->c1 then lower c1->c0. Cut ends become flat faces."""
    xs = [c0 + (c1 - c0) * 0.5 * (1 - math.cos(math.pi * i / n)) for i in range(n + 1)]
    up = [(x, naca_t(x, t) + droop * x) for x in xs]
    lo = [(x, -naca_t(x, t) + droop * x) for x in reversed(xs)]
    pts = up + lo
    # drop duplicate points at a sharp leading edge / closed trailing edge
    clean = []
    for p in pts:
        if not clean or abs(p[0] - clean[-1][0]) + abs(p[1] - clean[-1][1]) > 1e-6: clean.append(p)
    if abs(clean[0][0] - clean[-1][0]) + abs(clean[0][1] - clean[-1][1]) < 1e-6: clean.pop()
    return clean

def surface(mb, stations, thick_axis, c0=0.0, c1=1.0, n=14, mat=0):
    """stations: (LE point, chord vector LE->TE, thickness ratio). Lofts the chord slice c0..c1.
    Thickness is scaled by the full chord so slices of one wing line up exactly."""
    rings = []
    for le, chord, t in stations:
        rings.append([le + chord * u + thick_axis * (v * chord.length) for u, v in section(t, c0, c1, n)])
    return loft(mb, rings, True, True, mat)

# ------------------------------------------------------------------ primitives
def cyl_rings(p0, p1, r0, r1=None, N=24):
    r1 = r0 if r1 is None else r1
    p0, p1 = Vector(p0), Vector(p1)
    ax = (p1 - p0).normalized()
    ref = Vector((0, 0, 1)) if abs(ax.z) < 0.9 else Vector((1, 0, 0))
    u = ax.cross(ref).normalized(); v = ax.cross(u)
    return [[p + (u * math.cos(2 * math.pi * i / N) + v * math.sin(2 * math.pi * i / N)) * r for i in range(N)] for p, r in ((p0, r0), (p1, r1))]

def _scaled(N): return N if N_SCALE >= 1 else max(4, int(round(N * N_SCALE)))

def cyl(mb, p0, p1, r0, r1=None, N=24, caps=True, mat=0):
    N = _scaled(N)
    return loft(mb, cyl_rings(p0, p1, r0, r1, N), caps, caps, mat)

def tube(mb, pts, radii, N=16, mat=0, caps=True):
    """Swept circle along a polyline (for struts, braces, actuators)."""
    N = _scaled(N); rings = []
    for i, p in enumerate(pts):
        p = Vector(p)
        a = (Vector(pts[min(i + 1, len(pts) - 1)]) - Vector(pts[max(i - 1, 0)])).normalized()
        ref = Vector((0, 0, 1)) if abs(a.z) < 0.9 else Vector((1, 0, 0))
        u = a.cross(ref).normalized(); v = a.cross(u)
        r = radii[i] if isinstance(radii, (list, tuple)) else radii
        rings.append([p + (u * math.cos(2 * math.pi * k / N) + v * math.sin(2 * math.pi * k / N)) * r for k in range(N)])
    return loft(mb, rings, caps, caps, mat)

def rbox(mb, centre, size, bevel=0.02, mat=0, rot=None):
    """Box with chamfered edges (a cheap bevel) built as a loft of chamfered rectangles along Y."""
    cx, cy, cz = centre; sx, sy, sz = size
    b = min(bevel, sx / 2.5, sz / 2.5, sy / 2.5)
    def rect(y, shrink):
        hx, hz = sx / 2 - shrink, sz / 2 - shrink
        pts = [(hx - b, -hz), (hx, -hz + b), (hx, hz - b), (hx - b, hz), (-hx + b, hz), (-hx, hz - b), (-hx, -hz + b), (-hx + b, -hz)]
        return [Vector((x, y, z)) for x, z in reversed(pts)]     # this winding gives outward normals
    rings = [rect(-sy / 2, b), rect(-sy / 2 + b, 0), rect(sy / 2 - b, 0), rect(sy / 2, b)]
    if rot is not None:
        rings = [[rot @ p for p in r] for r in rings]
    rings = [[p + Vector((cx, cy, cz)) for p in r] for r in rings]
    return loft(mb, rings, True, True, mat, smooth=False)

def plate(mb, outline, thickness, normal, mat=0):
    """Extruded flat plate from a closed outline (list of Vector) along normal."""
    nrm = Vector(normal).normalized() * (thickness / 2)
    rings = [[p - nrm for p in outline], [p + nrm for p in outline]]
    return loft(mb, rings, True, True, mat, smooth=False)

# ------------------------------------------------------------------ objects
def make_obj(name, mb, mats, coll, origin=None, parent=None):
    """origin: world point that becomes the object's origin (vertices are stored relative to it)."""
    me = bpy.data.meshes.new(name)
    if origin is not None:
        o = Vector(origin)
        for v in mb.bm.verts: v.co -= o
    mb.bm.to_mesh(me); mb.bm.free()
    for m in mats: me.materials.append(m)
    ob = bpy.data.objects.new(name, me); coll.objects.link(ob)
    if origin is not None: ob.location = Vector(origin)
    if parent is not None: parent_keep(ob, parent)
    return ob

def parent_keep(child, parent):
    bpy.context.view_layer.update()
    mw = child.matrix_world.copy(); child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted(); child.matrix_world = mw

def empty(name, loc, coll, parent=None, kind='PLAIN_AXES', size=0.4):
    o = bpy.data.objects.new(name, None); o.empty_display_type = kind; o.empty_display_size = size
    o.location = Vector(loc); coll.objects.link(o)
    if parent is not None: parent_keep(o, parent)
    return o

def mirror_pts(pts): return [Vector((-p.x, p.y, p.z)) for p in pts]
