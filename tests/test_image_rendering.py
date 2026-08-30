"""使用本地 mock 数据生成完整服务器状态图片。"""

import base64
import copy
import io
from pathlib import Path

import pytest
from PIL import Image

import script.get_img as get_img
from script.get_img import generate_server_info_image, load_render_font, set_custom_font_path
from script.get_server_info import parse_motd
from script.preset_manager import BUILTIN_PRESETS


pytestmark = pytest.mark.image_rendering
TESTS_DIR = Path(__file__).resolve().parent


def assert_valid_png(
    encoded: str,
    expected_width: int | None = None,
    output_name: str | None = None,
) -> tuple[int, int]:
    """校验图片；指定名称时同时导出至 tests/ 供人工检查。"""
    data = base64.b64decode(encoded, validate=True)
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    if output_name:
        (TESTS_DIR / f"test_output_mock_{output_name}.png").write_bytes(data)
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        assert image.format == "PNG"
        if expected_width is not None:
            assert image.width == expected_width
        return image.size


async def test_generate_rich_image() -> None:
    encoded = await generate_server_info_image(
        players_list=[f"Player{i}" for i in range(1, 11)] + ["LongNamePlayerX", "TestUser"],
        latency=25, server_name="测试服务器", plays_max=100, plays_online=4,
        server_version="1.20.4", icon_base64=None, host_address="test.example.com",
        preset_name="rich", motd_lines=parse_motd("§a§l欢迎加入服务器！\n§6§o这是一个测试服务器"),
        note_text=None, group_name="测试群",
    )
    assert_valid_png(encoded, 1177, "rich")


async def test_rich_image_uses_configured_title(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rich preset 的 title 必须始终显示，且允许 preset 覆盖默认值。"""
    preset = copy.deepcopy(BUILTIN_PRESETS["rich"])
    preset["title"] = "自定义状态标题"
    captured_titles: list[str] = []
    original = get_img.draw_segments_centered

    def capture_title(*args, **kwargs):
        captured_titles.append("".join(segment.text for segment in args[3]))
        return original(*args, **kwargs)

    monkeypatch.setattr(get_img, "draw_segments_centered", capture_title)
    encoded = await get_img._generate_rich_image(
        players_list=[], latency=1, server_name="测试服务器", plays_max=20,
        plays_online=1, server_version="1.20.4", preset=preset,
    )

    assert_valid_png(encoded, 1177, "rich_custom_title")
    assert captured_titles == ["自定义状态标题"]


async def test_generate_rich_image_with_long_motd() -> None:
    motd = (
        "这是一个非常非常长的服务器描述文本用于测试自动换行功能是否正常工作"
        "当文本超出左栏宽度限制时应该自动换行到下一行显示以避免文字溢出图片边界"
        "同时保证多行换行后的每一行都保持原有颜色和格式信息不丢失"
    )
    encoded = await generate_server_info_image(
        players_list=[], latency=36, server_name="长MOTD测试服务器",
        plays_max=114514, plays_online=3, server_version="1.20.4",
        icon_base64=None, host_address="test.example.com", preset_name="rich",
        motd_lines=parse_motd(motd), note_text=None, group_name=None,
    )
    width, height = assert_valid_png(encoded, 1177, "rich_long_motd")
    assert width == 1177 and height > 226


async def test_generate_rich_image_with_custom_font() -> None:
    regular = TESTS_DIR / "SarasaUiSC-Regular.ttf"
    set_custom_font_path(str(regular))
    try:
        font = await load_render_font(22)
        assert Path(font.regular.path).resolve() == regular.resolve()
        encoded = await generate_server_info_image(
            players_list=["Player1", "Player2"], latency=20, server_name="字体测试",
            plays_max=100, plays_online=2, server_version="1.20.4", icon_base64=None,
            host_address="font.example.com", preset_name="rich", motd_lines=None,
            note_text=None, group_name="字体测试群",
        )
        assert_valid_png(encoded, 1177, "rich_custom_font")
    finally:
        set_custom_font_path(None)


async def test_generate_simple_image() -> None:
    encoded = await generate_server_info_image(
        players_list=["Player1", "Player2"], latency=150, server_name="简洁测试",
        plays_max=50, plays_online=2, server_version="1.20.4", icon_base64=None,
        host_address="simple.example.com", preset_name="simple", motd_lines=None,
        note_text=None, group_name=None,
    )
    width, height = assert_valid_png(encoded, output_name="simple")
    assert width > 0 and height > 0


@pytest.mark.parametrize("note, output_name", [
    ("§a§l本服拥有专属私人房间系统§r\n§6支持公开房间模式 §b同时支持创建私人房间", "rich_section_sign_note"),
    ("<color:#FF55FF>品红色文字</color> <color:#FFFF55>黄色文字</color> §l粗体文字", "rich_color_tag_note"),
    ("§#ffcd1a我§#ffbf26能§#ffb032吞§#ffa23e下§#ff934a玻§#ff8556璃§#ff7661而§#ff686d不§#ff5979伤§#ff4b85身§#ff3c91体§#ff2e9d。", "rich_hex_gradient_note"),
], ids=["section-sign-note", "color-tag-note", "hex-gradient-note"])
async def test_generate_rich_image_with_colored_note(note: str, output_name: str) -> None:
    encoded = await generate_server_info_image(
        players_list=[], latency=10, server_name="备注测试", plays_max=100,
        plays_online=5, server_version="1.20.4", icon_base64=None,
        host_address="note.example.com", preset_name="rich", motd_lines=None,
        note_text=note, group_name="备注测试群", display_override={"show_notes": True},
    )
    assert_valid_png(encoded, 1177, output_name)
