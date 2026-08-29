"""pytest 全局配置、共享路径与真实服务器 fixture。"""

import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio


TESTS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = TESTS_DIR.parent

# 同时支持 ``script.*`` 和 ``astrbot_mcgetter_enhanced.*`` 两种项目内导入。
sys.path.insert(0, str(TESTS_DIR))
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT.parent))

from mock_astrbot import setup_mock_astrbot


setup_mock_astrbot()


def _real_server_hosts() -> list[str]:
    configured = os.getenv("MC_TEST_SERVERS", "127.0.0.1:43596")
    return [host.strip() for host in configured.split(",") if host.strip()]


REAL_SERVER_HOSTS = _real_server_hosts()


@pytest.fixture(scope="module", params=REAL_SERVER_HOSTS, ids=REAL_SERVER_HOSTS)
def real_server_host(request: pytest.FixtureRequest) -> str:
    """返回一个真实服务器地址，可通过 MC_TEST_SERVERS 覆盖。"""
    return request.param


@pytest_asyncio.fixture(scope="module")
async def real_server_status(real_server_host: str):
    """获取真实状态；普通回归不可达时跳过，严格模式下直接失败。"""
    from script.get_server_info import get_server_status

    result = await get_server_status(real_server_host)
    if result is not None:
        return result

    message = f"真实测试服务器不可达: {real_server_host}"
    if os.getenv("MC_TEST_REQUIRE_SERVER") == "1":
        pytest.fail(message)
    pytest.skip(f"{message}；设置 MC_TEST_REQUIRE_SERVER=1 可启用严格失败")