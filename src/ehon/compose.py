"""文字とイラストを合成して、1080×1920 のスライドを20枚作る。

  ./ehon compose <ep>                 slides/01.png〜20.png
  ./ehon compose <ep> --placeholder   イラストが無くても仮の絵で通す（レイアウト確認用）

レイアウトの数値は config/channel.yaml の layout。設計書の仕様（背景 #F2F1EE、文字 #333、
強調1枚だけ #C0392B、文字は上部 Y=500〜900、イラストは下部中央）に合わせてある。
"""
from __future__ import annotations

import random
from functools import cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from .config import cfg, meta, script, set_state
from .layout import break_lines, font


def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


@cache
def paper() -> Image.Image:
    """紙の地。うっすら粒子を乗せる（毎回同じ乱数で、全コマ同じ紙に見えるように）。"""
    L = cfg("channel")["layout"]
    W, H = L["width"], L["height"]
    bg = Image.new("RGB", (W, H), hex_rgb(L["background"]))
    if L["paper_grain"] <= 0:
        return bg
    rnd = random.Random(7)
    small = Image.new("L", (W // 3, H // 3))
    small.putdata([128 + int(rnd.gauss(0, 40)) for _ in range(small.width * small.height)])
    grain = small.resize((W, H), Image.Resampling.BICUBIC).filter(ImageFilter.GaussianBlur(0.8))
    k = L["paper_grain"]          # 粒子の強さ（標準偏差 40 × k 階調）
    chans = [grain.point(lambda v, c=c: max(0, min(255, round(c + (v - 128) * k)))) for c in hex_rgb(L["background"])]
    return Image.merge("RGB", chans)


def match_paper(img: Image.Image) -> Image.Image:
    """イラストの紙の色（縁の中央値）を背景色にそろえる。ずれていると四角い色むらが見える。"""
    w, h = img.size
    pts = [img.getpixel((x, y)) for x in range(4, w, max(1, w // 40)) for y in (3, h - 4)] + \
          [img.getpixel((x, y)) for y in range(4, h, max(1, h // 40)) for x in (3, w - 4)]
    target = hex_rgb(cfg("channel")["layout"]["background"])
    delta = [target[i] - sorted(p[i] for p in pts)[len(pts) // 2] for i in range(3)]
    return Image.merge("RGB", [ch.point(lambda v, d=d: max(0, min(255, v + d))) for ch, d in zip(img.split(), delta)])


def feathered(img: Image.Image, width: int, feather: int) -> tuple[Image.Image, Image.Image]:
    """イラストを幅に合わせて縮め、縁をぼかすマスクを作る（紙になじませる）。"""
    h = round(img.height * width / img.width)
    img = img.resize((width, h), Image.Resampling.LANCZOS)
    img = match_paper(img)
    mask = Image.new("L", (width, h), 0)
    ImageDraw.Draw(mask).rectangle([feather, feather, width - feather, h - feather], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(feather / 2))
    return img, mask


def placeholder(sl: dict) -> Image.Image:
    im = Image.new("RGB", (1536, 1024), (236, 230, 220))
    d = ImageDraw.Draw(im)
    d.ellipse([618, 362, 918, 662], outline=(190, 170, 150), width=6)
    d.text((80, 900), f"{sl['n']:02d} {sl['shot'][:70]}", fill=(150, 140, 130), font=font(34))
    return im


def cover_label(im: Image.Image, series: str, no: int | None = None) -> None:
    """1枚目＝絵本の表紙。本のタイトルのように、アカウント名とシリーズ名を小さく載せる。"""
    L = cfg("channel")["layout"]
    W = L["width"]
    d = ImageDraw.Draw(im)
    title = cfg("channel")["name"].split("｜")[0] or "絵本"
    sub = cfg("series")["series"][series]["name"]
    mute = (138, 124, 108)
    top = L["text_center_y"] - 230          # フックの文の上に置く
    d.text((W // 2, top), title, font=font(46), fill=mute, anchor="mm")
    w = font(46).getlength(title)
    d.line([(W // 2 - w / 2, top + 46), (W // 2 + w / 2, top + 46)], fill=(200, 188, 172), width=2)
    label = f"― {sub}・第{no}話 ―" if no else f"― {sub} ―"
    d.text((W // 2, top + 90), label, font=font(34), fill=mute, anchor="mm")


def teaser(im: Image.Image, nxt: dict) -> None:
    """最後の1枚に次回予告を小さく入れる（フォローしておく理由を作る・2026-09-29）。"""
    L = cfg("channel")["layout"]
    W = L["width"]
    d = ImageDraw.Draw(im)
    mute = (138, 124, 108)
    y = L["image_top"] + round(L["image_width"] * 2 / 3) + 40
    d.text((W // 2, y), f"つぎのお話　{nxt['when']}", font=font(32), fill=mute, anchor="mm")
    d.text((W // 2, y + 50), f"「{nxt['title']}」", font=font(36), fill=mute, anchor="mm")


def render(sl: dict, illus: Image.Image | None, series: str = "B", ctx: dict | None = None) -> Image.Image:
    ctx = ctx or {}
    L = cfg("channel")["layout"]
    W = L["width"]
    im = paper().copy()
    if illus is not None:
        pic, mask = feathered(illus, L["image_width"], L["feather"])
        im.paste(pic, ((W - pic.width) // 2, L["image_top"]), mask)
    if sl["n"] == 1:
        cover_label(im, series, ctx.get("no"))
    if sl["n"] == 20 and ctx.get("next"):
        teaser(im, ctx["next"])
    size = L["hook_font_size"] if sl["n"] == 1 else L["font_size"]
    lines = break_lines(sl["text"], size) or break_lines(sl["text"], size, 3) or [sl["text"]]
    f = font(size)
    lh = round(size * L["line_spacing"])
    y = L["text_center_y"] - lh * len(lines) // 2
    color = hex_rgb(L["emphasis"] if sl.get("emphasis") else L["ink"])
    d = ImageDraw.Draw(im)
    for ln in lines:
        d.text((W // 2, y + lh // 2), ln, font=f, fill=color, anchor="mm")
        y += lh
    return im


def run(ep: Path, use_placeholder: bool = False) -> list[Path]:
    s = script(ep)
    src = {sl["n"]: (sl.get("reuse") or sl["n"]) for sl in s["slides"]}
    out = ep / "slides"
    out.mkdir(exist_ok=True)
    missing = [n for n in src.values() if not (ep / "images" / f"{n:02d}.png").exists()]
    if missing and not use_placeholder:
        raise SystemExit(f"エラー: イラストが足りません {sorted(set(missing))}（./ehon images {ep.name}。"
                         "レイアウトだけ見るなら --placeholder）")
    from .schedule import info
    ctx = info(ep)
    files = []
    for sl in s["slides"]:
        p = ep / "images" / f"{src[sl['n']]:02d}.png"
        illus = Image.open(p).convert("RGB") if p.exists() else placeholder(sl)
        dst = out / f"{sl['n']:02d}.png"
        render(sl, illus, meta(ep)["idea"]["series"], ctx).save(dst, optimize=True)
        files.append(dst)
    if not missing and meta(ep).get("state") in ("illustrated", "composed"):
        set_state(ep, "composed")
    print(f"  {ep.name}: スライド{len(files)}枚 → {out}")
    return files
