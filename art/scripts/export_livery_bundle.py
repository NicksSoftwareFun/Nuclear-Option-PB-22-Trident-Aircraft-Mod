"""Export the complete PB-22 exterior for livery painting (the repo's Livery Bundle).
Usage: python3 export_livery_bundle.py <pb22_detail.blend> <out_dir>
Writes <out_dir>/PB22 Exterior.fbx: every part of the aircraft at its place (gear up, doors and bays shut, wings
forward), named by part, with the in-game UVs. Every skin face is kept; other faces only when they can be seen from
outside. The livery goes
on material PB22_skin, which points at 'PB22 Base.png' in the same folder, so Blender shows the base colour as soon
as the FBX is imported. Internals (frames, systems, cabin, bulkhead and end caps) are left out.
Also writes <out_dir>/PB22 UV Layout.png (island outlines, 2048 px, transparent)."""
import bpy, bmesh, sys, os, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pb22_pose import apply_pose
a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
src, outdir = a[0], a[1]; os.makedirs(outdir, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=src)
apply_pose(gear=1.0, doors=0.0, sweep=0.0)
bpy.context.view_layer.update()
objs = [o for o in bpy.data.collections['MODEL'].objects if o.type == 'MESH' and len(o.data.polygons) and not o.hide_render]
vs, ps = [], []
for o in objs:
    mw = o.matrix_world; n0 = len(vs)
    vs.extend(mw @ v.co for v in o.data.vertices)
    ps.extend([n0 + i for i in p.vertices] for p in o.data.polygons)
tree = BVHTree.FromPolygons(vs, ps)
dirs = []
for i in range(64):
    z = 1 - 2 * (i + 0.5) / 64; r = math.sqrt(max(0.0, 1 - z * z)); t = i * 2.39996323
    dirs.append(Vector((r * math.cos(t), r * math.sin(t), z)))
def outside(p, n):
    for d in sorted(dirs, key=lambda d: -d.dot(n)):
        if d.dot(n) < -0.2: break                      # only look out of the face's own side
        if tree.ray_cast(p + d * 0.004, d, 80.0)[0] is None: return True
    return False
col = bpy.data.collections.new('LIVERY'); bpy.context.scene.collection.children.link(col)
kept = drop = 0; parts = []
for o in objs:
    b = bmesh.new(); b.from_mesh(o.data); b.transform(o.matrix_world); b.normal_update()
    sk = {i for i, m in enumerate(o.data.materials) if m and m.name == 'PB22_skin'}
    kill = [f for f in b.faces if f.material_index not in sk and not outside(f.calc_center_median(), f.normal)]
    drop += len(kill)
    bmesh.ops.delete(b, geom=kill, context='FACES')
    bmesh.ops.delete(b, geom=[v for v in b.verts if not v.link_faces], context='VERTS')
    if not b.faces: b.free(); continue
    kept += len(b.faces)
    me = bpy.data.meshes.new(o.name); b.to_mesh(me); b.free()
    for m in o.data.materials: me.materials.append(m)
    n = bpy.data.objects.new(o.name + '__lb', me); col.objects.link(n); parts.append(n)
for o in objs: o.name = o.name + '__src'; o.data.name = o.data.name + '__src'
for n in parts: n.name = n.name[:-4]; n.data.name = n.name
# drop material slots a part no longer uses
for n in parts:
    me = n.data; used = sorted({p.material_index for p in me.polygons})
    keep = [me.materials[i] for i in used]; remap = {u: k for k, u in enumerate(used)}
    idx = [remap[p.material_index] for p in me.polygons]
    me.materials.clear()
    for m in keep: me.materials.append(m)
    for p, k in zip(me.polygons, idx): p.material_index = k
print('exterior faces kept', kept, 'hidden faces dropped', drop, 'parts', len(parts))
# the skin material shows the base colour from the bundle folder
sk = bpy.data.materials['PB22_skin']; sk.use_nodes = True
nt = sk.node_tree
bsdf = next((x for x in nt.nodes if x.type == 'BSDF_PRINCIPLED'), None) or nt.nodes.new('ShaderNodeBsdfPrincipled')
img = bpy.data.images.new('PB22 Base', 16, 16); img.source = 'FILE'; img.filepath = '//PB22 Base.png'
tx = nt.nodes.new('ShaderNodeTexImage'); tx.image = img
nt.links.new(tx.outputs['Color'], bsdf.inputs['Base Color'])
for c in list(bpy.context.scene.collection.children):
    if c.name != 'LIVERY': bpy.context.view_layer.layer_collection.children[c.name].exclude = True
bpy.ops.object.select_all(action='DESELECT')
for n in parts: n.select_set(True)
bpy.context.view_layer.objects.active = parts[0]
bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
bpy.ops.export_scene.fbx(filepath=os.path.join(outdir, 'PB22 Exterior.fbx'), use_selection=True, apply_unit_scale=True,
    apply_scale_options='FBX_SCALE_UNITS', axis_forward='-Z', axis_up='Y', object_types={'MESH'}, mesh_smooth_type='FACE',
    use_mesh_modifiers=False, add_leaf_bones=False, use_tspace=True, path_mode='STRIP')
# UV layout of the livery atlas
from PIL import Image, ImageDraw
S = 2048; im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
for n in parts:
    me = n.data; si = {i for i, m in enumerate(me.materials) if m and m.name == 'PB22_skin'}
    if not si or not me.uv_layers: continue
    uv = me.uv_layers.active.data
    for p in me.polygons:
        if p.material_index not in si: continue
        pts = [(uv[li].uv.x * S, (1 - uv[li].uv.y) * S) for li in p.loop_indices]
        dr.line(pts + [pts[0]], fill=(255, 255, 255, 255), width=1)
im.save(os.path.join(outdir, 'PB22 UV Layout.png'))
print('tris', sum(sum(len(p.vertices) - 2 for p in n.data.polygons) for n in parts))
