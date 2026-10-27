"""Honeycomb core under the skin, like the stock Medusa and Ifrit: a thin, simplified copy of a part's skin set
INSET metres inside it, on the game's shared honeycomb material. A hole in the skin then shows torn composite
instead of the sky or the empty inside. One child object '<part>_hc' per part, so the part's own mesh (and its damage
material) is untouched; the stock honeycomb carries vertex colour (1, 0.49, 0.35, 1), copied here.
Internal structure is placed at least 8 mm inside the skin (pb22_structure2.py), so a 5 mm inset stays clear of it;
check_liners() reports anything that still crosses a liner."""
import bpy, bmesh, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree

INSET = 0.005
HC_COL = (1.0, 0.49, 0.35, 1.0)
PARTS = ['nose', 'tail', 'rudder_L', 'intake_R', 'intake_L', 'gearbay_R', 'gearbay_L', 'wingroot_R', 'wingroot_L',
         'wing1_R', 'wing1_L', 'wing2_R', 'wing2_L', 'wingtip_R', 'wingtip_L']


def _honey_mat():
    m = bpy.data.materials.get('PB22_honey')
    if m is None:
        m = bpy.data.materials.new('PB22_honey'); m.diffuse_color = (0.75, 0.55, 0.35, 1)
    return m


def make_liner(o, coll, ratio=0.45):
    si = [i for i, m in enumerate(o.data.materials) if m and m.name == 'PB22_skin']
    if not si: return None
    bm = bmesh.new(); bm.from_mesh(o.data)
    vsk = bm.faces.layers.int.get('visskin')        # duct lining on the skin material is not outer skin
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index not in si or (vsk is not None and f[vsk])], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    if not bm.faces: bm.free(); return None
    bm.normal_update()
    # shrink along the (outward) vertex normals, in world units
    sx = o.matrix_world.to_scale()
    k = INSET / max(1e-6, (abs(sx.x) + abs(sx.y) + abs(sx.z)) / 3)
    for v in bm.verts:
        n = v.normal
        if n.length > 0.5: v.co -= n * k
    me = bpy.data.meshes.new(o.name + '_hc'); bm.to_mesh(me); bm.free()
    h = bpy.data.objects.new(o.name + '_hc', me); coll.objects.link(h)
    h.parent = o; h.matrix_parent_inverse.identity(); h.matrix_basis.identity()
    me.materials.append(_honey_mat())
    for p in me.polygons: p.material_index = 0; p.use_smooth = True
    if ratio < 1.0 and len(me.polygons) > 40:
        md = h.modifiers.new('dec', 'DECIMATE'); md.ratio = ratio
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        nm = bpy.data.meshes.new_from_object(h.evaluated_get(dg)); h.modifiers.clear()
        old = h.data; h.data = nm; nm.name = o.name + '_hc'; bpy.data.meshes.remove(old)
    ca = h.data.color_attributes.new('Col', 'BYTE_COLOR', 'CORNER')
    for d in ca.data: d.color = HC_COL
    return h


def make_liners(objs, coll, log=print):
    made = []
    for n in PARTS:
        o = objs.get(n)
        if o is None or o.type != 'MESH': continue
        h = make_liner(o, coll)
        if h:
            made.append(h)
            log('honeycomb %s: %d tris' % (h.name, sum(len(p.vertices) - 2 for p in h.data.polygons)))
    return made


def _bvh(o, faces=None):
    m = o.matrix_world
    vs = [m @ v.co for v in o.data.vertices]
    ps = [list(p.vertices) for p in o.data.polygons if faces is None or faces(p)]
    return BVHTree.FromPolygons(vs, ps) if ps else None


def _targets(objs):
    """BVH per object of what a liner must not cross: every face except glass. Skin counts too, its own part's included
    (the liner is decimated, so in a hollow of the skin it can cut through it; other parts' skin: a wing panel tucked
    inside the glove)."""
    out = {}
    for o in objs.values():
        if o.type != 'MESH' or o.name.endswith('_hc') or 'colmesh' in o.name: continue
        mats = o.data.materials
        def nm(p, mats=mats):
            m = mats[p.material_index] if p.material_index < len(mats) else None
            return m.name if m else ''
        out[o.name] = (_bvh(o, lambda p, nm=nm: nm(p) not in ('PB22_skin', 'PB22_glass')),
                       _bvh(o, lambda p, nm=nm: nm(p) == 'PB22_skin'))
    return out


def trim_liners(liners, objs, log=print, passes=4):
    """Delete every liner face that crosses something (see _targets), until none does. Liners left with almost
    nothing are removed."""
    for k in range(passes):
        tg = _targets(objs); cut = 0
        for h in list(liners):
            ht = _bvh(h)
            if ht is None: continue
            own = h.parent.name if h.parent else None
            bad = set()
            for n, (t_int, t_skin) in tg.items():
                for t in (t_int, t_skin):
                    if t is not None: bad.update(a for a, b in ht.overlap(t))
            if not bad: continue
            bm = bmesh.new(); bm.from_mesh(h.data); bm.faces.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[bm.faces[i] for i in bad], context='FACES')
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
            bm.to_mesh(h.data); bm.free(); h.data.update(); cut += len(bad)
            if len(h.data.polygons) < 12:
                liners.remove(h); objs.pop(h.name, None); bpy.data.objects.remove(h)
        log('liner trim pass %d: %d faces cut' % (k + 1, cut))
        if not cut: break
    return liners


def check_liners(liners, objs, log=print):
    """Every face of every object that crosses a liner (BVH triangle overlap), the rules of _targets."""
    bad = []
    lt = {h.name: _bvh(h) for h in liners}
    hs = {h.name: h for h in liners}
    for oname, (t_int, t_skin) in _targets(objs).items():
        for hn, ht in lt.items():
            if ht is None: continue
            own = hs[hn].parent.name if hs[hn].parent else None
            pairs = []
            for t in (t_int, t_skin):
                if t is not None: pairs += ht.overlap(t)
            o = objs[oname]
            if pairs:
                c = Vector()
                for a, b in pairs[:20]: c += hs[hn].matrix_world @ hs[hn].data.polygons[a].center
                c /= min(len(pairs), 20)
                bad.append((hn, o.name, len(pairs), tuple(round(x, 2) for x in c)))
    for b in bad: log('CLIP liner %s x %s: %d face pairs near (%.2f, %.2f, %.2f)' % (b[0], b[1], b[2], *b[3]))
    log('liner clip check: %d crossings' % len(bad))
    return bad


def hide_visible(liners, objs, poses, apply_pose, log=print):
    """Delete every liner face that can be seen from outside the intact aircraft in any of the poses (through a door
    gap or the edge of an opening): the core is only meant to show once the skin over it is shot away."""
    from pb22_tear import _dirs, _world_bvh, _seen_from_outside
    dirs = _dirs()
    gone = 0
    for p in poses:
        apply_pose(**p); bpy.context.view_layer.update()
        tree = _world_bvh({n: o for n, o in objs.items() if not n.endswith('_hc')})
        for h in list(liners):
            m = h.matrix_world
            vs = h.data.vertices
            # the centre and points near each corner: a big face can show at one edge only
            bad = [q.index for q in h.data.polygons
                   if any(_seen_from_outside(tree, m @ p, dirs)
                          for p in [q.center] + [vs[i].co.lerp(q.center, 0.2) for i in q.vertices])]
            if not bad: continue
            bm = bmesh.new(); bm.from_mesh(h.data); bm.faces.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[bm.faces[i] for i in bad], context='FACES')
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
            bm.to_mesh(h.data); bm.free(); h.data.update(); gone += len(bad)
            if len(h.data.polygons) < 12:
                liners.remove(h); objs.pop(h.name, None); bpy.data.objects.remove(h)
    log('liner faces seen from outside, removed: %d' % gone)
    return liners
