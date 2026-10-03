"""イラストを生成する（OpenAI gpt-image）。nariagari の実装と実測値を土台にしている。

  ./ehon images <ep>               足りないコマだけ生成
  ./ehon images <ep> --only 3,7    指定したコマだけ作り直す
  ./ehon images --check            キーとモデルの疎通だけ確認

- 犬が描かれるコマは、その年齢の設定画（assets/ref/dog_<age>.png）を参照画像として添付する
- 犬がいないコマには参照を付けない（付けると、いない犬が出てくる — nariagari の教訓）
- 同じ指示なら再生成しない（指示と参照画像のハッシュでキャッシュ）
- 1枚ごとに API の usage から実費を計算して記録。月の予算を超えそうなら止まる
"""
from __future__ import annotations

import base64
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

from . import costs
from .config import ROOT, cfg, load_env_key, meta, read_json, script, set_state, write_json, yen

GEN = "https://api.openai.com/v1/images/generations"
EDIT = "https://api.openai.com/v1/images/edits"
# $/1M tokens（2026-09-25 公式の料金ページで確認。docs/research-2026-09-25.md）
RATE = {"text_in": 5.0, "image_in": 8.0, "image_out": 30.0}
# 見積もり用の1枚あたり（円）。nariagari の実測（2026-09-19）
EST = {0: 2.5, 1: 4.3, 2: 6.2}

# 設定画を添付するときに必ず添える指示。これがないと設定画の背景や3体並びまでコピーされる
REF_NOTE = ("The attached image is a character model sheet. Use it ONLY for the dog's identity "
            "(face, fur color, ears, body proportions, light-blue collar). Do not copy its layout, "
            "do not draw the dog three times, and do not copy the plain background. "
            "Draw a single new scene as described below.")


def usd_from_usage(u: dict) -> float:
    d = u.get("input_tokens_details", {})
    ti, ii = d.get("text_tokens", 0), d.get("image_tokens", 0)
    io = u.get("output_tokens_details", {}).get("image_tokens", u.get("output_tokens", 0))
    return (ti * RATE["text_in"] + ii * RATE["image_in"] + io * RATE["image_out"]) / 1e6


def ref_path(age: str) -> Path:
    return ROOT / "assets/ref" / f"dog_{age}.png"


def build_prompt(sl: dict, ep_meta: dict) -> tuple[str, list[Path]]:
    C = cfg("character")
    idea = ep_meta["idea"]
    parts = [C["style"]]
    refs: list[Path] = []
    if sl.get("dog"):
        age = sl.get("dog_age") or idea.get("dog_age", "adult")
        parts += [C["dog"]["common"], C["dog"]["ages"][age]]
        if ref_path(age).exists():
            refs = [ref_path(age)]
            parts.insert(0, REF_NOTE)
    else:
        parts.append("There is no dog in this picture.")
    people = sl.get("humans") or []
    if people:
        parts.append(C["humans"]["rule"])
        parts += [C["humans"][p] for p in people]
    else:
        parts.append("No people in this picture.")
    if C.get("props"):
        parts.append(C["props"])
    if sl.get("act") == "farewell":
        # 別れの予感のコマで窓の映り込みに2匹目の犬が出た（2026-09-27）→ 死を連想させるので強く禁止
        parts.append("The mood is calm and warm, not sad. Nothing that suggests death, ghosts, angels, light beams or halos.")
    parts.append(f"Scene: {sl['scene']}")
    parts.append(f"Framing: {sl['shot']}. Landscape 3:2. Keep the subject in the central area "
                 "with generous empty paper around it.")
    return "\n".join(parts), refs


def generate(key: str, prompt: str, refs: list[Path], tries: int = 5) -> tuple[bytes, dict]:
    I = cfg("channel")["image"]
    last = ""
    for attempt in range(tries):
        fhs = []
        try:
            if refs:
                fhs = [p.open("rb") for p in refs]
                r = requests.post(EDIT, headers={"Authorization": f"Bearer {key}"},
                                  files=[("image[]", (p.name, f, "image/png")) for p, f in zip(refs, fhs)],
                                  data={"model": I["model"], "prompt": prompt, "size": I["size"],
                                        "quality": I["quality"], "n": "1"}, timeout=600)
            else:
                r = requests.post(GEN, headers={"Authorization": f"Bearer {key}"},
                                  json={"model": I["model"], "prompt": prompt, "size": I["size"],
                                        "quality": I["quality"], "n": 1}, timeout=300)
            if r.status_code == 200:
                j = r.json()
                d = j["data"][0]
                raw = base64.b64decode(d["b64_json"]) if "b64_json" in d else requests.get(d["url"], timeout=120).content
                return raw, j.get("usage", {})
            if r.status_code == 429:
                code = (r.json().get("error") or {}).get("code", "") if r.headers.get("content-type", "").startswith("application/json") else ""
                # 残高切れの429は間欠的に出ることがある（nariagari 2026-09-21 実測）。長めに待って粘る
                wait = 45 if code in ("insufficient_quota", "credit_balance_exhausted") else \
                    float(r.headers.get("retry-after", 0)) or 20 * (attempt + 1)
                last = f"HTTP 429 {code}"
                time.sleep(wait)
                continue
            last = f"HTTP {r.status_code}: {r.text[:300]}"
            if r.status_code in (400, 401, 403, 404):
                break
        except requests.RequestException as e:
            last = f"{type(e).__name__}: {e}"
        finally:
            for f in fhs:
                f.close()
        time.sleep(3 * 2 ** attempt)
    raise RuntimeError(last or "不明なエラー")


def digest(prompt: str, refs: list[Path]) -> str:
    I = cfg("channel")["image"]
    h = hashlib.sha256(f"{I['model']}|{I['size']}|{I['quality']}|{prompt}".encode())
    for p in refs:
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def run(ep: Path, only: list[int] | None = None, force: bool = False) -> None:
    s = script(ep)
    m = meta(ep)
    if s.get("_check", {}).get("errors"):
        raise SystemExit(f"エラー: {ep.name} の台本にチェックエラーが残っています（./ehon check {ep.name}）")
    out = ep / "images"
    out.mkdir(exist_ok=True)
    jobs = []
    missing_ref = set()
    for sl in s["slides"]:
        if sl.get("reuse"):
            continue
        n = sl["n"]
        if only and n not in only:
            continue
        prompt, refs = build_prompt(sl, m)
        if sl.get("dog") and not refs:
            missing_ref.add(sl.get("dog_age") or m["idea"].get("dog_age", "adult"))
        h = digest(prompt, refs)
        prev = read_json(out / f"{n:02d}.json", {})
        if not force and not only and prev.get("hash") == h and (out / f"{n:02d}.png").exists():
            continue
        jobs.append((n, prompt, refs, h))
    if missing_ref:
        print(f"  ⚠ 設定画がありません: {sorted(missing_ref)} → キャラがブレます。先に ./ehon refsheet を通してください")
    if not jobs:
        print(f"  {ep.name}: 生成するコマはありません")
    else:
        est = sum(EST[min(len(j[2]), 2)] for j in jobs)
        costs.guard(est)
        cap = cfg("channel")["budget"]["episode_jpy"]
        if costs.episode_jpy(ep.name) + est > cap:
            raise SystemExit(f"停止: この回の費用が上限 {cap}円 を超えます（見込み {est:.0f}円）")
        print(f"  {ep.name}: {len(jobs)}コマ生成（見込み {est:.0f}円）")
        key = load_env_key("OPENAI_API_KEY", "sk-")

        def work(job):
            n, prompt, refs, h = job
            t = time.time()
            raw, usage = generate(key, prompt, refs)
            usd = usd_from_usage(usage)
            Image.open(BytesIO(raw)).convert("RGB").save(out / f"{n:02d}.png")
            write_json(out / f"{n:02d}.json", {"hash": h, "prompt": prompt, "refs": [p.name for p in refs],
                                               "usage": usage, "usd": usd})
            costs.record(ep.name, "image", usd)
            print(f"    ✓ {n:02d} {'参照' + str(len(refs)) if refs else '参照なし'} {yen(usd):.1f}円 {time.time() - t:.0f}秒")

        fails = []
        with ThreadPoolExecutor(cfg("channel")["image"]["workers"]) as ex:
            for job, fut in [(j, ex.submit(work, j)) for j in jobs]:
                try:
                    fut.result()
                except Exception as e:     # 1コマの失敗で全体を止めない。最後にまとめて出す
                    fails.append((job[0], str(e)))
        for n, e in fails:
            print(f"    ✗ {n:02d} {e}")
        print(f"  この回の累計 {costs.episode_jpy(ep.name):.0f}円 / 今月 {costs.month_jpy():.0f}円")
        if fails:
            raise SystemExit(f"{len(fails)}コマ失敗しました。もう一度 ./ehon images {ep.name} で続きから再開できます")
    need = [sl["n"] for sl in s["slides"] if not sl.get("reuse")]
    if all((out / f"{n:02d}.png").exists() for n in need) and m.get("state") in ("scripted", "illustrated"):
        set_state(ep, "illustrated")


def accept(ep: Path) -> None:
    """今ある絵を「この指示で作ったもの」として登録し直す。設定の文言を変えたあと、
    問題のない絵まで作り直されないようにする（ハッシュだけ更新する）。"""
    s, m = script(ep), meta(ep)
    n = 0
    for sl in s["slides"]:
        j = ep / "images" / f"{sl['n']:02d}.json"
        if sl.get("reuse") or not j.exists():
            continue
        prompt, refs = build_prompt(sl, m)
        d = read_json(j)
        d["hash"] = digest(prompt, refs)
        write_json(j, d)
        n += 1
    print(f"  {ep.name}: {n}コマを現状のまま承認")


def check_api() -> None:
    key = load_env_key("OPENAI_API_KEY", "sk-")
    r = requests.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {key}"}, timeout=30)
    if r.status_code != 200:
        raise SystemExit(f"エラー: OpenAI に繋がりません HTTP {r.status_code}: {r.text[:200]}")
    ids = sorted(x["id"] for x in r.json()["data"] if "image" in x["id"])
    print(f"疎通OK。使える画像モデル: {ids}\n設定中: {cfg('channel')['image']['model']}")
