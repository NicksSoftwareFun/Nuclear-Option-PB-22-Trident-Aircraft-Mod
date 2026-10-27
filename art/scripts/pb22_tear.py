"""Torn break lines at the skin seams between damage parts. Instead of a clean ring, the skin on each side of a seam
is cut into torn sheet-metal shards (a 3D Voronoi on a warped position, the same idea as the damage texture) and each
shard goes to one part or the other at random, more likely the nearer it sits to that part. A part that tears off
then leaves ragged, shard-shaped edges on both sides. Shards that would end up cut off from their own part are given
to the other one, so nothing floats. The closing bulkheads at each joint are torn the same way (holes punched by
shards), so the inside of a break looks ripped instead of capped.
Only the shape of the boundary changes: the cuts lie in the existing surfaces, and moved skin keeps its UVs.
tear_all(objs) works on world-placed objects (a finished blend, or the detail build before UVs and colliders).
Run on a blend: blender-python pb22_tear.py <in.blend> <out.blend>"""
import bpy, bmesh, math, sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree

SKIN = 'PB22_skin'
import os
DEBUG = os.environ.get('TEAR_DEBUG') == '1'


def _h(*k):
    x = 2166136261
    for v in k:
        x = ((x ^ (int(v) & 0xffffffff)) * 16777619) & 0xffffffff
        x ^= x >> 13
        x = (x * 2246822519) & 0xffffffff
    return (x % 1000003) / 1000003.0


def _vn(p, s, seed):
    """Cheap smooth value noise in [-1, 1]."""
    q = p / s; i = [math.floor(q.x), math.floor(q.y), math.floor(q.z)]; f = [q.x - i[0], q.y - i[1], q.z - i[2]]
    f = [t * t * (3 - 2 * t) for t in f]
    acc = 0.0
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                w = (f[0] if dx else 1 - f[0]) * (f[1] if dy else 1 - f[1]) * (f[2] if dz else 1 - f[2])
                acc += w * _h(i[0] + dx, i[1] + dy, i[2] + dz, seed)
    return acc * 2 - 1


def _cell(p, size, seed):
    """Nearest jittered-grid seed (3D Voronoi) of a warped point: (key, seed point)."""
    w = Vector((_vn(p, 0.35, seed + 1), _vn(p, 0.35, seed + 2), _vn(p, 0.35, seed + 3))) * (0.35 * size)
    q = (p + w) / size
    i0 = (math.floor(q.x), math.floor(q.y), math.floor(q.z))
    best, bk, bp = 1e9, None, None
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                c = (i0[0] + dx, i0[1] + dy, i0[2] + dz)
                sp = Vector((c[0] + 0.1 + 0.8 * _h(*c, seed, 1), c[1] + 0.1 + 0.8 * _h(*c, seed, 2), c[2] + 0.1 + 0.8 * _h(*c, seed, 3)))
                d = (sp - q).length_squared
                if d < best: best, bk, bp = d, c, sp
    return bk, bp * size


class Seam:
    """Part A behind the seam plane (s < 0), part B ahead (s > 0); s = (p - p0) . n."""
    def __init__(self, a, b, p0, n, depth, seed, kind='ring', centre=None, shard=0.15, grid=0.06):
        self.a, self.b, self.p0, self.n = a, b, Vector(p0), Vector(n).normalized()
        self.D, self.seed, self.kind, self.shard, self.grid = depth, seed, kind, shard, grid
        self.centre = Vector(centre) if centre else None

    def s(self, p): return (p - self.p0).dot(self.n)

    def planes(self, bm, faces):
        pl = []
        k = int(self.D / self.grid)
        for j in range(-k, k + 1):
            if j: pl.append((self.p0 + self.n * (j * self.grid + 0.37 * self.grid * (_h(self.seed, j) - 0.5)), self.n))
        if self.kind == 'ring':
            rmax = max(((v.co - self.centre) - self.n * (v.co - self.centre).dot(self.n)).length for f in faces for v in f.verts)
            m = max(8, int(math.pi * rmax / self.grid / 1.3))
            ex = Vector((1, 0, 0)); ez = Vector((0, 0, 1))
            for j in range(m):
                a = math.pi * (j + 0.4 * (_h(self.seed, j, 7) - 0.5)) / m
                r = ex * math.cos(a) + ez * math.sin(a); r -= self.n * r.dot(self.n)
                pl.append((self.centre, self.n.cross(r).normalized()))
        else:
            ys = [v.co.y for f in faces for v in f.verts]
            y0, y1 = min(ys), max(ys); m = max(4, int((y1 - y0) / (self.grid * 1.3)))
            for j in range(1, m):
                pl.append((Vector((0, y0 + (y1 - y0) * (j + 0.4 * (_h(self.seed, j, 9) - 0.5)) / m, 0)), Vector((0, 1, 0))))
        return pl


def _skin_idx(o):
    return [i for i, m in enumerate(o.data.materials) if m and m.name == SKIN]


def _in_band(f, seam, reach):
    if abs(f.normal.dot(seam.n)) > 0.9: return False        # end caps facing along the seam: torn as bulkheads
    ss = [seam.s(v.co) for v in f.verts]
    return min(ss) < reach and max(ss) > -reach


def _match_seam(bm, seam, is_skin, src, tol=1e-3):
    sv = {0: [], 1: []}
    for v in bm.verts:
        if abs(seam.s(v.co)) < tol:
            ks = {f[src] for f in v.link_faces if is_skin(f)}
            for k in ks: sv[k].append(v)
    for k in (0, 1):
        pts = [v.co.copy() for v in sv[1 - k]]
        for p in pts:
            edges = [e for e in bm.edges if all(abs(seam.s(w.co)) < tol for w in e.verts)
                     and any(is_skin(f) and f[src] == k for f in e.link_faces)]
            for e in edges:
                a, b = e.verts[0].co, e.verts[1].co
                ab = b - a; L2 = ab.length_squared
                if L2 < 1e-10: continue
                t = (p - a).dot(ab) / L2
                if 0.0005 < t < 0.9995 and (a + ab * t - p).length < tol:
                    ne, nv = bmesh.utils.edge_split(e, e.verts[0], t)
                    nv.co = p
                    break


def tear(seam, objs, log=print):
    A, B = objs[seam.a], objs[seam.b]
    sA, sB = _skin_idx(A), _skin_idx(B)
    if not sA or not sB: return 0
    bm = bmesh.new()
    src = bm.faces.layers.int.new('src'); lab = bm.faces.layers.int.new('lab')
    for k, o in enumerate((A, B)):
        me = o.data.copy(); me.transform(o.matrix_world)
        n0 = len(bm.faces); bm.from_mesh(me); bpy.data.meshes.remove(me)
        bm.faces.ensure_lookup_table()
        for f in bm.faces[n0:]: f[src] = k
    if len({f[src] for f in bm.faces}) < 2:
        raise RuntimeError('bmesh.from_mesh did not append')
    def is_skin(f): return f.material_index in (sA if f[src] == 0 else sB)
    reach = seam.D + 0.02
    band = lambda: [f for f in bm.faces if is_skin(f) and _in_band(f, seam, reach)]
    fs = band()
    if not fs: return 0
    # openings near the seam (glass, hatches, bays, lips): shards there keep their side
    prot = []
    for v in {v for f in fs for v in f.verts}:
        if any(not is_skin(g) and abs(g.normal.dot(seam.n)) < 0.9 for g in v.link_faces): prot.append(v.co.copy())
        elif any(len([g for g in e.link_faces if is_skin(g)]) == 1 for e in v.link_edges) and abs(seam.s(v.co)) > 0.01:
            prot.append(v.co.copy())
    # weld the two skins along the seam (first split seam edges at the other side's seam points: the two parts may
    # be divided differently along the seam), then cut the band into a fine grid and triangulate it
    _match_seam(bm, seam, is_skin, src)
    bmesh.ops.remove_doubles(bm, verts=list({v for f in fs for v in f.verts}), dist=1e-4)
    for co, no in seam.planes(bm, band()):
        fs = band()
        bmesh.ops.bisect_plane(bm, geom=list({e for f in fs for e in f.edges}) + fs + list({v for f in fs for v in f.verts}),
                               plane_co=co, plane_no=no, dist=1e-5)
    fs = band()
    bmesh.ops.triangulate(bm, faces=fs, quad_method='BEAUTY', ngon_method='BEAUTY')
    fs = band()
    bset = set(fs)
    # shard labels: 0 = A, 1 = B
    lim = 0.9 * seam.D
    cache = {}
    for f in bm.faces:
        if not is_skin(f): f[lab] = -1; continue
        if f not in bset: f[lab] = f[src]; continue
        c = f.calc_center_median()
        if any((c - p).length < 0.07 for p in prot):
            f[lab] = 0 if seam.s(c) < 0 else 1; continue
        key, sp = _cell(c, seam.shard, seam.seed)
        if key not in cache:
            t = (_h(*key, seam.seed, 5) * 2 - 1) * lim
            cache[key] = 1 if seam.s(sp) > t else 0
        f[lab] = cache[key]
    if DEBUG: log('  band tris %d, prot pts %d, labels A %d B %d, protected %d' % (len(fs), len(prot), sum(1 for f in fs if f[lab] == 0), sum(1 for f in fs if f[lab] == 1), sum(1 for f in fs if any((f.calc_center_median() - p).length < 0.07 for p in prot))))
    # no floating chips: a band face must connect (through faces of its label) to that part's skin outside the band
    for _ in range(6):
        seen = set(); stack = [f for f in bm.faces if f[lab] >= 0 and f not in bset]
        seen.update(stack)
        while stack:
            f = stack.pop()
            for e in f.edges:
                for g in e.link_faces:
                    if g not in seen and g[lab] == f[lab]: seen.add(g); stack.append(g)
        flips = [f for f in fs if f not in seen]
        if DEBUG: log('  flips %d' % len(flips))
        if not flips: break
        for f in flips: f[lab] = 1 - f[lab]
    # merge the grid back into big faces inside each label region (keeps the torn outline, drops the extra triangles)
    for f in fs: f.material_index = 30000 + f[lab]
    vs = list({v for f in fs for v in f.verts if all(g in bset for g in v.link_faces)})
    es = list({e for f in fs for e in f.edges if all(g in bset for g in e.link_faces)})
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(1.0), verts=vs, edges=es, delimit={'MATERIAL', 'UV'})
    moved = [0, 0]
    out = {}
    for k, o in enumerate((A, B)):
        b2 = bm.copy()
        l2 = b2.faces.layers.int['lab']; s2 = b2.faces.layers.int['src']
        si = (sA, sB)[k][0]
        kill = []
        for f in b2.faces:
            if f.material_index >= 30000:
                if f[l2] != k: kill.append(f)
                else:
                    if f[s2] != k: moved[k] += 1
                    f.material_index = si
            elif f[s2] != k: kill.append(f)
        bmesh.ops.delete(b2, geom=kill, context='FACES')
        bmesh.ops.delete(b2, geom=[v for v in b2.verts if not v.link_faces], context='VERTS')
        b2.faces.layers.int.remove(l2); b2.faces.layers.int.remove(b2.faces.layers.int['src'])
        b2.transform(o.matrix_world.inverted())
        out[o.name] = b2
    bm.free()
    for o in (A, B):
        b2 = out[o.name]; b2.normal_update(); b2.to_mesh(o.data); o.data.update(); b2.free()
    tree = _pose_bvhs(objs)
    nb = sum(_tear_cap(o, seam, tree) for o in (A, B))
    log('tear %s|%s: %d shards, %d faces to %s, %d to %s, bulkhead holes %d' % (seam.a, seam.b, len(cache), moved[1], seam.b, moved[0], seam.a, nb))
    return moved[0] + moved[1]


def _dirs(n=192):
    """Even directions over the sphere (Fibonacci)."""
    out = []
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n; r = math.sqrt(max(0.0, 1 - z * z)); a = i * 2.39996323
        out.append(Vector((r * math.cos(a), r * math.sin(a), z)))
    return out


def _world_bvh(objs):
    vs, ps = [], []
    for o in objs.values():
        if o.type != 'MESH' or 'colmesh' in o.name: continue
        mw = o.matrix_world; n0 = len(vs)
        vs.extend(mw @ v.co for v in o.data.vertices)
        ps.extend([n0 + i for i in p.vertices] for p in o.data.polygons)
    return BVHTree.FromPolygons(vs, ps)


def _pose_bvhs(objs):
    """World BVHs of the aircraft as it stands and with everything that opens opened (gear down, doors, bays, flaps,
    slats, spoilers): a bulkhead that shows through an open bay or slot counts as seen from outside."""
    trees = [_world_bvh(objs)]
    try:
        from pb22_pose import apply_pose
    except ImportError:
        return trees
    keep = {o.name: o.matrix_basis.copy() for o in bpy.data.objects}
    apply_pose(gear=0.0, doors=1.0, bay=1.0, flap=1.0, slat=1.0, spoiler=1.0)
    bpy.context.view_layer.update()
    trees.append(_world_bvh(objs))
    for o in bpy.data.objects: o.matrix_basis = keep[o.name]
    bpy.context.view_layer.update()
    return trees


def _seen_from_outside(tree, p, dirs):
    """True when any ray from p gets out of the aircraft (the face is outer surface, not an enclosed bulkhead).
    tree may be a list of BVHs (poses): seen in any of them counts."""
    for t in (tree if isinstance(tree, list) else [tree]):
        for d in dirs:
            if t.ray_cast(p + d * 0.003, d, 60.0)[0] is None: return True
    return False


def _tear_cap(o, seam, tree=None):
    """Punch shard holes in the flat closing bulkheads and end caps that sit at the seam plane. Only faces enclosed by
    the skin (no ray from them gets out of the aircraft) are holed: a step or slot wall at the seam that can be seen
    from outside stays whole."""
    si = _skin_idx(o)
    dirs = _dirs()
    bm = bmesh.new(); bm.from_mesh(o.data); bm.transform(o.matrix_world)
    def cap(f):
        if abs(f.normal.dot(seam.n)) < 0.9: return False
        return all(abs(seam.s(v.co)) < 0.13 for v in f.verts) and f.calc_area() > 0.0005
    fs = [f for f in bm.faces if cap(f)]
    if not fs:
        bm.free(); return 0
    u = seam.n.orthogonal().normalized(); w = seam.n.cross(u)
    vs = [v.co for f in fs for v in f.verts]
    for ax in (u, w):
        a0 = min(ax.dot(p) for p in vs); a1 = max(ax.dot(p) for p in vs); g = 0.08 if seam.kind == 'ring' else 0.06
        for j in range(1, int((a1 - a0) / g)):
            cur = [f for f in bm.faces if cap(f)]
            bmesh.ops.bisect_plane(bm, geom=list({e for f in cur for e in f.edges}) + cur + list({v for f in cur for v in f.verts}),
                                   plane_co=ax * (a0 + j * g + 0.3 * g * (_h(seam.seed, j, 11) - 0.5)), plane_no=ax, dist=1e-5)
    cur = [f for f in bm.faces if cap(f)]
    bmesh.ops.triangulate(bm, faces=cur)
    cur = [f for f in bm.faces if cap(f)]
    cset = set(cur)
    # tear it: big ragged holes (shards of about 25 cm, 55 % go), but keep a torn flange 2-7 cm wide round the edge
    # where it was riveted to the skin
    edge = [((e.verts[0].co + e.verts[1].co) / 2) for f in cur for e in f.edges
            if any(g not in cset for g in e.link_faces) or len(e.link_faces) == 1]
    from mathutils.kdtree import KDTree
    kd = KDTree(max(1, len(edge)))
    for i, p in enumerate(edge): kd.insert(p, i)
    kd.balance()
    rim, holes = set(), set()
    for f in cur:
        c = f.calc_center_median()
        if edge and kd.find(c)[2] < 0.045 + 0.025 * _vn(c, 0.09, seam.seed + 61):
            rim.add(f); continue
        if tree is not None and _seen_from_outside(tree, c, dirs): rim.add(f); continue
        key, _ = _cell(c, 0.25, seam.seed + 50)
        if _h(*key, seam.seed, 13) < 0.55: holes.add(f)
    # drop pieces of bulkhead left floating after the holes
    keep = set(); stack = [f for f in rim]; keep.update(stack)
    while stack:
        f = stack.pop()
        for e in f.edges:
            for g in e.link_faces:
                if g in cset and g not in holes and g not in keep: keep.add(g); stack.append(g)
    kill = [f for f in cur if f not in keep]
    mats = {}
    for f in cur: mats.setdefault(f.material_index, 0)
    bmesh.ops.delete(bm, geom=kill, context='FACES')
    left = [f for f in bm.faces if cap(f)]
    vs2 = list({v for f in left for v in f.verts if all(g in left for g in v.link_faces)})
    es2 = list({e for f in left for e in f.edges if all(g in left for g in e.link_faces)})
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(1.0), verts=vs2, edges=es2, delimit={'MATERIAL', 'UV'})
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.transform(o.matrix_world.inverted()); bm.normal_update(); bm.to_mesh(o.data); o.data.update(); bm.free()
    return len(kill)


def seams():
    S = []
    F = Vector((0, 1, 0))
    for i, (a, b, y, zc) in enumerate((('cockpit', 'nose', 13.6, 2.33), ('fuselage_FF', 'cockpit', 9.4, 2.50),
                                       ('fuselage_F', 'fuselage_FF', 6.9, 2.45), ('fuselage', 'fuselage_F', 4.4, 2.45),
                                       ('fuselage_R', 'fuselage', -8.5, 2.47))):
        S.append(Seam(a, b, (0, y, zc), F, 0.55, 101 + i, centre=(0, y, zc), shard=0.16))
    for side, m in (('R', 1), ('L', -1)):
        S.append(Seam('fuselage', f'intake_{side}', (0, 2.4, 0), F, 0.30, 121, centre=(m * 1.56, 2.4, 2.45)))
        S.append(Seam(f'wing1_{side}', f'wing2_{side}', (m * 11.10, 0, 0), (m, 0, 0), 0.45, 131, kind='span', shard=0.13, grid=0.05))
        S.append(Seam(f'wing2_{side}', f'wingtip_{side}', (m * 13.25, 0, 0), (m, 0, 0), 0.25, 141, kind='span', shard=0.10, grid=0.04))
    return S


def tear_all(objs, log=print):
    n = 0
    for s in seams():
        if s.a in objs and s.b in objs: n += tear(s, objs, log)
    log('torn seams: %d faces changed part' % n)


if __name__ == '__main__':
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    bpy.ops.wm.open_mainfile(filepath=a[0])
    tear_all({o.name: o for o in bpy.data.objects if o.type == 'MESH'})
    bpy.ops.wm.save_as_mainfile(filepath=a[1])
