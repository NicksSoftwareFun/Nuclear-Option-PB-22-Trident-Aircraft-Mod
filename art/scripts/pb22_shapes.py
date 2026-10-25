"""Polar cross-section lofting for the PB-22 detail model.
A station is (d, zc, xc, prof) where prof(theta) returns the radius of the cross-section boundary at
angle theta (0 = +X, pi/2 = up). Radii are interpolated between stations with Catmull-Rom, so a
superellipse nose can morph into a rounded-rectangle nacelle box without kinks."""
import math
from mathutils import Vector
from pb22_lib import Y

def _tan(a, b, c):
    d0, d1 = b - a, c - b
    if d0 * d1 <= 0 or abs(d0) < 1e-9 or abs(d1) < 1e-9: return 0.0
    return 2.0 / (1.0 / d0 + 1.0 / d1)

def catmull(p0, p1, p2, p3, t):
    """Monotone cubic Hermite through p1..p2 (no overshoot between stations; flat stretches stay flat).
    At the ends of a station list p0 == p1 (or p2 == p3), which gives a zero end slope."""
    m1, m2 = _tan(p0, p1, p2), _tan(p1, p2, p3)
    t2, t3 = t * t, t * t * t
    return (2 * t3 - 3 * t2 + 1) * p1 + (t3 - 2 * t2 + t) * m1 + (-2 * t3 + 3 * t2) * p2 + (t3 - t2) * m2

def prof_se(a, b, n):
    def f(th):
        c, s = abs(math.cos(th)), abs(math.sin(th))
        return ((c / a) ** n + (s / b) ** n) ** (-1.0 / n)
    return f

def prof_rr(W, H, rt, rb=None, zoff=0.0):
    """Rounded rectangle, half-width W, half-height H, top corner radius rt, bottom rb."""
    rb = rt if rb is None else rb
    def f(th):
        c, s = math.cos(th), math.sin(th)
        r = rt if s >= 0 else rb
        ac, as_ = abs(c), abs(s)
        if ac > 1e-9:
            t = W / ac
            if t * as_ <= H - r + 1e-9: return t
        if as_ > 1e-9:
            t = H / as_
            if t * ac <= W - r + 1e-9: return t
        cx, cz = W - r, H - r
        dot = ac * cx + as_ * cz
        return dot + math.sqrt(max(dot * dot - (cx * cx + cz * cz) + r * r, 0.0))
    return f

def thetas(N): return [2 * math.pi * k / N - math.pi / 2 for k in range(N)]

class Section:
    def __init__(self, stations, N):
        self.N = N; self.th = thetas(N)
        self.d = [s[0] for s in stations]
        self.zc = [s[1] for s in stations]; self.xc = [s[2] for s in stations]
        self.R = [[s[3](t) for t in self.th] for s in stations]
        self.profs = [s[3] for s in stations]
    def _seg(self, d):
        n = len(self.d)
        for i in range(n - 1):
            if d <= self.d[i + 1] + 1e-9 or i == n - 2:
                t = (d - self.d[i]) / (self.d[i + 1] - self.d[i]); return i, min(max(t, 0.0), 1.0)
    def _cr(self, arr, i, t):
        n = len(arr); return catmull(arr[max(i - 1, 0)], arr[i], arr[i + 1], arr[min(i + 2, n - 1)], t)
    def params(self, d):
        i, t = self._seg(d)
        return self._cr(self.zc, i, t), self._cr(self.xc, i, t), i, t
    def radius(self, d, th):
        zc, xc, i, t = self.params(d)
        rs = [p(th) for p in self.profs]
        return max(self._cr(rs, i, t), 0.0), zc, xc
    def point(self, d, th, off=0.0, dfun=None):
        r, zc, xc = self.radius(d, th)
        dd = dfun(d, r * math.sin(th) + zc) if dfun else d
        return Vector((xc + (r + off) * math.cos(th), Y(dd), zc + (r + off) * math.sin(th)))
    def ring(self, d, off=0.0, dfun=None):
        zc, xc, i, t = self.params(d)
        out = []
        for k, th in enumerate(self.th):
            r = max(catmull(self.R[max(i - 1, 0)][k], self.R[i][k], self.R[i + 1][k], self.R[min(i + 2, len(self.R) - 1)][k], t), 0.0)
            z = zc + (r + off) * math.sin(th)
            dd = dfun(d, z) if dfun else d
            out.append(Vector((xc + (r + off) * math.cos(th), Y(dd), z)))
        return out
    def ds(self, d0, d1, step):
        pts = {round(d0, 5), round(d1, 5)}
        for d in self.d:
            if d0 < d < d1: pts.add(round(d, 5))
        n = max(int(math.ceil((d1 - d0) / step)), 1)
        for k in range(1, n): pts.add(round(d0 + (d1 - d0) * k / n, 5))
        return sorted(pts)
    def rings(self, d0, d1, step, off=0.0, dfun=None):
        return [self.ring(d, off, dfun) for d in self.ds(d0, d1, step)]
