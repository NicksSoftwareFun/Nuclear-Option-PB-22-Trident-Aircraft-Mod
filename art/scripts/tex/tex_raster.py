"""Rasterise an atlas family from tex_geom.py output into texel maps: world position, normal, part id, coverage.
Usage: python3 tex_raster.py <geom.npz> <family> <size> <out.npz>
Uncovered texels are filled from the nearest covered texel (dilation) so bakes don't leave seams."""
import sys, numpy as np
from scipy import ndimage
g = np.load(sys.argv[1]); fam = sys.argv[2]; S = int(sys.argv[3])
UV, P, N, PID = g[fam + '_uv'], g[fam + '_p'], g[fam + '_n'], g[fam + '_pid']
pos = np.zeros((S, S, 3), np.float32); nrm = np.zeros((S, S, 3), np.float32)
pid = np.full((S, S), -1, np.int16); cov = np.zeros((S, S), bool)
uvp = UV * S - 0.5   # texel centres at integer coords
for t in range(len(UV)):
    a, b, c = uvp[t]
    x0 = max(int(np.floor(min(a[0], b[0], c[0]))), 0); x1 = min(int(np.ceil(max(a[0], b[0], c[0]))), S - 1)
    y0 = max(int(np.floor(min(a[1], b[1], c[1]))), 0); y1 = min(int(np.ceil(max(a[1], b[1], c[1]))), S - 1)
    if x1 < x0 or y1 < y0: continue
    xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
    den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(den) < 1e-12: continue
    w0 = ((b[1] - c[1]) * (xs - c[0]) + (c[0] - b[0]) * (ys - c[1])) / den
    w1 = ((c[1] - a[1]) * (xs - c[0]) + (a[0] - c[0]) * (ys - c[1])) / den
    w2 = 1 - w0 - w1
    e = -1e-4
    m = (w0 >= e) & (w1 >= e) & (w2 >= e)
    if not m.any(): continue
    W = np.stack([w0[m], w1[m], w2[m]], 1)
    yy, xx = ys[m], xs[m]
    pos[yy, xx] = W @ P[t]; nrm[yy, xx] = W @ N[t]; pid[yy, xx] = PID[t]; cov[yy, xx] = True
nrm /= np.maximum(np.linalg.norm(nrm, axis=2, keepdims=True), 1e-6)
# dilate: copy nearest covered texel into the gutter
idx = ndimage.distance_transform_edt(~cov, return_distances=False, return_indices=True)
pos = pos[idx[0], idx[1]]; nrm = nrm[idx[0], idx[1]]; pid = pid[idx[0], idx[1]]
# rows: image row 0 = top = UV v 1
np.savez(sys.argv[4], pos=pos[::-1].astype(np.float32), nrm=nrm[::-1].astype(np.float16), pid=pid[::-1], cov=cov[::-1], names=g['names'])
print(fam, S, 'coverage %.3f' % cov.mean())
