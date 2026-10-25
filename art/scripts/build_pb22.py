"""PB-22 Trident (Tu-22M3-based) model build, game metres.
Blender axes: X right, Y forward (nose tip at Y=+17), Z up, ground at Z=0. Unity: +Z forward, +Y up, +X right.
Stations are given as d = metres aft of the nose tip; Y = 17 - d.
Usage: python3 build_pb22.py <out.blend> [sweep_deg]   (sweep 0 = 20 deg wing, 45 = 65 deg)
All parts are lofted from the numbers below so revisions only touch numbers."""
import bpy, bmesh, sys, math
from mathutils import Vector, Matrix

args = [a for a in sys.argv[sys.argv.index('--') + 1:]] if '--' in sys.argv else sys.argv[1:]
out = args[0] if args else 'pb22.blend'
SWEEP = float(args[1]) if len(args) > 1 else 0.0
GEAR_UP = len(args) > 2 and args[2] == 'gearup'

NOSE_Y = 17.0
def Y(d): return NOSE_Y - d

# ---------------------------------------------------------------- fixed numbers
BELLY_Z = 1.30          # fuselage underside on gear (gear lowered 0.30 m)
FIN_TOP = 7.83          # fin tip incl. RWR fairing (limit 7.84)
PIVOT = (4.43, 21.2, 2.30)   # wing pivot (x, d, z)
WING_ANHEDRAL = -3.0
GEAR_X = 2.95           # main bogie centreline
GEAR_TRUNNION_X = 3.10  # in the glove; leg near vertical, folds inward
MAIN_WHEEL_R, MAIN_WHEEL_W = 0.41, 0.28
NOSE_WHEEL_R, NOSE_WHEEL_W = 0.40, 0.26
MID_PYLON_X, GLOVE_PYLON_X = 1.55, 3.9
PD_LEN, PD_DIA, PD_FIN = 6.975, 0.85, 1.31

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
def coll(name):
    c = bpy.data.collections.new(name); sc.collection.children.link(c); return c
G = coll('GUIDES'); P = coll('PIVOTS'); M = coll('MODEL')

# ---------------------------------------------------------------- materials (flat, first pass)
def mat(name, col, rough=0.5, metal=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*col, 1); b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    return m
SKIN = mat('PB22_skin', (0.60, 0.61, 0.62))
MECH = mat('PB22_mech', (0.42, 0.43, 0.44), 0.45, 0.3)
DARK = mat('PB22_dark', (0.05, 0.05, 0.055), 0.7)
GLASS = mat('PB22_glass', (0.08, 0.10, 0.13), 0.1)
TYRE = mat('PB22_tyre', (0.07, 0.07, 0.07), 0.8)

# ---------------------------------------------------------------- mesh helpers
def new_obj(name, bm, mats=(SKIN,), parent=None, col=M):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m_ in mats: me.materials.append(m_)
    o = bpy.data.objects.new(name, me); col.objects.link(o)
    if parent: o.parent = parent
    for p in me.polygons: p.use_smooth = True
    return o

def superellipse(a, b, n, N=32):
    pts = []
    for i in range(N):
        t = 2 * math.pi * i / N
        c, s = math.cos(t), math.sin(t)
        pts.append((a * math.copysign(abs(c) ** (2 / n), c), b * math.copysign(abs(s) ** (2 / n), s)))
    return pts

def loft(bm, rings, cap0=True, cap1=True, mat_index=0):
    """rings: list of lists of Vector (same count). Returns list of vert rings."""
    vr = [[bm.verts.new(p) for p in r] for r in rings]
    N = len(rings[0])
    for a, b in zip(vr, vr[1:]):
        for i in range(N):
            f = bm.faces.new((a[i], a[(i + 1) % N], b[(i + 1) % N], b[i])); f.material_index = mat_index
    if cap0:
        f = bm.faces.new(list(reversed(vr[0]))); f.material_index = mat_index
    if cap1:
        f = bm.faces.new(vr[-1]); f.material_index = mat_index
    return vr

def bridge(bm, ra, rb, mat_index=0):
    N = len(ra)
    for i in range(N):
        f = bm.faces.new((ra[i], ra[(i + 1) % N], rb[(i + 1) % N], rb[i])); f.material_index = mat_index

def body_rings(stations, N=40, xoff=0.0, rake=None):
    """stations: (d, half_w, half_h, z_centre, n). Ring in X-Z plane at Y(d)."""
    rings = []
    for k, (d, a, b, zc, n) in enumerate(stations):
        r = []
        for (x, z) in superellipse(a, b, n, N):
            dd = d
            if rake and k == 0:          # raked intake lip: bottom sits further aft
                dd = d + rake * ((zc + b) - (zc + z)) / (2 * b)
            r.append(Vector((xoff + x, Y(dd), zc + z)))
        rings.append(r)
    return rings

def naca(t, n=16):
    """closed symmetric section, chord 0..1 along +u, thickness +-v. returns list of (u, v)."""
    xs = [0.5 * (1 - math.cos(math.pi * i / n)) for i in range(n + 1)]
    def yt(x): return 5 * t * (0.2969 * math.sqrt(x) - 0.1260 * x - 0.3516 * x * x + 0.2843 * x ** 3 - 0.1036 * x ** 4)
    upper = [(x, yt(x)) for x in xs]
    lower = [(x, -yt(x)) for x in reversed(xs[1:-1])]
    return upper + lower

def surface(name, stations, thick_axis, mats=(SKIN,), parent=None, t_ratio=None, n=16):
    """stations: list of (LE Vector, chord vector (LE->TE), thickness ratio). thickness along thick_axis."""
    bm = bmesh.new(); rings = []
    for le, chord, t in stations:
        r = []
        for u, v in naca(t, n):
            r.append(le + chord * u + thick_axis * (v * chord.length))
        rings.append(r)
    loft(bm, rings)
    return new_obj(name, bm, mats, parent)

def cyl(name, p0, p1, r0, r1=None, N=24, mats=(MECH,), parent=None, caps=True):
    r1 = r0 if r1 is None else r1
    p0, p1 = Vector(p0), Vector(p1)
    ax = (p1 - p0).normalized()
    ref = Vector((0, 0, 1)) if abs(ax.z) < 0.9 else Vector((1, 0, 0))
    u = ax.cross(ref).normalized(); v = ax.cross(u)
    rings = []
    for p, r in ((p0, r0), (p1, r1)):
        rings.append([p + (u * math.cos(2 * math.pi * i / N) + v * math.sin(2 * math.pi * i / N)) * r for i in range(N)])
    bm = bmesh.new(); loft(bm, rings, caps, caps)
    return new_obj(name, bm, mats, parent)

def box(name, centre, size, mats=(MECH,), parent=None):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2])) + Vector(centre)
    o = new_obj(name, bm, mats, parent)
    for p in o.data.polygons: p.use_smooth = False
    return o

def wheel(name, centre, r, w, parent=None):
    """tyre with rounded shoulder + hub, axle along X."""
    c = Vector(centre); bm = bmesh.new(); rings = []
    prof = [(-0.5, 0.62), (-0.5, 0.80), (-0.42, 0.97), (-0.22, 1.0), (0.22, 1.0), (0.42, 0.97), (0.5, 0.80), (0.5, 0.62)]
    N = 32
    for (xf, rf) in prof:
        rings.append([c + Vector((xf * w, math.cos(2 * math.pi * i / N) * r * rf, math.sin(2 * math.pi * i / N) * r * rf)) for i in range(N)])
    loft(bm, rings, True, True, mat_index=0)
    o = new_obj(name, bm, (TYRE,), parent)
    cyl(name + '_hub', c + Vector((-w * 0.52, 0, 0)), c + Vector((w * 0.52, 0, 0)), r * 0.6, N=24, mats=(MECH,), parent=o)
    return o

def empty(name, loc, parent=None, kind='ARROWS', size=0.5, rot=(0, 0, 0)):
    o = bpy.data.objects.new(name, None); o.empty_display_type = kind; o.empty_display_size = size
    o.location = loc; o.rotation_euler = rot; P.objects.link(o)
    if parent: o.parent = parent
    return o

def set_parent_keep(child, parent):
    bpy.context.view_layer.update()
    mw = child.matrix_world.copy(); child.parent = parent; child.matrix_parent_inverse = parent.matrix_world.inverted(); child.matrix_world = mw

# ================================================================ FUSELAGE
# forward fuselage: radome, avionics, cockpit section (d 0 - 13.2)
fwd = [
    (0.00, 0.025, 0.025, 2.02, 2.0),
    (0.60, 0.17, 0.16, 2.04, 2.0),
    (1.60, 0.36, 0.34, 2.09, 2.0),
    (2.70, 0.54, 0.52, 2.15, 2.1),
    (3.40, 0.64, 0.62, 2.19, 2.2),
    (4.60, 0.80, 0.80, 2.24, 2.3),
    (6.00, 0.91, 0.94, 2.28, 2.4),
    (7.50, 0.95, 1.00, 2.31, 2.5),
    (9.50, 0.96, 1.10, 2.40, 2.6),
    (11.5, 0.95, 1.15, 2.45, 2.7),
    (13.6, 0.95, 1.16, 2.46, 2.7),
]
bm = bmesh.new(); loft(bm, body_rings(fwd), cap0=False)
fuselage_F = new_obj('fuselage_F', bm)

# canopy hump (cockpit) with glazed windscreen band
can = [
    (4.60, 0.40, 0.02, 3.00, 2.2),
    (5.30, 0.72, 0.26, 3.16, 2.4),
    (6.30, 0.86, 0.48, 3.22, 2.6),
    (7.60, 0.90, 0.52, 3.22, 2.8),
    (9.00, 0.89, 0.50, 3.22, 2.8),
    (10.4, 0.80, 0.36, 3.28, 2.8),
    (11.8, 0.52, 0.08, 3.42, 2.6),
]
bm = bmesh.new(); loft(bm, body_rings(can, N=32))
cockpit = new_obj('cockpit', bm)
# windscreen + side windows as thin dark glass panels laid on the hump
bm = bmesh.new()
gl = [(4.95, 0.58, 0.17, 3.16, 2.4), (5.45, 0.77, 0.34, 3.18, 2.5), (6.30, 0.865, 0.48, 3.225, 2.6)]
rings = body_rings(gl, N=32)
# keep only the upper half of each ring (z above centre) -> windscreen band
up = [[p for p in r if p.z > gl[k][3] + 0.02] for k, r in enumerate(rings)]
vr = [[bm.verts.new(p + Vector((0, 0, 0.012))) for p in r] for r in up]
for a, b in zip(vr, vr[1:]):
    for i in range(len(a) - 1):
        bm.faces.new((a[i], a[i + 1], b[i + 1], b[i]))
new_obj('canopy_glass', bm, (GLASS,), cockpit)

# bombsight / EO fairing under the nose
bm = bmesh.new(); loft(bm, body_rings([(3.6, 0.05, 0.03, 1.52, 2), (4.3, 0.24, 0.16, 1.48, 2.2), (5.6, 0.26, 0.18, 1.46, 2.2), (6.4, 0.10, 0.05, 1.45, 2)], N=24))
nose_fairing = new_obj('nose_fairing', bm, parent=fuselage_F)

# main fuselage box (d 12.6 - 31.8): wide rounded box over intakes/engines, flat belly
mainf = [
    (12.6, 0.95, 1.15, 2.45, 2.7),
    (14.6, 2.05, 1.17, 2.47, 5.0),
    (19.0, 2.06, 1.17, 2.47, 5.0),
    (24.0, 2.02, 1.16, 2.47, 4.6),
    (26.5, 1.75, 1.10, 2.47, 3.6),
    (28.8, 1.55, 0.98, 2.45, 3.2),
    (30.6, 1.42, 0.80, 2.42, 3.0),
    (31.8, 1.36, 0.66, 2.42, 2.8),
]
bm = bmesh.new(); loft(bm, body_rings(mainf), cap0=False, cap1=True)
fuselage_R = new_obj('fuselage_R', bm)

# intakes: raked box intakes with splitter gap, lip ring, short dark duct
def intake(side):
    s = 1 if side == 'R' else -1
    xo = s * 1.56
    st = [(11.0, 0.50, 0.88, 2.62, 7.0), (12.4, 0.50, 0.98, 2.52, 6.5), (13.8, 0.50, 1.12, 2.43, 6.0), (15.5, 0.50, 1.17, 2.47, 6.0), (18.0, 0.50, 1.17, 2.47, 6.0)]
    bm = bmesh.new()
    outer = body_rings(st, N=40, xoff=xo, rake=0.75)
    vo = loft(bm, outer, cap0=False, cap1=False)
    # lip: inner ring inset 7 cm, duct 1.4 m deep, dark cap
    inner0 = body_rings([(11.0, 0.43, 0.80, 2.62, 7.0)], N=40, xoff=xo, rake=0.75)[0]
    inner1 = [p + Vector((0, -1.4, 0)) for p in inner0]
    vi = [[bm.verts.new(p) for p in r] for r in (inner0, inner1)]
    bridge(bm, vo[0], vi[0])
    bridge(bm, vi[0], vi[1], mat_index=1)
    f = bm.faces.new(vi[1]); f.material_index = 1
    o = new_obj(f'intake_{side}', bm, (SKIN, DARK))
    # splitter plate standing off the fuselage side
    box(f'splitter_{side}', (s * 1.01, Y(12.1), 2.62), (0.03, 2.6, 1.75), (SKIN,), o)
    # visor plate: the intake roof projects ahead of the raked lip
    box(f'visor_{side}', (s * 1.56, Y(10.85), 3.47), (1.0, 0.5, 0.05), (SKIN,), o)
    # auxiliary intake doors (outline panel) on the outer face
    box(f'auxdoor_{side}', (s * 2.055, Y(13.1), 2.85), (0.02, 1.0, 0.6), (MECH,), o)
    return o
intake_L = intake('L'); intake_R = intake('R')

# dorsal spine + fin fillet (rises from d=17 to the fin leading edge)
spine = [
    (16.5, 0.30, 0.02, 3.63, 2.0),
    (19.0, 0.42, 0.18, 3.64, 2.0),
    (22.5, 0.45, 0.50, 3.75, 2.0),
    (25.5, 0.40, 0.95, 3.95, 2.0),
    (27.5, 0.33, 1.20, 4.05, 2.0),
    (30.0, 0.26, 1.10, 3.95, 2.0),
    (32.0, 0.20, 0.80, 3.75, 2.0),
]
bm = bmesh.new(); loft(bm, body_rings(spine, N=24))
spine_o = new_obj('spine', bm, parent=fuselage_R)

# tail cone between/above the nozzles carrying the gun turret (d 28 - 34.0)
tc = [(28.0, 0.62, 0.55, 3.15, 2.2), (31.0, 0.55, 0.52, 3.20, 2.2), (32.6, 0.42, 0.42, 3.22, 2.0), (33.2, 0.26, 0.28, 3.22, 2.0), (33.42, 0.10, 0.10, 3.22, 2.0)]
bm = bmesh.new(); loft(bm, body_rings(tc, N=28))
tail = new_obj('tail', bm, parent=fuselage_R)
cyl('tail_gun', (0, Y(33.0), 3.02), (0, Y(33.75), 3.02), 0.045, mats=(MECH,), parent=tail)

# nozzles (engines 1 = left, 3 = right, AB-4 naming)
nozzles = {}
for side, s in (('L', -1), ('R', 1)):
    num = 1 if side == 'L' else 3
    n = cyl(f'nozzle{num}', (s * 0.74, Y(31.7), 2.40), (s * 0.74, Y(33.0), 2.40), 0.60, 0.54, N=32, mats=(MECH,), caps=False)
    cyl(f'nozzle{num}_inner', (s * 0.74, Y(32.95), 2.40), (s * 0.74, Y(32.4), 2.40), 0.50, 0.46, N=32, mats=(DARK,), parent=n)
    nozzles[side] = n

# ================================================================ FIN + RUDDER (fin top cut 0.70 m)
def fin_le(z): return 24.36 + (z - 3.60) * 1.38      # LE line, sweep ~54 deg
def fin_te(z): return 32.20 + (z - 3.60) * 0.28      # TE swept ~15 deg
FIN_TIP_Z = FIN_TOP - 0.03                            # tip cap thickness on top
RUDDER_FRAC = 0.30
RUDDER_TOP = FIN_TIP_Z - 0.45
# below the rudder (z<4.6) the fin is full chord; build lower part and upper part separately
lower = [(Vector((0, Y(fin_le(z)), z)), Vector((0, -(fin_te(z) - fin_le(z)), 0)), t) for z, t in ((3.60, 0.075), (4.6, 0.07))]
fin = surface('fin', lower, Vector((1, 0, 0)), parent=fuselage_R)
mid = []
for z, t in ((4.6, 0.07), (RUDDER_TOP, 0.06)):
    le = fin_le(z); hinge = le + (fin_te(z) - le) * (1 - RUDDER_FRAC)
    mid.append((Vector((0, Y(le), z)), Vector((0, -(hinge - le), 0)), t / (1 - RUDDER_FRAC) * 0.8))
surface('fin_mid', mid, Vector((1, 0, 0)), parent=fin)
top = [(Vector((0, Y(fin_le(z)), z)), Vector((0, -(fin_te(z) - fin_le(z)), 0)), t) for z, t in ((RUDDER_TOP, 0.06), (FIN_TIP_Z, 0.06))]
surface('fin_tip', top, Vector((1, 0, 0)), parent=fin)
box('fin_tip_cap', (0, Y((fin_le(FIN_TIP_Z) + fin_te(FIN_TIP_Z)) / 2), FIN_TIP_Z + 0.015), (0.16, fin_te(FIN_TIP_Z) - fin_le(FIN_TIP_Z), 0.03), (SKIN,), fin)
# two slender pods stacked at the aft top, sticking out behind the TE (RWR / antenna fairings)
for k, (zp, rp) in enumerate(((FIN_TIP_Z - 0.18, 0.10), (FIN_TIP_Z - 0.42, 0.085))):
    cyl(f'fin_pod{k+1}', (0, Y(fin_te(zp) - 1.4), zp), (0, Y(fin_te(zp) + 0.5), zp), rp, rp * 0.7, N=16, mats=(SKIN,), parent=fin)
# rudder (moving) from hinge line to TE, from z 4.6 up to RUDDER_TOP
rud = []
for z in (4.6, RUDDER_TOP - 0.03):
    le = fin_le(z); hinge = le + (fin_te(z) - le) * (1 - RUDDER_FRAC)
    rud.append((Vector((0, Y(hinge + 0.04), z)), Vector((0, -(fin_te(z) - hinge - 0.04), 0)), 0.09))
h46 = fin_le(4.6) + (fin_te(4.6) - fin_le(4.6)) * (1 - RUDDER_FRAC)
rudder_hinge = empty('rudder_hinge1', Vector((0, Y(h46), 4.6)), kind='SINGLE_ARROW', size=1.5)
rudder = surface('rudder_L_visible', rud, Vector((1, 0, 0)), parent=None)
set_parent_keep(rudder, rudder_hinge)

# ================================================================ TAILPLANES (all-moving)
for side, s in (('L', -1), ('R', 1)):
    hinge = empty(f'elevatorHinge_{side}1', Vector((s * 1.55, Y(29.9), 2.12)), kind='SINGLE_ARROW', size=1.0)
    st = [(Vector((s * 1.1, Y(27.0), 2.12)), Vector((0, -5.5, 0)), 0.045),
          (Vector((s * 1.6, Y(27.4), 2.12)), Vector((0, -5.1, 0)), 0.045),
          (Vector((s * 4.9, Y(31.5), 2.12)), Vector((0, -2.4, 0)), 0.04),
          (Vector((s * 5.15, Y(32.1), 2.12)), Vector((0, -1.75, 0)), 0.04)]
    e = surface(f'elevator_{side}_visible', st, Vector((0, 0, 1)))
    set_parent_keep(e, hinge)

# ================================================================ WING GLOVES (fixed) + OUTER WINGS (swing)
GLOVE_Z = 2.30
def glove_le(x): return 15.9 + (abs(x) - 1.9) * (4.9 / 3.5)
for side, s in (('L', -1), ('R', 1)):
    st = [(Vector((s * 1.85, Y(glove_le(1.85)), GLOVE_Z)), Vector((0, -(24.9 - glove_le(1.85)), 0)), 0.065),
          (Vector((s * 3.6, Y(glove_le(3.6)), GLOVE_Z)), Vector((0, -(24.9 - glove_le(3.6)), 0)), 0.075),
          (Vector((s * 5.35, Y(glove_le(5.35)), GLOVE_Z - 0.02)), Vector((0, -(24.8 - glove_le(5.35)), 0)), 0.085)]
    surface(f'wingroot_{side}', st, Vector((0, 0, 1)), parent=fuselage_R)

wings = {}
for side, s in (('L', -1), ('R', 1)):
    piv = empty(f'wingHinge_{side}a', Vector((s * PIVOT[0], Y(PIVOT[1]), PIVOT[2])), kind='SINGLE_ARROW', size=1.2)
    an = math.radians(WING_ANHEDRAL)
    def wz(x): return PIVOT[2] + (abs(x) - PIVOT[0]) * math.tan(an)
    # outer panel planform at 20 deg sweep (the 0 pose); root extends inboard into the glove slot
    def le(x): return 20.8 + (abs(x) - 5.4) * (2.6 / 8.3)
    def te(x): return 24.7 + (abs(x) - 5.4) * (0.3 / 8.3)
    st = []
    for x, t, lex, tex in ((4.2, 0.075, 20.45, 23.1), (4.9, 0.075, None, None), (5.4, 0.075, None, None), (9.5, 0.065, None, None), (13.55, 0.055, None, None)):
        L_ = le(x) if lex is None else lex; T_ = te(x) if tex is None else tex
        st.append((Vector((s * x, Y(L_), wz(x))), Vector((0, -(T_ - L_), 0)), t))
    w = surface(f'wing1_{side}', st, Vector((0, 0, 1)))
    # rounded tip cap
    cyl(f'wingtip_{side}', (s * 13.62, Y(le(13.6) + 0.15), wz(13.6)), (s * 13.62, Y(te(13.6) - 0.1), wz(13.6)), 0.05, 0.03, N=12, mats=(SKIN,), parent=w)
    set_parent_keep(w, piv)
    piv.rotation_euler.z = -s * math.radians(SWEEP)   # sweep aft
    wings[side] = (piv, w)

# ================================================================ PYLONS (blockout blades)
for side, s in (('L', -1), ('R', 1)):
    box(f'midPylon_{side}', (s * MID_PYLON_X, Y(15.0), BELLY_Z - 0.04), (0.18, 3.4, 0.12), (SKIN,), intake_R if s > 0 else intake_L)
    box(f'glovePylon_{side}', (s * GLOVE_PYLON_X, Y(20.6), GLOVE_Z - 0.32), (0.18, 3.4, 0.36), (SKIN,), fuselage_R)
    empty(f'pylonMount_mid_{side}', (s * MID_PYLON_X, Y(15.0), BELLY_Z - 0.10))
    empty(f'pylonMount_glove_{side}', (s * GLOVE_PYLON_X, Y(20.6), GLOVE_Z - 0.50))

# ================================================================ LANDING GEAR (down; 'gearup' arg folds it)
for side, s in (('L', -1), ('R', 1)):
    trunnion = Vector((s * GEAR_TRUNNION_X, Y(20.7), 1.95))
    gh = empty(f'gearHinge_{side}', trunnion, kind='SINGLE_ARROW', size=0.8)
    bog = Vector((s * GEAR_X, Y(20.9), MAIN_WHEEL_R + 0.30))
    leg = cyl(f'gear_{side}', trunnion, bog + Vector((0, 0, 0.30)), 0.19, 0.16, mats=(MECH,))
    cyl(f'gear_{side}_slider', bog + Vector((0, 0, 0.62)), bog, 0.11, mats=(MECH,), parent=leg)
    # side brace on the inboard side, from the nacelle wall to mid leg
    cyl(f'gear_{side}_brace', (s * 2.08, Y(20.2), 1.75), trunnion.lerp(bog, 0.55) + Vector((-s * 0.12, 0, 0)), 0.065, mats=(MECH,), parent=leg)
    cyl(f'gear_{side}_drag', (s * GEAR_TRUNNION_X, Y(19.4), 1.95), trunnion.lerp(bog, 0.5), 0.06, mats=(MECH,), parent=leg)
    # trunnion fairing under the glove
    box(f'gearFairing_{side}', (s * GEAR_TRUNNION_X, Y(20.5), 2.02), (0.5, 2.4, 0.25), (SKIN,), fuselage_R)
    bogey = cyl(f'bogey_{side}', bog + Vector((0, 1.15, 0)), bog + Vector((0, -1.15, 0)), 0.09, mats=(MECH,))
    for k, dy in (('F', 1.0), ('M', 0.0), ('R', -1.0)):
        cyl(f'axle_{side}{k}', bog + Vector((-0.42, dy, -0.30)), bog + Vector((0.42, dy, -0.30)), 0.05, mats=(MECH,), parent=bogey)
        for ws, wx in (('i', -s), ('o', s)):
            wheel(f'wheel_{side}{k}{ws}', bog + Vector((wx * 0.21, dy, -0.30)), MAIN_WHEEL_R, MAIN_WHEEL_W, parent=bogey)
    set_parent_keep(bogey, leg); set_parent_keep(leg, gh)
    if GEAR_UP:
        gh.rotation_euler.y = math.radians(s * 90)       # fold inward about the fore-aft axis
    # main gear doors on the nacelle underside, hinged at the outer edge (open = hanging)
    if not GEAR_UP:
        box(f'gearDoor_{side}', (s * 1.30, Y(20.9), BELLY_Z - 0.55), (0.03, 2.7, 1.0), (SKIN,))

# nose gear: twin wheels, steerable, retracts aft
ng = empty('gearhinge_F', Vector((0, Y(10.7), 1.85)), kind='SINGLE_ARROW', size=0.8)
nax = Vector((0, Y(10.9), NOSE_WHEEL_R))
nleg = cyl('gear_F', (0, Y(10.7), 1.85), nax + Vector((0, 0, 0.15)), 0.10, 0.09, mats=(MECH,))
cyl('gear_F_axle', nax + Vector((-0.3, 0, 0)), nax + Vector((0.3, 0, 0)), 0.045, parent=nleg)
cyl('gear_F_drag', (0, Y(11.9), 1.6), (0, Y(10.75), 1.0), 0.05, parent=nleg)
for ws, wx in (('L', -0.19), ('R', 0.19)):
    wheel(f'wheel_F{ws}', nax + Vector((wx, 0, 0)), NOSE_WHEEL_R, NOSE_WHEEL_W, parent=nleg)
set_parent_keep(nleg, ng)
for side, s in (('L', -1), ('R', 1)):
    box(f'gearDoor_F{side}', (s * 0.40, Y(10.6), BELLY_Z - 0.45), (0.03, 2.2, 0.85), (SKIN,))

# ================================================================ BAYS (openings for the reused AB-4 doors), shown closed as panel outlines
box('bayDoor_F', (0, Y(15.9), BELLY_Z - 0.005), (2.0, 5.7, 0.02), (MECH,))
box('bayDoor_R', (0, Y(21.85), BELLY_Z - 0.005), (2.0, 5.4, 0.02), (MECH,))

# ================================================================ PIVOT empties for Unity transforms not created above
empty('CoM', (0, Y(19.5), 2.40), kind='SPHERE', size=0.4)
empty('weaponBay_forward', (0, Y(15.9), 1.75)); empty('weaponBay_rear', (0, Y(21.85), 1.75)); empty('weaponBay_combined', (0, Y(18.9), 1.75))
for side, s in (('L', -1), ('R', 1)):
    empty(f'flapHinge_{side}1', (s * 8.0, Y(24.2), 2.20))

# ================================================================ GUIDES
def line(name, pts):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'
    sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
    for p_, (x, y, z) in zip(sp.points, pts): p_.co = (x, y, z, 1)
    o = bpy.data.objects.new(name, cu); G.objects.link(o); o.hide_render = True; return o
line('hangar_door_8m', [(-22.89, Y(-2), 0), (-22.89, Y(-2), 8.0), (22.89, Y(-2), 8.0), (22.89, Y(-2), 0)])
def piledriver(name, x, d_nose, zc):
    o = cyl(name, (x, Y(d_nose), zc), (x, Y(d_nose + PD_LEN), zc), PD_DIA / 2, mats=(DARK,), N=24)
    for c in o.users_collection: c.objects.unlink(o)
    G.objects.link(o)
    for k in range(4):
        a = math.radians(45 + 90 * k)
        f = box(f'{name}_fin{k}', (PD_FIN / 4, 0, 0), (PD_FIN / 2, 0.8, 0.03), (DARK,))
        for c in f.users_collection: c.objects.unlink(f)
        G.objects.link(f)
        f.location = (x, Y(d_nose + PD_LEN - 0.5), zc); f.rotation_euler = (0, -a, 0)
    return o
for side, s in (('L', -1), ('R', 1)):
    piledriver(f'PD_mid_{side}', s * MID_PYLON_X, 11.6, BELLY_Z - 0.10 - PD_DIA / 2)
    piledriver(f'PD_glove_{side}', s * GLOVE_PYLON_X, 17.0, GLOVE_Z - 0.50 - PD_DIA / 2)
G.hide_render = True

bpy.ops.wm.save_as_mainfile(filepath=out)
print('saved', out, 'sweep', SWEEP)
