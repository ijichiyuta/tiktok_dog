"""タイムラインに置く要素 (テキスト/ボックス/図形/動的グラフィック)。

共通パラメータ:
    at      : (x, y) 配置位置 (アンカー=中心)。callable(t) も可
    enter   : 入りアニメ (anim.pop() など)
    exit    : 出アニメ
    emph    : [(相対秒, Anim), ...] 表示中の強調 (光沢/揺れ)
    layer   : "fg" (人物より前) / "bg" (人物より後ろ)
    blend   : "over" / "add" / "screen"
    drift   : 表示中にゆっくり拡大する量 (/秒)
    opacity : 不透明度
"""
from __future__ import annotations

import math
from functools import lru_cache

import cv2
import numpy as np

from . import shapes
from .anim import Anim, State
from .core import Sprite, blit, gblur, hash_rng, motion_blur, transform
from .easing import clamp01, ease_in_out, lerp
from .text import render_text

__all__ = ["Element", "Text", "Box", "Bubble", "Graphic", "ProgressBar", "Meter", "Phone", "Avatar",
           "AvatarGrid", "Heart", "TapHand", "Burst", "FrameRect", "kf", "Group"]


def kf(points, ease=ease_in_out):
    """キーフレーム補間関数を作る: kf([(0,0),(1.2,0.4),(2,1)]) → f(t)"""
    pts = sorted(points)

    def f(t):
        if t <= pts[0][0]:
            return pts[0][1]
        for (t0, v0), (t1, v1) in zip(pts, pts[1:]):
            if t <= t1:
                return lerp(v0, v1, ease((t - t0) / max(1e-6, t1 - t0)))
        return pts[-1][1]
    return f


class Element:
    def __init__(self, at=(540, 960), enter=None, exit=None, emph=(), layer="fg", blend="over",
                 drift=0.0, opacity=1.0, rot=0.0, scale=1.0, name=None):
        self.at = at
        self.enter: Anim | None = enter
        self.exit: Anim | None = exit
        self.emph = list(emph)
        self.layer = layer
        self.blend = blend
        self.drift = drift
        self.opacity = opacity
        self.rot = rot
        self.scale = scale
        self.start = 0.0
        self.end = 1.0
        self.name = name
        self._base = None

    # ---- サブクラスで実装 ----
    def build(self) -> Sprite:
        raise NotImplementedError

    def sprite(self, t: float, st: State) -> Sprite:
        """t: 要素内ローカル秒。動的要素は override。"""
        if self._base is None:
            self._base = self.build()
        return self._base

    # ---- 共通 ----
    def pos(self, t):
        return self.at(t) if callable(self.at) else self.at

    def state(self, t: float) -> State:
        st = State(scale=self.scale(t) if callable(self.scale) else self.scale, rot=self.rot,
                   opacity=self.opacity(t) if callable(self.opacity) else self.opacity)
        st.seed = hash((id(self), int(t * 30)))
        dur = self.end - self.start
        if self.enter and self.enter.dur > 0 and t < self.enter.dur:
            self.enter.apply(st, clamp01(t / self.enter.dur), False)
        if self.exit and self.exit.dur > 0 and t > dur - self.exit.dur:
            self.exit.apply(st, clamp01((t - (dur - self.exit.dur)) / self.exit.dur), True)
        for et, a in self.emph:
            if et <= t <= et + a.dur:
                a.apply(st, (t - et) / a.dur, False)
        if self.drift:
            st.scale *= 1 + self.drift * t
        return st

    def render(self, canvas: np.ndarray, tg: float):
        if not (self.start <= tg < self.end):
            return
        t = tg - self.start
        st = self.state(t)
        if st.opacity <= 0.003:
            return
        sp = self.sprite(t, st)
        sp = apply_state(sp, st, tg)
        x, y = self.pos(t)
        blit(canvas, sp, x + st.dx, y + st.dy, st.opacity, self.blend)


def apply_state(sp: Sprite, st: State, tg: float) -> Sprite:
    img = sp.img
    changed = False
    if st.white > 0.01:
        img = img.copy()
        img[..., :3] += (img[..., 3:4] - img[..., :3]) * min(1.0, st.white)
        changed = True
    if st.reveal < 0.999 or st.wipe_block > 0.01:
        img = _reveal(img if changed else img.copy(), st.reveal, st.reveal_dir, st.wipe_block)
        changed = True
    if st.shine is not None:
        img = _shine(img if changed else img.copy(), st.shine)
        changed = True
    sp = Sprite(img, sp.ax, sp.ay)
    if st.streak > 0.01:
        sp = _streak(sp, st.streak, st.seed)
    if st.glitch > 0.01:
        sp = _glitch(sp, st.glitch, int(tg * 30) * 7919 + st.seed % 1000)
    sp = transform(sp, st.scale, st.rot, st.sx, st.sy, st.skew)
    if st.blur > 0.4 or st.mblur > 1.5:
        pad = int(st.blur * 3 + st.mblur * 0.6) + 2
        sp = sp.pad(pad)
        im = sp.img
        if st.blur > 0.4:
            im = gblur(im, st.blur)
        if st.mblur > 1.5:
            im = motion_blur(im, st.mblur, st.mblur_angle)
        sp = Sprite(im, sp.ax, sp.ay)
    if st.rgb > 0.8:
        sp = _rgb_split(sp, st.rgb)
    return sp


def _reveal(img, r, direction, block):
    h, w = img.shape[:2]
    if direction in ("lr", "rl"):
        n, axis = w, 1
    else:
        n, axis = h, 0
    edge = r * (n + 40) - 20
    idx = np.arange(n, dtype=np.float32)
    if direction in ("rl", "bt"):
        idx = n - 1 - idx
    ramp = np.clip((edge - idx) / 20.0, 0, 1)
    ramp = ramp[None, :, None] if axis == 1 else ramp[:, None, None]
    out = img * ramp
    if block > 0.01:
        # 走査線の先頭に白ブロック (文字の外接矩形の高さ)
        a = img[..., 3]
        rows = np.nonzero(a.max(1) > 0.1)[0]
        cols = np.nonzero(a.max(0) > 0.1)[0]
        if len(rows) and len(cols):
            bw = max(10, int(0.18 * n))
            band = np.clip(1 - np.abs(idx - (edge - bw / 2)) / (bw / 2), 0, 1) ** 0.3 * block
            band = band[None, :] if axis == 1 else band[:, None]
            m = np.zeros((h, w), np.float32)
            m[rows.min():rows.max() + 1, cols.min():cols.max() + 1] = 1
            m = m * band
            out[..., :3] = out[..., :3] * (1 - m[..., None]) + m[..., None] * np.array([1, 1, 0.85], np.float32)
            out[..., 3] = out[..., 3] * (1 - m) + m
    return out


def _shine(img, pos):
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    u = (xx + yy * 0.6) / (w + h * 0.6)
    band = np.exp(-((u - pos) / 0.05) ** 2) * 0.95
    band2 = np.exp(-((u - pos + 0.09) / 0.015) ** 2) * 0.6
    b = (band + band2)[..., None] * img[..., 3:4]
    img[..., :3] += (img[..., 3:4] - img[..., :3]) * np.clip(b, 0, 1)
    return img


def _streak(sp: Sprite, a: float, seed: int) -> Sprite:
    """横方向に引き伸ばされた白い筋 → 文字 に収束。"""
    rng = np.random.default_rng(seed % 7 + 11)
    pad = int(sp.w * 0.5 * a) + 4
    sp = Sprite(cv2.copyMakeBorder(sp.img, 0, 0, pad, pad, cv2.BORDER_CONSTANT, value=(0, 0, 0, 0)),
                sp.ax + pad, sp.ay)
    img = sp.img
    h, w = img.shape[:2]
    bl = motion_blur(img, max(2, a * sp.w * 0.9))
    # 白化
    bl[..., :3] += (bl[..., 3:4] - bl[..., :3]) * min(1, a * 1.2)
    out = np.zeros_like(img)
    y = 0
    while y < h:
        bh = int(rng.integers(4, 22))
        off = int(rng.uniform(-1, 1) * a * sp.w * 0.35)
        band = bl[y:y + bh]
        out[y:y + bh] = np.roll(band, off, axis=1)
        if rng.random() < 0.35 * a:  # 完全な白線
            line = np.clip(bl[y:y + bh, :, 3].max(0, keepdims=True) * 4, 0, 1)
            out[y:y + bh, :, :3] = np.maximum(out[y:y + bh, :, :3], line[..., None] * a)
            out[y:y + bh, :, 3] = np.maximum(out[y:y + bh, :, 3], line * a)
        y += bh
    mix = min(1.0, a * 1.4)
    return Sprite(img * (1 - mix) + out * mix, sp.ax, sp.ay)


def _glitch(sp: Sprite, g: float, seed: int) -> Sprite:
    rng = np.random.default_rng(seed & 0xffffffff)
    pad = int(80 * g) + 2
    sp = Sprite(cv2.copyMakeBorder(sp.img, 0, 0, pad, pad, cv2.BORDER_CONSTANT, value=(0, 0, 0, 0)),
                sp.ax + pad, sp.ay)
    img = sp.img.copy()
    h = img.shape[0]
    y = 0
    while y < h:
        bh = int(rng.integers(3, max(4, int(h * 0.12))))
        if rng.random() < 0.55 * g + 0.1:
            off = int(rng.normal(0, 60 * g))
            img[y:y + bh] = np.roll(img[y:y + bh], off, axis=1)
            if rng.random() < 0.25 * g:
                img[y:y + bh] *= 0.0 if rng.random() < 0.5 else 1.0
                ch = int(rng.integers(0, 3))
                img[y:y + bh, :, ch] = np.minimum(img[y:y + bh, :, 3] * 1.0, 1)
        y += bh
    return Sprite(img, sp.ax, sp.ay)


def _rgb_split(sp: Sprite, px: float) -> Sprite:
    p = int(px) + 1
    sp = Sprite(cv2.copyMakeBorder(sp.img, 0, 0, p, p, cv2.BORDER_CONSTANT, value=(0, 0, 0, 0)), sp.ax + p, sp.ay)
    img = sp.img
    out = img.copy()
    s = int(px)
    r = np.roll(img, -s, axis=1)
    b = np.roll(img, s, axis=1)
    out[..., 0] = r[..., 0]
    out[..., 2] = b[..., 2]
    out[..., 3] = np.maximum(np.maximum(r[..., 3], b[..., 3]), img[..., 3])
    return Sprite(out, sp.ax, sp.ay)


# ---------------------------------------------------------------------------
class Text(Element):
    """装飾テキスト。style は palette.TEXT_STYLES のキー。"""

    def __init__(self, text, size=90, style="white_gothic", align="center", vertical=False, style_kw=None, **kw):
        super().__init__(**kw)
        self.text, self.size, self.style, self.align, self.vertical = text, size, style, align, vertical
        self.style_kw = style_kw or {}
        self._partial = {}

    def build(self):
        return render_text(self.text, self.size, self.style, self.align, self.vertical, **self.style_kw)

    def sprite(self, t, st):
        if st.chars is not None and st.chars < 1:
            n = sum(1 for c in self.text if c not in "{}|\n") + 1
            k = int(st.chars * n)
            if k not in self._partial:
                full = super().sprite(t, st)
                sp = render_text(self.text, self.size, self.style, self.align, self.vertical, max_chars=k,
                                 **self.style_kw)
                # 全文のレイアウト位置に合わせる (同じパディング計算なのでサイズ一致)
                self._partial[k] = Sprite(sp.img, full.ax, full.ay) if sp.img.shape == full.img.shape else sp
            return self._partial[k]
        return super().sprite(t, st)


class Box(Element):
    """テキスト入りラベルボックス。style は palette.BOX_STYLES のキー。"""

    def __init__(self, text, style="gold", size=46, w=None, h=None, min_w=0, pad=(26, 12), text_style=None,
                 fill=None, vertical=False, **kw):
        super().__init__(**kw)
        self.args = dict(text=text, style=style, size=size, w=w, h=h, min_w=min_w, pad=pad, text_style=text_style,
                         fill_override=fill, vertical=vertical)

    def build(self):
        return shapes.label_box(**self.args)


class Bubble(Element):
    def __init__(self, text, size=40, tail="left", **kw):
        super().__init__(**kw)
        self.text, self.size, self.tail = text, size, tail

    def build(self):
        return shapes.bubble(self.text, self.size, tail=self.tail)


class Graphic(Element):
    """任意の Sprite (もしくは生成関数) をそのまま置く。fn(t) を渡すと毎フレーム生成。"""

    def __init__(self, sprite=None, fn=None, **kw):
        super().__init__(**kw)
        self._sp, self.fn = sprite, fn

    def build(self):
        return self._sp if not callable(self._sp) else self._sp()

    def sprite(self, t, st):
        if self.fn is not None:
            return self.fn(t)
        return super().sprite(t, st)


class FrameRect(Element):
    def __init__(self, w, h, width=3, color="#e8e8e8", radius=4, size_fn=None, **kw):
        super().__init__(**kw)
        self.w, self.h, self.width, self.color, self.radius = w, h, width, color, radius
        self.size_fn = size_fn
        self._cache = {}

    def build(self):
        return shapes.frame_rect(self.w, self.h, self.width, self.color, self.radius)

    def sprite(self, t, st):
        if self.size_fn:
            w, h = self.size_fn(t)
            key = (int(w) // 2, int(h) // 2)
            if key not in self._cache:
                self._cache[key] = shapes.frame_rect(int(w), int(h), self.width, self.color, self.radius)
            return self._cache[key]
        return super().sprite(t, st)


class ProgressBar(Element):
    def __init__(self, w=560, h=36, frac=0.5, fill="green", marker=None, **kw):
        super().__init__(**kw)
        self.w, self.h, self.frac, self.fill, self.marker = w, h, frac, fill, marker
        self._cache = {}

    def sprite(self, t, st):
        f = self.frac(t) if callable(self.frac) else self.frac
        key = round(f, 3)
        if key not in self._cache:
            sp = shapes.progress_bar(self.w, self.h, f, self.fill)
            if self.marker:
                tag = shapes.label_box(self.marker, "black_tag", size=int(self.h * 0.55), pad=(10, 4),
                                       text_style="white_gothic", fill_override=[(0, "#c8121c"), (1, "#8a0a10")])
                img = sp.img.copy()
                blit(img, tag, sp.ax - self.w / 2 + tag.w / 2 - 18, sp.ay)
                sp = Sprite(img, sp.ax, sp.ay)
            self._cache[key] = sp
        return self._cache[key]


class Meter(Element):
    def __init__(self, w=560, h=70, frac=0.0, label="リーチ数", labels=("100", "300", "500", "1000", "3000"), **kw):
        super().__init__(**kw)
        self.w, self.h, self.frac, self.label, self.labels = w, h, frac, label, labels
        self._cache = {}

    def sprite(self, t, st):
        f = self.frac(t) if callable(self.frac) else self.frac
        key = round(f, 3)
        if key not in self._cache:
            self._cache[key] = shapes.meter(self.w, self.h, f, self.labels, label_text=self.label)
        return self._cache[key]


class Phone(Element):
    def __init__(self, w=170, h=320, title="Instagram\n新ルール", **kw):
        super().__init__(**kw)
        self.w, self.h, self.title = w, h, title

    def build(self):
        return shapes.phone(self.w, self.h, title=self.title)


class Avatar(Element):
    def __init__(self, r=44, kind="blue", badge=True, **kw):
        super().__init__(**kw)
        self.r, self.kind, self.badge = r, kind, badge

    def build(self):
        return shapes.avatar(self.r, self.kind, self.badge)


class AvatarGrid(Element):
    """アバターの格子 (rows×cols)。kinds は行ごとの色。"""

    def __init__(self, rows=3, cols=3, r=40, gap=120, kinds=("blue", "cyan", "violet"), **kw):
        super().__init__(**kw)
        self.rows, self.cols, self.r, self.gap, self.kinds = rows, cols, r, gap, kinds

    def build(self):
        W_ = int(self.gap * (self.cols - 1) + 2 * self.r + 60)
        H_ = int(self.gap * (self.rows - 1) + 2 * self.r + 60)
        img = np.zeros((H_, W_, 4), np.float32)
        for i in range(self.rows):
            for j in range(self.cols):
                a = shapes.avatar(self.r, self.kinds[i % len(self.kinds)])
                blit(img, a, 30 + self.r + j * self.gap, 30 + self.r + i * self.gap)
        return Sprite(img, W_ / 2, H_ / 2)


class Heart(Element):
    def __init__(self, size=60, **kw):
        super().__init__(**kw)
        self.size = size

    def build(self):
        return shapes.heart(self.size)


class TapHand(Element):
    """タップする指。tap_at=[相対秒...] で押し込み + 放射線。"""

    def __init__(self, size=120, tap_at=(), **kw):
        super().__init__(**kw)
        self.size, self.tap_at = size, tuple(tap_at)

    def build(self):
        return shapes.tap_hand(self.size)

    def render(self, canvas, tg):
        if not (self.start <= tg < self.end):
            return
        t = tg - self.start
        st = self.state(t)
        x, y = self.pos(t)
        for ta in self.tap_at:
            d = t - ta
            if 0 <= d < 0.45:
                p = d / 0.45
                b = shapes.burst(radius=int(30 + 60 * p), n=12, length=int(40 * (1 - p) + 8), width=4)
                blit(canvas, b, x, y + 10, st.opacity * (1 - p))
            if -0.12 < d < 0.12:
                st.scale *= 0.85 + 0.15 * abs(d) / 0.12
        sp = apply_state(super().sprite(t, st), st, tg)
        blit(canvas, sp, x + st.dx, y + st.dy, st.opacity, self.blend)


class Burst(Element):
    def __init__(self, radius=80, n=14, **kw):
        super().__init__(**kw)
        self.radius, self.n = radius, n

    def sprite(self, t, st):
        p = clamp01(t / max(1e-3, self.end - self.start))
        return shapes.burst(int(self.radius * (0.5 + p)), self.n, int(50 * (1 - p) + 6), 4)


class Group:
    """複数要素をまとめて同じ終了時刻・出アニメにする補助。
        g = Group(tl, end=12.5, exit=glitch())
        g.add(Text(...), 9.0)
    """

    def __init__(self, tl, end, exit=None):
        self.tl, self.end, self.exit = tl, end, exit

    def add(self, el, start, **kw):
        if self.exit is not None and el.exit is None:
            el.exit = self.exit
        return self.tl.add(el, start, self.end, **kw)
