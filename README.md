# ehon — マルプーの絵本アカウント

犬の飼い主が「うちの子もそうだ」と泣いて保存する20枚の絵本を、毎日1本出すための制作パイプライン。
TikTok（フォトモード・手動投稿）と YouTube（約70秒の縦動画）に出す。

- 設計書の原本: [docs/design.md](docs/design.md)
- **実装の正（決定事項）: [docs/decisions.md](docs/decisions.md)**
- 外部仕様の調査: [docs/research-2026-09-25.md](docs/research-2026-09-25.md)
- アカウント名の候補: [docs/account-names.md](docs/account-names.md)
- アカウント開設（匿名）: [docs/account-setup.md](docs/account-setup.md)

## 流れ

```
ネタ帳 ─ plan ─→ 台本 ─ check ─→ イラスト ─→ スライド20枚 ─→ 動画 ─→ 確認ページ
(ideas.yaml)     (Claude)  (機械)   (gpt-image)   (文字合成)    (ffmpeg)   (人の目)
                                                                              │ approve
                              スマホ(iCloud)→TikTok 手動投稿 ←─ ship ←───────┘
                              YouTube（監査前は Studio で手動予約）
数字 ─ metrics ─→ report（保存率ランキング）─→ ネタ帳に戻す
```

## 最初の1回だけ

```bash
cp .env.example .env          # ANTHROPIC_API_KEY と OPENAI_API_KEY を書く
./ehon images --check         # OpenAI の疎通確認

./ehon refsheet adult --n 3   # 成犬の設定画の候補（約8円）→ assets/ref/_candidates/
./ehon refsheet pick adult 2  # 気に入った番号を採用
./ehon refsheet puppy --n 2   # 子犬（成犬を参照して同じ子で）
./ehon refsheet pick puppy 1
./ehon refsheet senior --n 2
./ehon refsheet pick senior 1
./ehon brand icon --n 3       # アイコン候補
```

## 毎週（まとめて1回・30〜40分）

```bash
./ehon plan --start 2026-10-01 --days 7   # 1週間分の枠にネタを割り当て
./ehon run                                # 台本→画像→スライド→動画→確認ページ（全部の回）
#   ブレたコマだけ作り直す:  ./ehon images <回> --only 3,7 && ./ehon compose <回>
./ehon approve <回>                       # 確認ページを見てOKなら
./ehon ship                               # 承認済みをスマホへ書き出し（YouTube は案内が出る）
```

毎晩21時: iPhone の「ファイル」→ ehon → 当日のフォルダ → 20枚を保存 → TikTok（手順は `投稿メモ.txt`）

## 数字をつける（投稿の2日後）

```bash
./ehon metrics 2026-10-01 tiktok views=3200 likes=410 saves=38 shares=6 comments=2
./ehon followers tiktok 540
./ehon youtube stats          # YouTube は自動で取得（auth 済みなら）
./ehon report                 # 保存率の高い順。上位の場面をネタ帳に増やす
```

## 費用

| 項目 | 1本 | 月30本 |
|---|---|---|
| 台本（Claude Opus 5） | 約25円 | 約750円 |
| イラスト（gpt-image-2.5-flare medium・約16枚、犬のコマは参照1枚） | 約70円 | 約2,100円 |
| **合計** | **約95円** | **約2,850円**（予算5,000円） |

- 台本を Claude Code との会話で書けば、台本代は0円になる（CLAUDE.md の手順）
- `./ehon cost` で月ごとの実費を確認できる。月の予算（`config/channel.yaml` の budget）を超えそうになると、生成の前に止まる

## コマンド一覧

`./ehon -h`。回の指定は日付（`2026-10-01`）・ネタID（`B01`）・フォルダ名のどれでもよい。

## 構成

```
config/     channel（全体・予算・レイアウト）/ character（犬と人と画風）/ series（シリーズと曜日の枠）
            rules（台本の機械チェック）/ personas（ペルソナ10人）
content/    ideas.yaml（ネタ帳）
assets/     fonts（Klee One）/ ref（設定画）/ brand（アイコン等）/ bgm（YouTube 用の曲）
episodes/   <日付>_<ネタID>/ meta.json・script.json・images/・slides/・video.mp4・review.html
data/       costs.csv（費用）/ metrics.csv・followers.csv（数字）
src/ehon/   本体
```
