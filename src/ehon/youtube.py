"""YouTube への予約アップロードと数字の取得。

  ./ehon youtube auth              初回だけ。ブラウザでチャンネルのアカウントにログインして許可
  ./ehon youtube upload <ep>       動画を非公開で上げ、投稿日の21:00に公開予約
  ./ehon youtube stats             上げた回の再生・いいね・コメント数を data/metrics.csv に記録

⚠ API プロジェクトが監査（audit）を通るまでは、API で上げた動画は非公開のまま固定される
   （docs/research-2026-09-25.md §3）。監査が通るまでは video.mp4 を YouTube Studio から手動で予約する。
   config/channel.yaml の youtube.audited を true にすると、このコマンドで公開予約まで行う。

準備: Google Cloud でプロジェクトを作り「YouTube Data API v3」を有効化 → OAuth 同意画面（外部・テスト）→
      認証情報で「デスクトップ アプリ」の OAuth クライアントを作成 → JSON を .secrets/client_secret.json に保存。
      同意画面のテストユーザーに、チャンネルを持つ Google アカウントを追加する。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import ROOT, all_episodes, cfg, meta, script, write_json

SECRETS = ROOT / ".secrets"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly"]


def service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    tok = SECRETS / "youtube_token.json"
    creds = Credentials.from_authorized_user_file(str(tok), SCOPES) if tok.exists() else None
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    if not creds or not creds.valid:
        sec = SECRETS / "client_secret.json"
        if not sec.exists():
            raise SystemExit(f"エラー: {sec} がありません（このファイルの先頭の「準備」を参照）")
        creds = InstalledAppFlow.from_client_secrets_file(str(sec), SCOPES).run_local_server(port=0)
    SECRETS.mkdir(exist_ok=True)
    tok.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)


def publish_at(m: dict) -> str:
    """投稿日の post_time（日本時間）を UTC の ISO 8601 にする。"""
    hh, mm = map(int, cfg("channel")["post_time"].split(":"))
    y, mo, d = map(int, m["date"].split("-"))
    jst = datetime(y, mo, d, hh, mm, tzinfo=timezone(timedelta(hours=9)))
    return jst.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def description(s: dict, m: dict) -> str:
    tags = " ".join("#" + t for t in s["hashtags"])
    lines = [s["caption"].strip(), "", tags, "", "イラストはAIで生成し、文章とあわせて一話ずつ制作しています。#AI作画"]
    if m.get("bgm_credit"):
        lines += ["", f"BGM: {m['bgm_credit']}"]
    return "\n".join(lines)


def upload(ep: Path) -> None:
    from googleapiclient.http import MediaFileUpload

    s, m = script(ep), meta(ep)
    Y = cfg("channel")["youtube"]
    if m.get("state") not in ("approved", "shipped"):
        raise SystemExit(f"エラー: {ep.name} はまだ承認されていません")
    if m.get("youtube_id"):
        print(f"  {ep.name}: アップロード済み https://youtu.be/{m['youtube_id']}")
        return
    video = ep / "video.mp4"
    if not video.exists():
        raise SystemExit(f"エラー: 動画がありません（./ehon video {ep.name}）")
    status = {"privacyStatus": "private", "selfDeclaredMadeForKids": Y["made_for_kids"],
              "containsSyntheticMedia": Y["synthetic_media"]}
    if Y.get("audited"):
        status["publishAt"] = publish_at(m)
    body = {"snippet": {"title": s["youtube_title"][:100], "description": description(s, m),
                        "tags": s["hashtags"], "categoryId": Y["category_id"],
                        "defaultLanguage": Y["default_language"], "defaultAudioLanguage": Y["default_language"]},
            "status": status}
    req = service().videos().insert(part="snippet,status", body=body,
                                    media_body=MediaFileUpload(str(video), chunksize=-1, resumable=True))
    res = None
    while res is None:
        _, res = req.next_chunk()
    m["youtube_id"] = res["id"]
    write_json(ep / "meta.json", m)
    when = status.get("publishAt", "（非公開のまま。Studio で公開予約してください）")
    print(f"  {ep.name}: https://youtu.be/{res['id']}  公開予約 {when}")


def stats() -> None:
    from .metrics import add
    eps = {meta(ep).get("youtube_id"): ep for ep in all_episodes() if meta(ep).get("youtube_id")}
    if not eps:
        print("アップロード済みの回はありません")
        return
    yt = service()
    ids = list(eps)
    for i in range(0, len(ids), 50):
        res = yt.videos().list(part="statistics", id=",".join(ids[i:i + 50])).execute()
        for it in res.get("items", []):
            st = it["statistics"]
            add(eps[it["id"]].name, "youtube", [f"views={st.get('viewCount', 0)}", f"likes={st.get('likeCount', 0)}",
                                                  f"comments={st.get('commentCount', 0)}"])
