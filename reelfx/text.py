"""装飾テキストのレンダリング (グラデ塗り・多重フチ・ドロップシャドウ・グロー・ベベル・縦書き・リッチテキスト)。

リッチテキスト記法:  "{意|1.6}図的に\\n{バズらせる|1|crimson_gothic}方法"
    {テキスト|サイズ倍率|スタイル名}   倍率/スタイルは省略可。改行は \\n
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .core import Sprite, dilate, gblur, hex2rgb, hgradient, over, rgba_from_mask, transform, vgradient
from .fonts import get_font
from .palette import GRAD, TEXT_STYLES

VERT_ROTATE = set("ー―－〜～…‥「」『』（）()[]【】〈〉《》=＝-")


@dataclass(frozen=True)
class TextStyle:
    font: str = "gothic"
    fill: str = "white"            # GRAD 名 / "#rrggbb"
    fill_dir: str = "v"            # v | h
    strokes: tuple = ()            # ((width, color), ...) 内側→外側の順に太くなる
    shadow: tuple | None = None    # (color, dx, dy, blur, opacity)
    glow: tuple | None = None      # (color, radius, strength)
    bevel: float = 0.0             # 上エッジのハイライト強度
    tracking: float = 0.0          # 字間 (em)
    skew: float = 0.0              # 斜体 (0.2 ≒ 11°)
    line_gap: float = 0.12         # 行間 (em)
    embolden: float = 0.0          # 線を太らせる (em)
    rough: float = 0.0             # 輪郭の荒らし (em) — 明朝を筆文字風にする

    @staticmethod
    def get(name_or_style, **over_) -> "TextStyle":
        if isinstance(name_or_style, TextStyle):
            return replace(name_or_style, **over_) if over_ else name_or_style
        d = dict(TEXT_STYLES[name_or_style])
        d.update(over_)
        return TextStyle.from_dict(d)

    @staticmethod
    def from_dict(d: dict) -> "TextStyle":
        d = dict(d)
        if "strokes" in d:
            d["strokes"] = tuple(tuple(s) for s in d["strokes"])
        sh = d.get("shadow")
        if isinstance(sh, dict):
            d["shadow"] = (sh["color"], sh.get("dx", 0), sh.get("dy", 0), sh.get("blur", 4), sh.get("opacity", 1))
        gl = d.get("glow")
        if isinstance(gl, dict):
            d["glow"] = (gl["color"], gl.get("radius", 12), gl.get("strength", 1))
        return TextStyle(**d)


_RUN_RE = re.compile(r"\{([^{}|]*)(?:\|([0-9.]*))?(?:\|([a-zA-Z_0-9#]+))?\}")


def parse_rich(s: str):
    """→ lines: [[(text, scale, style_name|None), ...], ...]"""
    lines = []
    for raw in s.split("\n"):
        runs, pos = [], 0
        for m in _RUN_RE.finditer(raw):
            if m.start() > pos:
                runs.append((raw[pos:m.start()], 1.0, None))
            runs.append((m.group(1), float(m.group(2)) if m.group(2) else 1.0, m.group(3) or None))
            pos = m.end()
        if pos < len(raw):
            runs.append((raw[pos:], 1.0, None))
        lines.append(runs or [("", 1.0, None)])
    return lines


def _fill_rgb(fill: str, h: int, w: int, direction="v") -> np.ndarray:
    if fill in GRAD:
        return (vgradient if direction == "v" else hgradient)(h, w, GRAD[fill])
    return np.broadcast_to(hex2rgb(fill), (h, w, 3)).copy()


def _layout(text: str, size: int, style: TextStyle, align: str, vertical: bool):
    """文字ごとの配置を計算。→ glyphs [(ch, font_name, px, x, y_baseline, run_style, line_idx)], (w,h), line_boxes"""
    lines = parse_rich(text)
    glyphs = []
    line_boxes = []  # (top, bottom) per line (for per-line gradients)
    if not vertical:
        y = 0.0
        widths = []
        per_line = []
        for li, runs in enumerate(lines):
            x = 0.0
            asc_max, desc_max = 0.0, 0.0
            items = []
            for txt, sc, st in runs:
                rs = TextStyle.get(st) if st else style
                px = max(4, int(round(size * sc)))
                f = get_font(rs.font, px)
                asc, desc = f.getmetrics()
                asc_max, desc_max = max(asc_max, asc), max(desc_max, desc)
                for ch in txt:
                    adv = f.getlength(ch)
                    items.append((ch, rs.font, px, x, rs))
                    x += adv + rs.tracking * px
            if items:
                x -= items[-1][4].tracking * items[-1][2]
            if not items:
                f = get_font(style.font, size)
                asc_max, desc_max = f.getmetrics()
            widths.append(x)
            per_line.append((items, asc_max, desc_max))
        maxw = max(widths) if widths else 0
        for li, ((items, asc, desc), lw) in enumerate(zip(per_line, widths)):
            off = {"left": 0, "center": (maxw - lw) / 2, "right": maxw - lw}[align]
            base = y + asc
            for ch, fn, px, x, rs in items:
                glyphs.append((ch, fn, px, x + off, base, rs, li))
            line_boxes.append((y + asc * 0.12, base + desc * 0.6))
            y = base + desc + style.line_gap * size
        total_h = y - style.line_gap * size
        return glyphs, (maxw, total_h), line_boxes
    # 縦書き: 各行 = 1列, 右から左
    cols = []
    for runs in lines:
        items, yy = [], 0.0
        colw = 0
        for txt, sc, st in runs:
            rs = TextStyle.get(st) if st else style
            px = max(4, int(round(size * sc)))
            for ch in txt:
                items.append((ch, rs.font, px, yy, rs))
                yy += px * (1.0 + rs.tracking)
                colw = max(colw, px)
        cols.append((items, yy, colw))
    gap = size * (1 + style.line_gap)
    total_w = gap * (len(cols) - 1) + (cols[0][2] if cols else size)
    total_h = max(c[1] for c in cols) if cols else size
    for ci, (items, colh, colw) in enumerate(cols):
        cx = total_w - colw / 2 - ci * gap
        for ch, fn, px, yy, rs in items:
            glyphs.append((ch, fn, px, cx, yy, rs, ci))
        line_boxes.append((0, total_h))
    return glyphs, (total_w, total_h), line_boxes


@lru_cache(maxsize=4096)
def _glyph_mask(ch: str, font: str, px: int, rotate: bool) -> tuple:
    f = get_font(font, px)
    asc, desc = f.getmetrics()
    w = int(f.getlength(ch)) + px
    im = Image.new("L", (w + 4, asc + desc + 4), 0)
    ImageDraw.Draw(im).text((2, 2), ch, font=f, fill=255)
    a = np.asarray(im, np.float32) / 255.0
    if rotate:
        a = np.rot90(a, -1).copy()
    return a, asc


def render_mask(text: str, size: int, style: TextStyle, align="center", vertical=False, max_chars=None):
    """テキストのアルファマスクと各グリフの run スタイル別マスクを返す。"""
    glyphs, (tw, th), line_boxes = _layout(text, size, style, align, vertical)
    pad = 4
    Wm, Hm = int(np.ceil(tw)) + 2 * pad + size // 2, int(np.ceil(th)) + 2 * pad + size // 2
    masks: dict = {}  # style -> mask
    for gi, (ch, fn, px, x, y, rs, li) in enumerate(glyphs):
        if max_chars is not None and gi >= max_chars:
            break
        if ch.isspace():
            continue
        rot = vertical and ch in VERT_ROTATE
        a, asc = _glyph_mask(ch, fn, px, rot)
        if vertical:
            ys, xs = np.nonzero(a > 0.05)
            if len(xs) == 0:
                continue
            a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            small = ch in "ゃゅょっぁぃぅぇぉャュョッァィゥェォ、。"
            cy = y + px * (0.35 if small else 0.5)
            ox = int(round(x - a.shape[1] / 2 + pad + (px * 0.15 if small else 0)))
            oy = int(round(cy - a.shape[0] / 2 + pad))
        else:
            ox = int(round(x + pad - 2))
            oy = int(round(y - asc + pad - 2))
        m = masks.setdefault(rs, np.zeros((Hm, Wm), np.float32))
        h_, w_ = a.shape
        y0, x0 = max(oy, 0), max(ox, 0)
        y1, x1 = min(oy + h_, Hm), min(ox + w_, Wm)
        if y1 > y0 and x1 > x0:
            sub = a[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
            np.maximum(m[y0:y1, x0:x1], sub, out=m[y0:y1, x0:x1])
    return masks, (tw, th), pad, [(t + pad, b + pad) for t, b in line_boxes]


def render_text(text: str, size: int = 96, style="white_gothic", align="center", vertical=False,
                max_chars=None, **style_over) -> Sprite:
    """装飾テキストを Sprite (中心アンカー) として描画。"""
    st = TextStyle.get(style, **style_over)
    masks, (tw, th), pad0, line_boxes = render_mask(text, size, st, align, vertical, max_chars)
    if not masks:
        return Sprite(np.zeros((2, 2, 4), np.float32), 1, 1)
    any_m = next(iter(masks.values()))
    Hm, Wm = any_m.shape
    # 効果用の余白
    max_st = max([sw for s in masks for sw, _ in s.strokes] + [0])
    sh = st.shadow
    gl = st.glow
    P = int(max_st + 4 + (abs(sh[1]) + abs(sh[2]) + sh[3] * 3 if sh else 0) + (gl[1] * 2 if gl else 0))
    Hp, Wp = Hm + 2 * P, Wm + 2 * P

    def padm(m):
        return cv2.copyMakeBorder(m, P, P, P, P, cv2.BORDER_CONSTANT, value=0)

    masks = {s: padm(m) for s, m in masks.items()}
    masks = {s: (np.clip(gblur(dilate(m, s.embolden * size), 0.6), 0, 1) if s.embolden else m)
             for s, m in masks.items()}
    masks = {s: (_roughen(m, s.rough * size, hash(text) & 0xffff) if s.rough else m) for s, m in masks.items()}
    union = np.zeros((Hp, Wp), np.float32)
    for m in masks.values():
        np.maximum(union, m, out=union)
    outer = union
    outer_w = max_st
    if outer_w:
        outer = np.clip(gblur(dilate(union, outer_w), 0.6), 0, 1)

    out = np.zeros((Hp, Wp, 4), np.float32)
    # glow
    if gl:
        g = gblur(outer, gl[1]) * gl[2]
        out = over(out, rgba_from_mask(np.clip(g, 0, 1), gl[0]))
    # shadow
    if sh:
        col, dx, dy, blur, op = sh
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        s = cv2.warpAffine(outer, M, (Wp, Hp))
        s = np.clip(gblur(s, blur) * op * (1.3 if blur > 3 else 1.0), 0, 1)
        out = over(out, rgba_from_mask(s, col))
    # strokes (外側から) → fill
    for rs, m in masks.items():
        for sw, scol in sorted(rs.strokes, key=lambda s: -s[0]):
            sm = np.clip(gblur(dilate(m, sw), 0.5), 0, 1)
            out = over(out, rgba_from_mask(sm, scol))
    for rs, m in masks.items():
        if rs.fill in GRAD and rs.fill_dir == "v" and not vertical:
            rgb = np.zeros((Hp, Wp, 3), np.float32)
            for (t, b) in line_boxes:
                t, b = int(t + P), int(b + P)
                t0, b0 = max(0, t - 2), min(Hp, b + 2)
                if b0 > t0:
                    rgb[t0:b0] = vgradient(b0 - t0, Wp, _GR(rs.fill))
            # 行外の余白は最終色で埋める
            rgb[:max(0, int(line_boxes[0][0] + P) - 2)] = hex2rgb(_GR(rs.fill)[0][1])
            rgb[min(Hp, int(line_boxes[-1][1] + P) + 2):] = hex2rgb(_GR(rs.fill)[-1][1])
        else:
            rgb = _fill_rgb(rs.fill, Hp, Wp, rs.fill_dir)
        fill = np.empty((Hp, Wp, 4), np.float32)
        fill[..., :3] = rgb * m[..., None]
        fill[..., 3] = m
        out = over(out, fill)
        if rs.bevel > 0:
            # 上エッジの細いハイライト = マスク - 下にずらしたマスク
            shifted = np.zeros_like(m)
            k = max(1, size // 40)
            shifted[k:] = m[:-k]
            hl = np.clip(m - shifted, 0, 1) * rs.bevel
            hl = gblur(hl, 0.7)
            out[..., :3] += (1 - out[..., :3]) * hl[..., None] * m[..., None]
    sp = Sprite(out, Wp / 2, Hp / 2)
    if st.skew:
        sp = transform(sp, skew_x=-st.skew)
    return sp


def _GR(name):
    return GRAD[name]


def _roughen(m: np.ndarray, amp: float, seed: int) -> np.ndarray:
    """輪郭をノイズで歪ませ、かすれを加えて筆っぽくする。"""
    h, w = m.shape
    rng = np.random.default_rng(seed)
    def field(cell):
        gh, gw = max(2, int(h / cell)), max(2, int(w / cell))
        return cv2.resize(rng.standard_normal((gh, gw)).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
    cell = max(10.0, amp * 10)
    dx = field(cell) * amp + field(cell / 4) * amp * 0.15
    dy = field(cell) * amp * 0.5
    gx, gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    out = cv2.remap(m, gx + dx, gy + dy, cv2.INTER_LINEAR, borderValue=0)
    # かすれ: 横方向に伸びたノイズで輪郭付近を削る
    streak = cv2.resize(rng.random((max(2, h // 3), max(2, w // 40))).astype(np.float32), (w, h),
                        interpolation=cv2.INTER_LINEAR)
    edge = np.clip(out - cv2.erode(out, np.ones((int(amp) * 2 + 3,) * 2, np.uint8)), 0, 1)
    out = np.clip(out - edge * (streak > 0.88) * 0.8, 0, 1)
    return gblur(out, 0.6)
