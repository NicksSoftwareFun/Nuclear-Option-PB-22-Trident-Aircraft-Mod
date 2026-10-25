"""Preview renders of the PB-22 with the painted skin (Cycles CPU). The .blend is only read, never saved.
Usage: python3 tex_preview.py <pb22_detail.blend> <texdir> <outdir> [only=tag,tag] [samples=24] [res=1600x1000]
The PB22_skin material is rebuilt in memory to the stock AircraftSkin idea: base colour x AO, tangent-space normal
map (OpenGL), metallic = _m.R, roughness = 1 - _m.A (smoothness). Neutral sky + sun, light ground."""
import bpy, sys, os, math
from mathutils import Vector
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from pb22_pose import apply_pose

def coll_objs(c):
    yield from c.objects
    for ch in c.children: yield from coll_objs(ch)

a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
blend, texdir, out = a[0], a[1], a[2]
opts = dict(x.split('=', 1) for x in a[3:])
only = opts['only'].split(',') if 'only' in opts else None
samples = int(opts.get('samples', 24))
rx, ry = (int(v) for v in opts.get('res', '1600x1000').split('x'))
os.makedirs(out, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=blend)
apply_pose()
sc = bpy.context.scene
for n in ('GUIDES', 'COLLISION', 'FX'):
    c = bpy.data.collections.get(n)
    if c:
        for o in coll_objs(c):
            if o: o.hide_render = True
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = samples; sc.cycles.use_denoising = True
sc.cycles.max_bounces = 4
w = bpy.data.worlds.new('sky'); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes['Background']
bg.inputs['Color'].default_value = (0.70, 0.76, 0.86, 1); bg.inputs['Strength'].default_value = 0.85
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sc.collection.objects.link(sun)
sun.data.energy = 3.2; sun.data.angle = math.radians(2.0); sun.data.color = (1.0, 0.97, 0.92)
sun.rotation_euler = (math.radians(42), math.radians(12), math.radians(-40))
if 'sun' in opts:   # sun=rx,ry,rz in degrees
    sun.rotation_euler = tuple(math.radians(float(v)) for v in opts['sun'].split(','))
sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'; sc.view_settings.exposure = -0.55
sc.render.resolution_x = rx; sc.render.resolution_y = ry

def img(name, cs):
    p = os.path.join(texdir, name)
    if not os.path.exists(p): return None
    im = bpy.data.images.load(p); im.colorspace_settings.name = cs; return im

m = bpy.data.materials['PB22_skin']; m.use_nodes = True
nt = m.node_tree; nt.nodes.clear()
o_ = nt.nodes.new('ShaderNodeOutputMaterial'); bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
nt.links.new(bs.outputs[0], o_.inputs[0])
uv = nt.nodes.new('ShaderNodeUVMap')
ib, inn, im_, iao = img('PB22_skin_b.png', 'sRGB'), img('PB22_skin_n.png', 'Non-Color'), img('PB22_skin_m.png', 'Non-Color'), img('PB22_skin_ao.png', 'Non-Color')
def tex(i):
    t = nt.nodes.new('ShaderNodeTexImage'); t.image = i; t.interpolation = 'Linear'; nt.links.new(uv.outputs[0], t.inputs[0]); return t
tb = tex(ib)
col = tb.outputs['Color']
if iao:
    ta = tex(iao)
    mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
    mix.inputs['Factor'].default_value = 0.75
    nt.links.new(col, mix.inputs[6]); nt.links.new(ta.outputs['Color'], mix.inputs[7]); col = mix.outputs[2]
nt.links.new(col, bs.inputs['Base Color'])
if inn and opts.get('normal', '1') == '1':
    tn = tex(inn); nm = nt.nodes.new('ShaderNodeNormalMap'); nm.space = 'TANGENT'
    nt.links.new(tn.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs[0], bs.inputs['Normal'])
if im_:
    tm = tex(im_)
    sep = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(tm.outputs['Color'], sep.inputs[0])
    nt.links.new(sep.outputs[0], bs.inputs['Metallic'])
    inv = nt.nodes.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
    nt.links.new(tm.outputs['Alpha'], inv.inputs[1]); nt.links.new(inv.outputs[0], bs.inputs['Roughness'])
bs.inputs['Specular IOR Level'].default_value = 0.5

objs = [o for o in sc.objects if o and o.type == 'MESH' and not o.hide_render]
for o in objs:
    for p in o.data.polygons: p.use_smooth = True
for o in sc.objects:
    if o: o.select_set(o in objs)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
bpy.ops.mesh.primitive_plane_add(size=600, location=(0, 0, 0)); ground = bpy.context.active_object
gm = bpy.data.materials.new('g'); gm.use_nodes = True
gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.42, 0.43, 0.42, 1)
# PB22_mech as the game shows it: PB22Builder sets URP/Lit colour sRGB (86,94,97)
if 'PB22_mech' in bpy.data.materials:
    mm = bpy.data.materials['PB22_mech']; mm.use_nodes = True
    pb = next((nd for nd in mm.node_tree.nodes if nd.type == 'BSDF_PRINCIPLED'), None)
    if pb:
        pb.inputs['Base Color'].default_value = (0.093, 0.112, 0.120, 1); pb.inputs['Roughness'].default_value = 0.5
        pb.inputs['Metallic'].default_value = 0.0
gm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9
# nozzles: bare brushed metal (PB22Builder.NozzleMetal)
if 'PB22_mech' in bpy.data.materials:
    nm_ = bpy.data.materials['PB22_mech'].copy(); nm_.name = 'PB22_nozzle_metal'
    pb = next((nd for nd in nm_.node_tree.nodes if nd.type == 'BSDF_PRINCIPLED'), None)
    if pb:
        pb.inputs['Base Color'].default_value = (0.50, 0.49, 0.47, 1); pb.inputs['Metallic'].default_value = 0.9
        pb.inputs['Roughness'].default_value = 0.34; pb.inputs['Anisotropic'].default_value = 0.5
    for o in objs:
        if o.name.startswith('nozzle'):
            for sl in o.material_slots:
                if sl.material and sl.material.name == 'PB22_mech': sl.material = nm_
ground.data.materials.append(gm)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.clip_start = 0.05; cam.data.clip_end = 800
def Yd(d): return 17 - d

def shot(tag, loc, tgt, lens=35, ortho=None, ground_on=True, pose=None, res=None):
    if only and tag not in only: return
    ground.hide_render = not ground_on
    if pose: apply_pose(**pose)
    c, t = Vector(loc), Vector(tgt)
    cam.location = c; cam.rotation_mode = 'QUATERNION'; cam.rotation_quaternion = (t - c).to_track_quat('-Z', 'Y')
    if ortho: cam.data.type = 'ORTHO'; cam.data.ortho_scale = ortho
    else: cam.data.type = 'PERSP'; cam.data.lens = lens
    if res: sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = os.path.join(out, tag + '.png'); bpy.ops.render.render(write_still=True)
    sc.render.resolution_x, sc.render.resolution_y = rx, ry
    if pose: apply_pose()
    print('rendered', tag, flush=True)

for _a in eval(os.environ.get('EXTRA_SHOTS', '[]')): shot(*_a[:3], **(_a[3] if len(_a) > 3 else {}))
shot('01_front_3q', (-15.5, Yd(-7.5), 6.8), (0, Yd(14), 2.6), 35)
shot('02_rear_3q', (-12.5, Yd(42), 7.5), (0, Yd(21), 2.8), 35)
shot('03_side_left', (-60, Yd(17), 3.2), (0, Yd(17), 3.2), ortho=36)
shot('04_underside', (0, Yd(17), -60), (0, Yd(17), 0), ortho=36, ground_on=False)
shot('05_top', (0, Yd(17), 60), (0, Yd(17), 0), ortho=36)
shot('06_nose_cockpit', (-4.6, Yd(-1.2), 4.6), (0, Yd(6.2), 2.7), 42)
shot('07_intake', (-6.0, Yd(8.5), 2.2), (-1.5, Yd(13.0), 2.4), 38)
shot('08_glove_spoilers', (-3.5, Yd(29.0), 6.2), (-7.5, Yd(22.5), 2.2), 38, pose=dict(spoiler=1.0, flap=0.6))
shot('09_tail', (-6.5, Yd(38.5), 5.6), (0, Yd(30.5), 3.9), 40)
shot('10_spoiler_under', (-8.0, Yd(27.2), 3.1), (-8.6, Yd(23.6), 2.45), 40, pose=dict(spoiler=1.0, flap=0.0))
shot('11_ingame_distance', (-55.0, Yd(-25.0), 22.0), (0, Yd(16.0), 2.6), 35, res=(960, 600))
shot('12_belly_rear', (-4.0, Yd(36.0), 0.5), (0, Yd(28.0), 2.0), 40)
shot('14_panel_close', (-5.2, Yd(13.0), 4.6), (-1.0, Yd(17.5), 3.0), 45)
shot('13_spine_top', (-3.0, Yd(12.0), 8.0), (0, Yd(22.0), 3.6), 40)
shot('15_cabin_doors', (-5.6, Yd(9.0), 4.3), (0, Yd(8.3), 3.2), 45)
shot('16_markings', (-6.5, Yd(8.2), 2.7), (0, Yd(8.2), 2.4), 40)
shot('17_intake_into', (-1.95, Yd(5.0), 2.25), (-1.3, Yd(20.0), 2.45), 50)
shot('18_pod_gearup', (-9.0, Yd(18.5), -1.2), (-3.2, Yd(21.0), 1.6), 40, pose=dict(gear=1.0), ground_on=False)
