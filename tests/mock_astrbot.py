#!/usr/bin/env python3
"""pytest 环境使用的公共 AstrBot mock。"""

import sys
import types


class MockLogger:
    def info(self, _message: str) -> None:
        pass

    def warning(self, _message: str) -> None:
        pass

    def error(self, message: str) -> None:
        print(f"[ERROR] {message}", file=sys.stderr)

    def debug(self, _message: str) -> None:
        pass


def setup_mock_astrbot() -> None:
    """注册导入插件及渲染模块所需的最小 AstrBot API。"""
    astrbot = types.ModuleType("astrbot")
    api = types.ModuleType("astrbot.api")
    event = types.ModuleType("astrbot.api.event")
    star = types.ModuleType("astrbot.api.star")
    core = types.ModuleType("astrbot.core")
    message = types.ModuleType("astrbot.core.message")
    components = types.ModuleType("astrbot.core.message.components")
    command = types.ModuleType("astrbot.core.star.filter.command")

    class MockFilter:
        def command(self, _name: str):
            return lambda function: function

    class MockImage:
        @staticmethod
        def fromBase64(value: str) -> str:
            return value

    api.logger = MockLogger()
    api.AstrBotConfig = dict
    event.filter = MockFilter()
    event.AstrMessageEvent = object
    event.MessageEventResult = object
    star.Context = object
    star.Star = object
    star.StarTools = object
    star.register = lambda *_args, **_kwargs: lambda cls: cls
    components.Image = MockImage
    command.GreedyStr = str

    for name, module in {
        "astrbot": astrbot,
        "astrbot.api": api,
        "astrbot.api.event": event,
        "astrbot.api.star": star,
        "astrbot.core": core,
        "astrbot.core.message": message,
        "astrbot.core.message.components": components,
        "astrbot.core.star.filter.command": command,
    }.items():
        sys.modules[name] = module
