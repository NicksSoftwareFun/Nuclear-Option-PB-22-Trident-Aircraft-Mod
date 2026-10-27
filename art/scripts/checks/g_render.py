"""Gear review renders: python3 g_render.py <blend> <outprefix> view gear,doors gear,doors ...
views: front (ortho, looking aft at the right gear), q34 (low 3/4 from front-outboard), under (from below), side"""
import os, bpy, sys, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from mathutils import Vector
from pb22_pose import apply_pose
a=sys.argv[1:]; blend,outp,view=a[0],a[1],a[2]; states=[tuple(map(float,x.split(','))) for x in a[3:]]
bpy.ops.wm.open_mainfile(filepath=blend)
sc=bpy.context.scene
for n in ('GUIDES','COLLISION','PIVOTS','PROXY_AB4','FX'):
    c=bpy.data.collections.get(n)
    if c:
        for o in c.all_objects:
            if o: o.hide_render=True
sc.render.engine='CYCLES'; sc.cycles.device='CPU'; sc.cycles.samples=10; sc.cycles.use_denoising=True; sc.cycles.max_bounces=3
w=bpy.data.worlds.new('w'); sc.world=w; w.use_nodes=True
w.node_tree.nodes['Background'].inputs['Color'].default_value=(0.92,0.93,0.95,1); w.node_tree.nodes['Background'].inputs['Strength'].default_value=0.6
sun=bpy.data.objects.new('sun',bpy.data.lights.new('sun','SUN')); sc.collection.objects.link(sun)
sun.data.energy=3.0; sun.rotation_euler=(math.radians(150),math.radians(-20),math.radians(30))
sun2=bpy.data.objects.new('sun2',bpy.data.lights.new('sun2','SUN')); sc.collection.objects.link(sun2)
sun2.data.energy=1.6; sun2.rotation_euler=(math.radians(35),math.radians(15),math.radians(35))
sc.render.use_freestyle=True; sc.render.line_thickness_mode='ABSOLUTE'; sc.render.line_thickness=1.0
vl=sc.view_layers[0]; ls=vl.freestyle_settings.linesets[0] if vl.freestyle_settings.linesets else vl.freestyle_settings.linesets.new('ls')
ls.select_by_visibility=True; ls.select_silhouette=True; ls.select_border=False; ls.select_crease=True
sc.render.resolution_x=720; sc.render.resolution_y=512; sc.view_settings.view_transform='Standard'
objs=[o for o in sc.objects if o.type=='MESH' and not o.hide_render]
for o in objs: o.select_set(True)
bpy.context.view_layer.objects.active=objs[0]
bpy.ops.object.shade_smooth_by_angle(angle=math.radians(35))
Y=lambda d:17.0-d
cam=bpy.data.objects.new('cam',bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera=cam
if view=='front':
    cam.data.type='ORTHO'; cam.data.ortho_scale=4.6; c=Vector((3.3,Y(14.0),1.15)); t=Vector((3.3,Y(20.9),1.15))
    # cut away everything ahead of the bay so the section reads like the study's front view
    cam.data.clip_start=6.5; cam.data.clip_end=60
elif view=='q34':
    c,t=Vector((8.6,Y(15.6),-0.6)),Vector((3.0,Y(20.9),1.25)); cam.data.lens=34
elif view=='under':
    c,t=Vector((3.3,Y(20.9),-9.0)),Vector((3.3,Y(20.9),1.3)); cam.data.type='ORTHO'; cam.data.ortho_scale=6.5
elif view=='side':
    c,t=Vector((14,Y(20.9),0.9)),Vector((3.0,Y(20.9),0.9)); cam.data.type='ORTHO'; cam.data.ortho_scale=7.0
cam.location=c; cam.rotation_mode='QUATERNION'; cam.rotation_quaternion=(t-c).to_track_quat('-Z','Y' if view!='under' else 'Y')
for i,(g,dr) in enumerate(states):
    apply_pose(gear=g,doors=dr)
    sc.render.filepath=f'{outp}_{view}_{i}.png'; bpy.ops.render.render(write_still=True)
