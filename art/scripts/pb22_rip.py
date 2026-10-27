"""Torn break lines at the skin seams between damage parts. Each seam gets one long rip line: a jagged polyline that
wanders up to D either side of the joint. Every seam takes a random stretch of one long master rip (saw teeth, a slow
drift and the odd deep spike, like sheet metal torn along a row of rivets by a blast), so they all match in style but
none repeats. Both parts' skins near the joint are merged into one mesh, cut along that one line,
and split by which side of it each face lies on, so the two edges match exactly and nothing can leave a gap.
Only faces close to the real joint take part (a seam that is only part of a ring, like the intakes, stays local).
The closing bulkheads at each joint are holed afterwards (pb22_tear._tear_cap: only ones that can't be seen from
outside), so the inside of a break looks ripped instead of capped.
rip_all(objs) works on world-placed objects (a finished blend, or the detail build before UVs and colliders).
Run on a blend: blender-python pb22_rip.py <in.blend> <out.blend>"""
import bpy, bmesh, math, sys, os, bisect
from mathutils import Vector
from mathutils.kdtree import KDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pb22_tear import _h, _vn, _skin_idx, _match_seam, _tear_cap, _pose_bvhs, seams

DEBUG = os.environ.get('TEAR_DEBUG') == '1'
NB = 720                                          # angle bins for the seam loop


def _basis(seam):
    if abs(seam.n.y) > 0.9: return Vector((1, 0, 0)), Vector((0, 0, 1))
    return Vector((0, 1, 0)), Vector((0, 0, 1))


REF_LEN = 20.0                                    # master rip, longer than the longest seam (8.7 m)
REF_SEED = 7331
_REF = None


def _ref_rip(step=0.10):
    """The master rip: one long torn line [(arc, offset in units of D)], built by midpoint displacement (big wander,
    then smaller and smaller jags, like a crack in sheet metal), with a few deep spikes where a tear ran along a row
    of rivets and then turned back."""
    global _REF
    if _REF is not None: return _REF
    seed = REF_SEED
    n0 = int(REF_LEN / 0.8) + 1
    pts = [(i * 0.8, 1.0 * (_h(seed, i, 1) - 0.5)) for i in range(n0)]
    for lvl, amp in enumerate((0.34, 0.30, 0.30, 0.24, 0.14)):
        nxt = []
        for i in range(len(pts) - 1):
            (a0, o0), (a1, o1) = pts[i], pts[i + 1]
            t = 0.5 + 0.6 * (_h(seed, lvl, i, 2) - 0.5)           # off-centre split: uneven jag widths
            am = a0 + (a1 - a0) * t
            om = o0 + (o1 - o0) * t + amp * (_h(seed, lvl, i, 3) * 2 - 1)
            nxt += [(a0, o0), (am, om)]
            if lvl == 2 and _h(seed, i, 7) < 0.16:                # a torn tongue (10-20 cm wide) out to near full depth
                sg = 1 if om >= 0 else -1
                ta = am + (a1 - am) * (0.3 + 0.2 * _h(seed, i, 9))
                nxt += [(ta, sg * (0.65 + 0.25 * _h(seed, i, 8))), (ta + (a1 - ta) * 0.45, om + (o1 - om) * 0.5)]
        nxt.append(pts[-1]); pts = nxt
    out = pts
    _REF = [(a, max(-0.92, min(0.92, o))) for a, o in out]
    return _REF


def _rip_line(L, D, seed, scale):
    """A random stretch of the master rip, L long, scaled to the seam (depth D, tooth size scale x the master), as a
    closed polyline over [0, L]: list of (arc, offset). The last 0.25 m bends back to the first point so the loop
    closes."""
    ref = _ref_rip()
    span = L / scale
    a0 = _h(seed, 17) * (REF_LEN - span - 0.01)
    out = [(0.0, None)]
    for a, o in ref:
        if a0 < a < a0 + span: out.append(((a - a0) * scale, o * D))
    i = bisect.bisect_right([a for a, _ in ref], a0) - 1
    (x0, o0), (x1, o1) = ref[i], ref[i + 1]
    out[0] = (0.0, (o0 + (o1 - o0) * (a0 - x0) / max(1e-9, x1 - x0)) * D)
    close = min(0.25, 0.3 * L)
    out = [(a, o if a < L - close else o + (out[0][1] - o) * (a - (L - close)) / close) for a, o in out]
    out.append((L, out[0][1]))
    return out


def rip(seam, objs, log=print):
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
    vsk = bm.faces.layers.int.get('visskin')
    def is_skin(f): return f.material_index in (sA if f[src] == 0 else sB) and (vsk is None or f[vsk] == 0)
    D = seam.D; reach = D + 0.02
    def near_plane(f):
        if abs(f.normal.dot(seam.n)) > 0.9: return False        # end caps facing along the seam: holed as bulkheads
        ss = [seam.s(v.co) for v in f.verts]
        return min(ss) < reach and max(ss) > -reach
    # weld the two skins along the joint
    cand = [f for f in bm.faces if is_skin(f) and near_plane(f)]
    _match_seam(bm, seam, is_skin, src, tol=4e-3)
    bmesh.ops.remove_doubles(bm, verts=list({v for f in bm.faces if is_skin(f) and near_plane(f) for v in f.verts}), dist=1e-4)
    # the joint: welded skin points on the plane shared by both parts
    # (points on the plane of either skin that have the other skin within 2 cm: the two panels' outlines can be
    # sampled differently, so they need not weld everywhere)
    onp = {0: [], 1: []}
    for v in bm.verts:
        if abs(seam.s(v.co)) < 2e-3:
            for k in {f[src] for f in v.link_faces if is_skin(f)}: onp[k].append(v.co.copy())
    joint = []
    if onp[0] and onp[1]:
        k1 = KDTree(len(onp[1]))
        for i, p in enumerate(onp[1]): k1.insert(p, i)
        k1.balance()
        joint = [p for p in onp[0] if k1.find(p)[2] < 0.02] + onp[1]
        k0 = KDTree(len(onp[0]))
        for i, p in enumerate(onp[0]): k0.insert(p, i)
        k0.balance()
        joint = [p for p in onp[0] if k1.find(p)[2] < 0.02] + [p for p in onp[1] if k0.find(p)[2] < 0.02]
    if len(joint) < 4:
        bm.free(); log('rip %s|%s: no shared joint' % (seam.a, seam.b)); return 0
    kd = KDTree(len(joint))
    for i, p in enumerate(joint): kd.insert(p, i)
    kd.balance()
    lim = D + 0.08
    band = lambda: [f for f in bm.faces if is_skin(f) and near_plane(f) and min(kd.find(v.co)[2] for v in f.verts) < lim]
    # seam loop: angle around the joint's centre, radius per angle bin, arc length
    u, w = _basis(seam)
    c0 = seam.centre if seam.centre is not None else sum(joint, Vector()) / len(joint)
    c0 = c0 - seam.n * seam.s(c0)
    def ang(p):
        d = p - c0
        return math.atan2(d.dot(w), d.dot(u)) % (2 * math.pi)
    rs = [[] for _ in range(NB)]
    for p in joint:
        d = p - c0; d -= seam.n * d.dot(seam.n)
        rs[int(ang(p) / (2 * math.pi) * NB) % NB].append(d.length)
    have = [i for i in range(NB) if rs[i]]
    rad = [0.0] * NB
    for i in range(NB):
        if rs[i]: rad[i] = sum(rs[i]) / len(rs[i]); continue
        # nearest filled bins either way (wrapping)
        lo = max((h for h in have if h < i), default=have[-1]); hi = min((h for h in have if h > i), default=have[0])
        dl = (i - lo) % NB; dh = (hi - i) % NB
        rad[i] = (sum(rs[lo]) / len(rs[lo]) * dh + sum(rs[hi]) / len(rs[hi]) * dl) / max(1, dl + dh)
    dth = 2 * math.pi / NB
    arc = [0.0]
    for i in range(NB): arc.append(arc[-1] + rad[i] * dth)
    L = arc[-1]
    def th_of(a):
        i = min(NB - 1, max(0, bisect.bisect_right(arc, a) - 1))
        return (i + (a - arc[i]) / max(1e-9, arc[i + 1] - arc[i])) * dth
    def pos(th, off):
        i = int(th / dth) % NB
        return c0 + (u * math.cos(th) + w * math.sin(th)) * rad[i] + seam.n * off
    # openings next to the joint (glass, hatches, bays, lips): the line comes back to the joint there
    fs = band()
    prot = []; PM = {}
    for v in {v for f in fs for v in f.verts}:
        if any(not is_skin(g) and abs(g.normal.dot(seam.n)) < 0.9 for g in v.link_faces):
            prot.append(v.co.copy())
            if DEBUG:
                for g in v.link_faces:
                    if not is_skin(g): PM[(A, B)[g[src]].data.materials[g.material_index].name] = PM.get((A, B)[g[src]].data.materials[g.material_index].name, 0) + 1
    pa = sorted(arc[int(ang(p) / dth) % NB] for p in prot)
    line = _rip_line(L, D, seam.seed, 1.0)
    def damp(a):
        if not pa: return 1.0
        i = bisect.bisect_left(pa, a)
        d = min(abs(a - pa[k % len(pa)]) for k in (i - 1, i)) if len(pa) > 1 else abs(a - pa[0])
        d = min(d, L - d)
        return max(0.0, min(1.0, (d - 0.04) / 0.12))
    line = [(a, o * damp(a)) for a, o in line]
    line[-1] = (L, line[0][1])
    if DEBUG:
        log('  prot mats %s' % PM)
        log('  joint %d, band %d, prot %d, centre %s, max |off| %.3f, damped corners %d/%d' % (len(joint), len(fs), len(prot),
            tuple(round(x, 2) for x in c0), max(abs(o) for _, o in line), sum(1 for a, o in line if damp(a) < 0.5), len(line)))
    # every face remembers which face it was before the cuts, so the pieces can be joined back afterwards
    fid = bm.faces.layers.int.new('fid')
    for i, f in enumerate(bm.faces): f[fid] = i
    ths = [th_of(a) for a, _ in line]
    # cut: radial planes at every corner of the line, then each segment's own plane
    for th in ths[:-1]:
        r = u * math.cos(th) + w * math.sin(th)
        fs = band()
        bmesh.ops.bisect_plane(bm, geom=list({e for f in fs for e in f.edges}) + fs + list({v for f in fs for v in f.verts}),
                               plane_co=c0, plane_no=seam.n.cross(r).normalized(), dist=1e-5)
    segs = []
    for k in range(len(line) - 1):
        t0, t1 = ths[k], ths[k + 1]
        P0, P1 = pos(t0, line[k][1]), pos(t1, line[k + 1][1])
        tm = 0.5 * (t0 + t1); rm = u * math.cos(tm) + w * math.sin(tm)
        N = (P1 - P0).cross(rm)
        if N.length < 1e-9: N = seam.n.copy()
        N.normalize()
        if N.dot(seam.n) < 0: N = -N
        segs.append((t0, t1, P0, N))
    for t0, t1, P0, N in segs:
        fs = [f for f in band() if _in_seg(ang(f.calc_center_median()), t0, t1)]
        if not fs: continue
        bmesh.ops.bisect_plane(bm, geom=list({e for f in fs for e in f.edges}) + fs + list({v for f in fs for v in f.verts}),
                               plane_co=P0, plane_no=N, dist=1e-5)
    fs = band(); bset = set(fs)
    starts = [s[0] for s in segs]
    for f in bm.faces:
        if not is_skin(f): f[lab] = -1; continue
        if f not in bset: f[lab] = f[src]; continue
        c = f.calc_center_median(); th = ang(c)
        k = max(0, bisect.bisect_right(starts, th) - 1)
        if not _in_seg(th, segs[k][0], segs[k][1]): k = len(segs) - 1
        t0, t1, P0, N = segs[k]
        side = 1 if (c - P0).dot(N) > 0 else 0
        # only the strip between the joint and the line changes hands (a part may carry on past the plane beside a
        # partial joint, like the fuselage next to an intake)
        f[lab] = side if (side == 1 and f[src] == 0 and seam.s(c) < 0) or (side == 0 and f[src] == 1 and seam.s(c) > 0) else f[src]
    # safety: a band face must connect (through faces of its label) to that part's skin outside the band
    flipped = 0
    for _ in range(6):
        seen = set(); stack = [f for f in bm.faces if f[lab] >= 0 and f not in bset]
        seen.update(stack)
        while stack:
            f = stack.pop()
            for e in f.edges:
                for g in e.link_faces:
                    if g not in seen and g[lab] == f[lab]: seen.add(g); stack.append(g)
        flips = [f for f in fs if f not in seen]
        if not flips: break
        flipped += len(flips)
        for f in flips: f[lab] = 1 - f[lab]
    # merge the cut pieces back into big faces on each side (keeps the rip outline)
    for f in fs: f.material_index = 30000 + f[lab]
    vs = list({v for f in fs for v in f.verts if all(g in bset for g in v.link_faces)})
    es = list({e for f in fs for e in f.edges if all(g in bset for g in e.link_faces)})
    # first join the pieces of each original face that ended up on the same side: only the rip line itself keeps new
    # edges and vertices (the cuts cross the whole band, which would otherwise leave extra vertices everywhere)
    rejoin = [e for e in es if len(e.link_faces) == 2 and e.link_faces[0][fid] == e.link_faces[1][fid]
              and e.link_faces[0][lab] == e.link_faces[1][lab]]
    bmesh.ops.dissolve_edges(bm, edges=rejoin, use_verts=False)
    fs = [f for f in bm.faces if f.material_index >= 30000]
    # then the vertices those cuts left on the original edges (two edges, one side); the corners of the rip stay
    def straight(v):
        if len(v.link_edges) != 2: return False
        d0, d1 = [(e.other_vert(v).co - v.co) for e in v.link_edges]
        return d0.length > 1e-7 and d1.length > 1e-7 and d0.normalized().dot(d1.normalized()) < -0.99995
    lone = [v for v in {v for f in fs for v in f.verts} if straight(v)]
    if DEBUG:
        from collections import Counter
        log('  rejoin %d edges, lone %d, valence %s' % (len(rejoin), len(lone), Counter(len(v.link_edges) for v in {v for f in fs for v in f.verts}).most_common(6)))
    bmesh.ops.dissolve_verts(bm, verts=lone)
    fs = [f for f in bm.faces if f.material_index >= 30000]; bset = set(fs)
    vs = list({v for f in fs for v in f.verts if all(g in bset for g in v.link_faces)})
    es = list({e for f in fs for e in f.edges if all(g in bset for g in e.link_faces)})
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(1.0), verts=vs, edges=es, delimit={'MATERIAL', 'UV'})
    moved = [0, 0]; out = {}
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
        b2.faces.layers.int.remove(l2); b2.faces.layers.int.remove(b2.faces.layers.int['src']); b2.faces.layers.int.remove(b2.faces.layers.int['fid'])
        b2.transform(o.matrix_world.inverted())
        out[o.name] = b2
    bm.free()
    for o in (A, B):
        b2 = out[o.name]; b2.normal_update(); b2.to_mesh(o.data); o.data.update(); b2.free()
    tree = _pose_bvhs(objs)
    nb = sum(_tear_cap(o, seam, tree) for o in (A, B))
    log('rip %s|%s: line %.1f m, %d corners, %d faces to %s, %d to %s, safety flips %d, bulkhead holes %d' % (
        seam.a, seam.b, L, len(line), moved[1], seam.b, moved[0], seam.a, flipped, nb))
    return moved[0] + moved[1]


def _in_seg(th, t0, t1):
    return t0 - 1e-6 <= th <= t1 + 1e-6


def rip_all(objs, log=print):
    n = 0
    for s in seams():
        if s.a in objs and s.b in objs: n += rip(s, objs, log)
    log('ripped seams: %d faces changed part' % n)


if __name__ == '__main__':
    a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    bpy.ops.wm.open_mainfile(filepath=a[0])
    rip_all({o.name: o for o in bpy.data.objects if o.type == 'MESH'})
    bpy.ops.wm.save_as_mainfile(filepath=a[1])
