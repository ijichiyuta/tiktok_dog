"""20枚のスライドから YouTube 用の縦動画（1分超）を作る。

  ./ehon video <ep>

- 1枚の秒数は文字数で決める（読み終わる前にめくれないように）。合計は必ず min_total 秒を超える
- 切り替えはクロスフェード。ゆっくりズーム（kenburns）で静止画っぽさを和らげる
- BGM は assets/bgm/ から選ぶ（ファイル名が「A_」などで始まる曲はそのシリーズ専用）。無ければ無音
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from .config import ROOT, cfg, meta, script, write_json
from .layout import chars


def durations(slides: list[dict]) -> list[float]:
    V = cfg("channel")["video"]
    d = [V["base"] + V["per_char"] * chars(sl["text"]) for sl in slides]
    d[0], d[-1] = V["first_slide"], V["last_slide"]
    total = sum(d) - V["crossfade"] * (len(d) - 1)
    if total < V["min_total"]:
        k = (V["min_total"] - total) / sum(d[1:-1]) + 1
        d = [d[0], *[x * k for x in d[1:-1]], d[-1]]
    return [round(x, 2) for x in d]


def pick_bgm(ep: Path, series: str) -> Path | None:
    V = cfg("channel")["video"]
    files = sorted(p for p in (ROOT / V["bgm_dir"]).glob("*") if p.suffix.lower() in (".mp3", ".m4a", ".wav", ".aac"))
    own = [p for p in files if p.name.startswith(f"{series}_")]
    common = [p for p in files if len(p.name) < 2 or p.name[1] != "_"]
    pool = own or common
    if not pool:
        return None
    return pool[int(hashlib.md5(ep.name.encode()).hexdigest(), 16) % len(pool)]


def run(ep: Path) -> Path:
    s = script(ep)
    V = cfg("channel")["video"]
    L = cfg("channel")["layout"]
    W, H, fps, cf = V["width"], V["height"], V["fps"], V["crossfade"]
    bg = L["background"].lstrip("#")
    # スライド（3:4）を 9:16 の真ん中に置き、上下を紙の色で埋める
    fit = f"scale={W}:-2,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x{bg}"
    slides = [ep / "slides" / f"{sl['n']:02d}.png" for sl in s["slides"]]
    if not all(p.exists() for p in slides):
        raise SystemExit(f"エラー: スライドがありません（./ehon compose {ep.name}）")
    d = durations(s["slides"])
    total = round(sum(d) - cf * (len(d) - 1), 2)
    zoom = V.get("kenburns", 0)

    args = ["ffmpeg", "-y", "-loglevel", "error"]
    for p, t in zip(slides, d):
        args += ["-loop", "1", "-t", str(t), "-i", str(p)]
    bgm = pick_bgm(ep, meta(ep)["idea"]["series"])
    if bgm:
        args += ["-stream_loop", "-1", "-i", str(bgm)]
    else:
        args += ["-f", "lavfi", "-t", str(total), "-i", "anullsrc=r=48000:cl=stereo"]

    f = []
    for i, t in enumerate(d):
        frames = int(t * fps) + 1
        if zoom:
            # 2倍に拡大してから zoompan すると、ズーム中の揺れ（ジッター）が出にくい
            f.append(f"[{i}:v]{fit},scale={W * 2}:{H * 2},zoompan=z='1+{zoom}*on/{frames}':"
                     f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={fps},"
                     f"setsar=1,format=yuv420p[v{i}]")
        else:
            f.append(f"[{i}:v]{fit},fps={fps},setsar=1,format=yuv420p[v{i}]")
    cur, length = "v0", d[0]
    for i in range(1, len(d)):
        nxt = f"x{i}"
        f.append(f"[{cur}][v{i}]xfade=transition=fade:duration={cf}:offset={length - cf:.3f}[{nxt}]")
        cur, length = nxt, length + d[i] - cf
    a = len(d)
    f.append(f"[{a}:a]atrim=0:{total},asetpts=PTS-STARTPTS,afade=t=in:d=1.5,"
             f"afade=t=out:st={total - 3:.2f}:d=3,volume={V['bgm_volume_db']}dB[aout]")
    out = ep / "video.mp4"
    args += ["-filter_complex", ";".join(f), "-map", f"[{cur}]", "-map", "[aout]",
             "-t", str(total), "-r", str(fps), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)]
    subprocess.run(args, check=True)
    m = meta(ep)
    m["video_seconds"] = total
    # 曲の帰属表示が必要なら、曲と同じ名前の .txt に書いておく（例: B_evening.txt）
    credit = bgm.with_suffix(".txt") if bgm else None
    m["bgm_credit"] = credit.read_text(encoding="utf-8").strip() if credit and credit.exists() else ""
    write_json(ep / "meta.json", m)
    print(f"  {ep.name}: 動画 {total:.1f}秒 BGM={bgm.name if bgm else 'なし（無音）'} → {out}")
    return out
