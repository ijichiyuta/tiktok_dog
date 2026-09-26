"""効果音シンセ (外部素材なしで whoosh / hit / pop / glitch / shine / zap / tap / type を生成)。"""
from __future__ import annotations

import wave

import numpy as np

SR = 48000


def _env(n, a=0.005, d=0.2, curve=4.0):
    t = np.arange(n) / SR
    att = np.clip(t / max(a, 1e-4), 0, 1)
    dec = np.exp(-np.maximum(t - a, 0) / max(d, 1e-4) * (curve / 4))
    return att * dec


def _lp(x, cut):
    """時変 1 次ローパス (cut: 配列 or 定数 Hz)。"""
    cut = np.broadcast_to(np.asarray(cut, np.float64), x.shape)
    a = 1 - np.exp(-2 * np.pi * cut / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += a[i] * (x[i] - acc)
        y[i] = acc
    return y


def whoosh(dur=0.45, f0=300, f1=4500, rng=None):
    rng = rng or np.random.default_rng(1)
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    noise = rng.standard_normal(n)
    cut = f0 * (f1 / f0) ** np.sin(np.pi * t * 0.5)
    y = _lp(noise, cut) - _lp(noise, cut * 0.25)
    env = np.sin(np.pi * np.clip(t * 1.3, 0, 1)) ** 1.5
    return y * env * 1.6


def swish(dur=0.22):
    return whoosh(dur, 800, 7000, np.random.default_rng(2)) * 0.8


def hit(dur=0.7):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 55 + 90 * np.exp(-t * 18)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 5)
    click = np.random.default_rng(3).standard_normal(n) * np.exp(-t * 60) * 0.6
    return np.tanh((body + _lp(click, 3000)) * 2.2) * 0.9


def pop(dur=0.09):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 1200 * np.exp(-t * 25) + 350
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.002, 0.03) * 0.7


def glitch(dur=0.3):
    rng = np.random.default_rng(4)
    n = int(dur * SR)
    y = np.zeros(n)
    i = 0
    while i < n:
        L = int(rng.integers(300, 3000))
        kind = rng.random()
        seg = np.arange(min(L, n - i))
        if kind < 0.4:
            y[i:i + L] = np.sign(np.sin(2 * np.pi * rng.uniform(80, 2000) * seg / SR)) * 0.5
        elif kind < 0.8:
            y[i:i + L] = np.round(rng.standard_normal(len(seg)) * 3) / 3 * 0.5
        i += L
    return y * _env(n, 0.001, dur, 1)


def shine(dur=0.9):
    n = int(dur * SR)
    t = np.arange(n) / SR
    y = sum(np.sin(2 * np.pi * f * t + p) * a for f, a, p in ((2637, 0.5, 0), (3520, 0.35, 1), (5274, 0.25, 2), (7040, 0.15, 3)))
    return y * _env(n, 0.004, 0.25) * 0.35


def zap(dur=0.5):
    rng = np.random.default_rng(5)
    n = int(dur * SR)
    noise = rng.standard_normal(n)
    gate = (rng.random(n // 400 + 1) > 0.4).repeat(400)[:n]
    buzz = np.sign(np.sin(2 * np.pi * 110 * np.arange(n) / SR)) * 0.3
    return (noise * gate * 0.6 + buzz) * _env(n, 0.002, dur * 0.6) * 0.8


def tap(dur=0.06):
    n = int(dur * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 120) * 0.6


def type_(dur=0.03):
    n = int(dur * SR)
    rng = np.random.default_rng(6)
    return _lp(rng.standard_normal(n), 5000) * np.exp(-np.arange(n) / SR * 200) * 0.5


def riser(dur=0.8):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 200 * (8 ** (t / dur))
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.3 + whoosh(dur, 200, 8000)[:n] * 0.5
    return y * (t / dur) ** 2


SOUNDS = dict(whoosh=whoosh, swish=swish, hit=hit, pop=pop, glitch=glitch, shine=shine, zap=zap, tap=tap,
              type=type_, riser=riser)
_cache = {}


def get(name):
    if name not in _cache:
        _cache[name] = SOUNDS[name]().astype(np.float32)
    return _cache[name]


def mix(cues, duration, gain=0.5):
    """cues: [(time, name, gain)] → ステレオ float32 (n,2)"""
    n = int(duration * SR) + SR
    out = np.zeros((n, 2), np.float32)
    for i, (t, name, g) in enumerate(cues):
        s = get(name) * g * gain
        i0 = int(t * SR)
        if i0 >= n:
            continue
        L = min(len(s), n - i0)
        pan = 0.5 + 0.2 * np.sin(i * 1.7)
        out[i0:i0 + L, 0] += s[:L] * (1 - pan) * 1.4
        out[i0:i0 + L, 1] += s[:L] * pan * 1.4
    out = np.tanh(out * 1.2) / np.tanh(1.2)
    return out[:int(duration * SR)]


def write_wav(path, stereo):
    data = (np.clip(stereo, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
