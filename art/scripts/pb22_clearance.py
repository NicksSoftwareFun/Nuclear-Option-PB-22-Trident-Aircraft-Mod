"""Clearance numbers for review gates. Usage: python3 pb22_clearance.py <blend>
Prints min |x| of the outer wing panels (nacelle wall is x=2.06), min |x| / z range of the main
gear wheels (rear bay edge is x=1.0), and the lowest point of the Piledriver proxies."""
import bpy, sys
from mathutils import Vector
bpy.ops.wm.open_mainfile(filepath=sys.argv[-1]); bpy.context.view_layer.update()
def verts(o): return [o.matrix_world @ v.co for v in o.data.vertices]
def pts(prefixes):
    out = []
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name.startswith(prefixes): out += verts(o)
    return out
w = pts(('wing1_',)); print(f'wing1 min|x| {min(abs(p.x) for p in w):.2f}  (nacelle wall 2.06)')
g = pts(('wheel_L', 'wheel_R', 'bogey_')); print(f'main wheels/bogie min|x| {min(abs(p.x) for p in g):.2f}  z {min(p.z for p in g):.2f}..{max(p.z for p in g):.2f}  (bay edge 1.0)')
pd = pts(('PD_mid',)); print(f'mid Piledriver lowest z {min(p.z for p in pd):.2f}')
pd = pts(('PD_glove',)); print(f'glove Piledriver lowest z {min(p.z for p in pd):.2f}')
