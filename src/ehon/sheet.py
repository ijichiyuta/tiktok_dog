"""公開前の確認ページ（episodes/<ep>/review.html）。20枚を一覧し、キャプション・チェック結果・費用を並べる。

  ./ehon sheet <ep>      作ってブラウザで開く
"""
from __future__ import annotations

import html
import subprocess
from pathlib import Path

from . import costs
from .config import cfg, meta, script

CSS = """
body{margin:0;padding:24px 16px;background:#f2f1ee;color:#333;font:15px/1.7 -apple-system,'Hiragino Sans',sans-serif}
h1{font-size:20px;margin:0 0 4px} .sub{color:#777;margin-bottom:16px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:10px}
.grid figure{margin:0;background:#fff;border-radius:6px;padding:4px;box-shadow:0 1px 3px #0001}
.grid img{width:100%;display:block;border-radius:4px} figcaption{font-size:12px;color:#888;padding:2px 4px}
.box{background:#fff;border-radius:8px;padding:12px 16px;margin:16px 0;box-shadow:0 1px 3px #0001;max-width:760px}
.err{color:#b3261e} .warn{color:#8a5a00} pre{white-space:pre-wrap;margin:0}
.checklist li{margin:4px 0}
"""


def yt_desc(s: dict, m: dict) -> str:
    from .youtube import description
    return description(s, m)


def run(ep: Path, open_it: bool = True) -> Path:
    s = script(ep)
    m = meta(ep)
    ch = s.get("_check", {})
    tags = " ".join("#" + t for t in s["hashtags"])
    figs = "".join(
        f'<figure><img src="slides/{sl["n"]:02d}.png" loading="lazy"><figcaption>{sl["n"]:02d} {sl["act"]}'
        f'{" ・使い回し←" + str(sl["reuse"]) if sl.get("reuse") else ""}</figcaption></figure>'
        for sl in s["slides"])
    errs = "".join(f'<li class="err">{html.escape(e)}</li>' for e in ch.get("errors", []))
    warns = "".join(f'<li class="warn">{html.escape(w)}</li>' for w in ch.get("warnings", []))
    doc = f"""<!doctype html><meta charset="utf-8"><title>{html.escape(s['title'])}</title><style>{CSS}</style>
<h1>{html.escape(s['title'])}</h1>
<div class="sub">{m['date']}・{m['idea']['series']} {m['idea']['id']}・状態 {m.get('state')}・費用 {costs.episode_jpy(ep.name):.0f}円</div>
<div class="grid">{figs}</div>
<div class="box"><b>キャプション</b><pre>{html.escape(s['caption'])}\n\n{html.escape(tags)}</pre></div>
<div class="box"><b>YouTube（Studio で手動予約するとき用）</b><pre>タイトル: {html.escape(s['youtube_title'])}
公開: {m['date']} {cfg('channel')['post_time']}

{html.escape(yt_desc(s, m))}</pre></div>
<div class="box"><b>機械チェック</b><ul>{errs or '<li>エラーなし</li>'}{warns}</ul></div>
<div class="box"><b>ペルソナ7の目線での自己点検（Claude）</b><pre>{html.escape(s.get('self_review', ''))}</pre></div>
<div class="box checklist"><b>人の目で見ること</b><ul>
<li>犬の顔・毛色・水色の首輪が20枚でそろっているか（ブレたコマは ./ehon images {ep.name} --only 番号）</li>
<li>人の顔が描かれていないか。文字・ロゴ・透かしが混ざっていないか</li>
<li>ペットロス中の人が読んで傷つかないか（死・病気・後悔を煽る表現がないか）</li>
<li>1枚目で続きを見たくなるか。赤文字の1枚が決意の文になっているか</li>
</ul>OKなら <code>./ehon approve {ep.name}</code></div>
"""
    out = ep / "review.html"
    out.write_text(doc, encoding="utf-8")
    if open_it:
        subprocess.run(["open", str(out)], check=False)
    print(f"  確認ページ: {out}")
    return out
