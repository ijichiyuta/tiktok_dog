"""CLI:
  python -m reelfx render  PROJECT.py -o out/video.mp4 [--alpha out/fx.mov] [--footage in.mp4 [--matte auto|matte.mp4]]
  python -m reelfx still   PROJECT.py 12.5 -o out/frame.png [--footage in.mp4]
  python -m reelfx sheet   PROJECT.py -o out/sheet.jpg [--step 0.5] [--from 0 --to 10]
  python -m reelfx fonts   (フォント一括ダウンロード)
"""
import argparse

import numpy as np


def main():
    ap = argparse.ArgumentParser(prog="reelfx")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render")
    r.add_argument("project")
    r.add_argument("-o", "--out")
    r.add_argument("--alpha", help="透過動画 (.mov=ProRes4444 / .webm=VP9 alpha)")
    r.add_argument("--footage", help="下に敷く実写動画")
    r.add_argument("--matte", help="人物マスク動画 or 'auto' (mediapipe)")
    r.add_argument("--audio", help="音声トラック (例: 実写の音声)")
    r.add_argument("--no-sfx", action="store_true")
    r.add_argument("--sfx-gain", type=float, default=0.6)
    r.add_argument("--from", dest="start", type=float, default=0.0)
    r.add_argument("--to", dest="end", type=float)
    r.add_argument("--fps", type=int)
    r.add_argument("--workers", type=int)
    r.add_argument("--crf", type=int, default=18)
    s = sub.add_parser("still")
    s.add_argument("project")
    s.add_argument("t", type=float)
    s.add_argument("-o", "--out", required=True)
    s.add_argument("--footage")
    c = sub.add_parser("sheet")
    c.add_argument("project")
    c.add_argument("-o", "--out", required=True)
    c.add_argument("--step", type=float, default=0.5)
    c.add_argument("--from", dest="start", type=float, default=0.0)
    c.add_argument("--to", dest="end", type=float)
    c.add_argument("--cols", type=int, default=8)
    sub.add_parser("fonts")
    a = ap.parse_args()

    from . import render as R
    if a.cmd == "render":
        if not a.out and not a.alpha:
            ap.error("-o か --alpha を指定してください")
        R.render(a.project, a.out, a.alpha, a.footage, a.matte, a.start, a.end, a.fps, a.workers, a.audio,
                 not a.no_sfx, a.sfx_gain, a.crf)
    elif a.cmd == "still":
        R.still(a.project, a.t, a.out, a.footage)
    elif a.cmd == "sheet":
        tl = R.load_project(a.project)
        end = a.end if a.end is not None else tl.duration
        R.contact_sheet(a.project, list(np.arange(a.start, end, a.step)), a.out, a.cols)
    elif a.cmd == "fonts":
        from .fonts import ensure_all
        ensure_all()


if __name__ == "__main__":
    main()
