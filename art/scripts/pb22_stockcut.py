"""Stock-style break joints (1.0.5). Stock aircraft cut their damage parts straight along a panel line, both parts
share every vertex on the cut, the skin is double-sided (done in export_pb22.py) and the torn look comes from the
damage texture alone. This step takes the straight cuts the build already makes and:
  1. seals them: a skin boundary vertex of one part that lies on the other part's open skin edge (within SNAP) is
     snapped onto that edge and the edge is split there, so both sides have the same vertices (no T-junction cracks);
  2. opens them: flat skin end caps at a damage seam that can't be seen from outside are deleted (stock parts have
     none, a broken end shows the inside), and the closing bulkheads there are holed like a torn frame.
Works on world-placed objects in the seam pose (wings forward), like pb22_rip did."""
import bmesh
from mathutils import Vector
from mathutils.kdtree import KDTree
from pb22_tear import _skin_idx, _tear_cap, _pose_bvhs, _seen_from_outside, _dirs, seams

SNAP = 0.005          # a boundary vertex this close to the other part's open edge is on the seam
MATCH = 2e-4          # closer than this to a vertex counts as the same vertex


def _open_edges(bm, si):
    return [e for e in bm.edges if len([f for f in e.link_faces if f.material_index in si]) == 1]


def _seg(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
    return a + ab * t, t


def seal(objs, log=print, rounds=3):
    """Split open skin edges wherever a neighbouring part has a vertex on them; snap near-misses onto the edge."""
    skin = {n: o for n, o in objs.items() if o.type == 'MESH' and _skin_idx(o)}
    total = snapped = 0
    for _ in range(rounds):
        # world-space boundary vertices of every part
        BV = {}
        for n, o in skin.items():
            bm = bmesh.new(); bm.from_mesh(o.data); mw = o.matrix_world
            BV[n] = list({tuple(round(c, 6) for c in (mw @ v.co)) for e in _open_edges(bm, _skin_idx(o)) for v in e.verts})
            bm.free()
        KD = {}
        for n, vs in BV.items():
            kd = KDTree(max(1, len(vs))); [kd.insert(Vector(v), i) for i, v in enumerate(vs)]; kd.balance(); KD[n] = kd
        changed = 0
        for n, o in skin.items():
            mw = o.matrix_world; mi = mw.inverted()
            bm = bmesh.new(); bm.from_mesh(o.data)
            si = _skin_idx(o)
            ownkd = KD[n]
            # other parts' boundary vertices near this part's open edges
            cand = []
            for m, vs in BV.items():
                if m == n: continue
                cand += [Vector(v) for v in vs]
            if not cand: bm.free(); continue
            ck = KDTree(len(cand)); [ck.insert(p, i) for i, p in enumerate(cand)]; ck.balance()
            splits = []
            for e in _open_edges(bm, si):
                a, b = mw @ e.verts[0].co, mw @ e.verts[1].co
                mid = (a + b) / 2; r = (b - a).length / 2 + SNAP
                for p, i, d in ck.find_range(mid, r):
                    q, t = _seg(p, a, b)
                    if t <= 1e-4 or t >= 1 - 1e-4: continue
                    if (q - p).length > SNAP: continue
                    dd = ownkd.find(p)[2]
                    if dd is not None and dd <= MATCH: continue    # we already have a vertex there
                    splits.append((e, t, p))
            # split each edge at its points, furthest first so the remaining parameters stay valid
            by_edge = {}
            for e, t, p in splits: by_edge.setdefault(e, []).append((t, p))
            for e, pts in by_edge.items():
                pts = sorted({round(t, 6): (t, p) for t, p in pts}.values(), key=lambda x: x[0])
                v0 = e.verts[0]; cur = e; prev_t = 0.0
                for t, p in pts:
                    if not cur.is_valid: break
                    # parameter along the remaining edge piece from v0
                    f = (t - prev_t) / max(1e-9, 1 - prev_t)
                    other = cur.other_vert(v0)
                    ne, nv = bmesh.utils.edge_split(cur, v0, f)
                    nv.co = mi @ p
                    # continue on the piece between nv and the far vertex
                    cur = next((x for x in nv.link_edges if x.other_vert(nv) is other), None)
                    v0 = nv; prev_t = t
                    changed += 1
            # snap our own near-miss boundary vertices onto the other parts' edges is handled by their split above;
            # a vertex of ours that sits off the other edge by 0.2-5 mm is moved onto the closest other vertex
            for v in {v for e in _open_edges(bm, si) for v in e.verts}:
                p = mw @ v.co
                for m, kd in KD.items():
                    if m == n: continue
                    co, i, d = kd.find(p)
                    if d is not None and MATCH < d <= SNAP:
                        v.co = mi @ co; snapped += 1; changed += 1
                        break
            bm.normal_update(); bm.to_mesh(o.data); o.data.update(); bm.free()
        total += changed
        if not changed: break
    log('seal: %d edge splits / snaps (%d vertex snaps)' % (total, snapped))
    return total


def open_caps(objs, log=print):
    """Delete enclosed flat skin caps at every damage seam and hole the closing bulkheads there."""
    tree = _pose_bvhs(objs)
    dirs = _dirs()
    gone = holes = 0
    for s in seams():
        for name in (s.a, s.b):
            o = objs.get(name)
            if o is None: continue
            si = _skin_idx(o)
            bm = bmesh.new(); bm.from_mesh(o.data); mw = o.matrix_world
            dead = []
            for f in bm.faces:
                if f.material_index not in si: continue
                nw = (mw.to_3x3() @ f.normal).normalized()
                if abs(nw.dot(s.n)) < 0.9: continue
                ws = [mw @ v.co for v in f.verts]
                if not all(abs(s.s(p)) < 0.13 for p in ws): continue
                c = sum(ws, Vector()) / len(ws)
                if _seen_from_outside(tree, c, dirs): continue
                dead.append(f)
            if dead:
                bmesh.ops.delete(bm, geom=dead, context='FACES')
                bm.to_mesh(o.data); o.data.update(); gone += len(dead)
            bm.free()
            holes += _tear_cap(o, s, tree)
    log('open caps: %d enclosed skin cap faces removed, %d bulkhead faces holed' % (gone, holes))
