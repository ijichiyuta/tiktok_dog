"""勘コピ: Instagram リール「おすすめに載る新ルール」(73.6s) のテロップ・エフェクト全再現。

人物以外 (テロップ / 図解 / 光エフェクト / トランジション / 効果音) をすべて再構成している。
    python -m reelfx render projects/insta_reco_rule/timeline.py -o out/insta_reco_rule_fx.mp4 --alpha out/insta_reco_rule_fx.mov
実写に重ねる:
    python -m reelfx render projects/insta_reco_rule/timeline.py -o out/final.mp4 --footage my_talk.mp4 --audio my_talk.mp4
"""
from reelfx import *  # noqa
from reelfx.elements import kf
from reelfx.easing import ease_in_out, ease_out_cubic

DUR = 73.58
CX = 540


def build():
    tl = Timeline(DUR)
    A = tl.add

    # ------------------------------------------------------------------ 全体
    A(NeonSwirls(seed=7, intensity=0.6, n=10, opacity=kf([(0, 0), (0.4, 1)])), 2.45, DUR)
    tl.fx("vignette", 0, DUR, strength=1.5)  # 実写合成時のみ有効 (スポットライト感)

    # ============================================================ 0.0 – 2.45 OP
    A(LensStreak(p0=(300, 980), p1=(430, 830), length=240, angle=-60), 0.0, 0.3, sfx="swish")
    op_out = glitch(0.12)
    A(Text("いき\nなり", 470, "brush_bg", style_kw=dict(line_gap=0.55), at=(575, 1110), opacity=0.92,
           enter=combo(zoom_in(0.25, 1.5), blur_in(0.25, 16)), exit=op_out, drift=0.02), 0.5, 2.45, sfx="hit")
    A(EnergySlash(center=(520, 930), radius=(470, 300), angle=-25, arc=(160, 330), thickness=60), 0.55, 0.9,
      sfx="whoosh")
    A(Lightning(a=(120, 640), b=(640, 1500), branches=4, flash=0.12), 0.62, 1.02, sfx="zap")
    A(Lightning(a=(900, 700), b=(420, 1350), branches=2, flash=0.0, width=2), 0.72, 0.98)
    tl.fx("flash", 0.6, 0.8, color="#7fe9ff", peak=0.35)
    A(Text("今日", 271, "gold_mincho", at=(CX, 885), enter=glitch(0.3), exit=op_out, drift=0.012), 0.1, 2.45,
      sfx="glitch")
    A(Text("Instagram", 90, "latin_silver", at=(CX, 1010), enter=glitch(0.3), exit=op_out, drift=0.012), 0.12, 2.45)
    A(Text("おすすめ{に載る|0.36}", 210, "gold_mincho", at=(555, 1175),
           enter=combo(slide(0.3, 420, 0), flash_in(0.35)), exit=op_out, drift=0.012), 0.88, 2.45, sfx="whoosh")
    A(Text("新ルール\n{でしたね|0.55}", 144, "silver_mincho", style_kw=dict(line_gap=-0.05), at=(525, 1350),
           enter=wipe(0.22), exit=op_out, drift=0.012), 1.38, 2.45, sfx="swish")
    tl.fx("glitch", 2.25, 2.45, sfx="glitch", amount=1.2)

    # ============================================================ 2.5 – 6.9 積み上がるボックス
    # 新しいボックスが上に入り、既存は下へ押し出される
    slot = [1085, 1395, 1720]
    stack_exit = 6.9
    boxes = [
        (2.5, "#タグ全部消したり", "purple", 150),
        (3.7, "インスタの\n必須設定変えたり", "magenta", 250),
        (4.9, "キャプションに\nキーワード書いてみたり", "olive_gold", 250),
    ]
    pushes = [b[0] for b in boxes]
    for k, (t0, txt, st, h) in enumerate(boxes):
        pts = [(0, slot[0])]
        for j, tp in enumerate(pushes[k + 1:]):
            rel = tp - t0
            pts += [(rel, slot[j]), (rel + 0.25, slot[j + 1])]
        yfn = kf(pts, ease_out_cubic)
        A(Box(txt, st, size=62, w=800, h=h, at=(lambda t, f=yfn: (CX, f(t))), enter=streak(0.3),
              exit=blur_in(0.15)), t0, stack_exit, sfx="whoosh")
    A(Text("もう全て", 198, "silver_gothic", style_kw=dict(skew=0.12), at=(CX, 1060), enter=slam(0.2),
           exit=glitch(0.12), emph=[(0.35, shine(0.4))]), 5.9, stack_exit, sfx="hit")

    # ============================================================ 7.0 – 12.9 理解すべき
    A(Text("この動画を見ると", 116, "silver_gothic", style_kw=dict(skew=0.1), at=(CX, 960), enter=pop(),
           exit=fade(0.08)), 7.0, 7.95, sfx="pop")
    g_out = combo(blur_in(0.25, 14, 1.0), fade(0.25))
    L = 470
    A(Text("あなたの動画が", 113, "silver_mincho", style_kw=dict(skew=0.14), at=(L, 760), enter=slide(0.25, -350),
           exit=g_out), 8.0, 12.55, sfx="swish")
    A(Box("おすすめに載る仕組み", "gold", 60, w=760, h=100, at=(L, 870), enter=streak(0.3), exit=g_out), 8.15, 12.55)
    A(Text("{理|1.35}解すべき", 116, "silver_mincho", style_kw=dict(skew=0.14), at=(L - 30, 1040),
           enter=blur_in(0.3), exit=g_out), 9.0, 12.55, sfx="pop")
    A(Box("真のユーザーの正体", "gold", 60, w=760, h=100, at=(L, 1160), enter=streak(0.3), exit=g_out), 9.4, 12.55,
      sfx="swish")
    A(Text("{絶|1.35}対守るべき", 116, "silver_mincho", style_kw=dict(skew=0.14), at=(L, 1340),
           enter=slide(0.25, 380), exit=g_out), 10.4, 12.55, sfx="swish")
    A(Box("たった1つのこと", "gold", 60, w=760, h=100, at=(L, 1460), enter=streak(0.3), exit=g_out,
          emph=[(0.8, shine())]), 10.9, 12.55, sfx="swish")
    A(Text("全て理解\nできます", 185, "silver_gothic", style_kw=dict(skew=0.1), at=(CX, 1060), enter=slam(0.2),
           exit=glitch(0.15)), 12.35, 12.95, sfx="hit")

    # ============================================================ 13.0 – 18.4
    A(Text("まずインスタは", 116, "white_gothic", at=(CX, 900), enter=pop(), exit=fade(0.06)), 13.0, 13.45, sfx="pop")
    A(Text("あなたが\nアップする動画を", 111, "silver_gothic", style_kw=dict(skew=0.08), at=(CX, 910),
           enter=pop(), exit=fade(0.1)), 13.5, 15.45, sfx="pop")
    A(Text("必ず", 330, "silver_mincho", at=(CX, 1060), opacity=0.35, enter=blur_in(0.4, 30, 1.4),
           exit=fade(0.1)), 14.4, 15.45)
    A(Text("おすすめに載せ", 122, "gold_mincho", style_kw=dict(skew=0.14), at=(CX, 1060), enter=wipe(0.25),
           exit=fade(0.1)), 14.45, 15.45, sfx="swish")
    A(Text("100再生前後は\n{必ず担保させます|0.95|gold_gothic}", 109, "silver_gothic", style_kw=dict(skew=0.14),
           at=(CX, 950), enter=stretch(0.25), exit=fade(0.1), emph=[(0.9, shine(0.5))]), 15.5, 17.45, sfx="whoosh")
    A(Text("そこから\nインスタAIが", 119, "white_gothic", at=(CX, 930), enter=pop(), exit=fade(0.08)), 17.5, 18.45,
      sfx="pop")

    # ============================================================ 18.5 – 26.9 反応率グリッド & リーチメーター
    grid = [("いいね率", 18.5, 0, 0), ("コメント率", 19.0, 0, 1), ("保存率", 19.5, 1, 0), ("シェア率", 19.75, 1, 1),
            ("視聴維持率", 20.05, 2, 0), ("視聴完了率", 20.5, 2, 1)]
    gx, gy, gdx, gdy = (292, 788), 1000, None, 160
    shrink_at = 22.0
    gc = (540, 1160)       # グリッド中心 (縮小の基準)
    dst = (540, 1560)      # 縮小後の中心
    for txt, t0, r, c in grid:
        x, y = gx[c], gy + r * gdy
        rel = shrink_at - t0
        fx_ = kf([(0, x), (rel, x), (rel + 0.3, dst[0] + (x - gc[0]) * 0.45)], ease_out_cubic)
        fy_ = kf([(0, y), (rel, y), (rel + 0.3, dst[1] + (y - gc[1]) * 0.45)], ease_out_cubic)
        sc = kf([(0, 1), (rel, 1), (rel + 0.3, 0.45)], ease_out_cubic)
        A(Box(txt, "gold", 60, w=470, h=124, at=(lambda t, a=fx_, b=fy_: (a(t), b(t))), scale=sc,
              enter=pop(0.25, 1.3), exit=fade(0.15)), t0, 23.0, sfx="pop")
    fw_y = kf([(0, 1460), (0.6, 1460), (0.9, 1760)], ease_out_cubic)
    fsc = kf([(0, 1), (0.6, 1), (0.9, 0.45)], ease_out_cubic)
    A(Box("フォロー率", "gold", 56, w=560, h=110, at=(lambda t: (540, fw_y(t))), scale=fsc, enter=streak(0.3),
          exit=fade(0.15), emph=[(0.3, shine())]), 21.4, 23.0, sfx="swish")
    A(Text("などの", 76, "white_gothic", at=(CX, 885), enter=pop(), exit=blur_in(0.2)), 22.0, 26.95)
    # 白枠 + 下から金色が満ちる
    A(Graphic(fn=lambda t: _fill_frame(t, 760, 180), at=(CX, 1035), enter=pop(0.25, 1.2), exit=blur_in(0.2)),
      22.0, 26.95, sfx="pop")
    A(Text("ユーザーからの\n反応率", 97, "gold_gothic", style_kw=dict(line_gap=-0.02), at=(CX, 1035),
           enter=pop(0.25, 1.2), exit=blur_in(0.2)), 22.05, 26.95)
    A(Meter(760, 74, frac=kf([(0, 0.02), (0.5, 0.1), (1.2, 0.26), (2.0, 0.5), (2.8, 0.74)], ease_in_out),
            at=(CX, 1245), enter=streak(0.3), exit=blur_in(0.2)), 23.0, 26.95, sfx="whoosh")
    A(Text("みたいな感じで\n{リーチさせて|1.35}\n{いきます|1.35}", 103, "silver_gothic",
           style_kw=dict(skew=0.12, line_gap=-0.05), at=(CX, 1100), rot=-7, enter=slam(0.2), exit=blur_in(0.2)),
      25.9, 26.95, sfx="hit")

    # ============================================================ 27.0 – 33.4 再生時間
    A(Text("それ以外に\n{動画秒数の長さ|1|gold_gothic}", 105, "white_gothic", at=(CX, 1090), enter=pop(),
           exit=fade(0.1)), 27.0, 27.95, sfx="pop")
    phone_x = kf([(0, 540), (4.0, 540), (4.3, 950)], ease_out_cubic)
    phone_sc = kf([(0, 1), (4.0, 1), (4.3, 0.82)], ease_out_cubic)
    A(Phone(170, 320, at=(lambda t: (phone_x(t), 1560)), scale=phone_sc, enter=pop(), exit=fade(0.15)), 27.0, 34.4)
    bar_w = kf([(0, 800), (4.0, 800), (4.3, 780)])
    A(ProgressBar(800, 40, frac=kf([(0, 0.02), (1, 0.12), (4, 0.3), (5.5, 0.62), (7.3, 0.75)], ease_in_out),
                  marker=None, at=(lambda t: (500 if t > 4.2 else 540, 1600)), enter=streak(0.3), exit=fade(0.15)),
      27.0, 32.6)
    A(ProgressBar(780, 40, frac=kf([(0, 0.62), (1.8, 0.75)], ease_in_out), marker="閾値", at=(500, 1600),
                  enter=fade(0.05), exit=fade(0.15)), 32.6, 34.4)
    tl.fx("tint", 28.0, 31.0, color="#6d6cff", amount=0.75)
    A(Text("「", 70, "white_gothic", at=(95, 1030), enter=pop(), exit=fade(0.1)), 28.0, 31.0)
    A(Text("」", 70, "white_gothic", at=(990, 1250), enter=pop(), exit=fade(0.1)), 28.0, 31.0)
    A(Text("長く見られたコンテンツ\nほど評価するけど最初の\nハードルは超えろよ？", 76, "white_gothic", align="left",
           at=(CX, 1130), enter=typewriter(2.6), exit=fade(0.1)), 28.05, 31.0)
    for i in range(24):
        tl.cue(28.05 + i * 0.11, "type", 0.5)
    A(Text("っていう\n{動画最低|1|gold_gothic}\n{継続時間の閾値|1|gold_gothic}を\n超えているか", 87, "white_gothic",
           align="left", at=(420, 1150), enter=slide(0.25, -300), exit=fade(0.1)), 31.0, 33.45, sfx="swish")

    # ============================================================ 33.5 – 36.9
    A(Text("これらを見て\n{拡散させるか|1|gold_gothic}\n決めてます", 119, "white_gothic", at=(CX, 1010),
           enter=pop(), exit=fade(0.1), emph=[(0.6, pulse())]), 33.45, 34.95, sfx="pop")
    A(Text("ここからが\n{重要|1.35}", 159, "brush_red", at=(CX, 990), enter=slam(0.22, 2.2),
           exit=glitch(0.12), emph=[(0.05, shake(0.3, 16))]), 35.0, 35.95, sfx="hit")
    tl.fx("shake", 35.02, 35.3, amp=14)
    A(Text("あなたも\n経験あると\n思うんですけど", 103, "white_gothic", at=(CX, 1000), enter=pop(), exit=fade(0.1)),
      36.0, 36.95, sfx="pop")

    # ============================================================ 37.0 – 44.9
    A(Bubble("1つの筋トレ動画を\n見たらおすすめ欄が\n全部筋トレ動画に\nなってしまった", 54, at=(360, 860),
             enter=pop(0.3, 0.6), exit=streak(0.25)), 37.0, 40.55, sfx="pop")
    A(Text("実はインスタは\nレコメンド機能を\n使って", 105, "white_gothic", at=(CX, 940), enter=pop(),
           exit=fade(0.1)), 40.7, 42.85, sfx="pop")
    A(Text("{誰に拡散するのか|1|crimson_gothic}\n決めてます", 97, "white_gothic", at=(CX, 900), enter=pop(),
           exit=fade(0.1)), 42.9, 43.95, sfx="pop")
    A(Text("ちなみに\nレコメンド\nっていうのは", 109, "white_gothic", at=(CX, 940), enter=pop(), exit=fade(0.1)),
      44.0, 44.95, sfx="pop")

    # ============================================================ 45.0 – 50.4 レコメンド図解
    A(Phone(230, 430, at=(CX, 1060), enter=zoom_in(0.25), exit=blur_in(0.2)), 45.0, 45.95, sfx="pop")
    for i, y in enumerate((840, 1060, 1280)):
        A(Avatar(62, "gray", at=(250, y), enter=pop(0.25), exit=fade(0.15)), 45.0 + i * 0.05, 45.95)
        A(Avatar(62, "white", at=(830, y), enter=pop(0.25), exit=fade(0.15)), 45.0 + i * 0.05, 46.4 if i == 0 else 45.95)
        for side, x in ((0, 360), (1, 720)):
            fx_ = kf([(0, 540), (0.5, x)], ease_out_cubic)
            fy_ = kf([(0, 1060), (0.5, y)], ease_out_cubic)
            A(Heart(70, at=(lambda t, a=fx_, b=fy_: (a(t), b(t))), enter=zoom_in(0.2), exit=fade(0.2)),
              45.05 + i * 0.08, 45.85)
    tl.cue(45.1, "shine", 0.6)
    for j, x in enumerate((360, 540, 720)):
        A(Avatar(62, "white", at=(x, 850), enter=pop(0.2), exit=fade(0.1)), 45.95 + j * 0.06, 46.5)
    # 3x3 グリッドと枠
    A(AvatarGrid(3, 3, 60, 180, ("blue", "cyan", "violet"), at=(CX, 1010), enter=pop(0.3, 0.6),
                 exit=blur_in(0.2)), 46.5, 50.45, sfx="pop")
    fr_w = kf([(0, 520), (1, 520)])
    fr_h = kf([(0, 190), (0.4, 190), (0.6, 540), (1.0, 540), (1.3, 370)], ease_out_cubic)
    fr_y = kf([(0, 830), (0.4, 830), (0.6, 1010), (1.0, 1010), (1.3, 1100)], ease_out_cubic)
    A(FrameRect(520, 540, 4, "#f2f2f2", 6, size_fn=lambda t: (fr_w(t), fr_h(t)), at=(lambda t: (CX, fr_y(t))),
                enter=pop(0.2, 1.2), exit=fade(0.1)), 46.5, 48.45, sfx="swish")
    A(Graphic(shapes.box(540, 380, "yellow_panel", (5, "#ffffff"), 10), at=(CX, 1100), opacity=0.92,
              enter=wipe(0.2, "lr", False), exit=blur_in(0.2)), 48.4, 50.45, sfx="swish")
    A(AvatarGrid(2, 3, 60, 180, ("cyan", "violet"), at=(CX, 1100), enter=fade(0.1), exit=blur_in(0.2)), 48.4, 50.45)
    A(Box("おすすめ\nしてくれる機能", "black_gold", 80, w=640, h=230, at=(CX, 1130), enter=slam(0.2, 1.8),
          exit=blur_in(0.2), emph=[(0.2, shine(0.45))]), 49.0, 50.45, sfx="hit")
    tl.cue(49.2, "shine", 0.7)

    # ============================================================ 50.5 – 57.4
    A(Text("そしてインスタが\nそのレコメンドを\nする際", 101, "white_gothic", at=(CX, 1000), enter=pop(),
           exit=fade(0.1)), 50.5, 51.95, sfx="pop")
    A(Text("{どんなユーザーを|1|gold_gothic}\n見てるか", 101, "white_gothic", at=(CX, 1010), enter=pop(),
           exit=fade(0.1)), 52.0, 52.95, sfx="pop")
    A(Text("{優先|1.45}\n{ユーザー|1.45}{です|0.4|silver_mincho}", 148, "gold_mincho",
           style_kw=dict(skew=0.1, line_gap=-0.08), at=(CX, 1050), enter=slam(0.22), exit=fade(0.1),
           emph=[(0.4, shine(0.45))]), 53.0, 53.95, sfx="hit")
    A(Text("この優先ユーザー\nっていうのは", 101, "white_gothic", at=(CX, 1010), enter=pop(), exit=fade(0.1)),
      54.0, 54.95, sfx="pop")
    A(Text("動画に\n反応してくれた\nユーザーのこと", 101, "white_gothic", at=(CX, 1030), enter=pop(),
           exit=fade(0.08)), 55.0, 55.55, sfx="pop")
    A(Text("動画に\n反応してくれた\nユーザーのこと", 101, "gold_gothic", at=(CX, 1030), enter=wipe(0.25),
           exit=fade(0.1), emph=[(0.35, shine())]), 55.45, 56.45, sfx="swish")
    A(Text("僕の動画に\nいつも", 105, "white_gothic", at=(CX, 1000), enter=pop(), exit=fade(0.1)), 56.5, 57.45,
      sfx="pop")

    # ============================================================ 57.5 – 63.0
    A(Text("いいねなどをして", 82, "white_gothic", at=(CX, 900), enter=pop(), exit=fade(0.1)), 57.5, 59.45, sfx="pop")
    A(Text("反応してくれる\nあなたですね", 111, "gold_gothic", at=(CX, 1040),
           enter=combo(wipe(0.35), rgb_split(0.3, 10)), exit=fade(0.1), emph=[(0.05, shine(0.4))]),
      58.0, 59.45, sfx="shine")
    A(Text("じゃあ結局\n{何を大事に|1|crimson_gothic}\n{すればいいか|1|crimson_gothic}", 113, "white_gothic",
           at=(CX, 1030), enter=pop(), exit=fade(0.1)), 59.5, 60.95, sfx="pop")
    A(Text("1", 336, "gold_mincho", style_kw=dict(skew=0.12), at=(300, 950), enter=slam(0.2), exit=blur_in(0.15)),
      61.0, 63.0, sfx="hit")
    A(Text("アカウント", 93, "silver_gothic", style_kw=dict(skew=0.06), align="left", at=(575, 895),
           enter=slide(0.2, 300), exit=blur_in(0.15)), 61.05, 63.0)
    A(Text("テーマ", 93, "silver_gothic", style_kw=dict(skew=0.06), at=(490, 990), enter=slide(0.2, 300),
           exit=blur_in(0.15)), 61.45, 63.0, sfx="swish")
    A(Text("{一貫性|1.3|gold_gothic}のある\n{発信|1.3}です", 85, "silver_gothic", style_kw=dict(skew=0.1),
           at=(480, 1190), enter=stretch(0.25), exit=blur_in(0.15), emph=[(0.5, shine(0.5))]), 61.95, 63.0,
      sfx="whoosh")

    # ============================================================ 63.0 – 68.4
    A(Text("伸びなくても", 109, "white_gothic", at=(CX, 900), enter=pop(), exit=fade(0.05)), 63.0, 64.0, sfx="pop")
    A(Text("ジャンルを\n変えずに", 109, "white_gothic", at=(CX, 1040), enter=pop(), exit=fade(0.05)), 63.3, 64.0)
    tl.fx("hsmear", 63.85, 64.2, length=260)
    tl.fx("flash", 63.9, 64.15, color="#ffc8ee", peak=0.3, sfx="whoosh")
    A(Text("{一貫した発信|1|gold_gothic}{を|0.5|gold_gothic}\n{続けてください|0.85|crimson_gothic}\n変えずに", 113,
           "white_gothic", style_kw=dict(line_gap=0.02), at=(CX, 1010), enter=combo(fade(0.1), rgb_split(0.2)),
           exit=fade(0.05)), 64.0, 65.5)
    tl.fx("hsmear", 65.45, 65.8, length=300)
    tl.fx("glitch", 65.5, 65.7, amount=0.6, sfx="glitch")
    A(Text("軸をぶらすと\n{おすすめの|1.12|purple_gothic}\n{精度が落ちて|1.12|purple_gothic}", 93, "white_gothic",
           at=(CX, 1010), enter=combo(glitch(0.35, 1.2), rgb_split(0.35, 16)), exit=fade(0.05)), 65.65, 66.95)
    A(Text("あなたの\nアカウント\n終わります", 127, "crimson_gothic", style_kw=dict(line_gap=0.02),
           at=(CX, 1060), enter=combo(zoom_in(0.25, 3.2), blur_in(0.25, 18, 1.0)), exit=fade(0.1)), 67.0, 68.45,
      sfx="hit")
    tl.fx("shake", 67.0, 67.4, amp=20)
    tl.fx("rgb", 67.0, 67.3, px=12)

    # ============================================================ 68.5 – 73.58 まとめ & CTA
    A(Text("{明|1.7|gold_mincho}{日|1.25|gold_mincho}今回の動画", 76, "silver_gothic", align="left",
           style_kw=dict(skew=0.08), at=(420, 900), enter=slide(0.25, -300), exit=streak(0.2)), 68.5, 70.8,
      sfx="swish")
    A(Box("おすすめに載る仕組み", "gold", 60, w=760, h=100, at=(420, 985), enter=streak(0.3), exit=streak(0.2)),
      68.6, 70.8)
    A(Box("踏まえたうえで", "black_tag", 76, w=150, h=660, vertical=True, at=(975, 1220), enter=drop(0.3, 700),
          exit=blur_in(0.15)), 70.0, 72.7, sfx="whoosh")
    A(Text("{意|1.7|gold_mincho}図的に", 80, "silver_gothic", align="left", style_kw=dict(skew=0.08),
           at=(400, 900), enter=wipe(0.25), exit=blur_in(0.15)), 70.7, 72.7, sfx="swish")
    A(Box("バズらせる方法", "gold", 62, w=760, h=104, at=(420, 985), enter=wipe(0.25), exit=blur_in(0.15),
          emph=[(0.3, shine())]), 70.75, 72.7)
    A(Text("徹底解説", 185, "gold_mincho", style_kw=dict(skew=0.08), at=(420, 1130), enter=wipe(0.22),
           exit=blur_in(0.15), emph=[(0.45, shine(0.5))]), 71.7, 72.7, sfx="hit")
    A(Text("するので", 58, "white_gothic", at=(640, 1215), enter=fade(0.2), exit=blur_in(0.15)), 71.9, 72.7)
    tl.fx("hsmear", 72.55, 72.8, length=200)
    A(Text("おさるをフォロー\nしておいて", 93, "gold_gothic", at=(CX, 880), enter=pop(), exit=fade(0.1)), 72.7, DUR,
      sfx="pop")
    hy = kf([(0, 1010), (0.35, 1090), (0.5, 1160)], ease_out_cubic)
    A(TapHand(170, tap_at=(0.5,), at=(lambda t: (580, hy(t))), enter=slide(0.2, 0, 150), exit=fade(0.1)),
      72.7, DUR)
    tl.cue(73.2, "tap", 1.0)
    return tl


def _fill_frame(t, w, h):
    """白枠の内側を下から金色が満ちていく (反応率)"""
    from reelfx.core import Sprite, blit
    from reelfx.easing import clamp01
    import numpy as np
    frac = kf([(0, 0), (1.5, 0.0), (2.0, 0.18), (2.6, 0.45), (3.2, 0.58)], ease_in_out)(t)
    base = shapes.box(w, h, [(0, "#101010"), (1, "#000000")], None, 0)
    img = base.img.copy() * 0.55
    fh = int((h - 8) * frac)
    if fh > 1:
        fb = shapes.box(w - 8, fh, "gold_box", None, 0)
        blit(img, fb, base.ax, base.ay + h / 2 - 4 - fh / 2)
    fr = shapes.frame_rect(w, h, 4, "#f0f0f0", 0, shadow=False)
    blit(img, fr, base.ax, base.ay)
    return Sprite(img, base.ax, base.ay)
