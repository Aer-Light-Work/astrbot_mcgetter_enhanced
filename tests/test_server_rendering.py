"""使用一份真实服务器状态生成三种字体配置的完整 Rich 图片。"""

import base64
import io
from pathlib import Path

import pytest
from PIL import Image

from script.get_img import generate_server_info_image, load_render_font, set_custom_font_path


pytestmark = [pytest.mark.real_server, pytest.mark.server_rendering]
TESTS_DIR = Path(__file__).resolve().parent


def verify_and_save_png(encoded: str, output_path: Path) -> None:
    data = base64.b64decode(encoded, validate=True)
    output_path.write_bytes(data)
    with Image.open(io.BytesIO(data)) as image:
        image.load()
        assert image.format == "PNG"
        assert image.width == 1177


async def render_real_server(real_server_host: str, status: dict, suffix: str) -> None:
    encoded = await generate_server_info_image(
        players_list=status["players_list"], latency=status["latency"],
        server_name=real_server_host, plays_max=status["plays_max"],
        plays_online=status["plays_online"], server_version=status["server_version"],
        icon_base64=status["icon_base64"], host_address=status["host"],
        preset_name="rich", motd_lines=status["motd_lines"],
    )
    safe_host = real_server_host.replace("/", "_")
    verify_and_save_png(encoded, TESTS_DIR / f"test_output_ping_{safe_host}{suffix}.png")


async def test_render_real_server_with_default_font(real_server_host: str, real_server_status: dict) -> None:
    set_custom_font_path(None)
    await render_real_server(real_server_host, real_server_status, "")


async def test_render_real_server_with_custom_font(real_server_host: str, real_server_status: dict) -> None:
    regular = TESTS_DIR / "SarasaUiSC-Regular.ttf"
    bold = TESTS_DIR / "SarasaUiSC-Bold.ttf"
    set_custom_font_path(str(regular), str(bold))
    try:
        font = await load_render_font(26)
        assert Path(font.regular.path).resolve() == regular.resolve()
        assert font.bold is not None and Path(font.bold.path).resolve() == bold.resolve()
        await render_real_server(real_server_host, real_server_status, "_custom_font")
    finally:
        set_custom_font_path(None)


async def test_render_real_server_with_heavier_font_weight(
    real_server_host: str, real_server_status: dict,
) -> None:
    regular = TESTS_DIR / "SarasaUiSC-Regular.ttf"
    semibold = TESTS_DIR / "SarasaUiSC-SemiBold.ttf"
    bold = TESTS_DIR / "SarasaUiSC-Bold.ttf"
    set_custom_font_path(str(regular), heavier_font_weight=True)
    try:
        font = await load_render_font(26)
        assert Path(font.regular.path).resolve() == semibold.resolve()
        assert font.bold is not None and Path(font.bold.path).resolve() == bold.resolve()
        await render_real_server(real_server_host, real_server_status, "_heavier_font_weight")
    finally:
        set_custom_font_path(None)
