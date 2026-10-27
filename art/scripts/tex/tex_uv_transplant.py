"""Quick mode for a full model rebuild: give the new build the old build's UVs wherever a face is unchanged.
A rebuild re-packs the whole UV atlas (smart project + pack run over every part), so even a small model change would
otherwise need a full bake. This matches faces by their vertex positions (0.1 mm) and copies the old UVs over.
Faces whose outline changed but whose corners all sit on old vertices of the same part and material (the n-gon
dissolve can merge a little differently from run to run) take the old UVs per corner; where an old vertex sits on a
UV seam, the candidate nearest the face's other corners wins.
Usage: python3 tex_uv_transplant.py <old.blend> <new.blend> <out.blend>
Prints, per part and material, the faces that found no match. Unmatched faces in the painted atlases
(PB22_skin / PB22_mech / PB22_glass) need atlas space, so then the script exits 2 (do a full bake); unmatched faces
in the world-scale materials (structure, honeycomb, ...) keep their new UVs, which are scale-only unwraps anyway."""
import bpy, sys
from collections import defaultdict
ATLAS = ('PB22_skin', 'PB22_mech', 'PB22_glass')
a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
old_path, new_path, out_path = a[:3]
q = lambda v: (round(v.x, 4), round(v.y, 4), round(v.z, 4))

VUV = {}                                             # (part, material, vertex) -> old UVs at that corner
def face_uvs(blend):
    bpy.ops.wm.open_mainfile(filepath=blend)
    out = {}
    for o in bpy.data.collections['MODEL'].objects:
        if o.type != 'MESH' or not o.data.uv_layers: continue
        me = o.data; mw = o.matrix_world; uv = me.uv_layers.active.data
        vw = [q(mw @ v.co) for v in me.vertices]
        d = {}
        for p in me.polygons:
            key = tuple(sorted(vw[i] for i in p.vertices))
            d[key] = {vw[me.loops[li].vertex_index]: tuple(uv[li].uv) for li in p.loop_indices}
            mat = me.materials[p.material_index].name if p.material_index < len(me.materials) and me.materials[p.material_index] else ''
            for li in p.loop_indices:
                c = VUV.setdefault((o.name, mat, vw[me.loops[li].vertex_index]), [])
                t = tuple(uv[li].uv)
                if all(abs(t[0] - u[0]) + abs(t[1] - u[1]) > 1e-6 for u in c): c.append(t)
        out[o.name] = d
    return out

old = face_uvs(old_path)
bpy.ops.wm.open_mainfile(filepath=new_path)
miss = defaultdict(int); hit = 0; bad = 0; hit2 = [0]
for o in bpy.data.collections['MODEL'].objects:
    if o.type != 'MESH' or not o.data.uv_layers: continue
    me = o.data; mw = o.matrix_world; uv = me.uv_layers.active.data
    vw = [q(mw @ v.co) for v in me.vertices]
    d = old.get(o.name, {})
    for p in me.polygons:
        key = tuple(sorted(vw[i] for i in p.vertices))
        m = d.get(key)
        mat = me.materials[p.material_index].name if p.material_index < len(me.materials) and me.materials[p.material_index] else ''
        if m is None:
            cands = [VUV.get((o.name, mat, vw[me.loops[li].vertex_index])) for li in p.loop_indices]
            if not all(cands):
                miss[(o.name, mat)] += 1; continue
            ref = [c[0] for c in cands if len(c) == 1]
            if not ref:
                miss[(o.name, mat)] += 1; continue
            cx, cy = sum(u[0] for u in ref) / len(ref), sum(u[1] for u in ref) / len(ref)
            for li, c in zip(p.loop_indices, cands):
                uv[li].uv = min(c, key=lambda u: (u[0] - cx) ** 2 + (u[1] - cy) ** 2)
            hit2[0] += 1; continue
        for li in p.loop_indices: uv[li].uv = m[vw[me.loops[li].vertex_index]]
        hit += 1
print('faces matched', hit, 'matched by corners', hit2[0])
atlas_miss = 0
for (n, mat), c in sorted(miss.items()):
    flag = mat in ATLAS
    atlas_miss += c if flag else 0
    print('  unmatched %-24s %-12s %5d%s' % (n, mat, c, '  << atlas' if flag else ''))
bpy.context.scene['quick_changed'] = ','.join(sorted({n for (n, mat) in miss}))
bpy.ops.wm.save_as_mainfile(filepath=out_path)
print('saved', out_path, 'changed parts:', bpy.context.scene['quick_changed'])
if atlas_miss:
    print('%d atlas faces have no old UVs: full bake needed' % atlas_miss); sys.exit(2)
