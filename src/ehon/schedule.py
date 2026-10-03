"""投稿の順番（話数）と次回予告。1日3枠: 朝7時・昼12時・夜21時（2026-09-29 本人決定）。

話数は投稿順の通し番号。meta.json の date と slot で並べる（slot が無い古い回は 21:00 扱い）。
"""
from __future__ import annotations

from datetime import date as Date
from pathlib import Path

from .config import all_episodes, meta, read_json

SLOTS = {"07:00": "朝7時", "12:00": "昼12時", "21:00": "夜21時"}


def key(ep: Path) -> tuple[str, str]:
    m = meta(ep)
    return m["date"], m.get("slot", "21:00")


def ordered() -> list[Path]:
    return sorted(all_episodes(), key=key)


def title(ep: Path) -> str:
    s = read_json(ep / "script.json", {})
    return s.get("title") or meta(ep)["idea"]["title"]


def info(ep: Path) -> dict:
    eps = ordered()
    i = [e.name for e in eps].index(ep.name)
    out = {"no": i + 1, "next": None}
    if i + 1 < len(eps):
        nx = eps[i + 1]
        d, slot = key(nx)
        dd = Date.fromisoformat(d)
        out["next"] = {"when": f"{dd.month}月{dd.day}日 {SLOTS.get(slot, slot)}", "title": title(nx)}
    return out
