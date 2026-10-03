"""./ehon <コマンド>。一覧は ./ehon -h、流れは README.md。"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

from .config import all_episodes, ep_dir, meta, read_json, script, set_state, write_json


def cmd_status(_a) -> None:
    from . import costs
    eps = all_episodes()
    if not eps:
        print("エピソードはまだありません。./ehon plan --start YYYY-MM-DD --days 7 から")
    for ep in eps:
        m = meta(ep)
        s = read_json(ep / "script.json", {})
        flags = []
        if s.get("_check", {}).get("errors"):
            flags.append("⚠台本エラー")
        if m.get("youtube_id"):
            flags.append("YT済")
        print(f"  {ep.name:<20} {m.get('state', '?'):<11} {costs.episode_jpy(ep.name):>5.0f}円  "
              f"{s.get('title') or m['idea']['title']}  {' '.join(flags)}")
    costs.report()


def cmd_plan(a) -> None:
    from .plan import run
    start = date.fromisoformat(a.start) if a.start else date.today() + timedelta(days=1)
    run(start, a.days)


def cmd_script(a) -> None:
    from .script import generate
    for ep in targets(a.ep, "planned"):
        generate(ep, a.force)


def cmd_check(a) -> None:
    from .config import cfg
    from .validate import check
    for ep in targets(a.ep, None):
        s = script(ep)
        narrator = cfg("series")["series"][meta(ep)["idea"]["series"]]["narrator"]
        err, warn = check(s, narrator)
        s["_check"] = {"errors": err, "warnings": warn}
        write_json(ep / "script.json", s)
        for e in err:
            print(f"  ✗ {e}")
        for w in warn:
            print(f"  △ {w}")
        if not err:
            print(f"  {ep.name}: チェックOK")
            if meta(ep).get("state") == "planned":
                set_state(ep, "scripted")


def cmd_images(a) -> None:
    from .images import accept, check_api, run
    if a.check:
        return check_api()
    if a.accept:
        for ep in targets(a.ep, None):
            accept(ep)
        return
    only = [int(x) for x in a.only.split(",")] if a.only else None
    for ep in targets(a.ep, "scripted"):
        run(ep, only, a.force)


def cmd_refsheet(a) -> None:
    from .refsheet import make, pick
    if a.age == "pick":
        return pick(a.rest[0], int(a.rest[1]))
    if a.age in ("expressions", "poses", "together"):
        from .refsheet import pattern
        return pattern(a.age, a.n)
    make(a.age, a.n)


def cmd_qa(a) -> None:
    from .qa import run
    only = [int(x) for x in a.only.split(",")] if a.only else None
    for ep in targets(a.ep, None):
        run(ep, a.fix, only)


def cmd_brand(a) -> None:
    from .brand import make
    make(a.kind, a.n)


def cmd_compose(a) -> None:
    from .compose import run
    for ep in targets(a.ep, "illustrated"):
        run(ep, a.placeholder)


def cmd_video(a) -> None:
    from .video import run
    for ep in targets(a.ep, "composed"):
        run(ep)


def cmd_sheet(a) -> None:
    from .sheet import run
    for ep in targets(a.ep, None):
        run(ep, not a.no_open)


def cmd_approve(a) -> None:
    for ep in targets(a.ep, None):
        s = script(ep)
        if s.get("_check", {}).get("errors"):
            raise SystemExit(f"エラー: {ep.name} は台本チェックのエラーが残っています")
        if not all((ep / "slides" / f"{sl['n']:02d}.png").exists() for sl in s["slides"]):
            raise SystemExit(f"エラー: {ep.name} はスライドがそろっていません")
        set_state(ep, "approved")
        print(f"  {ep.name}: 承認しました")


def cmd_ship(a) -> None:
    """承認済みの回を、スマホへの書き出し＋YouTube へのアップロードまで進める。"""
    from .config import cfg
    from .export import run as export
    from .video import run as video
    from .youtube import upload
    for ep in targets(a.ep, "approved"):
        if not (ep / "video.mp4").exists():
            video(ep)
        export(ep)
        if a.no_youtube:
            pass
        elif cfg("channel")["youtube"].get("audited"):
            upload(ep)
        else:
            # 未監査のまま API で上げると非公開に固定されて使えない（docs/research-2026-09-25.md §3）
            print(f"  △ YouTube は Studio から手動で予約: {ep / 'video.mp4'}（公開 {meta(ep)['date']} "
                  f"{cfg('channel')['post_time']}・タイトルと説明文は review.html）")
        set_state(ep, "shipped")


def cmd_run(a) -> None:
    """台本 → 画像 → スライド → 動画 → 確認ページ を通しで。人の確認（approve）の手前で止まる。"""
    from .compose import run as compose
    from .images import run as images
    from .script import generate
    from .sheet import run as sheet
    from .video import run as video
    eps = [ep_dir(a.ep)] if a.ep else [ep for ep in all_episodes()
                                       if meta(ep).get("state") in ("planned", "scripted", "illustrated", "composed")]
    for ep in eps:
        s = generate(ep)
        if s.get("_check", {}).get("errors"):
            print(f"  {ep.name}: 台本にエラーが残ったので止めます（./ehon check {ep.name}）")
            continue
        images(ep)
        compose(ep)
        video(ep)
        sheet(ep, open_it=not a.no_open)


def cmd_export(a) -> None:
    from .export import run
    for ep in targets(a.ep, None):
        run(ep)


def cmd_youtube(a) -> None:
    from .youtube import service, stats, upload
    if a.action == "auth":
        service()
        print("認証OK")
    elif a.action == "upload":
        for ep in targets(a.ep, "approved"):
            upload(ep)
    elif a.action == "stats":
        stats()


def cmd_metrics(a) -> None:
    from .metrics import add
    add(ep_dir(a.ep).name, a.platform, a.values)


def cmd_followers(a) -> None:
    from .metrics import add_followers
    add_followers(a.platform, a.n)
    print("記録しました")


def cmd_report(a) -> None:
    from .metrics import report
    report(a.platform)


def cmd_cost(_a) -> None:
    from .costs import report
    report()


def targets(key: str | None, state: str | None):
    """key があればその回。無ければ state の回すべて（state=None なら全部）。"""
    if key:
        return [ep_dir(key)]
    eps = [ep for ep in all_episodes() if state is None or meta(ep).get("state") == state]
    if not eps:
        print(f"対象の回がありません（状態 {state}）")
    return eps


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="ehon", description="マルプー絵本アカウントの制作パイプライン")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_, ep=True):
        q = sub.add_parser(name, help=help_)
        if ep:
            q.add_argument("ep", nargs="?", help="回（日付かネタIDかフォルダ名）。省略すると該当する状態の回すべて")
        q.set_defaults(fn=fn)
        return q

    add("status", cmd_status, "全エピソードの状態と費用", ep=False)
    q = add("plan", cmd_plan, "投稿予定を立てる（ネタ帳から割り当て）", ep=False)
    q.add_argument("--start")
    q.add_argument("--days", type=int, default=7)
    q = add("script", cmd_script, "台本を Claude で作る")
    q.add_argument("--force", action="store_true")
    add("check", cmd_check, "台本の機械チェック（手で直したあとに）")
    q = add("images", cmd_images, "イラストを生成")
    q.add_argument("--only")
    q.add_argument("--force", action="store_true")
    q.add_argument("--check", action="store_true", help="キーとモデルの疎通だけ確認")
    q.add_argument("--accept", action="store_true", help="設定を変えたあと、今の絵を作り直さずに承認する")
    q = add("refsheet", cmd_refsheet, "設定画（adult/puppy/senior/expressions/poses/together または pick <age> <番号>）", ep=False)
    q.add_argument("age")
    q.add_argument("rest", nargs="*")
    q.add_argument("--n", type=int, default=3)
    q = add("qa", cmd_qa, "文と絵が合っているかを判定（--fix で直して作り直す）")
    q.add_argument("--fix", action="store_true")
    q.add_argument("--only")
    q = add("brand", cmd_brand, "アイコン・YouTubeバナーの候補を作る", ep=False)
    q.add_argument("kind", choices=["icon", "banner"])
    q.add_argument("--n", type=int, default=3)
    q = add("compose", cmd_compose, "文字を合成してスライド20枚")
    q.add_argument("--placeholder", action="store_true")
    add("video", cmd_video, "YouTube 用の縦動画")
    q = add("sheet", cmd_sheet, "確認ページを開く")
    q.add_argument("--no-open", action="store_true")
    add("approve", cmd_approve, "人の確認が済んだ印")
    q = add("run", cmd_run, "台本→画像→スライド→動画→確認ページ を通しで")
    q.add_argument("--no-open", action="store_true")
    q = add("ship", cmd_ship, "承認済みを書き出し＋YouTube へ")
    q.add_argument("--no-youtube", action="store_true")
    add("export", cmd_export, "スマホ用に書き出し（iCloud Drive）")
    q = add("youtube", cmd_youtube, "auth / upload <ep> / stats", ep=False)
    q.add_argument("action", choices=["auth", "upload", "stats"])
    q.add_argument("ep", nargs="?")
    q = add("metrics", cmd_metrics, "数字を記録: <ep> tiktok views=.. likes=.. saves=..", ep=False)
    q.add_argument("ep")
    q.add_argument("platform", choices=["tiktok", "youtube", "instagram"])
    q.add_argument("values", nargs="+")
    q = add("followers", cmd_followers, "フォロワー数を記録: tiktok 1234", ep=False)
    q.add_argument("platform")
    q.add_argument("n", type=int)
    q = add("report", cmd_report, "保存率ランキング", ep=False)
    q.add_argument("platform", nargs="?", default="tiktok")
    add("cost", cmd_cost, "月ごとの費用", ep=False)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main(sys.argv[1:])
