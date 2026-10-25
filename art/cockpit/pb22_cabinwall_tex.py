"""PB-22 cockpit wall liner: a 1024 px tiling set (b/n/m/ao) for the hull interior around the crew stations.
One tile = 0.60 m. Frame cap runs vertically at U 0.5, a stringer cap horizontally at V 0.5, liner panel seams on the tile edges.
Same palette as the cockpit panels: light structure grey, dark trim."""
import os
CK = os.path.dirname(os.path.abspath(__file__))  # scripts, ctx.obj and tex/ output live next to this file
import numpy as np, random, math
from PIL import Image, ImageDraw, ImageFilter
S = 1024; OUT = os.path.join(CK, 'tex')
rng = np.random.default_rng(22); random.seed(22)
LINER = np.array([124, 125, 123], np.float32); CAP = np.array([142, 143, 140], np.float32); SEAM = (86, 87, 86)

def tile_noise(cells, amp):      # wrap-around value noise so the tile repeats without seams
    g = rng.normal(0, 1, (cells, cells))
    g = np.concatenate([g, g[:1]], 0); g = np.concatenate([g, g[:, :1]], 1)
    im = Image.fromarray(np.uint8(np.clip(128 + g*40, 0, 255))).resize((S + S//cells, S + S//cells), Image.BICUBIC)
    a = (np.asarray(im, np.float32)[:S, :S] - 128)/40*amp
    return a
base = np.array([118, 121, 118], np.float32)[None, None, :] + tile_noise(8, 3.0)[:, :, None] + rng.normal(0, 3.0, (S, S, 1))
B = Image.fromarray(np.uint8(np.clip(base, 0, 255))); H = Image.new('L', (S, S), 128); G = Image.new('L', (S, S), 92)
db, dh, dg = ImageDraw.Draw(B), ImageDraw.Draw(H), ImageDraw.Draw(G)

def wrap_ellipse(cx, cy, r, **kw):   # draw on the tile and its wrapped copies
    for ox in (-S, 0, S):
        for oy in (-S, 0, S):
            yield (cx - r + ox, cy - r + oy, cx + r + ox, cy + r + oy)

# insulation blankets between frame and stringer: pillowed pads with diamond quilt stitching
LINER_T = np.array([118, 121, 118], np.float32)   # slightly warmer textile grey
for (x0, x1) in ((0, S//2 - 43), (S//2 + 43, S)):
    for (y0, y1) in ((0, S//2 - 14), (S//2 + 14, S)):
        for k in range(10):
            dh.rectangle((x0 + 4 + k*4, y0 + 4 + k*4, x1 - 4 - k*4, y1 - 4 - k*4), fill=124 + k*3)
QU = 64   # quilt pitch in px (37 mm)
for d in range(-S, 2*S, QU):
    for (a, b) in (((d, 0), (d + S, S)), ((d, S), (d + S, 0))):
        dh.line((a, b), fill=112, width=3); db.line((a, b), fill=(104, 106, 104), width=1)
# liner seams on the tile edges (show as a dark line once tiled)
for x in (0, S - 2):
    db.rectangle((x, 0, x + 1, S), fill=SEAM); dh.rectangle((x, 0, x + 1, S), fill=100)
for y in (0, S - 2):
    db.rectangle((0, y, S, y + 1), fill=SEAM); dh.rectangle((0, y, S, y + 1), fill=100)
# horizontal stringer cap at V 0.5
cy = S//2
db.rectangle((0, cy - 14, S, cy + 14), fill=tuple(int(v) for v in CAP - 6)); dh.rectangle((0, cy - 14, S, cy + 14), fill=170)
db.line((0, cy - 14, S, cy - 14), fill=(168, 169, 166)); db.line((0, cy + 14, S, cy + 14), fill=(84, 85, 84), width=2)
# vertical frame cap at U 0.5 with lightening holes and rivet rows
cx = S//2
db.rectangle((cx - 43, 0, cx + 43, S), fill=tuple(int(v) for v in CAP)); dh.rectangle((cx - 43, 0, cx + 43, S), fill=190)
db.line((cx - 43, 0, cx - 43, S), fill=(176, 177, 174), width=2); db.line((cx + 43, 0, cx + 43, S), fill=(80, 81, 80), width=3)
for k in range(4):
    y = 128 + k*256
    db.ellipse((cx - 24, y - 24, cx + 24, y + 24), fill=(40, 41, 43)); dh.ellipse((cx - 24, y - 24, cx + 24, y + 24), fill=70)
    db.ellipse((cx - 27, y - 27, cx + 27, y + 27), outline=(170, 171, 168), width=3)
    dg.ellipse((cx - 24, y - 24, cx + 24, y + 24), fill=40)
for y in range(16, S, 32):
    for x in (cx - 34, cx + 34):
        db.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(112, 113, 111)); dh.ellipse((x - 3, y - 3, x + 3, y + 3), fill=210)
# liner fasteners along the seams and the stringer
for t in range(24, S, 64):
    for (x, y) in ((12, t), (t, 12), (t, cy - 22), (t, cy + 22)):
        if abs(x - cx) < 50: continue
        for bb in wrap_ellipse(x, y, 4):
            db.ellipse(bb, fill=(104, 105, 103)); dh.ellipse(bb, fill=150)
        db.line((x - 3, y, x + 3, y), fill=(66, 66, 66))
# wiring loom: three cables along V 0.375, threaded through the frame's lightening hole, P-clamps on the blanket
wy = 384
for k, (dy, col) in enumerate(((-9, (34, 35, 37)), (0, (46, 47, 50)), (9, (30, 31, 33)))):
    db.rectangle((0, wy + dy - 4, S, wy + dy + 4), fill=col); dh.rectangle((0, wy + dy - 4, S, wy + dy + 4), fill=200)
    db.line((0, wy + dy - 3, S, wy + dy - 3), fill=tuple(c + 26 for c in col))
for t in range(64, S, 128):     # lacing ties
    if abs(t - cx) < 48: continue
    db.rectangle((t, wy - 15, t + 3, wy + 15), fill=(132, 128, 108))
for x in (cx - 150, cx + 150, 40, S - 40):
    db.rectangle((x - 10, wy - 18, x + 10, wy + 18), fill=(150, 151, 148)); dh.rectangle((x - 10, wy - 18, x + 10, wy + 18), fill=225)
    db.rectangle((x - 10, wy - 18, x + 10, wy + 18), outline=(92, 93, 92))
    db.ellipse((x - 3, wy + 22, x + 3, wy + 28), fill=(104, 105, 103))
db.rectangle((cx + 210, wy - 16, cx + 236, wy + 16), fill=(196, 160, 40))    # yellow ident sleeve
db.text((cx + 214, wy - 5), 'W22', fill=(30, 30, 30))
# sparse light scuffs (stock: light and sparse)
for _ in range(40):
    sx, sy = random.randint(0, S - 1), random.randint(0, S - 1); L = random.randint(5, 16); a = random.uniform(0, math.pi)
    db.line((sx, sy, sx + L*math.cos(a), sy + L*math.sin(a)), fill=(138, 139, 137))
# grime collecting under the stringer and beside the frame
grime = np.zeros((S, S), np.float32)
grime[cy + 15:cy + 60, :] += np.linspace(14, 0, 45)[:, None]
grime[:, cx + 44:cx + 80] += np.linspace(10, 0, 36)[None, :]
b = np.asarray(B, np.float32) - grime[:, :, None]
B = Image.fromarray(np.uint8(np.clip(b, 0, 255)))

B.save(OUT + '/PB22_cabinwall_b.png')
h = np.asarray(H.filter(ImageFilter.GaussianBlur(1.0)), np.float32)/255.0
dx = np.roll(h, -1, 1) - np.roll(h, 1, 1); dy = np.roll(h, -1, 0) - np.roll(h, 1, 0); k = 4.0
nx, ny, nz = -dx*k, dy*k, np.ones_like(h); l = np.sqrt(nx*nx + ny*ny + nz*nz)
Image.fromarray(np.uint8(np.stack([(nx/l + 1)*127.5, (ny/l + 1)*127.5, (nz/l + 1)*127.5], -1))).save(OUT + '/PB22_cabinwall_n.png')
M = np.zeros((S, S, 4), np.uint8); M[..., :3] = 10; M[..., 3] = np.asarray(G, np.uint8)
Image.fromarray(M, 'RGBA').save(OUT + '/PB22_cabinwall_m.png')
hb = np.asarray(H.filter(ImageFilter.GaussianBlur(6)), np.float32)
ao = np.clip(255 - np.clip(128 - hb, 0, 90)*1.4 - grime*1.5, 120, 255)
Image.fromarray(np.uint8(ao)).save(OUT + '/PB22_cabinwall_ao.png')
# 2x2 preview to check the tiling
pv = Image.new('RGB', (2*S, 2*S))
for ox in (0, S):
    for oy in (0, S): pv.paste(Image.open(OUT + '/PB22_cabinwall_b.png'), (ox, oy))
pv.resize((1024, 1024)).save(os.path.join(CK, 'cabinwall_tiled.jpg'), quality=88)
print('cabin wall written')
