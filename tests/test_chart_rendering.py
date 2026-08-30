"""柱状图 PNG 输出测试。"""

import base64
import io

import pytest
from PIL import Image

from script.bar_chart import generate_bar_chart_image


pytestmark = pytest.mark.image_rendering


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
def test_bar_chart_is_valid_png(history) -> None:
    encoded = generate_bar_chart_image(history, "测试服务器")
    with Image.open(io.BytesIO(base64.b64decode(encoded))) as image:
        assert image.format == "PNG"
        assert image.size == (820, 400)
