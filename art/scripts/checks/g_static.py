import os, bpy, sys, bmesh
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from mathutils.bvhtree import BVHTree
from pb22_pose import apply_pose
bpy.ops.wm.open_mainfile(filepath=sys.argv[1])
def wbvh(o):
    M=o.matrix_world; me=o.data
    return BVHTree.FromPolygons([M@v.co for v in me.vertices],[tuple(p.vertices) for p in me.polygons])
# signed volumes L vs R
for o in bpy.data.objects:
    if o.type!='MESH' or o.users_collection[0].name!='MODEL' or '_R' not in o.name: continue
    l=bpy.data.objects.get(o.name.replace('_R','_L'))
    if not l: continue
    def vol(x):
        bm=bmesh.new(); bm.from_mesh(x.data); v=bm.calc_volume(signed=True); bm.free(); return v
    vr,vl=vol(o),vol(l)
    if vr*vl<0 or vr<0: print('VOLUME', o.name, round(vr,4), l.name, round(vl,4))
names=lambda pre:[o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith(pre)]
movers=[o for o in bpy.data.objects if o.type=='MESH' and o.users_collection[0].name=='MODEL' and o.name.startswith(('wing1_','flap_','slat_','spoiler_'))]
fixed=[o for o in bpy.data.objects if o.type=='MESH' and o.name.startswith(('gearbay_','glovePylon_','PD_glove','gearDoor_R','gearDoor_L'))]
for sw in (0,10,20,30,45):
    for fl in (0,1):
        apply_pose(sweep=sw,flap=fl,doors=1.0)
        hits=[]
        for a in movers:
            ba=wbvh(a)
            for b in fixed:
                n=len(ba.overlap(wbvh(b)))
                if n: hits.append(f'{a.name}x{b.name}:{n}')
        print('sweep',sw,'flap',fl,' '.join(hits) or 'clean')
# door stack vs Piledriver guide
apply_pose(doors=1.0)
for s in 'RL':
    d=[o for o in fixed if o.name.startswith('gearDoor_'+s)]
    pd=bpy.data.objects.get('PD_glove_'+s)
    for o in d:
        n=len(wbvh(o).overlap(wbvh(pd))); print('door vs PD',o.name,n)
    import mathutils
    ws=[pd.matrix_world@v.co for v in pd.data.vertices]; print('PD',s,'x',round(min(w.x for w in ws),2),round(max(w.x for w in ws),2),'d',round(17-max(w.y for w in ws),2),round(17-min(w.y for w in ws),2),'z',round(min(w.z for w in ws),2),round(max(w.z for w in ws),2))
