"""Clipping report for the main gear in game order. Retract: fold 0->1 with doors open, then doors 1->0.
Designed contacts (pivots, lugs, telescoping halves, oleo) are skipped; everything else that touches is reported."""
import os, bpy, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from mathutils.bvhtree import BVHTree
from pb22_pose import apply_pose
blend=sys.argv[1]; side=sys.argv[2] if len(sys.argv)>2 else 'R'; steps=int(sys.argv[3]) if len(sys.argv)>3 else 20
bpy.ops.wm.open_mainfile(filepath=blend)
def wbvh(o):
    M=o.matrix_world; me=o.data
    return BVHTree.FromPolygons([M@v.co for v in me.vertices],[tuple(p.vertices) for p in me.polygons])
G=[f'gear_{side}',f'gear_unsprung_{side}',f'bogey_{side}',f'legDoor_{side}',f'actCyl_{side}',f'actRod_{side}',f'braceU_{side}',f'braceL_{side}']
model=[o for o in bpy.data.objects if o.type=='MESH' and o.users_collection[0].name=='MODEL' and len(o.data.polygons)]
gear=[o for o in model if o.name in G or o.name.startswith(f'wheel_{side}')]
doors=[o for o in model if o.name in (f'gearDoor_{side}O',f'gearDoor_{side}I')]
static=[o for o in model if o not in gear and o not in doors and not o.name.startswith(('gear_F','gear_unsprung_F','wheel_F','gearDoor_F'))]
OK={frozenset(p) for p in [(f'actCyl_{side}',f'actRod_{side}'),(f'braceU_{side}',f'braceL_{side}'),(f'actRod_{side}',f'gear_{side}'),
    (f'braceL_{side}',f'gear_{side}'),(f'actCyl_{side}',f'gearbay_{side}'),(f'braceU_{side}',f'gearbay_{side}'),(f'legDoor_{side}',f'gear_{side}'),
    (f'gear_{side}',f'gearbay_{side}'),(f'gear_{side}',f'gear_unsprung_{side}'),(f'gear_unsprung_{side}',f'bogey_{side}'),
    (f'gearDoor_{side}O',f'gearDoor_{side}I'),(f'gearDoor_{side}O',f'gearbay_{side}'),
    (f'actCyl_{side}',f'wingroot_{side}'),(f'braceU_{side}',f'wingroot_{side}'),(f'gear_{side}',f'wingroot_{side}')]}
seq=[('fold',f/steps,1.0) for f in range(0,steps+1)]+[('doors',1.0,d/8) for d in range(7,-1,-1)]
bad=0
for tag,g,dr in seq:
    apply_pose(gear=g,doors=dr)
    B={o.name:wbvh(o) for o in gear+doors+static}
    hits={}
    mv=gear+doors
    for i,a in enumerate(mv):
        for b in mv[i+1:]+static:
            if frozenset((a.name,b.name)) in OK: continue
            if a.name.startswith('wheel') and b.name.startswith(('wheel','bogey')): continue
            if b.name.startswith('wheel') and a.name.startswith(('wheel','bogey')): continue
            n=len(B[a.name].overlap(B[b.name]))
            if n: hits[f'{a.name} x {b.name}']=n
    bad+=len(hits)
    print(f'{tag} gear={g:.2f} doors={dr:.3f}:', '  '.join(f'{k}:{v}' for k,v in sorted(hits.items())) or 'clean')
print('TOTAL pair-frames with contact:',bad)
