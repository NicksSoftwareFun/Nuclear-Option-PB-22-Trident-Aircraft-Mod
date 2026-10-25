"""Review renders for the PB-22 model, same look and angles as render_ingame_refs.py.
Usage: python3 render_pb22.py <model.blend> <outdir> [tag]
Writes PB22_<view>.png for the six review views plus overlay masks (top/side, ortho, 40 px per m)
that compose_overlays.py lays over the D01 three-view."""
import bpy, sys, math, os
from mathutils import Vector
blend, outdir = sys.argv[-2], sys.argv[-1]
if blend.startswith('-') or not blend.endswith('.blend'):
    raise SystemExit('usage: render_pb22.py <model.blend> <outdir>')
os.makedirs(outdir, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene
GUIDE_OBJS = [o for o in bpy.data.collections['GUIDES'].all_objects if o]
for o in GUIDE_OBJS: o.hide_render = True
show_guides = os.environ.get('GUIDES') == '1'
if show_guides:
    for o in GUIDE_OBJS:
        if o.name.startswith('PD_'): o.hide_render = False
    bpy.data.collections['GUIDES'].hide_render = False
objs = [o for o in sc.objects if o.type == 'MESH' and not o.hide_render and o not in GUIDE_OBJS]
mn = Vector((1e9,) * 3); mx = Vector((-1e9,) * 3)
for o in objs:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c); mn = Vector(map(min, mn, w)); mx = Vector(map(max, mx, w))
print('bbox', tuple(round(v, 2) for v in mn), tuple(round(v, 2) for v in mx))
ctr = (mn + mx) / 2; size = mx - mn; R = max(size)
for o in sc.objects:
    if o.type == 'MESH':
        o.data.shade_smooth() if hasattr(o.data, 'shade_smooth') else None
for o in objs:
    bpy.context.view_layer.objects.active = o; o.select_set(True)
bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = int(os.environ.get('SAMPLES', 16)); sc.cycles.use_denoising = True; sc.cycles.max_bounces = 3
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.92, 0.93, 0.95, 1); w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.8
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sc.collection.objects.link(sun)
sun.data.energy = 3.5; sun.rotation_euler = (math.radians(40), math.radians(15), math.radians(35))
sc.render.use_freestyle = True; sc.render.line_thickness_mode = 'ABSOLUTE'; sc.render.line_thickness = 1.0
vl = sc.view_layers[0]
ls = vl.freestyle_settings.linesets[0] if vl.freestyle_settings.linesets else vl.freestyle_settings.linesets.new('ls')
ls.select_by_visibility = True; ls.select_silhouette = True; ls.select_border = False; ls.select_crease = True
ls.linestyle = ls.linestyle or bpy.data.linestyles.new('ink'); ls.linestyle.color = (0.08, 0.08, 0.08)
sc.view_settings.view_transform = 'Standard'
sc.render.resolution_x = 1600; sc.render.resolution_y = 1000
bpy.ops.mesh.primitive_plane_add(size=R * 60, location=(ctr.x, ctr.y, 0)); ground = bpy.context.active_object
gm = bpy.data.materials.new('ground'); ground.data.materials.append(gm)
cam_data = bpy.data.cameras.new('cam'); cam = bpy.data.objects.new('cam', cam_data); sc.collection.objects.link(cam); sc.camera = cam
SHOTS = os.environ.get('SHOTS')
def shoot(tag, direction, ortho=True, target=None, dist=1.05, lens=35, scale=1.15):
    if SHOTS and tag not in SHOTS.split(','): return
    ground.hide_render = direction[2] < 0
    portrait = abs(direction[2]) > 0.99
    sc.render.resolution_x, sc.render.resolution_y = (1000, 1600) if portrait else (1600, 1000)
    d = Vector(direction).normalized(); tgt = Vector(target) if target else ctr
    cam.rotation_mode = 'QUATERNION'
    cam.rotation_quaternion = (-d).to_track_quat('-Z', 'Y')
    if portrait and direction[2] < 0:
        cam.rotation_mode = 'XYZ'; cam.rotation_euler = (3.14159265, 0, 0)
    if ortho:
        cam_data.type = 'ORTHO'; cam_data.ortho_scale = R * scale * (1.15 if portrait else 1.0); cam.location = tgt + d * R * 3
    else:
        cam_data.type = 'PERSP'; cam_data.lens = lens; cam.location = tgt + d * R * dist
    cam_data.clip_end = R * 10
    sc.render.filepath = os.path.join(outdir, f'PB22_{tag}.png')
    bpy.ops.render.render(write_still=True)
shoot('1_top', (0, 0.0001, 1))
shoot('2_side', (-1, 0, 0))
shoot('3_front', (0, 1, 0))
shoot('4_3q_front', (0.9, 1.0, 0.55), False)
shoot('5_3q_rear', (-0.9, -1.0, 0.5), False, target=ctr + Vector((0, 0, 0.6)), dist=1.25)
shoot('6_underside', (0, 0.0001, -1))
shoot('7_gear_closeup', (0.45, 1.0, 0.10), False, target=(2.6, -4.3, 1.0), dist=0.30, lens=35)
shoot('8_intake_closeup', (0.8, 1.0, 0.35), False, target=(1.4, 5.5, 2.4), dist=0.32, lens=35)
shoot('9_tail_closeup', (0.9, -1.0, 0.35), False, target=(0, -13.5, 4.2), dist=0.36, lens=35)

# ---- overlay masks: flat red silhouettes, transparent background, fixed 40 px/m framing
if os.environ.get('MASKS', '1') == '1':
    sc.render.use_freestyle = False; sc.render.film_transparent = True; ground.hide_render = True
    red = bpy.data.materials.new('mask'); red.use_nodes = True
    nt = red.node_tree; nt.nodes.clear()
    em = nt.nodes.new('ShaderNodeEmission'); em.inputs['Color'].default_value = (1, 0, 0, 1)
    out = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(em.outputs[0], out.inputs[0])
    for o in objs:
        for i in range(len(o.data.materials)): o.data.materials[i] = red
    cam_data.type = 'ORTHO'; cam_data.ortho_scale = 40.0
    sc.render.resolution_x = 1600; sc.render.resolution_y = 1600
    cam.rotation_mode = 'XYZ'; cam.rotation_euler = (0, 0, 0); cam.location = (0, 0, 50)   # top: nose up in image
    sc.render.filepath = os.path.join(outdir, 'mask_top.png'); bpy.ops.render.render(write_still=True)
    sc.render.resolution_y = 800
    cam.rotation_euler = (math.radians(90), 0, math.radians(-90)); cam.location = (-50, 0, 4.0)  # side: from -X, nose left
    sc.render.filepath = os.path.join(outdir, 'mask_side.png'); bpy.ops.render.render(write_still=True)
print('done')
