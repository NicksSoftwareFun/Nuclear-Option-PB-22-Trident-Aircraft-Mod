"""Integrated crew cabin for the PB-22: the cockpit hump is a smooth union of the fuselage section and a hump section,
and the forward fuselage hull is built on a fixed (d, theta) grid so windows and roof hatches are exact grid cells.
Window cells are cut out of the hull (with reveal walls and inset glass), hatch cells become separate parts, and a
thin inner shell lines the cabin so the crew stations can be seen through the glazing."""
import math
from mathutils import Vector
from pb22_lib import Y
from pb22_shapes import thetas

def smax(a, b, k):
    h = max(k - abs(a - b), 0.0) / k
    return max(a, b) + h * h * k * 0.25

class UnionSection:
    """Body section with a hump section (own centre zc) merged on top by a smooth max along rays from the body centre."""
    def __init__(self, body, hump, k=0.10):
        self.body, self.hump, self.k = body, hump, k
        self.N = body.N; self.th = thetas(body.N)
        self.h0, self.h1 = hump.d[0], hump.d[-1]
    def _hump_t(self, d, th, zb):
        if d < self.h0 or d > self.h1: return 0.0
        zh = self.hump.params(d)[0]
        c, s = math.cos(th), math.sin(th)
        def inside(t):
            x, z = t * c, zb + t * s - zh
            rho = math.hypot(x, z)
            return rho <= self.hump.radius(d, math.atan2(z, x))[0]
        last = None; t = 0.0
        while t < 2.2:
            if inside(t): last = t
            t += 0.05
        if last is None: return 0.0
        lo, hi = last, last + 0.05
        for _ in range(14):
            mid = (lo + hi) / 2
            if inside(mid): lo = mid
            else: hi = mid
        return lo
    def radius(self, d, th):
        rb, zb, xb = self.body.radius(d, th)
        rh = self._hump_t(d, th, zb)
        return (smax(rb, rh, self.k) if rh > 0 else rb), zb, xb
    def point(self, d, th, off=0.0, dfun=None):
        r, zc, xc = self.radius(d, th)
        return Vector((xc + (r + off) * math.cos(th), Y(d), zc + (r + off) * math.sin(th)))
    def normal(self, d, th, eps=1e-3):
        p = self.point(d, th)
        a = self.point(d, th + eps) - self.point(d, th - eps)
        b = self.point(d + eps, th) - self.point(d - eps, th)
        n = a.cross(b).normalized()
        return n if n.dot(p - self.point(d, th, -0.1)) > 0 else -n

def deg_cell(a):
    """theta in degrees -> grid index for N cells (theta_k = 360 k / N - 90)."""
    return a

class Grid:
    """Hull cells on rings d_list x thetas. Each cell is (k, i): between ring k and k+1, theta i and i+1."""
    def __init__(self, sec, d_list):
        self.sec, self.d = sec, d_list
        self.N = sec.N
        self.thd = [360.0 * i / self.N - 90.0 for i in range(self.N + 1)]
        self.P = {}
    def pt(self, k, i, off=0.0):
        key = (k, i % self.N, round(off, 4))
        if key not in self.P:
            self.P[key] = self.sec.point(self.d[k], math.radians(self.thd[i % self.N]), off)
        return self.P[key]
    def cells(self):
        for k in range(len(self.d) - 1):
            for i in range(self.N):
                yield k, i
    def centre(self, k, i):
        dm = (self.d[k] + self.d[k + 1]) / 2
        a = (self.thd[i] + self.thd[i + 1]) / 2
        return dm, a
    def quad(self, k, i, off=0.0):
        return [self.pt(k, i, off), self.pt(k, i + 1, off), self.pt(k + 1, i + 1, off), self.pt(k + 1, i, off)]

def in_rect(d, a, r):
    """r = (d0, d1, a0, a1) in degrees; a may wrap (left side windows use 180 - a)."""
    d0, d1, a0, a1 = r
    a = (a + 90.0) % 360.0 - 90.0
    return d0 <= d <= d1 and a0 <= a <= a1

def mirror_rect(r):
    d0, d1, a0, a1 = r
    return (d0, d1, 180.0 - a1, 180.0 - a0)

def boundary_edges(cells, grid):
    """Directed boundary edges of a set of cells (outer ring winding), as pairs of (k, i) grid nodes."""
    S = set(cells)
    out = []
    for k, i in cells:
        N = grid.N
        nb = [((k, (i - 1) % N), ((k + 1, i), (k, i))),            # theta-minus side: edge node(k+1,i)->node(k,i)
              ((k, (i + 1) % N), ((k, i + 1), (k + 1, i + 1))),     # theta-plus side
              ((k - 1, i), ((k, i), (k, i + 1))),                  # d-minus side
              ((k + 1, i), ((k + 1, i + 1), (k + 1, i)))]          # d-plus side
        for (nk, ni), e in nb:
            if (nk, ni) not in S: out.append(e)
    return out
