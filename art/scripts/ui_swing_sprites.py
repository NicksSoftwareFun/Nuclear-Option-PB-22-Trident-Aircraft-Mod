# Sweep gauge sprites in the stock layout: the left half of the airframe without the outer wing (128x512, centreline on
# the right edge, nose up) and the left outer wing drawn unswept (512x256, root on the right). Outlines come from a
# top-down raster of every part, so part edges read as panel lines like the stock diagrams.
# usage: python3 ui_swing_sprites.py <blend> <outdir> [min_sweep_deg]
import bpy, sys, math, json, os
import numpy as np
from mathutils import Vector, Matrix
from PIL import Image, ImageDraw, ImageFilter

a = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
BLEND, OUT = a[0], a[1]
MIN_SWEEP = float(a[2]) if len(a) > 2 else 20.0
bpy.ops.wm.open_mainfile(filepath=BLEND)
os.makedirs(OUT, exist_ok=True)

SKIP = ('gear_', 'wheel_', 'bogey_', 'brace', 'act', 'legDoor', 'crew_', 'seat', 'pilot', 'decal_')
HINGE = bpy.data.objects['wingHinge_Lb'].matrix_world.translation.copy()

def anc(o):
    r = []
    while o.parent: o = o.parent; r.append(o.name)
    return r

def tris(objs, rot=None):
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for pid, o in enumerate(objs):
        ev = o.evaluated_get(dg); me = ev.to_mesh(); M = o.matrix_world
        if rot is not None: M = rot @ M
        V = [M @ v.co for v in me.vertices]
        me.calc_loop_triangles()
        for t in me.loop_triangles:
            p = [V[i] for i in t.vertices]
            out.append((sum(q.z for q in p) / 3, pid, [(q.x, q.y) for q in p]))
        ev.to_mesh_clear()
    out.sort(key=lambda t: t[0])
    return out

def raster(T, x0, y1, ppm, W, H, ss=4):
    # painter's order (low to high), ids start at 1, 0 = background
    im = Image.new('I', (W * ss, H * ss), 0); d = ImageDraw.Draw(im)
    for z, pid, p in T:
        d.polygon([((x - x0) * ppm * ss, (y1 - y) * ppm * ss) for x, y in p], fill=pid + 1)
    return np.array(im)

def outline(ids, ss=4, outer=4.0, inner=2.0):
    # edge pixels where the id changes; the silhouette edge is drawn thicker than the part seams
    e_in = np.zeros(ids.shape, bool); e_out = np.zeros(ids.shape, bool)
    for dy, dx in ((0, 1), (1, 0)):
        A = ids[:ids.shape[0] - dy, :ids.shape[1] - dx]; B = ids[dy:, dx:]
        diff = A != B; sil = diff & ((A == 0) | (B == 0))
        e_out[:A.shape[0], :A.shape[1]] |= sil; e_in[:A.shape[0], :A.shape[1]] |= diff & ~sil
    def grow(m, w):
        im = Image.fromarray((m * 255).astype(np.uint8)); k = int(round(w * ss)) | 1
        return np.array(im.filter(ImageFilter.MaxFilter(k))) > 127
    m = grow(e_out, outer) | grow(e_in, inner)
    h, w = m.shape
    a = Image.fromarray((m * 255).astype(np.uint8)).resize((w // ss, h // ss), Image.LANCZOS)
    rgba = Image.new('RGBA', a.size, (214, 214, 214, 0)); rgba.putalpha(a)
    return rgba

model = [o for o in bpy.data.collections['MODEL'].all_objects if o.type == 'MESH' and not o.name.startswith(SKIP)]
wing = [o for o in model if 'wingHinge_Lb' in anc(o)]
body = [o for o in model if o not in wing]

# ---- body: left half, x in [-W/ppm, 0], full length
y_top, y_bot = 17.0, -17.0
FH = 512; ppm_f = FH / (y_top - y_bot); FW = 128
x0 = -FW / ppm_f
T = [t for t in tris(body)]
ids = raster(T, x0, y_top, ppm_f, FW, FH)
ids[:, ids.shape[1] - 1] = ids[:, ids.shape[1] - 2]   # no seam on the centreline cut
outline(ids).save(os.path.join(OUT, 'PB22_swing_fuselage.png'))

# ---- wing: rotated forward by the minimum sweep about the pivot, so the gauge's own rotation shows the true sweep
R = Matrix.Translation(HINGE) @ Matrix.Rotation(math.radians(-MIN_SWEEP), 4, 'Z') @ Matrix.Translation(-HINGE)
TW = tris(wing, R)
xs = [x for _, _, p in TW for x, y in p]; ys = [y for _, _, p in TW for x, y in p]
pad = 0.25
wx0, wx1, wy0, wy1 = min(xs) - pad, max(max(xs), HINGE.x) + pad, min(ys) - pad, max(max(ys), HINGE.y) + pad
WW, WH = 512, 256
ppm_w = min(WW / (wx1 - wx0), WH / (wy1 - wy0))
# right-align the root and top-align the leading edge like the stock sprite
wx0 = wx1 - WW / ppm_w; wy0 = wy1 - WH / ppm_w
ids = raster(TW, wx0, wy1, ppm_w, WW, WH)
# the wing sprite is shown at about a third of the fuselage sprite's pixels per HUD unit, so its lines are 3x as wide
outline(ids, outer=12.0, inner=6.0).save(os.path.join(OUT, 'PB22_swing_wing.png'))

hp = ((HINGE.x - wx0) * ppm_w, (wy1 - HINGE.y) * ppm_w)          # hinge in wing sprite px (y down)
hf = ((HINGE.x - x0) * ppm_f, (y_top - HINGE.y) * ppm_f)          # hinge in fuselage sprite px (y down)
info = dict(min_sweep=MIN_SWEEP, fus_px=[FW, FH], fus_m=[FW / ppm_f, FH / ppm_f], wing_px=[WW, WH], wing_m=[WW / ppm_w, WH / ppm_w],
            wing_pivot=[hp[0] / WW, 1 - hp[1] / WH], hinge_fus_px=list(hf), hinge_fus_norm=[hf[0] / FW, 1 - hf[1] / FH])
json.dump(info, open(os.path.join(OUT, 'swing.json'), 'w'), indent=1)
print(json.dumps(info))
