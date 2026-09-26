"""タイムライン: 要素の配置 + 画面全体エフェクト (グローバルFX) + 効果音キュー。"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np

from .core import FPS, H, W, gblur, hex2rgb, motion_blur, new_canvas
from .easing import clamp01, ease_out, ease_out_cubic, ease_out_expo


@dataclass
class GFx:
    kind: str
    start: float
    end: float
    params: dict = field(default_factory=dict)

    def p(self, t):
        return clamp01((t - self.start) / max(1e-6, self.end - self.start))


class Timeline:
    def __init__(self, duration: float, fps: int = FPS, size=(W, H)):
        self.duration, self.fps, self.size = duration, fps, size
        self.elements = []
        self.gfx: list[GFx] = []
        self.sfx: list[tuple] = []  # (time, name, gain)

    # ---- 構築 API ----
    def add(self, el, start: float, end: float, sfx: str | None = None, gain: float = 1.0):
        el.start, el.end = float(start), float(end)
        self.elements.append(el)
        if sfx:
            self.sfx.append((float(start), sfx, gain))
        return el

    def fx(self, kind: str, start: float, end: float, sfx: str | None = None, **params):
        """画面全体エフェクト。
        kind: glitch / flash / zoom / shake / rgb / hsmear / tint / vignette / fade_black / blur
        """
        self.gfx.append(GFx(kind, float(start), float(end), params))
        if sfx:
            self.sfx.append((float(start), sfx, params.get("gain", 1.0)))

    def cue(self, t: float, name: str, gain: float = 1.0):
        self.sfx.append((float(t), name, gain))

    # ---- レンダリング ----
    def layers(self, t: float):
        """→ (bg, fg) premultiplied RGBA キャンバス"""
        bg, fg = new_canvas(*self.size), new_canvas(*self.size)
        for el in self.elements:
            if el.start <= t < el.end:
                el.render(bg if el.layer == "bg" else fg, t)
        return bg, fg

    def compose(self, t: float, footage: np.ndarray | None = None, matte: np.ndarray | None = None,
                bg_mode: str = "auto"):
        """1フレーム合成。
        footage: (H,W,3) float32 0..1 の実写 (None なら透明背景 = エフェクトのみ)
        matte  : (H,W) 0..1 人物マスク (1=人物)。bg レイヤーを人物の後ろに回すために使う。
        戻り値: premultiplied RGBA (footage 有りならアルファ=1)
        """
        bg, fg = self.layers(t)
        if footage is None:
            out = bg
            out *= (1 - fg[..., 3:4])
            out += fg
            return self._apply_gfx(out, t, footage_mode=False)
        base = footage.astype(np.float32).copy()
        for g in self.gfx:
            if g.kind == "tint" and g.start <= t < g.end:
                base = _tint(base, g, t)
        # bg レイヤー: 人物の後ろ
        if matte is not None:
            hold = (1 - matte)[..., None]
        else:  # マット無し: 暗部にだけ乗せる (黒背景スタジオ撮影向け)
            lum = base.mean(-1, keepdims=True)
            hold = np.clip(1 - lum * 3.0, 0, 1) ** 2
        bgc = bg[..., :3] * hold
        base = base + bgc - base * bgc  # screen
        out = np.dstack([base, np.ones(base.shape[:2], np.float32)])
        out *= (1 - fg[..., 3:4])
        out += fg
        return self._apply_gfx(out, t, footage_mode=True)

    def _apply_gfx(self, img: np.ndarray, t: float, footage_mode: bool):
        for g in self.gfx:
            if not (g.start <= t < g.end) or g.kind == "tint":
                continue
            if g.kind == "vignette" and not footage_mode:
                continue
            img = GFX_FUNCS[g.kind](img, g, t)
        return img


# ---- グローバルFX 実装 -------------------------------------------------------

def _tint(img, g, t):
    """実写の色味変更 (回想/引用シーンなど)。color を multiply → mix"""
    c = hex2rgb(g.params.get("color", "#6a6cff"))
    amt = g.params.get("amount", 0.6)
    fade = g.params.get("fade", 0.12)
    k = amt * min(clamp01((t - g.start) / fade), clamp01((g.end - t) / fade))
    lum = img.mean(-1, keepdims=True)
    tinted = np.clip(lum * c * 1.8 + img * 0.25, 0, 1)
    return img * (1 - k) + tinted * k


def _glitch(img, g, t):
    rng = np.random.default_rng(int(t * 60) * 977 + 3)
    amt = g.params.get("amount", 1.0) * (1 - 0.5 * g.p(t))
    out = img.copy()
    h, w = img.shape[:2]
    y = 0
    while y < h:
        bh = int(rng.integers(6, 90))
        if rng.random() < 0.6:
            off = int(rng.normal(0, 70 * amt))
            out[y:y + bh] = np.roll(img[y:y + bh], off, axis=1)
            if rng.random() < 0.3:
                ch = int(rng.integers(0, 3))
                out[y:y + bh, :, ch] = np.roll(img[y:y + bh, :, ch], int(rng.normal(0, 40 * amt)), axis=1)
        y += bh
    # ブロックノイズ
    for _ in range(int(12 * amt)):
        bw, bh = int(rng.integers(40, 300)), int(rng.integers(8, 60))
        x0, y0 = int(rng.integers(0, w - bw)), int(rng.integers(0, h - bh))
        sx, sy = int(rng.integers(0, w - bw)), int(rng.integers(0, h - bh))
        out[y0:y0 + bh, x0:x0 + bw] = img[sy:sy + bh, sx:sx + bw]
    s = int(12 * amt)
    if s:
        out[..., 0] = np.roll(out[..., 0], s, 1)
        out[..., 2] = np.roll(out[..., 2], -s, 1)
    # 走査線
    out[::3] *= 1 - 0.25 * amt
    if out.shape[-1] == 4:
        out[..., 3] = np.maximum(out[..., 3], out[..., :3].max(-1))
    return out


def _flash(img, g, t):
    c = hex2rgb(g.params.get("color", "#ffffff"))
    peak = g.params.get("peak", 0.9)
    k = peak * (1 - ease_out(g.p(t)))
    out = img.copy()
    out[..., :3] = out[..., :3] + (c - out[..., :3]) * k
    if out.shape[-1] == 4:
        out[..., 3] = out[..., 3] + (1 - out[..., 3]) * k
    return out


def _zoom(img, g, t):
    """ズームパンチ: frm 倍から 1 倍へ (or to 倍へ)。放射ブラー近似。"""
    frm, to = g.params.get("frm", 1.25), g.params.get("to", 1.0)
    e = ease_out_expo(g.p(t))
    s = frm + (to - frm) * e
    h, w = img.shape[:2]
    cx, cy = g.params.get("center", (w / 2, h / 2))
    M = np.float32([[s, 0, cx - s * cx], [0, s, cy - s * cy]])
    out = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    blur = g.params.get("blur", 1.0) * abs(frm - to) * (1 - e) * 20
    if blur > 1:
        acc = out * 0.4
        for k, wgt in ((1.02, 0.3), (1.05, 0.3)):
            ss = 1 + (k - 1) * blur / 10
            M2 = np.float32([[ss, 0, cx - ss * cx], [0, ss, cy - ss * cy]])
            acc += cv2.warpAffine(out, M2, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT) * wgt
        out = acc
    return out


def _shake(img, g, t):
    amp = g.params.get("amp", 18) * (1 - g.p(t))
    dx = math.sin(t * 90) * amp
    dy = math.cos(t * 71) * amp * 0.7
    M = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(img, M, (img.shape[1], img.shape[0]), borderMode=cv2.BORDER_REFLECT)


def _rgb(img, g, t):
    s = int(g.params.get("px", 10) * (1 - g.p(t)))
    if s < 1:
        return img
    out = img.copy()
    out[..., 0] = np.roll(img[..., 0], s, 1)
    out[..., 2] = np.roll(img[..., 2], -s, 1)
    return out


def _hsmear(img, g, t):
    """横方向の強いブラー (トランジション)。前半で強まり後半で戻る。"""
    p = g.p(t)
    k = math.sin(math.pi * p) * g.params.get("length", 220)
    return motion_blur(img, k, 0) if k > 2 else img


def _blur(img, g, t):
    p = g.p(t)
    k = math.sin(math.pi * p) * g.params.get("sigma", 14)
    return gblur(img, k)


def _vignette(img, g, t):
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = g.params.get("center", (w / 2, h * 0.45))
    rx, ry = g.params.get("radius", (w * 0.62, h * 0.52))
    d = np.sqrt(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    v = np.clip(1 - (d - 0.7) * g.params.get("strength", 1.6), 0, 1) ** 1.5
    out = img.copy()
    out[..., :3] *= v[..., None]
    return out


def _fade_black(img, g, t):
    p = g.p(t)
    k = p if g.params.get("out", True) else 1 - p
    return img * (1 - k)


GFX_FUNCS = dict(glitch=_glitch, flash=_flash, zoom=_zoom, shake=_shake, rgb=_rgb, hsmear=_hsmear,
                 blur=_blur, vignette=_vignette, fade_black=_fade_black)
