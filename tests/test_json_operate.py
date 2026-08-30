"""JSON 默认配置与迁移隔离测试。"""

import pytest

from script.json_operate import DEFAULT_CONFIG, migrate_old_format, read_json


pytestmark = pytest.mark.commands


async def test_new_default_configs_do_not_share_nested_data(tmp_path) -> None:
    first = await read_json(str(tmp_path / "first.json"))
    first["servers"]["1"] = {"name": "测试服"}
    first["trends"]["1"] = {"history": []}

    second = await read_json(str(tmp_path / "second.json"))
    assert second["servers"] == {}
    assert second["trends"] == {}
    assert DEFAULT_CONFIG["servers"] == {}
    assert DEFAULT_CONFIG["trends"] == {}


def test_migrated_config_does_not_share_default_nested_data() -> None:
    migrated = migrate_old_format({"旧服务器": {"name": "旧服务器", "host": "127.0.0.1"}})
    migrated["trends"]["1"] = {"history": []}

    assert DEFAULT_CONFIG["servers"] == {}
    assert DEFAULT_CONFIG["trends"] == {}
