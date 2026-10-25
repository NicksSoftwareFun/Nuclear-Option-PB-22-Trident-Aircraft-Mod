"""PB-22 Trident cockpit detail model. Unity prefab-root coordinates (x right, y up, z forward).
Builds the meshes with UVs into one 2048 atlas (regions in ATLAS, painted by pb22_cockpit_tex.py).
Front crew sit RAISE above 0.4.4 so the over-nose view reaches -7.5 deg."""
import os
CK = os.path.dirname(os.path.abspath(__file__))  # scripts, ctx.obj and tex/ output live next to this file
import math, json

RAISE = 0.19          # 2026-10-19: 0.15 after the roof clip, then +4 cm (eye y 0.497); matches PB22Cockpit FRONT_SEAT_Y -0.15
EYE = (-0.307, 0.307 + RAISE, 10.301)
FLOOR = -0.80

# ------------------------------------------------------------------ atlas (pixels in a 2048 texture, origin top-left)
ATLAS = {
    'paint':   (0, 0, 1024, 1024),       # panel paint, box-projected at PAINT_SCALE
    'dark':    (1024, 0, 512, 512),      # hood / bezel / grip paint
    'mfd':     (1536, 0, 256, 206),
    'mfd_r':   (1792, 0, 256, 206),      # rear station display bezel
    'mfdw':    (1024, 1560, 464, 206),   # merged centre display bezel
    'tread':   (1536, 1560, 512, 488),   # floor tread plate, one panel per UV square
    'heelpad': (1024, 1780, 128, 96),
    'pedal':   (1160, 1780, 96, 160),
    'hazard':  (1024, 1950, 256, 32),    # ejection hatch border (PB22Cockpit.UV_HAZARD), 0.10 m per region width
    'annun':   (1024, 512, 1024, 48),
    'adi':     (1024, 560, 160, 160),
    'asi':     (1184, 560, 128, 128),
    'alt':     (1312, 560, 128, 128),
    'rpm':     (1440, 560, 128, 128),
    'egt':     (1568, 560, 128, 128),
    'fuel':    (1696, 560, 128, 128),
    'clock':   (1824, 560, 128, 128),
    'cabalt':  (1024, 720, 128, 128),
    'keypad':  (1152, 720, 192, 132),
    'caution': (1344, 720, 192, 132),
    'cswitch': (1536, 720, 108, 210),
    'gear':    (1644, 720, 144, 120),
    'quad':    (1788, 720, 144, 300),
    'ped0':    (1024, 860, 240, 96),
    'ped1':    (1264, 860, 240, 96),
    'ped2':    (1280, 1240, 240, 96),
    'con0':    (0, 1024, 180, 216),
    'con1':    (180, 1024, 180, 216),
    'con2':    (360, 1024, 180, 216),
    'con3':    (540, 1024, 180, 216),
    'rctl':    (720, 1024, 400, 140),
    'rstat':   (1120, 1024, 300, 100),
    'rkbd':    (1420, 1024, 300, 140),
    'rcon':    (0, 1240, 180, 216),
    'grip':    (1720, 1024, 128, 128),
    'wall':    (0, 1456, 1024, 592),     # side-wall liner with lightening holes, planar mapped
    'sw':      (1024, 1240, 240, 96),    # glareshield-end switch strip
    'red':     (1940, 720, 64, 64),
    'ff':      (1536, 1260, 128, 128),
    'hyd':     (1664, 1260, 128, 128),
    'oil':     (1792, 1260, 128, 128),
    'nozl':    (1536, 1388, 128, 128),
    'brk':     (1664, 1388, 128, 128),
    'volt':    (1792, 1388, 128, 128),
    'o2':      (1920, 1388, 128, 128),
}
TEX = 2048.0
PAINT_SCALE = 0.30      # UV units per metre inside the paint region (1 m = 614 px)

# ------------------------------------------------------------------ mesh store
PARTS = {}   # part -> {'v':[], 'f':[(idx tuple, uv list, mat)]}
def _part(n): return PARTS.setdefault(n, {'v': [], 'f': []})

def vadd(a, b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def vsub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def vmul(a, s): return (a[0]*s, a[1]*s, a[2]*s)
def vdot(a, b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def vcross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def vnorm(a):
    l = math.sqrt(vdot(a, a)) or 1.0
    return (a[0]/l, a[1]/l, a[2]/l)

def region_uv(reg, s, t):
    """s,t in 0..1 across a region (t=0 bottom) -> atlas UV (v up)."""
    x, y, w, h = ATLAS[reg]
    return ((x + s*w)/TEX, 1.0 - (y + (1.0-t)*h)/TEX)

def paint_uv(p, n, reg='paint'):
    ax = max(range(3), key=lambda i: abs(n[i]))
    a, b = [(1, 2), (0, 2), (0, 1)][ax]
    x, y, w, h = ATLAS[reg]
    span = (w/TEX)/PAINT_SCALE * (1.0 if reg == 'paint' else 1.0)
    s = ((p[a] + 0.9) % span) / span
    t = ((p[b] + 0.9) % span) / span
    return region_uv(reg, s, t)

def poly(part, pts, mat='PB22_cockpit', uvs=None, paint='paint'):
    """add one polygon (world points, counter-clockwise seen from the visible side)."""
    P = _part(part)
    if uvs is None and mat == 'PB22_cabin':
        # cabin lining: box-projected at 2.5 m per UV unit, the same convention as the hull's PB22_cabin faces
        n = vnorm(vcross(vsub(pts[1], pts[0]), vsub(pts[2], pts[0])))
        ax = max(range(3), key=lambda i: abs(n[i])); a, b = [(2, 1), (0, 2), (0, 1)][ax]
        uvs = [(p[a]/2.5, p[b]/2.5) for p in pts]
    elif uvs is None:
        n = vnorm(vcross(vsub(pts[1], pts[0]), vsub(pts[2], pts[0])))
        if vdot(n, n) < 0.5 and len(pts) > 3:
            n = vnorm(vcross(vsub(pts[2], pts[1]), vsub(pts[3], pts[1])))
        # per-face paint projection, shifted so the face stays contiguous
        uvs = [paint_uv(p, n, paint) for p in pts]
        us = [u for u, _ in uvs]; vs = [v for _, v in uvs]
        x, y, w, h = ATLAS[paint]
        if max(us) - min(us) > (w/TEX)*0.5 or max(vs) - min(vs) > (h/TEX)*0.5:
            cen = (x + w*0.25)/TEX, 1.0 - (y + h*0.75)/TEX
            ax = max(range(3), key=lambda i: abs(n[i])); a, b = [(1, 2), (0, 2), (0, 1)][ax]
            mn_a = min(p[a] for p in pts); mn_b = min(p[b] for p in pts)
            uvs = [(cen[0] + (p[a]-mn_a)*PAINT_SCALE*(w/1024.0)*0.5, cen[1] + (p[b]-mn_b)*PAINT_SCALE*(h/1024.0)*0.5) for p in pts]
    base = len(P['v'])
    P['v'].extend(pts)
    P['f'].append((tuple(range(base, base+len(pts))), list(uvs), mat))

class Frame:
    def __init__(self, o, u, v, n): self.o, self.u, self.v, self.n = o, vnorm(u), vnorm(v), vnorm(n)
    def p(self, a, b, c=0.0): return vadd(self.o, vadd(vmul(self.u, a), vadd(vmul(self.v, b), vmul(self.n, c))))
    def at(self, a, b, c=0.0): return Frame(self.p(a, b, c), self.u, self.v, self.n)
    def yaw(self, deg):   # rotate u,n about v
        t = math.radians(deg); c, s = math.cos(t), math.sin(t)
        return Frame(self.o, vadd(vmul(self.u, c), vmul(self.n, s)), self.v, vsub(vmul(self.n, c), vmul(self.u, s)))
    def pitch(self, deg):  # rotate v,n about u (+ tips the top toward n)
        t = math.radians(deg); c, s = math.cos(t), math.sin(t)
        return Frame(self.o, self.u, vadd(vmul(self.v, c), vmul(self.n, s)), vsub(vmul(self.n, c), vmul(self.v, s)))
    def roll(self, deg):   # rotate u,v about n
        t = math.radians(deg); c, s = math.cos(t), math.sin(t)
        return Frame(self.o, vadd(vmul(self.u, c), vmul(self.v, s)), vsub(vmul(self.v, c), vmul(self.u, s)), self.n)

WORLD_FWD = Frame((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, -1))   # n toward the front crew (aft)

# ------------------------------------------------------------------ 2D shapes (local a,b)
def rect(w, h):
    def f(i=0.0):
        a, b = w/2-i, h/2-i
        return [(-a, -b), (a, -b), (a, b), (-a, b)]
    return f
def rrect(w, h, r, seg=3):
    def f(i=0.0):
        a, b, rr = w/2-i, h/2-i, max(r-i, 0.001)
        pts = []
        for cx, cy, a0 in ((a-rr, -b+rr, -90), (a-rr, b-rr, 0), (-a+rr, b-rr, 90), (-a+rr, -b+rr, 180)):
            for k in range(seg+1):
                t = math.radians(a0 + 90*k/seg)
                pts.append((cx + rr*math.cos(t), cy + rr*math.sin(t)))
        return pts
    return f
def circle(r, n=16):
    def f(i=0.0):
        return [((r-i)*math.cos(2*math.pi*k/n), (r-i)*math.sin(2*math.pi*k/n)) for k in range(n)]
    return f
def ngon(pts2):
    def f(i=0.0):
        if not i: return list(pts2)
        cx = sum(p[0] for p in pts2)/len(pts2); cy = sum(p[1] for p in pts2)/len(pts2)
        out = []
        for x, y in pts2:
            dx, dy = x-cx, y-cy; l = math.hypot(dx, dy) or 1
            out.append((x - dx/l*i, y - dy/l*i))
        return out
    return f

def _rpoly(part, pts, mat='PB22_cockpit', uvs=None, paint='paint'):
    """poly with reversed winding (prism builds its faces counter-clockwise in u,v, which faces -n)."""
    poly(part, list(reversed(pts)), mat, list(reversed(uvs)) if uvs else None, paint)

def prism(part, fr, shape, depth, mat='PB22_cockpit', decal=None, paint='paint', chamfer=0.0, proud=0.0,
          side_paint=None, back=False, decal_box=None, front=True, knobs=True):
    """extrude shape (in frame u,v) from n*proud back to n*(proud-depth); front face faces +n.
    decal: atlas region for the front face (mapped over the shape's bounding box, or decal_box=(w,h))."""
    poly = _rpoly
    outer = shape(0.0); m = len(outer)
    inner = shape(chamfer) if chamfer else outer
    if decal_box: bw, bh = decal_box
    else:
        bw = max(p[0] for p in outer) - min(p[0] for p in outer); bh = max(p[1] for p in outer) - min(p[1] for p in outer)
    def duv(pt): return region_uv(decal, 0.5 + pt[0]/bw, 0.5 + pt[1]/bh)
    zf = proud; zc = proud - chamfer; zb = proud - depth
    F = [fr.p(a, b, zf) for a, b in inner]
    if front: poly(part, F, mat, [duv(p) for p in inner] if decal else None, paint)
    if decal and knobs:
        for s_, t_, kind, rr_ in KNOB_MAP().get(decal, []):
            physical_knob(part, fr.at((s_ - 0.5)*bw, (t_ - 0.5)*bh), zf, kind, rr_*bw)
    sp = side_paint or paint
    if chamfer:
        for k in range(m):
            j = (k+1) % m
            q = [fr.p(*outer[k], zc), fr.p(*outer[j], zc), fr.p(*inner[j], zf), fr.p(*inner[k], zf)]
            poly(part, q, mat, [duv(outer[k]), duv(outer[j]), duv(inner[j]), duv(inner[k])] if decal else None, sp)
    if depth > chamfer:
        for k in range(m):
            j = (k+1) % m
            poly(part, [fr.p(*outer[k], zb), fr.p(*outer[j], zb), fr.p(*outer[j], zc), fr.p(*outer[k], zc)], mat, None, sp)
    if back:
        poly(part, [fr.p(a, b, zb) for a, b in reversed(outer)], mat, None, sp)

_KNOBS = {}
def KNOB_MAP():
    """knob / toggle positions printed by pb22_cockpit_tex.py, per atlas region (2026-10-19: every printed knob gets geometry)"""
    if not _KNOBS:
        try: _KNOBS.update(json.load(open(os.path.join(CK, 'knobs.json'))))
        except OSError: _KNOBS['_none'] = []
    return _KNOBS

def physical_knob(part, fr, z, kind, r):
    if kind == 'knob':      # skirted rotary knob with a red index line
        r = max(r, 0.007)
        prism(part, fr, circle(r*1.30, 10), 0.003, proud=z + 0.003, paint='dark', knobs=False)
        prism(part, fr, circle(r, 8), 0.014, chamfer=0.0015, proud=z + 0.017, paint='dark', knobs=False)
        prism(part, fr.at(0, r*0.45), rect(0.0016, r*0.8), 0.001, proud=z + 0.0175, decal='red', knobs=False)
    else:                   # bat toggle on a hex nut, leaning up; guarded ones get a red guard either side
        r = max(r, 0.004)
        prism(part, fr, circle(r*0.85, 6), 0.004, proud=z + 0.004, paint='dark', knobs=False)
        p0 = fr.p(0, 0, z + 0.004); p1 = fr.p(0, 0.006, z + 0.019)
        tube(part, p0, p1, 0.0018, 6)
        tube(part, p1, fr.p(0, 0.0072, z + 0.0235), 0.0030, 6)
        if kind == 'guard':
            for g in (-1, 1):
                prism(part, fr.at(g*r*1.45, -0.002), rect(0.0016, r*2.6), 0.016, proud=z + 0.016, decal='red', side_paint='dark',
                      decal_box=(0.4, 0.4), knobs=False)

def poly_shape(pts):
    """shape function for an arbitrary counter-clockwise outline (mitred inset for chamfers)"""
    def f(i=0.0):
        if not i: return list(pts)
        out = []; m = len(pts)
        for k in range(m):
            a, b, cc = pts[k-1], pts[k], pts[(k+1) % m]
            def nrm(p, q):
                dx, dy = q[0]-p[0], q[1]-p[1]; l = math.hypot(dx, dy) or 1.0
                return (-dy/l, dx/l)          # left of the edge = inside for a ccw outline
            n1, n2 = nrm(a, b), nrm(b, cc)
            bx, by = n1[0] + n2[0], n1[1] + n2[1]; bl = math.hypot(bx, by) or 1.0
            cosh = (n1[0]*bx + n1[1]*by)/bl or 1.0
            out.append((b[0] + bx/bl*i/cosh, b[1] + by/bl*i/cosh))
        return out
    return f

def face_toward(part, pts, want, mat='PB22_cockpit', uvs=None, paint='paint'):
    """polygon whose visible side faces the direction want, whatever order the points came in"""
    n = vcross(vsub(pts[1], pts[0]), vsub(pts[2], pts[0]))
    if vdot(n, want) < 0:
        pts = pts[::-1]; uvs = uvs[::-1] if uvs else None
    poly(part, pts, mat, uvs, paint)

def boxw(part, c, size, mat='PB22_cockpit', paint='paint', skip=()):
    """world-axis box; skip: faces to omit ('-x','+x','-y','+y','-z','+z')."""
    cx, cy, cz = c; w, h, d = size[0]/2, size[1]/2, size[2]/2
    V = lambda sx, sy, sz: (cx+sx*w, cy+sy*h, cz+sz*d)
    faces = {'-x': [V(-1,-1,-1), V(-1,-1,1), V(-1,1,1), V(-1,1,-1)], '+x': [V(1,-1,1), V(1,-1,-1), V(1,1,-1), V(1,1,1)],
             '-y': [V(-1,-1,-1), V(1,-1,-1), V(1,-1,1), V(-1,-1,1)], '+y': [V(-1,1,1), V(1,1,1), V(1,1,-1), V(-1,1,-1)],
             '-z': [V(1,-1,-1), V(-1,-1,-1), V(-1,1,-1), V(1,1,-1)], '+z': [V(-1,-1,1), V(1,-1,1), V(1,1,1), V(-1,1,1)]}
    for k, q in faces.items():
        if k not in skip: poly(part, q, mat, None, paint)

def tube(part, p0, p1, r, n=8, mat='PB22_cockpit', paint='dark', caps=True):
    d = vnorm(vsub(p1, p0)); a = vnorm(vcross(d, (0, 1, 0) if abs(d[1]) < 0.9 else (1, 0, 0))); b = vcross(d, a)
    ring = lambda c: [vadd(c, vadd(vmul(a, r*math.cos(2*math.pi*k/n)), vmul(b, r*math.sin(2*math.pi*k/n)))) for k in range(n)]
    r0, r1 = ring(p0), ring(p1)
    for k in range(n):
        j = (k+1) % n
        poly(part, [r0[k], r0[j], r1[j], r1[k]], mat, None, paint)
    if caps:
        poly(part, list(reversed(r0)), mat, None, paint); poly(part, r1, mat, None, paint)

# ================================================================== FRONT COCKPIT
TILT = 14.0
PZ, PY = 11.22, -0.05                 # panel face reference point (raised)
HINGE = 0.48                          # outer panel wings start here and yaw toward each seat
WING_YAW = 8.0
PANEL_TOP, PANEL_BOT, PANEL_HALF = 0.228, -0.34, 0.73

def face_z(y): return PZ + (y-PY)*math.tan(math.radians(TILT))
_t = math.radians(TILT)
CENTRE = Frame((0, PY, PZ), (1, 0, 0), (0, math.cos(_t), math.sin(_t)), (0, math.sin(_t), -math.cos(_t)))

def panel_frame(x, y):
    """frame on the panel face at unrolled x (wings fold toward the seats) and height y."""
    b = (y - PY)/math.cos(_t)
    if abs(x) <= HINGE: return CENTRE.at(x, b)
    s = 1 if x > 0 else -1
    h = CENTRE.at(s*HINGE, b).yaw(s*WING_YAW)
    return h.at(x - s*HINGE, 0)

def on_panel(part, x, y, shape, depth, **kw):
    prism(part, panel_frame(x, y), shape, depth, **kw)

# ---- panel body: centre slab plus two yawed wings, front skin with a knee-hole step at the bottom
# 2026-10-19: instruments below the MFDs sit recessed in the faceplate, the faceplate is the gauge-housing dark grey,
# and a half-hexagon notch under each pilot's cluster gives the knees room. The face is triangulated round the holes (earcut).
LEG_NOTCH = (0.31, 0.15, 0.08, -0.27)     # centre |x|, half-width at the bottom edge, half-width at the top, top y
FACES = {}    # face id -> (frame, inset outline); holes are cut when the instruments are placed
HOLES = {}    # face id -> list of hole outlines (face-local, clockwise not required)
_BC = ((PANEL_TOP + PANEL_BOT)/2 - PY)/math.cos(_t)
def face_of(x):
    """face id and local offset for a panel x (centre slab or a yawed wing)"""
    if abs(x) <= HINGE: return 'C', x
    s = 1 if x > 0 else -1
    return ('R' if s > 0 else 'L'), x - s*HINGE - s*(PANEL_HALF - HINGE)/2
def cut_hole(x, y, outline):
    fid, a0 = face_of(x)
    if fid == 'C': assert all(abs(a0 + a) <= HINGE - 0.008 for a, _ in outline), ('hole crosses the hinge', x, y)
    b0 = (y - PY)/math.cos(_t) - _BC
    HOLES.setdefault(fid, []).append([(a0 + a, b0 + b) for a, b in outline])
def panel_body():
    bh = (PANEL_TOP - PANEL_BOT)/math.cos(_t)
    B, T = -bh/2, -bh/2 + (LEG_NOTCH[3] - PANEL_BOT)/math.cos(_t)
    cx, hb, ht, _ = LEG_NOTCH
    out = [(-HINGE, B), (-(cx + hb), B), (-(cx + ht), T), (-(cx - ht), T), (-(cx - hb), B),
           ((cx - hb), B), ((cx - ht), T), ((cx + ht), T), ((cx + hb), B), (HINGE, B), (HINGE, bh/2), (-HINGE, bh/2)]
    shp = poly_shape(out)
    fr = CENTRE.at(0, _BC)
    prism('cockpit_int', fr, shp, 0.14, chamfer=0.006, proud=0.0, paint='dark', front=False)
    FACES['C'] = (fr, shp(0.006))
    for s in (-1, 1):
        w = PANEL_HALF - HINGE
        fr = CENTRE.at(s*HINGE, _BC).yaw(s*WING_YAW).at(s*w/2, 0)
        prism('cockpit_int', fr, rect(w, bh), 0.14, chamfer=0.006, paint='dark', front=False)
        FACES['R' if s > 0 else 'L'] = (fr, rect(w, bh)(0.006))
    # centre lower panel continues down into the pedestal
    lo = (-0.47 - PY)/math.cos(_t); hi = (PANEL_BOT + 0.02 - PY)/math.cos(_t)
    prism('cockpit_int', CENTRE.at(0, (lo+hi)/2), rect(0.26, hi-lo), 0.20, chamfer=0.006, paint='dark')

def faceplate():
    """front skin of the three panel faces with the instrument holes cut out"""
    import numpy as np, mapbox_earcut as earcut
    for fid, (fr, outline) in FACES.items():
        rings = [outline] + [h if _area(h) < 0 else h[::-1] for h in HOLES.get(fid, [])]
        flat = [p for r in rings for p in r]
        ends = np.cumsum([len(r) for r in rings]).astype(np.uint32)
        tri = earcut.triangulate_float64(np.array(flat, dtype=np.float64), ends)
        for k in range(0, len(tri), 3):
            face_toward('cockpit_int', [fr.p(*flat[i], 0.0) for i in tri[k:k+3]], fr.n, paint='dark')
def _area(r): return sum(r[k-1][0]*r[k][1] - r[k][0]*r[k-1][1] for k in range(len(r)))/2

# ---- glareshield hood: lofted along the panel top, lip overhangs the screens; ends kick up outboard
HOOD_TOP, HOOD_LIP, HOOD_FWD = 0.265, 0.13, 0.20
def hood():
    stations = [-PANEL_HALF, -0.64, -HINGE, -0.45, 0.0, 0.45, HINGE, 0.64, PANEL_HALF]
    def kick(x):
        ax = abs(x)
        return 0.0 if ax <= 0.55 else min(1.0, (ax-0.55)/0.12)*0.035
    def section(x):
        fr = panel_frame(x, PANEL_TOP)
        up = (0, 1, 0)
        k = kick(x)
        lip_n = HOOD_LIP + k*0.4
        base_aft = fr.p(0, 0, 0.0)
        # points: under-lip (aft), lip top aft, top front, panel-top front (behind face)
        p_under = vadd(fr.p(0, 0, lip_n), (0, 0.0, 0))
        p_lipb = (p_under[0], PANEL_TOP - 0.028, p_under[2])     # deep lip face carries two rows of annunciators
        p_lipt = (p_under[0], HOOD_TOP + k, p_under[2])
        top_f = fr.p(0, 0, -HOOD_FWD)
        p_topf = (top_f[0], HOOD_TOP + k - 0.012, top_f[2])
        p_botf = (top_f[0], PANEL_TOP - 0.02, top_f[2])
        p_face = (base_aft[0], PANEL_TOP + 0.002, base_aft[2])
        # rounded lip: quarter round from the lip face onto the top
        top_y = HOOD_TOP + k
        R_ = 0.018
        arc = []
        for j in range(1, 4):
            a = math.radians(90*j/4)
            arc.append((p_under[0], top_y - R_ + R_*math.sin(a), p_under[2] + R_ - R_*math.cos(a) + 0.0))
        p_lipt = (p_under[0], top_y - R_, p_under[2])
        p_top2 = (p_under[0], top_y, p_under[2] + R_)
        return [p_face, p_lipb, p_lipt] + arc + [p_top2, p_topf, p_botf]
    secs = [section(x) for x in stations]
    for i in range(len(stations)-1):
        A, B = secs[i], secs[i+1]
        central = stations[i] >= -0.45 and stations[i+1] <= 0.45
        for k in range(len(A)-1):
            q = [A[k], A[k+1], B[k+1], B[k]]
            if k == 1 and central:
                # each pilot's half of the lip face shows the same lamp strip, drawn live by the stock tac screen apps
                uv = [rt_uv('annun', 0, 0), rt_uv('annun', 0, 1), rt_uv('annun', 1, 1), rt_uv('annun', 1, 0)]
                poly('tacScreen', q, 'tacScreenDisplay', uv)
            else:
                poly('cockpit_int', q, 'PB22_cockpit', None, 'dark')
    # end caps
    poly('cockpit_int', list(reversed(secs[0])), 'PB22_cockpit', None, 'dark')
    poly('cockpit_int', secs[-1], 'PB22_cockpit', None, 'dark')
    # stock-style red warning lamps at the hood corners (CockpitWarningLights flashes these)
    for s in (-1, 1):
        x = s*0.665
        fr = panel_frame(x, PANEL_TOP)
        c = fr.p(0, 0, HOOD_LIP + 0.012)
        y = HOOD_TOP + kick(x) + 0.004
        # master caution push-light: dark bezel with a recessed lamp face (the face is the flashing CockpitWarningLight)
        top = Frame((c[0], y, c[2]+0.025), (1, 0, 0), (0, 0, 1), (0, 1, 0))
        prism('cockpit_int', top, rrect(0.064, 0.046, 0.006, 2), 0.012, chamfer=0.003, proud=0.012, paint='dark')
        prism('warningLights', top, rrect(0.046, 0.028, 0.004, 2), 0.004, mat='CockpitWarningLight', proud=0.0135)
        # small switch strip on the end
        prism('cockpit_int', Frame((c[0], y+0.0, c[2]+0.09), (1, 0, 0), (0, 0, 1), (0, 1, 0)), rect(0.10, 0.05), 0.004, decal='sw', proud=0.004)

# ---- closeouts: bulkhead plates from the panel ends out to the hull, so no hull shows past the panel edges
def closeouts():
    # outline follows the 0.4.5 cabin wall (half-width 0.81 at the panel foot, 0.74 at the sill) and stops below the windscreen sill
    out = [(0.725, PANEL_BOT), (0.805, PANEL_BOT), (0.790, -0.25), (0.765, -0.15), (0.744, -0.05), (0.735, 0.06), (0.725, 0.06)]
    for s in (-1, 1):
        e = panel_frame(s*PANEL_HALF, (PANEL_BOT + 0.06)/2).p(0, 0, -0.03)
        pts = [(s*x, y) for x, y in out]
        if s < 0: pts = pts[::-1]
        prism('cockpit_int', Frame((0, 0, e[2]), (1, 0, 0), (0, 1, 0), (0, 0, -1)), ngon(pts), 0.02, proud=0.01)

# ---- displays (2026-10-19, after the 0.4.6 flight): tac map on the outer pair, stores page on the middle pair,
# one shared engine / flight display where the inboard pair was. Every glass shows a region of the stock tac screen
# render texture (1024x512, laid out by PB22Cockpit.TacScreen); RT_REGIONS must match the canvas layout there.
DISPLAY_Y = 0.076      # screens stretched down to the gauge rows (2026-10-19)
DISPLAY_X = (0.12, 0.351, 0.5975)    # 2026-10-19: centre switch box moved outboard, screens widened into the gap
BEZEL = (0.219, 0.204); GLASS = (0.184, 0.167)
CENTRE_BEZEL = (2*DISPLAY_X[0] + BEZEL[0], BEZEL[1])            # the two inboard displays merged into one
CENTRE_GLASS = (CENTRE_BEZEL[0] - (BEZEL[0] - GLASS[0]), GLASS[1])
RT_W, RT_H = 1024, 512
RT_REGIONS = {                       # pixels, origin top-left of the render texture
    'tac':    (0, 0, 440, 400),      # 1.10 : 1, the outer glass aspect
    'centre': (440, 0, 584, 230),    # 2.54 : 1, the merged centre glass
    'stores': (440, 230, 310, 282),  # 1.10 : 1, the middle glass
    'annun':  (0, 400, 440, 46),     # one pilot's lamp strip (0.45 x 0.047 m)
    'adi':    (760, 250, 256, 256),  # standby attitude ball (stock ArtificialHorizon), both pilots
}
def rt_uv(name, s, t):
    """s, t in 0..1 across the region (t = 0 at the bottom edge) -> render texture UV."""
    x, y, w, h = RT_REGIONS[name]
    return ((x + s*w)/RT_W, 1.0 - (y + (1.0 - t)*h)/RT_H)
SCREENS = []   # (side, idx, frame); idx 0 = centre (side 0), 1 = middle, 2 = outer
def display(fr, bezel, glass, region, decal, nbtn):
    prism('cockpit_int', fr, rrect(*bezel, 0.010, 2), 0.03, decal=decal, chamfer=0.004, proud=0.026, side_paint='dark',
          decal_box=bezel)
    g = fr.at(0, 0.004)
    gw, gh = glass
    pts = [g.p(-gw/2, -gh/2, 0.0275), g.p(gw/2, -gh/2, 0.0275), g.p(gw/2, gh/2, 0.0275), g.p(-gw/2, gh/2, 0.0275)]
    uv = [rt_uv(region, 0, 0), rt_uv(region, 1, 0), rt_uv(region, 1, 1), rt_uv(region, 0, 1)]
    poly('tacScreen', pts[::-1], 'tacScreenDisplay', uv[::-1])     # glass faces the crew (+n)
    # push buttons along the top and bottom edges
    pitch = 0.034
    for row in (-1, 1):
        for b in range(nbtn):
            prism('cockpit_int', fr.at((b - (nbtn - 1)/2)*pitch, row*0.0935), rect(0.018, 0.009), 0.006, proud=0.032, paint='dark')
def displays():
    fr = panel_frame(0.0, DISPLAY_Y)
    display(fr, CENTRE_BEZEL, CENTRE_GLASS, 'centre', 'mfdw', 11)
    SCREENS.append((0, 0, fr))
    for s in (-1, 1):
        for i, region in ((1, 'stores'), (2, 'tac')):
            fr = panel_frame(s*DISPLAY_X[i], DISPLAY_Y)
            display(fr, BEZEL, GLASS, region, 'mfd', 5)
            SCREENS.append((s, i, fr))

# ---- analog standby cluster under each centre display: attitude, airspeed, altimeter
SB_Y = -0.085
SCREEN_PAD = 32.5/930   # screen sheet cells are 512x465 with the 512x400 page centred
SW_Y = -0.112
WELL = 0.020       # instrument recess depth behind the faceplate
def well(fr, outline, depth, x, y, lip=0.004):
    """hole in the faceplate with dark walls, a back plate and a thin raised lip round the opening"""
    cut_hole(x, y, outline)
    m = len(outline)
    cen = fr.p(0, 0, -depth/2)
    for k in range(m):
        a, b = outline[k], outline[(k+1) % m]
        q = [fr.p(*a, 0.0), fr.p(*b, 0.0), fr.p(*b, -depth), fr.p(*a, -depth)]
        mid = vmul(vadd(q[0], q[2]), 0.5)
        face_toward('cockpit_int', q, vsub(cen, mid), paint='dark')
    face_toward('cockpit_int', [fr.p(*p, -depth) for p in outline], fr.n, paint='dark')
    if lip:
        cx = sum(p[0] for p in outline)/m; cy = sum(p[1] for p in outline)/m
        def grow(p, d):
            dx, dy = p[0] - cx, p[1] - cy; l = math.hypot(dx, dy) or 1.0
            return (p[0] + dx/l*d, p[1] + dy/l*d)
        for k in range(m):
            a, b = outline[k], outline[(k+1) % m]
            ring = [fr.p(*a, 0.002), fr.p(*b, 0.002), fr.p(*grow(b, lip), 0.002), fr.p(*grow(a, lip), 0.002)]
            face_toward('cockpit_int', ring, fr.n, paint='dark')
            edge = [fr.p(*grow(a, lip), 0.002), fr.p(*grow(b, lip), 0.002), fr.p(*grow(b, lip), 0.0), fr.p(*grow(a, lip), 0.0)]
            face_toward('cockpit_int', edge, vsub(edge[0], fr.p(cx, cy, 0.0)), paint='dark')
def gauge(x, y, r, face, n=16):
    fr = panel_frame(x, y)
    well(fr, circle(r + 0.003, n)(), WELL, x, y)
    if face == 'adi':       # live attitude ball: the stock ArtificialHorizon app draws into the tac screen texture
        pts = circle(r, n)(); 
        face_toward('tacScreen', [fr.p(a, b, -0.012) for a, b in pts], fr.n, 'tacScreenDisplay',
                    [rt_uv('adi', 0.5 + a/(2*r), 0.5 + b/(2*r)) for a, b in pts])
    else:
        prism('cockpit_int', fr, circle(r, n), 0.0015, decal=face, proud=-0.012, decal_box=(2*r, 2*r))
def inset_panel(x, y, shape, decal, depth=0.012, **kw):
    """rectangular instrument panel sunk into the faceplate (knobs and toggles still stand proud)"""
    fr = panel_frame(x, y)
    o = shape(); m = len(o)
    well(fr, poly_shape(o)(-0.003), depth, x, y)
    prism('cockpit_int', fr, shape, 0.006, decal=decal, proud=-0.007, side_paint='dark', **kw)
    return fr
def standby():
    for s in (-1, 1):
        x = s*0.342
        gauge(x, SB_Y - 0.006, 0.046, 'adi', 24)          # standby gauges sized to read from the seat
        gauge(x - 0.093, SB_Y, 0.033, 'asi', 18)       # cluster pulled in so no hole crosses the panel hinge
        gauge(x + 0.093, SB_Y, 0.033, 'alt', 18)
        inset_panel(s*0.141, SB_Y - 0.005, rrect(0.100, 0.105, 0.008, 2), 'keypad')
        # master arm / jettison / ECM switch box with gear and flap lights, one per pilot where the caution grid was
        inset_panel(s*0.60, SW_Y, rect(0.088, 0.16), 'cswitch')
    # shared engine stack (analog) on the centre lower panel
    for dx in (-0.045, 0.045):
        gauge(dx, -0.075, 0.030, 'rpm')
        gauge(dx, -0.152, 0.027, 'egt')
    # second analog row under each pilot's standby gauges and keypad (outboard to inboard)
    for s, faces in ((-1, ('ff', 'fuel', 'hyd', 'oil')), (1, ('nozl', 'brk', 'volt', 'o2'))):
        for x, face in zip((0.434, 0.342, 0.250, 0.158), faces):
            gauge(s*x, -0.205, 0.035, face, 18)
    # gear handle panel on the pilot's lower left, handle sticks out toward him
    inset_panel(-0.59, -0.272, rrect(0.13, 0.11, 0.008, 2), 'gear')
    fr = panel_frame(-0.62, -0.272)
    tube('cockpit_int', fr.p(0, 0, -0.007), fr.p(0, 0, 0.09), 0.008, 6)
    prism('cockpit_int', fr.at(0, 0, 0.09), circle(0.022, 10), 0.03, proud=0.03, paint='dark', back=True)
    # co-pilot's lower right: fuel and hydraulic panel
    inset_panel(0.59, -0.272, rrect(0.13, 0.11, 0.008, 2), 'ped2')
    faceplate()

# ---- pedestal and throttle quadrant
PED_TOP = -0.28
THROTTLE_PIVOT = (0.0, PED_TOP + 0.02, 10.84)
PIVOTS = {}   # part -> pivot point (unity); parts not listed pivot at the prefab-root origin
def pedestal():
    # pedestal box from the panel back toward the seats
    z0, z1 = 10.30, face_z(-0.47)
    boxw('cockpit_int', (0, (FLOOR + PED_TOP)/2, (z0+z1)/2), (0.26, PED_TOP - FLOOR, z1 - z0), skip=('+z', '-y'))
    # throttle quadrant: raised box with two slots, levers swing on a shaft (Cockpit.throttles[])
    qz = 10.80
    fr = Frame((0, PED_TOP + 0.05, qz), (1, 0, 0), (0, 0, 1), (0, 1, 0)).pitch(-6)
    prism('cockpit_int', fr, rect(0.20, 0.30), 0.09, decal='quad', chamfer=0.006, proud=0.0)    # deep enough to sit into the pedestal top
    for k, z in enumerate((10.55, 10.45, 10.35)):
        prism('cockpit_int', Frame((0, PED_TOP + 0.001, z), (1, 0, 0), (0, 0, 1), (0, 1, 0)), rect(0.22, 0.085), 0.01,
              decal='ped%d' % (k % 2), proud=0.008)
    for s in (-1, 1):
        x = s*0.045
        piv = THROTTLE_PIVOT[:1] and (x, THROTTLE_PIVOT[1], THROTTLE_PIVOT[2])
        a = math.radians(45.0)                        # idle: lever leans aft 45 deg; full throttle swings it +54 deg (stock range) to 9 deg forward
        top = (x, piv[1] + 0.20*math.cos(a), piv[2] - 0.20*math.sin(a))
        tube('throttle', piv, top, 0.010, 6, paint='dark')
        prism('throttle', Frame(top, (1, 0, 0), (0, 1, 0), (0, 0, -1)), rrect(0.07, 0.035, 0.012, 2), 0.045, proud=0.0225,
              paint='dark', back=True, decal='grip', decal_box=(0.07, 0.035))

# ---- side consoles (pilot left, co-pilot right)
CON_TOP = -0.37
def consoles():
    for s in (-1, 1):
        x = s*0.715
        boxw('cockpit_int', (x, (FLOOR + CON_TOP)/2, 10.50), (0.17, CON_TOP - FLOOR, 1.10), skip=('-y', '+z'))
        for k in range(4):
            prism('cockpit_int', Frame((x, CON_TOP + 0.0, 10.88 - k*0.24), (1, 0, 0), (0, 0, 1), (0, 1, 0)),
                  rect(0.15, 0.21), 0.012, decal='con%d' % ((k + (0 if s < 0 else 2)) % 4), chamfer=0.003, proud=0.008)
        # sill liner above the console up to the canopy rail
        fr = Frame((s*0.765, -0.20, 10.55), (0, 0, -s), (0, 1, 0), (-s, 0, 0))     # kept below the canopy sill so it reads as liner, not a box
        prism('cockpit_int', fr, rect(1.10, 0.32), 0.02, mat='PB22_cabin', proud=0.0)

# ---- yokes: column pivots at the floor (pitch), wheel turns about the column axis (roll)
HUB_Y = -0.08
COL_TILT = 8.0
YOKE_PIVOTS = {}
def yokes():
    for s in (-1, 1):
        x = s*0.34
        foot = (x, FLOOR + 0.03, 10.98)
        # column well: base plate with a stepped rubber boot round the column foot
        flat = lambda y, z: Frame((x, y, z), (1, 0, 0), (0, 0, 1), (0, 1, 0))
        prism('cockpit_int', flat(FLOOR + 0.012, 10.92), rrect(0.17, 0.15, 0.012, 2), 0.012, chamfer=0.003, proud=0.0, paint='dark')
        for k, (bw, bd) in enumerate(((0.12, 0.11), (0.095, 0.085), (0.07, 0.06))):
            prism('cockpit_int', flat(FLOOR + 0.012 + 0.018*(k + 1), 10.94), rrect(bw, bd, 0.012, 2), 0.018, chamfer=0.004, proud=0.0, paint='dark')
        # column: straight tube leaning aft by COL_TILT
        t = math.radians(COL_TILT)
        L = (HUB_Y - foot[1]) / math.cos(t)
        axis = (0, math.cos(t), -math.sin(t))
        hub = vadd(foot, vmul(axis, L))
        side = 'L' if s < 0 else 'R'
        tube('yoke_col_' + side, foot, hub, 0.024, 8)
        PIVOTS['yoke_col_' + side] = foot; PIVOTS['yoke_wheel_' + side] = hub
        YOKE_PIVOTS[s] = {'column_pivot': foot, 'column_axis': axis, 'hub': hub}
        # wheel frame: n along the column toward the pilot (perpendicular to the wheel), u across, v up the wheel
        wn = vnorm((0, math.sin(t), -math.cos(t)))
        wv = vnorm(vcross(wn, (1, 0, 0)))
        wv = vmul(wv, -1) if wv[1] < 0 else wv
        W = Frame(vadd(hub, vmul(wn, 0.03)), (1, 0, 0), wv, wn)
        prism('yoke_wheel_' + side, W, rrect(0.10, 0.075, 0.02, 2), 0.06, chamfer=0.006, proud=0.03, paint='dark', back=True, decal='grip',
              decal_box=(0.10, 0.075))
        # column detail: guide collar where the column leaves the boot, clamp band mid-way, bearing housing under the hub
        for f_, rr_, ln in ((0.10, 0.032, 0.03), (0.55, 0.029, 0.018), (0.93, 0.034, 0.04)):
            c0 = vadd(foot, vmul(axis, L*f_)); tube('yoke_col_' + side, c0, vadd(c0, vmul(axis, ln)), rr_, 10, paint='dark')
        # hub boss between column head and wheel, with a trim switch plate and a checklist clip on the centre
        tube('yoke_wheel_' + side, hub, vadd(hub, vmul(wn, 0.03)), 0.030, 10, paint='dark')
        prism('yoke_wheel_' + side, W.at(0, 0.045), rrect(0.07, 0.014, 0.004, 2), 0.006, proud=0.036, paint='dark')
        prism('yoke_wheel_' + side, W.at(0, -0.012), circle(0.008, 8), 0.006, proud=0.036, decal='grip', decal_box=(0.3, 0.3))
        # shallow W cross-bar under the hub out to the horns
        for g in (-1, 1):
            a0 = W.p(g*0.045, -0.03); a1 = W.p(g*0.12, -0.055); a2 = W.p(g*0.175, -0.035)
            tube('yoke_wheel_' + side, a0, a1, 0.014, 6, caps=False); tube('yoke_wheel_' + side, a1, a2, 0.014, 6, caps=False)
            # horn grip canted outboard ~18 deg, with a dark grip head (hat switch, red pickle button)
            hb = a2; ht = vadd(hb, vadd(vmul(W.v, 0.085), vmul(W.u, g*0.030)))
            tube('yoke_wheel_' + side, hb, vadd(hb, vmul(vsub(ht, hb), 0.5)), 0.019, 10, caps=False); tube('yoke_wheel_' + side, vadd(hb, vmul(vsub(ht, hb), 0.5)), ht, 0.017, 10)
            hd = vnorm(vsub(ht, hb))
            for f_ in (0.30, 0.48, 0.66):       # finger ridges round the grip
                gr = vadd(hb, vmul(vsub(ht, hb), f_)); tube('yoke_wheel_' + side, gr, vadd(gr, vmul(hd, 0.006)), 0.0215, 10, paint='dark')
            # trigger on the forward face, thumb button on the inboard face
            trg = Frame(vadd(hb, vmul(vsub(ht, hb), 0.78)), W.u, hd, vmul(W.n, -1))
            prism('yoke_wheel_' + side, trg, rrect(0.012, 0.024, 0.004, 2), 0.016, proud=0.026, paint='dark', back=True)
            thb = Frame(vadd(hb, vmul(vsub(ht, hb), 0.85)), W.n, hd, vmul(W.u, -g))
            prism('yoke_wheel_' + side, thb, circle(0.005, 8), 0.006, proud=0.022, decal='grip', decal_box=(0.3, 0.3))
            # gusset plate where the horn meets the cross-bar
            prism('yoke_wheel_' + side, Frame(a1, W.u, W.v, W.n), ngon([(-g*0.0, -0.012), (g*0.055, 0.010), (0.0, 0.016)]) if g > 0 else
                  ngon([(0.0, -0.012), (0.0, 0.016), (g*0.055, 0.010)]), 0.008, proud=0.004, paint='dark', back=True)
            head = Frame(ht, W.u, hd, W.n).at(0, 0.012)
            prism('yoke_wheel_' + side, head, rrect(0.040, 0.030, 0.010, 2), 0.036, chamfer=0.004, proud=0.018, paint='dark', back=True)
            prism('yoke_wheel_' + side, head.at(0, 0.006), circle(0.006, 6), 0.005, proud=0.024, mat='PB22_cockpit', decal='grip',
                  decal_box=(0.4, 0.4))                         # hat switch
            top = Frame(vadd(ht, vmul(vnorm(vsub(ht, hb)), 0.028)), vmul(W.u, -1), W.n, vnorm(vsub(ht, hb)))
            prism('yoke_wheel_' + side, top.at(-g*0.006, 0.004), circle(0.006, 6), 0.004, proud=0.004, decal='red')   # pickle
        # rudder pedals: ribbed faces with toe-brake bands on swing arms from a cross shaft at the front of the heel rest
        piv_z, piv_y = 11.47, FW_Y + 0.045
        tube('cockpit_int', (x - 0.14, piv_y, piv_z), (x + 0.14, piv_y, piv_z), 0.016, 8)
        for bx in (x - 0.15, x + 0.15):
            boxw('cockpit_int', (bx, (FW_Y + piv_y)/2 + 0.01, piv_z), (0.025, piv_y - FW_Y + 0.04, 0.06), paint='dark', skip=('-y',))
        for dx in (-0.09, 0.09):
            fr = Frame((x+dx, FW_Y + 0.08, 11.30), (1, 0, 0), (0, 1, 0), (0, 0, -1)).pitch(-20)
            prism('cockpit_int', fr, rrect(0.075, 0.13, 0.012, 2), 0.025, chamfer=0.004, paint='dark', back=True, decal='pedal',
                  decal_box=(0.075, 0.13))
            back_c = fr.p(0, 0, -0.026)
            tube('cockpit_int', back_c, (x + dx, piv_y, piv_z), 0.011, 6)
            tube('cockpit_int', fr.p(0, 0.05, -0.026), (x + dx, piv_y + 0.01, piv_z - 0.02), 0.008, 6)

# ---- footwell: raised heel rest under the pedals
FW_Y = FLOOR + 0.12 + (RAISE - 0.15)    # heel rest follows the seat raise
def footwell():
    boxw('cockpit_int', (0, FW_Y - 0.01, 11.33), (1.40, 0.02, 0.66), 'aircraft_structure', skip=('-y', '+y'))
    boxw('cockpit_int', (0, (FLOOR + FW_Y)/2, 10.995), (1.40, FW_Y - FLOOR, 0.01), 'PB22_cabin', skip=('+z', '-y'))
    flat = lambda x, y, z: Frame((x, y, z), (1, 0, 0), (0, 0, 1), (0, 1, 0))
    # heel rest: one tread plate per pilot, rubber heel pad, metal nosing on the step
    for s in (-1, 1):
        prism('cockpit_int', flat(s*0.35, FW_Y, 11.33), rect(0.70, 0.66), 0.006, decal='tread', decal_box=(0.70, 0.66), proud=0.0, paint='dark')
        prism('cockpit_int', flat(s*0.34, FW_Y + 0.006, 11.09), rrect(0.24, 0.15, 0.012, 2), 0.006, decal='heelpad', decal_box=(0.24, 0.15),
              chamfer=0.002, proud=0.0)
    boxw('cockpit_int', (0, FW_Y + 0.003, 11.005), (1.40, 0.012, 0.03), paint='dark')
    # main floor: tread plates in a deliberate grid (outboard pairs either side, a centre plate aft of the pedestal),
    # seated on a dark frame so the plate edges read as separate panels
    boxw('cockpit_int', (0, FLOOR + 0.003, 10.32), (1.30, 0.006, 1.35), paint='dark', skip=('-y',))
    for s in (-1, 1):
        for z0, z1 in ((9.65, 10.32), (10.32, 10.99)):
            prism('cockpit_int', flat(s*0.38, FLOOR + 0.006, (z0 + z1)/2), rect(0.49, z1 - z0 - 0.012), 0.008, decal='tread',
                  decal_box=(0.50, 0.67), chamfer=0.002, proud=0.004, paint='dark')
    prism('cockpit_int', flat(0.0, FLOOR + 0.006, 9.975), rect(0.24, 0.638), 0.008, decal='tread', decal_box=(0.50, 0.67),
          chamfer=0.002, proud=0.004, paint='dark')
    # seat risers (front seats sit RAISE higher than the stock mounting)
    for s in (-1, 1):
        boxw('cockpit_int', (s*0.34, FLOOR + RAISE/2, 10.45), (0.36, RAISE, 0.46), 'PB22_cabin', skip=('-y',))

# ---- partition between the front seats and the aft-facing rear stations (avionics racks)
def partition():
    boxw('cockpit_int', (0, -0.40, 9.60), (1.62, 0.80, 0.10), 'PB22_cabin', skip=('-y',))
    for k, x in enumerate((-0.52, -0.17, 0.17, 0.52)):
        for zz, nz in ((9.655, 1), (9.545, -1)):
            f = Frame((x, -0.42, zz), (1, 0, 0) if nz < 0 else (-1, 0, 0), (0, 1, 0), (0, 0, -1) if nz < 0 else (0, 0, 1))
            prism('cockpit_int', f, rect(0.30, 0.55), 0.03, chamfer=0.004, proud=0.03, paint='dark')
    boxw('cockpit_int', (0, 0.02, 9.60), (1.50, 0.04, 0.16), paint='dark')

# ================================================================== REAR STATIONS (aft-facing)
def rear():
    WALL_Z = 7.66
    REAR = Frame((0, 0, WALL_Z + 0.05), (-1, 0, 0), (0, 1, 0), (0, 0, 1))   # faces +z (toward the rear crew, who face aft)
    # wall follows the cabin taper at the top corners (cabin half-width 0.75 at y 0.3, 0.71 at y 0.5)
    prism('rear_int', REAR.at(0, 0.05), ngon([(-0.72, -0.475), (0.72, -0.475), (0.72, 0.24), (0.60, 0.475), (-0.60, 0.475), (-0.72, 0.24)]),
          0.10, chamfer=0.008)
    for s in (-1, 1):
        xc = s*0.34
        a = -xc   # REAR.u is -x
        for dx in (-0.135, 0.135):
            fr = REAR.at(a + dx, 0.12)
            prism('rear_int', fr, rrect(0.25, 0.20, 0.01, 2), 0.02, decal='mfd_r', chamfer=0.004, proud=0.02, side_paint='dark',
                  decal_box=(0.25, 0.20))
            g = fr; gw, gh = 0.212, 0.16
            # screen sheet: left column flight (top) / nav (bottom), right column EW (top) / stores (bottom)
            def page(u0, v0, p=SCREEN_PAD): return [(u0, v0 + p), (u0 + 0.5, v0 + p), (u0 + 0.5, v0 + 0.5 - p), (u0, v0 + 0.5 - p)]   # crop the tall-cell padding
            mission = page(0.5, 0.5) if s < 0 else page(0.5, 0.0)     # navigator/EW officer: threat page, weapons officer: stores page
            ruv = page(0.0, 0.0) if (dx < 0) == (s < 0) else mission
            poly('rear_screens', [g.p(-gw/2, -gh/2, 0.0205), g.p(gw/2, -gh/2, 0.0205), g.p(gw/2, gh/2, 0.0205), g.p(-gw/2, gh/2, 0.0205)][::-1],
                 'PB22_screen', ruv[::-1])
        prism('rear_int', REAR.at(a, 0.31), rect(0.30, 0.10), 0.015, decal='rstat', proud=0.015, side_paint='dark')
        # glare hood over the display pair
        hz = REAR.at(a, 0.235)
        for q in ([hz.p(-0.29, 0, 0.0), hz.p(0.29, 0, 0.0), hz.p(0.29, 0, 0.09), hz.p(-0.29, 0, 0.09)],):
            poly('rear_int', q, 'PB22_cockpit', None, 'dark'); poly('rear_int', list(reversed(q)), 'PB22_cockpit', None, 'dark')
        for e in (-0.29, 0.29):
            q = [hz.p(e, 0, 0.0), hz.p(e, 0, 0.09), hz.p(e, -0.24, 0.035), hz.p(e, -0.24, 0.0)]
            poly('rear_int', q, 'PB22_cockpit', None, 'dark'); poly('rear_int', list(reversed(q)), 'PB22_cockpit', None, 'dark')
        for dy, face in ((0.17, 'clock'), (0.06, 'cabalt')):       # analog clock and cabin altimeter outboard of the displays
            c = REAR.at(a - s*0.325, dy)
            prism('rear_int', c, circle(0.030, 12), 0.015, chamfer=0.003, proud=0.02, paint='dark')
            prism('rear_int', c, circle(0.026, 12), 0.0015, decal=face, proud=0.0205, decal_box=(0.052, 0.052))
        prism('rear_int', REAR.at(a, -0.335), rect(0.24, 0.096), 0.02, decal='ped0' if s < 0 else 'ped2', chamfer=0.003, proud=0.02, side_paint='dark')
        prism('rear_int', REAR.at(a, -0.19).pitch(-15), rect(0.40, 0.14), 0.03, decal='rctl', chamfer=0.004, proud=0.03, side_paint='dark')
        # desk with keyboard and hand controller
        prism('rear_int', Frame((xc, -0.40, 7.95), (-1, 0, 0), (0, 0, -1), (0, 1, 0)), rect(0.30, 0.15), 0.02, decal='rkbd',
              chamfer=0.003, proud=0.02)
        prism('rear_int', Frame((xc + s*0.20, -0.40, 7.97), (-1, 0, 0), (0, 0, -1), (0, 1, 0)), circle(0.035, 10), 0.04,
              chamfer=0.006, proud=0.04, paint='dark')
        # side console
        boxw('rear_int', (s*0.72, -0.62, 8.65), (0.16, 0.32, 0.80), skip=('-y',))
        prism('rear_int', Frame((s*0.72, -0.46, 8.65), (-1, 0, 0), (0, 0, -1), (0, 1, 0)), rect(0.14, 0.20), 0.01, decal='rcon',
              proud=0.006)
    boxw('rear_int', (0, -0.42, 7.92), (1.42, 0.04, 0.44), skip=('-y',))
    boxw('rear_int', (0, 0.0, 7.76), (0.04, 0.70, 0.12))     # divider between the two stations
    boxw('rear_int', (0, -0.62, 7.86), (1.42, 0.36, 0.30), skip=('-y', '-z'))

# ================================================================== simple exterior stand-ins (*_int_simple, Matte_black)
# ---- glareshield deck: the hood top carried forward to the base of the nose glass (2026-10-19)
# stations (z, deck height, inner hull half-width at that height) measured on the 0.4.5 hull
DECK = [(11.38, 0.240, 0.722), (11.46, 0.248, 0.716), (11.6, 0.243, 0.690), (11.8, 0.229, 0.643), (12.0, 0.215, 0.581), (12.2, 0.201, 0.501),
        (12.4, 0.187, 0.410), (12.6, 0.173, 0.363), (12.8, 0.159, 0.311), (13.0, 0.145, 0.247), (13.15, 0.135, 0.181),
        (13.3, 0.122, 0.205), (13.42, 0.108, 0.175), (13.52, 0.094, 0.02)]   # tapers to a point inside the nose skin
def deck(part='cockpit_int', mat='PB22_cockpit', paint='dark'):
    # first row starts under the hood top (the hood's front face steps down onto the deck); edges run flush to the hull with a skirt below
    rows = [[(-w, y, z), (0.0, y, z), (w, y, z)] for z, y, w in DECK]
    for a, b in zip(rows, rows[1:]):
        for k in range(2):
            poly(part, [a[k], a[k+1], b[k+1], b[k]][::-1], mat, None, paint)
        for k, sgn in ((0, -1), (2, 1)):      # side skirts 4 cm down so no daylight shows between the deck edge and the hull
            lo_a = (a[k][0], a[k][1] - 0.04, a[k][2]); lo_b = (b[k][0], b[k][1] - 0.04, b[k][2])
            q = [a[k], b[k], lo_b, lo_a]
            poly(part, q if sgn > 0 else q[::-1], mat, None, paint)

def simple():
    P = 'cockpit_int_simple'
    deck(P, 'Matte_black')
    boxw(P, (0, (PANEL_TOP + PANEL_BOT)/2, face_z(0.0) + 0.05), (1.46, PANEL_TOP - PANEL_BOT, 0.18), 'Matte_black', skip=('-y',))
    boxw(P, (0, HOOD_TOP - 0.02, 11.30), (1.46, 0.05, 0.36), 'Matte_black')
    boxw(P, (0, (FLOOR + PED_TOP)/2, 10.70), (0.26, PED_TOP - FLOOR, 0.80), 'Matte_black', skip=('-y',))
    for s in (-1, 1):
        boxw(P, (s*0.715, (FLOOR + CON_TOP)/2, 10.50), (0.17, CON_TOP - FLOOR, 1.10), 'Matte_black', skip=('-y',))
    boxw(P, (0, -0.40, 9.60), (1.62, 0.80, 0.10), 'Matte_black', skip=('-y',))
    boxw('rear_int_simple', (0, 0.05, 7.66), (1.42, 0.95, 0.10), 'Matte_black')
    boxw('rear_int_simple', (0, -0.52, 7.90), (1.42, 0.56, 0.44), 'Matte_black', skip=('-y',))

def build_all():
    PARTS.clear(); SCREENS.clear(); PIVOTS.clear(); PIVOTS['throttle'] = THROTTLE_PIVOT
    panel_body(); closeouts(); hood(); deck(); displays(); standby(); pedestal(); consoles(); yokes(); footwell(); partition(); rear(); simple()
    return PARTS

def tri_count(parts=None):
    parts = parts or PARTS
    return {k: sum(len(f[0]) - 2 for f in p['f']) for k, p in parts.items()}

if __name__ == '__main__':
    build_all()
    tc = tri_count(); print(tc, 'front', sum(v for k, v in tc.items() if not k.startswith('rear') and 'simple' not in k),
                            'rear', sum(v for k, v in tc.items() if k.startswith('rear') and 'simple' not in k))
