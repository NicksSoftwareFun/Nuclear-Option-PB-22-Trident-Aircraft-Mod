# Visible-surface materials (exec'd from build_pb22_detail.py once every part is an object, before the dissolve).
# The game's shared structure materials (jet_mechanical / aircraft_structure) are for the internals, which only show
# when a part is shot open. Every PB22_mech / PB22_int face that can be seen on an intact aircraft (gear down, bays and
# hatches open, looking into the intakes or through the canopy) is moved to a solid material instead:
#   intake duct lining -> PB22_skin, cabin lining -> PB22_cabin (cockpit texture), engine fan -> PB22_noz (nozzle metal),
#   everything else (gear, bay walls, doors, pylons, sensors) -> PB22_metal.
from mathutils.bvhtree import BVHTree

VIS_MATS = {n: bpy.data.materials.get(n) or mat(n, c, r, m) for n, c, r, m in (
    ('PB22_metal', (0.34, 0.37, 0.38), 0.5, 0.2), ('PB22_noz', (0.39, 0.38, 0.36), 0.35, 0.45), ('PB22_cabin', (0.55, 0.56, 0.56), 0.7, 0.0))}
SOLID_OBJ = ('gear_', 'bogey', 'brace', 'act', 'wheel_', 'gearDoor', 'legDoor', 'bayDoor', 'midPylon', 'glovePylon', 'intake_')   # intakes: side louvres and lip details are all on show
OPEN_OBJ = ('gear_', 'bogey', 'brace', 'act', 'wheel_', 'gearDoor', 'legDoor', 'bayDoor', 'hatch_', 'afterburner')   # left out of the occluders: open or moving
CAB_BOX = (3.35, 9.70, 1.80)        # d0, d1, z floor: the crew compartment
BAY_BOX = (12.9, 24.4, 1.02, 2.80)  # d0, d1, |x|, z top: the weapon bays

def _mname(o, f):
    return o.data.materials[f.material_index].name if f.material_index < len(o.data.materials) else ''

def _visskin(o, f):
    # 1.0.2: lining faces moved onto the skin here are marked, so the rip (which now runs later) and the honeycomb
    # liners still treat them as lining, not outer skin
    o.data.attributes['visskin'].data[f.index].value = 1

def _slot(o, name):
    for i, m in enumerate(o.data.materials):
        if m and m.name == name: return i
    o.data.materials.append(VIS_MATS.get(name) or bpy.data.materials[name]); return len(o.data.materials) - 1

_objs = [o for o in C_MODEL.objects if o.type == 'MESH']
for o in _objs:
    if o.data.attributes.get('visskin') is None: o.data.attributes.new('visskin', 'INT', 'FACE')
_vs, _fs = [], []
for o in _objs:
    if o.name.startswith(OPEN_OBJ): continue
    mw = o.matrix_world; b = len(_vs)
    _vs += [mw @ v.co for v in o.data.vertices]
    for p in o.data.polygons:
        if _mname(o, p) != 'PB22_glass': _fs.append([b + i for i in p.vertices])
_bvh = BVHTree.FromPolygons(_vs, _fs)

_DIRS = [(0.0, 0.0)] + [(r * math.cos(2 * math.pi * k / 8 + r), r * math.sin(2 * math.pi * k / 8 + r)) for r in (0.5, 1.2, 3.0) for k in range(8)]
def _exposed(c, n):
    t1 = n.orthogonal().normalized(); t2 = n.cross(t1)
    o = c + n * 0.03     # clear coincident flanges and double-sided copies
    for a, b in _DIRS:
        v = (n + t1 * a + t2 * b).normalized()
        if _bvh.ray_cast(o, v, 60.0)[0] is None: return True
    return False

_count = {}
for o in _objs:
    if o.name.startswith(('nozzle', 'slimelight', 'navlight')): continue      # nozzles: Unity sets their metal itself
    mw = o.matrix_world; nmw = mw.to_3x3().inverted().transposed()
    whole = o.name.startswith(SOLID_OBJ) or o.name.endswith('_visible')
    for f in o.data.polygons:
        mn = _mname(o, f)
        if mn not in ('PB22_mech', 'PB22_int'): continue
        if o.name.startswith('fan_'): to = 'PB22_noz'
        elif whole and not (mn == 'PB22_int' and o.name.startswith('intake_')): to = 'PB22_metal'     # intake lining stays skin (below)
        else:
            c = mw @ f.center; n = (nmw @ f.normal).normalized()
            d = 17.0 - c.y
            if o.name.startswith(('cockpit', 'fuselage_FF', 'hatch_')) and CAB_BOX[0] <= d <= CAB_BOX[1] and c.z > CAB_BOX[2] \
                    and (d >= CAB_D[0] - 0.05 or c.z >= DECK_Z - 0.05):
                # the whole crew compartment (lining, floor, bulkheads, windscreen deck) takes the cabin texture
                f.material_index = _slot(o, 'PB22_cabin'); _count[(o.name, 'PB22_cabin')] = _count.get((o.name, 'PB22_cabin'), 0) + 1
                continue
            if mn == 'PB22_int' and o.name.startswith('intake_'):
                f.material_index = _slot(o, 'PB22_skin'); _visskin(o, f); _count[(o.name, 'PB22_skin')] = _count.get((o.name, 'PB22_skin'), 0) + 1
                continue
            if mn == 'PB22_int' and in_duct(c) and not o.name.startswith(('cockpit', 'fuselage_FF', 'hatch_')):
                # duct lining: the copy facing the duct axis is what you see looking in from the intake lip
                ax = duct_axis(1 if c.x > 0 else -1)(c)
                if (ax - c).dot(n) > 0: f.material_index = _slot(o, 'PB22_skin'); _visskin(o, f); _count[(o.name, 'PB22_skin')] = _count.get((o.name, 'PB22_skin'), 0) + 1
                continue
            if (o.name.startswith('gearbay') or (o.name == 'fuselage' and BAY_BOX[0] <= d <= BAY_BOX[1] and abs(c.x) <= BAY_BOX[2] and c.z <= BAY_BOX[3]) \
                    or (o.name == 'fuselage' and 14.0 <= d <= 25.0 and abs(c.x) > 1.05 and c.z < 2.05 and c.x * n.x > 0)):
                f.material_index = _slot(o, 'PB22_metal'); _count[(o.name, 'PB22_metal')] = _count.get((o.name, 'PB22_metal'), 0) + 1
                continue       # weapon bays and gear wells: everything inside is on show with the doors open
            if not _exposed(c, n): continue
            to = 'PB22_metal'
        f.material_index = _slot(o, to); _count[(o.name, to)] = _count.get((o.name, to), 0) + 1
_tot = {}
for (on, to), k in _count.items(): _tot[to] = _tot.get(to, 0) + k
print('vismat', _tot)
for (on, to), k in sorted(_count.items()):
    if not on.startswith(SOLID_OBJ): print('  vismat', on, to, k)

# second pass: anything still on a structure material that a camera orbiting the aircraft can see (small brackets, rib
# edges at part seams) goes to PB22_metal too. Rays from 40 positions around and under the aircraft, glass ignored.
_vs, _fs, _own = [], [], []
for o in _objs:
    mw = o.matrix_world; b = len(_vs)
    _vs += [mw @ v.co for v in o.data.vertices]
    for p in o.data.polygons:
        if _mname(o, p) != 'PB22_glass': _fs.append([b + i for i in p.vertices]); _own.append((o, p.index))
_bvh2 = BVHTree.FromPolygons(_vs, _fs)
_cams = [Vector((r * math.sin(k * math.pi / 8), Y(17.0) + r * math.cos(k * math.pi / 8), zz)) for r, zz in ((15.0, 6.5), (15.0, -1.0), (9.0, 2.6)) for k in range(16)] \
        + [Vector((x, Y(dd), zz)) for x in (-3.0, 3.0) for dd in (10.0, 17.0, 24.0) for zz in (-2.5, 7.0)]
_hit = set()
for cp in _cams:
    fw = (Vector((0.0, Y(17.0), 2.5)) - cp).normalized(); rt = fw.cross(Vector((0, 0, 1))).normalized(); up = rt.cross(fw)
    for j in range(90):
        for i in range(160):
            v = (fw + rt * 0.85 * (2 * (i + .5) / 160 - 1) + up * 0.5 * (1 - 2 * (j + .5) / 90)).normalized()
            idx = _bvh2.ray_cast(cp, v, 120.0)[2]
            if idx is not None: _hit.add(idx)
_n2 = 0
for idx in _hit:
    o, pi = _own[idx]
    if o.name.startswith(('nozzle', 'slimelight', 'navlight')): continue
    f = o.data.polygons[pi]
    if _mname(o, f) in ('PB22_mech', 'PB22_int'):
        f.material_index = _slot(o, 'PB22_metal'); _n2 += 1
print('vismat orbit pass', _n2)

# 0.4.7: the engine body takes the stock engine casing look of the Medusa (EW-1) engine: solid casing, no cut-outs. The
# jet_mechanical atlas (PB22_mech) carries alpha cut-outs (lattice, hex holes, pipe sheets) that showed straight through the
# engine; the Medusa engine core is the solid aircraft_structure casing (PB22_int), so the engine body uses that throughout.
_ne = 0
for o in _objs:
    if not o.name.startswith('engine_body'): continue
    for f in o.data.polygons:
        if _mname(o, f) == 'PB22_mech': f.material_index = _slot(o, 'PB22_int'); _ne += 1
print('vismat engine casing', _ne)
