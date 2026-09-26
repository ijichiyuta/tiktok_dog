"""イージング関数。すべて p∈[0,1] → [0,1] (back/elastic はオーバーシュートあり)。"""
import math

__all__ = ["clamp01", "lerp", "linear", "ease_in", "ease_out", "ease_in_out", "ease_out_cubic",
           "ease_in_cubic", "ease_out_expo", "ease_in_expo", "ease_out_back", "ease_out_elastic",
           "ease_in_back", "smoothstep", "EASINGS"]


def clamp01(p):
    return 0.0 if p < 0 else 1.0 if p > 1 else p


def lerp(a, b, p):
    return a + (b - a) * p


def linear(p): return clamp01(p)
def ease_in(p): p = clamp01(p); return p * p
def ease_out(p): p = clamp01(p); return 1 - (1 - p) ** 2
def ease_in_out(p): p = clamp01(p); return 2 * p * p if p < .5 else 1 - (-2 * p + 2) ** 2 / 2
def ease_out_cubic(p): p = clamp01(p); return 1 - (1 - p) ** 3
def ease_in_cubic(p): p = clamp01(p); return p ** 3
def ease_out_expo(p): p = clamp01(p); return 1.0 if p >= 1 else 1 - 2 ** (-10 * p)
def ease_in_expo(p): p = clamp01(p); return 0.0 if p <= 0 else 2 ** (10 * p - 10)
def smoothstep(p): p = clamp01(p); return p * p * (3 - 2 * p)


def ease_out_back(p, s=1.70158):
    p = clamp01(p) - 1
    return p * p * ((s + 1) * p + s) + 1


def ease_in_back(p, s=1.70158):
    p = clamp01(p)
    return p * p * ((s + 1) * p - s)


def ease_out_elastic(p):
    p = clamp01(p)
    if p in (0, 1):
        return p
    return 2 ** (-10 * p) * math.sin((p * 10 - 0.75) * (2 * math.pi / 3)) + 1


EASINGS = {k: v for k, v in globals().items() if k.startswith("ease") or k in ("linear", "smoothstep")}
