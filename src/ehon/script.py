"""台本（20枚の文・絵の指示・キャプション）を Claude で作る。

  ./ehon script <ep>          台本を作る（チェックに通るまで最大3回やり直す）
  ./ehon script <ep> --force  既にあっても作り直す

API を使わずに Claude Code との会話で台本を書いてもよい（費用ゼロ）。
その場合は script.json を同じ形で置いて ./ehon check <ep> を通す。
"""
from __future__ import annotations

import json
from typing import Literal, Optional

import anthropic
import yaml
from pydantic import BaseModel, Field

from .config import all_episodes, cfg, load_env_key, meta, read_json, set_state, write_json, yen
from .validate import check

Act = Literal["hook", "daily", "notice", "response", "farewell", "resolve", "ending"]
Person = Literal["owner", "partner", "child", "parents"]
Age = Literal["puppy", "adult", "senior"]


class Slide(BaseModel):
    n: int = Field(description="1から20の通し番号")
    text: str = Field(description="画面に出す日本語の1フレーズ。空白を除き30字以内。改行したい位置があれば \\n")
    act: Act
    emphasis: bool = Field(description="赤文字にするか。18か19枚目のどちらか1枚だけ true")
    scene: str = Field(description="English illustration direction: who, where, doing what, mood. No text in image.")
    shot: str = Field(description="English camera framing, e.g. 'close-up of the dog looking up', 'wide view of a dim living room'")
    dog: bool = Field(description="この絵に主役の犬が描かれるか")
    dog_age: Optional[Age] = Field(default=None, description="回の基本と違う年齢で描くときだけ（回想など）")
    humans: list[Person] = Field(description="描かれる人物。顔は描かない。いなければ空")
    reuse: Optional[int] = Field(default=None, description="前の枚の絵をそのまま使うなら、その枚数。新しく描くなら null")


class Script(BaseModel):
    title: str = Field(description="回のタイトル（内部管理用・YouTubeにも使う）")
    theme: str = Field(description="この回で描く犬の行動の『意味』を一文で")
    slides: list[Slide]
    caption: str = Field(description="TikTokキャプション。1行目=物語の余韻、2行目=コメントを誘う問いかけ。改行で区切る。ハッシュタグは含めない")
    hashtags: list[str] = Field(description="4〜6個。#は付けない。シリーズタグを含める")
    youtube_title: str = Field(description="YouTube用タイトル。40字以内。結末を明かさない")
    self_review: str = Field(description="ペットロス中の人（ペルソナ7）の目線で読んだときに傷つける箇所がないかの点検結果")


SAMPLE = """1. 雨だから、今日の散歩はなしにした
2. 仕事で疲れていたのもある
3. ソファでスマホを眺めていたら、足元に気配がした
4. リードをくわえたこの子が、じっと座っていた
5. 「ごめん、今日は雨だよ」と言うと
6. リードを置いて、玄関の前で丸くなった
7. 怒るでも、鳴くでもなく
8. ただ、ドアが開くのを待っていた
9. この子の一日は、あの散歩が一番の楽しみなんだ
10. 私の一日のうちの30分は
11. この子にとっては一日の全部だった
12. 傘をさして、外に出た
13. 水たまりをよけながら、しっぽがずっと揺れている
14. びしょ濡れで帰って、タオルで包んだ
15. 腕の中で、満足そうに目を閉じた
16. あと何回、一緒に雨の道を歩けるんだろう
17. 10年なんて、きっとあっという間だ
18. 【赤】だから、面倒な日ほど一緒に行こう
19. この子が待っていてくれる限り
20. あなたの子にとっての「一番の30分」は何ですか？"""


def system_prompt() -> str:
    R = cfg("rules")
    return f"""あなたは犬の飼い主に向けた絵本作家です。TikTokのフォトモード（20枚の画像を指でめくる形式）とYouTubeショートに載せる、1話完結の短い絵本の台本を書きます。

# このアカウントの核
10年しかない、この子との「ふつうの一日」を絵本にする。見た人が投稿を閉じたあと、愛犬を撫でたくなる・今日を大切にしたくなることがゴール。

# なぜ泣けるのか（毎回このどれかを物語の芯にする）
1. 視点の反転：世話しているつもりが、実は犬のほうが見守っていた
2. 時間の非対称：犬にとって飼い主は「全部」、飼い主にとって犬は「一部」
3. 無言の献身：犬は言葉で訴えない。行動（床で寝る、ついてくる、見上げる）に意味を与える
4. 別れの予告：終盤で1枚だけ「いつか」に触れる。直接は描かない
5. 決意で終わる：悲しみで終わらせず、今夜・明日の小さな行動で締める

# 20枚の型
- 1枚目 hook：絵本の表紙。答えの見えない一文（「〜の理由」「なぜ」「◯時」など）でめくらせる。絵には必ず犬を描き、物語の核心の瞬間を結末を明かさずに見せる（dog=true）
- 2〜4枚目 daily：飼い主の小さな失敗や疲れ。共感の入口
- 5〜8枚目 notice：犬の行動に意味があったと気づく
- 9〜15枚目 response：飼い主が行動で返す。犬が寄り添う
- 16〜17枚目 farewell：時間の短さに1枚だけ触れる（「あと何回」「10年」など）
- 18〜19枚目 resolve：決意。どちらか1枚を赤文字（emphasis=true）にする
- 20枚目 ending：読者への問いかけ、または「今夜は〜してあげてください」系の行動提案

# 文のルール（機械でチェックします）
- 1枚＝1フレーズ。空白を除いて{R['max_chars']}字以内、画面で2行以内。文が2枚にまたがってもよい
- 別れを直接指す語（{'・'.join(R['farewell_words'])}）は1投稿で1枚まで、しかも16か17枚目だけ
- 次の語は使わない: {'・'.join(R['banned_words'])}
- 死・病気・病院・介護を直接描かない。飼い主を責める、罪悪感や後悔を煽る表現をしない
- 説教しない。「〜すべき」「〜しないとダメ」は使わない
- 犬の名前は出さない（読者が自分の子の名前を当てはめられるように）
- 固有の地名・店名・商品名・実在の人名を出さない
- 既存の詩（犬の十戒・虹の橋など）や歌詞の文言を引用しない。テーマだけ借りてすべて自分の言葉で書く
- 毎回ちがう物語にする。決まり文句の結末（「今夜はぎゅっと」だけで終わる、など）を繰り返さない。その回の場面から生まれた具体的な行動で締める

# 絵の指示（scene / shot は英語）
- 1枚に1つの瞬間。何が・どこで・どんな表情で、を具体的に。文の「気持ち」が伝わる瞬間を選ぶ
- **文が表す位置関係・視線・動作・時間帯を、絵の指示に必ず明記する**（例：「振り返ると、あなたがいる」→ the owner walks BEHIND the dog; the dog looks back over its shoulder at the owner）。文と絵がずれるのが一番の失敗
- 人物の顔は絶対に描かない（後ろ姿・肩から下・手・足元のみ）。shot もそれに合う構図にする
- 犬がいない場面は dog=false（いない犬を描かせないため）。ただし写真・額縁・スマホ画面の中にこの子が写るコマは dog=true（参照を付けないと別の犬種が描かれる）
- 絵の使い回しはしない（reuse は常に null）。20枚すべて違う瞬間を描く
- 文字・看板・画面の中の文字は描かせない

# 見本（設計書のサンプル。この水準の具体性と間を目指す。文言は真似しない）
{SAMPLE}
"""


def persona_block(pid: int) -> str:
    p = next((x for x in cfg("personas") if x["id"] == pid), None)
    return yaml.safe_dump(p, allow_unicode=True, sort_keys=False) if p else "（指定なし）"


def recent_titles(limit: int = 30) -> list[str]:
    out = []
    for ep in all_episodes()[-limit:]:
        s = read_json(ep / "script.json")
        if s:
            out.append(f"{s['title']} — 1枚目「{s['slides'][0]['text']}」／20枚目「{s['slides'][-1]['text']}」")
    return out


HOUSEHOLD = {
    "solo": "飼い主の一人暮らし",
    "partner": "飼い主とパートナーの二人暮らし",
    "family": "飼い主とパートナーと小さな子ども（4歳くらい）の家族",
    "parents": "飼い主が実家に帰っている（飼い主の年配の両親がいる）",
}


def user_prompt(m: dict) -> str:
    idea = m["idea"]
    S = cfg("series")["series"][idea["series"]]
    lines = [
        f"# 今回の回",
        f"シリーズ: {idea['series']}. {S['name']}（語り: {S['voice']}）",
        f"シリーズの注意: {S.get('note', 'なし')}",
        f"タイトル案: {idea['title']}",
        f"場面: {idea['scene']}",
        f"犬の年齢: {idea.get('dog_age', 'adult')}",
        f"家族構成: {HOUSEHOLD[idea.get('household', 'solo')]}",
        f"この回の注意: {idea.get('note', 'なし')}",
        "",
        "# いちばん届けたい相手（ペルソナ）",
        persona_block(idea.get("persona", 2)),
        "",
        "# これまでの回（同じ始まり方・終わり方を避ける）",
        *(recent_titles() or ["（まだなし）"]),
        "",
        "hashtags にはシリーズタグ「" + S["tag"] + "」を含め、残りは次から選ぶ: "
        + "、".join(cfg("channel")["hashtags_base"]),
    ]
    return "\n".join(lines)


def cost_usd(u) -> float:
    rate = {"claude-opus-5": (5, 25), "claude-sonnet-5": (2, 10), "claude-haiku-4-5": (1, 5)}
    i, o = rate.get(cfg("channel")["claude"]["model"], (5, 25))
    tin = u.input_tokens + (u.cache_creation_input_tokens or 0) * 1.25 + (u.cache_read_input_tokens or 0) * 0.1
    return (tin * i + u.output_tokens * o) / 1e6


def generate(ep, force: bool = False) -> dict:
    m = meta(ep)
    if (ep / "script.json").exists() and not force:
        print(f"  {ep.name}: 台本は作成済み（作り直すなら --force）")
        return read_json(ep / "script.json")
    C = cfg("channel")["claude"]
    narrator = cfg("series")["series"][m["idea"]["series"]]["narrator"]
    client = anthropic.Anthropic(api_key=load_env_key("ANTHROPIC_API_KEY", "sk-ant-"))
    messages: list = [{"role": "user", "content": user_prompt(m)}]
    total = 0.0
    s: dict = {}
    err: list[str] = []
    warn: list[str] = []
    for attempt in range(3):
        r = client.messages.parse(
            model=C["model"],
            max_tokens=16000,
            system=[{"type": "text", "text": system_prompt(), "cache_control": {"type": "ephemeral"}}],
            thinking={"type": "adaptive"},
            output_config={"effort": C["effort"]},
            messages=messages,
            output_format=Script,
            extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
            extra_body={"fallbacks": "default"},
        )
        total += cost_usd(r.usage)
        if r.stop_reason == "refusal":
            raise SystemExit(f"エラー: 台本の生成が断られました（{getattr(r, 'stop_details', None)}）")
        if r.parsed_output is None:
            raise SystemExit(f"エラー: 台本を読み取れませんでした（stop_reason={r.stop_reason}）")
        s = r.parsed_output.model_dump()
        err, warn = check(s, narrator)
        print(f"  {ep.name}: 試行{attempt + 1} エラー{len(err)} 注意{len(warn)}（{yen(total):.1f}円）")
        if not err:
            break
        for e in err:
            print(f"    ✗ {e}")
        messages += [{"role": "assistant", "content": replay(r.content)},
                     {"role": "user", "content": "機械チェックで次の問題が見つかりました。直した台本全体を出し直してください。\n"
                      + "\n".join(f"- {e}" for e in err)}]
    s["_check"] = {"errors": err, "warnings": warn}
    write_json(ep / "script.json", s)
    log_cost(ep, "script", total)
    if not err:
        set_state(ep, "scripted")
    return s


def replay(blocks) -> list[dict]:
    """やり直しの依頼で前の応答を返すとき、API が受け付ける項目だけに絞る。
    （parse の戻り値には parsed_output などの余分な項目が付いている）"""
    out = []
    for b in blocks:
        if b.type == "thinking":
            out.append({"type": "thinking", "thinking": b.thinking, "signature": b.signature})
        elif b.type == "redacted_thinking":
            out.append({"type": "redacted_thinking", "data": b.data})
        elif b.type == "text":
            out.append({"type": "text", "text": b.text})
    return out


def log_cost(ep, kind: str, usd: float) -> None:
    from .costs import record
    record(ep.name, kind, usd)
