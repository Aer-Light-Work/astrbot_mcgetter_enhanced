#!/usr/bin/env python3
"""
图片生成 mock 测试（不依赖真实网络）
测试 presets 系统的各个组件与多种样式图片的生成
"""

import asyncio
import sys
import os
import io
import base64
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# 使用公共 astrbot mock
from mock_astrbot import setup_mock_astrbot
setup_mock_astrbot()

from script.get_server_info import (
    parse_section_sign_text,
    parse_with_mcstatus,
    manual_parse_motd,
    parse_custom_note_text,
    parse_mc_color,
    TextSegment,
    MotdLine,
)
from script.preset_manager import get_preset_manager, PresetManager
from script.get_img import (
    generate_server_info_image, load_font, wrap_segments_to_lines,
    set_custom_font_path, load_render_font, measure_text, draw_segments, _unifont,
)
from PIL import Image, ImageDraw


def test_parse_section_sign_text():
    """测试 § 格式代码解析"""
    print("=" * 60)
    print("测试: parse_section_sign_text")
    print("=" * 60)

    # 测试颜色代码
    text = "§a绿色文字 §c红色文字 §r重置文字"
    segments = parse_section_sign_text(text)
    print(f"输入: {repr(text)}")
    for seg in segments:
        print(f"  段: text={repr(seg.text)}, color={seg.color}, bold={seg.bold}, italic={seg.italic}")
    assert len(segments) == 3
    assert segments[0].color == (85, 255, 85)  # §a 绿色
    assert segments[1].color == (255, 85, 85)  # §c 红色
    assert segments[2].color is None  # §r 重置
    print("✓ 颜色代码测试通过\n")

    # 测试格式代码
    text = "§l粗体 §o斜体 §n下划线 §m删除线"
    segments = parse_section_sign_text(text)
    print(f"输入: {repr(text)}")
    for seg in segments:
        print(f"  段: text={repr(seg.text)}, bold={seg.bold}, italic={seg.italic}, underline={seg.underline}, strikethrough={seg.strikethrough}")
    assert len(segments) == 4
    assert segments[0].bold is True
    assert segments[1].italic is True
    assert segments[2].underline is True
    assert segments[3].strikethrough is True
    print("✓ 格式代码测试通过\n")

    # 测试组合
    text = "§a§l绿色粗体 §c§o红色斜体"
    segments = parse_section_sign_text(text)
    print(f"输入: {repr(text)}")
    for seg in segments:
        print(f"  段: text={repr(seg.text)}, color={seg.color}, bold={seg.bold}, italic={seg.italic}")
    assert len(segments) == 2
    assert segments[0].color == (85, 255, 85) and segments[0].bold is True
    assert segments[1].color == (255, 85, 85) and segments[1].italic is True
    print("✓ 组合测试通过\n")

    # 测试 1.16+ 十六进制颜色 §#RRGGBB（渐变色）
    text = "§#ffcd1a我§#ffbf26能§#ffb032吞§#ffa23e下§#ff934a玻§#ff8556璃§#ff7661而§#ff686d不§#ff5979伤§#ff4b85身§#ff3c91体§#ff2e9d。"
    segments = parse_section_sign_text(text)
    print(f"输入: {repr(text[:20])}...")
    for seg in segments:
        print(f"  段: text={repr(seg.text)}, color={seg.color}")
    assert len(segments) == 12
    assert segments[0].text == "我"
    assert segments[0].color == (255, 205, 26)  # #ffcd1a
    assert segments[-1].text == "。"
    assert segments[-1].color == (255, 46, 157)  # #ff2e9d
    print("✓ §#RRGGBB 十六进制颜色(渐变)测试通过\n")

    # 测试无格式代码
    text = "普通文字"
    segments = parse_section_sign_text(text)
    assert len(segments) == 1
    assert segments[0].text == "普通文字"
    assert segments[0].color is None
    print("✓ 无格式代码测试通过\n")


def test_parse_mc_color():
    """测试颜色解析"""
    print("=" * 60)
    print("测试: parse_mc_color")
    print("=" * 60)

    assert parse_mc_color("a") == (85, 255, 85)
    assert parse_mc_color("#FF0000") == (255, 0, 0)
    assert parse_mc_color("red") == (255, 85, 85)
    assert parse_mc_color("reset") is None
    assert parse_mc_color("") is None
    print("✓ 颜色解析测试通过\n")


def test_parse_custom_note_text():
    """测试自定义备注文本解析"""
    print("=" * 60)
    print("测试: parse_custom_note_text")
    print("=" * 60)

    # 测试 <color:#hex> 标签
    text = "<color:#FF0000>红色文字</color> 普通文字"
    segments = parse_custom_note_text(text)
    print(f"输入: {repr(text)}")
    for seg in segments:
        print(f"  段: text={repr(seg.text)}, color={seg.color}")
    assert len(segments) >= 2
    assert segments[0].color == (255, 0, 0)
    print("✓ <color:#hex> 标签测试通过\n")

    # 测试混合使用
    text = "§a绿色 <color:#FF00FF>品红</color> §c红色"
    segments = parse_custom_note_text(text)
    print(f"输入: {repr(text)}")
    for seg in segments:
        print(f"  段: text={repr(seg.text)}, color={seg.color}")
    print("✓ 混合使用测试通过\n")


def test_parse_motd():
    """测试 MOTD 解析"""
    print("=" * 60)
    print("测试: parse_motd")
    print("=" * 60)

    # 测试纯字符串 MOTD
    motd = "§a第一行\n§c第二行"
    lines = manual_parse_motd(motd)
    print(f"输入: {repr(motd)}")
    print(f"  行数: {len(lines)}")
    for i, line in enumerate(lines):
        print(f"  行{i}: {line.plain_text()}")
        for seg in line.segments:
            print(f"    段: text={repr(seg.text)}, color={seg.color}")
    assert len(lines) == 2
    assert lines[0].plain_text() == "第一行"
    assert lines[1].plain_text() == "第二行"
    print("✓ MOTD 解析测试通过\n")

    # 测试 dict 格式 MOTD
    motd_dict = {
        "text": "",
        "extra": [
            {"text": "Hello ", "color": "green"},
            {"text": "World", "color": "red", "bold": True},
        ]
    }
    lines = manual_parse_motd(motd_dict)
    print(f"输入: {motd_dict}")
    for i, line in enumerate(lines):
        print(f"  行{i}: {line.plain_text()}")
        for seg in line.segments:
            print(f"    段: text={repr(seg.text)}, color={seg.color}, bold={seg.bold}")
    assert len(lines) == 1
    assert lines[0].plain_text() == "Hello World"
    print("✓ dict 格式 MOTD 测试通过\n")


async def test_preset_manager():
    """测试 PresetManager"""
    print("=" * 60)
    print("测试: PresetManager")
    print("=" * 60)

    pm = PresetManager()
    presets = pm.list_presets()
    print(f"可用 presets: {presets}")
    assert "rich" in presets
    assert "simple" in presets

    rich = pm.get_preset("rich")
    print(f"rich preset name: {rich.get('name')}, layout: {rich.get('layout')}")
    assert rich.get("name") == "丰富样式"

    simple = pm.get_preset("simple")
    print(f"simple preset name: {simple.get('name')}, layout: {simple.get('layout')}")
    assert simple.get("name") == "简洁样式"

    default = pm.get_preset()
    print(f"default preset: {default.get('name')}")
    assert default.get("name") == "丰富样式"  # 默认是 rich

    print("✓ PresetManager 测试通过\n")


async def test_generate_rich_image():
    """测试生成 rich 样式图片（mock，不依赖网络）"""
    print("=" * 60)
    print("测试: 生成 rich 样式图片")
    print("=" * 60)

    from script.get_server_info import manual_parse_motd

    # 模拟 MOTD
    motd_text = "§a§l欢迎加入服务器！\n§6§o这是一个测试服务器"
    motd_lines = manual_parse_motd(motd_text)

    # 模拟玩家列表（12个，测试超过10个的省略逻辑）
    players = [f"Player{i}" for i in range(1, 11)] + ["LongNamePlayerX", "TestUser"]

    # 生成图片
    img_b64 = await generate_server_info_image(
        players_list=players,
        latency=25,
        server_name="测试服务器",
        plays_max=100,
        plays_online=4,
        server_version="1.20.4",
        icon_base64=None,
        host_address="test.example.com",
        preset_name="rich",
        motd_lines=motd_lines,
        note_text=None,
        group_name="测试群",
    )

    assert img_b64 is not None
    img_data = base64.b64decode(img_b64)
    print(f"图片大小: {len(img_data)} bytes")

    # 校验 rich 图片宽度为 1177px
    img = Image.open(io.BytesIO(img_data))
    print(f"图片尺寸: {img.size[0]}x{img.size[1]}")
    assert img.size[0] == 1177, f"rich 图片宽度应为 1177，实际为 {img.size[0]}"

    # 保存图片到文件
    output_path = Path(__file__).resolve().parent / "test_output_rich.png"
    with open(output_path, "wb") as f:
        f.write(img_data)
    print(f"✓ rich 样式图片已保存到: {output_path}\n")


async def test_generate_rich_image_with_long_motd():
    """测试超长单行 MOTD 自动折行（mock，不依赖网络）"""
    print("=" * 60)
    print("测试: 超长单行 MOTD 自动折行")
    print("=" * 60)

    from script.get_server_info import manual_parse_motd

    # 超长单行 MOTD（确定为 992px 左栏宽度的数倍，保证必然折行）
    motd_text = (
        "这是一个非常非常长的服务器描述文本用于测试自动换行功能是否正常工作"
        "当文本超出左栏宽度限制时应该自动换行到下一行显示以避免文字溢出图片边界"
        "同时保证多行换行后的每一行都保持原有颜色和格式信息不丢失"
    )
    motd_lines = manual_parse_motd(motd_text)
    assert len(motd_lines) == 1, "该测试用例应为单行 MOTD"

    # 直接验证折行逻辑：使用与 _generate_rich_image 相同的参数计算
    # 左栏 MOTD 最大宽度 = (img_width - padding) - name_x - 10
    #   name_x = padding + icon_size + 15 = 30 + 100 + 15 = 145
    #   motd_max_width = (1177 - 30) - 145 - 10 = 992
    text_font = await load_font(22)
    tmp_img = Image.new("RGB", (1177, 10))
    tmp_draw = ImageDraw.Draw(tmp_img)
    motd_max_width = 992
    wrapped = wrap_segments_to_lines(
        tmp_draw, motd_lines[0].segments, text_font, motd_max_width
    )
    print(f"折行后行数: {len(wrapped)}")
    for i, line in enumerate(wrapped):
        print(f"  行{i}: {''.join(s.text for s in line)}")

    # 超长单行 MOTD 应被折成多行
    assert len(wrapped) > 1, f"超长单行 MOTD 应折行为多行，实际为 {len(wrapped)} 行"

    # 生成图片（折行后高度应大于原始单行的等效高度）
    img_b64 = await generate_server_info_image(
        players_list=[],
        latency=36,
        server_name="长MOTD测试服务器",
        plays_max=114514,
        plays_online=3,
        server_version="1.20.4",
        icon_base64=None,
        host_address="test.example.com",
        preset_name="rich",
        motd_lines=motd_lines,
        note_text=None,
        group_name=None,
    )

    assert img_b64 is not None
    img_data = base64.b64decode(img_b64)
    img = Image.open(io.BytesIO(img_data))
    print(f"图片尺寸: {img.size[0]}x{img.size[1]}")
    assert img.size[0] == 1177, f"图片宽度应为 1177，实际为 {img.size[0]}"
    # 无群名、无玩家的 1 行 MOTD 基线高度 = 30+100+14+24+28+30 = 226
    # 折行后高度应大于基线（3 行 MOTD 实际为 250）
    assert img.size[1] > 226, f"长 MOTD 折行后图片高度应大于基线 226，实际为 {img.size[1]}"

    # 保存图片到文件
    output_path = Path(__file__).resolve().parent / "test_output_rich_long_motd.png"
    with open(output_path, "wb") as f:
        f.write(img_data)
    print(f"✓ 超长单行 MOTD 折行图片已保存到: {output_path}\n")


async def test_custom_font():
    """测试自定义字体路径（使用 tests/SarasaUiSC-Regular.ttf，mock 不依赖网络）"""
    print("=" * 60)
    print("测试: 自定义字体")
    print("=" * 60)

    custom_font = Path(__file__).resolve().parent / "SarasaUiSC-Regular.ttf"
    assert custom_font.exists(), f"测试字体不存在: {custom_font}"

    # 设置自定义字体
    set_custom_font_path(str(custom_font))
    try:
        # 验证字体能正常加载
        test_font = await load_font(22)
        assert test_font is not None, "自定义字体加载失败"

        # 使用自定义字体生成图片
        img_b64 = await generate_server_info_image(
            players_list=["Player1", "Player2"],
            latency=20,
            server_name="字体测试",
            plays_max=100,
            plays_online=2,
            server_version="1.20.4",
            icon_base64=None,
            host_address="font.example.com",
            preset_name="rich",
            motd_lines=None,
            note_text=None,
            group_name="字体测试群",
        )
        assert img_b64 is not None, "自定义字体图片生成失败"
        img_data = base64.b64decode(img_b64)
        print(f"图片大小: {len(img_data)} bytes")

        output_path = Path(__file__).resolve().parent / "test_output_custom_font.png"
        with open(output_path, "wb") as f:
            f.write(img_data)
        print(f"✓ 自定义字体图片已保存到: {output_path}\n")
    finally:
        # 恢复系统默认字体逻辑
        set_custom_font_path(None)


async def test_bold_and_unifont_fallback():
    """验证真实粗体选择与 UniFont 缺字回退，不使用固定像素截图断言。"""
    print("=" * 60)
    print("测试: 粗体字体与 UniFont 回退")
    print("=" * 60)

    custom_font = Path(__file__).resolve().parent / "SarasaUiSC-Regular.ttf"
    custom_bold_font = Path(__file__).resolve().parent / "SarasaUiSC-Bold.ttf"
    assert _unifont.glyph("☃") is not None, "UniFont 应包含测试符号 U+2603"

    set_custom_font_path(str(custom_font), str(custom_bold_font))
    try:
        font = await load_render_font(24)
        assert font.bold is not None, "配置的粗体字体应被加载"
        assert Path(font.bold.path).resolve() == custom_bold_font.resolve(), "粗体段必须使用配置的粗体文件"

        # 用主字体没有的非 BMP 字符验证回退选择；UniFont 包含该字符即可验证逻辑。
        fallback_char = next(chr(cp) for cp in (0x1F0A1, 0x1F4A9, 0x1F300) if _unifont.glyph(chr(cp)))
        assert font.source_for(fallback_char) == "unifont", "主字体缺字时应切换到 UniFont"

        img = Image.new("RGB", (600, 100), "black")
        draw = ImageDraw.Draw(img)
        segments = [TextSegment("普通"), TextSegment("粗体", bold=True), TextSegment(f" {fallback_char} ☃")]
        expected_width = sum(measure_text(draw, seg.text, font, seg.bold) for seg in segments)
        end_x = draw_segments(draw, 20, 30, segments, font, (255, 255, 255))
        assert end_x - 20 == expected_width, "绘制推进宽度必须与测量宽度一致"

        wrapped = wrap_segments_to_lines(draw, [TextSegment(fallback_char * 12)], font, 80)
        assert len(wrapped) > 1, "UniFont 回退字符应参与自动换行"
        assert all(sum(measure_text(draw, seg.text, font, seg.bold) for seg in line) <= 80 for line in wrapped), "换行结果不可超过最大宽度"

        output_path = Path(__file__).resolve().parent / "test_output_bold_unifont.png"
        img.save(output_path)
        print(f"✓ 粗体与 UniFont 测试渲染图已保存到: {output_path}\n")
    finally:
        set_custom_font_path(None)


async def test_non_default_font_without_bold_fallback():
    """验证非默认字体在没有粗体文件时使用无光晕的整数像素粗体 fallback。"""
    print("=" * 60)
    print("测试: 非默认字体的粗体 fallback")
    print("=" * 60)

    custom_font = Path(__file__).resolve().parent / "SarasaUiSC-Regular.ttf"
    # 显式指定不存在的粗体路径，避免测试目录中的 SarasaUiSC-Bold.ttf 被自动猜中。
    set_custom_font_path(str(custom_font), str(custom_font.parent / "missing-bold-font.ttf"))
    try:
        font = await load_render_font(24)
        assert font.bold is None, "未提供粗体文件时应进入 fallback 路径"
        image = Image.new("RGB", (700, 120), "#101010")
        draw = ImageDraw.Draw(image)
        segments = [
            TextSegment("自定义字体："),
            TextSegment("§l粗体 Bold 中文", bold=True),
            TextSegment(" ☃ ", color=(85, 255, 255)),
        ]
        expected_width = sum(measure_text(draw, seg.text, font, seg.bold) for seg in segments)
        end_x = draw_segments(draw, 20, 30, segments, font, (255, 255, 255))
        assert end_x - 20 == expected_width, "fallback 粗体的实际推进宽度必须与测量一致"
        assert end_x <= image.width, "非默认字体案例不应绘制到画布外"

        output_path = Path(__file__).resolve().parent / "test_output_non_default_font_bold_fallback.png"
        image.save(output_path)
        print(f"✓ 非默认字体粗体 fallback 测试渲染图已保存到: {output_path}\n")
    finally:
        set_custom_font_path(None)


async def test_heavier_font_weight_mode():
    """验证整体加重模式以 SemiBold 渲染常规文本、以 Bold 渲染 §l 文本。"""
    print("=" * 60)
    print("测试: 整体加重字体模式")
    print("=" * 60)

    tests_dir = Path(__file__).resolve().parent
    regular_font = tests_dir / "SarasaUiSC-Regular.ttf"
    semibold_font = tests_dir / "SarasaUiSC-SemiBold.ttf"
    bold_font = tests_dir / "SarasaUiSC-Bold.ttf"
    assert all(path.exists() for path in (regular_font, semibold_font, bold_font)), "Sarasa 字重测试字体不完整"

    set_custom_font_path(str(regular_font), heavier_font_weight=True)
    try:
        font = await load_render_font(24)
        assert Path(font.regular.path).resolve() == semibold_font.resolve(), "整体加重模式的常规文本必须使用 SemiBold"
        assert font.bold is not None, "整体加重模式必须加载 Bold"
        assert Path(font.bold.path).resolve() == bold_font.resolve(), "整体加重模式的 §l 文本必须使用 Bold"

        image = Image.new("RGB", (700, 120), "#101010")
        draw = ImageDraw.Draw(image)
        segments = [TextSegment("常规 SemiBold 文字  "), TextSegment("§l粗体 Bold 文字", bold=True)]
        expected_width = sum(measure_text(draw, seg.text, font, seg.bold) for seg in segments)
        end_x = draw_segments(draw, 20, 30, segments, font, (255, 255, 255))
        assert end_x - 20 == expected_width, "整体加重模式的绘制和测量宽度必须一致"

        output_path = tests_dir / "test_output_heavier_font_weight.png"
        image.save(output_path)
        print(f"✓ 整体加重字体测试渲染图已保存到: {output_path}\n")
    finally:
        set_custom_font_path(None)


async def test_generate_simple_image():
    """测试生成 simple 样式图片（mock，不依赖网络）"""
    print("=" * 60)
    print("测试: 生成 simple 样式图片")
    print("=" * 60)

    players = ["Player1", "Player2"]

    img_b64 = await generate_server_info_image(
        players_list=players,
        latency=150,
        server_name="简洁测试",
        plays_max=50,
        plays_online=2,
        server_version="1.20.4",
        icon_base64=None,
        host_address="simple.example.com",
        preset_name="simple",
        motd_lines=None,
        note_text=None,
        group_name=None,
    )

    assert img_b64 is not None
    img_data = base64.b64decode(img_b64)
    print(f"图片大小: {len(img_data)} bytes")

    output_path = Path(__file__).resolve().parent / "test_output_simple.png"
    with open(output_path, "wb") as f:
        f.write(img_data)
    print(f"✓ simple 样式图片已保存到: {output_path}\n")


async def test_generate_with_note():
    """测试带备注的图片生成（mock，不依赖网络）"""
    print("=" * 60)
    print("测试: 带备注的图片生成")
    print("=" * 60)

    note = "§a§l本服拥有专属私人房间系统§r\n§6支持公开房间模式 §b同时支持创建私人房间"
    img_b64 = await generate_server_info_image(
        players_list=[],
        latency=5,
        server_name="备注测试",
        plays_max=200,
        plays_online=10,
        server_version="1.20.4",
        icon_base64=None,
        host_address="note.example.com",
        preset_name="rich",
        motd_lines=None,
        note_text=note,
        group_name="备注测试群",
        display_override={"show_notes": True},
    )

    assert img_b64 is not None
    img_data = base64.b64decode(img_b64)

    output_path = Path(__file__).resolve().parent / "test_output_note.png"
    with open(output_path, "wb") as f:
        f.write(img_data)
    print(f"✓ 带备注图片已保存到: {output_path}\n")


async def test_generate_with_color_tag_note():
    """测试带 <color:#hex> 标签的备注（mock，不依赖网络）"""
    print("=" * 60)
    print("测试: 带 <color:#hex> 标签的备注")
    print("=" * 60)

    note = "<color:#FF55FF>品红色文字</color> <color:#FFFF55>黄色文字</color> §l粗体文字"
    img_b64 = await generate_server_info_image(
        players_list=[],
        latency=10,
        server_name="颜色标签测试",
        plays_max=100,
        plays_online=5,
        server_version="1.20.4",
        icon_base64=None,
        host_address="colortag.example.com",
        preset_name="rich",
        motd_lines=None,
        note_text=note,
        group_name="颜色标签测试群",
        display_override={"show_notes": True},
    )

    assert img_b64 is not None
    img_data = base64.b64decode(img_b64)

    output_path = Path(__file__).resolve().parent / "test_output_colortag.png"
    with open(output_path, "wb") as f:
        f.write(img_data)
    print(f"✓ 颜色标签备注图片已保存到: {output_path}\n")


async def test_generate_hex_gradient():
    """测试十六进制渐变色渲染图片（mock，不依赖网络）"""
    print("=" * 60)
    print("测试: 十六进制渐变色渲染图片")
    print("=" * 60)

    # 用户提供的渐变色十六进制文本
    note = "§#ffcd1a我§#ffbf26能§#ffb032吞§#ffa23e下§#ff934a玻§#ff8556璃§#ff7661而§#ff686d不§#ff5979伤§#ff4b85身§#ff3c91体§#ff2e9d。"
    img_b64 = await generate_server_info_image(
        players_list=[],
        latency=10,
        server_name="渐变色测试",
        plays_max=100,
        plays_online=5,
        server_version="1.20.4",
        icon_base64=None,
        host_address="gradient.example.com",
        preset_name="rich",
        motd_lines=None,
        note_text=note,
        group_name="渐变色测试群",
        display_override={"show_notes": True},
    )

    assert img_b64 is not None
    img_data = base64.b64decode(img_b64)

    output_path = Path(__file__).resolve().parent / "test_output_hex_gradient.png"
    with open(output_path, "wb") as f:
        f.write(img_data)
    print(f"✓ 十六进制渐变色图片已保存到: {output_path}\n")


async def main():
    print("\n" + "=" * 60)
    print("  MC Server Status Plugin - 图片生成 mock 测试")
    print("=" * 60 + "\n")

    # 单元测试
    test_parse_section_sign_text()
    test_parse_mc_color()
    test_parse_custom_note_text()
    test_parse_motd()
    await test_preset_manager()

    # 图片生成测试
    await test_generate_rich_image()
    await test_generate_rich_image_with_long_motd()
    await test_custom_font()
    await test_bold_and_unifont_fallback()
    await test_non_default_font_without_bold_fallback()
    await test_heavier_font_weight_mode()
    await test_generate_simple_image()
    await test_generate_with_note()
    await test_generate_with_color_tag_note()
    await test_generate_hex_gradient()

    print("=" * 60)
    print("  所有测试通过！✓")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())