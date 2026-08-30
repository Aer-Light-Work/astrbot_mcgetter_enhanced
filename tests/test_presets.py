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


def test_builtin_presets_do_not_share_nested_data(tmp_path) -> None:
    """一个 manager 的临时修改不能污染后续内置 preset 回退。"""
    first = PresetManager(tmp_path)
    first.get_preset("rich")["colors"]["background"][0] = 99

    second = PresetManager(tmp_path)
    assert second.get_preset("rich")["colors"]["background"] == [15, 15, 15]
