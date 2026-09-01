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

    def get_sender_id(self) -> str:
        return "command-test-user"

    def plain_result(self, value: str) -> str:
        return value

    def chain_result(self, value: List[str]) -> List[str]:
        return value


async def collect(generator: AsyncGenerator[Any, None]) -> List[Any]:
    return [item async for item in generator]


async def test_mcadd_missing_parameters_shows_friendly_usage() -> None:
    """/mcadd 缺少名称或地址时，应返回用户可直接照抄的用法。"""
    plugin = plugin_main.MyPlugin.__new__(plugin_main.MyPlugin)
    expected = [
        "用法：/mcadd <服务器名称> <服务器地址> [True]\n"
        "示例：/mcadd 生存服 127.0.0.1:25565",
    ]

    assert await collect(plugin.mcadd(MockEvent())) == expected
    assert await collect(plugin.mcadd(MockEvent(), "生存服")) == expected


async def test_command_parameter_errors_show_friendly_usage() -> None:
    """各命令的缺参和类型错误应返回中文用法，而非框架内部签名。"""
    plugin = plugin_main.MyPlugin.__new__(plugin_main.MyPlugin)
    event = MockEvent()
    cases = [
        (lambda: plugin.mcdel(event), "用法：/mcdel <名称或ID>\n示例：/mcdel 1"),
        (lambda: plugin.mcget(event), "用法：/mcget <名称或ID>\n示例：/mcget 1"),
        (
            lambda: plugin.mcup(event),
            "用法：/mcup <名称或ID> [新名称] [新地址]\n示例：/mcup 1 新生存服",
        ),
        (
            lambda: plugin.mcnote(event),
            "用法：/mcnote <名称或ID> [备注]\n示例：/mcnote 1 欢迎来到服务器",
        ),
        (
            lambda: plugin.mcalias(event),
            "用法：/mcalias <名称或ID> [别名]\n示例：/mcalias 1 生存服",
        ),
        (
            lambda: plugin.mctoggle(event),
            "用法：/mctoggle <players|notes|time|id>\n示例：/mctoggle players",
        ),
        (
            lambda: plugin.mcadd(event, "生存服", "127.0.0.1:25565", "yes"),
            "用法：/mcadd <服务器名称> <服务器地址> [True]\n"
            "说明：末尾仅可填写 True 以跳过预查询。",
        ),
        (
            lambda: plugin.mcdata(event, None, "many"),
            "小时数必须是 1 到 168 的整数。\n"
            "用法：/mcdata [名称或ID] [小时数]\n示例：/mcdata 1 48",
        ),
    ]

    for command, expected in cases:
        assert await collect(command()) == [expected]


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


async def test_mcgetter_merges_server_images(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """/mc 应把所有成功查询结果合并为一张图，并关闭子图时间戳。"""
    json_path = tmp_path / "merged-images.json"
    await write_json(str(json_path), {
        "version": "2.3",
        "next_id": 3,
        "servers": {
            "1": {"id": 1, "name": "服务器一", "host": "one.example"},
            "2": {"id": 2, "name": "服务器二", "host": "two.example"},
        },
        "trends": {},
    })
    plugin = plugin_main.MyPlugin.__new__(plugin_main.MyPlugin)

    async def get_json_path(_group_id: str) -> Path:
        return json_path

    observed: dict[str, Any] = {}

    async def get_img(
        *_args,
        suppress_query_time: bool = False,
        suppress_title: bool = False,
        **_kwargs,
    ) -> str:
        assert suppress_query_time
        assert suppress_title
        return "child-image"

    async def merge_images(images, query_time, **_kwargs) -> str:
        observed["images"] = images
        observed["query_time"] = query_time
        return "merged-image"

    async def no_cleanup(_path: Path):
        return []

    plugin.get_json_path = get_json_path
    plugin.get_img = get_img
    monkeypatch.setattr(plugin_main, "merge_server_info_images", merge_images)
    monkeypatch.setattr(plugin_main, "auto_cleanup_servers", no_cleanup)

    assert await collect(plugin.mcgetter(MockEvent())) == [["merged-image"]]
    assert observed["images"] == ["child-image", "child-image"]
    assert observed["query_time"] is not None


async def test_get_json_path_rejects_empty_group_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """缺失群 ID 时不能创建 ``.json`` 或在数据目录外写入文件。"""
    plugin = plugin_main.MyPlugin.__new__(plugin_main.MyPlugin)

    class DataTools:
        @staticmethod
        def get_data_dir(_plugin_name: str) -> Path:
            return tmp_path

    monkeypatch.setattr(plugin_main, "StarTools", DataTools)

    for invalid_group_id in (None, "", "   ", ".", "../outside", "group\\name"):
        with pytest.raises(ValueError):
            await plugin.get_json_path(invalid_group_id)

    assert not (tmp_path / ".json").exists()
    valid_path = await plugin.get_json_path("test-group-1")
    assert valid_path == tmp_path / "test-group-1.json"


async def test_get_event_json_path_uses_sender_for_private_chat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """私聊没有群 ID 时，应以发送者 ID 创建独立配置而非 `.json`。"""
    plugin = plugin_main.MyPlugin.__new__(plugin_main.MyPlugin)

    class DataTools:
        @staticmethod
        def get_data_dir(_plugin_name: str) -> Path:
            return tmp_path

    class PrivateEvent(MockEvent):
        def get_group_id(self) -> str:
            return ""

        def get_sender_id(self) -> str:
            return "private-user-42"

    monkeypatch.setattr(plugin_main, "StarTools", DataTools)
    assert await plugin.get_event_json_path(PrivateEvent()) == tmp_path / "private_private-user-42.json"
    assert not (tmp_path / ".json").exists()
