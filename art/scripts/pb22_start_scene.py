"""PB-22 Trident (Tu-22M3-based) starter scene: scale guides, pivots and clearance proxies (game metres).
Blender axes: X right, Y forward (nose at +Y), Z up, ground at Z=0.
Run: python3 pb22_start_scene.py <out.blend>
Everything here is a guide object in the GUIDES collection (never exported) plus named pivot
empties in PIVOTS that the modelling script should parent parts to."""
import bpy, sys, math
out=sys.argv[-1]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc=bpy.context.scene
sc.unit_settings.system='METRIC'; sc.unit_settings.scale_length=1.0

# ---- fixed numbers (see tu22_research.md / BUILD_GUIDE.md section 2)
LENGTH=34.0            # nose tip to tail cone, game m
SPAN_SPREAD=27.4       # at 20 deg sweep
SPAN_SWEPT=18.6        # at 65 deg sweep
MAX_HEIGHT=7.84        # fin tip on gear, after 0.30 m gear drop + 0.70 m fin cut
DOOR_W, DOOR_H = 45.78, 8.00
NOSE_Y=LENGTH/2        # aircraft centred on Y=0 for now; re-centre on CoM later
MID_PYLON_X=1.55; GLOVE_PYLON_X=3.9
PD_LEN, PD_DIA, PD_FIN = 6.975, 0.85, 1.31   # Piledriver, game mesh
S=0.8  # real->game scale for any real-world measurement taken from drawings

def coll(name):
    c=bpy.data.collections.new(name); sc.collection.children.link(c); return c
G=coll('GUIDES'); P=coll('PIVOTS'); M=coll('MODEL')
def link(o,c):
    for u in o.users_collection: u.objects.unlink(o)
    c.objects.link(o)
def wire_box(name,size,loc,c=G):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc); o=bpy.context.object
    o.name=name; o.scale=size; o.display_type='WIRE'; o.hide_render=True; link(o,c); return o
def empty(name,loc,c=P,kind='ARROWS',size=0.5,rot=(0,0,0)):
    o=bpy.data.objects.new(name,None); o.empty_display_type=kind; o.empty_display_size=size
    o.location=loc; o.rotation_euler=rot; c.objects.link(o); return o
def line(name,pts,c=G):
    cu=bpy.data.curves.new(name,'CURVE'); cu.dimensions='3D'
    sp=cu.splines.new('POLY'); sp.points.add(len(pts)-1)
    for p,(x,y,z) in zip(sp.points,pts): p.co=(x,y,z,1)
    o=bpy.data.objects.new(name,cu); c.objects.link(o); o.hide_render=True; return o

# hangar door frame (looking along Y), envelope boxes
line('hangar_door_8m',[(-DOOR_W/2,0,0),(-DOOR_W/2,0,DOOR_H),(DOOR_W/2,0,DOOR_H),(DOOR_W/2,0,0)])
line('max_height_7.84',[(-15,-20,MAX_HEIGHT),(15,-20,MAX_HEIGHT),(15,20,MAX_HEIGHT),(-15,20,MAX_HEIGHT),(-15,-20,MAX_HEIGHT)])
wire_box('envelope_spread',(SPAN_SPREAD,LENGTH,MAX_HEIGHT),(0,0,MAX_HEIGHT/2))
wire_box('envelope_swept_span',(SPAN_SWEPT,LENGTH,0.05),(0,0,0.025))
bpy.ops.mesh.primitive_plane_add(size=120); g=bpy.context.object; g.name='ground'; link(g,G)

# Piledriver clearance proxies on the four pylons (cylinders, nose at +Y)
def piledriver(name,x,y_nose,z_centre):
    bpy.ops.mesh.primitive_cylinder_add(radius=PD_DIA/2,depth=PD_LEN,location=(x,y_nose-PD_LEN/2,z_centre),rotation=(math.radians(90),0,0),vertices=24)
    o=bpy.context.object; o.name=name; o.display_type='WIRE'; link(o,G)
    bpy.ops.mesh.primitive_cube_add(size=1,location=(x,y_nose-PD_LEN+0.6,z_centre)); f=bpy.context.object
    f.name=name+'_fins'; f.scale=(PD_FIN*0.7071,1.2,PD_FIN*0.7071); f.rotation_euler=(0,math.radians(45),0); f.display_type='WIRE'; link(f,G)
# schematic positions from pb22_piledriver_loadout.svg (nose-referenced), converted to centred Y
for sd in (1,-1):
    piledriver(f'PD_mid_{"R" if sd>0 else "L"}',sd*MID_PYLON_X,NOSE_Y-11.6,0.715)
    piledriver(f'PD_glove_{"R" if sd>0 else "L"}',sd*GLOVE_PYLON_X,NOSE_Y-15.4,1.035)

# reused AB-4 bays: two 2.0 m wide openings on the centreline (forward ~5.7 m, rear ~5.4 m)
wire_box('bay_forward_AB4',(2.0,5.7,1.6),(0,NOSE_Y-13.0-5.7/2,1.2))
wire_box('bay_rear_AB4',(2.0,5.4,1.6),(0,NOSE_Y-13.0-5.7-0.3-5.4/2,1.2))
# open bay doors hang 1.0 m below the hinge line at x=+-1.0
for sd in (1,-1):
    wire_box(f'bay_door_open_{"R" if sd>0 else "L"}',(0.06,11.4,1.0),(sd*1.0,NOSE_Y-13.0-5.7,0.4))

# pivot empties named for the Unity hierarchy (positions are first guesses from the schematic; move them to the drawings)
empty('CoM',(0,-1.0,2.3),kind='SPHERE',size=0.4)
for sd,s in ((-1,'L'),(1,'R')):
    empty(f'wingHinge_{s}a',(sd*4.3,NOSE_Y-17.1,2.3),kind='SINGLE_ARROW',size=1.5)   # vertical swing axis on the glove
    empty(f'gearHinge_{s}',(sd*2.6,NOSE_Y-17.5,1.6))
    empty(f'flapHinge_{s}1',(sd*8.0,NOSE_Y-19.6,2.1))
    empty(f'elevatorHinge_{s}1',(sd*2.4,NOSE_Y-29.6,2.8))
    empty(f'pylonMount_glove_{s}',(sd*GLOVE_PYLON_X,NOSE_Y-17.2,1.66))
    empty(f'pylonMount_mid_{s}',(sd*MID_PYLON_X,NOSE_Y-13.4,1.14))
empty('gearhinge_F',(0,NOSE_Y-6.9,1.3))
empty('rudder_hinge1',(0,NOSE_Y-31.0,3.6),kind='SINGLE_ARROW',size=2)
empty('weaponBay_forward',(0,NOSE_Y-15.85,1.0)); empty('weaponBay_rear',(0,NOSE_Y-21.6,1.0)); empty('weaponBay_combined',(0,NOSE_Y-18.7,1.0))
empty('nozzle_L',(-0.9,-LENGTH/2+2.2,2.2)); empty('nozzle_R',(0.9,-LENGTH/2+2.2,2.2))

# reference image planes: drop 3-view images into refs and set these paths (empties of type IMAGE)
for name,loc,rot in (('REF_top',(0,0,-0.01),(0,0,0)),('REF_side',(-30,0,0),(math.radians(90),0,math.radians(-90))),('REF_front',(0,-40,0),(math.radians(90),0,0))):
    e=bpy.data.objects.new(name,None); e.empty_display_type='IMAGE'; e.empty_display_size=LENGTH
    e.location=loc; e.rotation_euler=rot; G.objects.link(e)
bpy.ops.wm.save_as_mainfile(filepath=out)
print('saved',out)
