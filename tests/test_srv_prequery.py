"""/mcadd 的 SRV 预查询端到端回归测试。

目标地址仅从 ``MC_TEST_SRV_SERVER`` 环境变量读取，避免真实服务器地址进入仓库。
"""

import os
from pathlib import Path
from typing import Any, AsyncGenerator, List

import pytest

from astrbot_mcgetter_enhanced import main as plugin_main
from astrbot_mcgetter_enhanced.script.json_operate import read_json


pytestmark = [pytest.mark.real_server, pytest.mark.srv_lookup]


class _MockEvent:
    def get_group_id(self) -> str:
        return "srv-prequery-test"

    def plain_result(self, value: str) -> str:
        return value


async def _collect(generator: AsyncGenerator[Any, None]) -> List[Any]:
    return [item async for item in generator]


async def test_mcadd_prequery_accepts_srv_address(tmp_path: Path) -> None:
    """/mcadd 应以 SRV 解析得到的端口完成预查询，而不需要 ``True`` 强制添加。"""
    host = os.getenv("MC_TEST_SRV_SERVER")
    if not host:
        pytest.skip("设置 MC_TEST_SRV_SERVER 后运行此真实 SRV 回归测试")

    plugin = plugin_main.MyPlugin.__new__(plugin_main.MyPlugin)
    json_path = tmp_path / "srv-prequery.json"

    async def get_json_path(_group_id: str) -> Path:
        return json_path

    plugin.get_json_path = get_json_path
    result = await _collect(plugin.mcadd(_MockEvent(), "SRV 测试服务器", host))

    assert result == ["成功添加服务器 SRV 测试服务器 (ID: 1)"]
    assert (await read_json(str(json_path)))["servers"]["1"]["host"] == host
