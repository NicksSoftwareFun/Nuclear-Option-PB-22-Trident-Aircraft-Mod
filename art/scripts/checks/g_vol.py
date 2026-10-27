import bpy, bmesh, sys
bpy.ops.wm.open_mainfile(filepath=sys.argv[1])
for o in sorted(bpy.data.objects, key=lambda o:o.name):
    if o.type!='MESH' or o.users_collection[0].name not in ('MODEL',): continue
    bm=bmesh.new(); bm.from_mesh(o.data)
    man=all(e.is_manifold for e in bm.edges)
    v=bm.calc_volume(signed=True); bm.free()
    if v<0: print('NEG', o.name, round(v,4), 'manifold' if man else 'open')
