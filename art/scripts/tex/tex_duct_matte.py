"""Matte the intake duct lining: skin texels inside the duct tube that face the duct axis get low smoothness in the _m
map, so the duct reads as painted metal in shadow instead of mirroring the sky, plus a gentle darkening with depth
(full brightness at the lip, 25 % darker at the fan).
Usage: tex_duct_matte.py <maps.npz> <_m.png in/out> [<_ao.png in/out>]
0.4.7: texels are picked from the raster maps (world position and normal per texel), not from the blend's face UVs:
those are the unpacked UVs, so 0.4.6 painted its mask onto unrelated parts of the atlas (dark bands on the outer skin)."""
import sys
import numpy as np
from PIL import Image

# duct centre line and half sizes, from pb22_structure.DUCT: (d, x centre, z centre, -, half height)
DUCT = [(14.6, 1.56, 2.45, 0.43, 0.99), (15.5, 1.55, 2.38, 0.425, 0.84), (16.5, 1.54, 2.30, 0.42, 0.72), (19.0, 1.52, 2.25, 0.42, 0.62),
        (22.0, 1.50, 2.25, 0.42, 0.58), (24.3, 1.50, 2.30, 0.42, 0.54), (24.7, 1.49, 2.31, 0.42, 0.53), (25.4, 1.06, 2.38, 0.50, 0.52),
        (26.3, 0.74, 2.40, 0.52, 0.52)]
a = sys.argv[1:]
mp = np.load(a[0])
pos, nrm, cov, mat, mats = mp['pos'], mp['nrm'], mp['cov'], mp['mat'], list(mp['mats'])
S = pos.shape[0]
x, y, z = pos[..., 0], pos[..., 1], pos[..., 2]
d = 17.0 - y; ax = np.abs(x)
ds = np.array([r[0] for r in DUCT]); cols = np.array([r[1:] for r in DUCT])
dc = np.clip(d, ds[0], ds[-1])
xc, zc, W, H = [np.interp(dc, ds, cols[:, j]) for j in range(4)]
# lip to 14.6: the intake mouth (rounded rectangle about x 1.56, z 2.465)
lip = (d >= 12.4) & (d < 14.6) & (np.abs(ax - 1.56) < 0.52) & (np.abs(z - 2.465) < 1.19)
tube = (d >= 14.6) & (d <= 26.3) & (np.abs(ax - xc) < W + 0.04) & (np.abs(z - zc) < H + 0.04)
xc = np.where(lip, 1.56, xc); zc = np.where(lip, 2.465, zc)
to_ax = np.stack([np.sign(x) * xc - x, np.zeros_like(x), zc - z], -1)
facing = (to_ax * nrm).sum(-1) > 0
skin = mat == mats.index('PB22_skin') if 'PB22_skin' in mats else np.ones_like(cov)
k = (cov & skin & (lip | tube) & facing).astype(np.float32)
depth = np.clip((d - 13.0) / 13.3, 0, 1)            # 0 at the lip, 1 at the fan
print('duct texels', int(k.sum()), 'of', S * S)


def fit(arr, size):
    return np.array(Image.fromarray((arr * 255).astype(np.uint8)).resize((size, size), Image.BILINEAR)).astype(np.float32) / 255


img = Image.open(a[1]).convert('RGBA'); Wd = img.size[0]
km = fit(k, Wd)
m = np.array(img).astype(np.float32)
m[..., 3] = m[..., 3] * (1 - km) + 0.12 * 255 * km
Image.fromarray(m.clip(0, 255).astype(np.uint8)).save(a[1])
if len(a) > 2:
    ao_img = Image.open(a[2]).convert('RGB'); Wa = ao_img.size[0]
    kd = fit(k * depth, Wa)
    ao = np.array(ao_img).astype(np.float32) * (1 - 0.25 * kd)[..., None]
    Image.fromarray(ao.clip(0, 255).astype(np.uint8)).save(a[2])
