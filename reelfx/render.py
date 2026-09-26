"""レンダラ: タイムライン → 動画ファイル (ffmpeg パイプ, マルチプロセス)。"""
from __future__ import annotations

import importlib.util
import multiprocessing as mp
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from .core import to_uint8_rgb, to_uint8_rgba


def ffmpeg_exe() -> str:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def load_project(path: str):
    """プロジェクトファイル (build() -> Timeline を定義した .py) を読み込む。"""
    path = str(Path(path).resolve())
    if path.endswith((".yaml", ".yml")):
        from .recipes import from_yaml
        return from_yaml(path)
    spec = importlib.util.spec_from_file_location("reelfx_project", path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(Path(path).parent))
    spec.loader.exec_module(mod)
    if hasattr(mod, "build"):
        return mod.build()
    return mod.timeline


# ---- worker ----
_TL = None


def _init(project):
    global _TL
    import cv2
    cv2.setNumThreads(1)  # プロセス並列なので OpenCV 内部スレッドは切る
    _TL = load_project(project)


def _work(args):
    i, t, footage, matte, want_rgb, want_rgba = args
    ft = None if footage is None else footage.astype(np.float32) / 255.0
    mt = None if matte is None else matte.astype(np.float32) / 255.0
    img = _TL.compose(t, ft, mt)
    rgb = to_uint8_rgb(img).tobytes() if want_rgb else None
    rgba = to_uint8_rgba(img).tobytes() if want_rgba else None
    return i, rgb, rgba


def _reader(path, w, h, fps, start=0.0, gray=False):
    cmd = [ffmpeg_exe(), "-v", "error", "-ss", str(start), "-i", str(path), "-vf",
           f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps}",
           "-f", "rawvideo", "-pix_fmt", "gray" if gray else "rgb24", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    n = w * h * (1 if gray else 3)
    while True:
        buf = p.stdout.read(n)
        if len(buf) < n:
            break
        yield np.frombuffer(buf, np.uint8).reshape(h, w) if gray else np.frombuffer(buf, np.uint8).reshape(h, w, 3)


def _auto_matte(frames):
    """mediapipe があれば人物セグメンテーション。"""
    try:
        import mediapipe as mpp
    except ImportError:
        raise SystemExit("--matte auto には mediapipe が必要です: pip install mediapipe")
    seg = mpp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=0)
    for f in frames:
        r = seg.process(f)
        yield (np.clip(r.segmentation_mask, 0, 1) * 255).astype(np.uint8)


def render(project, out=None, alpha_out=None, footage=None, matte=None, start=0.0, end=None, fps=None,
           workers=None, audio=None, sfx=True, sfx_gain=0.6, crf=18):
    tl = load_project(project)
    fps = fps or tl.fps
    end = tl.duration if end is None else end
    w, h = tl.size
    n = int(round((end - start) * fps))
    workers = workers or max(1, (os.cpu_count() or 2))
    ff = ffmpeg_exe()
    tmp = Path(tempfile.mkdtemp(prefix="reelfx_"))

    # --- 音声 ---
    wav = None
    if sfx and tl.sfx:
        from . import sfx as S
        cues = [(t - start, nm, g) for t, nm, g in tl.sfx if start <= t < end]
        wav = tmp / "sfx.wav"
        S.write_wav(wav, S.mix(cues, end - start, sfx_gain))

    procs = []
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        cmd = [ff, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps),
               "-i", "-"]
        amaps = []
        if audio:
            cmd += ["-ss", str(start), "-i", str(audio)]
            amaps.append(len(amaps) + 1)
        if wav:
            cmd += ["-i", str(wav)]
            amaps.append(len(amaps) + 1)
        cmd += ["-map", "0:v"]
        if len(amaps) == 2:
            cmd += ["-filter_complex", f"[1:a][2:a]amix=inputs=2:normalize=0[a]", "-map", "[a]"]
        elif len(amaps) == 1:
            cmd += ["-map", f"{amaps[0]}:a"]
        cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p",
                "-movflags", "+faststart"]
        if amaps:
            cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
        cmd += [str(out)]
        procs.append(("rgb", subprocess.Popen(cmd, stdin=subprocess.PIPE)))
    if alpha_out:
        Path(alpha_out).parent.mkdir(parents=True, exist_ok=True)
        cmd = [ff, "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}", "-r", str(fps),
               "-i", "-"]
        if wav:
            cmd += ["-i", str(wav), "-map", "0:v", "-map", "1:a"]
        if str(alpha_out).endswith(".webm"):
            cmd += ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "5M", "-auto-alt-ref", "0",
                    "-deadline", "realtime", "-cpu-used", "8", "-row-mt", "1"]
            if wav:
                cmd += ["-c:a", "libopus"]
        else:
            cmd += ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-qscale:v", "11"]
            if wav:
                cmd += ["-c:a", "pcm_s16le"]
        cmd += ["-shortest", str(alpha_out)] if wav else [str(alpha_out)]
        procs.append(("rgba", subprocess.Popen(cmd, stdin=subprocess.PIPE)))

    fr = _reader(footage, w, h, fps, start) if footage else None
    mt = None
    if matte == "auto" and footage:
        mt = _auto_matte(_reader(footage, w, h, fps, start))
    elif matte:
        mt = _reader(matte, w, h, fps, start, gray=True)

    def jobs():
        for i in range(n):
            f = next(fr, None) if fr else None
            if fr and f is None:
                f = np.zeros((h, w, 3), np.uint8)
            m = next(mt, None) if mt else None
            yield (i, start + i / fps, f, m, any(k == "rgb" for k, _ in procs), any(k == "rgba" for k, _ in procs))

    t0 = time.time()
    with mp.get_context("spawn").Pool(workers, _init, (project,)) as pool:
        for k, (i, rgb, rgba) in enumerate(pool.imap(_work, jobs(), chunksize=2)):
            for kind, p in procs:
                p.stdin.write(rgb if kind == "rgb" else rgba)
            if k % 30 == 0 or k == n - 1:
                el = time.time() - t0
                eta = el / (k + 1) * (n - k - 1)
                print(f"\r[reelfx] {k + 1}/{n} frames  {el:5.1f}s  eta {eta:5.1f}s", end="", flush=True)
    print()
    for _, p in procs:
        p.stdin.close()
        p.wait()
    shutil.rmtree(tmp, ignore_errors=True)


def still(project, t, out, footage=None, bg=(0, 0, 0)):
    from PIL import Image
    tl = load_project(project)
    f = None
    if footage:
        w, h = tl.size
        f = next(_reader(footage, w, h, tl.fps, t)).astype(np.float32) / 255.0
    img = tl.compose(t, f)
    Image.fromarray(to_uint8_rgb(img, bg)).save(out)


def contact_sheet(project, times, out, cols=6, thumb=(270, 480), bg=(28, 28, 36)):
    """指定時刻のサムネ一覧 (デザイン確認用)。"""
    from PIL import Image, ImageDraw
    tl = load_project(project)
    rows = (len(times) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb[0], rows * thumb[1]), (0, 0, 0))
    d = ImageDraw.Draw(sheet)
    for k, t in enumerate(times):
        im = Image.fromarray(to_uint8_rgb(tl.compose(t), bg)).resize(thumb)
        x, y = (k % cols) * thumb[0], (k // cols) * thumb[1]
        sheet.paste(im, (x, y))
        d.rectangle([x, y, x + 64, y + 20], fill=(0, 0, 0))
        d.text((x + 4, y + 4), f"{t:.2f}s", fill=(255, 230, 0))
    sheet.save(out)
