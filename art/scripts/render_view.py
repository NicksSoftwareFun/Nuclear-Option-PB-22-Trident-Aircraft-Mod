"""Quick single view for checking details. Usage: python3 render_view.py <blend> <out.png> cx,cy,cz tx,ty,tz [lens] [samples]"""
import bpy, sys, math
from mathutils import Vector
a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
bpy.ops.wm.open_mainfile(filepath=a[0])
sc = bpy.context.scene
for n in ('GUIDES', 'COLLISION'):
    if n in bpy.data.collections:
        for o in bpy.data.collections[n].all_objects:
            if o: o.hide_render = True
sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = int(a[5]) if len(a) > 5 else 12; sc.cycles.use_denoising = True
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.92, 0.93, 0.95, 1); w.node_tree.nodes['Background'].inputs['Strength'].default_value = 0.8
sun = bpy.data.objects.new('sun', bpy.data.lights.new('sun', 'SUN')); sc.collection.objects.link(sun)
sun.data.energy = 3.5; sun.rotation_euler = (math.radians(40), math.radians(15), math.radians(35))
sc.render.use_freestyle = True; sc.render.line_thickness_mode = 'ABSOLUTE'; sc.render.line_thickness = 1.0
vl = sc.view_layers[0]; ls = vl.freestyle_settings.linesets[0] if vl.freestyle_settings.linesets else vl.freestyle_settings.linesets.new('ls')
ls.select_by_visibility = True; ls.select_silhouette = True; ls.select_border = False; ls.select_crease = True
sc.view_settings.view_transform = 'Standard'; sc.render.resolution_x = 1600; sc.render.resolution_y = 1000
for o in sc.objects:
    if o.type == 'MESH':
        for p in o.data.polygons: p.use_smooth = True
objs = [o for o in sc.objects if o.type == 'MESH']
for o in objs: o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, 0))
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
c = Vector(map(float, a[2].split(','))); t = Vector(map(float, a[3].split(',')))
cam.location = c; cam.rotation_mode = 'QUATERNION'; cam.rotation_quaternion = (t - c).to_track_quat('-Z', 'Y')
cam.data.lens = float(a[4]) if len(a) > 4 else 35; cam.data.clip_start = 0.05
sc.render.filepath = a[1]; bpy.ops.render.render(write_still=True)
