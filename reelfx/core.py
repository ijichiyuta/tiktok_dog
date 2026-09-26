"""画像演算の基礎。全レイヤーは premultiplied RGBA float32 (0..1) で扱う。"""
from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

W, H, FPS = 1080, 1920, 30


def hex2rgb(h: str | tuple) -> np.ndarray:
    if isinstance(h, (tuple, list, np.ndarray)):
        a = np.asarray(h, np.float32)
        return a / 255.0 if a.max() > 1.0 else a
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float32)


@dataclass
class Sprite:
    """premultiplied RGBA 画像 + アンカー位置 (画像内座標)。"""
    img: np.ndarray  # (h, w, 4) float32 premultiplied
    ax: float = 0.0
    ay: float = 0.0

    @property
    def h(self):
        return self.img.shape[0]

    @property
    def w(self):
        return self.img.shape[1]

    @staticmethod
    def centered(img: np.ndarray) -> "Sprite":
        return Sprite(img, img.shape[1] / 2, img.shape[0] / 2)

    def copy(self) -> "Sprite":
        return Sprite(self.img.copy(), self.ax, self.ay)

    def pad(self, p: int) -> "Sprite":
        if p <= 0:
            return self
        return Sprite(cv2.copyMakeBorder(self.img, p, p, p, p, cv2.BORDER_CONSTANT, value=(0, 0, 0, 0)),
                      self.ax + p, self.ay + p)


def new_canvas(w=W, h=H) -> np.ndarray:
    return np.zeros((h, w, 4), np.float32)


def rgba_from_mask(mask: np.ndarray, color) -> np.ndarray:
    """単色 + アルファマスク → premultiplied RGBA。color は (3,) か (h,w,3)。"""
    c = hex2rgb(color) if isinstance(color, str) else np.asarray(color, np.float32)
    out = np.empty(mask.shape + (4,), np.float32)
    out[..., :3] = c * mask[..., None]
    out[..., 3] = mask
    return out


def over(dst: np.ndarray, src: np.ndarray) -> np.ndarray:
    """同サイズ premultiplied の over 合成 (in-place)。"""
    a = src[..., 3:4]
    dst *= (1.0 - a)
    dst += src
    return dst


def blit(canvas: np.ndarray, sp: Sprite, x: float, y: float, opacity: float = 1.0, mode: str = "over"):
    """sprite のアンカーを canvas 上の (x, y) に置いて合成。"""
    if opacity <= 0.001:
        return
    x0 = int(round(x - sp.ax))
    y0 = int(round(y - sp.ay))
    H_, W_ = canvas.shape[:2]
    sx0, sy0 = max(0, -x0), max(0, -y0)
    dx0, dy0 = max(0, x0), max(0, y0)
    dx1 = min(W_, x0 + sp.w)
    dy1 = min(H_, y0 + sp.h)
    if dx1 <= dx0 or dy1 <= dy0:
        return
    s = sp.img[sy0:sy0 + (dy1 - dy0), sx0:sx0 + (dx1 - dx0)]
    d = canvas[dy0:dy1, dx0:dx1]
    if opacity < 0.999:
        s = s * opacity
    if mode == "over":
        d *= (1.0 - s[..., 3:4])
        d += s
    elif mode == "add":  # 光系: 加算 (アルファも足してクランプ)
        d += s
        np.minimum(d, 1.0, out=d)
    elif mode == "screen":
        d[...] = d + s - d * s
    else:
        raise ValueError(mode)


def gblur(img: np.ndarray, sigma: float) -> np.ndarray:
    if sigma < 0.3:
        return img
    return cv2.GaussianBlur(img, (0, 0), sigma)


def motion_blur(img: np.ndarray, length: float, angle_deg: float = 0.0) -> np.ndarray:
    """方向性モーションブラー。length px。"""
    L = int(abs(length))
    if L < 2:
        return img
    if angle_deg % 180 == 0:
        return cv2.blur(img, (L, 1))
    if angle_deg % 180 == 90:
        return cv2.blur(img, (1, L))
    k = np.zeros((L, L), np.float32)
    c = (L - 1) / 2
    a = math.radians(angle_deg)
    for i in range(L):
        t = i - c
        k[int(round(c + t * math.sin(a))), int(round(c + t * math.cos(a)))] = 1
    k /= k.sum()
    return cv2.filter2D(img, -1, k)


def transform(sp: Sprite, scale: float = 1.0, rot: float = 0.0, sx: float = 1.0, sy: float = 1.0,
              skew_x: float = 0.0) -> Sprite:
    """アンカー中心に拡縮・回転・スキュー。新しい Sprite を返す。"""
    if abs(scale - 1) < 1e-4 and abs(rot) < 1e-3 and abs(sx - 1) < 1e-4 and abs(sy - 1) < 1e-4 and abs(skew_x) < 1e-4:
        return sp
    kx, ky = scale * sx, scale * sy
    a = math.radians(rot)
    ca, sa = math.cos(a), math.sin(a)
    # M = R * Skew * S
    M = np.array([[ca, -sa], [sa, ca]]) @ np.array([[1, skew_x], [0, 1]]) @ np.diag([kx, ky])
    corners = np.array([[0, 0], [sp.w, 0], [0, sp.h], [sp.w, sp.h]], np.float64) - [sp.ax, sp.ay]
    tc = corners @ M.T
    mn, mx = tc.min(0), tc.max(0)
    ow, oh = int(math.ceil(mx[0] - mn[0])) + 2, int(math.ceil(mx[1] - mn[1])) + 2
    if ow <= 0 or oh <= 0 or ow * oh > 6000 * 6000:
        return Sprite(np.zeros((1, 1, 4), np.float32), 0, 0)
    off = -mn + 1
    A = np.zeros((2, 3))
    A[:, :2] = M
    A[:, 2] = off - M @ np.array([sp.ax, sp.ay])
    out = cv2.warpAffine(sp.img, A, (ow, oh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                         borderValue=(0, 0, 0, 0))
    return Sprite(out, off[0], off[1])


def vgradient(h: int, w: int, stops) -> np.ndarray:
    """縦グラデーション (h,w,3)。stops=[(pos, color), ...]"""
    pos = np.array([s[0] for s in stops], np.float32)
    cols = np.array([hex2rgb(s[1]) for s in stops], np.float32)
    y = np.linspace(0, 1, max(h, 1), dtype=np.float32)
    col = np.stack([np.interp(y, pos, cols[:, i]) for i in range(3)], -1)
    return np.broadcast_to(col[:, None, :], (h, w, 3)).copy()


def hgradient(h: int, w: int, stops) -> np.ndarray:
    pos = np.array([s[0] for s in stops], np.float32)
    cols = np.array([hex2rgb(s[1]) for s in stops], np.float32)
    x = np.linspace(0, 1, max(w, 1), dtype=np.float32)
    col = np.stack([np.interp(x, pos, cols[:, i]) for i in range(3)], -1)
    return np.broadcast_to(col[None, :, :], (h, w, 3)).copy()


def dilate(mask: np.ndarray, r: float) -> np.ndarray:
    if r <= 0:
        return mask
    ri = int(math.ceil(r))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * ri + 1, 2 * ri + 1))
    return cv2.dilate(mask, k)


def to_uint8_rgb(canvas: np.ndarray, bg=(0, 0, 0)) -> np.ndarray:
    bgc = np.asarray(bg, np.float32) / 255.0
    rgb = canvas[..., :3] + bgc * (1.0 - canvas[..., 3:4])
    return (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)


def to_uint8_rgba(canvas: np.ndarray) -> np.ndarray:
    """premultiplied → straight RGBA uint8."""
    a = canvas[..., 3:4]
    rgb = np.where(a > 1e-5, canvas[..., :3] / np.maximum(a, 1e-5), 0)
    out = np.concatenate([rgb, a], -1)
    return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)


def hash_rng(*keys) -> np.random.Generator:
    return np.random.default_rng(abs(hash(tuple(keys))) % (2 ** 32))
