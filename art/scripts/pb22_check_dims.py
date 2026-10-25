"""Dimension and clearance check for the PB-22 Trident model. Run inside Blender (or bpy) on the model .blend.
Prints PASS/FAIL against the fixed numbers. Objects in the GUIDES collection are ignored.
Usage: python3 pb22_check_dims.py <model.blend>"""
import bpy, sys
from mathutils import Vector
bpy.ops.wm.open_mainfile(filepath=sys.argv[-1])
LIMITS=dict(length=34.0, span_spread=27.4, span_swept=18.6, max_height=7.84, door_h=8.00, door_w=45.78)
TOL=0.25
def bbox(objs):
    mn=Vector((1e9,)*3); mx=Vector((-1e9,)*3)
    for o in objs:
        for v in o.data.vertices:
            w=o.matrix_world@v.co; mn=Vector(map(min,mn,w)); mx=Vector(map(max,mx,w))
    return mn,mx
guides=set(bpy.data.collections['GUIDES'].all_objects) if 'GUIDES' in bpy.data.collections else set()
model=[o for o in bpy.context.scene.objects if o.type=='MESH' and o not in guides and not o.hide_get()]
if not model:
    print("NO MODEL: nothing outside GUIDES to check yet"); sys.exit(0)
mn,mx=bbox(model)
L=mx.y-mn.y; W=mx.x-mn.x
def rep(name,val,target,ok):
    print(f'{"PASS" if ok else "FAIL"}  {name:<28} {val:7.2f}  (target {target})')
rep('length',L,LIMITS['length'],abs(L-LIMITS['length'])<=TOL)
rep('span at current sweep',W,f"{LIMITS['span_spread']} spread / {LIMITS['span_swept']} swept",True)
rep('height above ground (fin tip)',mx.z,f"<= {LIMITS['max_height']}",mx.z<=LIMITS['max_height']+1e-3)
rep('door headroom',LIMITS['door_h']-mx.z,'>= 0.15',LIMITS['door_h']-mx.z>=0.15)
rep('lowest point (should be wheels at 0)',mn.z,'0.00',abs(mn.z)<0.02)
rep('fits door width',W,f"<= {LIMITS['door_w']}",W<=LIMITS['door_w'])
