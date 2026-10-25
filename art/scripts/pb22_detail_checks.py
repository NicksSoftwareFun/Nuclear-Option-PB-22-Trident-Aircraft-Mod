"""Clearance and envelope checks for the detail model. Usage: python3 pb22_detail_checks.py <rest.blend>
Poses the model itself (gear up, wing swept) and prints PASS/FAIL lines."""
import bpy, sys, os
from mathutils import Vector
from mathutils.kdtree import KDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pb22_pose import apply_pose
a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
bpy.ops.wm.open_mainfile(filepath=a[0])
def verts(o):
    return [o.matrix_world @ v.co for v in o.data.vertices]
def objs(prefixes, coll='MODEL'):
    return [o for o in bpy.data.collections[coll].objects if o.type == 'MESH' and o.name.startswith(prefixes)]
def tree(os_):
    pts = [p for o in os_ for p in verts(o)]
    t = KDTree(len(pts))
    for i, p in enumerate(pts): t.insert(p, i)
    t.balance(); return t, pts
def mindist(A, B):
    t, _ = tree(B); best = 1e9
    for o in A:
        for p in verts(o):
            best = min(best, t.find(p)[2])
    return best
import math
PD_GEOM = {}
def pd_dist(name, p):
    x0, d0, z0 = PD_GEOM[name]; L, r, fin = 6.975, 0.425, 0.655
    d = 17.0 - p.y
    best = 1e9
    dx, dz = p.x - x0, p.z - z0
    if d0 <= d <= d0 + L: best = max(math.hypot(dx, dz) - r, 0.0)
    else:
        dd = d0 - d if d < d0 else d - d0 - L
        best = math.hypot(dd, max(math.hypot(dx, dz) - r, 0.0))
    if d0 + L - 0.9 <= d <= d0 + L - 0.1:
        for k in range(4):
            a = math.radians(45 + 90 * k); ux, uz = math.cos(a), math.sin(a)
            t = min(max(dx * ux + dz * uz, r), fin)
            best = min(best, math.hypot(dx - ux * t, dz - uz * t))
    return best
def pd_min(name, os_):
    return min(pd_dist(name, p) for o in os_ for p in verts(o))
def report(name, ok, val):
    print(('PASS ' if ok else 'FAIL ') + name + ': ' + val)
from mathutils import Vector as V
Y = lambda d: 17.0 - d
apply_pose()
# tyre to glove Piledriver (gear down)
for s, sg in (('R', 1), ('L', -1)):
    PD_GEOM[f'PD_glove_{s}'] = (sg * 3.9, 17.0, 2.30 - 0.50 - 0.425); PD_GEOM[f'PD_mid_{s}'] = (sg * 1.55, 11.6, 1.30 - 0.10 - 0.425)
for s in ('R', 'L'):
    g = pd_min(f'PD_glove_{s}', objs((f'wheel_{s}', f'gearDoor_{s}', f'bogey_{s}', f'gear_{s}')))
    report(f'tyres, legs and doors to glove PD {s}', g >= 0.20, f'{g:.3f} m (need >= 0.20)')
    g = pd_min(f'PD_glove_{s}', objs((f'gearbay_{s}',)))
    report(f'gear pod (fixed) to glove PD fins {s}', g >= 0.10, f'{g:.3f} m (need >= 0.10)')
# mid Piledriver to belly / intakes
body = objs(('fuselage', 'intake_', 'gearDoor_F'))
for s in ('R', 'L'):
    g = pd_min(f'PD_mid_{s}', body)
    report(f'mid PD to belly {s}', g >= 0.05, f'{g:.3f} m (need >= 0.05)')
lo = min(p.z for p in verts(bpy.data.objects['PD_mid_R']))
report('mid PD ground clearance', lo >= 0.25, f'{lo:.2f} m')
# gear up envelope
apply_pose(gear=1.0)
bad = []
for o in objs(('gear_L', 'gear_R', 'gear_unsprung_L', 'gear_unsprung_R', 'bogey_', 'wheel_L', 'wheel_R', 'arm')):
    for p in verts(o):
        ax = abs(p.x); d = 17.0 - p.y
        inside_d = 19.25 <= d <= 22.55 or (ax > 2.06 and 18.6 <= d <= 23.4)
        if ax <= 2.10: ok = 1.30 <= p.z and ax >= 1.08
        elif ax <= 3.36: ok = 1.70 <= p.z <= 2.45
        else: ok = False
        if not (ok and inside_d): bad.append((o.name, round(p.x, 2), round(d, 2), round(p.z, 2)))
report('main gear stowed inside well/pod', not bad, f'{len(bad)} verts outside' + (f', e.g. {bad[:4]}' if bad else ''))
bad = []
for o in objs(('gear_F', 'gear_unsprung_F', 'wheel_F')):
    for p in verts(o):
        d = 17.0 - p.y
        if not (10.15 <= d <= 12.58 and abs(p.x) <= 0.42 and p.z >= 1.30): bad.append((o.name, round(p.x, 2), round(d, 2), round(p.z, 2)))
report('nose gear stowed inside well', not bad, f'{len(bad)} verts outside' + (f', e.g. {bad[:4]}' if bad else ''))
print('     stowed main gear top z %.2f' % max(p.z for o in objs(('gear_R', 'bogey_R', 'wheel_R', 'arm')) for p in verts(o)))
k = bpy.data.objects['arm_R']['knee']; print('     right knee stowed at x %.2f d %.2f z %.2f' % (k[0], 17 - k[1], k[2]))
# swept wing
apply_pose(sweep=45.0, gear=1.0)
mx = min(abs(p.x) for o in objs(('wing1_', 'flap_', 'slat_', 'spoiler_')) for p in verts(o))
report('swept wing clear of nacelle', mx >= 2.10, f'min |x| {mx:.2f} (nacelle 2.06)')
# overall dims (rest)
apply_pose()
allv = [p for o in bpy.data.collections['MODEL'].objects if o.type == 'MESH' for p in verts(o)]
L = max(p.y for p in allv) - min(p.y for p in allv); W = max(p.x for p in allv) - min(p.x for p in allv); H = max(p.z for p in allv)
report('length', abs(L - 34.0) < 0.3, f'{L:.2f} m'); report('span 20 deg', abs(W - 27.4) < 0.3, f'{W:.2f} m'); report('height', H <= 7.84, f'{H:.3f} m (limit 7.84)')
tris = sum(len(p.vertices) - 2 for o in bpy.data.collections['MODEL'].objects if o.type == 'MESH' for p in o.data.polygons)
report('LOD0 triangles', 90000 <= tris <= 120000, str(tris))
