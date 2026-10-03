"""アカウントの顔（アイコンと YouTube のバナー）を作る。設定画（成犬）を参照して同じ子で描く。

  ./ehon brand icon --n 3      アイコン候補（正方形。TikTok/YouTube 共通）
  ./ehon brand banner --n 2    YouTube バナー候補（2560×1440 に整える。文字は後から入れない）

出力は assets/brand/。気に入ったものを各サービスに手でアップロードする。
"""
from __future__ import annotations

from io import BytesIO

from PIL import Image

from . import costs
from .config import ROOT, cfg, load_env_key, yen
from .images import REF_NOTE, generate, ref_path, usd_from_usage

OUT = ROOT / "assets/brand"

PROMPTS = {
    "icon": ("A single close-up portrait of the dog's face and chest, looking gently at the viewer, "
             "head slightly tilted, centered, filling most of a square frame, soft plain paper background.", "1024x1024"),
    "banner": ("A very wide, calm scene: the dog curled up asleep on a soft blanket on the right third, "
               "a large area of empty warm paper on the left and center, soft window light.", "1536x1024"),
}


def make(kind: str, n: int) -> None:
    if not ref_path("adult").exists():
        raise SystemExit("先に成犬の設定画を確定してください（./ehon refsheet adult → pick）")
    C = cfg("character")
    what, size = PROMPTS[kind]
    prompt = "\n".join([REF_NOTE, C["style"], C["dog"]["common"], C["dog"]["ages"]["adult"],
                        "No people in this picture.", f"Scene: {what}"])
    costs.guard(n * 4.5)
    key = load_env_key("OPENAI_API_KEY", "sk-")
    OUT.mkdir(parents=True, exist_ok=True)
    img_cfg = cfg("channel")["image"]
    orig = img_cfg["size"]
    img_cfg["size"] = size            # この呼び出しの間だけサイズを変える
    try:
        for i in range(1, n + 1):
            raw, usage = generate(key, prompt, [ref_path("adult")])
            usd = usd_from_usage(usage)
            costs.record("_brand", "brand", usd)
            im = Image.open(BytesIO(raw)).convert("RGB")
            if kind == "banner":
                im = to_banner(im)
            dst = OUT / f"{kind}_{i}.png"
            im.save(dst)
            print(f"  ✓ {dst.relative_to(ROOT)}  {yen(usd):.1f}円")
    finally:
        img_cfg["size"] = orig


def to_banner(im: Image.Image) -> Image.Image:
    """YouTube バナー（2560×1440。どの端末でも見える安全領域は中央 1546×423）。"""
    W, H = 2560, 1440
    bg = Image.new("RGB", (W, H), tuple(int(cfg("channel")["layout"]["background"][i:i + 2], 16) for i in (1, 3, 5)))
    pic = im.resize((W, round(im.height * W / im.width)), Image.Resampling.LANCZOS)
    bg.paste(pic, (0, (H - pic.height) // 2))
    return bg
