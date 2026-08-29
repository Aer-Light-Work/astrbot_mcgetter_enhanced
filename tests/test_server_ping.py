"""只验证真实 Minecraft 服务器状态获取。"""

import pytest


pytestmark = [pytest.mark.real_server, pytest.mark.server_ping]


async def test_real_server_status_fields(real_server_host: str, real_server_status: dict) -> None:
    result = real_server_status
    assert result["host"] == real_server_host
    assert result["server_version"]
    assert result["plays_max"] > 0
    assert 0 <= result["plays_online"] <= result["plays_max"]
    assert result["latency"] >= 0
    assert len(result["motd_lines"]) >= 1
    assert isinstance(result["players_list"], list)
    assert isinstance(result["icon_base64"], str) and result["icon_base64"]
