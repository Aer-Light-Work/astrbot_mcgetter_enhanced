"""纯文字解析、字体选择、测量与换行测试。"""

from pathlib import Path

import pytest
from mcstatus.motd import Motd
from PIL import Image, ImageDraw

from script.get_img import (
    _unifont,
    draw_segments,
    load_render_font,
    measure_text,
    set_custom_font_path,
    wrap_segments_to_lines,
)
from script.get_server_info import (
    TextSegment,
    parse_motd,
    parse_custom_note_text,
    parse_mc_color,
    parse_section_sign_text,
)


pytestmark = pytest.mark.text_rendering
TESTS_DIR = Path(__file__).resolve().parent


def test_parse_section_sign_text() -> None:
    segments = parse_section_sign_text("§a绿色文字 §c红色文字 §r重置文字")
    assert [segment.color for segment in segments] == [
        (85, 255, 85), (255, 85, 85), None,
    ]

    segments = parse_section_sign_text("§l粗体 §o斜体 §n下划线 §m删除线")
    assert len(segments) == 4
    assert segments[0].bold
    assert segments[1].italic
    assert segments[2].underline
    assert segments[3].strikethrough

    segments = parse_section_sign_text("§a§l绿色粗体 §c§o红色斜体")
    assert segments[0].color == (85, 255, 85) and segments[0].bold
    assert segments[1].color == (255, 85, 85) and segments[1].italic
    assert not segments[1].bold, "颜色代码应按 Java 版规则重置已有格式"

    gradient = "§#ffcd1a我§#ffbf26能§#ffb032吞§#ffa23e下§#ff934a玻§#ff8556璃§#ff7661而§#ff686d不§#ff5979伤§#ff4b85身§#ff3c91体§#ff2e9d。"
    segments = parse_section_sign_text(gradient)
    assert len(segments) == 12
    assert (segments[0].text, segments[0].color) == ("我", (255, 205, 26))
    assert (segments[-1].text, segments[-1].color) == ("。", (255, 46, 157))

    segments = parse_section_sign_text("普通文字")
    assert len(segments) == 1
    assert segments[0].text == "普通文字" and segments[0].color is None


def test_parse_mc_color() -> None:
    assert parse_mc_color("a") == (85, 255, 85)
    assert parse_mc_color("#FF0000") == (255, 0, 0)
    assert parse_mc_color("red") == (255, 85, 85)
    assert parse_mc_color("reset") is None
    assert parse_mc_color("") is None


def test_parse_custom_note_text() -> None:
    segments = parse_custom_note_text("<color:#FF0000>红色文字</color> 普通文字")
    assert len(segments) >= 2
    assert segments[0].color == (255, 0, 0)

    segments = parse_custom_note_text("§a绿色 <color:#FF00FF>品红</color> §c红色")
    colors = {segment.color for segment in segments}
    assert {(85, 255, 85), (255, 0, 255), (255, 85, 85)}.issubset(colors)


def test_parse_motd() -> None:
    lines = parse_motd("§a第一行\n\n§c第三行")
    assert [line.plain_text() for line in lines] == ["第一行", "", "第三行"]

    lines = parse_motd({
        "text": "",
        "extra": [
            {"text": "Hello ", "color": "green"},
            {"text": "World", "color": "red", "bold": True},
        ],
    })
    assert len(lines) == 1
    assert lines[0].plain_text() == "Hello World"
    assert lines[0].segments[-1].bold

    motd = Motd.parse({"text": "渐变", "color": "#12abef", "underlined": True})
    lines = parse_motd(motd)
    assert lines[0].segments[0].color == (18, 171, 239)
    assert lines[0].segments[0].underline

    # WebColor 直接写入渲染模型，且不应像 Legacy 颜色代码那样清除继承样式。
    lines = parse_motd({
        "text": "A",
        "bold": True,
        "extra": [{"text": "B", "color": "#123456"}],
    })
    assert [(segment.text, segment.color, segment.bold) for segment in lines[0].segments] == [
        ("A", None, True),
        ("B", (18, 52, 86), True),
    ]


async def test_long_motd_wraps_within_width() -> None:
    motd = (
        "这是一个非常非常长的服务器描述文本用于测试自动换行功能是否正常工作"
        "当文本超出左栏宽度限制时应该自动换行到下一行显示以避免文字溢出图片边界"
        "同时保证多行换行后的每一行都保持原有颜色和格式信息不丢失"
    )
    segments = parse_motd(motd)[0].segments
    font = await load_render_font(22)
    draw = ImageDraw.Draw(Image.new("RGB", (1177, 10)))
    wrapped = wrap_segments_to_lines(draw, segments, font, 992)

    assert len(wrapped) > 1
    assert all(
        sum(measure_text(draw, segment.text, font, segment.bold) for segment in line) <= 992
        for line in wrapped
    )
    assert "".join(segment.text for line in wrapped for segment in line) == motd


async def test_bold_and_unifont_fallback() -> None:
    regular = TESTS_DIR / "SarasaUiSC-Regular.ttf"
    bold = TESTS_DIR / "SarasaUiSC-Bold.ttf"
    assert _unifont.glyph("☃") is not None

    set_custom_font_path(str(regular), str(bold))
    try:
        font = await load_render_font(24)
        assert font.bold is not None
        assert Path(font.bold.path).resolve() == bold.resolve()
        fallback_char = next(
            chr(codepoint)
            for codepoint in (0x1F0A1, 0x1F4A9, 0x1F300)
            if _unifont.glyph(chr(codepoint))
        )
        assert font.source_for(fallback_char) == "unifont"

        image = Image.new("RGB", (600, 100), "black")
        draw = ImageDraw.Draw(image)
        segments = [TextSegment("普通"), TextSegment("粗体", bold=True), TextSegment(f" {fallback_char} ☃")]
        expected = sum(measure_text(draw, segment.text, font, segment.bold) for segment in segments)
        assert draw_segments(draw, 20, 30, segments, font, (255, 255, 255)) - 20 == expected

        wrapped = wrap_segments_to_lines(draw, [TextSegment(fallback_char * 12)], font, 80)
        assert len(wrapped) > 1
        assert all(
            sum(measure_text(draw, segment.text, font, segment.bold) for segment in line) <= 80
            for line in wrapped
        )
    finally:
        set_custom_font_path(None)


async def test_unifont_is_default_without_system_noto(monkeypatch: pytest.MonkeyPatch) -> None:
    """未配置自定义字体且系统没有 Noto Sans 时，完整文本应优先走 UniFont。"""
    import script.get_img as get_img

    set_custom_font_path(None)
    monkeypatch.setattr(get_img, "_load_system_noto_font", lambda _size: None)
    font = await load_render_font(24)

    assert font.use_unifont
    assert font.source_for("中") == "unifont"
    assert font.source_for("A") == "unifont"


async def test_non_default_font_without_bold_uses_measured_fallback() -> None:
    regular = TESTS_DIR / "SarasaUiSC-Regular.ttf"
    set_custom_font_path(str(regular), str(TESTS_DIR / "missing-bold-font.ttf"))
    try:
        font = await load_render_font(24)
        assert font.bold is None
        image = Image.new("RGB", (700, 120), "#101010")
        draw = ImageDraw.Draw(image)
        segments = [
            TextSegment("自定义字体："),
            TextSegment("§l粗体 Bold 中文", bold=True),
            TextSegment(" ☃ ", color=(85, 255, 255)),
        ]
        expected = sum(measure_text(draw, segment.text, font, segment.bold) for segment in segments)
        end_x = draw_segments(draw, 20, 30, segments, font, (255, 255, 255))
        assert end_x - 20 == expected
        assert end_x <= image.width
    finally:
        set_custom_font_path(None)


async def test_heavier_font_weight_mode() -> None:
    regular = TESTS_DIR / "SarasaUiSC-Regular.ttf"
    semibold = TESTS_DIR / "SarasaUiSC-SemiBold.ttf"
    bold = TESTS_DIR / "SarasaUiSC-Bold.ttf"
    assert all(path.exists() for path in (regular, semibold, bold))

    set_custom_font_path(str(regular), heavier_font_weight=True)
    try:
        font = await load_render_font(24)
        assert Path(font.regular.path).resolve() == semibold.resolve()
        assert font.bold is not None and Path(font.bold.path).resolve() == bold.resolve()

        image = Image.new("RGB", (700, 120), "#101010")
        draw = ImageDraw.Draw(image)
        segments = [TextSegment("常规 SemiBold 文字  "), TextSegment("§l粗体 Bold 文字", bold=True)]
        expected = sum(measure_text(draw, segment.text, font, segment.bold) for segment in segments)
        assert draw_segments(draw, 20, 30, segments, font, (255, 255, 255)) - 20 == expected
    finally:
        set_custom_font_path(None)
