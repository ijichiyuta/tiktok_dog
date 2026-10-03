"""数字の記録と振り返り。「刺さった場面」をネタ帳に戻すループの入口。

  ./ehon metrics <ep> tiktok views=3200 likes=410 saves=38 shares=6 comments=2
  ./ehon metrics <ep> youtube views=900 likes=40 comments=1
  ./ehon followers tiktok 1234
  ./ehon report

保存率は分母を2つ持つ（decisions.md #8）:
  保存/再生 … KPI（型の検証期は3%以上）  保存/いいね … 参考投稿の6.3%と比べる用
"""
from __future__ import annotations

import csv
from datetime import datetime

from .config import DATA, all_episodes, meta, read_json

FILE = DATA / "metrics.csv"
FOLLOW = DATA / "followers.csv"
KEYS = ["views", "likes", "saves", "shares", "comments", "completion"]


def _append(path, fields, row) -> None:
    DATA.mkdir(exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fields)
        if new:
            w.writeheader()
        w.writerow(row)


def _read(path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def add(episode: str, platform: str, pairs: list[str]) -> None:
    row = {"at": datetime.now().isoformat(timespec="seconds"), "episode": episode, "platform": platform}
    for p in pairs:
        k, _, v = p.partition("=")
        if k not in KEYS:
            raise SystemExit(f"エラー: 知らない項目 {k}（使えるのは {KEYS}）")
        row[k] = v
    _append(FILE, ["at", "episode", "platform", *KEYS], row)
    print("記録しました")


def add_followers(platform: str, n: int) -> None:
    _append(FOLLOW, ["at", "platform", "followers"],
            {"at": datetime.now().isoformat(timespec="seconds"), "platform": platform, "followers": n})


def latest_followers(platform: str = "tiktok") -> int:
    rows = [r for r in _read(FOLLOW) if r["platform"] == platform]
    return int(rows[-1]["followers"]) if rows else 0


def _num(r: dict, k: str) -> float:
    try:
        return float(r.get(k) or 0)
    except ValueError:
        return 0.0


def report(platform: str = "tiktok") -> None:
    latest: dict[str, dict] = {}
    for r in _read(FILE):
        if r["platform"] == platform:
            latest[r["episode"]] = r          # 同じ回は最後の記録を使う
    if not latest:
        print(f"{platform} の記録はまだありません（./ehon metrics <ep> {platform} views=... likes=... saves=...）")
        return
    rows = []
    for ep in all_episodes():
        r = latest.get(ep.name)
        if not r:
            continue
        m, s = meta(ep), read_json(ep / "script.json", {})
        v, lk, sv, sh = (_num(r, k) for k in ("views", "likes", "saves", "shares"))
        rows.append({
            "ep": ep.name, "series": m["idea"]["series"], "title": s.get("title", m["idea"]["title"]),
            "views": v, "save_view": sv / v if v else 0, "save_like": sv / lk if lk else 0,
            "share_view": sh / v if v else 0,
        })
    rows.sort(key=lambda x: x["save_view"], reverse=True)
    print(f"{'回':<22}{'系':<3}{'再生':>8}{'保存/再生':>10}{'保存/いいね':>11}{'シェア/再生':>11}  タイトル")
    for x in rows:
        print(f"{x['ep']:<22}{x['series']:<3}{x['views']:>8.0f}{x['save_view']:>10.1%}{x['save_like']:>11.1%}"
              f"{x['share_view']:>11.1%}  {x['title']}")
    print("\nシリーズ別の平均（保存/再生）")
    by: dict[str, list[float]] = {}
    for x in rows:
        by.setdefault(x["series"], []).append(x["save_view"])
    for k, vs in sorted(by.items()):
        print(f"  {k}: {sum(vs) / len(vs):.1%}（{len(vs)}本）")
    print(f"\nフォロワー: TikTok {latest_followers('tiktok')} / YouTube {latest_followers('youtube')}")
