"""Dump the skin (and mech) atlas geometry of the PB-22 at rest pose for texture painting (tex_geom.py plus a
per-triangle material index: <fam>_mat indexes the list in 'mats').
Usage: python3 tex_geom_m.py <pb22_detail.blend> <out.npz>
Per material family: triangles' UVs, world positions, smooth normals (35 deg auto-smooth, as exported) and part ids."""
import bpy, bmesh, sys, os, math, json
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from pb22_pose import apply_pose
a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
bpy.ops.wm.open_mainfile(filepath=a[0])
apply_pose(doors=0.0)
bpy.context.view_layer.update()
out = {}
names = []
# 1.0.2: the part each face was built in (faces near a rip line changed part); painting places features by it
ONAMES = json.loads(bpy.context.scene['opart_names']) if 'opart_names' in bpy.context.scene else None
mats = []
for fam in ('PB22_skin', 'PB22_mech', 'PB22_glass'):
    UV, P, N, PID, RPID, MAT = [], [], [], [], [], []
    for o in bpy.data.collections['MODEL'].objects:
        if o.type != 'MESH' or not o.data.materials or o.data.materials[0].name != fam: continue
        if o.name not in names: names.append(o.name)
        pid = names.index(o.name)
        me = o.data.copy()
        bm = bmesh.new(); bm.from_mesh(me)
        bmesh.ops.triangulate(bm, faces=bm.faces)
        bm.to_mesh(me); bm.free()
        me.transform(o.matrix_world)
        if o.matrix_world.determinant() < 0: me.flip_normals()
        # smooth by angle like the export
        me.shade_smooth()
        try: me.set_sharp_from_angle(angle=math.radians(35))
        except AttributeError: pass
        me.calc_loop_triangles()
        uvl = me.uv_layers.active.data
        cn = np.array([cl.vector for cl in me.corner_normals]) if hasattr(me, 'corner_normals') else None
        oa = me.attributes.get('opart') if ONAMES is not None else None
        opid = None
        if oa is not None:
            ov = np.zeros(len(me.polygons), np.int32); oa.data.foreach_get('value', ov)
            opid = {}
            for k in set(ov.tolist()):
                nm = ONAMES[k]
                if nm not in names: names.append(nm)
                opid[k] = names.index(nm)
            opid = np.array([opid[k] for k in ov.tolist()], np.int32)
        for t in me.loop_triangles:
            mn = me.materials[t.material_index].name if me.materials and t.material_index < len(me.materials) and me.materials[t.material_index] else fam
            UV.append([tuple(uvl[l].uv) for l in t.loops])
            P.append([tuple(me.vertices[v].co) for v in t.vertices])
            N.append([tuple(cn[l]) if cn is not None else tuple(t.normal) for l in t.loops])
            PID.append(int(opid[t.polygon_index]) if opid is not None else pid)
            RPID.append(pid)               # the part it is in now (the damage seams follow this)
            if mn not in mats: mats.append(mn)
            MAT.append(mats.index(mn))
        bpy.data.meshes.remove(me)
    out[fam + '_uv'] = np.array(UV, np.float32); out[fam + '_p'] = np.array(P, np.float32)
    out[fam + '_n'] = np.array(N, np.float32); out[fam + '_pid'] = np.array(PID, np.int16)
    out[fam + '_mat'] = np.array(MAT, np.int16); out[fam + '_rpid'] = np.array(RPID, np.int16)
    print(fam, len(UV), 'tris')
out['names'] = np.array(names)
out['mats'] = np.array(mats)
np.savez_compressed(a[1], **out)
print('saved', a[1])
