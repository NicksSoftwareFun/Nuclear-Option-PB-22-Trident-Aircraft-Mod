# Executed inside build_pb22_detail.py after pb22_systems.py: the second structure pass, which ties the airframe into
# one coherent frame. Nose bay frames and the radar mount, frames and keel beams under the crew floor, a closing frame
# behind the cabin, the glove root rib, wing root ribs and lug arms, stringers over and under the wing fuel cells,
# a tip rib set, more fin and rudder structure with the fin posts carried down into the dorsal fillet, and spars and
# ribs in the all-moving tailplanes.
# Structure may join other structure, but every piece is built in a scratch mesh first and only kept if it stays
# inside the skin, touches no skin, glass, duct lining or system, and keeps out of the volumes things swing into.
STR2_LOG = {'kept': 0, 'rejected': []}


NM_INFO = []
# structure may meet other structure, and wires, hydraulic and fuel lines run through holes in frames and ribs
LINE_MATS = {MECH} | {i for i, m in enumerate(MATS) if m.name in ('PB22_wire', 'PB22_hyd', 'PB22_fuelline')}


def _bvh_nonmech():
    vs, fs = [], []
    for p in PARTS.values():
        bm = p.mb.bm; bm.verts.ensure_lookup_table(); bm.verts.index_update()
        base = len(vs)
        vs.extend(v.co.copy() for v in bm.verts)
        for f in bm.faces:
            if f.material_index in LINE_MATS: continue
            fs.append([base + v.index for v in f.verts])
            NM_INFO.append((p.name, f.material_index, f.calc_center_median().copy()))
    return BVHTree.FromPolygons(vs, fs, epsilon=0.0)


NONMECH_BVH = _bvh_nonmech()
SKIN_BVH2 = _world_tris(True)


def sfits(build, name, where):
    tmp = MeshBuilder(); build(tmp)
    bm = tmp.bm
    if not bm.verts: STR2_LOG['rejected'].append(f'{name}: nothing left to build'); tmp.bm.free(); return False
    why = None
    for v in bm.verts:
        k = _keep_out(v.co)
        if k is True or (k == 'glove' and where.startswith('wingroot')):
            why = f'keep-out at d{dd_of(v.co):.2f},x{v.co.x:.2f},z{v.co.z:.2f}'; break
    if why is None:
        c = sum((v.co for v in bm.verts), Vector()) / len(bm.verts)
        os_ = [c, c + Vector((0.2, 0, 0)), c - Vector((0.2, 0, 0)), c + Vector((0, 0.2, 0)), c - Vector((0, 0.2, 0))]
        up = any(SKIN_BVH2.ray_cast(o, Vector((0, 0, 1)))[0] is not None for o in os_)
        dn = any(SKIN_BVH2.ray_cast(o, Vector((0, 0, -1)))[0] is not None for o in os_)
        if not (up and dn): why = 'outside skin'
    if why is None:
        ov = _bvh_of(bm).overlap(NONMECH_BVH)
        if ov:
            hit = {}
            for _, j in ov[:100]:
                n_, mi, cc = NM_INFO[j]; hit.setdefault((n_, mi), cc)
            why = 'clips ' + ', '.join(f'{n_}/{MATS[mi].name[5:]}@d{dd_of(cc):.2f},x{cc.x:.2f},z{cc.z:.2f}' for (n_, mi), cc in list(hit.items())[:3])
    if why:
        STR2_LOG['rejected'].append(f'{name}: {why}'); tmp.bm.free(); return False
    tmp.bm.free()
    build(PARTS[where].mb)
    STR2_LOG['kept'] += 1
    return True


def splace(build, name, where, shrink=None):
    if sfits(build, name, where): return True
    if shrink:
        first = STR2_LOG['rejected'].pop()
        for k in range(1, 5):
            if sfits(shrink(k), f'{name}~{k}', where): return True
            last = STR2_LOG['rejected'].pop()
        STR2_LOG['rejected'].append(first + ' | smallest: ' + last.split(': ', 1)[1])
    return False


def ring_frame(mb, d, depth=0.06, width=0.04, off=0.012, mask=None, step=3):
    """frame() into any mesh: a ring hugging the BODY skin at d, split into runs where `mask` is true."""
    po, pi = BODY.ring(d, -off), BODY.ring(d, -(off + depth))
    idx = list(range(0, len(po), step))
    keep = [not (mask and (mask(po[k]) or mask(pi[k]))) for k in idx]
    w = Vector((0, width / 2, 0))
    sec = lambda k: [po[k] + w, po[k] - w, pi[k] - w, pi[k] + w]
    if all(keep):
        n0 = _fv(mb); loft(mb, [sec(k) for k in idx] + [sec(idx[0])], False, False, MECH, smooth=False); _closed(mb, n0); return
    n = len(idx); start = next(i for i in range(n) if not keep[i]); run = []
    for j in range(1, n + 1):
        i = (start + j) % n
        if keep[i]: run.append(idx[i])
        if (not keep[i] or j == n) and len(run) >= 2:
            n0 = _fv(mb); loft(mb, [sec(k) for k in run], True, True, MECH, smooth=False); _closed(mb, n0)
        if not keep[i]: run = []


def bar(mb, pts, r):
    n0 = _fv(mb); tube(mb, pts, r, N=4, mat=MECH); _closed(mb, n0)


KO = lambda p: _keep_out(p) is True


# ================================================================ nose bay: radar mount, frames, longerons and keel ahead of the cabin
splace(lambda m: rbox(m, (0, Y(3.20), 2.33), (0.34, 0.26, 0.28), 0.02, MECH), 'radar mount', 'nose')
NOSE_KO = lambda p: KO(p) or p.z > DECK_Z - 0.04          # frames under the windscreen stop below its deck
for d in (3.62, 4.05, 4.50, 4.92):
    splace(lambda m, d=d: ring_frame(m, d, mask=NOSE_KO), f'nose frame d{d}', 'cockpit',
           shrink=lambda k, d=d: (lambda m: ring_frame(m, d, depth=0.06 - 0.01 * k, width=0.03, off=0.010, mask=NOSE_KO)))
for th_deg in (20, 55, 125, 160, 200, 235, 270, 305, 340):
    th = math.radians(th_deg)
    ds = (3.40, 3.56, 3.72) if th_deg in (55, 125) else (3.40, 3.95, 4.50, 4.85)       # upper pair ends at the windscreen; others at the bulkhead
    pts = [BODY.point(d, th, -0.05) for d in ds]
    splace(lambda m, pts=pts: bar(m, pts, 0.022), f'nose longeron {th_deg}', 'cockpit',
           shrink=lambda k, th=th, ds=ds: (lambda m: bar(m, [BODY.point(d, th, -0.04 + 0.004 * k) for d in ds[:-1] + (ds[-1] - 0.05 * k,)], 0.018 - 0.002 * k)))

# ================================================================ under the crew floor: frames, keel beams and floor beams
FLOOR_TOP = 2.05 - 0.03
under = lambda p: KO(p) or p.z > FLOOR_TOP or (p.z < 1.55 and abs(p.x) < 0.40)      # open at the keel: chin window, well
for k in range(10):
    d = 5.25 + 0.5 * k
    part_ = 'cockpit' if d < 7.6 else 'fuselage_FF'
    splace(lambda m, d=d: ring_frame(m, d, mask=under), f'floor frame d{d:.2f}', part_,
           shrink=lambda kk, d=d: (lambda m: ring_frame(m, d, depth=0.05 - 0.008 * kk, width=0.03, off=0.012 + 0.02 * kk, mask=under)))
for xk in (-0.42, 0.0, 0.42):
    for d0, d1, part_ in ((4.95, 7.58, 'cockpit'), (7.62, 10.08, 'fuselage_FF')):
        splace(lambda m, xk=xk, d0=d0, d1=d1: rbox(m, (xk, Y((d0 + d1) / 2), FLOOR_TOP - 0.05), (0.05, d1 - d0, 0.09), 0.008, MECH),
               f'floor beam x{xk} d{d0}', part_,
               shrink=lambda k, xk=xk, d0=d0, d1=d1: (lambda m: rbox(m, (xk, Y((d0 + d1) / 2), FLOOR_TOP - 0.035), (0.04, d1 - d0, 0.06 - 0.01 * k), 0.006, MECH)))
# closing frame behind the cabin, where the cockpit section meets the forward fuselage
for d in (9.62, 9.92):
    splace(lambda m, d=d: ring_frame(m, d, depth=0.09, width=0.06, mask=KO), f'aft cabin frame d{d}', 'fuselage_FF',
           shrink=lambda k, d=d: (lambda m: ring_frame(m, d, depth=0.07 - 0.01 * k, width=0.04, off=0.012 + 0.02 * k, mask=lambda p: KO(p) or (p.z < 1.55 and abs(p.x) < 0.40))))
for th_deg in (210, 240, 300, 330):
    th = math.radians(th_deg)
    for d0, d1, part_ in ((4.98, 7.58, 'cockpit'), (7.62, 10.12, 'fuselage_FF')):
        pts = [BODY.point(d0 + (d1 - d0) * j / 4, th, -0.045) for j in range(5)]
        splace(lambda m, pts=pts: bar(m, pts, 0.02), f'cabin longeron {th_deg} d{d0}', part_,
               shrink=lambda k, pts=pts: (lambda m: bar(m, pts, 0.016 - 0.002 * k)))

# ================================================================ glove root rib and stringers, wing root ribs and lug arms
GST = [(1.85, 0.065), (2.6, 0.068), (3.6, 0.075), (4.6, 0.08), (5.35, 0.085)]
def _gt(x):
    for a, b in zip(GST, GST[1:]):
        if x <= b[0]: return a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0])
    return GST[-1][1]
def _gpt(s, x, c, side_, inset=0.012):
    le = glove_le(x); ch = 24.9 - le
    return Vector((s * x, Y(le + ch * c), GLOVE_Z + side_ * (naca_t(c, _gt(x)) * ch - inset)))
def _gok(x, p):
    return not (1.9 <= x <= 4.6 and BAY_DD[0] - 0.32 <= dd_of(p) <= BAY_DD[1] + 0.32 and p.z < 2.31)   # same box as the wheel-well keep-out

for side, s in (('R', 1), ('L', -1)):
    gw = f'wingroot_{side}'
    def grib(m, x, cs0=0.10, cs1=0.88, th=0.03, s=s):
        cs = [cs0 + (cs1 - cs0) * j / 10 for j in range(11)]
        top = [_gpt(s, x, c, 1) for c in cs]
        bot = [_gpt(s, x, c, -1) for c in cs]
        bot = [Vector((b.x, b.y, max(b.z, 2.31))) for b in bot]                       # stand on the gear pod / wheel-well roof
        n0 = _fv(m); plate(m, top + list(reversed(bot)), th, (1, 0, 0), MECH); _closed(m, n0)
    splace(lambda m: grib(m, 2.08), f'glove root rib {side}', gw,
           shrink=lambda k: (lambda m: grib(m, 2.08 + 0.04 * k, 0.12 + 0.02 * k, 0.86 - 0.02 * k, 0.02)))
    for c, sd in ((0.30, 1), (0.50, 1), (0.70, 1), (0.70, -1)):     # the lower c0.3/0.5 lines would run along the wheel-well roof
        if True:
            def gstr(m, c=c, sd=sd, inset=0.025, r=0.014, xe=4.55):
                pts = [_gpt(s, x, c, sd, inset) for x in (2.10, 2.6, 3.4, 4.0, xe)]
                pts = [p if (sd > 0 or _gok(abs(p.x), p)) and not _keep_out(p) else None for p in pts]
                runs, cur = [], []
                for p in pts + [None]:
                    if p is None:
                        if cur: runs.append(cur)
                        cur = []
                    else: cur.append(p)
                run = max(runs, key=len) if runs else []
                if len(run) >= 2: bar(m, run, r)
            splace(gstr, f'glove stringer {side} c{c} {sd}', gw,
                   shrink=lambda k, c=c, sd=sd: (lambda m: gstr(m, c, sd, 0.025 + 0.004 * k, 0.012 - 0.0015 * k, 4.55 - 0.1 * k)))

    w1 = f'wing1_{side}'
    # heavy root rib between the spars and two arms from the pivot lug out to the spar roots
    def wrib(m, x, c0=0.14, c1=0.64, th=0.03, inset=0.008):
        cs = [c0 + (c1 - c0) * j / 9 for j in range(10)]
        out = [wbox(m, s, x, c, inset)[0] for c in cs] + [wbox(m, s, x, c, inset)[1] for c in reversed(cs)]
        n0 = _fv(m); plate(m, out, th, (1, 0, 0), MECH); _closed(m, n0)
    splace(lambda m: wrib(m, 4.66), f'wing root rib {side}', w1,
           shrink=lambda k: (lambda m: wrib(m, 4.66 + 0.03 * k, 0.15 + 0.01 * k, 0.62 - 0.01 * k, 0.02, 0.012)))
    pv = Vector((s * PIVOT[0], Y(PIVOT[1]), PIVOT[2] + 0.07))       # above the stowed bogie under the glove
    for c in (0.15, 0.62):
        t, b = wbox(None, s, 4.75, c)
        tgt = (t + b) / 2 + Vector((0, 0, 0.02))
        p0 = pv + (tgt - pv).normalized() * 0.22                       # clear of the pivot pin cap
        splace(lambda m, tgt=tgt, p0=p0: bar(m, [p0, tgt], 0.035), f'lug arm {side} c{c}', w1,
               shrink=lambda k, tgt=tgt, p0=p0: (lambda m: bar(m, [p0 + (tgt - p0).normalized() * 0.05 * k, tgt], 0.035 - 0.005 * k)))

    # stringers over and under the fuel cells, rib to rib, on both panels; and a rib set in the tip
    for mbn, xs in ((w1, [5.45, 6.55, 7.75, 8.95, 10.15, W_SPLIT - 0.06]), (f'wing2_{side}', [W_SPLIT + 0.06, 11.95, 12.55, W_TIP - 0.07])):
        for c in (0.24, 0.33, 0.42, 0.51):
            for sd in (0, 1):
                def wstr(m, c=c, sd=sd, xs=xs, inset=0.016, r=0.007):
                    pts = [wbox(m, s, x, c, inset)[sd] for x in xs]
                    bar(m, pts, r)
                splace(wstr, f'wing stringer {mbn} c{c} {"top" if sd == 0 else "bot"}', mbn,
                       shrink=lambda k, c=c, sd=sd, xs=xs: (lambda m: wstr(m, c, sd, xs, 0.014 - 0.001 * k, 0.006 - 0.0005 * k)))
    tw = f'wingtip_{side}'
    for x in (W_TIP + 0.12, W_TIP + 0.26):
        splace(lambda m, x=x: wrib(m, x, 0.16, 0.60, 0.014, 0.01), f'tip rib {side} x{x:.2f}', tw,
               shrink=lambda k, x=x: (lambda m: wrib(m, x, 0.18 + 0.02 * k, 0.58 - 0.02 * k, 0.012, 0.012 + 0.002 * k)))
    for c in (0.18, 0.58):
        def tsp(m, c=c, inset=0.012):
            e = Vector((0, 0.010, 0)); rings = []
            for x in (W_TIP + 0.04, W_TIP + 0.32):
                t, b = wbox(m, s, x, c, inset); rings.append([t + e, t - e, b - e, b + e])
            n0 = _fv(m); loft(m, rings, True, True, MECH, smooth=False); _closed(m, n0)
        splace(tsp, f'tip spar {side} c{c}', tw, shrink=lambda k, c=c: (lambda m: tsp(m, c, 0.014 + 0.003 * k)))

# ================================================================ fin: mid spar, intermediate ribs, spars carried down into the fillet, rudder
def fpt2(z, c, side_, inset=0.010):
    le, te = fin_le(z), fin_te(z); ch = te - le
    return Vector((side_ * max(naca_t(c, _fin_t(z)) * ch - inset, 0.004), Y(le + ch * c), z))
def fspar(m, c, zs, w=0.012, inset=0.010):
    e = Vector((0, 0, w)); rings = []
    for z in zs:
        a, b = fpt2(z, c, 1, inset), fpt2(z, c, -1, inset); rings.append([a + e, a - e, b - e, b + e])
    n0 = _fv(m); loft(m, rings, True, True, MECH, smooth=False); _closed(m, n0)
def frib(m, z, c0, c1, th=0.012, inset=0.010):
    cs = [c0 + (c1 - c0) * j / 8 for j in range(9)]
    out = [fpt2(z, c, 1, inset) for c in cs] + [fpt2(z, c, -1, inset) for c in reversed(cs)]
    n0 = _fv(m); plate(m, out, th, (0, 0, 1), MECH); _closed(m, n0)
splace(lambda m: fspar(m, 0.38, (FIN_ROOT_Z + 0.05, 5.6, 6.6, RUDDER_TOP - 0.04)), 'fin mid spar', 'rudder_L',
       shrink=lambda k: (lambda m: fspar(m, 0.38, (FIN_ROOT_Z + 0.05 + 0.05 * k, 5.6, 6.6, RUDDER_TOP - 0.04 - 0.03 * k), 0.010, 0.012)))
for z in [5.025 + 0.45 * k for k in range(6)]:
    if z > FIN_TOP - 0.3: break
    splace(lambda m, z=z: frib(m, z, 0.10, 0.65), f'fin rib z{z:.2f}', 'rudder_L',
           shrink=lambda k, z=z: (lambda m: frib(m, z, 0.12 + 0.02 * k, 0.63 - 0.02 * k, 0.010, 0.012)))
def spt(z, c, side_, inset=0.010):
    le, te = spine_le(z), _fin_te(z); d = le + (te - le) * c
    return Vector((side_ * max(fin_half(d, z) - inset, 0.004), Y(d), z))
def spost(m, c, zs, w=0.012, inset=0.010):
    e = Vector((0, 0, w)); rings = []
    for z in zs:
        a, b = spt(z, c, 1, inset), spt(z, c, -1, inset); rings.append([a + e, a - e, b - e, b + e])
    n0 = _fv(m); loft(m, rings, True, True, MECH, smooth=False); _closed(m, n0)
def srib(m, z, c0, c1, th=0.012, inset=0.010):
    cs = [c0 + (c1 - c0) * j / 8 for j in range(9)]
    out = [spt(z, c, 1, inset) for c in cs] + [spt(z, c, -1, inset) for c in reversed(cs)]
    n0 = _fv(m); plate(m, out, th, (0, 0, 1), MECH); _closed(m, n0)
# the fin's three spars carry on down through the dorsal spine along the same swept lines and land on the fuselage, where
# a heavy frame takes each spar foot and a keel beam along the top of the fuselage ties the feet together
def fin_d(z, c): return fin_le(z) + (fin_te(z) - fin_le(z)) * c
# the dorsal spine is hollow between the fuselage top skin (about z 3.6) and the fin root (z 4.6); spars stand on that skin
def spine_floor(d, w=0.06):
    zs = []
    for x in (-w, 0.0, w):
        h = SKIN_BVH2.ray_cast(Vector((x, Y(d), 3.95)), Vector((0, 0, -1)))[0]
        if h is None: return None
        zs.append(h.z)
    return max(zs)
def skin_hw(d, z):
    o = Vector((0, Y(d), z)); hs = [SKIN_BVH2.ray_cast(o, Vector((sx, 0, 0)))[0] for sx in (1, -1)]
    return min(abs(h.x) for h in hs) if all(h is not None for h in hs) else None
def z_at(c, d):                                     # fin_d is linear in z
    a, b = fin_d(0.0, c), fin_d(1.0, c); return (d - a) / (b - a)
def spar_zs(c, lift=0.0, n=6):
    z0 = 3.6
    for _ in range(4): z0 = spine_floor(fin_d(z0, c)) + 0.035 + lift
    return [z0 + (FIN_ROOT_Z - 0.03 - z0) * j / (n - 1) for j in range(n)]
def fspar_low(m, c, zs, t=0.03, inset=0.012, dlo=-1e9, dhi=1e9):
    zl = [z for z in zs if dlo <= fin_d(z, c) <= dhi]
    for dd in (dlo, dhi):
        zc = z_at(c, dd)
        if zs[0] < zc < zs[-1]: zl.append(zc)
    zl = sorted(set(round(z, 5) for z in zl)); e = Vector((0, t / 2, 0)); rings = []
    for z in zl:
        d = fin_d(z, c); hw = skin_hw(d, z)
        if hw is None: continue
        hw = max(hw - inset, 0.006)
        a, b = Vector((hw, Y(d), z)), Vector((-hw, Y(d), z)); rings.append([a + e, a - e, b - e, b + e])
    if len(rings) < 2: return
    n0 = _fv(m); loft(m, rings, True, True, MECH, smooth=False); _closed(m, n0)
SPLIT_RANGES = (('fuselage', -1e9, REAR_SPLIT - 0.015), ('fuselage_R', REAR_SPLIT + 0.015, 1e9))
for c in (0.10, 0.38, 0.65):
    zs = spar_zs(c)
    for where, dlo, dhi in SPLIT_RANGES:
        if fin_d(zs[-1], c) < dlo or fin_d(zs[0], c) > dhi: continue
        splace(lambda m, c=c, dlo=dlo, dhi=dhi: fspar_low(m, c, spar_zs(c), dlo=dlo, dhi=dhi), f'fin spar root c{c} {where}', where,
               shrink=lambda k, c=c, dlo=dlo, dhi=dhi: (lambda m: fspar_low(m, c, spar_zs(c, 0.02 * k), 0.026 - 0.002 * k, 0.014 + 0.004 * k, dlo, dhi)))
    foot = fin_d(zs[0], c)
    frame('fuselage' if foot < REAR_SPLIT else 'fuselage_R', foot, depth=0.12, width=0.07, mask=FR_MASK)   # fin attachment frame under the spar foot
# keel beam: a shallow box beam on the spine floor tying the three spar feet together, front to back
def keel(m, d0, d1, h=0.05, w=0.10, lift=0.004):
    n = max(3, int((d1 - d0) / 0.25) + 1); rings = []
    for j in range(n):
        d = d0 + (d1 - d0) * j / (n - 1); f = spine_floor(d, w / 2)
        if f is None: continue
        zb = f + lift; y = Y(d)
        rings.append([Vector((w / 2, y, zb + h)), Vector((-w / 2, y, zb + h)), Vector((-w / 2, y, zb)), Vector((w / 2, y, zb))])
    if len(rings) < 2: return
    n0 = _fv(m); loft(m, rings, True, True, MECH, smooth=False); _closed(m, n0)
F0, F1 = fin_d(spar_zs(0.10)[0], 0.10), fin_d(spar_zs(0.65)[0], 0.65)
KD = [(F0 - 0.3, REAR_SPLIT - 0.015, 'fuselage'), (REAR_SPLIT + 0.015, 27.97, 'fuselage_R'), (28.03, F1 + 0.3, 'fuselage_R')]   # the tail cone starts at d 28
for d0, d1, where in KD:
    if d1 - d0 < 0.2: continue
    splace(lambda m, d0=d0, d1=d1: keel(m, d0, d1), f'fin keel beam d{d0:.1f}', where,
           shrink=lambda k, d0=d0, d1=d1: (lambda m: keel(m, d0, d1, 0.05 - 0.008 * k, 0.10 - 0.01 * k, 0.004 + 0.006 * k)))
for z in (4.10, 4.40):
    splace(lambda m, z=z: srib(m, z, 0.25, 0.92), f'fillet rib z{z}', 'tail',
           shrink=lambda k, z=z: (lambda m: srib(m, z, 0.25 + 0.05 * k, 0.92 - 0.03 * k, 0.010, 0.012 + 0.003 * k)))
# rudder: a deep front spar along the hinge, a trailing-edge member, and ribs lined up with the fin ribs so the two read
# as one structure following the fin's sweep
def fweb(m, c, zs, t=0.03, inset=0.008):
    e = Vector((0, t / 2, 0)); rings = []
    for z in zs:
        a, b = fpt2(z, c, 1, inset), fpt2(z, c, -1, inset); rings.append([a + e, a - e, b - e, b + e])
    n0 = _fv(m); loft(m, rings, True, True, MECH, smooth=False); _closed(m, n0)
RC0 = 1 - RUDDER_FRAC + 0.02
RZ = (RUDDER_BOT + 0.05, (RUDDER_BOT + RUDDER_TOP) / 2, RUDDER_TOP - 0.06)
splace(lambda m: fweb(m, RC0, RZ, 0.035), 'rudder spar', 'rudder_L_visible',
       shrink=lambda k: (lambda m: fweb(m, RC0 + 0.01 * k, (RZ[0] + 0.03 * k, RZ[1], RZ[2] - 0.03 * k), 0.03, 0.010 + 0.002 * k)))
splace(lambda m: fweb(m, 0.93, RZ, 0.02, 0.004), 'rudder trailing edge', 'rudder_L_visible',
       shrink=lambda k: (lambda m: fweb(m, 0.93 - 0.02 * k, (RZ[0] + 0.03 * k, RZ[1], RZ[2] - 0.03 * k), 0.016, 0.005 + 0.001 * k)))
for z in [4.80 + 0.225 * k for k in range(20)]:
    if z < RUDDER_BOT + 0.10: continue
    if z > RUDDER_TOP - 0.12: break
    splace(lambda m, z=z: frib(m, z, RC0, 0.94, 0.018, 0.008), f'rudder rib z{z:.2f}', 'rudder_L_visible',
           shrink=lambda k, z=z: (lambda m: frib(m, z, RC0 + 0.01 * k, 0.92 - 0.02 * k, 0.014, 0.010)))

# ================================================================ tailplanes: spindle, spars and ribs (all-moving, so they go with the visible part)
EST = [(1.1, 27.0, 5.5, 0.045), (1.6, 27.4, 5.1, 0.045), (3.3, 29.45, 3.75, 0.042), (4.9, 31.5, 2.4, 0.04), (5.15, 32.1, 1.75, 0.035), (5.2, 32.35, 1.35, 0.02)]
def est(x):
    for a, b in zip(EST, EST[1:]):
        if x <= b[0]:
            f = (x - a[0]) / (b[0] - a[0]); return [a[j] + (b[j] - a[j]) * f for j in (1, 2, 3)]
    return list(EST[-1][1:])
def ept(s, x, c, side_, inset=0.008):
    le, ch, t = est(x)
    return Vector((s * x, Y(le + ch * c), 2.12 + side_ * max(naca_t(c, t) * ch - inset, 0.003)))
for side, s in (('R', 1), ('L', -1)):
    ev = f'elevator_{side}_visible'
    splace(lambda m: cyl(m, (s * 1.75, Y(29.9), 2.12), (s * 2.6, Y(29.9), 2.12), 0.04, N=12, mat=MECH), f'tailplane spindle {side}', ev,
           shrink=lambda k: (lambda m: cyl(m, (s * (1.75 + 0.1 * k), Y(29.9), 2.12), (s * 2.6, Y(29.9), 2.12), 0.035 - 0.005 * k, N=12, mat=MECH)))
    for c in (0.12, 0.45, 0.75):
        def esp(m, c=c, inset=0.008, w=0.010):
            e = Vector((0, w, 0)); rings = []
            for x in (2.05, 2.5, 3.3, 4.1, 4.85):      # 0.9.5: from the fixed root stub's joint (x 2.0) outward
                a, b = ept(s, x, c, 1, inset), ept(s, x, c, -1, inset); rings.append([a + e, a - e, b - e, b + e])
            n0 = _fv(m); loft(m, rings, True, True, MECH, smooth=False); _closed(m, n0)
        splace(esp, f'tailplane spar {side} c{c}', ev, shrink=lambda k, c=c: (lambda m: esp(m, c, 0.010 + 0.002 * k, 0.008)))
    for x in (2.05, 2.4, 3.0, 3.6, 4.2, 4.8):
        def erib(m, x=x, c0=0.06, c1=0.92, inset=0.008, th=0.010):
            cs = [c0 + (c1 - c0) * j / 10 for j in range(11)]
            out = [ept(s, x, c, 1, inset) for c in cs] + [ept(s, x, c, -1, inset) for c in reversed(cs)]
            n0 = _fv(m); plate(m, out, th, (1, 0, 0), MECH); _closed(m, n0)
        splace(erib, f'tailplane rib {side} x{x}', ev,
               shrink=lambda k, x=x: (lambda m: erib(m, x, 0.08 + 0.02 * k, 0.90 - 0.02 * k, 0.010, 0.008)))

print('structure2 kept', STR2_LOG['kept'], 'rejected', len(STR2_LOG['rejected']))
for r in STR2_LOG['rejected']: print('  s2 reject', r)
