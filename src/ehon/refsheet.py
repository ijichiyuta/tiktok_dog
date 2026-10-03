"""設定画（キャラ参照）を作る。全コマの一貫性はここで決まる。

  ./ehon refsheet adult --n 3     成犬の候補を3枚（1枚 約2.5円）
  ./ehon refsheet pick adult 2    2番目を採用 → assets/ref/dog_adult.png
  ./ehon refsheet puppy --n 3     子犬の候補（採用済みの成犬を参照して同じ子として描く）
  ./ehon refsheet senior --n 3    シニアの候補（同上）

順番は 成犬 → 子犬・シニア。成犬を「正」として、年齢だけ変える。
"""
from __future__ import annotations

import shutil
from io import BytesIO

from PIL import Image

from . import costs
from .config import ROOT, cfg, load_env_key, yen
from .images import generate, ref_path, usd_from_usage

CAND = ROOT / "assets/ref/_candidates"


def make(age: str, n: int) -> None:
    C = cfg("character")
    base = ref_path("adult")
    icon = ROOT / "assets/ref/icon_source.png"     # アカウントのアイコン（この子の「正」の顔）
    photos = sorted((ROOT / "assets/ref/maru").glob("*.png"))[:3]   # モデルになった実際の犬の写真（非公開）
    if age == "adult" and photos:
        refs = photos
        note = ["The attached photos show the real dog this character is based on. Capture its identity exactly — "
                "warm caramel-apricot curly fur, teddy-bear trim, round face, round pom-pom ears, eyes and nose, slim legs, "
                "plumed tail — but render it as a soft colored-pencil picture-book illustration, not a photo. "
                "Do not copy the clothes, furniture, bedding or backgrounds. The dog wears only a light-blue collar."]
    elif age == "adult":
        refs = [icon] if icon.exists() else []
        note = ["The attached portrait is the canonical face of this dog (the account icon). "
                "Draw this exact individual dog: same face shape, eye spacing, fur color and curl, ear shape, "
                "light-blue collar and small round silver tag."] if refs else []
    else:
        if not base.exists():
            raise SystemExit("先に成犬の設定画を確定してください（./ehon refsheet adult → pick）")
        refs = [base]
        note = ["The attached sheet shows the SAME dog as an adult. Draw this exact individual dog at a different age, "
                "keeping the face shape, markings, fur color and light-blue collar."]
        if age == "puppy":
            # 成犬を参照すると体つきまで成犬になる（2026-09-27 実測）。赤ちゃんの体型を強く指定する
            note = ["The attached sheet shows this dog as a grown adult. Now draw the SAME dog as a very young baby puppy: "
                    "keep only its fur color (warm caramel-apricot) and light-blue collar, but change the body to clearly baby "
                    "proportions — a chubby round body, very short legs, head as large as the body, tiny muzzle, huge eyes, "
                    "soft fuzzy fur with no trimmed shape. It must obviously look like a baby, not a small adult."]
    prompt = "\n".join([
        *note,
        C["style"], C["dog"]["common"], C["dog"]["ages"][age], C["refsheet"]["prompt"],
    ])
    costs.guard(n * (4.3 if refs else 2.5))
    key = load_env_key("OPENAI_API_KEY", "sk-")
    CAND.mkdir(parents=True, exist_ok=True)
    start = len(list(CAND.glob(f"{age}_*.png"))) + 1
    for i in range(start, start + n):
        raw, usage = generate(key, prompt, refs)
        usd = usd_from_usage(usage)
        Image.open(BytesIO(raw)).convert("RGB").save(CAND / f"{age}_{i}.png")
        costs.record("_refsheet", "refsheet", usd)
        print(f"  ✓ {CAND.relative_to(ROOT)}/{age}_{i}.png  {yen(usd):.1f}円")
    print(f"見比べて ./ehon refsheet pick {age} <番号> で採用してください")


def pick(age: str, i: int) -> None:
    src = CAND / f"{age}_{i}.png"
    if not src.exists():
        raise SystemExit(f"エラー: {src} がありません")
    shutil.copy(src, ref_path(age))
    print(f"採用: {ref_path(age).relative_to(ROOT)}（この画像が今後の全コマの参照になります）")


# 採用した成犬（assets/ref/dog_adult.png）を参照にして、表情・ポーズの一覧を作る。
# 本番のコマで表情や動きがブレたときの「見本帳」として使う。
PATTERNS = {
    "expressions": "Expression sheet of the SAME dog, six head-and-shoulders portraits in a 3x2 grid on plain paper: "
                   "(1) happy with mouth slightly open, (2) looking up hopefully, (3) ears down and a little lonely, "
                   "(4) head tilted curiously, (5) eyes closed contentedly, (6) sleepy and yawning. "
                   "Identical face, fur color and light-blue collar in all six.",
    "poses": "Pose sheet of the SAME dog, six full-body poses in a 3x2 grid on plain paper: "
             "(1) holding a blue leash in its mouth, sitting, (2) curled up on a small entrance mat, "
             "(3) trotting happily with tail up, (4) standing on hind legs to greet, front paws raised, "
             "(5) lying with chin on front paws, (6) looking back over its shoulder. Identical dog in all six.",
    "together": "Sheet of the SAME dog with a human shown only as hands, arms and legs (no face, no head): "
                "(1) held in two arms against an oatmeal knit sweater, (2) a hand stroking its head, "
                "(3) wrapped in a cream towel held by two hands, (4) walking beside a person's feet on a path. "
                "2x2 grid on plain paper. Identical dog in all four.",
}


def pattern(kind: str, n: int) -> None:
    base = ref_path("adult")
    if not base.exists():
        raise SystemExit("先に成犬の設定画を確定してください")
    C = cfg("character")
    prompt = "\n".join([
        "The attached sheet is the canonical design of this dog. Draw exactly this dog "
        "(same face, fur color and curl, round pom-pom ears, light-blue collar with silver tag). Do not copy its layout.",
        C["style"], C["dog"]["common"], C["dog"]["ages"]["adult"],
        *( [C["humans"]["rule"], C["humans"]["owner"]] if kind == "together" else ["No people in this picture."] ),
        PATTERNS[kind],
    ])
    costs.guard(n * 4.5)
    key = load_env_key("OPENAI_API_KEY", "sk-")
    CAND.mkdir(parents=True, exist_ok=True)
    start = len(list(CAND.glob(f"{kind}_*.png"))) + 1
    for i in range(start, start + n):
        raw, usage = generate(key, prompt, [base])
        usd = usd_from_usage(usage)
        Image.open(BytesIO(raw)).convert("RGB").save(CAND / f"{kind}_{i}.png")
        costs.record("_refsheet", "refsheet", usd)
        print(f"  ✓ {CAND.relative_to(ROOT)}/{kind}_{i}.png  {yen(usd):.1f}円")
