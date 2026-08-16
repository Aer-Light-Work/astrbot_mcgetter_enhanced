#!/usr/bin/env python3
"""
公共 astrbot mock 模块
测试环境不需要真实的 astrbot，此模块提供统一 mock 供各测试脚本复用
"""

import sys


class MockLogger:
    def info(self, msg): print(f"[INFO] {msg}")
    def warning(self, msg): print(f"[WARN] {msg}")
    def error(self, msg): print(f"[ERROR] {msg}")
    def debug(self, msg): pass


class MockAstrbot:
    class api:
        logger = MockLogger()
    class core:
        class message:
            class components:
                pass


def setup_mock_astrbot() -> None:
    """注册 astrbot mock 到 sys.modules"""
    sys.modules['astrbot'] = MockAstrbot
    sys.modules['astrbot.api'] = MockAstrbot.api
    sys.modules['astrbot.core'] = MockAstrbot.core
    sys.modules['astrbot.core.message'] = MockAstrbot.core.message
    sys.modules['astrbot.core.message.components'] = MockAstrbot.core.message.components