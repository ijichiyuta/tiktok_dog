"""スマホに送る（TikTok は手動投稿。本人決定 2026-09-25 の方式 a）。

  ./ehon export <ep>

iCloud Drive の ehon フォルダに「日付_タイトル/」を作り、JPEG 20枚・キャプション・投稿メモを置く。
iPhone:「ファイル」アプリ → そのフォルダ → 20枚を選択 → 共有 →「画像を保存」→ TikTok のフォトモードで選ぶ。
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
import shutil
from pathlib import Path

from PIL import Image

from .config import cfg, meta, script


def caption_text(s: dict) -> str:
    tags = " ".join("#" + t for t in s["hashtags"])
    # フォローする理由をはっきり書く（2026-09-29）
    return f"{s['caption'].strip()}\n\n毎日 朝7時・昼12時・夜21時に、この子の絵本を1話ずつ。\n\n{tags}"


def checklist(s: dict, m: dict) -> str:
    S = cfg("series")["series"][m["idea"]["series"]]
    return "\n".join([
        f"投稿日: {m['date']} {m.get('slot', cfg('channel')['post_time'])}",
        f"シリーズ: {S['name']}（BGMはこのシリーズの固定曲）",
        "",
        "□ 20枚を順番どおりに選んだ（01→20）",
        "□ 公開範囲が「誰でも」になっている（TikTok Studio から投稿すると「自分のみ」になることがある）",
        "□ 「AI生成コンテンツ」のラベルをオン（その他の設定 → AI生成コンテンツ）",
        "□ BGM: アプリ内の商用利用可のピアノ曲。音量は小さめ",
        "□ キャプションを caption.txt から貼った",
        "□ 位置情報はオフ",
        "□ 投稿後、./ehon metrics で2日後の数字を記録",
    ])


def run(ep: Path) -> Path:
    s = script(ep)
    m = meta(ep)
    if m.get("state") not in ("approved", "shipped"):
        raise SystemExit(f"エラー: {ep.name} はまだ承認されていません（確認して ./ehon approve {ep.name}）")
    base = Path(cfg("channel")["export"]["dir"]).expanduser()
    safe = re.sub(r'[\\/:*?"<>|]', "", s["title"])[:30]
    out = base / f"{m['date']}_{safe}"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    # 写真アプリは「撮影日時」の新しい順に並ぶ。01 がいちばん新しくなるよう1分ずつずらして書き込む。
    # → iPhone で20枚を一括保存しても、写真アプリと TikTok の選択画面で 01,02,…,20 の順に並ぶ
    base_t = datetime.now()
    for sl in s["slides"]:
        im = Image.open(ep / "slides" / f"{sl['n']:02d}.png").convert("RGB")
        stamp = (base_t - timedelta(minutes=sl["n"])).strftime("%Y:%m:%d %H:%M:%S")
        exif = im.getexif()
        exif[306] = stamp                              # DateTime
        exif.get_ifd(0x8769)[36867] = stamp            # DateTimeOriginal（写真アプリの並び順に使われる）
        exif.get_ifd(0x8769)[36868] = stamp            # DateTimeDigitized
        im.save(out / f"{sl['n']:02d}.jpg", quality=92, optimize=True, exif=exif)
    (out / "caption.txt").write_text(caption_text(s), encoding="utf-8")
    (out / "投稿メモ.txt").write_text(checklist(s, m), encoding="utf-8")
    # スマホ用: 20枚＋キャプションを1つの ZIP に（ファイルApp で開くとフォルダに展開され、一括で写真に保存できる）
    import zipfile
    zp = base / f"{m['date']}_{safe}.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_STORED) as z:
        for f in sorted(out.iterdir()):
            z.write(f, f"{m['date']}_{safe}/{f.name}")
    print(f"  ZIP: {zp}")
    print(f"  書き出し: {out}")
    return out
