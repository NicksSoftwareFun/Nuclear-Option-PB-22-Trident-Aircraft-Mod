"""Quick mode: the texel mask for a small geometry change, and a check that nothing else moved.
Usage: python3 tex_quick_mask.py <old maps.npz> <new maps.npz> <part,part,...> <out mask.npy>
The parts are build-time part names (the 'opart' tags, which the painter places features by) and rip parts.
Covered texels of those parts are repainted. Every other texel must keep its UV coverage and sit within 1 mm of
where it was, otherwise the UV layout changed and a full bake is needed (exit code 2)."""
import sys
import numpy as np

old, new = np.load(sys.argv[1]), np.load(sys.argv[2])
parts = [p for p in sys.argv[3].split(',') if p]
out = sys.argv[4]
names = [str(n) for n in new['names']]
if [str(n) for n in old['names']] != names: sys.exit('part list changed: full bake needed') or None
ids = [names.index(p) for p in parts if p in names]
missing = [p for p in parts if p not in names]
if missing: print('not in the atlas (skipped):', missing)
cov = new['cov'] > 0
mask = cov & (np.isin(new['pid'], ids) | np.isin(new['rpid'], ids))
rest = cov & ~mask
bad_cov = int(((old['cov'] > 0) != cov)[~mask].sum())
d = np.linalg.norm(new['pos'][rest] - old['pos'][rest], axis=1)
bad_pos = int((d > 0.001).sum())
moved = mask & (old['cov'] > 0)
dm = np.linalg.norm(new['pos'][moved] - old['pos'][moved], axis=1)
print('mask %d texels (%.2f%% of the atlas), parts %s' % (mask.sum(), 100 * mask.sum() / cov.sum(), parts))
print('inside the mask: max move %.3f m, %d texels moved > 1 mm' % (dm.max() if len(dm) else 0, int((dm > 0.001).sum())))
print('outside the mask: coverage changes %d, texels moved > 1 mm %d (max %.4f m)' % (bad_cov, bad_pos, d.max() if len(d) else 0))
if bad_cov or bad_pos:
    print('UV layout changed outside the changed parts: run the full bake'); sys.exit(2)
np.save(out, mask)
# the objects the masked texels sit on now (rip parts): the AO bake has to rebake all of them
objs = sorted({names[i] for i in np.unique(new['rpid'][mask])})
open(out + '.objs', 'w').write(','.join(objs))
print('saved', out, 'objects', objs)
