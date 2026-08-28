#!/usr/bin/env python3
"""
真实服务器 ping 获取测试（依赖网络）
通过服务器列表验证 get_server_status 能正确获取服务器状态并生成图片
后续可在此列表中追加其他用于 ping 测试的服务器
"""

import asyncio
import sys
import base64
import io
from pathlib import Path
from PIL import Image

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# 使用公共 astrbot mock
from mock_astrbot import setup_mock_astrbot
setup_mock_astrbot()

from script.get_server_info import get_server_status
from script.get_img import generate_server_info_image, load_render_font, set_custom_font_path

# 用于真实 ping 测试的服务器列表（后续按需追加）
# 注意：默认地址已去敏感化，实际使用时请替换为真实服务器地址
PING_TEST_SERVERS = [
    "127.0.0.1:43596",
]


async def test_ping_server(host: str) -> None:
    """测试从真实服务器获取状态信息并生成图片"""
    print("=" * 60)
    print(f"测试: 真实服务器 ping - {host}")
    print("=" * 60)

    result = await get_server_status(host)
    assert result is not None, f"无法获取服务器 {host} 的状态信息"

    print(f"  服务器:    {result['host']}")
    print(f"  版本:      {result['server_version']}")
    print(f"  在线人数:  {result['plays_online']}/{result['plays_max']}")
    print(f"  延迟:      {result['latency']}ms")
    print(f"  MOTD 行数: {len(result['motd_lines'])}")
    # motd_texts = [line.plain_text() for line in result['motd_lines']]
    print(f"Original MOTD: {result['motd_lines']}")
    # print(f"  MOTD 文本: {' | '.join(motd_texts)}")
    print(f"  玩家:      {result['players_list']}")

    # 基本字段断言
    assert result["host"] == host
    assert result["server_version"], "版本号不应为空"
    assert result["plays_max"] > 0, "最大玩家数应大于 0"
    assert 0 <= result["plays_online"] <= result["plays_max"], "在线人数应在合理范围内"
    assert result["latency"] >= 0, "延迟不应为负数"
    assert len(result["motd_lines"]) >= 1, "MOTD 应至少有一行"

    # 字段类型断言
    assert isinstance(result["players_list"], list), "玩家列表应为 list"
    assert isinstance(result["icon_base64"], str) and result["icon_base64"], "图标 base64 不应为空"

    # 使用真实数据生成 rich 样式图片
    img_b64 = await generate_server_info_image(
        players_list=result["players_list"],
        latency=result["latency"],
        server_name=host,
        plays_max=result["plays_max"],
        plays_online=result["plays_online"],
        server_version=result["server_version"],
        icon_base64=result["icon_base64"],
        host_address=result["host"],
        preset_name="rich",
        motd_lines=result["motd_lines"],
    )
    assert img_b64 is not None, "图片生成失败"

    img_data = base64.b64decode(img_b64)
    print(f"  图片大小:  {len(img_data)} bytes")

    # 保存图片到文件（文件名含服务器名，避免多个服务器互相覆盖）
    output_path = Path(__file__).resolve().parent / f"test_output_ping_{host}.png"
    with open(output_path, "wb") as f:
        f.write(img_data)
    print(f"  图片已保存: {output_path}")

    print("✓ 真实服务器 ping 测试通过\n")


async def test_ping_server_with_custom_font(host: str) -> None:
    """使用同一份真实服务器 MOTD，以非默认字体重新渲染。"""
    print("=" * 60)
    print(f"测试: 真实服务器 MOTD 的非默认字体渲染 - {host}")
    print("=" * 60)

    result = await get_server_status(host)
    assert result is not None, f"无法获取服务器 {host} 的状态信息"

    tests_dir = Path(__file__).resolve().parent
    regular_font = tests_dir / "SarasaUiSC-Regular.ttf"
    bold_font = tests_dir / "SarasaUiSC-Bold.ttf"
    assert regular_font.exists(), f"非默认常规字体不存在: {regular_font}"
    assert bold_font.exists(), f"非默认粗体字体不存在: {bold_font}"

    set_custom_font_path(str(regular_font), str(bold_font))
    try:
        render_font = await load_render_font(26)
        assert render_font.bold is not None, "非默认粗体字体加载失败"
        assert Path(render_font.regular.path).resolve() == regular_font.resolve()
        assert Path(render_font.bold.path).resolve() == bold_font.resolve()

        img_b64 = await generate_server_info_image(
            players_list=result["players_list"],
            latency=result["latency"],
            server_name=host,
            plays_max=result["plays_max"],
            plays_online=result["plays_online"],
            server_version=result["server_version"],
            icon_base64=result["icon_base64"],
            host_address=result["host"],
            preset_name="rich",
            motd_lines=result["motd_lines"],
        )
        assert img_b64, "非默认字体图片生成失败"
        img_data = base64.b64decode(img_b64)

        output_path = tests_dir / f"test_output_ping_{host}_custom_font.png"
        output_path.write_bytes(img_data)
        with Image.open(io.BytesIO(img_data)) as image:
            image.verify()
            print(f"  非默认字体图片尺寸: {image.size[0]}x{image.size[1]}")
        print(f"  非默认字体图片已保存: {output_path}")
    finally:
        set_custom_font_path(None)

    print("✓ 真实服务器非默认字体 MOTD 测试通过\n")


async def test_ping_server_with_heavier_font_weight(host: str) -> None:
    """使用真实服务器 MOTD 验证 SemiBold 常规字体与 Bold 粗体字体的整体加重模式。"""
    print("=" * 60)
    print(f"测试: 真实服务器 MOTD 的整体加重字体渲染 - {host}")
    print("=" * 60)

    result = await get_server_status(host)
    assert result is not None, f"无法获取服务器 {host} 的状态信息"

    tests_dir = Path(__file__).resolve().parent
    regular_font = tests_dir / "SarasaUiSC-Regular.ttf"
    semibold_font = tests_dir / "SarasaUiSC-SemiBold.ttf"
    bold_font = tests_dir / "SarasaUiSC-Bold.ttf"
    assert all(path.exists() for path in (regular_font, semibold_font, bold_font)), "整体加重字体测试资源不完整"

    set_custom_font_path(str(regular_font), heavier_font_weight=True)
    try:
        render_font = await load_render_font(26)
        assert Path(render_font.regular.path).resolve() == semibold_font.resolve(), "真实服务器整体加重模式的常规字体必须为 SemiBold"
        assert render_font.bold is not None, "真实服务器整体加重模式的粗体字体加载失败"
        assert Path(render_font.bold.path).resolve() == bold_font.resolve(), "真实服务器整体加重模式的粗体字体必须为 Bold"

        img_b64 = await generate_server_info_image(
            players_list=result["players_list"],
            latency=result["latency"],
            server_name=host,
            plays_max=result["plays_max"],
            plays_online=result["plays_online"],
            server_version=result["server_version"],
            icon_base64=result["icon_base64"],
            host_address=result["host"],
            preset_name="rich",
            motd_lines=result["motd_lines"],
        )
        assert img_b64, "整体加重字体图片生成失败"
        img_data = base64.b64decode(img_b64)

        output_path = tests_dir / f"test_output_ping_{host}_heavier_font_weight.png"
        output_path.write_bytes(img_data)
        with Image.open(io.BytesIO(img_data)) as image:
            image.verify()
            print(f"  整体加重字体图片尺寸: {image.size[0]}x{image.size[1]}")
        print(f"  整体加重字体图片已保存: {output_path}")
    finally:
        set_custom_font_path(None)

    print("✓ 真实服务器整体加重字体 MOTD 测试通过\n")


async def main():
    print("\n" + "=" * 60)
    print("  MC Server Status Plugin - 真实服务器 ping 测试")
    print("=" * 60 + "\n")

    print(f"测试服务器列表: {PING_TEST_SERVERS}\n")
    for host in PING_TEST_SERVERS:
        await test_ping_server(host)
        await test_ping_server_with_custom_font(host)
        await test_ping_server_with_heavier_font_weight(host)

    print("=" * 60)
    print("  所有真实服务器 ping 测试通过！✓")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())