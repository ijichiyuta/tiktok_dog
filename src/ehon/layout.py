"""日本語の改行。BudouX で文節に切り、2行以内で左右のバランスがいちばん良い位置で折る。"""
from __future__ import annotations

from functools import cache

import budoux
from PIL import ImageFont

from .config import ROOT, cfg

_parser = budoux.load_default_japanese_parser()
MARGIN = 64   # 左右の余白(px)。30字=15字×2行が 60px で収まる幅


@cache
def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(ROOT / cfg("channel")["layout"]["font"]), size)


def width(text: str, size: int) -> float:
    return font(size).getlength(text)


def chars(text: str) -> int:
    """文字数（空白と改行は数えない）。"""
    return len("".join(text.split()))


def break_lines(text: str, size: int, max_lines: int = 2) -> list[str] | None:
    """収まる折り方を返す。max_lines 行に収まらなければ None。
    本文に「\\n」があればそこで折る（台本側で意図した改行を優先する）。"""
    L = cfg("channel")["layout"]
    avail = L["width"] - MARGIN * 2
    if "\n" in text:
        lines = [s.strip() for s in text.split("\n") if s.strip()]
        ok = len(lines) <= max_lines and all(width(s, size) <= avail for s in lines)
        return lines if ok else None
    if width(text, size) <= avail:
        return [text]
    phrases = _parser.parse(text)
    best = None
    for i in range(1, len(phrases)):
        a, b = "".join(phrases[:i]), "".join(phrases[i:])
        wa, wb = width(a, size), width(b, size)
        if wa <= avail and wb <= avail:
            score = abs(wa - wb) + (40 if wb > wa * 1.6 else 0)   # 2行目だけ極端に長いのは避ける
            if a[-1] in "、。」！？":
                score -= 600      # 読点の後で折るのを最優先（「面倒な／日ほど」のような泣き別れを防ぐ）
            if best is None or score < best[0]:
                best = (score, [a, b])
    if best or max_lines < 3:
        return best[1] if best else None
    return None
