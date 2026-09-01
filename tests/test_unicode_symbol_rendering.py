"""Unicode 符号的位图回退渲染测试。"""

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from script.get_img import draw_segments, load_render_font, set_custom_font_path
from script.get_server_info import TextSegment


pytestmark = pytest.mark.text_rendering
TESTS_DIR = Path(__file__).resolve().parent


async def test_unicode_symbol_bitmap_fallback_is_antialiased() -> None:
    """缺字的十字星放大后应保留平滑边缘，避免 UniFont 的像素锯齿。"""
    set_custom_font_path(str(TESTS_DIR / "SarasaUiSC-Regular.ttf"))
    try:
        font = await load_render_font(24)
        assert font.source_for("✦") == "unifont"

        image = Image.new("RGB", (80, 80), "black")
        draw_segments(
            ImageDraw.Draw(image), 20, 20, [TextSegment("✦")], font, (255, 255, 255),
        )

        # 抗锯齿边缘应存在介于背景和前景之间的灰度像素。
        assert any(0 < pixel[0] < 255 for pixel in image.get_flattened_data())
    finally:
        set_custom_font_path(None)
