"""图片 preset 配置管理测试。"""

import pytest

from script.preset_manager import PresetManager


pytestmark = pytest.mark.presets


def test_preset_manager_lists_and_loads_builtin_presets() -> None:
    manager = PresetManager()

    assert {"rich", "simple"}.issubset(manager.list_presets())
    assert manager.get_preset("rich").get("name") == "丰富样式"
    assert manager.get_preset("simple").get("name") == "简洁样式"
    assert manager.get_preset().get("name") == "丰富样式"