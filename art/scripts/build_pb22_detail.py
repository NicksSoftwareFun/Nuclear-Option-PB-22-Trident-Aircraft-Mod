"""PB-22 Trident detail exterior (step 2), game metres.
Blender: X right, Y forward (nose tip at Y=+17), Z up, ground Z=0. d = metres aft of the nose, Y = 17 - d.
Usage: blender-python build_pb22_detail.py <out.blend>
Builds every part at rest (wing 20 deg, gear down, surfaces neutral) with its origin on its hinge, then
UV-unwraps and makes *_colmesh collision hulls. Poses are applied afterwards with pb22_pose.py."""
import bpy, bmesh, sys, os, math
from mathutils import Vector, Matrix, Quaternion
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pb22_lib import (Y, MeshBuilder, loft, section, naca_t, cyl, tube, rbox, plate, parent_keep, catmull)
from pb22_shapes import prof_se, prof_rr, Section
import pb22_lib
pb22_lib.LOFT_TOL, pb22_lib.LOFT_MATS = 0.004, (0,)      # simplify skin lofts (SKIN = 0): drop rings and points that add no shape

args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
OUT = args[0] if args else 'pb22_detail.blend'

# ---------------------------------------------------------------- fixed numbers
BELLY_Z = 1.30
FIN_TOP = 7.58                     # trimmed 0.25 m: the fin tip scraped the medium hangar
PIVOT = (4.43, 21.2, 2.30)
WING_ANHEDRAL = -3.0
GLOVE_Z = 2.30
GEAR_T = (2.70, 20.9, 1.68)        # main trunnion (x, d, z): inboard side of the fairing, bogie straight below it
GEAR_X = 2.70                      # bogie centreline (track 5.4 m)
FAIR_Z = 1.28                      # main gear fairing bottom skin = closed door line
OPEN_X = (2.24, 4.53)              # bottom opening of the main gear bay (inboard, outboard edge)
BAY_DD = (19.25, 22.55)            # main gear bay length (d)
DOOR_HX = 4.51                     # main door hinge on the outboard edge of the opening (OPEN_X[1] - 0.02)
ACT_D, BRACE_D = 20.45, 21.25      # retraction actuator plane (ahead of the leg) and side-brace plane (behind it)
BRACE_SWING = 48.9                 # upper side-brace link travel over the full retraction (deg)
MAIN_R, MAIN_W, MAIN_OFF = 0.41, 0.28, 0.21
NOSE_R, NOSE_W = 0.40, 0.26
MID_PYLON_X, GLOVE_PYLON_X = 1.55, 5.45
PD_LEN, PD_DIA, PD_FIN = 6.975, 0.85, 1.31
BAYS = ((15.9, 5.7), (21.85, 5.4))   # (centre d, length), 2.0 m wide each
ROOT_ORIGIN = (0.0, 0.0, 2.85)       # the prefab root (centre fuselage) sits here; Unity (0,0,0)
REAR_SPLIT = 25.5                    # centre fuselage (prefab root) ends, rear fuselage (fuselage_R) begins

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
def coll(name):
    c = bpy.data.collections.new(name); sc.collection.children.link(c); return c
C_MODEL, C_PIV, C_COL, C_PROXY, C_GUIDE, C_TMP, C_FX = (coll(n) for n in ('MODEL', 'PIVOTS', 'COLLISION', 'PROXY_AB4', 'GUIDES', 'TMP', 'FX'))

def mat(name, col, rough=0.5, metal=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*col, 1); b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
    m.diffuse_color = (*col, 1)
    return m
MATS = [mat('PB22_skin', (0.60, 0.61, 0.62)), mat('PB22_mech', (0.42, 0.43, 0.44), 0.45, 0.3),
        mat('PB22_dark', (0.05, 0.05, 0.055), 0.7), mat('PB22_glass', (0.08, 0.10, 0.13), 0.1),
        mat('PB22_tyre', (0.07, 0.07, 0.07), 0.8), mat('PB22_int', (0.16, 0.17, 0.18), 0.6)]
SKIN, MECH, DARK, GLASS, TYRE, INT = range(6)
# colour-coded systems inside the structure (pb22_systems.py)
MATS += [mat('PB22_fuelcell', (0.30, 0.26, 0.19), 0.8), mat('PB22_hyd', (0.78, 0.60, 0.12), 0.5), mat('PB22_wire', (0.58, 0.56, 0.48), 0.7),
         mat('PB22_oxy', (0.17, 0.40, 0.22), 0.5), mat('PB22_fuelline', (0.48, 0.15, 0.09), 0.5), mat('PB22_red', (0.58, 0.08, 0.06), 0.5)]
FUELC, HYD, WIRE, OXY, FUELL, RED = range(6, 12)

# ---------------------------------------------------------------- part registry
class Part:
    def __init__(self, name, origin=None, parent=None, coll=None):
        self.name, self.origin, self.parent = name, origin, parent
        self.mb = MeshBuilder(); self.coll = coll or C_MODEL; self.col = True; self.rot = None
PARTS = {}
def part(name, origin=None, parent=None, coll=None, col=True):
    if name not in PARTS:
        PARTS[name] = Part(name, origin, parent, coll); PARTS[name].col = col
    return PARTS[name]

EMPTIES = {}
def hinge(name, loc, axis=None, up=None, parent=None, size=0.6):
    """Empty whose local X lies along `axis` (hinge line). Poses rotate it about local X (or Z for sweep/rudder)."""
    o = bpy.data.objects.new(name, None); o.empty_display_type = 'ARROWS'; o.empty_display_size = size
    C_PIV.objects.link(o); o.location = Vector(loc)
    if axis is not None:
        x = Vector(axis).normalized(); u = Vector(up or (0, 0, 1))
        y = u.cross(x).normalized(); z = x.cross(y)
        o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = Matrix((x, y, z)).transposed().to_quaternion()
    else:
        o.rotation_mode = 'QUATERNION'
    o['rest_q'] = list(o.rotation_quaternion)
    EMPTIES[name] = (o, parent)
    return o

def pair(base, loc, axis=None, parent=None, up=None, size=0.5):
    """AB-4 hinge pattern: <base>1 sets the axis orientation, <base>2 (same orientation, child of 1) is what rotates."""
    hinge(base + '1', loc, axis=axis, up=up, parent=parent, size=size)
    hinge(base + '2', loc, axis=axis, up=up, parent=base + '1', size=size * 0.8)
    return base + '2'

def mirror_x(v): return Vector((-v.x, v.y, v.z))

# ================================================================ BODY (nose to nacelle box)
BODY = Section([
    (0.00, 2.42, 0, prof_se(0.035, 0.025, 2.0)),
    (0.35, 2.40, 0, prof_se(0.17, 0.12, 2.0)),
    (1.00, 2.37, 0, prof_se(0.32, 0.245, 2.1)),
    (1.80, 2.35, 0, prof_se(0.46, 0.37, 2.15)),
    (2.70, 2.34, 0, prof_se(0.58, 0.51, 2.25)),
    (3.40, 2.33, 0, prof_se(0.67, 0.62, 2.3)),
    (4.60, 2.33, 0, prof_se(0.80, 0.80, 2.3)),
    (6.00, 2.33, 0, prof_se(0.91, 0.94, 2.4)),
    (7.50, 2.34, 0, prof_se(0.95, 1.00, 2.5)),
    (9.50, 2.40, 0, prof_se(0.96, 1.10, 2.6)),
    # between the intakes the body widens gradually (0.96 -> 1.03 half width) to halve the open slot to the intake walls
    (10.4, 2.43, 0, prof_se(0.985, 1.13, 2.65)),
    (11.5, 2.45, 0, prof_se(1.03, 1.15, 2.7)),
    (12.6, 2.45, 0, prof_se(1.03, 1.15, 2.7)),
    (14.6, 2.47, 0, prof_rr(2.06, 1.17, 0.34, 0.30)),
    (19.0, 2.47, 0, prof_rr(2.06, 1.17, 0.34, 0.30)),
    (24.0, 2.47, 0, prof_rr(2.02, 1.16, 0.40, 0.34)),
    (26.5, 2.47, 0, prof_rr(1.75, 1.10, 0.55, 0.45)),
    (28.8, 2.45, 0, prof_rr(1.55, 0.98, 0.62, 0.52)),
    (30.6, 2.42, 0, prof_rr(1.42, 0.80, 0.62, 0.52)),
    (31.8, 2.42, 0, prof_rr(1.36, 0.66, 0.56, 0.46)),
], 96)
for name, d0, d1 in (('nose', 0.0, 3.4), ('fuselage', 12.6, REAR_SPLIT), ('fuselage_R', REAR_SPLIT, 31.8)):
    p = part(name, origin=ROOT_ORIGIN if name == 'fuselage' else None, parent={'nose': 'cockpit', 'fuselage_R': 'fuselage'}.get(name))
    rings = BODY.rings(d0, d1, 0.2 if d0 < 3.4 else 0.3)
    if d0 == 0.0: rings[0] = [Vector((0, Y(0), 2.30))] * len(rings[0])
    loft(p.mb, rings, cap0=d0 >= 8.0, cap1=d1 >= 12.6, mat=SKIN)
bmesh.ops.remove_doubles(PARTS['nose'].mb.bm, verts=PARTS['nose'].mb.bm.verts, dist=1e-5)

exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pb22_cabin_build.py')).read())

# ---------------------------------------------------------------- booleans (bays, wheel wells) on the body parts
def cutter(name, xmin, xmax, d0, d1, zmin, zmax):
    me = bpy.data.meshes.new(name); bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector(((xmin + xmax) / 2 + v.co.x * (xmax - xmin), Y((d0 + d1) / 2) + v.co.y * (d1 - d0), (zmin + zmax) / 2 + v.co.z * (zmax - zmin)))
    bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); C_TMP.objects.link(o); return o

def apply_cuts(p, cutters):
    me = bpy.data.meshes.new(p.name + '_tmp'); p.mb.bm.to_mesh(me)
    for m in MATS: me.materials.append(m)
    o = bpy.data.objects.new(p.name + '_tmp', me); C_TMP.objects.link(o)
    for c in cutters:
        md = o.modifiers.new('cut', 'BOOLEAN'); md.operation = 'DIFFERENCE'; md.solver = 'EXACT'; md.object = c
    dg = bpy.context.evaluated_depsgraph_get()
    res = bpy.data.meshes.new_from_object(o.evaluated_get(dg))
    p.mb.bm.free(); p.mb.bm = bmesh.new(); p.mb.bm.from_mesh(res)
    p.mb.uv = p.mb.bm.loops.layers.uv.get('UVMap') or p.mb.bm.loops.layers.uv.new('UVMap')
    # faces that came from the cutter (well walls) -> mech material, flat shaded
    for f in p.mb.bm.faces:
        if f.material_index >= len(MATS): f.material_index = MECH
    bpy.data.objects.remove(o); bpy.data.meshes.remove(me); bpy.data.meshes.remove(res)

# nose wheel well (wheels fold aft into d 10.2-12.55)
cuts_F = [cutter('cut_nosewell', -0.42, 0.42, 10.15, 12.58, 0.5, 2.35)]
# weapon bays (2.0 m wide): one open bay under both door pairs (no bulkhead), so a combined-bay load fits across the door split
# (the main gear now stows outboard in the glove fairings, so the fuselage keeps no wheel wells)
cuts_R = [cutter('cut_bay', -1.0, 1.0, BAYS[0][0] - BAYS[0][1] / 2, BAYS[1][0] + BAYS[1][1] / 2, 0.5, 2.80)]   # roof 2.80: room for the AGM-99 x6 stack
for c in cuts_F + cuts_R:
    c.data.materials.append(MATS[MECH])
apply_cuts(PARTS['fuselage_F'], cuts_F)
apply_cuts(PARTS['fuselage'], cuts_R)
def drop_cap(p, d):
    yy = Y(d)
    bad = [f for f in p.mb.bm.faces if len(f.verts) > 8 and all(abs(v.co.y - yy) < 1e-4 for v in f.verts)]
    bmesh.ops.delete(p.mb.bm, geom=bad, context='FACES_ONLY')
drop_cap(PARTS['fuselage_F'], CAB_SPLIT[1]); drop_cap(PARTS['fuselage_F'], 12.6); drop_cap(PARTS['fuselage'], 12.6)
drop_cap(PARTS['fuselage'], REAR_SPLIT); drop_cap(PARTS['fuselage_R'], REAR_SPLIT)

# ---------------------------------------------------------------- body extras
def slab(mb, sec, d0, d1, th0, th1, off0, off1, mat, nd=6, nt=6, dfun=None):
    """Closed thin panel following a Section surface (windows, hatches, vents)."""
    grid = lambda off: [[sec.point(d0 + (d1 - d0) * i / nd, th0 + (th1 - th0) * j / nt, off) for j in range(nt + 1)] for i in range(nd + 1)]
    lo, hi = grid(off0), grid(off1)
    vl = [mb.verts(r) for r in lo]; vh = [mb.verts(r) for r in hi]
    for i in range(nd):
        for j in range(nt):
            mb.face((vh[i][j], vh[i + 1][j], vh[i + 1][j + 1], vh[i][j + 1]), None, mat)
            mb.face((vl[i][j + 1], vl[i + 1][j + 1], vl[i + 1][j], vl[i][j]), None, mat)
    edge = [vh[i][0] for i in range(nd + 1)] + [vh[nd][j] for j in range(1, nt + 1)] + [vh[i][nt] for i in range(nd - 1, -1, -1)] + [vh[0][j] for j in range(nt - 1, 0, -1)]
    edgel = [vl[i][0] for i in range(nd + 1)] + [vl[nd][j] for j in range(1, nt + 1)] + [vl[i][nt] for i in range(nd - 1, -1, -1)] + [vl[0][j] for j in range(nt - 1, 0, -1)]
    n = len(edge)
    for k in range(n):
        mb.face((edgel[k], edgel[(k + 1) % n], edge[(k + 1) % n], edge[k]), None, mat, False)

def blade(mb, root_le, root_c, tip_le, tip_c, t, mat=SKIN, axis=Vector((1, 0, 0))):
    """Antenna blade / small fin: two aerofoil stations."""
    rings = [[le + Vector((0, -c, 0)) * u + axis * (v * c) for u, v in section(t, 0, 1, 8)] for le, c in ((root_le, root_c), (tip_le, tip_c))]
    loft(mb, rings, True, True, mat, smooth=False)

ffF = part('fuselage_FF').mb
ckM = part("cockpit").mb
D2R = math.radians
# EO/IR sensor fairing on the belly just ahead of the nose-gear doors (modern successor to the TV bombsight), with a
# forward-facing window angled down
EO = Section([(8.80, 1.40, 0, prof_rr(0.06, 0.05, 0.03, 0.03)), (9.15, 1.34, 0, prof_rr(0.21, 0.10, 0.05, 0.06)),
              (9.70, 1.33, 0, prof_rr(0.23, 0.11, 0.05, 0.06)), (10.05, 1.36, 0, prof_rr(0.16, 0.07, 0.04, 0.05))], 32)
loft(ffF, EO.rings(8.80, 10.05, 0.12), True, True, SKIN)
plate(ffF, [Vector((-0.13, Y(9.02), 1.31)), Vector((0.13, Y(9.02), 1.31)), Vector((0.13, Y(9.12), 1.40)), Vector((-0.13, Y(9.12), 1.40))], 0.012, (0, 0.7, -0.6), GLASS)
# blade antennas on the forward fuselage
blade(part('fuselage_F').mb, Vector((0, Y(11.9), 3.50)), 0.55, Vector((0, Y(12.35), 3.90)), 0.28, 0.12)
blade(ckM, Vector((0, Y(7.0), 1.47)), 0.35, Vector((0, Y(7.3), 1.20)), 0.18, 0.12)

fC = part('fuselage').mb; fR = part('fuselage_R').mb
# dorsal spine: a narrow straight ramp that runs from behind the cockpit into the fin leading edge, like a thick fin root
def prof_dorsal(Wb, H, Wt, Dn):
    """Fin-like section: half width Wb at the base easing to Wt at height H (rounded top), shallow ellipse below."""
    def inside(x, z):
        if z < 0: return (x / Wb) ** 2 + (z / Dn) ** 2 <= 1.0
        if z > H + Wt: return False
        if z > H: return x * x + (z - H) ** 2 <= Wt * Wt
        return abs(x) <= Wt + (Wb - Wt) * (1.0 - z / H) ** 1.6
    def f(th):
        c, sn = math.cos(th), math.sin(th)
        lo, hi = 0.0, max(Wb, H + Wt, Dn) * 1.5
        for _ in range(30):
            mid = (lo + hi) / 2
            if inside(mid * c, mid * sn): lo = mid
            else: hi = mid
        return lo
    return f
SPINE_Z = 3.58
# dorsal fillet: a low spine that runs evenly aft and curves up into the fin leading edge, meeting it tangentially at the
# fin's attachment face (z = FIN_ROOT_Z). Aft of d 20 the spine IS the lower fin: its section is the fin's own airfoil,
# lofted from a leading edge that follows the fillet line, so fin and spine read as one piece with no seam or step.
FIN_ROOT_Z = 4.60                                             # = RUDDER_BOT; the fin part starts here
_SA, _SB, _SM = 24.78, 25.74, 0.06                             # parabola start, fin LE at FIN_ROOT_Z, slope of the straight run
def spine_top(d):
    u = max(d - _SA, 0.0)
    return 3.64 + _SM * (d - 15.0) + 0.344 * u * u
def spine_le(z):
    """d of the fillet leading edge at height z (inverse of spine_top)."""
    lo, hi = 15.0, _SB
    if z <= 3.64: return 15.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if spine_top(mid) < z: lo = mid
        else: hi = mid
    return lo
def _fin_le(z): return 24.36 + (z - 3.60) * 1.38
def _fin_te(z): return 32.20 + (z - 3.60) * 0.28
def _fin_t(z): return 0.075 + (0.07 - 0.075) * (z - 3.40) / (FIN_ROOT_Z - 3.40)
def fin_half(d, z):
    """Half thickness of the (spine + lower fin) body at station d and height z."""
    le = spine_le(z); te = _fin_te(z)
    if d < le or d > te: return 0.0
    T = _fin_t(z) * (te - _fin_le(z))                             # the fin's real thickness at this height
    x = (d - le) / (te - le)
    return naca_t(x, 1.0) * T
# the fin-spine is lofted from horizontal airfoil slices (like the fin): each slice runs from the fillet leading edge to
# the fin trailing edge with the fin's real thickness, from inside the fuselage deck (z 3.30) up to FIN_ROOT_Z, where its
# top slice is the fin part's root section. Split at REAR_SPLIT between the centre and rear fuselage parts.
FS_Z = [3.30, 3.45, 3.56, 3.62] + [3.64 + (FIN_ROOT_Z - 3.64) * k / 30 for k in range(31)]
def fs_slice(z, c0, c1, n=24):
    le, te = spine_le(z), _fin_te(z)
    ch = te - le
    t = _fin_t(z) * (te - _fin_le(z)) / ch
    xs = [c0 + (c1 - c0) * 0.5 * (1 - math.cos(math.pi * i / n)) for i in range(n + 1)]
    uv = [(x, naca_t(x, t)) for x in xs] + [(x, -naca_t(x, t)) for x in reversed(xs)]
    return [Vector((0, Y(le + ch * u), z)) + X_ * (v * ch) for u, v in uv]
X_ = Vector((1, 0, 0))
def _csplit(z):
    le, te = spine_le(z), _fin_te(z)
    return (REAR_SPLIT - le) / (te - le)
_fwd = [z for z in FS_Z if _csplit(z) > 0.01]
loft(fC, [fs_slice(z, 0.0, min(_csplit(z), 1.0)) for z in _fwd], True, True, SKIN)
loft(fR, [fs_slice(z, max(_csplit(z), 0.0) if _csplit(z) > 0.01 else 0.0, 1.0) for z in FS_Z], True, True, SKIN)
# TA-6 APU exhaust and intake grilles on the fillet (left side) and blade antennas
def spine_x(d, z, side):
    """Point on the fin-spine flank at height z (side +1 right, -1 left)."""
    return Vector((side * fin_half(d, z), Y(d), z))
# fin-root air intake on the left flank (cooling air for the tail avionics and the APU): a raised scoop with a dark mouth
for d0, d1 in ((25.55, 26.25),):
    pa, pb = spine_x(d0, 4.28, -1), spine_x(d1, 4.28, -1)
    xin = (pa.x + pb.x) / 2
    # faired half-pod sunk into the flank: blunt raked mouth at the front, tapering to nothing 0.6 m aft
    SC = Section([(d0, 4.28, xin - 0.01, prof_se(0.06, 0.15, 2.6)), (d0 + 0.25, 4.28, xin - 0.01, prof_se(0.065, 0.155, 2.6)),
                  (d1, 4.27, xin + 0.005, prof_se(0.04, 0.12, 2.4)), (d1 + 0.35, 4.26, xin + 0.03, prof_se(0.006, 0.03, 2.0))], 32)
    loft(fR, SC.rings(d0, d1 + 0.35, 0.1), False, True, SKIN)
    mouth = SC.rings(d0, d0 + 0.01, 0.01)[0]
    cen = sum(mouth, Vector()) / len(mouth)
    fR_v = fR.verts([cen + (p - cen) * 0.97 + Vector((0, -0.04, 0)) for p in mouth])   # dark mouth 4 cm inside
    fR.face(list(reversed(fR_v)), None, DARK, False)
# APU exhaust on the right flank
_ap = [spine_x(dd, zz, 1) + Vector((0.004, 0, 0)) for dd, zz in ((25.95, 3.92), (26.30, 3.92), (26.30, 4.06), (25.95, 4.06))]
plate(fR, _ap, 0.006, (1, 0, 0), DARK)
# spine antennas (the SATCOM blister is gone, per the owner)
blade(fC, Vector((0, Y(15.4), spine_top(15.4) - 0.02)), 0.5, Vector((0, Y(15.8), spine_top(15.4) + 0.38)), 0.26, 0.12)
blade(fC, Vector((0, Y(20.0), spine_top(20.0) - 0.02)), 0.5, Vector((0, Y(20.4), spine_top(20.0) + 0.32)), 0.26, 0.12)   # sits on the lowered spine
blade(fR, Vector((0, Y(27.5), BELLY_Z + 0.35)), 0.5, Vector((0, Y(27.9), BELLY_Z + 0.05)), 0.24, 0.12)
# tailplane pivot spindle fairings
for s in (1, -1):
    SPF = Section([(29.1, 2.12, s * 1.43, prof_se(0.04, 0.05, 2)), (29.6, 2.12, s * 1.44, prof_se(0.12, 0.17, 2)),
                   (30.4, 2.12, s * 1.42, prof_se(0.12, 0.17, 2)), (31.2, 2.12, s * 1.37, prof_se(0.03, 0.04, 2))], 20)
    loft(fR, SPF.rings(29.1, 31.2, 0.25), True, True, SKIN)

# ================================================================ INTAKES (sharp-edged box scoops that round off into the nacelle box)
RAKE = 2.70                          # lip rake (m of d from the top lip back to the bottom lip): the top plate leads, Tu-22M3 style
LIP_D0 = 10.0                        # d of the top lip (the forward-most point of the intake)
IN_ZT, IN_ZB = 3.64, 1.30            # top and bottom of the intake box (the nacelle box); every station uses them
LIP_ZT = 3.15                        # the top lip after the scoop droop
SCOOP_END = 12.7                     # the scoop (top droop, outboard cant, sharp corners) lives ahead of this station; flat and uniform behind it
IN_CANT = 0.0                        # outboard cant of the scoop top (m across the width); off: it left a step at the tip in side view
SCOOP_BEND = 0.12                    # the bend from the flat top into the slope is a soft curve over 2 * this share of the scoop length
def scoop_f(pos):
    x = min(max((SCOOP_END - pos) / (SCOOP_END - LIP_D0), 0.0), 1.0); b = SCOOP_BEND
    return (x * x / (4 * b) if x < 2 * b else x - b) / (1 - b)
def scoop_z(z, pos):
    """the scoop droop: the top line falls in a straight line from the nacelle top to LIP_ZT at the lip; the bottom stays put"""
    return z - (IN_ZT - LIP_ZT) * scoop_f(pos) * max(z - IN_ZB, 0.0) / (IN_ZT - IN_ZB)
def lip_pos(z):
    """station of the raked lip at raw height z, so that after the droop the lip edge is a straight line"""
    pos = LIP_D0
    for _ in range(8):
        pos = LIP_D0 + RAKE * (LIP_ZT - scoop_z(z, pos)) / (LIP_ZT - IN_ZB)
    return pos
class CantSection(Section):
    """intake section that gets the scoop droop and outboard cant by true station (so the slope is one straight, even line)"""
    def __init__(self, stations, N, s):
        super().__init__(stations, N); self.s = s
    def _shape(self, v, xc):
        pos = 17.0 - v.y; f = scoop_f(pos)
        u = min(max((self.s * (v.x - xc) / 0.5 + 1.0) * 0.5, 0.0), 1.0)
        w = min(max((v.z - 2.47) / 1.17, 0.0), 1.0)
        v.z = scoop_z(v.z, pos) - IN_CANT * f * u * w
        return v
    def point(self, d, th, off=0.0, dfun=None):
        return self._shape(super().point(d, th, off, dfun), self.params(d)[1])
    def ring(self, d, off=0.0, dfun=None):
        xc = self.params(d)[1]
        return [self._shape(v, xc) for v in super().ring(d, off, dfun)]
def rake_d(d0, ztop, zbot):
    return lambda d, z: lip_pos(z) if abs(d - d0) < 1e-6 else d
def intake_inner(xo):
    return CantSection([(11.0, 2.465, xo, prof_rr(0.485, 1.155, 0.02, 0.285)), (11.6, 2.465, xo, prof_rr(0.46, 1.135, 0.06, 0.27)),
                        (13.4, 2.465, xo, prof_rr(0.44, 1.135, 0.30, 0.27))], 64, 1 if xo > 0 else -1)
IN_W = {11.0: 1.0, 11.6: 0.8, 13.4: 0.12}   # how much of the lip rake each inner duct ring keeps (fades out down the duct)
def inner_d(d, z):
    return d + (lip_pos(z) - 11.0 + 0.02) * IN_W[round(d, 1)]
for side, s in (('R', 1), ('L', -1)):
    xo = s * 1.56
    # the bottom (1.30, corner 0.30) is the same at every station; only the top dips and sharpens inside the scoop
    IN = CantSection([(11.0, 2.47, xo, prof_rr(0.50, 1.17, 0.03, 0.30)), (12.0, 2.47, xo, prof_rr(0.50, 1.17, 0.10, 0.30)),
                      (13.1, 2.47, xo, prof_rr(0.50, 1.17, 0.34, 0.30)), (13.8, 2.47, xo, prof_rr(0.50, 1.17, 0.34, 0.30)),
                      (14.6, 2.47, xo, prof_rr(0.50, 1.17, 0.34, 0.30)),
                      (15.4, 2.47, xo, prof_rr(0.50, 1.17, 0.34, 0.30))], 64, s)
    INNER = intake_inner(xo)
    dfun = rake_d(11.0, IN_ZT, IN_ZB)
    p = part(f'intake_{side}')
    # the rake fades out along the intake so no ring sits ahead of the raked lip (no folded skin)
    dfo = lambda d, z: dfun(11.0, z) + (d - 11.0) * (14.6 - dfun(11.0, z)) / (14.6 - 11.0)
    outer = IN.rings(11.0, 14.6, 0.2, dfun=dfo)
    class OnSkin:
        """IN as it actually lies after the rake shear: point(d) lands on the skin at true station d (for panels on the flank)"""
        def point(self, d, th, off=0.0):
            p_ = d
            for _ in range(4):
                r_, zc_, xc_ = IN.radius(p_, th); z_ = zc_ + r_ * math.sin(th); dl = dfun(11.0, z_)
                p_ = 11.0 + (d - dl) * (14.6 - 11.0) / (14.6 - dl)
            return IN.point(p_, th, off, dfun=dfo)
    SK = OnSkin()
    vo = loft(p.mb, outer, cap0=False, cap1=False, mat=SKIN, simplify=False)   # its ring 0 is stitched to the lip below
    lip_i = INNER.ring(11.0, dfun=lambda d, z: inner_d(11.0, z))
    lip_m = [a.lerp(b, 0.5) for a, b in zip(outer[0], lip_i)]
    duct = [INNER.ring(d, dfun=lambda dd, z, d=d: inner_d(d, z)) for d in (11.0, 11.6, 13.4)]
    vm = p.mb.verts(lip_m); vi = [p.mb.verts(r) for r in duct]
    N = len(vm)
    for i in range(N):
        j = (i + 1) % N
        p.mb.face((vo[0][i], vo[0][j], vm[j], vm[i]), None, SKIN)
        p.mb.face((vm[i], vm[j], vi[0][j], vi[0][i]), None, SKIN)
        for a, b in zip(vi, vi[1:]):
            p.mb.face((a[i], a[j], b[j], b[i]), None, INT)
    # the duct continues past d 13.4 to the engine face (pb22_structure.py), so the end stays open
    # variable ramp: a dark panel set back along the inner (fuselage-side) duct wall
    xi = s * (1.56 - 0.45)
    plate(p.mb, [Vector((xi + s * 0.01, Y(13.3), 1.75)), Vector((xi + s * 0.01, Y(13.3), 3.35)), Vector((xi + s * 0.10, Y(14.1), 3.35)), Vector((xi + s * 0.10, Y(14.1), 1.75))], 0.02, (1, 0, 0), DARK)
    # formation light strip low on the outer flank, below the relief doors (its own part: the game lights it green)
    sl = part(f'slimelight_I{side}', parent=f'intake_{side}', col=False)
    slab(sl.mb, SK, 13.05, 14.35, D2R(-12) if s > 0 else math.pi - D2R(-3), D2R(-3) if s > 0 else math.pi - D2R(-12), 0.002, 0.008, DARK, 6, 2)
    # auxiliary (suction relief) doors: two rows of three high on the outer flank
    for k in range(3):
        d0 = 12.85 + k * 0.50
        for a0, a1 in ((32, 47), (52, 67)):
            slab(p.mb, SK, d0, d0 + 0.40, D2R(a0) if s > 0 else math.pi - D2R(a1), D2R(a1) if s > 0 else math.pi - D2R(a0), 0.002, 0.008, MECH, 2, 3)

# ================================================================ TAIL: cone, radar, turret, fin, RWR pods
tl = part('tail', parent='fuselage_R')
# tail cone ending in the tail-warning radar radome (the gun station is gone, B-52H style)
TC = Section([(28.0, 3.15, 0, prof_se(0.62, 0.55, 2.2)), (31.0, 3.20, 0, prof_se(0.56, 0.52, 2.2)), (32.4, 3.24, 0, prof_se(0.46, 0.46, 2.1)),
              (33.00, 3.27, 0, prof_se(0.38, 0.39, 2.0)), (33.35, 3.28, 0, prof_se(0.27, 0.28, 2.0)), (33.55, 3.28, 0, prof_se(0.14, 0.15, 2.0)),
              (33.62, 3.28, 0, prof_se(0.02, 0.02, 2.0))], 56)
loft(tl.mb, TC.rings(28.0, 33.62, 0.10), True, True, SKIN)
# chin fairing where the turret was: towed-decoy launcher with two ports and a vented cover strip on its flat aft face
CH = Section([(31.9, 3.05, 0, prof_rr(0.04, 0.03, 0.02)), (32.35, 3.00, 0, prof_rr(0.22, 0.13, 0.08, 0.10)),
              (32.80, 2.98, 0, prof_rr(0.24, 0.14, 0.08, 0.11)), (33.08, 2.98, 0, prof_rr(0.23, 0.13, 0.08, 0.10))], 40)
loft(tl.mb, CH.rings(31.9, 33.08, 0.1), True, True, SKIN)
for x in (-0.10, 0.10):
    cyl(tl.mb, (x, Y(33.0), 2.95), (x, Y(33.095), 2.95), 0.065, N=16, mat=DARK)
rbox(tl.mb, (0, Y(33.085), 3.06), (0.30, 0.02, 0.05), 0.005, DARK)
# side jammer antenna canoes at the fin base
for s_ in (1, -1):
    CN = Section([(30.2, 3.30, s_ * 0.585, prof_se(0.01, 0.02, 2)), (30.8, 3.30, s_ * 0.585, prof_se(0.06, 0.12, 2.4)),
                  (32.3, 3.30, s_ * 0.585, prof_se(0.07, 0.13, 2.6)), (32.95, 3.30, s_ * 0.55, prof_se(0.065, 0.12, 2.6)),
                  (32.99, 3.30, s_ * 0.55, prof_se(0.05, 0.10, 2.6))], 32)
    loft(tl.mb, CN.rings(30.2, 32.99, 0.15), True, True, SKIN)
# fin-root aft bullet: twin brake-chute bay with a rear-sector ESM cap
BU = Section([(31.3, 3.86, 0, prof_se(0.02, 0.02, 2)), (31.8, 3.86, 0, prof_se(0.14, 0.15, 2)), (32.9, 3.86, 0, prof_se(0.16, 0.16, 2)),
              (33.1, 3.86, 0, prof_se(0.16, 0.16, 2)), (33.25, 3.86, 0, prof_se(0.13, 0.13, 2)), (33.34, 3.86, 0, prof_se(0.02, 0.02, 2))], 32)
loft(tl.mb, BU.rings(31.3, 33.34, 0.12), True, True, SKIN)
for s_ in (1, -1):
    dome(fR, (s_ * 0.60, Y(26.5), 1.39), (s_ * 0.35, -0.2, -1.0), 0.055)
for s_ in (1, -1):
    dome(tl.mb, (s_ * 0.36, Y(31.6), 3.58), (s_ * 0.6, -0.5, 0.62), 0.06)
def fin_le(z): return 24.36 + (z - 3.60) * 1.38
def fin_te(z): return 32.20 + (z - 3.60) * 0.28
FIN_TIP_Z = FIN_TOP - 0.03
RUDDER_FRAC = 0.30
RUDDER_TOP = FIN_TIP_Z - 0.45
RUDDER_BOT = FIN_ROOT_Z
X = Vector((1, 0, 0))
def fin_station(z, c0, c1, t):
    le, te = fin_le(z), fin_te(z)
    return (Vector((0, Y(le), z)), Vector((0, -(te - le), 0)), t)
def fsurf(mb, zs, c0, c1, mat=SKIN, n=24):
    rings = []
    for z, t in zs:
        le, ch, _ = fin_station(z, 0, 1, t)
        rings.append([le + ch * u + X * (v * ch.length) for u, v in section(t, c0, c1, n)])
    loft(mb, rings, True, True, mat)
fin = part('rudder_L', parent='tail')
fsurf(fin.mb, [(RUDDER_BOT, 0.07), (RUDDER_TOP, 0.06)], 0, 1 - RUDDER_FRAC - 0.006)
fsurf(fin.mb, [(RUDDER_TOP, 0.06), (FIN_TIP_Z, 0.055)], 0, 1)
le_t, te_t = fin_le(FIN_TIP_Z), fin_te(FIN_TIP_Z)
rbox(fin.mb, (0, Y((le_t + te_t) / 2), FIN_TIP_Z + 0.012), (0.15, te_t - le_t - 0.1, 0.03), 0.01, SKIN)
# two slender pointed RWR pods at the fin tip, 1.3 m long, 0.5 m past the trailing edge
for zp, rp, ln in ((FIN_TIP_Z - 0.10, 0.075, 1.35), (FIN_TIP_Z - 0.34, 0.065, 1.2)):
    d1 = fin_te(zp) + 0.5; d0 = d1 - ln
    pts = [(0, Y(d0 + ln * f), zp) for f in (0.0, 0.04, 0.15, 0.35, 0.7, 0.9, 1.0)]
    tube(fin.mb, pts, [0.0, rp * 0.45, rp * 0.85, rp, rp, rp * 0.7, 0.0], N=14, mat=SKIN, caps=False)
# formation light strips on both faces of the fin (own parts, lit green by the game)
for nm, sg in (('slimelight_FinR', 1), ('slimelight_FinL', -1)):
    sp = part(nm, parent='rudder_L', col=False)
    us = [0.32 + 0.30 * k / 8 for k in range(9)]           # centred in the fin panels, over the painted strip (2026-10-18)
    def _fp(z, u, off):
        t = 0.07 + (0.06 - 0.07) * (z - RUDDER_BOT) / (RUDDER_TOP - RUDDER_BOT)
        le, te = fin_le(z), fin_te(z); ch = te - le
        return Vector((sg * (naca_t(u, t) * ch + off), Y(le + ch * u), z))
    # four rows round the strip's cross-section: (z0, in) (z0, out) (z1, out) (z1, in), lofted along the chord and capped
    rows = [[_fp(z, u, off) for u in us] for z, off in ((6.55, 0.001), (6.55, 0.006), (6.65, 0.006), (6.65, 0.001))]
    loft(sp.mb, [[rows[r][k] for r in range(4)] for k in range(len(us))], True, True, DARK)
# rudder (moving) on its own hinge line
hb, ht = (lambda z: fin_le(z) + (fin_te(z) - fin_le(z)) * (1 - RUDDER_FRAC))(RUDDER_BOT), (lambda z: fin_le(z) + (fin_te(z) - fin_le(z)) * (1 - RUDDER_FRAC))(RUDDER_TOP)
pb, pt = Vector((0, Y(hb), RUDDER_BOT)), Vector((0, Y(ht), RUDDER_TOP))
rh = pair('rudderHinge_L', pb, axis=(pt - pb), up=(0, -1, 0), parent='rudder_L', size=1.0)
rd = part('rudder_L_visible', origin=pb, parent=rh)
fsurf(rd.mb, [(RUDDER_BOT + 0.01, 0.07), (RUDDER_TOP - 0.02, 0.06)], 1 - RUDDER_FRAC + 0.004, 1.0)
# dark web on the centre plane across the fin/rudder gap, so the gap does not show the sky
_hc = lambda z, f: fin_le(z) + (fin_te(z) - fin_le(z)) * (1 - RUDDER_FRAC + f)
plate(fin.mb, [Vector((0, Y(_hc(RUDDER_BOT, -0.02)), RUDDER_BOT)), Vector((0, Y(_hc(RUDDER_BOT, 0.012)), RUDDER_BOT)),
               Vector((0, Y(_hc(RUDDER_TOP, 0.012)), RUDDER_TOP)), Vector((0, Y(_hc(RUDDER_TOP, -0.02)), RUDDER_TOP))], 0.012, (1, 0, 0), DARK)
for zd in (5.2, 6.0, 6.8):
    cyl(rd.mb, (0, Y(fin_te(zd) - 0.02), zd), (0, Y(fin_te(zd) + 0.12), zd - 0.02), 0.012, 0.007, N=6, mat=MECH)

# ================================================================ NOZZLES (engine 1 left, engine 3 right; AB-4 numbering)
for side, s, num in (('L', -1, 1), ('R', 1, 3)):
    xc, zc = s * 0.74, 2.40
    hinge(f'engines_{side}', (xc, Y(26.0), zc), parent='fuselage_R', size=0.4)
    hinge(f'engine{num}', (xc, Y(26.0), zc), parent=f'engines_{side}', size=0.4)
    hinge(f'nozzles_{side}', (xc, Y(31.6), zc), parent=f'engines_{side}', size=0.4)
    nz = part(f'nozzle{num}', origin=(xc, Y(31.6), zc), parent=f'nozzles_{side}')
    NZ = Section([(31.4, zc, xc, prof_se(0.61, 0.61, 2)), (32.0, zc, xc, prof_se(0.60, 0.60, 2)), (32.55, zc, xc, prof_se(0.575, 0.575, 2))], 40)
    loft(nz.mb, NZ.rings(31.4, 32.55, 0.3), False, False, MECH)
    # 16 convergent petals with small gaps
    for k in range(16):
        a0 = 2 * math.pi * (k + 0.06) / 16; a1 = 2 * math.pi * (k + 0.94) / 16
        arc = lambda r, d: [Vector((xc + r * math.cos(a0 + (a1 - a0) * j / 3), Y(d), zc + r * math.sin(a0 + (a1 - a0) * j / 3))) for j in range(4)]
        rings = []
        for d, r in ((32.50, 0.575), (33.15, 0.515)):
            o, i = arc(r, d), arc(r - 0.03, d)
            rings.append(o + list(reversed(i)))
        loft(nz.mb, rings, True, True, MECH, smooth=False)
    # liner and afterburner flame holders
    cyl(nz.mb, (xc, Y(33.10), zc), (xc, Y(31.8), zc), 0.50, 0.47, N=40, caps=False, mat=DARK)
    for d, r in ((32.1, 0.36), (32.3, 0.22)):
        tube(nz.mb, [(xc + r * math.cos(2 * math.pi * k / 24), Y(d), zc + r * math.sin(2 * math.pi * k / 24)) for k in range(25)], 0.025, N=6, mat=DARK, caps=False)
    cyl(nz.mb, (xc, Y(31.85), zc), (xc, Y(32.35), zc), 0.47, 0.06, N=24, caps=False, mat=DARK)
    # afterburner glow disc and flame (rehearsal proxies for the AB-4 Afterburner / glow meshes) + thrust point
    hinge(f'thrustTransform{num}', (xc, Y(33.15), zc), parent=f'nozzle{num}', size=0.3)
    ab = part(f'afterburner{num}_proxy', origin=(xc, Y(33.15), zc), parent=f'nozzle{num}', coll=C_FX, col=False)
    cyl(ab.mb, (xc, Y(32.40), zc), (xc, Y(32.42), zc), 0.46, N=24, mat=GLASS)
    loft(ab.mb, [[Vector((xc + r * math.cos(2 * math.pi * k / 24), Y(d), zc + r * math.sin(2 * math.pi * k / 24))) for k in range(24)] for d, r in ((33.1, 0.44), (34.6, 0.30), (36.8, 0.04))], True, True, GLASS)

# ================================================================ WING GLOVES, pivot fairing, gear pods, glove pylons
def glove_le(x): return 15.9 + (abs(x) - 1.9) * (4.9 / 3.5)
for side, s in (('R', 1), ('L', -1)):
    wr = part(f'wingroot_{side}')
    # root at x 2.00: just inside the fuselage side (2.02-2.06) and clear of the intake duct wall (outer face <= 2.00)
    st = [(2.00, 0.065, 24.9, GLOVE_Z), (2.6, 0.068, 24.9, GLOVE_Z), (3.6, 0.075, 24.9, GLOVE_Z), (4.6, 0.08, 24.85, GLOVE_Z - 0.01), (5.35, 0.085, 24.8, GLOVE_Z - 0.02)]
    rings = []
    for x, t, te, z in st:
        le = glove_le(x); ch = Vector((0, -(te - le), 0))
        rings.append([Vector((s * x, Y(le), z)) + ch * u + Vector((0, 0, 1)) * (v * ch.length) for u, v in section(t, 0, 1, 28)])
    loft(wr.mb, rings, True, True, SKIN)
    # main gear fairing under the glove (streamlined past the trailing edge): the bogie stows flat inside it, outboard of the leg
    gb = part(f'gearbay_{side}')
    GP = Section([(17.9, 1.96, s * 2.55, prof_rr(0.40, 0.14, 0.05, 0.12)), (18.7, 1.71, s * 3.00, prof_rr(1.00, 0.39, 0.05, 0.30)),
                  (19.15, 1.69, s * 3.36, prof_rr(1.33, 0.41, 0.06, 0.30)), (22.65, 1.69, s * 3.36, prof_rr(1.33, 0.41, 0.06, 0.30)),
                  (23.5, 1.72, s * 3.05, prof_rr(0.98, 0.38, 0.06, 0.28)), (25.0, 1.82, s * 2.85, prof_rr(0.66, 0.28, 0.05, 0.20)),
                  (26.9, 2.00, s * 2.70, prof_rr(0.12, 0.06, 0.04, 0.05))], 64)
    loft(gb.mb, GP.rings(17.9, 26.9, 0.2), True, True, SKIN)
    lo, hi = sorted((s * 2.08, s * 4.55))
    olo, ohi = sorted((s * OPEN_X[0], s * OPEN_X[1]))
    cav = cutter(f'cut_cav{side}', lo, hi, BAY_DD[0], BAY_DD[1], FAIR_Z + 0.03, 2.30)
    opn = cutter(f'cut_open{side}', olo, ohi, BAY_DD[0], BAY_DD[1], 0.5, FAIR_Z + 0.05)
    for c in (cav, opn): c.data.materials.append(MATS[MECH])
    apply_cuts(gb, [cav, opn])
    # recess in the glove underside over the inboard part of the bay (room for the leg door and brackets; stops short of the
    # outer wing root that sits inside the glove further out)
    rlo, rhi = sorted((s * 2.08, s * 4.15))
    rec = cutter(f'cut_glove{side}', rlo, rhi, BAY_DD[0], BAY_DD[1], 1.80, 2.20); rec.data.materials.append(MATS[MECH])
    apply_cuts(wr, [rec])
    # (no pivot fairing blister on the upper glove: the pivot stays inside the glove, per the owner)
    # outer pylon: a stub off the outboard flank of the gear fairing (the outer wing root swings inside the glove further
    # out, so nothing can hang from the glove there); the mount rail sits under the stub tip
    gp = part(f'glovePylon_{side}', parent=f'gearbay_{side}')
    rings = []
    for x, d0, ln, zc in ((4.58, 20.95, 2.60, 1.93), (GLOVE_PYLON_X + 0.08, 21.15, 2.20, 1.90)):
        rings.append([Vector((s * x, Y(d0), zc)) + Vector((0, -ln, 0)) * u + Vector((0, 0, 1)) * (v * ln) for u, v in section(0.09, 0, 1, 14)])
    loft(gp.mb, rings, True, True, SKIN)
    # short blade down to the rail, low enough that a full-length rack clears the lowered flap
    rings = [[Vector((s * GLOVE_PYLON_X, Y(d0), z)) + Vector((0, -ln, 0)) * u + X * (v * ln) for u, v in section(0.05, 0, 1, 10)]
             for z, d0, ln in ((1.88, 21.15, 2.25), (1.685, 21.25, 2.05))]
    loft(gp.mb, rings, True, True, SKIN)
    rbox(gp.mb, (s * GLOVE_PYLON_X, Y(22.25), 1.675), (0.10, 1.9, 0.04), 0.012, MECH)
    # actuator and side-brace anchor brackets hanging from the glove into the bay
    for ax, ad in ((2.72, ACT_D), (3.30, BRACE_D)):
        rbox(gb.mb, (s * ax, Y(ad), 2.09), (0.16, 0.14, 0.20), 0.02, MECH)
    # trunnion bearings either side of the leg
    for bd in (20.66, 21.15):
        rbox(gb.mb, (s * GEAR_T[0], Y(bd), GEAR_T[2] + 0.10), (0.20, 0.06, 0.44), 0.015, MECH)

# ================================================================ OUTER WINGS with slats, flaps, spoilers
an = math.radians(WING_ANHEDRAL)
WKEY = [(4.2, 20.45, 23.1, 0.075), (4.9, 20.64, 24.68, 0.075), (5.4, 20.8, 24.70, 0.075), (9.5, 22.08, 24.85, 0.065), (13.55, 23.35, 24.99, 0.055), (13.64, 23.62, 24.86, 0.022)]
def wkey(x):
    ax = abs(x)
    for a, b in zip(WKEY, WKEY[1:]):
        if ax <= b[0] + 1e-9:
            t = (ax - a[0]) / (b[0] - a[0]); return [a[i] + (b[i] - a[i]) * t for i in (1, 2, 3)]
    return WKEY[-1][1:]
def wz(x): return PIVOT[2] + (abs(x) - PIVOT[0]) * math.tan(an)
def wstation(s, x):
    le, te, t = wkey(x)
    return Vector((s * x, Y(le), wz(x))), Vector((0, -(te - le), 0)), t
BREAKS = [4.2, 4.9, 5.05, 5.4, 5.6, 7.6, 7.65, 9.4, 9.45, 9.5, 10.1, 10.15, 11.1, 12.55, 13.2, 13.25, 13.55, 13.64]
# each wing breaks up in three pieces like the AB-4: inner panel (wing1), outer panel (wing2) from the spoiler end, and the tip
W_SPLIT, W_TIP = 11.1, 13.25
def wing_strip(mb, s, xa, xb, c0, c1, mat=SKIN, n=12, zoff=0.0):
    xs = [xa] + [b for b in BREAKS if xa < b < xb] + [xb]
    rings = []
    for x in xs:
        le, ch, t = wstation(s, x)
        up = Vector((math.sin(an) * -s * 0, 0, 1))
        rings.append([le + ch * u + Vector((0, 0, 1)) * (v * ch.length + zoff) for u, v in section(t, c0, c1, n)])
    loft(mb, rings, True, True, mat)
def chord_pt(s, x, c, surface_side=0.0):
    le, ch, t = wstation(s, x)
    return le + ch * c + Vector((0, 0, 1)) * (surface_side * naca_t(c, t) * ch.length)

SLAT_C, FLAP_C, SPOIL = 0.12, 0.72, (0.56, 0.71)
FLAPS = ((5.05, 7.60), (7.65, 10.10), (10.15, 12.55))
SLATS = ((5.6, 9.4), (9.45, 11.08))
SLATS2 = ((11.12, 13.2),)          # outer slat section rides the outer panel
SPOILERS = ((6.2, 8.6), (8.7, 11.1))
for side, s in (('R', 1), ('L', -1)):
    piv = hinge(f'wingHinge_{side}a', (s * PIVOT[0], Y(PIVOT[1]), PIVOT[2]), size=1.2, parent=f'wingroot_{side}')
    hinge(f'wingHinge_{side}b', (s * PIVOT[0], Y(PIVOT[1]), PIVOT[2]), size=1.0, parent=f'wingHinge_{side}a')
    w = part(f'wing1_{side}', origin=piv.location.copy(), parent=f'wingHinge_{side}b')
    w2 = part(f'wing2_{side}', origin=chord_pt(s, W_SPLIT, 0.35), parent=f'wing1_{side}')
    wt = part(f'wingtip_{side}', origin=chord_pt(s, 13.62, 0.5), parent=f'wing2_{side}')
    for mb_, xa, xb in ((w.mb, 4.2, W_SPLIT), (w2.mb, W_SPLIT, W_TIP), (wt.mb, W_TIP, 13.64)):
        wing_strip(mb_, s, xa, xb, SLAT_C, FLAP_C, n=16)
    wing_strip(w.mb, s, 4.2, 5.6, 0.0, SLAT_C, n=8)
    wing_strip(w2.mb, s, 13.2, W_TIP, 0.0, SLAT_C, n=8)
    wing_strip(wt.mb, s, W_TIP, 13.64, 0.0, SLAT_C, n=8)
    wing_strip(w.mb, s, 4.2, 5.05, FLAP_C, 1.0, n=8)
    wing_strip(w2.mb, s, 12.55, W_TIP, FLAP_C, 1.0, n=8)
    wing_strip(wt.mb, s, W_TIP, 13.64, FLAP_C, 1.0, n=8)
    for a, b in ((7.60, 7.65), (10.10, 10.15)):
        wing_strip(w.mb, s, a, b, FLAP_C, 0.86, n=6)
    # navigation light: a slim pod faired onto the tip (wing skin) with the lens at its nose as its own part, so the
    # game can swap the lens to its lit material (red left, green right)
    tip = chord_pt(s, 13.6, 0.3)
    nb = tip + Vector((s * 0.035, 0, 0))
    tube(wt.mb, [nb + Vector((0, 0.06, 0)), nb + Vector((0, 0.02, 0)), nb + Vector((0, -0.25, 0)), nb + Vector((0, -0.62, 0)), nb + Vector((0, -0.80, 0))],
         [0.042, 0.046, 0.046, 0.032, 0.0], N=12, mat=SKIN, caps=True)
    nl = part(f'navlight_{side}', origin=nb + Vector((0, 0.06, 0)), parent=f'wingtip_{side}', col=False)
    tube(nl.mb, [nb + Vector((0, 0.055, 0)), nb + Vector((0, 0.12, 0)), nb + Vector((0, 0.19, 0)), nb + Vector((0, 0.235, 0))],
         [0.043, 0.040, 0.028, 0.0], N=12, mat=GLASS, caps=True)
    for xd in (12.85, 13.2, 13.5):
        te = chord_pt(s, xd, 0.99)
        cyl((wt if xd > W_TIP else w2).mb, te, te + Vector((0, -0.14, 0)), 0.012, 0.007, N=6, mat=MECH)
    # flap (3 sections, one hinge line below the lower surface at 74 % chord)
    fa, fb = chord_pt(s, FLAPS[0][0], 0.74, -1) - Vector((0, 0, 0.10)), chord_pt(s, FLAPS[-1][1], 0.74, -1) - Vector((0, 0, 0.10))
    ax = (fb - fa) * s
    hinge(f'flap_{side}', fa, parent=f'wing1_{side}', size=0.3)
    fl = part(f'flap_{side}_visible', origin=fa, parent=pair(f'flapHinge_{side}', fa, axis=ax, parent=f'flap_{side}'))
    for xa, xb in FLAPS:
        wing_strip(fl.mb, s, xa, xb, FLAP_C + 0.015, 1.0, n=8)
    # flap track fairings under the wing (fixed)
    for xf in (7.625, 10.125):
        p0 = chord_pt(s, xf, 0.45, -1); p1 = chord_pt(s, xf, 1.06, -1)
        tube(w.mb, [p0 + Vector((0, 0, 0.02)), p0.lerp(p1, 0.3) - Vector((0, 0, 0.09)), p0.lerp(p1, 0.85) - Vector((0, 0, 0.11)), p1 - Vector((0, 0, 0.04))], [0.02, 0.06, 0.05, 0.015], N=10, mat=SKIN)
    # slats (2 sections, hinge below the leading edge)
    sa, sb = chord_pt(s, SLATS[0][0], 0.10, -1) - Vector((0, 0, 0.06)), chord_pt(s, SLATS2[-1][1], 0.10, -1) - Vector((0, 0, 0.06))
    hinge(f'slat_{side}', sa, parent=f'wing1_{side}', size=0.3)
    sl = part(f'slat_{side}_visible', origin=sa, parent=pair(f'slatHinge_{side}', sa, axis=(sb - sa) * s, parent=f'slat_{side}'))
    for xa, xb in SLATS:
        wing_strip(sl.mb, s, xa, xb, 0.0, SLAT_C - 0.008, n=8)
    # the outer slat section on its own hinge under the outer panel (same axis), so it goes with that panel when it breaks off
    sa2 = chord_pt(s, SLATS2[0][0], 0.10, -1) - Vector((0, 0, 0.06))
    hinge(f'slat2_{side}', sa2, parent=f'wing2_{side}', size=0.3)
    sl2 = part(f'slat2_{side}_visible', origin=sa2, parent=pair(f'slat2Hinge_{side}', sa2, axis=(sb - sa) * s, parent=f'slat2_{side}'))
    for xa, xb in SLATS2:
        wing_strip(sl2.mb, s, xa, xb, 0.0, SLAT_C - 0.008, n=8)
    # spoilers: thin panels on the upper surface, hinged at their leading edge
    pa, pb = chord_pt(s, SPOILERS[0][0], SPOIL[0], 1), chord_pt(s, SPOILERS[-1][1], SPOIL[0], 1)
    hinge(f'spoiler_{side}', pa, parent=f'wing1_{side}', size=0.3)
    spo = part(f'spoiler_{side}_visible', origin=pa, parent=pair(f'spoilerHinge_{side}', pa, axis=(pb - pa) * s, parent=f'spoiler_{side}'))
    for xa, xb in SPOILERS:
        rings = []
        for x in (xa, xb):
            cs = [SPOIL[0] + (SPOIL[1] - SPOIL[0]) * k / 5 for k in range(6)]
            top = [chord_pt(s, x, c, 1) + Vector((0, 0, 0.012)) for c in cs]
            bot = [chord_pt(s, x, c, 1) for c in reversed(cs)]
            rings.append(top + bot)
        loft(spo.mb, rings, True, True, SKIN, smooth=False)
    # dark cove shrouds under the slat and flap gaps (you see this, not the sky, through the gap); they sit at the lower
    # skin, partly inside the slat / flap, and become the cove floor when those deploy
    for spans, ca, cb in ((SLATS + SLATS2, SLAT_C - 0.025, SLAT_C + 0.02), (FLAPS, FLAP_C - 0.02, FLAP_C + 0.035)):
        for xa0, xb0 in spans:
            for xa, xb, mb_ in ((xa0, min(xb0, W_SPLIT), w.mb), (max(xa0, W_SPLIT), xb0, w2.mb)):
                if xb - xa < 0.1: continue
                ol = [chord_pt(s, xa + 0.02, ca, -1), chord_pt(s, xb - 0.02, ca, -1), chord_pt(s, xb - 0.02, cb, -1), chord_pt(s, xa + 0.02, cb, -1)]
                plate(mb_, [p + Vector((0, 0, 0.012)) for p in ol], 0.006, (0, 0, 1), DARK)

# ================================================================ TAILPLANES (all-moving, pivot spindle at x 1.55, d 29.9)
for side, s in (('R', 1), ('L', -1)):
    hp = Vector((s * 1.55, Y(29.9), 2.12))
    hinge(f'elevator_{side}', hp, parent='fuselage_R', size=0.3)
    el = part(f'elevator_{side}_visible', origin=hp, parent=pair(f'elevatorHinge_{side}', hp, axis=(1, 0, 0), parent=f'elevator_{side}'))
    st = [(1.1, 27.0, 5.5, 0.045), (1.6, 27.4, 5.1, 0.045), (3.3, 29.45, 3.75, 0.042), (4.9, 31.5, 2.4, 0.04), (5.15, 32.1, 1.75, 0.035), (5.2, 32.35, 1.35, 0.02)]
    rings = []
    for x, le, ch, t in st:
        c = Vector((0, -ch, 0))
        rings.append([Vector((s * x, Y(le), 2.12)) + c * u + Vector((0, 0, 1)) * (v * ch) for u, v in section(t, 0, 1, 22)])
    loft(el.mb, rings, True, True, SKIN)
    for xd, ted in ((4.85, 33.80), (5.10, 33.84)):
        cyl(el.mb, (s * xd, Y(ted - 0.02), 2.12), (s * xd, Y(ted + 0.12), 2.12), 0.012, 0.007, N=6, mat=MECH)

# ================================================================ MID PYLONS (under the intakes)
for side, s in (('R', 1), ('L', -1)):
    mp = part(f'midPylon_{side}', parent=f'intake_{side}')
    px = s * MID_PYLON_X
    rings = [[Vector((px, Y(d0), z)) + Vector((0, -ln, 0)) * u + X * (v * ln) for u, v in section(0.05, 0, 1, 10)] for z, d0, ln in ((BELLY_Z + 0.04, 13.9, 3.0), (BELLY_Z - 0.08, 14.1, 2.6))]
    loft(mp.mb, rings, True, True, SKIN)
    rbox(mp.mb, (px, Y(15.2), BELLY_Z - 0.09), (0.09, 2.2, 0.03), 0.01, MECH)

# ================================================================ MAIN LANDING GEAR (rest = down). The leg hangs from a fore-aft trunnion on the
# inboard side of the glove fairing and swings OUTBOARD and up through 90 deg, so the six-wheel bogie stows flat
# (axles vertical) under the glove. A two-link side brace behind the leg folds inboard, a retraction actuator ahead of
# the leg telescopes, a leg door on the leg closes the inboard part of the opening and a bi-fold main door, hinged on
# the outboard edge, closes the rest. Game rules this has to live with: the doors open fully before the leg moves and
# close after it is up (and stay open while the gear is down); the leg angle, the brace angle and the door angles are
# all linear in the fold; the actuator halves and the lower brace link aim at each other (LookAt).
def wheel(mb, c, r, w, axis=Vector((1, 0, 0))):
    # tyre: rounded shoulders, 20 segments round, open sides (the rim flanges cover them); about 280 triangles
    prof = [(-0.5, 0.60), (-0.5, 0.84), (-0.40, 0.96), (-0.20, 1.0), (0.20, 1.0), (0.40, 0.96), (0.5, 0.84), (0.5, 0.60)]
    N = 20; rings = []
    for xf, rf in prof:
        rings.append([c + Vector((xf * w, math.cos(2 * math.pi * i / N) * r * rf, math.sin(2 * math.pi * i / N) * r * rf)) for i in range(N)])
    loft(mb, rings, False, False, TYRE)
    # wheel: rim flanges, a dished hub and the hub cap
    hub = [(-0.52, 0.30), (-0.52, 0.64), (-0.40, 0.40), (0.40, 0.40), (0.52, 0.64), (0.52, 0.30)]
    rings = [[c + Vector((xf * w, math.cos(2 * math.pi * i / 16) * r * rf, math.sin(2 * math.pi * i / 16) * r * rf)) for i in range(16)] for xf, rf in hub]
    loft(mb, rings, True, True, MECH)
    for sx in (-1, 1):
        cyl(mb, c + Vector((sx * 0.52 * w, 0, 0)), c + Vector((sx * 0.60 * w, 0, 0)), r * 0.20, r * 0.13, N=8, mat=MECH)    # hub cap
        for k in range(6):                                                                                               # wheel bolts
            a = 2 * math.pi * k / 6
            o = Vector((sx * 0.52 * w, math.cos(a) * r * 0.27, math.sin(a) * r * 0.27))
            cyl(mb, c + o, c + o + Vector((sx * 0.03, 0, 0)), 0.016, N=3, mat=MECH)

def brake_lines(mb, pts, rad=0.012):
    """Hydraulic and brake lines down a gear leg (a thin tube through the given points)."""
    tube(mb, pts, rad, N=6, mat=MECH, caps=True)

def brace_knee(S, B, L1, L2, inboard_x):
    """Knee of a two-link brace S-K-B in the x-z plane, on the side nearer inboard_x."""
    d = (B - S).length; u = (B - S).normalized()
    a = (L1 * L1 - L2 * L2 + d * d) / (2 * d); h = math.sqrt(max(L1 * L1 - a * a, 0.0))
    m = S + u * a; n = Vector((-u.z, 0, u.x))
    k1, k2 = m + n * h, m - n * h
    return k1 if abs(k1.x - inboard_x) < abs(k2.x - inboard_x) else k2

# piano hinge for a door: a rod on the fixed structure along the hinge line, brackets tying the rod into the skin, and
# knuckles on the door wrapped round the rod (they turn about the rod's own axis, so they stay on it at any angle)
def door_hinge(fixed_mb, door_mb, H, d0, d1, out, n=3):
    cyl(fixed_mb, (H.x, Y(d0), H.z), (H.x, Y(d1), H.z), 0.016, N=8, mat=MECH)
    step = (d1 - d0) / n
    for k in range(n):
        dk = d0 + step * (k + 0.5)
        cyl(door_mb, (H.x, Y(dk - 0.08), H.z), (H.x, Y(dk + 0.08), H.z), 0.030, N=8, mat=MECH)
        for dd in (dk - 0.13, dk + 0.13):
            cyl(fixed_mb, (H.x, Y(dd - 0.04), H.z), (H.x, Y(dd + 0.04), H.z), 0.030, N=8, mat=MECH)
            c = H + out * 0.5
            rbox(fixed_mb, (c.x, Y(dd), c.z), (abs(out.x) + 0.04, 0.07, abs(out.z) + 0.04), 0.006, MECH)

GEAR_INFO = {}
for side, s in (('R', 1), ('L', -1)):
    T = Vector((s * GEAR_T[0], Y(GEAR_T[1]), GEAR_T[2]))
    BOG = Vector((s * GEAR_X, Y(GEAR_T[1]), MAIN_R + 0.30))
    DN = Vector((0, 0, -1)); L = (T - BOG).length
    hinge(f'gearHinge_{side}', T, axis=(0, 1, 0), size=0.8, parent=f'gearbay_{side}')
    g = part(f'gear_{side}', origin=T, parent=f'gearHinge_{side}')
    # trunnion (between the two bearings on the fairing) and the main shock-strut cylinder
    cyl(g.mb, T + Vector((0, Y(20.69) - Y(20.9), 0)), T + Vector((0, Y(21.12) - Y(20.9), 0)), 0.10, N=10, mat=MECH)
    rbox(g.mb, tuple(T + DN * 0.02), (0.30, 0.34, 0.20), 0.03, MECH)
    cyl(g.mb, T + DN * 0.08, T + DN * (L * 0.58), 0.15, 0.14, N=12, mat=MECH)
    rbox(g.mb, tuple(T + DN * (L * 0.56)), (0.32, 0.26, 0.08), 0.02, MECH)          # gland nut collar
    # actuator lug (front) and side-brace lug (rear)
    rbox(g.mb, (s * GEAR_X, Y((ACT_D + 20.75) / 2), GEAR_T[2] - 0.35), (0.08, 20.75 - ACT_D + 0.06, 0.10), 0.015, MECH)
    rbox(g.mb, (s * GEAR_X, Y((BRACE_D + 21.05) / 2), GEAR_T[2] - 0.52), (0.08, BRACE_D - 21.05 + 0.06, 0.10), 0.015, MECH)
    # leg door: a plate inboard of the leg on two brackets; stowed, it lies flush in the skin from OPEN_X[0] to 3.45
    LDX = GEAR_T[0] - (GEAR_T[2] - FAIR_Z)
    ld = part(f'legDoor_{side}', origin=T, parent=f'gear_{side}', col=False)
    za, zb = GEAR_T[2] - (3.49 - GEAR_T[0]), GEAR_T[2] + (GEAR_T[0] - (OPEN_X[0] + 0.012))   # closed seams 8-12 mm
    rbox(ld.mb, (s * LDX, Y(20.9), (za + zb) / 2), (0.03, BAY_DD[1] - BAY_DD[0] - 0.02, zb - za), 0.008, SKIN)
    for bz in (GEAR_T[2] - 0.22, GEAR_T[2] - 0.50):
        for bd in (20.62, 21.18):
            tube(ld.mb, [Vector((s * (LDX + 0.01), Y(bd), bz)), Vector((s * (GEAR_X - 0.10), Y(20.9 + (bd - 20.9) * 0.45), bz))], 0.025, N=8, mat=MECH)
    # unsprung slider with torque links
    u = part(f'gear_unsprung_{side}', origin=BOG + Vector((0, 0, -0.30)), parent=f'gear_{side}')
    cyl(u.mb, T + DN * (L * 0.45), BOG + Vector((0, 0, 0.10)), 0.11, N=12, mat=MECH)
    k1 = T + DN * (L * 0.62) + Vector((0, 0.16, 0)); k2 = BOG + Vector((0, 0.14, 0.18)); kn = k1.lerp(k2, 0.5) + Vector((0, 0.14, 0))
    tube(u.mb, [k1, kn, k2], 0.03, N=8, mat=MECH)
    # hydraulic lines down the back of the strut (on the strut) and the brake manifold block
    for off in (-0.06, 0.06):
        brake_lines(g.mb, [T + Vector((off, -0.17, -0.10)), T + DN * (L * 0.30) + Vector((off, -0.17, 0)), T + DN * (L * 0.54) + Vector((off, -0.17, 0))])
    rbox(u.mb, tuple(BOG + Vector((0, -0.16, 0.24))), (0.18, 0.08, 0.10), 0.01, MECH)
    # bogie beam, axle hangers and six wheels
    bo = part(f'bogey_{side}', origin=BOG, parent=f'gear_unsprung_{side}')
    cyl(bo.mb, BOG + Vector((0, 1.22, 0)), BOG + Vector((0, -1.22, 0)), 0.085, N=10, mat=MECH)
    rbox(bo.mb, tuple(BOG + Vector((0, 1.26, 0.02))), (0.10, 0.08, 0.12), 0.015, MECH)                    # towing lug
    for dy in (0.55, -0.55):                                                                              # brake lines along the beam
        brake_lines(bo.mb, [BOG + Vector((-0.07, 0, 0.08)), BOG + Vector((-0.07, dy * 1.6, 0.06)), BOG + Vector((-0.07, dy * 1.8, -0.12))], 0.010)
    rbox(bo.mb, tuple(BOG), (0.30, 0.34, 0.24), 0.03, MECH)
    for k, dy in (('F', 1.0), ('M', 0.0), ('R', -1.0)):
        ac = BOG + Vector((0, dy, -0.30))
        rbox(bo.mb, tuple(BOG + Vector((0, dy, -0.15))), (0.12, 0.16, 0.34), 0.02, MECH)
        cyl(bo.mb, ac + Vector((-0.355, 0, 0)), ac + Vector((0.355, 0, 0)), 0.05, N=8, mat=MECH)
        for ws, wx in (('i', -s), ('o', s)):
            wp = part(f'wheel_{side}{k}{ws}', origin=ac + Vector((wx * MAIN_OFF, 0, 0)), parent=f'bogey_{side}', col=False)
            wheel(wp.mb, ac + Vector((wx * MAIN_OFF, 0, 0)), MAIN_R, MAIN_W)
    # retraction actuator: cylinder hangs from the glove, rod end on the leg lug; each half aims at the other end
    A = Vector((s * 2.72, Y(ACT_D), 2.02)); R0 = Vector((s * GEAR_X, Y(ACT_D), GEAR_T[2] - 0.35))
    ac_ = part(f'actCyl_{side}', origin=A, parent=f'gearbay_{side}', col=False)
    cyl(ac_.mb, A + Vector((0, 0.0, 0)), A + Vector((0, 0.39, 0)), 0.07, N=10, mat=MECH)
    rbox(ac_.mb, tuple(A), (0.10, 0.10, 0.10), 0.02, MECH)
    ar = part(f'actRod_{side}', origin=R0, parent=f'gear_{side}', col=False)
    cyl(ar.mb, R0, R0 + Vector((0, 0.39, 0)), 0.04, N=8, mat=MECH)
    rbox(ar.mb, tuple(R0), (0.09, 0.09, 0.09), 0.02, MECH)
    hinge(f'actTgtRod_{side}', R0, parent=f'gear_{side}', size=0.15)
    hinge(f'actTgtAnchor_{side}', A, parent=f'gearbay_{side}', size=0.15)
    # side brace: upper link swings about its glove anchor (linear in the fold), lower link on the leg aims at the knee
    S = Vector((s * 3.30, Y(BRACE_D), 2.02)); B0 = Vector((s * GEAR_X, Y(BRACE_D), GEAR_T[2] - 0.52))
    LB = (S - B0).length / 2; K0 = S.lerp(B0, 0.5)
    bu = part(f'braceU_{side}', origin=S, parent=f'gearbay_{side}', col=False)
    tube(bu.mb, [S, K0], 0.05, N=8, mat=MECH)
    rbox(bu.mb, tuple(S), (0.12, 0.10, 0.12), 0.02, MECH)
    rbox(bu.mb, tuple(K0), (0.12, 0.12, 0.12), 0.02, MECH)                             # knee clevis
    rbox(bu.mb, tuple(S.lerp(K0, 0.55) + Vector((0, 0, 0))), (0.05, 0.06, 0.18), 0.01, MECH)   # downlock link stub
    hinge(f'braceKnee_{side}', K0, parent=f'braceU_{side}', size=0.12)
    bl = part(f'braceL_{side}', origin=B0, parent=f'gear_{side}', col=False)
    cyl(bl.mb, B0, B0 + Vector((0, LB - 0.03, 0)), 0.045, N=8, mat=MECH)
    rbox(bl.mb, tuple(B0), (0.09, 0.09, 0.09), 0.02, MECH)
    GEAR_INFO[side] = dict(T=T, A=A, R0=R0, S=S, B0=B0, LB=LB)
    # bi-fold main door: outer panel hinged on the opening's outboard edge, inner panel hinged to it; both fold down
    # into a stack under the hinge (the inner panel's free edge runs along the skin line)
    W2 = (DOOR_HX - 3.47) / 2
    H = Vector((s * DOOR_HX, Y(20.9), FAIR_Z + 0.015))
    gd1 = part(f'gearDoor_{side}O', origin=H, parent=pair(f'gearDoorHinge_{side}O', H, axis=(0, 1, 0), parent=f'gearbay_{side}'))
    rbox(gd1.mb, (s * (DOOR_HX - W2 / 2), Y(20.9), FAIR_Z), (W2 - 0.002, BAY_DD[1] - BAY_DD[0] - 0.02, 0.03), 0.008, SKIN)
    E = Vector((s * (DOOR_HX - W2), Y(20.9), FAIR_Z - 0.015))
    gd2 = part(f'gearDoor_{side}I', origin=E, parent=pair(f'gearDoorHinge_{side}I', E, axis=(0, 1, 0), parent=f'gearDoor_{side}O'))
    rbox(gd2.mb, (s * (DOOR_HX - 1.5 * W2), Y(20.9), FAIR_Z), (W2 - 0.006, BAY_DD[1] - BAY_DD[0] - 0.02, 0.03), 0.008, SKIN)
    gb_mb = PARTS[f'gearbay_{side}'].mb
    # seal strip inside the fairing over the door hinge line, so the hinge gap shows skin, not a dark slit
    rbox(gb_mb, (s * (DOOR_HX - 0.02), Y((BAY_DD[0] - 0.17 + BAY_DD[1] + 0.02) / 2), FAIR_Z + 0.07), (0.22, BAY_DD[1] - BAY_DD[0] + 0.19, 0.02), 0.004, SKIN)
    # fixed sill along the inboard edge of the opening: closes the slot between the stowed leg door and the bay lip
    rbox(gb_mb, (s * 2.17, Y(20.9), FAIR_Z - 0.015), (0.22, BAY_DD[1] - BAY_DD[0] + 0.08, 0.03), 0.006, SKIN)
    door_hinge(gb_mb, gd1.mb, H, BAY_DD[0] + 0.10, BAY_DD[1] - 0.10, Vector((s * 0.05, 0, 0.035)), n=4)
    door_hinge(gd1.mb, gd2.mb, E, BAY_DD[0] + 0.10, BAY_DD[1] - 0.10, Vector((s * 0.03, 0, 0.0)), n=4)

# ================================================================ NOSE GEAR (retracts aft)
NG = Vector((0, Y(10.7), 1.85)); NAX = Vector((0, Y(10.9), NOSE_R))
hinge('gearhinge_F', NG, axis=(1, 0, 0), size=0.8, parent='fuselage_F')
gf = part('gear_F', origin=NG, parent='gearhinge_F')
cyl(gf.mb, NG + Vector((-0.28, 0, 0)), NG + Vector((0.28, 0, 0)), 0.08, N=10, mat=MECH)
cyl(gf.mb, NG, NG.lerp(NAX, 0.55), 0.10, 0.095, N=12, mat=MECH)
tube(gf.mb, [Vector((0, Y(11.9), 1.70)), NG.lerp(NAX, 0.45) + Vector((0, -0.08, 0))], 0.045, N=8, mat=MECH)
rbox(gf.mb, tuple(NG.lerp(NAX, 0.35) + Vector((0, 0.13, 0))), (0.16, 0.10, 0.14), 0.02, GLASS)   # taxi light
cyl(gf.mb, NG.lerp(NAX, 0.20), NG.lerp(NAX, 0.28), 0.135, N=12, mat=MECH)                       # steering collar
brake_lines(gf.mb, [NG + Vector((0.10, -0.06, -0.05)), NG.lerp(NAX, 0.30) + Vector((0.11, -0.05, 0)), NG.lerp(NAX, 0.52) + Vector((0.10, -0.04, 0))])
uf = part('gear_unsprung_F', origin=NAX, parent='gear_F')
_sz = (NG - NAX).normalized(); _sx = Vector((1, 0, 0)); _sy = _sz.cross(_sx).normalized()
uf.rot = Matrix((_sx, _sy, _sz)).transposed()
cyl(uf.mb, NG.lerp(NAX, 0.45), NAX + Vector((0, 0, 0.08)), 0.07, N=10, mat=MECH)
rbox(uf.mb, tuple(NAX + Vector((0, 0, 0.06))), (0.30, 0.16, 0.14), 0.02, MECH)
cyl(uf.mb, NAX + Vector((-0.32, 0, 0)), NAX + Vector((0.32, 0, 0)), 0.04, N=8, mat=MECH)
for ws, wx in (('L', -0.19), ('R', 0.19)):
    wp = part(f'wheel_F{ws}', origin=NAX + Vector((wx, 0, 0)), parent='gear_unsprung_F', col=False)
    wheel(wp.mb, NAX + Vector((wx, 0, 0)), NOSE_R, NOSE_W)
for side, s in (('R', 1), ('L', -1)):
    hl = Vector((s * 0.42, Y(11.35), BELLY_Z + 0.06))
    d = part(f'gearDoor_F{side}', origin=hl, parent=pair(f'gearDoorHinge_F{side}', hl, axis=(0, 1, 0), parent='fuselage_F'))
    rbox(d.mb, (s * 0.21, Y(11.35), BELLY_Z + 0.05), (0.42, 2.38, 0.03), 0.01, SKIN)
    door_hinge(PARTS['fuselage_F'].mb, d.mb, hl, 10.25, 12.45, Vector((s * 0.03, 0, 0.03)), n=3)

# ================================================================ bay doors: our own panels on the AB-4 door hinges and animation
# outer skin face takes the livery (PB22_skin), the inner face and its stiffeners are mechanism grey (PB22_mech)
for k, (dc, ln) in enumerate(BAYS):
    fr = 'F' if k == 0 else 'R'
    for side, s in (('R', 1), ('L', -1)):
        hl = Vector((s * 1.0, Y(dc), BELLY_Z + 0.01))
        d = part(f'bayDoor_{fr}{side}', origin=hl, parent=pair(f'bayDoorHinge_{fr}{side}', hl, axis=(0, 1, 0), parent='fuselage'), col=False)
        rbox(d.mb, (s * 0.5, Y(dc), BELLY_Z + 0.005), (0.999, ln - 0.008, 0.03), 0.01, MECH)
        d.mb.bm.normal_update()
        for f in d.mb.bm.faces:
            if f.normal.z < -0.5: f.material_index = SKIN
        # inner stiffeners: a spine along the door and transverse ribs (kept 3 cm tall, clear of the bay loads)
        rbox(d.mb, (s * 0.5, Y(dc), BELLY_Z + 0.035), (0.04, ln - 0.30, 0.03), 0.006, MECH)
        n = max(2, int(round((ln - 0.4) / 0.75)))
        for i in range(n + 1):
            yy = dc - (ln - 0.4) / 2 + i * (ln - 0.4) / n
            rbox(d.mb, (s * 0.5, Y(yy), BELLY_Z + 0.035), (0.86, 0.03, 0.03), 0.006, MECH)

# fixed belly strip between the two bays (the bay cut runs through, so the doors alone left a 0.4 m open slot)
_g0, _g1 = BAYS[0][0] + BAYS[0][1] / 2, BAYS[1][0] - BAYS[1][1] / 2
_mb = PARTS['fuselage'].mb; _n0 = len(_mb.bm.faces)
rbox(_mb, (0.0, Y((_g0 + _g1) / 2), BELLY_Z + 0.005), (2.0, _g1 - _g0 - 0.008, 0.03), 0.004, MECH)
_mb.bm.faces.ensure_lookup_table(); _mb.bm.normal_update()
for f in _mb.bm.faces[_n0:]:
    if f.normal.z < -0.5: f.material_index = SKIN
# dividing frame between the forward and rear bays (owner): a bulkhead web round the cavity's sides and roof over the
# belly strip. It leaves the middle of the cavity open so the combined-bay loads still hang across the split.
_dw = (_g0 + _g1) / 2
for cx, sx, cz, sz in ((-0.91, 0.18, 2.065, 1.47), (0.91, 0.18, 2.065, 1.47), (0.0, 2.0, 2.71, 0.18)):
    rbox(_mb, (cx, Y(_dw), cz), (sx, 0.05, sz), 0.006, MECH)
for cx in (-0.80, 0.80):                                                     # flanges on the web's free edges
    rbox(_mb, (cx, Y(_dw), 2.065), (0.03, 0.14, 1.47), 0.004, MECH)
rbox(_mb, (0.0, Y(_dw), 2.62), (1.62, 0.14, 0.03), 0.004, MECH)

# ================================================================ reference empties
for nm, loc in (('CoM', (0, Y(19.5), 2.40)), ('weaponBay_forward', (0, Y(15.9), 2.01)), ('weaponBay_rear', (0, Y(21.85), 2.04)),
                ('weaponBay_combined', (0, Y(18.9), 2.05)), ('cockpit_seat_ref', (0, Y(7.0), 2.30))):
    hinge(nm, loc, size=0.3, parent='fuselage' if nm == 'weaponBay_rear' else None)
for side, s in (('R', 1), ('L', -1)):
    hinge(f'pylonMount_mid_{side}', (s * MID_PYLON_X, Y(15.0), BELLY_Z - 0.10), size=0.3, parent=f'midPylon_{side}')
    hinge(f'pylonMount_glove_{side}', (s * GLOVE_PYLON_X, Y(22.25), 1.655), size=0.3, parent=f'glovePylon_{side}')

# ================================================================ GUIDES (hangar door, Piledrivers)
def guide_pd2(name, x, d_nose, zc):
    mb = MeshBuilder()
    cyl(mb, (x, Y(d_nose), zc), (x, Y(d_nose + PD_LEN), zc), PD_DIA / 2, N=24, mat=DARK)
    fc = Vector((x, Y(d_nose + PD_LEN - 0.5), zc))
    for k in range(4):
        a = math.radians(45 + 90 * k)
        rot = Matrix.Rotation(-a, 3, 'Y')
        sub = MeshBuilder(); rbox(sub, (PD_FIN / 4, 0, 0), (PD_FIN / 2, 0.8, 0.03), 0.005, DARK)
        for v in sub.bm.verts: v.co = rot @ v.co + fc
        tmp = bpy.data.meshes.new('t'); sub.bm.to_mesh(tmp); sub.bm.free(); mb.bm.from_mesh(tmp); bpy.data.meshes.remove(tmp)
    me = bpy.data.meshes.new(name); mb.bm.to_mesh(me); mb.bm.free()
    me.materials.append(MATS[DARK])
    o = bpy.data.objects.new(name, me); C_GUIDE.objects.link(o)
    return o
for side, s in (('R', 1), ('L', -1)):
    guide_pd2(f'PD_mid_{side}', s * MID_PYLON_X, 11.6, BELLY_Z - 0.10 - PD_DIA / 2)
    guide_pd2(f'PD_glove_{side}', s * GLOVE_PYLON_X, 22.25 - PD_LEN / 2, 1.655 - PD_DIA / 2)
cu = bpy.data.curves.new('hangar_door_8m', 'CURVE'); cu.dimensions = '3D'
sp = cu.splines.new('POLY'); sp.points.add(3)
for p_, (x, y, z) in zip(sp.points, [(-22.89, Y(-2), 0), (-22.89, Y(-2), 8.0), (22.89, Y(-2), 8.0), (22.89, Y(-2), 0)]): p_.co = (x, y, z, 1)
C_GUIDE.objects.link(bpy.data.objects.new('hangar_door_8m', cu))

# ================================================================ interior machinery (wells, bay, engine faces)
# everything from here to the end of the structure pass is internal (seen only through battle damage): build it coarser
pb22_lib.INT_TOL, pb22_lib.INT_SKIP, pb22_lib.N_SCALE = 0.012, (GLASS, TYRE), 0.5
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pb22_interior.py')).read())
# ================================================================ internal structure (frames, ducts, engines, racks, spars and ribs)
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pb22_structure.py')).read())
# underside filler between the forward bay doors and the intake floors (d 13.0-14.55): the fuselage skin stopped at the
# bay lip there, leaving an open slot with a loose edge under the intake transition (0.4.5)
for _s in (1, -1):
    rbox(PARTS['fuselage'].mb, (_s * 1.1375, Y(13.775), 1.318), (0.265, 1.55, 0.032), 0.004, SKIN)
# ================================================================ systems (fuel cells, hydraulics, wiring, engine plumbing), clip-checked
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pb22_systems.py')).read())
# ================================================================ structure pass 2 (ties the frame together), clip-checked
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pb22_structure2.py')).read())
pb22_lib.INT_TOL, pb22_lib.N_SCALE = 0.0, 1.0

# ================================================================ FINALIZE: objects, parenting, collision hulls
for c in list(C_TMP.objects): bpy.data.objects.remove(c)
OBJS = {}
# parts built for the left side from mirrored (-x) points come out inside-out; turn them the right way round
# so they match their right-hand partner (otherwise the game culls their outer skin)
for name, p in PARTS.items():
    if '_L' not in name: continue
    r = PARTS.get(name.replace('_L', '_R'))
    if r is None: continue
    vl, vr = p.mb.bm.calc_volume(signed=True), r.mb.bm.calc_volume(signed=True)
    if vl * vr < 0 and abs(vl) > 1e-4:
        bmesh.ops.reverse_faces(p.mb.bm, faces=p.mb.bm.faces[:], flip_multires=False)
        print('flipped inside-out part', name)
# any other closed part that came out inside-out (negative signed volume) is turned the right way round too
for name, p in PARTS.items():
    bm = p.mb.bm
    if all(e.is_manifold for e in bm.edges) and bm.calc_volume(signed=True) < -1e-4:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:], flip_multires=False)
        print('flipped inside-out closed part', name)
for name, p in PARTS.items():
    bm = p.mb.bm
    used = sorted({f.material_index for f in bm.faces})
    remap = {m: i for i, m in enumerate(used)}
    for f in bm.faces: f.material_index = remap[f.material_index]
    if p.origin is None:
        mn = Vector((min(v.co.x for v in bm.verts), min(v.co.y for v in bm.verts), min(v.co.z for v in bm.verts)))
        mx = Vector((max(v.co.x for v in bm.verts), max(v.co.y for v in bm.verts), max(v.co.z for v in bm.verts)))
        org = (mn + mx) / 2
    else:
        org = Vector(p.origin)
    for v in bm.verts: v.co -= org
    if p.rot is not None:
        inv = p.rot.inverted()
        for v in bm.verts: v.co = inv @ v.co
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for m in used: me.materials.append(MATS[m])
    o = bpy.data.objects.new(name, me); p.coll.objects.link(o); o.location = org
    if p.rot is not None:
        o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = p.rot.to_quaternion(); o['rest_q'] = list(o.rotation_quaternion); o['keep_frame'] = 1
    OBJS[name] = o
bpy.context.view_layer.update()
for name, (e, par) in EMPTIES.items():
    if par: parent_keep(e, OBJS.get(par) or EMPTIES[par][0])
for name, p in PARTS.items():
    if p.parent: parent_keep(OBJS[name], OBJS.get(p.parent) or EMPTIES[p.parent][0])
# arms carry their geometry along local +Z; pb22_pose.py aims them
OBJS['gear_unsprung_F']['steer_axis'] = list((NG - NAX).normalized())
# actuator halves and the lower brace link carry their geometry along local +Y (Unity +Z) so the game's LookAt can aim them
for side in ('R', 'L'):
    for nm in (f'actCyl_{side}', f'actRod_{side}', f'braceL_{side}'):
        OBJS[nm]['keep_frame'] = 1; OBJS[nm].rotation_mode = 'QUATERNION'
    OBJS[f'braceU_{side}'].rotation_mode = 'QUATERNION'
# every visible surface must face the camera: fix inconsistent winding and inside-out islands by ray voting
from pb22_orient import fix_orientation
bpy.context.view_layer.update()
fix_orientation([o for o in C_MODEL.all_objects if o.type == 'MESH'], dirs=128, grid=0.05)

def hull(o, target=250):
    """Convex collision hull under Unity's 255-triangle cap: thin the points on a grid (keeping the point
    farthest from the centre in each cell, so the extents survive) until the hull is small enough."""
    pts = [v.co.copy() for v in o.data.vertices]
    c = sum(pts, Vector()) / len(pts)
    ext = max(max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3))
    cell = ext / 14.0
    while True:
        cells = {}
        for p in pts:
            k = (round(p.x / cell), round(p.y / cell), round(p.z / cell))
            if k not in cells or (p - c).length > (cells[k] - c).length: cells[k] = p
        bm = bmesh.new()
        for p in cells.values(): bm.verts.new(p)
        bmesh.ops.convex_hull(bm, input=bm.verts)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        bmesh.ops.triangulate(bm, faces=bm.faces)
        if len(bm.faces) <= target or cell > ext: break
        bm.free(); cell *= 1.25
    me = bpy.data.meshes.new(o.name + '_colmesh'); bm.to_mesh(me); bm.free()
    h = bpy.data.objects.new(o.name + '_colmesh', me); C_COL.objects.link(h)
    h.parent = o; h.matrix_parent_inverse = Matrix.Identity(4); h.location = (0, 0, 0)
    h.hide_render = True
    return h
for name, p in PARTS.items():
    if p.col and p.coll is C_MODEL and not name.startswith(('arm', 'gearDoor', 'canopy', 'legDoor', 'act', 'brace')):
        hull(OBJS[name])
for side, s in (('L', -1), ('R', 1)):
    e = EMPTIES[f'engines_{side}'][0]; xc, zc = s * 0.74, 2.40
    bm = bmesh.new()
    for d in (24.7, 31.0):            # starts behind the rear weapon bay (d 24.55) so bay loads don't overlap it
        for k in range(12):
            a = 2 * math.pi * k / 12; bm.verts.new(Vector((xc + 0.55 * math.cos(a), Y(d), zc + 0.55 * math.sin(a))) - e.matrix_world.translation)
    bmesh.ops.convex_hull(bm, input=bm.verts); bmesh.ops.triangulate(bm, faces=bm.faces)
    me = bpy.data.meshes.new(f'engines_{side}_colmesh'); bm.to_mesh(me); bm.free()
    h = bpy.data.objects.new(f'engines_{side}_colmesh', me); C_COL.objects.link(h); h.parent = e; h.matrix_parent_inverse = Matrix.Identity(4); h.hide_render = True
C_COL.hide_render = True; C_GUIDE.hide_render = True
for o in C_FX.objects: o.hide_render = True

exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pb22_vismat.py')).read())

# ================================================================ triangle budget: merge near-coplanar faces of the internals
# (limited dissolve, 5 deg, never across materials or sharp edges; skin, glass and tyres are left exactly as built)
KEEP_TOPO = ('PB22_skin', 'PB22_glass', 'PB22_tyre')
def _internal(o, f):
    m = o.data.materials[f.material_index] if f.material_index < len(o.data.materials) else None
    return m is not None and m.name not in KEEP_TOPO
for o in C_MODEL.objects:
    if o.type != 'MESH' or o.name.startswith(('slimelight', 'nozzle', 'navlight')): continue   # exterior strips and nozzles keep their curves
    bm = bmesh.new(); bm.from_mesh(o.data)
    fs = [f for f in bm.faces if _internal(o, f)]
    if fs:
        es = list({e for f in fs for e in f.edges if all(_internal(o, g) for g in e.link_faces)})
        vs = list({v for e in es for v in e.verts if all(_internal(o, g) for g in v.link_faces)})
        bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(5.0), verts=vs, edges=es, delimit={'MATERIAL', 'SHARP'})
        bm.to_mesh(o.data)
    bm.free()

# ================================================================ UVs: smart project, shared texel density, one atlas per material family
# The painted skin texture is shared by every face with the PB22_skin material, so those faces get the whole atlas
# to themselves (tight concave packing: livery markings and panel lines are painted straight into it, the way the
# stock skins are). Faces of the other materials in the same objects are packed separately on top of it: they use
# other (plain or tiling) materials, so their overlap with the skin islands never shows.
def unwrap(objs, pick=None, world=None):
    """Smart-project the picked faces. Packed into one atlas, or with `world` (metres per UV unit) left at world scale
    for the game's shared tiling structure materials (stock parts run about 2.5 m per UV unit)."""
    bpy.context.view_layer.objects.active = objs[0]
    if bpy.context.object and bpy.context.object.mode != 'OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.context.scene.tool_settings.use_uv_select_sync = False     # pack only the UVs of the selected faces
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='FACE')
    nsel = 0
    for o in objs:                                                  # face selection set in edit mode (object-mode flags get re-derived)
        bm = bmesh.from_edit_mesh(o.data)
        for v in bm.verts: v.select = False
        for e in bm.edges: e.select = False
        for f in bm.faces:
            m = o.data.materials[f.material_index] if f.material_index < len(o.data.materials) else None
            f.select = pick is None or pick(m.name if m else ''); nsel += f.select
        bm.select_flush_mode(); bmesh.update_edit_mesh(o.data)
    if nsel:
        bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.0005, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
        bpy.ops.uv.select_all(action='SELECT')
        bpy.ops.uv.average_islands_scale()
        if world is None:
            bpy.ops.uv.pack_islands(rotate=True, margin_method='FRACTION', margin=0.001, shape_method='CONCAVE')
        else:
            for o in objs:
                bm = bmesh.from_edit_mesh(o.data); uvl = bm.loops.layers.uv.active
                sel = [f for f in bm.faces if f.select]
                a3 = sum(f.calc_area() for f in sel)
                au = sum(abs(sum((l[uvl].uv.x * l.link_loop_next[uvl].uv.y - l.link_loop_next[uvl].uv.x * l[uvl].uv.y) for l in f.loops)) / 2 for f in sel)
                if a3 <= 0 or au <= 0: continue
                k = math.sqrt(a3 / au) / world
                for f in sel:
                    for l in f.loops: l[uvl].uv = l[uvl].uv * k
                bmesh.update_edit_mesh(o.data)
    bpy.ops.object.mode_set(mode='OBJECT')
skin = [o for o in C_MODEL.objects if o.type == 'MESH' and o.data.materials and o.data.materials[0].name == 'PB22_skin']
mech = [o for o in C_MODEL.objects if o.type == 'MESH' and o not in skin]
if os.environ.get('UV', '1') == '1':
    # skin faces get the packed livery atlas; everything else is at stock world scale for jet_mechanical / aircraft_structure
    unwrap(skin, lambda mn: mn != 'PB22_skin', world=2.5); unwrap(skin, lambda mn: mn == 'PB22_skin'); unwrap(mech, world=2.5)

tris = 0
for o in C_MODEL.objects:
    if o.type == 'MESH': tris += sum(len(p.vertices) - 2 for p in o.data.polygons)
from pb22_pose import apply_pose
apply_pose(**{k.lower(): float(v) for k, v in os.environ.items() if k in ('SWEEP', 'GEAR', 'FLAP', 'SLAT', 'SPOILER', 'ELEV', 'RUDDER', 'BAY')})
print('PARTS', len(PARTS), 'LOD0 tris', tris, 'colmesh', len(C_COL.objects))
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print('saved', OUT)
