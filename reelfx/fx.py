"""光・エネルギー系の手続き的エフェクト要素 (加算合成で使う)。

NeonSwirls  : 背景の紫ネオンの渦 (人物の後ろ)
Lightning   : 稲妻
EnergySlash : シアンの斬撃スウッシュ
LensStreak  : ピンク白のレンズストリーク
Sparkles    : キラキラ粒子
"""
from __future__ import annotations

import math

import cv2
import numpy as np

from .core import H, W, Sprite, gblur, hex2rgb
from .easing import clamp01, ease_out_cubic
from .elements import Element

__all__ = ["NeonSwirls", "Lightning", "EnergySlash", "LensStreak", "Sparkles"]


def _glow_stack(core: np.ndarray, sigmas=(2, 7, 20), weights=(1.0, 0.8, 0.6)) -> np.ndarray:
    out = core.copy()
    for s, w in zip(sigmas, weights):
        out += gblur(core, s) * w
    return out


def _to_sprite_add(rgb: np.ndarray, scale: int = 1) -> Sprite:
    if scale != 1:
        rgb = cv2.resize(rgb, (rgb.shape[1] * scale, rgb.shape[0] * scale), interpolation=cv2.INTER_LINEAR)
    rgb = np.clip(rgb, 0, 1)
    a = np.clip(rgb.max(-1), 0, 1)
    return Sprite(np.dstack([rgb, a]).astype(np.float32), 0, 0)


class NeonSwirls(Element):
    """紫〜マゼンタのネオン・リボンがゆっくり回る。画面全体サイズ。"""

    def __init__(self, seed=3, intensity=1.0, speed=1.0, colors=("#7a2cff", "#c040ff", "#5a4cff", "#ff4ce0"),
                 zones=((0.02, 0.40), (0.98, 0.38), (0.5, 0.22), (0.05, 0.66), (0.96, 0.64)), n=10, **kw):
        kw.setdefault("layer", "bg")
        kw.setdefault("blend", "add")
        kw.setdefault("at", (0, 0))
        super().__init__(**kw)
        rng = np.random.default_rng(seed)
        self.intensity, self.speed = intensity, speed
        self.rib = []
        for i in range(n):
            zx, zy = zones[i % len(zones)]
            self.rib.append(dict(
                cx=zx * W + rng.normal(0, 60), cy=zy * H + rng.normal(0, 80),
                a=rng.uniform(140, 420), b=rng.uniform(60, 260), rot0=rng.uniform(0, 360),
                w=rng.uniform(-25, 25), s0=rng.uniform(0, 360), span=rng.uniform(70, 200),
                th=rng.uniform(1.5, 4.0), col=hex2rgb(colors[i % len(colors)]) * rng.uniform(0.7, 1.1),
                ph=rng.uniform(0, 6.28), sw=rng.uniform(-60, 60)))

    def sprite(self, t, st):
        s = 2  # 半解像度で描いて拡大
        h, w = H // s, W // s
        core = np.zeros((h, w, 3), np.float32)
        T = t * self.speed
        for r in self.rib:
            rot = r["rot0"] + r["w"] * T
            s0 = r["s0"] + r["sw"] * T
            flick = 0.75 + 0.25 * math.sin(T * 2.1 + r["ph"])
            col = tuple(float(c) * flick for c in r["col"])
            cv2.ellipse(core, (int(r["cx"] / s), int(r["cy"] / s)), (int(r["a"] / s), int(r["b"] / s)), rot,
                        s0, s0 + r["span"], col, max(1, int(r["th"] / s * 1.5)), cv2.LINE_AA)
        glow = _glow_stack(core, (1.5, 5, 16), (1.2, 1.0, 0.9)) * self.intensity
        # コアを白っぽく
        lum = core.max(-1, keepdims=True)
        glow += lum * 0.6
        return _to_sprite_add(glow, s)


class Lightning(Element):
    """稲妻。a→b に枝分かれ付きのボルトを数フレームごとに再生成。"""

    def __init__(self, a=(150, 700), b=(700, 1500), color="#63f2ff", branches=3, rate=15, width=3,
                 flash=0.35, **kw):
        kw.setdefault("blend", "add")
        kw.setdefault("at", (0, 0))
        super().__init__(**kw)
        self.a, self.b, self.color, self.branches, self.rate, self.width, self.flash = a, b, color, branches, rate, width, flash

    @staticmethod
    def _bolt(p0, p1, rng, disp, depth=6):
        pts = [np.array(p0, float), np.array(p1, float)]
        for _ in range(depth):
            new = [pts[0]]
            for q0, q1 in zip(pts, pts[1:]):
                mid = (q0 + q1) / 2
                d = q1 - q0
                n = np.array([-d[1], d[0]]) / (np.linalg.norm(d) + 1e-6)
                mid += n * rng.normal(0, disp)
                new += [mid, q1]
            pts = new
            disp *= 0.55
        return np.array(pts)

    def sprite(self, t, st):
        s = 2
        h, w = H // s, W // s
        rng = np.random.default_rng(int(t * self.rate) * 131 + 7)
        core = np.zeros((h, w, 3), np.float32)
        a, b = np.array(self.a) / s, np.array(self.b) / s
        L = np.linalg.norm(b - a)
        main = self._bolt(a, b, rng, L * 0.12)
        cv2.polylines(core, [main.astype(np.int32)], False, (1, 1, 1), max(1, self.width // s + 1), cv2.LINE_AA)
        for _ in range(self.branches):
            i = int(rng.integers(len(main) // 5, len(main) - 2))
            p0 = main[i]
            ang = rng.uniform(-1, 1) + math.atan2(*(b - a)[::-1])
            p1 = p0 + np.array([math.cos(ang), math.sin(ang)]) * L * rng.uniform(0.15, 0.35)
            br = self._bolt(p0, p1, rng, L * 0.05, 5)
            cv2.polylines(core, [br.astype(np.int32)], False, (0.8, 0.8, 0.8), 1, cv2.LINE_AA)
        c = hex2rgb(self.color)
        glow = core + gblur(core, 3) * c * 2.0 + gblur(core, 12) * c * 2.5 + gblur(core, 40) * c * 3.0
        if self.flash:
            yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
            m = (a + b) / 2
            r = np.exp(-(((xx - m[0]) ** 2 + (yy - m[1]) ** 2) / (2 * (L * 0.6) ** 2)))
            glow += r[..., None] * c * self.flash * (0.6 + 0.4 * rng.random())
        return _to_sprite_add(glow, s)


class EnergySlash(Element):
    """シアンの三日月型スウッシュ (斬撃)。sweep で弧が伸び、末尾から消える。"""

    def __init__(self, center=(540, 800), radius=(420, 260), angle=-20, arc=(200, 340), color="#4fe8ff",
                 thickness=46, **kw):
        kw.setdefault("blend", "add")
        kw.setdefault("at", (0, 0))
        super().__init__(**kw)
        self.center, self.radius, self.angle, self.arc, self.color, self.thickness = center, radius, angle, arc, color, thickness

    def sprite(self, t, st):
        s = 2
        h, w = H // s, W // s
        dur = self.end - self.start
        p = clamp01(t / max(dur, 1e-3))
        head = self.arc[0] + (self.arc[1] - self.arc[0]) * ease_out_cubic(clamp01(p * 1.6))
        tail = self.arc[0] + (self.arc[1] - self.arc[0]) * ease_out_cubic(clamp01((p - 0.25) * 1.4))
        core = np.zeros((h, w, 3), np.float32)
        n = 24
        c = hex2rgb(self.color)
        for i in range(n):
            q = i / (n - 1)
            a0 = tail + (head - tail) * q
            a1 = tail + (head - tail) * (q + 1 / n)
            th = max(1, int(self.thickness / s * math.sin(math.pi * q) ** 0.8))
            col = tuple(float(x) for x in (c * 0.6 + 0.4 * q))
            cv2.ellipse(core, (int(self.center[0] / s), int(self.center[1] / s)),
                        (int(self.radius[0] / s), int(self.radius[1] / s)), self.angle, a0, a1, col, th, cv2.LINE_AA)
        glow = core * 0.9 + gblur(core, 6) * 1.2 + gblur(core, 24) * c * 1.4
        return _to_sprite_add(glow * (1 - clamp01((p - 0.7) / 0.3)), s)


class LensStreak(Element):
    """細長いレンズフレアの光条 (ピンク〜白)。p0→p1 に移動。"""

    def __init__(self, p0=(300, 700), p1=(420, 560), length=260, angle=-55, color="#ff7ad9", **kw):
        kw.setdefault("blend", "add")
        kw.setdefault("at", (0, 0))
        super().__init__(**kw)
        self.p0, self.p1, self.length, self.angle, self.color = p0, p1, length, angle, color

    def sprite(self, t, st):
        dur = self.end - self.start
        p = clamp01(t / max(dur, 1e-3))
        x = self.p0[0] + (self.p1[0] - self.p0[0]) * p
        y = self.p0[1] + (self.p1[1] - self.p0[1]) * p
        S = int(self.length * 1.6)
        core = np.zeros((S, S, 3), np.float32)
        a = math.radians(self.angle)
        d = np.array([math.cos(a), math.sin(a)]) * self.length / 2
        c0 = np.array([S / 2, S / 2])
        cv2.line(core, tuple((c0 - d).astype(int)), tuple((c0 + d).astype(int)), (1, 1, 1), 6, cv2.LINE_AA)
        col = hex2rgb(self.color)
        glow = core + gblur(core, 5) * col * 2 + gblur(core, 18) * col * 1.5
        glow *= math.sin(math.pi * p)
        sp = _to_sprite_add(glow)
        return Sprite(sp.img, S / 2 - x, S / 2 - y)  # at=(0,0) なので逆算してアンカーを置く


class Sparkles(Element):
    """ランダムなキラキラ粒子 (範囲 rect 内)。"""

    def __init__(self, rect=(0, 0, W, H), n=40, color="#fff4c0", seed=1, **kw):
        kw.setdefault("blend", "add")
        kw.setdefault("at", (0, 0))
        super().__init__(**kw)
        rng = np.random.default_rng(seed)
        x0, y0, x1, y1 = rect
        self.pts = np.stack([rng.uniform(x0, x1, n), rng.uniform(y0, y1, n), rng.uniform(0, 6.28, n),
                             rng.uniform(1.5, 4, n), rng.uniform(-40, -10, n)], 1)
        self.color = color

    def sprite(self, t, st):
        s = 2
        core = np.zeros((H // s, W // s, 3), np.float32)
        c = tuple(float(v) for v in hex2rgb(self.color))
        for x, y, ph, sz, vy in self.pts:
            k = 0.5 + 0.5 * math.sin(t * 6 + ph)
            cv2.circle(core, (int(x / s), int((y + vy * t) / s)), max(1, int(sz * k / s * 2)),
                       tuple(v * k for v in c), -1, cv2.LINE_AA)
        glow = core + gblur(core, 4) * 1.5
        return _to_sprite_add(glow, s)
