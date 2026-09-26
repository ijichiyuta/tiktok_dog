"""アニメーション: 入り(enter)・出(exit)・強調(emph) を State への変更として定義する。

Anim は p (0→1) を受け取り State を書き換える。enter は p=0 で「出現前」、p=1 で「定位置」。
exit は p=0 で「定位置」、p=1 で「消えた後」。同じ Anim を enter/exit 両方に使える
(exit のときは内部で p を反転して使う: reverse=True)。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .easing import *  # noqa

__all__ = ["State", "Anim", "fade", "pop", "slam", "zoom_in", "slide", "blur_in", "streak", "glitch",
           "wipe", "drop", "flash_in", "stretch", "spin_in", "shine", "shake", "pulse", "typewriter",
           "rgb_split", "none", "combo"]


@dataclass
class State:
    dx: float = 0.0
    dy: float = 0.0
    scale: float = 1.0
    sx: float = 1.0
    sy: float = 1.0
    rot: float = 0.0
    skew: float = 0.0
    opacity: float = 1.0
    blur: float = 0.0
    mblur: float = 0.0          # モーションブラー長 (px)
    mblur_angle: float = 0.0
    white: float = 0.0          # 白飛び量 0..1
    streak: float = 0.0         # 横ストリーク 0..1
    glitch: float = 0.0         # グリッチ 0..1
    rgb: float = 0.0            # RGB ずれ px
    reveal: float = 1.0         # ワイプ表示率
    reveal_dir: str = "lr"
    wipe_block: float = 0.0     # ワイプ時の白ブロック強度
    shine: float | None = None  # 光沢スイープ位置 (-0.2..1.2)
    chars: float | None = None  # タイプライター表示割合
    seed: int = 0


@dataclass
class Anim:
    dur: float = 0.3
    fn: callable = None
    name: str = ""

    def apply(self, st: State, p: float, exit_: bool = False):
        self.fn(st, (1 - p) if exit_ else p, exit_)


def _mk(name, dur, fn):
    return Anim(dur, fn, name)


def none(dur=0.0):
    return _mk("none", dur, lambda st, p, ex: None)


def fade(dur=0.25, ease=ease_out):
    def f(st, p, ex):
        st.opacity *= ease(p)
    return _mk("fade", dur, f)


def pop(dur=0.28, from_scale=1.45, overshoot=1.9, blur=6):
    """ポン！と弾んで出る (最頻出)。"""
    def f(st, p, ex):
        e = ease_out_back(p, overshoot) if not ex else ease_out(p)
        st.scale *= lerp(from_scale, 1.0, e)
        st.opacity *= clamp01(p * 3)
        st.blur += blur * (1 - clamp01(p * 1.5))
    return _mk("pop", dur, f)


def slam(dur=0.22, from_scale=2.8, flash=0.9):
    """巨大サイズから叩きつけ + 白フラッシュ + ズームブラー。見出しのインパクト用。"""
    def f(st, p, ex):
        e = ease_out_expo(p)
        st.scale *= lerp(from_scale, 1.0, e)
        st.opacity *= clamp01(p * 4)
        st.blur += 10 * (1 - e)
        st.white = max(st.white, flash * (1 - clamp01(p * 1.2)))
    return _mk("slam", dur, f)


def zoom_in(dur=0.3, from_scale=0.2):
    def f(st, p, ex):
        e = ease_out_back(p, 1.3)
        st.scale *= lerp(from_scale, 1.0, e)
        st.opacity *= clamp01(p * 2.5)
    return _mk("zoom_in", dur, f)


def slide(dur=0.3, dx=-400, dy=0, blur=True, ease=ease_out_expo):
    """方向モーションブラー付きスライド。"""
    def f(st, p, ex):
        e = ease(p)
        st.dx += dx * (1 - e)
        st.dy += dy * (1 - e)
        st.opacity *= clamp01(p * 3)
        if blur:
            v = (1 - e) * math.hypot(dx, dy) * 0.35
            st.mblur += v
            st.mblur_angle = math.degrees(math.atan2(dy, dx))
    return _mk("slide", dur, f)


def blur_in(dur=0.35, sigma=22, from_scale=1.12):
    """ボケ → ピント (ソフトな出現)。"""
    def f(st, p, ex):
        e = ease_out_cubic(p)
        st.blur += sigma * (1 - e)
        st.scale *= lerp(from_scale, 1.0, e)
        st.opacity *= clamp01(p * 1.8)
    return _mk("blur_in", dur, f)


def streak(dur=0.3):
    """横方向の白い光の筋が収束して文字になる (ボックス系の出現)。"""
    def f(st, p, ex):
        e = ease_out_cubic(p)
        st.streak = max(st.streak, 1 - e)
        st.opacity *= clamp01(p * 4)
    return _mk("streak", dur, f)


def glitch(dur=0.2, amount=1.0):
    """スライスずれ + RGB 分離 (出/入 どちらでも)。"""
    def f(st, p, ex):
        g = (1 - p) * amount
        st.glitch = max(st.glitch, g)
        st.rgb += 18 * g
        st.opacity *= clamp01(p * 3) if not ex else clamp01(0.3 + p)
    return _mk("glitch", dur, f)


def wipe(dur=0.25, direction="lr", block=True):
    """白いブロックが走って文字を置いていくワイプ。"""
    def f(st, p, ex):
        e = ease_out_cubic(p)
        st.reveal = min(st.reveal, e)
        st.reveal_dir = direction
        if block:
            st.wipe_block = max(st.wipe_block, 1 - clamp01((p - 0.6) / 0.4))
    return _mk("wipe", dur, f)


def drop(dur=0.3, dist=500):
    """上から落ちてくる (縦モーションブラー)。縦書きタグ向け。"""
    return slide(dur, 0, -dist, True, ease_out_expo)


def flash_in(dur=0.25):
    def f(st, p, ex):
        st.white = max(st.white, 1 - ease_out(p))
        st.opacity *= clamp01(p * 3)
    return _mk("flash_in", dur, f)


def stretch(dur=0.25, axis="x", amount=2.5):
    """横(縦)に伸びた状態から縮む。"""
    def f(st, p, ex):
        e = ease_out_expo(p)
        k = lerp(amount, 1.0, e)
        if axis == "x":
            st.sx *= k
            st.sy *= lerp(0.3, 1, e)
        else:
            st.sy *= k
            st.sx *= lerp(0.3, 1, e)
        st.opacity *= clamp01(p * 3)
        st.mblur += 60 * (1 - e)
        st.mblur_angle = 0 if axis == "x" else 90
    return _mk("stretch", dur, f)


def spin_in(dur=0.35, turns=-0.25, from_scale=0.3):
    def f(st, p, ex):
        e = ease_out_back(p, 1.2)
        st.rot += 360 * turns * (1 - e)
        st.scale *= lerp(from_scale, 1, e)
        st.opacity *= clamp01(p * 2)
    return _mk("spin_in", dur, f)


def rgb_split(dur=0.25, px=14):
    def f(st, p, ex):
        st.rgb += px * (1 - p)
        st.opacity *= clamp01(p * 3)
    return _mk("rgb_split", dur, f)


def typewriter(dur=1.0):
    """1文字ずつ表示 (enter のみ)。"""
    def f(st, p, ex):
        st.chars = p
    return _mk("typewriter", dur, f)


def combo(*anims):
    """複数アニメの合成。dur は最大値。"""
    def f(st, p, ex):
        d = max(a.dur for a in anims)
        for a in anims:
            q = clamp01(p * d / a.dur) if a.dur > 0 else 1
            a.fn(st, q, ex)
    return _mk("combo", max(a.dur for a in anims), f)


# ---- 強調 (hold 中の一点アクセント) --------------------------------------
def shine(dur=0.45):
    """斜めの光沢が走る。"""
    def f(st, p, ex):
        st.shine = lerp(-0.25, 1.25, ease_in_out(p))
    return _mk("shine", dur, f)


def shake(dur=0.25, amp=14):
    def f(st, p, ex):
        k = (1 - p) * amp
        st.dx += math.sin(p * 55) * k
        st.dy += math.cos(p * 43) * k * 0.6
    return _mk("shake", dur, f)


def pulse(dur=0.3, amount=0.12):
    def f(st, p, ex):
        st.scale *= 1 + amount * math.sin(math.pi * p)
    return _mk("pulse", dur, f)
