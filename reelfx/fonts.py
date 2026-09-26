"""フォント管理。assets/fonts に無ければ Google Fonts リポジトリ (OFL) から自動取得する。"""
from __future__ import annotations

import os
import urllib.request
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

FONT_DIR = Path(os.environ.get("REELFX_FONT_DIR", Path(__file__).resolve().parent.parent / "assets" / "fonts"))
_BASE = "https://raw.githubusercontent.com/google/fonts/main/ofl/"

# name: (file, url_path, variable-weight or None)
FONTS = {
    # 太明朝: 見出し・強調 (今日 / おすすめ / 理解すべき / 優先ユーザー)
    "mincho": ("ZenOldMincho-Black.ttf", "zenoldmincho/ZenOldMincho-Black.ttf", None),
    # 極太ゴシック: 通常テロップ・ラベル
    "gothic": ("NotoSansJP-VF.ttf", "notosansjp/NotoSansJP%5Bwght%5D.ttf", 900),
    "gothic_bold": ("NotoSansJP-VF.ttf", "notosansjp/NotoSansJP%5Bwght%5D.ttf", 700),
    "gothic_medium": ("NotoSansJP-VF.ttf", "notosansjp/NotoSansJP%5Bwght%5D.ttf", 500),
    # ポップ極太: 数字・インパクト
    "dela": ("DelaGothicOne-Regular.ttf", "delagothicone/DelaGothicOne-Regular.ttf", None),
}


def ensure_font(name: str) -> Path:
    file, url, _ = FONTS[name]
    p = FONT_DIR / file
    if not p.exists():
        FONT_DIR.mkdir(parents=True, exist_ok=True)
        print(f"[reelfx] downloading font {file} ...")
        urllib.request.urlretrieve(_BASE + url, p)
    return p


def ensure_all():
    for n in FONTS:
        ensure_font(n)


@lru_cache(maxsize=512)
def get_font(name: str, size: int) -> ImageFont.FreeTypeFont:
    if name not in FONTS and Path(name).exists():
        return ImageFont.truetype(name, size)
    p = ensure_font(name)
    f = ImageFont.truetype(str(p), max(1, int(size)))
    wght = FONTS[name][2]
    if wght is not None:
        try:
            f.set_variation_by_axes([wght])
        except Exception:
            pass
    return f
