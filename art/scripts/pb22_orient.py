"""Face orientation fixer for the PB-22 model: every surface the camera can see should face the camera.
fix_orientation(objs) works per connected island of every mesh object:
  1. islands with inconsistent winding (an edge walked the same way by both of its faces) are made consistent
     (bmesh recalc_face_normals on that island only);
  2. rays are shot at the whole model from many directions outside it (orthographic grids); each first hit votes
     front or back for its island; an island with enough votes and mostly back-face hits is reversed.
Hidden islands (no votes) are left alone. Returns a list of (object, island size, back fraction) that were flipped."""
import bpy, bmesh, math
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def _islands(bm):
    seen, out = set(), []
    for f in bm.faces:
        if f.index in seen: continue
        stack, isl = [f], []
        seen.add(f.index)
        while stack:
            g = stack.pop(); isl.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in seen: seen.add(h.index); stack.append(h)
        out.append(isl)
    return out


def _inconsistent(isl):
    fs = set(isl)
    for f in isl:
        for lp in f.loops:
            e = lp.edge
            for l2 in e.link_loops:
                if l2.face is not f and l2.face in fs and l2.vert is lp.vert: return True
    return False


def _fib(n):
    g = math.pi * (3 - math.sqrt(5))
    for i in range(n):
        y = 1 - 2 * (i + 0.5) / n; r = math.sqrt(1 - y * y)
        yield Vector((math.cos(g * i) * r, math.sin(g * i) * r, y))


def fix_orientation(objs, dirs=96, grid=0.06, min_votes=12, thresh=0.6, verbose=True):
    objs = [o for o in objs if o.type == 'MESH' and len(o.data.polygons)]
    bms = {}
    for o in objs:
        bm = bmesh.new(); bm.from_mesh(o.data); bm.faces.ensure_lookup_table(); bms[o] = bm
        for isl in _islands(bm):
            if _inconsistent(isl):
                bmesh.ops.recalc_face_normals(bm, faces=isl)
                if verbose: print('orient: made winding consistent', o.name, len(isl))
    # world-space triangles of everything, with (object, face index) per triangle
    verts, tris, owner = [], [], []
    for o in objs:
        bm = bms[o]; mw = o.matrix_world
        base = len(verts)
        verts.extend(mw @ v.co for v in bm.verts)
        bm.verts.index_update()
        for f in bm.faces:
            vs = [v.index + base for v in f.verts]
            for k in range(1, len(vs) - 1):
                tris.append((vs[0], vs[k], vs[k + 1])); owner.append((o, f.index))
    bvh = BVHTree.FromPolygons(verts, tris, epsilon=0.0)
    lo = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
    hi = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
    c, R = (lo + hi) / 2, (hi - lo).length / 2 + 1.0
    isl_of = {}
    for o in objs:
        for k, isl in enumerate(_islands(bms[o])):
            for f in isl: isl_of[(o, f.index)] = k
    votes = {}
    n_steps = int(2 * R / grid)
    for dv in _fib(dirs):
        u = dv.orthogonal().normalized(); w = dv.cross(u)
        for i in range(n_steps):
            for j in range(n_steps):
                org = c - dv * R + u * (-R + i * grid) + w * (-R + j * grid)
                hit = bvh.ray_cast(org, dv, 2 * R)
                if hit[0] is None: continue
                o, fi = owner[hit[2]]
                key = (o, isl_of[(o, fi)])
                fr = hit[1].dot(dv) < 0
                v = votes.setdefault(key, [0, 0]); v[0 if fr else 1] += 1
    flipped = []
    for o in objs:
        bm = bms[o]
        for k, isl in enumerate(_islands(bm)):
            fv, bv = votes.get((o, k), (0, 0))
            if fv + bv >= min_votes and bv / (fv + bv) > thresh:
                bmesh.ops.reverse_faces(bm, faces=isl, flip_multires=False)
                flipped.append((o.name, len(isl), round(bv / (fv + bv), 2)))
                if verbose: print('orient: reversed island', o.name, len(isl), 'faces, back hits', round(bv / (fv + bv), 2))
        bm.to_mesh(o.data); o.data.update(); bm.free()
    return flipped, votes
