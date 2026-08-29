"""命令 handler 回归测试：不依赖真实 AstrBot 或网络。"""

import ast
from pathlib import Path
from typing import Any, AsyncGenerator, List

import pytest

pytestmark = pytest.mark.commands
PROJECT_ROOT = Path(__file__).resolve().parent.parent

from astrbot_mcgetter_enhanced import main as plugin_main
from astrbot_mcgetter_enhanced.script.json_operate import read_json, write_json


class MockEvent:
    def get_group_id(self) -> str:
        return "command-test-group"

    def plain_result(self, value: str) -> str:
        return value

    def chain_result(self, value: List[str]) -> List[str]:
        return value


async def collect(generator: AsyncGenerator[Any, None]) -> List[Any]:
    return [item async for item in generator]


def test_command_documentation_consistency() -> None:
    """所有实际注册命令必须同时出现在 HELP_INFO 和 README 中。"""
    source = (PROJECT_ROOT / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    registered = set()
    help_text = None

    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "HELP_INFO" for target in node.targets
        ):
            help_text = ast.literal_eval(node.value)
        if isinstance(node, ast.ClassDef) and node.name == "MyPlugin":
            for item in node.body:
                if not isinstance(item, ast.AsyncFunctionDef):
                    continue
                for decorator in item.decorator_list:
                    if (
                        isinstance(decorator, ast.Call)
                        and isinstance(decorator.func, ast.Attribute)
                        and decorator.func.attr == "command"
                    ):
                        registered.add(decorator.args[0].value)

    assert help_text is not None, "未定义 HELP_INFO"
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    for command in registered:
        assert f"/{command}" in help_text, f"HELP_INFO 缺少 /{command}"
        assert f"/{command}" in readme, f"README 缺少 /{command}"


async def test_command_handlers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """验证文档列出的管理、显示和趋势命令能执行并正确保存状态。"""
    json_path = tmp_path / "command-test.json"
    await write_json(str(json_path), {
        "version": "2.3",
        "next_id": 2,
        "servers": {
            "1": {"id": 1, "name": "生存服", "host": "127.0.0.1:25565"},
        },
        "trends": {},
    })

    plugin = plugin_main.MyPlugin.__new__(plugin_main.MyPlugin)

    async def get_json_path(_group_id: str) -> Path:
        return json_path

    plugin.get_json_path = get_json_path
    event = MockEvent()

    help_message = (await collect(plugin.get_help(event)))[0]
    for command in (
        "/mc", "/mcadd", "/mcget", "/mcdel", "/mcup", "/mclist",
        "/mccleanup", "/mcdata", "/mcpreset", "/mcnote", "/mcalias", "/mctoggle",
    ):
        assert command in help_message, f"帮助文本遗漏命令: {command}"

    preset_info = await collect(plugin.mcpreset(event))
    assert len(preset_info) == 1 and "当前 preset:" in preset_info[0] and "可用 preset:" in preset_info[0]
    assert await collect(plugin.mcalias(event, "1", "我的 生存服务器")) == ["已设置服务器 生存服 的别名为: 我的 生存服务器"]
    assert await collect(plugin.mcnote(event, "1", "§a欢迎 来到服务器")) == ["已设置服务器 生存服 的备注"]

    assert await collect(plugin.mctoggle(event, "players")) == ["已关闭玩家列表"]
    assert await collect(plugin.mctoggle(event, "notes")) == ["已关闭备注"]
    assert await collect(plugin.mctoggle(event, "time")) == ["已关闭查询时间"]
    assert await collect(plugin.mctoggle(event, "id")) == ["已关闭序号显示"]
    assert await collect(plugin.mctoggle(event, "unknown")) == ["无效选项，可选: players, notes, time, id"]

    assert await collect(plugin.mcpreset(event, "simple")) == ["已切换为 preset: simple"]
    assert await collect(plugin.mcget(event, "生存服")) == ["生存服 (ID: 1) 的地址是:", "127.0.0.1:25565"]
    listing = await collect(plugin.mclist(event))
    assert len(listing) == 1 and "ID: 1" in listing[0] and "生存服" in listing[0]
    assert await collect(plugin.mcup(event, "1", "新生存服", None)) == ["成功更新服务器信息: 新生存服 (ID: 1)"]

    data = await read_json(str(json_path))
    assert data["servers"]["1"]["alias"] == "我的 生存服务器"
    assert data["servers"]["1"]["note"] == "§a欢迎 来到服务器"
    assert data["display"] == {
        "show_players": False,
        "show_notes": False,
        "show_query_time": False,
    }
    assert data["show_id"] is False
    assert data["preset"] == "simple"
    assert data["servers"]["1"]["name"] == "新生存服"

    observed = {}

    async def get_all_trend_histories(_path: str, hours: int):
        observed["hours"] = hours
        return {"1": []}

    async def get_server_status(_host: str):
        return {"plays_online": 0}

    monkeypatch.setattr(plugin_main, "get_all_trend_histories", get_all_trend_histories)
    monkeypatch.setattr(plugin_main, "get_server_status", get_server_status)
    monkeypatch.setattr(plugin_main, "generate_bar_chart_image", lambda *_args, **_kwargs: "chart")
    assert await collect(plugin.mcdata(event, "48")) == [["chart"]]
    assert observed["hours"] == 48, "/mcdata 48 应作为全服 48 小时处理"

    assert await collect(plugin.mcalias(event, "1")) == ["已清除服务器 新生存服 的别名"]
    assert await collect(plugin.mcnote(event, "1")) == ["已清除服务器 新生存服 的备注"]
    assert await collect(plugin.mcdel(event, "1")) == ["成功删除服务器 1"]
    assert (await read_json(str(json_path)))["servers"] == {}
    assert await collect(plugin.mcgetter(event)) == ["请先使用 /mcadd 添加服务器"]

    async def auto_cleanup_servers(_path: Path):
        return []

    monkeypatch.setattr(plugin_main, "auto_cleanup_servers", auto_cleanup_servers)
    assert await collect(plugin.mccleanup(event)) == ["没有需要清理的服务器"]

    async def fail_if_called(_host: str):
        raise AssertionError("force=True 时不应执行预查询")

    monkeypatch.setattr(plugin_main, "get_server_status", fail_if_called)
    add_result = await collect(plugin.mcadd(event, "强制添加服", "127.0.0.1:25565", True))
    assert add_result == ["成功添加服务器 强制添加服 (ID: 2)"], add_result
