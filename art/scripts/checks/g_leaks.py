"""Gap and see-through scan for the PB-22 exterior, no rendering.
Usage: python3 g_leaks.py <blend> <out.json> [rays] [pose: up|down]
Fires random sight lines from outside the aircraft at points spread over every surface and keeps the first thing each
line hits. A hit is reported when, from outside, a line reaches:
  back    - the back side of a face (a hole in a skin, or a part with missing faces); a hit that a 1 mm nudge of the
            line turns into a front face is an edge graze, not a hole, and is not counted
  inner   - an internal-system material (fuel cells and lines, hydraulics, oxygen, wiring)
  stowed  - a landing gear part while the gear is up
  cavity  - a non-skin face inside a bay, well or recess while its doors are shut (pose 'up' only)
Glass is see-through, so lines that hit glass first are skipped (the cockpit is meant to show through it).
Each finding keeps one sample hit with the direction it was seen from (pointing back toward the viewer, in x, d, z).
Hits are grouped in 10 cm cells and listed with the part name and position (x, d = metres aft of the nose, z)."""
import os, bpy, sys, json, math, random
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from pb22_pose import apply_pose
from pb22_lib import NOSE_Y

blend, out = sys.argv[1], sys.argv[2]
N = int(sys.argv[3]) if len(sys.argv) > 3 else 600000
pose = sys.argv[4] if len(sys.argv) > 4 else 'up'
bpy.ops.wm.open_mainfile(filepath=blend)
if pose == 'up': apply_pose(gear=1.0, doors=0.0, sweep=20.0)
else: apply_pose(gear=0.0, doors=1.0, sweep=0.0)
bpy.context.view_layer.update()

INNER = {'PB22_fuelcell', 'PB22_fuelline', 'PB22_hyd', 'PB22_oxy', 'PB22_wire'}
STOWED = ('gear_', 'wheel_', 'bogey_', 'braceU_', 'braceL_', 'actCyl_', 'actRod_', 'gear_unsprung_')
def D(y): return NOSE_Y - y
# cavities as boxes (x0, x1, d0, d1, z0, z1), shrunk 1 cm, from the cutters in build_pb22_detail.py
BOX = [(-0.41, 0.41, 10.16, 12.57, 1.40, 2.34)]                                   # nose wheel well (above the closed doors)
for s in (1, -1):
    for x0, x1, z0, z1 in ((2.09, 3.59, 1.345, 2.29), (3.56, 4.54, 1.345, 2.20)):  # main bays (above the door lips)
        a, b = sorted((s * x0, s * x1)); BOX.append((a, b, 19.26, 22.54, z0, z1))
def inbox(p):
    d = D(p.y)
    return any(b[0] < p.x < b[1] and b[2] < d < b[3] and b[4] < p.z < b[5] for b in BOX)

objs = [o for o in bpy.data.objects if o.type == 'MESH' and o.users_collection and o.users_collection[0].name == 'MODEL'
        and len(o.data.polygons) and not o.hide_render]
verts, polys, info = [], [], []
dg = bpy.context.evaluated_depsgraph_get()
for o in objs:
    me = o.evaluated_get(dg).to_mesh(); M = o.matrix_world; base = len(verts)
    verts.extend(M @ v.co for v in me.vertices)
    for p in me.polygons:
        polys.append([base + i for i in p.vertices])
        mat = o.material_slots[p.material_index].material.name if p.material_index < len(o.material_slots) and o.material_slots[p.material_index].material else ''
        info.append((o.name, mat, p.area * (M.median_scale ** 2)))
    o.evaluated_get(dg).to_mesh_clear()
bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)
lo = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
hi = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
R = (hi - lo).length + 5

# targets: random points on faces, area weighted
cum, tot = [], 0.0
for i, (_, _, a) in enumerate(info): tot += a; cum.append(tot)
import bisect
rnd = random.Random(7)
def sample():
    i = bisect.bisect_left(cum, rnd.random() * tot); pv = [verts[k] for k in polys[i]]
    # random point in a random fan triangle of the polygon
    j = rnd.randrange(1, len(pv) - 1); a, b, c = pv[0], pv[j], pv[j + 1]
    u, v = rnd.random(), rnd.random()
    if u + v > 1: u, v = 1 - u, 1 - v
    return a + (b - a) * u + (c - a) * v
def rdir():
    z = rnd.uniform(-1, 1); t = rnd.uniform(0, 2 * math.pi); r = math.sqrt(1 - z * z)
    return Vector((r * math.cos(t), r * math.sin(t), z))

cells = {}
counts = {'rays': 0, 'glass': 0}
for _ in range(N):
    t = sample(); dvec = rdir(); org = t - dvec * R
    loc, nrm, idx, dist = bvh.ray_cast(org, dvec, 2 * R)
    if loc is None: continue
    counts['rays'] += 1
    name, mat, _ = info[idx]
    if mat == 'PB22_glass': counts['glass'] += 1; continue
    kind = None
    if nrm.dot(dvec) > 0.05 and mat not in ('PB22_tyre',):
        # a line that grazes an edge shared by two faces can report either one: nudge it 1 mm two ways and only
        # count the hit when both nudged lines also see a back face (a real hole is wider than that)
        side = dvec.orthogonal().normalized(); real = True
        for off in (side * 0.001, dvec.cross(side) * 0.001):
            l2, n2, i2, _ = bvh.ray_cast(org + off, dvec, 2 * R)
            if l2 is None or n2.dot(dvec) <= 0.05 or info[i2][1] == 'PB22_glass': real = False; break
        if real: kind = 'back'
    elif mat in INNER: kind = 'inner'
    elif pose == 'up' and name.startswith(STOWED): kind = 'stowed'
    elif pose == 'up' and mat != 'PB22_skin' and inbox(loc): kind = 'cavity'   # outer skin dipping into a box is fine
    if kind is None: continue
    key = (kind, name, round(loc.x, 1), round(D(loc.y), 1), round(loc.z, 1))
    c = cells.setdefault(key, [0, 9.0, -9.0, None])
    c[0] += 1; c[1] = min(c[1], loc.z); c[2] = max(c[2], loc.z)
    if c[3] is None: c[3] = [round(loc.x, 3), round(D(loc.y), 3), round(loc.z, 3), round(-dvec.x, 2), round(dvec.y, 2), round(-dvec.z, 2)]

rows = sorted(({'kind': k[0], 'part': k[1], 'x': k[2], 'd': k[3], 'z': k[4], 'hits': n[0], 'z0': n[1], 'z1': n[2], 'sample': n[3]} for k, n in cells.items()),
              key=lambda r: -r['hits'])
# merge neighbouring cells of the same part and kind into findings
find = []
for r in rows:
    for f in find:
        if f['kind'] == r['kind'] and f['part'] == r['part'] and abs(f['x'] - r['x']) <= 0.35 and abs(f['d'] - r['d']) <= 0.6 and abs(f['z'] - r['z']) <= 0.35:
            f['hits'] += r['hits']; f['cells'] += 1
            f['xr'] = [min(f['xr'][0], r['x']), max(f['xr'][1], r['x'])]; f['dr'] = [min(f['dr'][0], r['d']), max(f['dr'][1], r['d'])]
            f['zr'] = [min(f['zr'][0], r['z0']), max(f['zr'][1], r['z1'])]
            break
    else:
        find.append({'kind': r['kind'], 'part': r['part'], 'x': r['x'], 'd': r['d'], 'z': r['z'], 'hits': r['hits'], 'cells': 1,
                     'xr': [r['x']] * 2, 'dr': [r['d']] * 2, 'zr': [r['z0'], r['z1']], 'sample': r['sample']})
find.sort(key=lambda f: -f['hits'])
json.dump({'pose': pose, 'counts': counts, 'findings': find}, open(out, 'w'), indent=1)
print('pose', pose, counts, 'findings', len(find))
for f in find[:40]:
    print(f"{f['hits']:6d} {f['kind']:7s} {f['part']:24s} x {f['xr'][0]:+.1f}..{f['xr'][1]:+.1f} d {f['dr'][0]:.1f}..{f['dr'][1]:.1f} z {f['zr'][0]:.2f}..{f['zr'][1]:.2f}  seen from (x,d,z dir) {f['sample'][3:]}")
