"""柱状图 PNG 输出测试。"""

import base64
import io
from pathlib import Path

import pytest
from PIL import Image

from script.bar_chart import generate_bar_chart_image


pytestmark = pytest.mark.image_rendering
TESTS_DIR = Path(__file__).resolve().parent


@pytest.mark.parametrize(
    "history",
    [
        [],
        [
            {"ts": 1_700_000_100, "count": 3},
            {"ts": 1_700_007_300, "count": 7},
        ],
    ],
)
def test_bar_chart_is_valid_png(history, request: pytest.FixtureRequest) -> None:
    encoded = generate_bar_chart_image(history, "测试服务器")
    data = base64.b64decode(encoded)
    output_name = request.node.callspec.id
    (TESTS_DIR / f"test_output_chart_{output_name}.png").write_bytes(data)
    with Image.open(io.BytesIO(data)) as image:
        assert image.format == "PNG"
        assert image.size == (820, 400)
