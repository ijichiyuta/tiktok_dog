# tiktok_dog — 縦型ショート動画の編集キット `reelfx`

「黒背景 × 紫ネオン × 金属テロップ」系のかっこいいトーク動画を、**Python/YAML の台本からテロップ・図解・光エフェクト・効果音までまとめて自動生成**するツールです。

- 出力は 2 種類: **エフェクトのみの動画**（黒背景 mp4 / 透過 ProRes4444 .mov / 透過 WebM）と、**実写の上に合成した完成動画**
- デザインの根拠は [`docs/STYLE_GUIDE.md`](docs/STYLE_GUIDE.md)（リファレンス動画の分析：配色・書体・モーション・タイミングのルール）
- リファレンス動画のエフェクトを人物以外すべて勘コピした台本: [`projects/insta_reco_rule/timeline.py`](projects/insta_reco_rule/timeline.py)

## セットアップ

```bash
./scripts/setup.sh          # pip install + フォント(OFL)のダウンロード
```

ffmpeg はシステムに無くても `imageio-ffmpeg` 同梱のバイナリを自動で使います。

## 使い方

```bash
# 1) 見た目チェック（コンタクトシート）
python -m reelfx sheet  projects/template/script.yaml -o out/check.jpg --step 0.5

# 2) 1 枚だけ確認
python -m reelfx still  projects/insta_reco_rule/timeline.py 53.3 -o out/frame.png

# 3) エフェクトのみ（黒背景 mp4 ＋ 透過 mov、効果音入り）
python -m reelfx render projects/insta_reco_rule/timeline.py \
    -o out/fx.mp4 --alpha out/fx_alpha.mov

# 4) 実写に合成（人物の後ろにネオンを回す場合はマットを指定）
python -m reelfx render projects/template/script.yaml -o out/final.mp4 \
    --footage talk.mp4 --audio talk.mp4 [--matte auto | --matte person_matte.mp4]
```

- `--matte` を省略すると、ネオンなどの背景レイヤーは**実写の暗い部分にだけ**乗ります（黒背景スタジオ撮影ならこれで十分）。
- `--matte auto` は mediapipe（`pip install mediapipe`）で人物を自動で切り抜きます。
- `--from/--to` で区間だけ、`--fps 15` で軽いプレビューを書き出せます。

## 台本の書き方

### A. YAML（おすすめ・コード不要）

```yaml
duration: 16
background: neon
cues:
  - {t: [0.0, 2.45], do: opening, bg_text: "いき\nなり", lines: [[0.1, "今日", gold_mincho, 271, 885]]}
  - {t: [2.5, 3.6], do: caption, text: "まず結論から言うと"}
  - {t: [3.6, 5.2], do: caption, text: "{毎日投稿|1|gold_gothic}より\n大事なことがある"}
  - {t: [8.0, 9.2], do: warning, text: "ここからが\n{重要|1.35}"}
  - {t: 12.4, do: transition, kind: smear}
  - {t: [14.0, 16.0], do: cta_follow, text: "フォローして\nおいてください"}
```

使えるレシピ（`reelfx/recipes.py`）:
`opening` `caption` `headline` `label` `stack` `warning` `doom` `quote` `bubble` `vertical_tag` `number_hero` `progress` `cta_follow` `transition` `neon_bg`

全部入りの例: [`projects/template/script.yaml`](projects/template/script.yaml)

### B. Python（細かく作り込む）

```python
from reelfx import *

def build():
    tl = Timeline(10)
    tl.add(NeonSwirls(intensity=0.6), 0, 10)
    tl.add(Text("{優先|1.45}\n{ユーザー|1.45}{です|0.4}", 112, "gold_mincho",
                at=(540, 1050), enter=slam(), exit=fade(0.1), emph=[(0.4, shine())]),
           1.0, 2.5, sfx="hit")
    tl.add(Box("おすすめに載る仕組み", "gold", 54, w=680, at=(440, 985), enter=streak()), 2.5, 4.0)
    tl.fx("glitch", 3.8, 4.0, sfx="glitch")
    return tl
```

## 構成

```
reelfx/
  core.py      合成の基礎 (premultiplied RGBA, 変形, ブラー)
  text.py      装飾テキスト (金属グラデ/多重フチ/影/ベベル/縦書き/筆文字化/リッチテキスト)
  palette.py   デザイントークン (色・グラデ・テキスト/ボックスのプリセット)
  shapes.py    ボックス/吹き出し/メーター/バー/スマホ/アバター/ハート/指/集中線
  anim.py      入り・出・強調アニメ (pop, slam, streak, wipe, glitch, typewriter, shine ...)
  elements.py  タイムライン要素 (Text, Box, Bubble, ProgressBar, Meter, AvatarGrid, TapHand ...)
  fx.py        光エフェクト (NeonSwirls, Lightning, EnergySlash, LensStreak, Sparkles)
  timeline.py  タイムライン + 画面全体FX (glitch/flash/hsmear/tint/shake/zoom/vignette)
  sfx.py       効果音シンセ (whoosh/hit/pop/glitch/shine/zap/tap/type/riser)
  recipes.py   高レベルレシピ + YAML 台本ローダ
  render.py    ffmpeg パイプ出力 (マルチプロセス)
projects/
  insta_reco_rule/timeline.py   リファレンスの完全勘コピ (73.6 秒)
  template/script.yaml          新規動画用テンプレ
docs/STYLE_GUIDE.md             デザイン分析とルール
```

フォント: Zen Old Mincho / Noto Sans JP / Dela Gothic One（すべて SIL Open Font License）。`assets/fonts/` に自動ダウンロードされます。
