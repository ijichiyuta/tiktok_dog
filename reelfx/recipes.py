"""レシピ: リファレンスの「センス」をそのまま再利用できる高レベル関数群。

各関数は Timeline に要素・FX・効果音をまとめて追加する。YAML 台本 (from_yaml) からも同名で呼べる。
配色ルール (docs/STYLE_GUIDE.md 参照):
    白 = 通常 / 金 = 結論・キーワード / 赤 = 警告・否定 / 紫 = 抽象概念・AI / 銀 = 見出しの補助
"""
from __future__ import annotations

from .anim import (blur_in, combo, drop, fade, flash_in, glitch, pop, rgb_split, shake, shine, slam, slide,
                   streak, stretch, typewriter, wipe, zoom_in)
from .easing import ease_out_cubic
from .elements import Box, Bubble, Phone, ProgressBar, TapHand, Text, kf
from .fx import EnergySlash, Lightning, LensStreak, NeonSwirls, Sparkles
from .timeline import Timeline

CX = 540
TONE = {"white": "white_gothic", "gold": "gold_gothic", "red": "crimson_gothic", "purple": "purple_gothic",
        "silver": "silver_gothic"}


def neon_bg(tl: Timeline, t0=0.0, t1=None, intensity=0.6, seed=7):
    """人物の背後に紫ネオンの渦 (常時)。"""
    tl.add(NeonSwirls(seed=seed, intensity=intensity, n=10, opacity=kf([(0, 0), (0.4, 1)])), t0, t1 or tl.duration)
    tl.fx("vignette", t0, t1 or tl.duration, strength=1.5)


def caption(tl, text, t0, t1, y=1000, tone="white", size=94, enter="pop", x=CX, align="center", sfx="pop"):
    """標準テロップ。 {強調|1|gold_gothic} 記法で部分色替え。"""
    en = dict(pop=pop(), slide=slide(0.25, -320), wipe=wipe(0.25), stretch=stretch(0.25), blur=blur_in(),
              glitch=combo(glitch(0.3), rgb_split(0.3)), type=typewriter(max(0.3, (t1 - t0) * 0.7)))[enter]
    return tl.add(Text(text, size, TONE.get(tone, tone), align=align, at=(x, y), enter=en, exit=fade(0.08)),
                  t0, t1, sfx=sfx if enter != "type" else None)


def headline(tl, text, t0, t1, y=960, style="gold_mincho", size=190, x=CX, skew=0.1, sfx="hit"):
    """見出し: 巨大サイズから叩きつけ + 光沢。"""
    return tl.add(Text(text, size, style, style_kw=dict(skew=skew), at=(x, y), enter=slam(0.22),
                       exit=glitch(0.12), emph=[(0.35, shine(0.45))], drift=0.01), t0, t1, sfx=sfx)


def label(tl, text, t0, t1, at=(CX, 1000), style="gold", size=54, w=680, h=None, enter="streak"):
    """ラベルボックス (金/紫/マゼンタ/黒金)。"""
    en = dict(streak=streak(0.3), wipe=wipe(0.25), pop=pop(0.25, 1.3))[enter]
    return tl.add(Box(text, style, size, w=w, h=h, at=at, enter=en, exit=blur_in(0.15)), t0, t1, sfx="swish")


def stack(tl, items, end, slots=(1085, 1395, 1720), w=800):
    """新しい箱が上に入り、既存の箱が下へ押し出される積み上げ演出。
    items: [(start, text, box_style), ...]"""
    pushes = [it[0] for it in items]
    for k, (t0, txt, st) in enumerate(items):
        pts = [(0, slots[0])]
        for j, tp in enumerate(pushes[k + 1:]):
            if j + 1 >= len(slots):
                break
            pts += [(tp - t0, slots[j]), (tp - t0 + 0.25, slots[j + 1])]
        f = kf(pts, ease_out_cubic)
        h = 150 if "\n" not in txt else 250
        tl.add(Box(txt, st, 62, w=w, h=h, at=(lambda t, f=f: (CX, f(t))), enter=streak(0.3), exit=blur_in(0.15)),
               t0, end, sfx="whoosh")


def warning(tl, text, t0, t1, y=1000, size=120, style="brush_red"):
    """警告・強調 (赤筆文字 + 画面揺れ)。"""
    tl.add(Text(text, size, style, at=(CX, y), enter=slam(0.22, 2.2), exit=glitch(0.12),
                emph=[(0.05, shake(0.3, 16))]), t0, t1, sfx="hit")
    tl.fx("shake", t0 + 0.02, t0 + 0.3, amp=14)


def doom(tl, text, t0, t1, y=1060, size=113):
    """「終わります」系: 巨大から縮む赤文字 + 揺れ + RGBずれ。"""
    tl.add(Text(text, size, "crimson_gothic", at=(CX, y), enter=combo(zoom_in(0.25, 3.2), blur_in(0.25, 18, 1.0)),
                exit=fade(0.1)), t0, t1, sfx="hit")
    tl.fx("shake", t0, t0 + 0.4, amp=20)
    tl.fx("rgb", t0, t0 + 0.3, px=12)


def quote(tl, text, t0, t1, y=1130, size=68, tint="#6d6cff"):
    """引用 (回想): タイプライター + 鉤括弧 + 実写を青紫に。"""
    tl.fx("tint", t0, t1, color=tint, amount=0.75)
    tl.add(Text("「", 82, "white_gothic", at=(95, y - 100), enter=pop(), exit=fade(0.1)), t0, t1)
    tl.add(Text("」", 82, "white_gothic", at=(990, y + 120), enter=pop(), exit=fade(0.1)), t0, t1)
    n = len(text.replace("\n", ""))
    dur = min((t1 - t0) * 0.85, n * 0.1)
    tl.add(Text(text, size, "white_gothic", align="left", at=(CX, y), enter=typewriter(dur), exit=fade(0.1)), t0, t1)
    for i in range(int(dur / 0.11)):
        tl.cue(t0 + i * 0.11, "type", 0.5)


def bubble(tl, text, t0, t1, at=(360, 860), size=54):
    tl.add(Bubble(text, size, at=at, enter=pop(0.3, 0.6), exit=streak(0.25)), t0, t1, sfx="pop")


def vertical_tag(tl, text, t0, t1, at=(975, 1220), size=76):
    """右端の縦書き黒タグ (上から落ちてくる)。"""
    h = int(size * (len(text) + 1.6))
    tl.add(Box(text, "black_tag", size, w=int(size * 2), h=h, vertical=True, at=at, enter=drop(0.3, 700),
               exit=blur_in(0.15)), t0, t1, sfx="whoosh")


def number_hero(tl, num, text, t0, t1, at=(300, 950), size=300):
    """巨大な金の数字 + 横に説明 (「1 アカウント」)。"""
    tl.add(Text(num, size, "gold_mincho", style_kw=dict(skew=0.12), at=at, enter=slam(0.2), exit=blur_in(0.15)),
           t0, t1, sfx="hit")
    tl.add(Text(text, 83, "silver_gothic", style_kw=dict(skew=0.06), align="left",
                at=(at[0] + size * 0.9, at[1] - size * 0.18), enter=slide(0.2, 300), exit=blur_in(0.15)), t0 + 0.05, t1)


def progress(tl, t0, t1, frac=((0, 0.02), (3, 0.6)), y=1600, phone=True):
    """再生維持率バー (+ スマホ)。"""
    if phone:
        tl.add(Phone(170, 320, at=(CX, y - 40), enter=pop(), exit=fade(0.15)), t0, t1)
    tl.add(ProgressBar(800, 40, frac=kf(list(frac)), at=(CX, y), enter=streak(0.3), exit=fade(0.15)), t0, t1)


def cta_follow(tl, text, t0, t1, y=880):
    """フォロー誘導: 金テロップ + タップする指。"""
    tl.add(Text(text, 83, "gold_gothic", at=(CX, y), enter=pop(), exit=fade(0.1)), t0, t1, sfx="pop")
    hy = kf([(0, y + 130), (0.35, y + 210), (0.5, y + 280)], ease_out_cubic)
    tl.add(TapHand(170, tap_at=(0.5, 1.4), at=(lambda t: (580, hy(t))), enter=slide(0.2, 0, 150), exit=fade(0.1)),
           t0, t1)
    tl.cue(t0 + 0.5, "tap")
    tl.cue(t0 + 1.4, "tap")


def transition(tl, t, kind="glitch", dur=0.25):
    """画面全体のトランジション。glitch / smear / flash / zoom / whiteout"""
    if kind == "glitch":
        tl.fx("glitch", t, t + dur, sfx="glitch", amount=1.0)
    elif kind == "smear":
        tl.fx("hsmear", t, t + dur * 1.4, length=280)
        tl.fx("flash", t + 0.05, t + dur, color="#ffc8ee", peak=0.3, sfx="whoosh")
    elif kind == "flash":
        tl.fx("flash", t, t + dur, peak=0.85, sfx="swish")
    elif kind == "zoom":
        tl.fx("zoom", t, t + dur, frm=1.3, to=1.0, sfx="whoosh")
    elif kind == "lightning":
        tl.add(EnergySlash(), t, t + 0.35, sfx="whoosh")
        tl.add(Lightning(branches=4, flash=0.12), t + 0.07, t + 0.45, sfx="zap")
        tl.fx("flash", t + 0.05, t + 0.25, color="#7fe9ff", peak=0.35)


def opening(tl, bg_text, lines, t0=0.0, t1=2.45):
    """OP: 背景の巨大筆文字 + 稲妻 + 見出しの多段落とし + 最後にグリッチ。
    lines: [(start, text, style, size, y), ...]"""
    tl.add(LensStreak(p0=(300, 980), p1=(430, 830)), t0, t0 + 0.3, sfx="swish")
    tl.add(Text(bg_text, 470, "brush_bg", style_kw=dict(line_gap=0.55), at=(575, 1110), opacity=0.92,
                enter=combo(zoom_in(0.25, 1.5), blur_in(0.25, 16)), exit=glitch(0.12), drift=0.02),
           t0 + 0.5, t1, sfx="hit")
    transition(tl, t0 + 0.55, "lightning")
    enters = [glitch(0.3), combo(slide(0.3, 420, 0), flash_in(0.35)), wipe(0.22)]
    for i, (s, txt, st, size, y) in enumerate(lines):
        tl.add(Text(txt, size, st, at=(CX, y), enter=enters[i % len(enters)], exit=glitch(0.12), drift=0.012),
               s, t1, sfx=["glitch", "whoosh", "swish"][i % 3])
    tl.fx("glitch", t1 - 0.2, t1, sfx="glitch", amount=1.2)


# ---------------------------------------------------------------- YAML 台本
RECIPES = dict(caption=caption, headline=headline, label=label, stack=stack, warning=warning, doom=doom,
               quote=quote, bubble=bubble, vertical_tag=vertical_tag, number_hero=number_hero, progress=progress,
               cta_follow=cta_follow, transition=transition, opening=opening, neon_bg=neon_bg)


def from_yaml(path) -> Timeline:
    """YAML 台本 → Timeline。
    duration: 20
    background: neon          # 省略可
    cues:
      - {t: [0.0, 2.4], do: headline, text: "今日"}
      - {t: [2.5, 4.0], do: caption, text: "普通の{強調|1|gold_gothic}テロップ"}
      - {t: 4.0, do: transition, kind: glitch}
    """
    import yaml
    with open(path, encoding="utf-8") as f:
        d = yaml.safe_load(f)
    tl = Timeline(float(d["duration"]))
    if d.get("background", "neon") == "neon":
        neon_bg(tl)
    for c in d.get("cues", []):
        c = dict(c)
        fn = RECIPES[c.pop("do")]
        t = c.pop("t")
        for k in ("at",):
            if k in c and isinstance(c[k], list):
                c[k] = tuple(c[k])
        if "items" in c:
            c["items"] = [tuple(x) for x in c["items"]]
        if "lines" in c:
            c["lines"] = [tuple(x) for x in c["lines"]]
        if isinstance(t, list):
            fn(tl, t0=t[0], t1=t[1], **c) if fn not in (stack,) else fn(tl, end=t[1], **c)
        else:
            fn(tl, t, **c)
    return tl
