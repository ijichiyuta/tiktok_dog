"""投稿予定を立てる。曜日の枠（config/series.yaml の weekly）に、ネタ帳から未使用のネタを割り当てる。

  ./ehon plan --start 2026-10-01 --days 7
"""
from __future__ import annotations

from datetime import date, timedelta

from .config import EPISODES, all_episodes, cfg, ideas, meta, write_json


def used_ids() -> set[str]:
    return {meta(ep)["idea"]["id"] for ep in all_episodes()}


def followers() -> int:
    from .metrics import latest_followers
    return latest_followers()


def in_season(idea: dict, day: date) -> bool:
    """months があるネタはその月だけ（季節回に限らない。例: はじめての雪）。E は months 必須。"""
    if "months" in idea:
        return day.month in idea["months"]
    return idea["series"] != "E"


def pick(day: date, used: set[str]) -> dict | None:
    S = cfg("series")
    pool = [i for i in ideas() if i["id"] not in used]
    for series in S["weekly"][day.weekday()]:
        need = S["series"][series].get("enabled_from_followers")
        if need and followers() < need:
            continue
        for i in pool:
            if i["series"] != series:
                continue
            if not in_season(i, day):
                continue
            return i
    # 枠に合うネタが尽きたら、B → C → A の順で残りから
    for series in ("B", "C", "A"):
        for i in pool:
            if i["series"] == series and in_season(i, day):
                return i
    return None


def run(start: date, days: int) -> None:
    used = used_ids()
    taken = {meta(ep)["date"] for ep in all_episodes()}
    for k in range(days):
        day = start + timedelta(days=k)
        if day.isoformat() in taken:
            print(f"  {day} は予定済み")
            continue
        idea = pick(day, used)
        if not idea:
            print(f"  {day}: ネタ帳が尽きました（content/ideas.yaml に追加してください）")
            break
        used.add(idea["id"])
        ep = EPISODES / f"{day.isoformat()}_{idea['id']}"
        write_json(ep / "meta.json", {"date": day.isoformat(), "idea": idea, "state": "planned"})
        wd = "月火水木金土日"[day.weekday()]
        print(f"  {day}({wd}) {idea['series']} {idea['id']} {idea['title']}")
