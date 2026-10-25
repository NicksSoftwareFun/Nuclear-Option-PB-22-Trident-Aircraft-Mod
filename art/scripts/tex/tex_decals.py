"""Decal layer of the PB-22 skin: collects every Decal feature of the painter spec, per livery, and packs their images
into one RGBA atlas sheet per livery (identical layout on every sheet) plus a JSON list of the decal geometry for
build_decals.py (Blender), which turns them into thin meshes just above the skin.
Usage: python3 tex_decals.py <maps.npz> <outdir> [spec_module] [liveries=grey,maritime,lowlevel] [pad=6]
Writes  <outdir>/PB22_decals_<livery>.png   straight alpha, opacity baked into alpha, colours as drawn
        <outdir>/PB22_decals.json            union of the decals of all liveries (one entry per unique geometry)
Decals that paint no texel in the painter are dropped; decals whose images are equal on every livery share a rect.
Paint the skin with PB22_DECALS=1 so tex_paint.py leaves these stencils out of the skin texture."""
import sys, os, json, hashlib, importlib
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tex_feat as TF
from tex_paint import Model

SHEETS = [(2048, 2048), (4096, 1024), (4096, 2048), (4096, 4096)]


def r5(v): return [round(float(x), 5) for x in np.ravel(v)]


def collect(M, specname, livery):
    """Decal features of one livery, exactly as tex_paint.run() builds them."""
    os.environ['PB22_LIVERY'] = livery
    import pb22_stencils, pb22_livery
    importlib.reload(pb22_stencils); importlib.reload(pb22_livery)
    spec = importlib.import_module(specname); spec = importlib.reload(spec)
    return [f for f in spec.features(M) if isinstance(f, TF.Decal)]


def accept(M, f):
    """Texels the painter would touch (same test as Decal.paint), as {part: count}."""
    I = M.select(f.parts, f.bbox, f.margin)
    if len(I) == 0: return {}
    P, N = M.P[I], M.N[I]
    q = P - f.C; w, h = f.size
    u = q @ f.R / w + 0.5; v = 0.5 - q @ f.U / h
    ok = (u >= 0) & (u <= 1) & (v >= 0) & (v <= 1) & (np.abs(q @ f.Fc) < f.tol) & (N @ f.Fc > 0.35)
    a = f.img[:, :, 3]
    H, W = a.shape
    x = np.clip((u * W).astype(int), 0, W - 1); y = np.clip((v * H).astype(int), 0, H - 1)
    ok &= a[y, x] > 0                                    # only count texels that get paint
    ok &= M.mat[I] == (M.mats.index('PB22_skin') if 'PB22_skin' in M.mats else 0)   # paint on glass etc. never shows
    out = {}
    for p in M.pid[I[ok]]:
        n = M.names[p]; out[n] = out.get(n, 0) + 1
    return out


def key(f):
    b = {k: r5(v) for k, v in sorted(f.bbox.items())}
    return json.dumps([r5(f.C), r5(f.R), r5(f.U), r5(f.Fc), r5(f.size), round(float(f.tol), 5), b,
                       round(float(f.margin), 5), sorted(f.parts)])


def rgba8(f):
    im = f.img.copy(); im[:, :, 3] *= f.op
    return np.clip(np.round(im * 255), 0, 255).astype(np.uint8)


def pack(sizes, pad):
    """Shelf packing, tallest first. sizes = [(w, h)]; returns (sheet, [(x, y)]) or None."""
    order = sorted(range(len(sizes)), key=lambda i: (-sizes[i][1], -sizes[i][0]))
    for SW, SH in SHEETS:
        pos = [None] * len(sizes); x = y = rowh = 0; ok = True
        for i in order:
            w, h = sizes[i][0] + 2 * pad, sizes[i][1] + 2 * pad
            if w > SW: ok = False; break
            if x + w > SW: x, y, rowh = 0, y + rowh, 0
            if y + h > SH: ok = False; break
            pos[i] = (x + pad, y + pad); x += w; rowh = max(rowh, h)
        if ok: return (SW, SH), pos
    return None


def bleed(cell):
    """Spread the colour of painted pixels into the transparent ones (alpha stays 0): no dark fringes when filtered."""
    from scipy import ndimage
    a = cell[:, :, 3]
    if not (a > 0).any(): return cell
    _, (iy, ix) = ndimage.distance_transform_edt(a == 0, return_indices=True)
    out = cell.copy(); out[:, :, :3] = cell[iy, ix, :3]; out[:, :, 3] = a
    return out


def run(maps, outdir, specname='pb22_panels', liveries=('grey', 'maritime', 'lowlevel'), pad=6):
    M = Model(maps)
    old = os.environ.get('PB22_LIVERY')
    dec = {}                                             # key -> dict(feat, imgs={livery: rgba}, parts={})
    for liv in liveries:
        n = 0
        for f in collect(M, specname, liv):
            hit = accept(M, f)
            if not hit: continue
            k = key(f)
            e = dec.setdefault(k, dict(f=f, imgs={}, parts={}))
            e['imgs'][liv] = rgba8(f); n += 1
            for p, c in hit.items(): e['parts'][p] = max(e['parts'].get(p, 0), c)
        print(liv, n, 'decals')
    if old is None: os.environ.pop('PB22_LIVERY', None)
    else: os.environ['PB22_LIVERY'] = old
    # rect groups: decals whose images agree on every livery share one rect
    groups = {}
    for k, e in dec.items():
        g = tuple(hashlib.md5(e['imgs'][l].tobytes() + str(e['imgs'][l].shape).encode()).hexdigest() if l in e['imgs'] else None
                  for l in liveries)
        groups.setdefault(g, []).append(k)
    gl = list(groups.items())
    sizes = []
    for g, ks in gl:
        ims = dec[ks[0]]['imgs'].values()
        sizes.append((max(i.shape[1] for i in ims), max(i.shape[0] for i in ims)))
    res = pack(sizes, pad)
    if res is None: raise SystemExit('decal atlas does not fit 4096x4096')
    (SW, SH), pos = res
    sheets = {l: np.zeros((SH, SW, 4), np.uint8) for l in liveries}
    rects = {}
    trims = {}
    for (g, ks), (w, h), (x, y) in zip(gl, sizes, pos):
        for l in liveries:
            src = next((dec[k]['imgs'][l] for k in ks if l in dec[k]['imgs']), None)
            if src is None: continue
            if src.shape[:2] != (h, w):                  # same geometry, other pixel size: fill the rect
                src = np.asarray(Image.fromarray(src, 'RGBA').resize((w, h), Image.BICUBIC))
            cell = np.zeros((h + 2 * pad, w + 2 * pad, 4), np.uint8); cell[pad:pad + h, pad:pad + w] = src
            sheets[l][y - pad:y + h + pad, x - pad:x + w + pad] = bleed(cell)
        for k in ks: rects[k] = (x, y, w, h)
        # painted part of the rect over every livery (decal u, v), one pixel wider: the mesh only covers this
        a = np.zeros((h, w), bool)
        for l in liveries: a |= sheets[l][y:y + h, x:x + w, 3] > 0
        ys, xs = np.nonzero(a)
        t = [max(xs.min() - 1, 0) / w, max(ys.min() - 1, 0) / h, min(xs.max() + 2, w) / w, min(ys.max() + 2, h) / h]
        for k in ks: trims[k] = [round(v, 5) for v in t]
    os.makedirs(outdir, exist_ok=True)
    for l, im in sheets.items():
        Image.fromarray(im, 'RGBA').save(os.path.join(outdir, 'PB22_decals_%s.png' % l), optimize=False, compress_level=9)
        print('wrote PB22_decals_%s.png' % l)
    # json: decals sorted along the aircraft
    out = []
    for k in sorted(dec, key=lambda k: (-dec[k]['f'].C[1], dec[k]['f'].C[0], dec[k]['f'].C[2])):
        e = dec[k]; f = e['f']; x, y, w, h = rects[k]
        out.append(dict(
            id=len(out), liveries=[l for l in liveries if l in e['imgs']],
            centre=r5(f.C), d=round(17.0 - float(f.C[1]), 5), right=r5(f.R), up=r5(f.U), facing=r5(f.Fc),
            size=r5(f.size), tol=round(float(f.tol), 5), box={kk: r5(v) for kk, v in sorted(f.bbox.items())},
            margin=round(float(f.margin), 5), parts=list(f.parts), hit_parts=sorted(e['parts']),
            rect=[x, y, w, h], trim=trims[k], uv=[x / SW, 1 - (y + h) / SH, (x + w) / SW, 1 - y / SH],
            px_per_m=round(min(w / f.size[0], h / f.size[1]), 1)))
    meta = dict(sheet=[SW, SH], pad=pad, liveries=list(liveries), offset_m=0.003,
                note='u = q.right/w + 0.5, v = 0.5 - q.up/h, q = P - centre (Blender world, rest pose); accepted if 0<=u,v<=1, '
                     '|q.facing| < tol, N.facing > 0.35 and inside box +- margin (d = 17 - y, ax = |x|). '
                     'uv = [u0, v0, u1, v1] of the rect, v up (Blender / Unity); image row 0 = top. '
                     'trim = [u0, v0, u1, v1] in decal u, v: the painted part, the mesh only needs to cover it.',
                decals=out)
    json.dump(meta, open(os.path.join(outdir, 'PB22_decals.json'), 'w'), indent=1)
    print('decals', len(out), 'rects', len(gl), 'sheet %dx%d' % (SW, SH))


if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if '=' not in x]
    o = dict(x.split('=', 1) for x in sys.argv[1:] if '=' in x)
    run(a[0], a[1], a[2] if len(a) > 2 else 'pb22_panels',
        tuple(o.get('liveries', 'grey,maritime,lowlevel').split(',')), int(o.get('pad', 6)))
