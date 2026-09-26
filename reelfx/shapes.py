"""図形パーツ: ラベルボックス / 吹き出し / メーター / プログレスバー / スマホ / アバター / タップ手 / 集中線 など。
すべて Sprite (中心アンカー) を返す。"""
from __future__ import annotations

import math

import cv2
import numpy as np

from .core import Sprite, gblur, hex2rgb, hgradient, over, rgba_from_mask, vgradient
from .palette import BOX_STYLES, GRAD
from .text import TextStyle, render_text

SS = 2  # 図形のスーパーサンプリング倍率


def _rrect_mask(w, h, r, ss=SS):
    W_, H_ = int(w * ss), int(h * ss)
    m = np.zeros((H_, W_), np.uint8)
    r = int(min(r * ss, W_ / 2, H_ / 2))
    if r <= 0:
        m[:] = 255
    else:
        cv2.rectangle(m, (r, 0), (W_ - r - 1, H_ - 1), 255, -1)
        cv2.rectangle(m, (0, r), (W_ - 1, H_ - r - 1), 255, -1)
        for cx, cy in ((r, r), (W_ - r - 1, r), (r, H_ - r - 1), (W_ - r - 1, H_ - r - 1)):
            cv2.circle(m, (cx, cy), r, 255, -1, cv2.LINE_AA)
    return cv2.resize(m, (int(w), int(h)), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0


def _fill(fill, h, w, direction="v"):
    if fill is None:
        return None
    if isinstance(fill, str) and fill in GRAD:
        return (vgradient if direction == "v" else hgradient)(h, w, GRAD[fill])
    if isinstance(fill, list):
        return (vgradient if direction == "v" else hgradient)(h, w, fill)
    return np.broadcast_to(hex2rgb(fill), (h, w, 3)).copy()


def _shadowed(core: np.ndarray, alpha: np.ndarray, shadow, pad: int) -> np.ndarray:
    """core: premult RGBA (pad 済), alpha: 影の元形状"""
    if not shadow:
        return core
    sh = shadow if isinstance(shadow, dict) else dict(zip(("color", "dx", "dy", "blur", "opacity"), shadow))
    M = np.float32([[1, 0, sh.get("dx", 0)], [0, 1, sh.get("dy", 0)]])
    s = cv2.warpAffine(alpha, M, (alpha.shape[1], alpha.shape[0]))
    s = np.clip(gblur(s, sh.get("blur", 6)) * sh.get("opacity", 0.9), 0, 1)
    out = rgba_from_mask(s, sh.get("color", "#000"))
    return over(out, core)


def box(w, h, fill="gold_box", border=None, radius=0, shadow=None, hl=0.0, fill_dir="v") -> Sprite:
    """グラデ塗り + 枠線 + 上ハイライト + 影 付きの矩形。"""
    w, h = int(w), int(h)
    P = 30 if shadow else 4
    Wp, Hp = w + 2 * P, h + 2 * P
    m = np.zeros((Hp, Wp), np.float32)
    m[P:P + h, P:P + w] = _rrect_mask(w, h, radius)
    out = np.zeros((Hp, Wp, 4), np.float32)
    rgb = _fill(fill, h, w, fill_dir)
    if rgb is not None:
        full = np.zeros((Hp, Wp, 3), np.float32)
        full[P:P + h, P:P + w] = rgb
        out[..., :3] = full * m[..., None]
        out[..., 3] = m
        if hl > 0:  # 上半分に薄いハイライト (ガラス感)
            g = np.zeros((Hp, Wp), np.float32)
            g[P:P + h // 2, P:P + w] = np.linspace(hl, 0, h // 2, dtype=np.float32)[:, None]
            g *= m
            out[..., :3] += (out[..., 3:4] - out[..., :3]) * g[..., None]
    if border:
        bw, bc = border
        inner = np.zeros_like(m)
        inner[P + bw:P + h - bw, P + bw:P + w - bw] = _rrect_mask(w - 2 * bw, h - 2 * bw, max(0, radius - bw))
        ring = np.clip(m - inner, 0, 1)
        out = over(out, rgba_from_mask(ring, bc))
    alpha = out[..., 3].copy()
    out = _shadowed(out, alpha, shadow, P)
    return Sprite(out, Wp / 2, Hp / 2)


def label_box(text, style="gold", size=46, pad=(26, 12), min_w=0, w=None, h=None, text_style=None,
              align="center", fill_override=None, vertical=False) -> Sprite:
    """テロップ用ラベルボックス (金/紫/マゼンタ/黒金 など)。"""
    bs = dict(BOX_STYLES[style])
    if fill_override:
        bs["fill"] = fill_override
    ts = render_text(text, size, text_style or bs["text"], align=align, vertical=vertical)
    # テキストの見た目サイズ (影パディング込みの sprite から概算)
    tw, th = _ink_size(ts)
    bw = w or max(min_w, tw + 2 * pad[0])
    bh = h or th + 2 * pad[1]
    b = box(bw, bh, bs["fill"], bs.get("border"), bs.get("radius", 0), bs.get("shadow"), bs.get("hl", 0))
    out = b.img.copy()
    _blit_center(out, ts, b.ax, b.ay)
    return Sprite(out, b.ax, b.ay)


def _ink_size(sp: Sprite):
    a = sp.img[..., 3]
    ys, xs = np.nonzero(a > 0.5)
    if len(xs) == 0:
        return 0, 0
    return xs.max() - xs.min(), ys.max() - ys.min()


def _blit_center(dst, sp: Sprite, cx, cy):
    from .core import blit
    blit(dst, sp, cx, cy)


def bubble(text, size=40, pad=(28, 22), tail="left", text_style="label_dark") -> Sprite:
    """角丸の吹き出し (明るいグレーグラデ + 濃色文字)。"""
    ts = render_text(text, size, TextStyle.get(text_style, font="gothic_bold"), align="left")
    tw, th = _ink_size(ts)
    w, h = tw + 2 * pad[0], th + 2 * pad[1]
    P = 40
    Wp, Hp = w + 2 * P, h + 2 * P
    m = np.zeros((Hp, Wp), np.float32)
    m[P:P + h, P:P + w] = _rrect_mask(w, h, 22)
    # しっぽ
    tm = np.zeros((Hp * SS, Wp * SS), np.uint8)
    if tail == "left":
        pts = np.array([[P + 10, P + 28], [P - 22, P - 10], [P + 44, P + 10]]) * SS
    else:
        pts = np.array([[P + w - 10, P + 28], [P + w + 22, P - 10], [P + w - 44, P + 10]]) * SS
    cv2.fillPoly(tm, [pts.astype(np.int32)], 255, cv2.LINE_AA)
    m = np.maximum(m, cv2.resize(tm, (Wp, Hp), interpolation=cv2.INTER_AREA).astype(np.float32) / 255)
    out = np.zeros((Hp, Wp, 4), np.float32)
    rgb = vgradient(Hp, Wp, GRAD["bubble"])
    out[..., :3] = rgb * m[..., None]
    out[..., 3] = m
    # 薄い縁
    edge = np.clip(m - cv2.erode(m, np.ones((5, 5), np.uint8)), 0, 1) * 0.5
    out = over(out, rgba_from_mask(edge, "#8a8a90"))
    out = _shadowed(out, m, dict(color="#000", dx=4, dy=8, blur=10, opacity=0.8), P)
    sp = Sprite(out, Wp / 2, Hp / 2)
    from .core import blit
    blit(sp.img, ts, Wp / 2, Hp / 2)
    return sp


def frame_rect(w, h, width=3, color="#e8e8e8", radius=4, shadow=True) -> Sprite:
    return box(w, h, None, (width, color), radius, dict(color="#000", dx=0, dy=4, blur=8, opacity=0.7) if shadow else None)


def progress_bar(w, h, frac, fill="green", track="#1a1a1a", border=(3, "#d8d8d8")) -> Sprite:
    """横プログレスバー (再生維持率など)。frac 0..1"""
    b = box(w, h, [(0, track), (1, "#050505")], border, 2, dict(color="#000", dx=0, dy=4, blur=8, opacity=0.7))
    out = b.img
    fw = int((w - 2 * border[0]) * max(0.0, min(1.0, frac)))
    if fw > 0:
        x0 = int(b.ax - w / 2 + border[0])
        y0 = int(b.ay - h / 2 + border[0])
        hh = h - 2 * border[0]
        rgb = vgradient(hh, fw, GRAD[fill] if isinstance(fill, str) and fill in GRAD else [(0, fill), (1, fill)])
        seg = out[y0:y0 + hh, x0:x0 + fw]
        seg[..., :3] = rgb
        seg[..., 3] = 1
    return b


def meter(w, h, frac, labels=("100", "300", "500", "1000", "3000"), ticks=(0.25, 0.5, 0.75, 0.92),
          label_text="リーチ数", fill="gold_box") -> Sprite:
    """リーチ数メーター: 白枠 + 金フィル + 区切り + 下に目盛り数値。"""
    P = 60
    Wp, Hp = w + 2 * P, h + 2 * P + 60
    out = np.zeros((Hp, Wp, 4), np.float32)
    fr = frame_rect(w, h, 3, "#eeeeee", 0)
    from .core import blit
    bgd = box(w, h, [(0, "#0c0c0c"), (1, "#000")], None, 0)
    blit(out, bgd, Wp / 2, P + h / 2, 0.55)
    fw = int((w - 6) * max(0, min(1, frac)))
    if fw > 2:
        fb = box(fw, h - 6, fill, None, 0)
        blit(out, fb, P + 3 + fw / 2, P + h / 2)
    for t in ticks:
        x = int(P + w * t)
        out[P:P + h, x - 2:x + 2, :] = [0.9, 0.9, 0.9, 1]
    blit(out, fr, Wp / 2, P + h / 2)
    lt = render_text(label_text, int(h * 0.55), "white_gothic")
    blit(out, lt, Wp / 2, P + h / 2)
    n = len(labels)
    for i, lab in enumerate(labels):
        x = P + w * (i / (n - 1)) if n > 1 else Wp / 2
        x = min(max(x, P + 30), P + w - 30)
        blit(out, render_text(lab, 34, "gold_gothic", strokes=((2, "#222"),)), x, P + h + 34)
    return Sprite(out, Wp / 2, P + h / 2)


def phone(w=180, h=330, screen=None, title="Instagram\n新ルール") -> Sprite:
    """スマホのモック (黒ベゼル + 画面)。screen: (h,w,3) rgb か None → 赤黒グラデ + タイトル"""
    P = 30
    Wp, Hp = w + 2 * P, h + 2 * P
    out = np.zeros((Hp, Wp, 4), np.float32)
    from .core import blit
    blit(out, box(w, h, [(0, "#1d1d1d"), (1, "#050505")], (3, "#6d6d6d"), 26,
                  dict(color="#000", dx=0, dy=6, blur=12, opacity=0.9)), Wp / 2, Hp / 2)
    sw, sh = w - 18, h - 22
    if screen is None:
        scr = box(sw, sh, [(0, "#3a0a10"), (0.55, "#b0141e"), (1, "#16030a")], None, 18)
        blit(scr.img, render_text(title, int(sw * 0.16), "gold_mincho", strokes=((2, "#200"),)), scr.ax, scr.ay - sh * 0.1)
        # 画面下の人影シルエット (抽象)
        m = np.zeros((scr.h, scr.w), np.float32)
        cv2.ellipse(m, (int(scr.ax), int(scr.ay + sh * 0.42)), (int(sw * 0.32), int(sh * 0.22)), 0, 180, 360, 1, -1, cv2.LINE_AA)
        cv2.circle(m, (int(scr.ax), int(scr.ay + sh * 0.12)), int(sw * 0.13), 1, -1, cv2.LINE_AA)
        blit(scr.img, Sprite(rgba_from_mask(m * 0.55, "#0a0a14"), scr.ax, scr.ay), scr.ax, scr.ay)
        blit(out, scr, Wp / 2, Hp / 2)
    else:
        s = cv2.resize(screen, (sw, sh)).astype(np.float32)
        s = s / 255.0 if s.max() > 1 else s
        m = _rrect_mask(sw, sh, 18)
        sp = Sprite(np.dstack([s * m[..., None], m]), sw / 2, sh / 2)
        blit(out, sp, Wp / 2, Hp / 2)
    # ノッチ
    cv2.rectangle(out, (int(Wp / 2 - 22), P + 8), (int(Wp / 2 + 22), P + 16), (0, 0, 0, 1), -1)
    return Sprite(out, Wp / 2, Hp / 2)


AVATAR = dict(
    gray=[(0, "#d9d9d9"), (1, "#8a8a8a")],
    white=[(0, "#ffffff"), (1, "#d0d0d8")],
    blue=[(0, "#9fc4ff"), (1, "#4a78f0")],
    cyan=[(0, "#9ff4ff"), (1, "#2fb4ff")],
    violet=[(0, "#c3b0ff"), (1, "#6a4cf0")],
)


def avatar(r=44, kind="blue", badge=True) -> Sprite:
    """丸アイコン + 人型シルエット + 右下の青い「+」バッジ。"""
    P = 16
    D = 2 * r + 2 * P
    ss = SS
    m = np.zeros((D * ss, D * ss), np.uint8)
    cv2.circle(m, (D * ss // 2, D * ss // 2), r * ss, 255, -1, cv2.LINE_AA)
    m = cv2.resize(m, (D, D), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    rgb = vgradient(D, D, AVATAR[kind])
    out = np.dstack([rgb * m[..., None], m])
    # シルエット
    s = np.zeros((D * ss, D * ss), np.uint8)
    c = D * ss // 2
    cv2.circle(s, (c, c - int(r * 0.22 * ss)), int(r * 0.34 * ss), 255, -1, cv2.LINE_AA)
    cv2.ellipse(s, (c, c + int(r * 0.78 * ss)), (int(r * 0.62 * ss), int(r * 0.55 * ss)), 0, 180, 360, 255, -1, cv2.LINE_AA)
    s = cv2.resize(s, (D, D), interpolation=cv2.INTER_AREA).astype(np.float32) / 255 * m
    out = over(out, rgba_from_mask(s * 0.55, "#ffffff"))
    out = over(out, rgba_from_mask(np.clip(m - cv2.erode(m, np.ones((3, 3), np.uint8)), 0, 1) * 0.6, "#ffffff"))
    sp = Sprite(out, D / 2, D / 2)
    if badge:
        from .core import blit
        br = max(8, r // 3)
        bb = np.zeros((br * 2 + 6, br * 2 + 6), np.float32)
        cv2.circle(bb, (br + 3, br + 3), br + 2, 1, -1, cv2.LINE_AA)
        bs = rgba_from_mask(bb, "#ffffff")
        inner = np.zeros_like(bb)
        cv2.circle(inner, (br + 3, br + 3), br, 1, -1, cv2.LINE_AA)
        bs = over(bs, rgba_from_mask(inner, "#1e90ff"))
        pl = np.zeros_like(bb)
        cv2.line(pl, (br + 3 - br // 2, br + 3), (br + 3 + br // 2, br + 3), 1, 2, cv2.LINE_AA)
        cv2.line(pl, (br + 3, br + 3 - br // 2), (br + 3, br + 3 + br // 2), 1, 2, cv2.LINE_AA)
        bs = over(bs, rgba_from_mask(pl, "#ffffff"))
        blit(sp.img, Sprite(bs, br + 3, br + 3), D / 2 + r * 0.72, D / 2 + r * 0.72)
    return sp


def heart(size=60, thickness=5, rainbow=True) -> Sprite:
    """アウトラインのハート (虹グラデ)。"""
    P = 10
    S = size + 2 * P
    ss = 3
    m = np.zeros((S * ss, S * ss), np.uint8)
    t = np.linspace(0, 2 * math.pi, 200)
    x = 16 * np.sin(t) ** 3
    y = -(13 * np.cos(t) - 5 * np.cos(2 * t) - 2 * np.cos(3 * t) - np.cos(4 * t))
    pts = np.stack([x, y], 1) / 34 * size * ss + S * ss / 2
    cv2.polylines(m, [pts.astype(np.int32)], True, 255, thickness * ss, cv2.LINE_AA)
    m = cv2.resize(m, (S, S), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    if rainbow:
        rgb = hgradient(S, S, [(0, "#ff4d6d"), (0.35, "#ffb347"), (0.65, "#7afcff"), (1, "#b36bff")])
    else:
        rgb = np.broadcast_to(hex2rgb("#ff5a7a"), (S, S, 3))
    return Sprite(np.dstack([rgb * m[..., None], m]).astype(np.float32), S / 2, S / 2)


def tap_hand(size=120, color="#f7a54a") -> Sprite:
    """タップを促す指アイコン (オレンジ + 白フチ)。指先がアンカー。"""
    ss = 3
    S = int(size * 1.6)
    m = np.zeros((S * ss, S * ss), np.uint8)
    u = size * ss / 100.0
    cx = S * ss // 2
    # 人差し指
    cv2.ellipse(m, (int(cx), int(22 * u)), (int(11 * u), int(11 * u)), 0, 0, 360, 255, -1, cv2.LINE_AA)
    cv2.rectangle(m, (int(cx - 11 * u), int(22 * u)), (int(cx + 11 * u), int(80 * u)), 255, -1)
    # 手のひら
    cv2.ellipse(m, (int(cx + 12 * u), int(92 * u)), (int(34 * u), int(30 * u)), 0, 0, 360, 255, -1, cv2.LINE_AA)
    for i, dx in enumerate((22, 40)):
        cv2.ellipse(m, (int(cx + dx * u), int(62 * u)), (int(10 * u), int(12 * u)), 0, 0, 360, 255, -1, cv2.LINE_AA)
    # 親指
    cv2.ellipse(m, (int(cx - 22 * u), int(84 * u)), (int(11 * u), int(22 * u)), -35, 0, 360, 255, -1, cv2.LINE_AA)
    m = cv2.resize(m, (S, S), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    outline = cv2.dilate(m, k)
    out = rgba_from_mask(outline, "#ffffff")
    rgb = vgradient(S, S, [(0, "#ffc27a"), (1, color)])
    out = over(out, np.dstack([rgb * m[..., None], m]).astype(np.float32))
    return Sprite(out, S / 2, 22 * size / 100.0 - 11 * size / 100 + 2)


def burst(radius=80, n=12, length=40, width=5, color="#ffffff", phase=0.0) -> Sprite:
    """タップ時の放射線 (集中線ミニ)。"""
    S = int(2 * (radius + length) + 20)
    ss = 2
    m = np.zeros((S * ss, S * ss), np.uint8)
    c = S * ss / 2
    for i in range(n):
        a = 2 * math.pi * i / n + phase
        x0, y0 = c + math.cos(a) * radius * ss, c + math.sin(a) * radius * ss
        x1, y1 = c + math.cos(a) * (radius + length) * ss, c + math.sin(a) * (radius + length) * ss
        cv2.line(m, (int(x0), int(y0)), (int(x1), int(y1)), 255, width * ss, cv2.LINE_AA)
    m = cv2.resize(m, (S, S), interpolation=cv2.INTER_AREA).astype(np.float32) / 255
    return Sprite(rgba_from_mask(m, color), S / 2, S / 2)
