"""Export the PB-22 detail model for Unity (step 4).
Usage: python3 export_pb22.py <pb22_detail.blend> <out_dir>
Writes <out_dir>/PB22_parts.fbx: every MODEL and COLLISION mesh as its own object at the origin, unparented,
vertices in the part's pivot frame with world-aligned axes (rest pose), pre-rotated 180 deg about Z so the
FBX import lands Blender (x, y, z) at Unity (x, z, y) [see export_axis_test.py].
Also writes PB22_layout.json: name, kind, parent, Blender world position and rotation of every MODEL/PIVOTS/
COLLISION/PROXY/FX object, so a Unity editor script can rebuild the transforms."""
import bpy, sys, os, json, math
from mathutils import Matrix, Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pb22_pose import apply_pose
a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
src, outdir = a[0], a[1]; os.makedirs(outdir, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=src)
apply_pose(doors=0.0)   # geometry rest: gear down, every door closed, surfaces neutral
COLLS = ('MODEL', 'PIVOTS', 'COLLISION', 'PROXY_AB4', 'FX')
# Unity builds submeshes in order of first use, so every mesh drops unused slots and has its faces sorted by slot
for me in bpy.data.meshes:
    if not me.materials: continue
    top = len(me.materials) - 1
    for p in me.polygons:
        if p.material_index > top: p.material_index = top   # Blender draws out-of-range slots with the last one
    used = sorted({p.material_index for p in me.polygons})
    if used != list(range(len(me.materials))):
        keep = [me.materials[i] for i in used]; remap = {u: k for k, u in enumerate(used)}
        idx = [remap[p.material_index] for p in me.polygons]
        me.materials.clear()                                  # (clearing the slots resets every face to slot 0)
        for m in keep: me.materials.append(m)
        for p, k in zip(me.polygons, idx): p.material_index = k
        print('dropped unused slots on', me.name)
layout = []
for cname in COLLS:
    for o in bpy.data.collections[cname].objects:
        mw = o.matrix_world
        q = mw.to_quaternion()
        mats = [m.name for m in o.data.materials] if o.type == 'MESH' else []
        layout.append(dict(name=o.name, coll=cname, kind=o.type, parent=o.parent.name if o.parent else None,
                           pos=list(mw.translation), rot=[q.w, q.x, q.y, q.z], mats=mats, keep_frame=bool(o.get('keep_frame')),
                           bmin=[min((mw.to_3x3() @ v.co)[i] for v in o.data.vertices) for i in range(3)] if o.type == 'MESH' else None,
                           bmax=[max((mw.to_3x3() @ v.co)[i] for v in o.data.vertices) for i in range(3)] if o.type == 'MESH' else None))
json.dump(layout, open(os.path.join(outdir, 'PB22_layout.json'), 'w'), indent=1)
# flat export scene
Rz = Matrix.Rotation(math.pi, 4, 'Z')
exp = bpy.data.collections.new('EXPORT'); bpy.context.scene.collection.children.link(exp)
src = [o for cname in ('MODEL', 'COLLISION', 'PROXY_AB4') for o in bpy.data.collections[cname].objects if o.type == 'MESH']
for o in src:
    o.data.name = o.name + '__src'
for o in src:
    if True:
        me = o.data.copy(); me.name = o.name
        # arms keep their own frame (shaft along local +Z, Unity +Y) so an IK aim can drive them; the layout has their rest rotation
        rot = Matrix.Identity(4) if o.get('keep_frame') else o.matrix_world.to_quaternion().to_matrix().to_4x4()
        me.transform(Rz @ rot)
        if rot.to_quaternion().angle > 1e-4: print('baked rotation into', o.name)
        n = bpy.data.objects.new(o.name + '__x', me); exp.objects.link(n)
for o in src: o.name = o.name + '__src'
for c in bpy.context.scene.collection.children:
    if c.name != 'EXPORT': bpy.context.view_layer.layer_collection.children[c.name].exclude = True
for o in exp.objects: o.name = o.name[:-3] if o.name.endswith('__x') else o.name
# hard edges above 35 deg, the same look as the review renders
bpy.ops.object.select_all(action='DESELECT')
for o in exp.objects: o.select_set(True)
bpy.context.view_layer.objects.active = exp.objects[0]
bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
# triangulate every face here (beauty split), the same split tex_geom_m.py paints with, so a straight painted line
# stays straight across warped quads (Unity's own quad split differs) and Unity never splits non-planar n-gon caps itself
import bmesh
for o in exp.objects:
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.triangulate(bm, faces=bm.faces, quad_method='BEAUTY', ngon_method='BEAUTY')
    # 1.0.5: double-sided skin like every stock aircraft. Each skin triangle gets a back-facing twin on the same spot
    # with the same UVs, so the inside of the skin shows (in shadow) through a broken joint or a damage hole and a
    # hairline crack at a joint shows the inside of the aircraft, never the sky. Triangles that already have a
    # reversed twin (thin panels built from both sides) are left alone.
    sk = [i for i, m in enumerate(o.data.materials) if m and m.name == 'PB22_skin']
    if sk and 'colmesh' not in o.name and not o.name.startswith('wheel'):
        key = lambda f: tuple(sorted(tuple(round(c, 5) for c in v.co) for v in f.verts))
        tri = [f for f in bm.faces if f.material_index in sk]
        seen = {}
        for f in tri: seen[key(f)] = seen.get(key(f), 0) + 1
        one = [f for f in tri if seen[key(f)] == 1]
        if one:
            out = bmesh.ops.duplicate(bm, geom=one)
            nf = [g for g in out['geom'] if isinstance(g, bmesh.types.BMFace)]
            bmesh.ops.reverse_faces(bm, faces=nf)
            print('double-sided', o.name, len(nf), 'twins')
    bm.faces.sort(key=lambda f: f.material_index)
    bm.to_mesh(o.data); bm.free()
# LOD1 shells are the colmeshes; stock LOD meshes carry vertex colour (41,41,41) for the LOD shader
for o in exp.objects:
    if 'colmesh' in o.name:
        while o.data.color_attributes: o.data.color_attributes.remove(o.data.color_attributes[0])
        ca = o.data.color_attributes.new('Col', 'BYTE_COLOR', 'CORNER')
        g = 41 / 255
        for d in ca.data: d.color_srgb = (g, g, g, 1.0)
bpy.ops.export_scene.fbx(filepath=os.path.join(outdir, 'PB22_parts.fbx'), use_selection=False, use_active_collection=False,
    apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Z', axis_up='Y', bake_space_transform=True,
    object_types={'MESH'}, mesh_smooth_type='FACE', use_mesh_modifiers=False, add_leaf_bones=False, use_tspace=True)
print('exported', len(exp.objects), 'meshes,', len(layout), 'layout entries')
