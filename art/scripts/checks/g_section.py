import bpy, sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree
bpy.ops.wm.open_mainfile(filepath=sys.argv[sys.argv.index('--') + 1])
dg=bpy.context.evaluated_depsgraph_get()
skip=('gear','arm','bogey','wheel','Door','colmesh','bayDoor','pylon','Pylon')
objs=[o for o in bpy.data.objects if o.type=='MESH' and o.users_collection[0].name=='MODEL' and not any(k in o.name for k in skip)]
trees={o.name:BVHTree.FromObject(o,dg) for o in objs}
mats={o.name:o.matrix_world for o in objs}
def cast(p,d):
    best=None
    for n,t in trees.items():
        M=mats[n]; Mi=M.inverted()
        lp=Mi@p; ld=(Mi.to_3x3()@d).normalized()
        h=t.ray_cast(lp,ld,100)
        if h[0] is not None:
            w=M@h[0]; dist=(w-p).length
            if best is None or dist<best[0]: best=(dist,n,w)
    return best
for d in (19.0,20.0,21.0,22.0,23.0):
    Yv=17-d; row=[]
    for xi in range(0,56,2):
        x=xi/10
        b=cast(Vector((x,Yv,-5)),Vector((0,0,1)))
        row.append(f"{x:.1f}:{b[1][:6]}@{b[2].z:.2f}" if b else f"{x:.1f}:-")
    print('d',d,' '.join(row))
