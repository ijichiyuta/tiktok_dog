"""デザイントークン: 色・グラデーション・テキスト／ボックスのスタイルプリセット。

リファレンス (ダーク背景 × 紫ネオン × オリーブゴールドの金属文字) の配色を採取して定義。
"""

# ---- 基本色 -------------------------------------------------------------
C = dict(
    gold_hi="#fffbd6", gold="#e7e08a", gold_mid="#cfc65a", gold_lo="#8f8820", olive="#a9a22c",
    silver_hi="#ffffff", silver="#e4e4ea", silver_lo="#9a9aa6",
    crimson_hi="#ff8a8a", crimson="#e0303a", crimson_lo="#7c0c16",
    ink_red="#9c0f18", blood="#5e060c",
    purple_hi="#f0c8ff", purple="#b25cf0", purple_lo="#5a1ca8",
    neon_violet="#8a3cff", neon_magenta="#d23cff", neon_blue="#4a5cff",
    navy="#27206a", magenta="#b01e8c",
    green="#35d14a", green_lo="#138a24",
    shadow="#000000", dark="#0b0b12", white="#ffffff", cyan="#63f2ff",
)

# 金属グラデーション (上→下)。中央付近に "水平線" を作ると金属っぽくなる
GRAD = dict(
    gold=[(0, "#fffde8"), (0.38, "#efe995"), (0.52, "#c9c04a"), (0.78, "#b3aa33"), (1, "#e2da78")],
    gold_flat=[(0, "#f4efa8"), (1, "#bdb445")],
    silver=[(0, "#ffffff"), (0.45, "#f1f1f5"), (0.55, "#b9b9c4"), (1, "#e9e9ef")],
    white=[(0, "#ffffff"), (1, "#ffffff")],
    cream=[(0, "#fffef2"), (1, "#f3eecb")],
    crimson=[(0, "#ff7b7b"), (0.5, "#e02a35"), (1, "#8e1019")],
    ink_red=[(0, "#b0141e"), (1, "#5e060c")],
    purple=[(0, "#f3d4ff"), (0.45, "#c07cf5"), (0.55, "#8d3ee0"), (1, "#b684ff")],
    green=[(0, "#6ff07b"), (1, "#1c9c2e")],
    gold_box=[(0, "#e9e36f"), (0.5, "#c5bd3b"), (1, "#8e8718")],
    purple_box=[(0, "#3a2a90"), (1, "#261a5e")],
    magenta_box=[(0, "#c42aa0"), (1, "#7a1a9a")],
    black_box=[(0, "#161616"), (1, "#050505")],
    bubble=[(0, "#fafafa"), (1, "#cfcfd4")],
    yellow_panel=[(0, "#ffd84a"), (1, "#f0b020")],
)

_SH = dict(color="#000000", dx=6, dy=9, blur=8, opacity=1.0)  # 標準ドロップシャドウ
_SH_SOFT = dict(color="#000000", dx=0, dy=6, blur=14, opacity=0.9)

# ---- テキストスタイル ------------------------------------------------------
# fill: グラデ名 or 色 / strokes: [(太さ, 色)] 外側から / shadow / glow / bevel
TEXT_STYLES = {
    # 金属オリーブゴールド明朝 (メイン見出し)
    "gold_mincho": dict(font="mincho", fill="gold", strokes=[(5, "#2e2b05")], embolden=0.012, shadow=_SH, bevel=0.55),
    # 同ゴシック版
    "gold_gothic": dict(font="gothic", fill="gold", strokes=[(4, "#2e2b05")], shadow=_SH, bevel=0.5),
    # 白銀明朝 (Instagram/新ルール/理解すべき)
    "silver_mincho": dict(font="mincho", fill="silver", strokes=[(4, "#1d1d24")], embolden=0.012, shadow=_SH, bevel=0.4),
    "silver_gothic": dict(font="gothic", fill="silver", strokes=[(2, "#2a2a33")], shadow=_SH, bevel=0.4),
    # 白ゴシック + 黒の柔らかい影 (標準字幕)
    "white_gothic": dict(font="gothic", fill="white", strokes=[(3, "#141414")], shadow=_SH_SOFT),
    # 赤 (警告/強調)
    "crimson_gothic": dict(font="gothic", fill="crimson", strokes=[(3, "#2a0205")], shadow=_SH, bevel=0.35),
    "crimson_mincho": dict(font="mincho", fill="crimson", strokes=[(3, "#2a0205")], shadow=_SH, bevel=0.35),
    # 筆文字赤 (ここからが重要 / 背景巨大文字)
    "brush_red": dict(font="mincho", fill="crimson", strokes=[(3, "#2a0205")], shadow=_SH, bevel=0.3, embolden=0.022, rough=0.012),
    "brush_bg": dict(font="mincho", fill="ink_red", strokes=[], shadow=None, glow=None, embolden=0.03, rough=0.014),
    # 紫メタル
    "purple_gothic": dict(font="gothic", fill="purple", strokes=[(2, "#1e0838")], shadow=_SH, bevel=0.35),
    # ボックス内ラベル (白〜クリーム + 濃い影)
    "label": dict(font="gothic", fill="cream", strokes=[(2, "#2a2805")],
                  shadow=dict(color="#000000", dx=2, dy=3, blur=2, opacity=0.8)),
    "label_dark": dict(font="gothic", fill="#232323", strokes=[], shadow=None),
    # 欧文セリフ
    "latin_silver": dict(font="mincho", fill="silver", strokes=[(2, "#1d1d24")], shadow=_SH, tracking=0.12),
    # 数字インパクト
    "gold_dela": dict(font="dela", fill="gold", strokes=[(3, "#3b3708")], shadow=_SH, bevel=0.5),
    "white_dela": dict(font="dela", fill="white", strokes=[(3, "#111")], shadow=_SH_SOFT),
}

# ---- ボックススタイル ------------------------------------------------------
BOX_STYLES = {
    "gold": dict(fill="gold_box", border=(3, "#f7f3b8"), shadow=_SH_SOFT, text="label", radius=2, hl=0.35),
    "purple": dict(fill="purple_box", border=(3, "#8f8f9a"), shadow=_SH_SOFT, text="label", radius=2, hl=0.2),
    "magenta": dict(fill="magenta_box", border=(3, "#8f8f9a"), shadow=_SH_SOFT, text="label", radius=2, hl=0.2),
    "olive_gold": dict(fill="gold_box", border=(3, "#8f8f9a"), shadow=_SH_SOFT, text="label", radius=2, hl=0.25),
    "black_gold": dict(fill="black_box", border=(5, "#f1f1f1"), shadow=_SH_SOFT, text="gold_gothic", radius=3, hl=0.0),
    "frame": dict(fill=None, border=(3, "#e8e8e8"), shadow=None, text="gold_gothic", radius=2, hl=0.0),
    "black_tag": dict(fill="black_box", border=None, shadow=_SH_SOFT, text="white_gothic", radius=0, hl=0.0),
    "yellow_panel": dict(fill="yellow_panel", border=(4, "#ffffff"), shadow=_SH_SOFT, text="label", radius=8, hl=0.2),
}
