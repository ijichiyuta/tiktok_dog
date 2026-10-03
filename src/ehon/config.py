"""設定ファイルと、エピソードのフォルダの読み書き。"""
from __future__ import annotations

import json
import os
import re
from functools import cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
EPISODES = ROOT / "episodes"
DATA = ROOT / "data"


@cache
def cfg(name: str):
    """config/<name>.yaml を読む（channel / character / series / rules / personas）。"""
    return yaml.safe_load((ROOT / "config" / f"{name}.yaml").read_text(encoding="utf-8"))


def ideas() -> list[dict]:
    return yaml.safe_load((ROOT / "content/ideas.yaml").read_text(encoding="utf-8"))


def load_env_key(name: str, prefix: str = "") -> str:
    """このリポジトリの .env → 環境変数 の順に探す。見つからなければ手順を出して止まる。"""
    p = ROOT / ".env"
    if p.exists():
        m = re.search(rf'^\s*{name}\s*=\s*["\']?([^"\'\s#]+)', p.read_text(encoding="utf-8"), re.M)
        if m and m.group(1).startswith(prefix):
            return m.group(1)
    if (v := os.environ.get(name)) and v.startswith(prefix):
        return v
    raise SystemExit(f"エラー: {name} が見つかりません。{ROOT}/.env に  {name}=...  と書いてください"
                     "（ひな形は .env.example）")


# ---- エピソード ---------------------------------------------------------------
# episodes/<YYYY-MM-DD>_<アイデアID>/
#   meta.json    日付・アイデア・状態（planned → scripted → illustrated → composed → approved → shipped）
#   script.json  台本（20枚の文・絵の指示・キャプション）
#   images/      生成したイラスト（NN.png）と、そのメタ（NN.json）
#   slides/      文字を合成した完成スライド（NN.png）
#   video.mp4    YouTube 版
#   cost.json    費用ログ

STATES = ["planned", "scripted", "illustrated", "composed", "approved", "shipped"]


def ep_dir(key: str) -> Path:
    """日付・ID・フォルダ名の一部のどれでも引けるようにする（例: 2026-10-01 / B01）。"""
    if (EPISODES / key).is_dir():
        return EPISODES / key
    hits = sorted(p for p in EPISODES.glob("*") if p.is_dir() and key in p.name)
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise SystemExit(f"エラー: エピソード「{key}」が見つかりません（./ehon status で一覧）")
    raise SystemExit(f"エラー: 「{key}」に当てはまるものが複数あります: " + ", ".join(h.name for h in hits))


def all_episodes() -> list[Path]:
    return sorted(p for p in EPISODES.glob("*") if (p / "meta.json").exists())


def read_json(p: Path, default=None):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def write_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def meta(ep: Path) -> dict:
    return read_json(ep / "meta.json", {})


def set_state(ep: Path, state: str) -> None:
    m = meta(ep)
    # 後戻り（作り直し）も記録する。先に進んだ状態を勝手に巻き戻さないのは呼び出し側の責任
    m["state"] = state
    write_json(ep / "meta.json", m)


def script(ep: Path) -> dict:
    s = read_json(ep / "script.json")
    if not s:
        raise SystemExit(f"エラー: {ep.name} にはまだ台本がありません（./ehon script {ep.name}）")
    return s


def yen(usd: float) -> float:
    return usd * cfg("channel")["budget"]["usd_jpy"]
