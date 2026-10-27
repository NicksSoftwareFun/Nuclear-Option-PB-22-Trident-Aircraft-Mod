"""Re-cast the sample sight line of chosen g_leaks findings and print the faces along it.
Usage: python3 g_leak_probe.py <blend> <leaks.json> <i> [<i> ...]   (finding indexes, 0 = most hits)"""
import os, bpy, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from pb22_pose import apply_pose
from pb22_lib import NOSE_Y
blend, js = sys.argv[1], sys.argv[2]; ids = [int(a) for a in sys.argv[3:]]
J = json.load(open(js))
bpy.ops.wm.open_mainfile(filepath=blend)
if J['pose'] == 'up': apply_pose(gear=1.0, doors=0.0, sweep=20.0)
else: apply_pose(gear=0.0, doors=1.0, sweep=0.0)
bpy.context.view_layer.update()
objs = [o for o in bpy.data.objects if o.type == 'MESH' and o.users_collection and o.users_collection[0].name == 'MODEL' and len(o.data.polygons)]
dg = bpy.context.evaluated_depsgraph_get(); trees = []
for o in objs:
    me = o.evaluated_get(dg).to_mesh(); M = o.matrix_world
    trees.append((o, BVHTree.FromPolygons([M @ v.co for v in me.vertices], [tuple(p.vertices) for p in me.polygons]),
                  [o.material_slots[p.material_index].material.name if o.material_slots and o.material_slots[p.material_index].material else '' for p in me.polygons]))
for i in ids:
    f = J['findings'][i]; s = f['sample']
    P = Vector((s[0], NOSE_Y - s[1], s[2])); toward = Vector((s[3], -s[4], s[5])).normalized()
    org = P + toward * 30; dvec = -toward
    hits = []
    for o, t, mats in trees:
        st = org
        for _ in range(6):
            loc, n, idx, dist = t.ray_cast(st, dvec, 60)
            if loc is None: break
            hits.append(((loc - org).length, o.name, idx, mats[idx], round(n.dot(dvec), 2), tuple(round(c, 3) for c in (loc.x, NOSE_Y - loc.y, loc.z))))
            st = loc + dvec * 1e-4
    hits.sort()
    print(f"#{i} {f['kind']} {f['part']} hits {f['hits']}  sample {s}")
    for h in hits[:6]: print('    %.3f %-18s face %-6d %-14s n.d %+.2f at %s' % h)
