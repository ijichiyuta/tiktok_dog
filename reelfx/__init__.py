"""reelfx — テロップ／モーショングラフィックス合成エンジン (縦型ショート動画向け).

主要API:
    from reelfx import *
    tl = Timeline(duration=10)
    tl.add(Text("今日", style="gold_mincho", size=200), 0.5, 3.0, at=(540, 800),
           enter=slam(), exit=glitch_out())
"""
from .core import W, H, FPS, Sprite
from .easing import *  # noqa
from .palette import TEXT_STYLES, BOX_STYLES, C
from .text import TextStyle, render_text
from .anim import *  # noqa
from .elements import *  # noqa
from .fx import *  # noqa
from .timeline import Timeline
from . import shapes
