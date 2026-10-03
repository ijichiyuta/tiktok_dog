"""費用の台帳（data/costs.csv）。月の予算（config/channel.yaml の budget）を超えそうなら止める。"""
from __future__ import annotations

import csv
from datetime import datetime

from .config import DATA, cfg, yen

FILE = DATA / "costs.csv"
FIELDS = ["at", "episode", "kind", "usd", "jpy"]


def record(episode: str, kind: str, usd: float) -> None:
    DATA.mkdir(exist_ok=True)
    new = not FILE.exists()
    with FILE.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        if new:
            w.writeheader()
        w.writerow({"at": datetime.now().isoformat(timespec="seconds"), "episode": episode,
                    "kind": kind, "usd": f"{usd:.5f}", "jpy": f"{yen(usd):.2f}"})


def rows() -> list[dict]:
    if not FILE.exists():
        return []
    with FILE.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def month_jpy(ym: str | None = None) -> float:
    ym = ym or datetime.now().strftime("%Y-%m")
    return sum(float(r["jpy"]) for r in rows() if r["at"].startswith(ym))


def episode_jpy(episode: str) -> float:
    return sum(float(r["jpy"]) for r in rows() if r["episode"] == episode)


def guard(estimate_jpy: float) -> None:
    """今月の実績＋これから使う見込みが月の予算を超えるなら止める。"""
    B = cfg("channel")["budget"]
    used = month_jpy()
    if used + estimate_jpy > B["monthly_jpy"]:
        raise SystemExit(f"停止: 今月の費用が予算を超えます（使用済み {used:.0f}円 + 見込み {estimate_jpy:.0f}円 > "
                         f"{B['monthly_jpy']}円）。config/channel.yaml の budget.monthly_jpy を見直してください")


def report() -> None:
    by: dict[str, dict[str, float]] = {}
    for r in rows():
        ym = r["at"][:7]
        by.setdefault(ym, {}).setdefault(r["kind"], 0.0)
        by[ym][r["kind"]] += float(r["jpy"])
    B = cfg("channel")["budget"]["monthly_jpy"]
    if not by:
        print("まだ費用の記録はありません")
    for ym, kinds in sorted(by.items()):
        tot = sum(kinds.values())
        detail = "  ".join(f"{k} {v:.0f}円" for k, v in sorted(kinds.items()))
        print(f"{ym}: 合計 {tot:.0f}円 / 予算 {B}円（{tot / B:.0%}）  {detail}")
