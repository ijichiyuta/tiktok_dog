"""台本の機械チェック。config/rules.yaml の数値で判定する。

errors は直すまで先に進めないもの。warnings は人の目で見てほしいもの。
"""
from __future__ import annotations

from .config import cfg
from .layout import break_lines, chars


def check(s: dict, narrator: str = "owner") -> tuple[list[str], list[str]]:
    R = cfg("rules")
    L = cfg("channel")["layout"]
    err: list[str] = []
    warn: list[str] = []
    slides = s.get("slides", [])

    if len(slides) != R["slides"]:
        err.append(f"枚数が{len(slides)}枚です。{R['slides']}枚にしてください")
    for i, sl in enumerate(slides, 1):
        if sl.get("n") != i:
            err.append(f"{i}枚目の番号が {sl.get('n')} になっています（1から順に）")
            break

    farewell_at: list[int] = []
    for sl in slides:
        n, t = sl.get("n"), sl.get("text", "")
        c = chars(t)
        if c > R["max_chars"]:
            err.append(f"{n}枚目が{c}字です（{R['max_chars']}字以内）: {t}")
        size = L["hook_font_size"] if n == 1 else L["font_size"]
        if break_lines(t, size, R["max_lines"]) is None:
            err.append(f"{n}枚目が{R['max_lines']}行に収まりません: {t}")
        for w in R["banned_words"]:
            if w in t:
                err.append(f"{n}枚目に使えない語「{w}」があります: {t}")
        if any(w in t for w in R["farewell_words"]):
            farewell_at.append(n)
        if (r := sl.get("reuse")) is not None and not (1 <= r < n):
            err.append(f"{n}枚目の reuse={r} は、それより前の枚数を指してください")
        if sl.get("reuse") is not None and slides[sl["reuse"] - 1].get("reuse") is not None:
            err.append(f"{n}枚目は使い回しの使い回しになっています（元の絵の枚数を指してください）")

    if len(farewell_at) > R["max_farewell"]:
        err.append(f"別れの語が{len(farewell_at)}枚にあります（{R['max_farewell']}枚まで）: {farewell_at}枚目")
    for n in farewell_at:
        if n not in R["farewell_slides"]:
            err.append(f"別れの語は{R['farewell_slides']}枚目にだけ置けます（いま{n}枚目）")

    emph = [sl["n"] for sl in slides if sl.get("emphasis")]
    if len(emph) != 1 or emph[0] not in R["emphasis_slides"]:
        err.append(f"赤文字は{R['emphasis_slides']}枚目のどちらか1枚だけにしてください（いま{emph}）")

    reuse = sum(1 for sl in slides if sl.get("reuse") is not None)
    if reuse > R["max_reuse"]:
        err.append(f"絵の使い回しが{reuse}回です（{R['max_reuse']}回まで）")

    if slides and R.get("cover_dog") and not slides[0].get("dog"):
        err.append("1枚目は表紙です。犬を描いてください（dog=true）")
    if slides and not any(w in slides[0].get("text", "") for w in R.get("cover_hook_words", [])):
        warn.append("1枚目にフックの言葉（理由・なぜ・時刻など）がありません")
    if slides:
        last = slides[-1].get("text", "")
        if not any(p in last for p in R["last_slide_patterns"]):
            err.append(f"20枚目は問いかけか行動提案で終えてください: {last}")

    tags = s.get("hashtags", [])
    lo, hi = R["hashtags"]
    if not lo <= len(tags) <= hi:
        err.append(f"ハッシュタグが{len(tags)}個です（{lo}〜{hi}個）")
    if any(t.startswith("#") for t in tags):
        err.append("ハッシュタグは # を付けずに書いてください（書き出し時に付けます）")

    body = "".join(sl.get("text", "") for sl in slides)
    if narrator == "owner":
        if "この子" not in body:
            warn.append("「この子」が一度も出てきません（飼い主目線の回）")
        if "ぼく" in body:
            warn.append("飼い主目線の回に「ぼく」があります")
    else:
        if "ぼく" not in body:
            warn.append("犬目線の回なのに「ぼく」が出てきません")
    if any(w in body + s.get("theme", "") for w in R["always_review_themes"]):
        warn.append("体調・病院に近いテーマです。公開前に必ずペルソナ7の目線で読んでください")
    if len(s.get("caption", "").splitlines()) < 2:
        warn.append("キャプションは2行（1行目=余韻、2行目=コメント誘導）にしてください")
    return err, warn
