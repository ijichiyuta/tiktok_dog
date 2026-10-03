"""文と絵が合っているかを、画像を読めるモデルで1枚ずつ確かめる。

  ./ehon qa <ep>          全コマを判定して qa.json に保存、合っていないコマを一覧
  ./ehon qa <ep> --fix    合っていないコマの絵の指示を直して作り直し、もう一度判定

2026-09-29 本人の指摘: 「ときどき振り返ると、ちゃんとあなたがいる」なのに、飼い主が犬の前を歩いていた。
文が意味する「位置関係・視線・動き・時間帯・小物」を絵が満たしているかを見る。
"""
from __future__ import annotations

import base64
import json
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

from . import costs
from .config import cfg, load_env_key, meta, read_json, script, write_json, yen

MODEL = "gpt-5-mini"
RATE = (0.25, 2.0)       # $/1M（入力・出力）

PROMPT = """You are checking a picture-book slide. The Japanese sentence is shown on the slide above the illustration.
Judge ONLY whether the illustration depicts what the sentence means. Check carefully:
- spatial relations (who is in front / behind / beside, who is looking at whom, looking back = the other is BEHIND)
- the action and pose described (sitting, lying, running, holding something in the mouth, being hugged ...)
- who is present (the dog, the owner, others) and who must NOT be present
- time of day, weather, place, and key objects the sentence mentions
- the narrator: {narrator}
Ignore drawing style and minor details that the sentence does not imply.
If the sentence is a question or message addressed to the reader (the viewer), the picture only needs to fit its mood; do not require the reader to appear.
Do not fail a picture for left/right placement unless the sentence implies it. Humans never show faces by design; that is fine.

Sentence: {text}
Intended scene (English direction used to draw it): {scene}

First describe what you actually see, in this order:
1. dog_body: which way the dog's BODY points (toward the viewer / away from the viewer / left / right) and which way it is moving.
2. dog_gaze: where the dog's EYES are looking, and WHO or WHAT is actually located in that direction in the picture (it may be nobody).
3. people: where each person is relative to the dog's direction of travel (ahead of the dog = in the direction its body points;
   behind the dog = opposite to where its body points), and which way they face or walk.
Do not confuse depth in the picture with "behind the dog": "behind the dog" means opposite to the dog's direction of travel. Then compare with what the sentence implies. Be strict:
if the sentence implies a relation (e.g. the dog looks back and sees the owner) and the picture shows a different one
(e.g. the owner is walking ahead, away from the dog), it is NOT ok.

Reply in JSON: {{"dog_body": "...", "dog_gaze": "...", "people": "...", "implied": "<English, what the sentence requires>", "ok": true|false, "problem": "<Japanese, one short sentence, empty if ok>", "fix_scene": "<if not ok: a corrected English scene direction that states the spatial relations explicitly and keeps EXACTLY the same characters (people present: {people}); never add a new person; else empty>"}}"""


def b64(p: Path) -> str:
    im = Image.open(p).convert("RGB")
    im.thumbnail((768, 768))
    buf = BytesIO()
    im.save(buf, "JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def judge(key: str, img: Path, text: str, scene: str, narrator: str, people: str = "") -> tuple[dict, float]:
    body = {"model": MODEL, "reasoning_effort": "medium", "response_format": {"type": "json_object"},
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": PROMPT.format(text=text.replace("\n", ""), scene=scene, narrator=narrator, people=people or "none")},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64(img)}", "detail": "high"}}]}]}
    r = requests.post("https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {key}"},
                      json=body, timeout=120)
    r.raise_for_status()
    j = r.json()
    u = j.get("usage", {})
    usd = (u.get("prompt_tokens", 0) * RATE[0] + u.get("completion_tokens", 0) * RATE[1]) / 1e6
    try:
        return json.loads(j["choices"][0]["message"]["content"]), usd
    except (KeyError, json.JSONDecodeError):
        return {"ok": True, "problem": "（判定できず）", "fix_scene": ""}, usd


def run(ep: Path, fix: bool = False, only: list[int] | None = None) -> list[int]:
    s, m = script(ep), meta(ep)
    narrator = "the dog speaks to its owner (ぼく=dog, あなた=owner)" \
        if cfg("series")["series"][m["idea"]["series"]]["narrator"] == "dog" else "the owner speaks (私=owner, この子=dog)"
    key = load_env_key("OPENAI_API_KEY", "sk-")
    res = read_json(ep / "qa.json", {})
    total, bad = 0.0, []
    for sl in s["slides"]:
        n = sl["n"]
        if only and n not in only:
            continue
        img = ep / "images" / f"{(sl.get('reuse') or n):02d}.png"
        if not img.exists():
            continue
        r, usd = judge(key, img, sl["text"], sl["scene"], narrator, ", ".join(sl.get("humans") or []))
        total += usd
        res[str(n)] = r
        if not r.get("ok"):
            bad.append(n)
            print(f"    ✗ {n:02d} {sl['text'].replace(chr(10), '')} → {r.get('problem')}")
    write_json(ep / "qa.json", res)
    costs.record(ep.name, "qa", total)
    print(f"  {ep.name}: 文と絵のずれ {len(bad)}コマ {bad}（判定 {yen(total):.1f}円）")
    if fix and bad:
        for n in bad:
            fs = res[str(n)].get("fix_scene")
            if fs:
                s["slides"][n - 1]["scene"] = fs
        write_json(ep / "script.json", s)
        from .images import run as images
        images(ep, only=bad)
        return run(ep, fix=False, only=bad)
    return bad
