# Executed inside build_pb22_detail.py (shares its namespace): forward fuselage d 3.4-12.6 with the integrated crew cabin.
# Parts: cockpit (d 3.4-7.6, pilot and co-pilot), fuselage_FF (7.6-10.1, navigator and weapons officer), fuselage_F (10.1-12.6).
from pb22_cabin import UnionSection, Grid, in_rect, mirror_rect, boundary_edges

CAB_SPLIT = (7.60, 10.10)
CAB_D = (4.95, 9.40)               # pressurised cabin lining (front bulkhead behind the radar, rear bulkhead behind the navigators)
FLOOR_Z = 2.05
LINING = 0.05                      # skin + frame depth: window reveals and hatch thickness
SEAT_P, SEAT_N = (0.34, 6.50, 2.66), (0.34, 8.25, 2.505)   # crew seat reference points (x, d, z): pilots raised 15 cm (20 cm clipped the seat through the roof, 2026-10-19)

HUMP = Section([(4.30, 2.88, 0, prof_se(0.30, 0.13, 2.4)), (4.90, 2.95, 0, prof_se(0.58, 0.29, 2.5)),
                (5.60, 3.08, 0, prof_se(0.74, 0.46, 2.6)), (6.30, 3.22, 0, prof_se(0.80, 0.47, 2.7)),
                (7.60, 3.26, 0, prof_se(0.81, 0.43, 2.8)), (9.00, 3.26, 0, prof_se(0.78, 0.39, 2.8)),
                (10.4, 3.28, 0, prof_se(0.66, 0.28, 2.8)), (11.8, 3.40, 0, prof_se(0.44, 0.08, 2.6))], 64)
FRONT = UnionSection(BODY, HUMP, 0.10)

WINDOWS = {'ws_C': (5.00, 6.15, 82.5, 97.5)}
# forward view (2026-10-19): the old windscreen front edge stays as a support arch, with clear glass in front of and
# below it down to a low sill; with the pilots raised the view clears -7.5 deg over the nose; the old posts become thin frame bars
WS_ARCH_D, WS_FRONT_D, WS_SILL_Z, WS_A = 5.025, 3.80, 2.93, (37.5, 142.5)
WS_POSTS = (80.625, 99.375)
DECK_Z = WS_SILL_Z - 0.03
WS_FA = (41.25, 138.75)
# crew hatches (Tu-22M3 style, also the crew entry doors): a roof panel hinged on the centre spine plus a cut-out down the
# fuselage side, opening outward to each side. The small side windows ride in the hatches. Each is a list of rects.
HATCHES, HATCH_WIN = {}, {}
for side in ('R', 'L'):
    m = (lambda r: r) if side == 'R' else mirror_rect
    WINDOWS[f'ws_{side}'] = m((5.05, 6.15, 37.5, 78.75))
    # roof panel and side cut-out share one fore/aft extent, so each hatch is a plain wrap-round panel with straight edges
    HATCHES[f'P{side}'] = [m((6.30, 7.45, 56.25, 86.25)), m((6.30, 7.45, 28.125, 56.25))]
    HATCHES[f'N{side}'] = [m((7.95, 9.05, 56.25, 86.25)), m((7.95, 9.05, 28.125, 56.25))]
    HATCH_WIN[f'P{side}'] = [m((6.45, 7.05, 63.75, 82.5))]       # 0.4.7: the low side window became a round porthole at head height (PORTHOLE)
    # 0.4.9: the rear hatch windows are cut as level rectangles further down (REAR_WIN), not grid cells that follow the hatch's slope
def in_any(d, a, rs): return any(in_rect(d, a, r) for r in rs)
WS_ARCH_BAND = (5.00, 5.055)       # the support arch: a band of skin across the canopy, flush with the glass either side
def ws_frame(d, a):
    """frame members are skin-surface bands between the panes (flush, like a real canopy frame), not bars stuck on top"""
    if WS_ARCH_BAND[0] <= d <= WS_ARCH_BAND[1]: return True
    if d > WS_ARCH_BAND[1]: return any(abs(a - p) < 1.9 for p in WS_POSTS)          # posts between the side and centre panes
    return abs(a - 90.0) < 3.8                                                        # centre post splitting the front pane
def in_ws(d, a, z):
    a = (a + 90.0) % 360.0 - 90.0
    if not (WS_A[0] <= a <= WS_A[1]): return False
    if ws_frame(d, a): return False
    if 5.00 <= d <= 6.15: return True                                   # the old panes and the posts between them
    return WS_FRONT_D <= d < 5.00 and WS_FA[0] <= a <= WS_FA[1]     # front pane: straight sill along a constant-angle line
ALL_RECTS = list(WINDOWS.values()) + [r for v in HATCHES.values() for r in v] + [r for v in HATCH_WIN.values() for r in v]

dl = {3.4, 12.6, *CAB_SPLIT, *CAB_D, WS_FRONT_D, 4.75, WS_ARCH_BAND[1]}
for r in ALL_RECTS: dl.update(r[:2])
dl.update(BODY.d[i] for i in range(len(BODY.d)) if 3.4 < BODY.d[i] < 12.6)
dl.update(HUMP.d)
dl = sorted(dl)
fine = []
for a, b in zip(dl, dl[1:]):
    n = max(int(math.ceil((b - a) / 0.30 - 1e-6)), 1)        # grid rings at most 0.30 m apart (was 0.15; every window, hatch and split edge is still a ring)
    fine += [a + (b - a) * j / n for j in range(n)]
fine.append(dl[-1])
G = Grid(FRONT, [round(x, 5) for x in fine])

def part_of(d):
    return 'cockpit' if d < CAB_SPLIT[0] else ('fuselage_FF' if d < CAB_SPLIT[1] else 'fuselage_F')
for nm, par in (('fuselage_F', None), ('fuselage_FF', 'fuselage_F'), ('cockpit', 'fuselage_FF')):
    part(nm, parent=par)

class VCache:
    def __init__(self, mb): self.mb, self.v = mb, {}
    def __call__(self, k, i, off=0.0):
        key = (k, i % G.N, round(off, 4))
        if key not in self.v: self.v[key] = self.mb.bm.verts.new(G.pt(k, i, off))
        return self.v[key]
VC = {}
def vc(name):
    if name not in VC: VC[name] = VCache(part(name).mb)
    return VC[name]

def quad(name, k, i, off=0.0, mat=SKIN, flip=False, smooth=True):
    c = vc(name)
    vs = [c(k, i, off), c(k, i + 1, off), c(k + 1, i + 1, off), c(k + 1, i, off)]
    if flip: vs.reverse()
    try: part(name).mb.face(vs, None, mat, smooth)
    except ValueError: pass

def wall(name, cells, off0, off1, mat=SKIN):
    """Walls round the boundary of a cell set from offset off0 to off1, facing into the hole (towards the set)."""
    c = vc(name)
    S = set(cells)
    cen = sum((G.pt(k, i) for k, i in cells), Vector()) / len(cells)
    for (ka, ia), (kb, ib) in boundary_edges(cells, G):
        # own vertices 0.1 mm under the skin: shared ones bent the smooth skin normals round every opening
        A0, B0, A1, B1 = c(ka, ia, off0 - 1e-4), c(kb, ib, off0 - 1e-4), c(ka, ia, off1), c(kb, ib, off1)
        vs = [A0, B0, B1, A1]
        n = (vs[1].co - vs[0].co).cross(vs[3].co - vs[0].co)
        mid = (A0.co + B0.co) / 2
        if n.dot(cen - mid) < 0: vs.reverse()
        try: part(name).mb.face(vs, None, mat, False)
        except ValueError: pass

win_cells = {n: [] for n in WINDOWS}; hatch_cells = {n: [] for n in HATCHES}; hwin_cells = {n: [] for n in HATCH_WIN}
for k, i in G.cells():
    d, a = G.centre(k, i)
    nm = part_of(d)
    w = 'ws_C' if in_ws(d, a, (G.pt(k, i).z + G.pt(k + 1, i + 1).z) / 2) else None
    h = next((n for n, r in HATCHES.items() if in_any(d, a, r)), None)
    if w: win_cells[w].append((k, i)); continue
    if h:
        hatch_cells[h].append((k, i))
        if h in HATCH_WIN and in_any(d, a, HATCH_WIN[h]): hwin_cells[h].append((k, i))
        continue
    quad(nm, k, i)
    if CAB_D[0] <= d <= CAB_D[1] and G.pt(k, i).z > FLOOR_Z + 0.02 and G.pt(k + 1, i + 1).z > FLOOR_Z + 0.02:
        quad(nm, k, i, -LINING, INT, flip=True)
        quad(nm, k, i, -LINING + 0.004, INT)                  # back of the lining: no daylight through an open hatch

# crack skirts: the first cell row behind each part split is repeated 4 mm inside the skin on the part in front, so a
# hairline gap between the two separately transformed parts shows skin, not daylight
for split, front in ((CAB_SPLIT[0], 'cockpit'), (CAB_SPLIT[1], 'fuselage_FF')):
    for k, i in G.cells():
        if abs(G.d[k] - split) > 1e-4: continue
        dd, aa = G.centre(k, i)
        if any(in_rect(dd, aa, r) for r in ALL_RECTS) or in_ws(dd, aa, 9.0): continue
        quad(front, k, i, -0.012, DARK)      # dark and 12 mm in: at 4 mm the painted skirt z-fought the skin behind and read as a second seam (0.4.5)

# window holes: reveals through the lining and glass set into them (both faces, so it reads from the cabin too)
GLASS_OF = {}
for n, cells in win_cells.items():
    if not cells: continue
    owner = part_of(G.centre(*cells[0])[0])
    wall(owner, cells, 0.0, -LINING, SKIN)
    gname = 'canopy' if owner == 'cockpit' else 'canopy_R'
    part(gname, parent=owner, col=False)
    for k, i in cells:
        quad(gname, k, i, -0.004, GLASS)                     # set into the frame, just under the skin line: flush
        quad(gname, k, i, -0.004, GLASS, flip=True)

# windscreen frame: the support arch along the old front edge and two thin posts, on the outside of the glass
def ws_bar(pts, w, h=0.025, taper=0):
    mb = part('cockpit').mb; rings = []; h0 = h
    for j, (d, th) in enumerate(pts):
        p = FRONT.point(d, th, 0.004); n = FRONT.normal(d, th)
        if taper:   # the arch feet run down flush into the sill instead of ending square on the skin
            h = h0 * min(1.0, (min(j, len(pts) - 1 - j) + 0.15) / taper)
        q = FRONT.point(pts[min(j + 1, len(pts) - 1)][0], pts[min(j + 1, len(pts) - 1)][1]) - FRONT.point(pts[max(j - 1, 0)][0], pts[max(j - 1, 0)][1])
        u = q.cross(n).normalized() * (w / 2)
        rings.append([p + u, p - u, p - u + n * h, p + u + n * h])
    loft(mb, rings, True, True, SKIN, smooth=False)
# (frame members are now flush skin bands, see ws_frame; ws_bar is kept for one-off trim)

# crew hatches: separate parts on a hinge along their inboard (spine) edge (the game blows them off before the seats fire)
for n, cells in hatch_cells.items():
    if not cells: continue
    owner = 'cockpit' if n[0] == 'P' else 'fuselage_FF'
    side = n[1]
    ks = [k for k, i in cells]; isx = sorted({i for k, i in cells})
    i_in = max(isx) + 1 if side == 'R' else min(isx)           # inboard (spine) edge node index
    k0, k1 = min(ks), max(ks) + 1
    hl = (G.pt(k0, i_in) + G.pt(k1, i_in)) / 2
    hname = f'hatch_{n}'
    part(hname, origin=hl, parent=pair(f'hatchHinge_{n}', hl, axis=(0, 1, 0), parent=owner), col=False)
    wall(owner, cells, 0.0, -LINING, INT)                        # hull side of the opening (seen once the hatch is gone)
    wset = set(hwin_cells.get(n, []))
    for k, i in cells:
        if (k, i) in wset: continue
        quad(hname, k, i, 0.0, SKIN)
        quad(hname, k, i, -LINING, INT, flip=True)
    # hatch edge walls face outwards from the hatch
    c = vc(hname); cen = sum((G.pt(k, i) for k, i in cells), Vector()) / len(cells)
    for (ka, ia), (kb, ib) in boundary_edges(cells, G):
        A0, B0, A1, B1 = c(ka, ia, -1e-4), c(kb, ib, -1e-4), c(ka, ia, -LINING), c(kb, ib, -LINING)
        vs = [A0, B0, B1, A1]
        nrm = (vs[1].co - vs[0].co).cross(vs[3].co - vs[0].co)
        if nrm.dot((A0.co + B0.co) / 2 - cen) < 0: vs.reverse()
        try: part(hname).mb.face(vs, None, SKIN, False)
        except ValueError: pass
    if wset:
        wall(hname, list(wset), 0.0, -LINING, SKIN)
        for k, i in wset:
            quad(hname, k, i, -0.004, GLASS); quad(hname, k, i, -0.004, GLASS, flip=True)

# pilot portholes (2026-10-19): a round window in each pilot hatch looking straight out to the side, centred on the
# pilot's head, glazed with a domed blister the pilot can lean into to look a little forward or aft. Cut through the hatch
# skin and lining with a skin reveal round the hole; the dome rises from the skin line (both faces, so it reads from inside).
PORTHOLE = (6.70, 3.25, 0.15, 0.06)      # d, z centre (0.4.7b: lowered onto the vertical hatch side; pilot eye d 6.70, z 3.31 stays inside), hole radius, dome height
PORT_GLASS_R, PORT_FRAME_R, PORT_FRAME_H, PORT_DOME_H = 0.145, 0.185, 0.002, 0.06   # glass base radius, frame outer radius, frame clearance, bulge
PORT_BEVEL = 0.025                       # frame bevel: flat face ends at FRAME_R - this, meets the skin at FRAME_R + this
from mathutils.bvhtree import BVHTree as _BVH
for side, s in (('L', -1), ('R', 1)):
    hp = part(f'hatch_P{side}'); hb = hp.mb.bm
    hb.verts.ensure_lookup_table(); hb.faces.ensure_lookup_table()
    tree = _BVH.FromBMesh(hb)
    pd, pz, pr, ph = PORTHOLE; NSEG = 32
    def skin_at(dd, zz):
        loc, nrm, _i, _ = tree.ray_cast(Vector((s * 2.0, Y(dd), zz)), Vector((-s, 0, 0)), 3.0)
        return loc, nrm
    # cutter: a 32-sided cylinder along x through the hatch
    me = bpy.data.meshes.new('cut_port'); cb = bmesh.new()
    r0 = [cb.verts.new((s * 0.55, Y(pd) + pr * math.cos(2 * math.pi * k / NSEG), pz + pr * math.sin(2 * math.pi * k / NSEG))) for k in range(NSEG)]
    r1 = [cb.verts.new((s * 1.10, Y(pd) + pr * math.cos(2 * math.pi * k / NSEG), pz + pr * math.sin(2 * math.pi * k / NSEG))) for k in range(NSEG)]
    for k in range(NSEG): cb.faces.new((r0[k], r0[(k + 1) % NSEG], r1[(k + 1) % NSEG], r1[k]))
    cb.faces.new(r0); cb.faces.new(r1[::-1])
    bmesh.ops.recalc_face_normals(cb, faces=cb.faces[:]); cb.to_mesh(me); cb.free()
    co = bpy.data.objects.new('cut_port', me); C_TMP.objects.link(co); me.materials.append(MATS[SKIN])
    tm = bpy.data.meshes.new('hp_tmp'); hb.to_mesh(tm)
    for mm in MATS: tm.materials.append(mm)
    to = bpy.data.objects.new('hp_tmp', tm); C_TMP.objects.link(to)
    md = to.modifiers.new('cut', 'BOOLEAN'); md.operation = 'DIFFERENCE'; md.solver = 'EXACT'; md.object = co
    res = bpy.data.meshes.new_from_object(to.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    hb.free(); hp.mb.bm = bmesh.new(); hp.mb.bm.from_mesh(res); hb = hp.mb.bm
    hp.mb.uv = hb.loops.layers.uv.get('UVMap') or hb.loops.layers.uv.new('UVMap')
    nwall = 0
    for f in hb.faces:
        c = f.calc_center_median()
        if f.material_index >= len(MATS) or (abs(f.normal.x) < 0.3 and abs(math.hypot(c.y - Y(pd), c.z - pz) - pr) < 0.004): f.material_index = SKIN   # reveal walls only (a lining n-gon round the hole can have its centre near pr too); f.smooth = False; nwall += 1
    bpy.data.objects.remove(to); bpy.data.meshes.remove(tm); bpy.data.meshes.remove(res); bpy.data.objects.remove(co); bpy.data.meshes.remove(me)
    # 0.4.7b: an undistorted spherical cap 6 cm high on a flat round mounting frame. The frame plane is square to
    # the skin normal at the centre and stands just clear of the curved skin; a skirt closes it down to the skin, a sleeve
    # lines the hole beneath it. Frame bolts are painted in the livery (pb22_panels).
    tree = _BVH.FromBMesh(hb)                                  # the cut hatch
    hits = [skin_at(pd - PORT_FRAME_R * math.cos(2 * math.pi * k / 8), pz + PORT_FRAME_R * math.sin(2 * math.pi * k / 8))[0] for k in range(8)]
    ax_ = (hits[0] - hits[4]).cross(hits[2] - hits[6]).normalized()
    if ax_.x * s < 0: ax_ = -ax_
    loc = sum(hits, Vector()) / 8
    u_ = ax_.cross(Vector((0, 0, 1))).normalized(); w_ = ax_.cross(u_).normalized()
    rg, ro = PORT_GLASS_R, PORT_FRAME_R
    def circ(c, r, k): a = 2 * math.pi * k / NSEG; return c + u_ * (r * math.cos(a)) + w_ * (r * math.sin(a))
    # plane height: clear the skin under the whole frame by 6 mm
    hmax = 0.0
    for k in range(NSEG):
        q = circ(loc, ro, k); hit = tree.ray_cast(q + ax_ * 0.3, -ax_, 0.6)[0]
        if hit is not None: hmax = max(hmax, (hit - loc).dot(ax_))
    C0 = loc + ax_ * (hmax + PORT_FRAME_H)
    inner = [circ(C0, rg, k) for k in range(NSEG)]; outer = [circ(C0, ro - PORT_BEVEL, k) for k in range(NSEG)]   # flat face stops short; the bevel runs out to the skin
    foot = []
    for k in range(NSEG):
        q = circ(C0, ro + PORT_BEVEL, k); hit = tree.ray_cast(q + ax_ * 0.1, -ax_, 0.6)[0]
        foot.append((hit if hit is not None else q - ax_ * (hmax + PORT_FRAME_H)) - ax_ * 0.002)
    sleeve = [circ(C0 - ax_ * (hmax + PORT_FRAME_H + 0.05), rg, k) for k in range(NSEG)]
    mb = hp.mb
    # rounded bevel: a mid ring between the frame edge and the foot, lifted so the profile is convex
    mid = []
    for k in range(NSEG):
        a_, b_ = outer[k], foot[k]; m_ = a_.lerp(b_, 0.45)
        mid.append(m_ + ax_ * (0.30 * max((a_ - b_).dot(ax_), 0.0)))
    vi, vo, vf, vs = mb.verts(inner), mb.verts(outer), mb.verts(foot), mb.verts(sleeve); vm = mb.verts(mid)
    vi2, vs2 = mb.verts(inner), mb.verts(sleeve)              # own verts for the sleeve's back faces
    def quad(a, b, c, d):
        return mb.face([a, b, c, d], None, SKIN, False)
    for k in range(NSEG):
        k1 = (k + 1) % NSEG
        f = quad(vi[k], vi[k1], vo[k1], vo[k])                  # frame face
        if f.normal.dot(ax_) < 0: f.normal_flip()
        for a_, b_ in ((vo, vm), (vm, vf)):                    # bevel down to the skin
            f = quad(a_[k], a_[k1], b_[k1], b_[k]); f.smooth = True
            if (f.calc_center_median() - C0).dot(f.normal) < 0: f.normal_flip()
        quad(vi[k], vi[k1], vs[k1], vs[k]); quad(vs2[k], vs2[k1], vi2[k1], vi2[k])   # sleeve through the hole, both sides
    # glass: a true spherical cap, base radius rg on the frame plane, height PORT_DOME_H
    ph = PORT_DOME_H; R_ = (rg * rg + ph * ph) / (2 * ph); fmax = math.asin(min(rg / R_, 1.0)); NR = 6
    Cs = C0 - ax_ * (R_ - ph)                                  # sphere centre
    rings = []
    for j in range(NR):
        f_ = fmax * (1 - j / NR)
        rings.append([Cs + ax_ * (R_ * math.cos(f_)) + (circ(C0, 1.0, k) - C0) * (R_ * math.sin(f_)) for k in range(NSEG)])
    apex = C0 + ax_ * ph
    for flip in (False, True):
        vr = [mb.verts(r) for r in rings]; va = mb.verts([apex])[0]
        fs = [(vr[j][k], vr[j][(k + 1) % NSEG], vr[j + 1][(k + 1) % NSEG], vr[j + 1][k]) for j in range(NR - 1) for k in range(NSEG)]
        fs += [(vr[-1][k], vr[-1][(k + 1) % NSEG], va) for k in range(NSEG)]
        for fv in fs:
            f = mb.face(list(fv), None, GLASS, True)
            outward = (f.calc_center_median() - Cs).dot(f.normal) > 0
            if outward == flip: f.normal_flip()
    print('porthole', side, 'centre', tuple(round(v, 3) for v in C0), 'frame plane %.3f above skin' % (hmax + PORT_FRAME_H), 'axis', tuple(round(v, 3) for v in ax_))
    print('porthole', side, 'reveal faces', nwall)

# rear crew windows (2026-10-19): level with the aircraft, straight fore and aft, not tilted with the hatch panel.
# Same place and size as the old grid window (d 8.25-8.70, section angle 31.875-41.25 deg); cut through the hatch with a
# level box, skin-coloured reveal round the hole, glass just under the skin line (both faces).
REAR_WIN = (8.25, 8.70, 31.875, 41.25)
_wz = [FRONT.point((REAR_WIN[0] + REAR_WIN[1]) / 2, math.radians(a_)).z for a_ in REAR_WIN[2:]]
RW_Z = (min(_wz), max(_wz))
for side, s in (('L', -1), ('R', 1)):
    hp = part(f'hatch_N{side}'); hb = hp.mb.bm
    me = bpy.data.meshes.new('cut_rw'); cb = bmesh.new()
    xs, ys, zs = (s * 0.40, s * 1.20), (Y(REAR_WIN[0]), Y(REAR_WIN[1])), RW_Z
    bv = [cb.verts.new((xs[i], ys[j], zs[k])) for i in (0, 1) for j in (0, 1) for k in (0, 1)]
    bmesh.ops.convex_hull(cb, input=bv)
    bmesh.ops.recalc_face_normals(cb, faces=cb.faces[:]); cb.to_mesh(me); cb.free()
    co = bpy.data.objects.new('cut_rw', me); C_TMP.objects.link(co); me.materials.append(MATS[SKIN])
    tm = bpy.data.meshes.new('hn_tmp'); hb.to_mesh(tm)
    for mm in MATS: tm.materials.append(mm)
    to = bpy.data.objects.new('hn_tmp', tm); C_TMP.objects.link(to)
    md = to.modifiers.new('cut', 'BOOLEAN'); md.operation = 'DIFFERENCE'; md.solver = 'EXACT'; md.object = co
    res = bpy.data.meshes.new_from_object(to.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    hb.free(); hp.mb.bm = bmesh.new(); hp.mb.bm.from_mesh(res); hb = hp.mb.bm
    hp.mb.uv = hb.loops.layers.uv.get('UVMap') or hb.loops.layers.uv.new('UVMap')
    ymin, ymax = min(ys), max(ys)
    for f in hb.faces:
        c = f.calc_center_median()
        on_wall = (abs(f.normal.x) < 0.3 and (min(abs(c.y - ymin), abs(c.y - ymax)) < 0.004 or min(abs(c.z - RW_Z[0]), abs(c.z - RW_Z[1])) < 0.004))
        if f.material_index >= len(MATS) or on_wall: f.material_index = SKIN
    bpy.data.objects.remove(to); bpy.data.meshes.remove(tm); bpy.data.meshes.remove(res); bpy.data.objects.remove(co); bpy.data.meshes.remove(me)
    tree = _BVH.FromBMesh(hb)
    # glass: a 5 x 3 grid following the skin curve, 4 mm under the skin line; rays hit the hatch skin just outside the hole
    NU, NV = 5, 3
    pts = []
    for j in range(NV):
        row = []
        for i in range(NU):
            dd = REAR_WIN[0] + (REAR_WIN[1] - REAR_WIN[0]) * i / (NU - 1); zz = RW_Z[0] + (RW_Z[1] - RW_Z[0]) * j / (NV - 1)
            fx = s * abs(FRONT.point(dd, math.radians(36.5)).x)                          # fallback: the section surface
            x_ = None
            for d_off in (0.0, 0.03, -0.03, 0.06, -0.06):
                hit = tree.ray_cast(Vector((s * 2.0, Y(dd), zz + d_off)), Vector((-s, 0, 0)), 3.0)[0]
                if hit is not None: x_ = hit.x; break
            row.append(Vector((x_ if x_ is not None else fx, Y(dd), zz)) - Vector((s * 0.004, 0, 0)))
        pts.append(row)
    mb = hp.mb
    for flip in (False, True):
        vg = [mb.verts(r) for r in pts]
        for j in range(NV - 1):
            for i in range(NU - 1):
                f = mb.face([vg[j][i], vg[j][i + 1], vg[j + 1][i + 1], vg[j + 1][i]], None, GLASS, False)
                if (f.normal.x * s > 0) == flip: f.normal_flip()
    print('rear window', side, 'z %.3f-%.3f' % RW_Z)

# cabin floor and bulkheads (lining material)
def kidx(d): return min(range(len(G.d)), key=lambda k: abs(G.d[k] - d))
for nm, d0, d1 in (('cockpit', CAB_D[0], CAB_SPLIT[0]), ('fuselage_FF', CAB_SPLIT[0], CAB_D[1])):
    mb = part(nm).mb
    vs = mb.verts([Vector((-0.80, Y(d0), FLOOR_Z)), Vector((0.80, Y(d0), FLOOR_Z)), Vector((0.80, Y(d1), FLOOR_Z)), Vector((-0.80, Y(d1), FLOOR_Z))])
    mb.face(vs, None, INT, False)
    vs = mb.verts([Vector((-0.80, Y(d0), FLOOR_Z - 0.004)), Vector((-0.80, Y(d1), FLOOR_Z - 0.004)), Vector((0.80, Y(d1), FLOOR_Z - 0.004)), Vector((0.80, Y(d0), FLOOR_Z - 0.004))])
    mb.face(vs, None, INT, False)                             # floor seen from both sides
for nm, d, front in (('cockpit', CAB_D[0], True), ('fuselage_FF', CAB_D[1], False)):
    k = kidx(d); c = vc(nm)
    top = DECK_Z if front else 99.0                          # the front bulkhead stops at the windscreen deck
    ring = [i for i in range(G.N) if FLOOR_Z < G.pt(k, i, -LINING).z <= top]
    # walk the upper arc from the right side over the top to the left side
    ring.sort(key=lambda i: (G.thd[i] + 90.0) % 360.0)
    pts = [G.pt(k, i, -LINING) for i in ring]
    mb = part(nm).mb
    vs = mb.verts([Vector((pts[0].x, Y(d), FLOOR_Z))] + pts + [Vector((pts[-1].x, Y(d), FLOOR_Z))])
    if not front: vs.reverse()
    try: mb.face(vs, None, INT, False)
    except ValueError: pass

# windscreen deck: a floor over the forward equipment bay at sill height, from the front bulkhead to the glass front edge,
# so the cabin stays closed under the new low glazing (the glareshield sits on it)
def deck_x(d, z):
    best = None
    for j in range(361):
        th = math.radians(-90 + 180 * j / 360)
        q = FRONT.point(d, th, -LINING)
        if best is None or abs(q.z - z) < abs(best.z - z): best = q
    return abs(best.x)
mbd = part('cockpit').mb
ds_ = [WS_FRONT_D - 0.02 + (CAB_D[0] - WS_FRONT_D + 0.02) * j / 6 for j in range(7)]
for a_, b_ in zip(ds_, ds_[1:]):
    xa, xb = deck_x(a_, DECK_Z), deck_x(b_, DECK_Z)
    q = [Vector((-xa, Y(a_), DECK_Z)), Vector((xa, Y(a_), DECK_Z)), Vector((xb, Y(b_), DECK_Z)), Vector((-xb, Y(b_), DECK_Z))]
    mbd.face(mbd.verts(q), None, INT, False); mbd.face(mbd.verts(list(reversed(q))), None, INT, False)

# rear crew stations: a console in front of each seat (the front stations use the Medusa instrument panel in the game)
for s in (1, -1):
    x, d, z = s * SEAT_N[0], SEAT_N[1], SEAT_N[2]
    rbox(part('fuselage_FF').mb, (x, Y(d - 0.62), z + 0.20), (0.50, 0.22, 0.06), 0.01, INT)
    rbox(part('fuselage_FF').mb, (x, Y(d - 0.74), z + 0.48), (0.50, 0.05, 0.50), 0.01, INT)
    rbox(part('fuselage_FF').mb, (x + s * 0.30, Y(d - 0.10), z + 0.15), (0.10, 0.70, 0.30), 0.01, INT)

# fuselage_F needs caps for the nose-well boolean (dropped again afterwards)
cF = vc('fuselage_F')
for d, rev in ((CAB_SPLIT[1], True), (12.6, False)):
    k = kidx(d)
    vs = [cF(k, i) for i in range(G.N)]
    if rev: vs.reverse()
    part('fuselage_F').mb.face(vs, None, SKIN, False)

# reference empties for the game builder: crew seats (Pilot transforms) and the Medusa instrument panel origin
for nm, (x, d, z), par in (('seat_PL', (-SEAT_P[0], SEAT_P[1], SEAT_P[2]), 'cockpit'), ('seat_PR', SEAT_P, 'cockpit'),
                           ('seat_NL', (-SEAT_N[0], SEAT_N[1], SEAT_N[2]), 'fuselage_FF'), ('seat_NR', SEAT_N, 'fuselage_FF'),
                           ('cockpit_int_ref', (0.0, SEAT_P[1] - 0.092, SEAT_P[2] + 0.123), 'cockpit')):
    hinge(nm, (x, Y(d), z), size=0.3, parent=par)
print('cabin: grid rings', len(G.d), 'windows', {n: len(c) for n, c in win_cells.items()}, 'hatches', {n: len(c) for n, c in hatch_cells.items()})

# ---------------------------------------------------------------- small external parts on the forward fuselage
def dome(mb, c, n, r, mat=SKIN, N=14):
    """Sensor window: a low dome on a surface point c facing n."""
    n = Vector(n).normalized(); ref = Vector((0, 0, 1)) if abs(n.z) < 0.9 else Vector((1, 0, 0))
    u = n.cross(ref).normalized(); v = n.cross(u)
    rings = []
    for k in range(5):
        a = math.pi / 2 * k / 4
        rr = r * math.cos(a); h = r * math.sin(a) - r * 0.35
        rings.append([Vector(c) + n * h + (u * math.cos(2 * math.pi * j / N) + v * math.sin(2 * math.pi * j / N)) * max(rr, 1e-4) for j in range(N)])
    loft(mb, rings, True, False, mat)
def front_pt(d, z, side):
    best = None
    for k in range(721):
        th = math.radians(-90 + 180 * k / 720)
        if side < 0: th = math.pi - th
        p = FRONT.point(d, th)
        if best is None or abs(p.z - z) < abs(best.z - z): best, bth = p, th
    return best, FRONT.normal(d, bth)
for s in (1, -1):
    # L-shaped air-data probes on the lower radome flanks, pointing forward and down
    p, n = front_pt(4.30, 1.88, s)
    fwd = Vector((0, 0.87, -0.5))
    tube(part('cockpit').mb, [p - n * 0.03, p + n * 0.07, p + n * 0.09 + fwd * 0.06, p + n * 0.09 + fwd * 0.40], [0.03, 0.025, 0.02, 0.012], N=8, mat=MECH)
    # angle-of-attack vane
    p, n = front_pt(5.10, 2.10, s)
    plate(part('cockpit').mb, [p + n * 0.005, p + n * 0.08 + Vector((0, 0.03, 0.02)), p + n * 0.08 + Vector((0, 0.08, 0.02)), p + n * 0.005 + Vector((0, 0.06, 0))], 0.008, (0, 0, 1), MECH)
    # forward missile-approach-warning windows on the upper cheeks
    p, n = front_pt(9.60, 2.90, s)
    dome(part('fuselage_FF').mb, p, n + Vector((0, 0.6, 0)), 0.055)
# anti-collision beacon under the cabin
p, n = front_pt(6.2, 1.30, 1)
p = FRONT.point(6.2, -math.pi / 2)
dome(part('cockpit').mb, p, (0, 0, -1), 0.06, GLASS)
