#!/usr/bin/env python3
"""The odds model of src/calib.h in Python (workstream anypos): Calib::odds (hat basis on log2 tile sum, logit
a_T(s) + b_T(s) u with u = log(max(value / vbar(s), 0.01)), chain rule over targets) times the next-tile survival, as
analyze computes a position's odds from its "odds_in" (surviving spawns' mean value, survival, tile sum, max tile).
Optional extra term (candidate fixes): z_T += sum_j c_T,j(s) x_j for extra features x (hat-interpolated c, same knots)."""
import math

class Model:
    def __init__(self, path):
        self.knots, self.vbar, self.umode, self.target, self.extra = [], [], 0, {}, {}
        self.lines = open(path).read().split('\n')
        for line in self.lines:
            p = line.split()
            if not p: continue
            if p[0] == 'knots': self.knots = [float(x) for x in p[1:]]
            elif p[0] == 'vbar': self.vbar = [float(x) for x in p[1:]]
            elif p[0] == 'umode': self.umode = int(p[1])
            elif p[0] == 'target': self.target[int(p[1])] = [float(x) for x in p[2:]]

    def hats(self, s):
        k = self.knots; n = len(k); B = [0.0] * n
        if s <= k[0]: B[0] = 1; return B
        if s >= k[-1]: B[-1] = 1; return B
        for i in range(n - 1):
            if k[i] <= s < k[i + 1]:
                w = (s - k[i]) / (k[i + 1] - k[i]); B[i], B[i + 1] = 1 - w, w; return B
        return B

    def z(self, T, tile_sum, value, x=None, coef=None):
        B = self.hats(math.log2(max(tile_sum, 2.0)))
        n = len(self.knots)
        vb = max(1.0, sum(b * v for b, v in zip(B, self.vbar)))
        ratio = value / vb
        u = math.log(max(ratio, 0.01)) if self.umode == 1 else max(-0.3, min(0.3, ratio - 1.0))
        c = self.target[T]
        z = sum(B[i] * c[i] for i in range(n)) + sum(B[i] * c[n + i] for i in range(n)) * u
        if x is not None and coef is not None and T in coef:
            for j, xj in enumerate(x):
                cj = coef[T][j]
                z += sum(B[i] * cj[i] for i in range(n)) * xj
        return z, u

    def prob(self, T, tile_sum, value, x=None, coef=None):
        z, _ = self.z(T, tile_sum, value, x, coef)
        return 1 / (1 + math.exp(-max(-30, min(30, z))))

    def odds(self, max_tile, tile_sum, value, survival=1.0, x=None, coef=None):
        B = self.hats(math.log2(max(tile_sum, 2.0)))
        avg = max(1.0, sum(b * v for b, v in zip(B, self.vbar)))
        out, prev, prev_base = {}, -1, -1
        for T in sorted(self.target):
            if T <= max_tile: continue
            p = self.prob(T, tile_sum, value, x, coef)
            base = self.prob(T, tile_sum, avg, x, coef)  # the extra term shifts the base too (a formation effect)
            if prev >= 0 and prev_base > 0: p = min(p, prev * min(1.0, base / prev_base))
            if prev >= 0: p = min(p, prev)
            out[T] = p
            prev, prev_base = p, base
        return {T: p * survival for T, p in out.items()}
