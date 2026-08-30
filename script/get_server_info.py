"""查询 Minecraft Java 服务器并将 MOTD 转换为渲染模型。"""

import asyncio
import base64
import re
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import aiohttp
from astrbot.api import logger
from mcstatus import JavaServer
from mcstatus.motd import Motd
from mcstatus.motd.components import JavaFormatting, JavaMinecraftColor, WebColor

CSU_HOST = "csu-mc.org"
CSU_PLAYERS_URL = "https://map.magicalsheep.cn/tiles/players.json"

# Minecraft 颜色代码映射
MC_COLOR_CODES = {
    "0": (0, 0, 0),
    "1": (0, 0, 170),
    "2": (0, 170, 0),
    "3": (0, 170, 170),
    "4": (170, 0, 0),
    "5": (170, 0, 170),
    "6": (255, 170, 0),
    "7": (170, 170, 170),
    "8": (85, 85, 85),
    "9": (85, 85, 255),
    "a": (85, 255, 85),
    "b": (85, 255, 255),
    "c": (255, 85, 85),
    "d": (255, 85, 255),
    "e": (255, 255, 85),
    "f": (255, 255, 255),
}

MC_COLOR_NAMES = {
    "black": (0, 0, 0),
    "dark_blue": (0, 0, 170),
    "dark_green": (0, 170, 0),
    "dark_aqua": (0, 170, 170),
    "dark_red": (170, 0, 0),
    "dark_purple": (170, 0, 170),
    "gold": (255, 170, 0),
    "gray": (170, 170, 170),
    "grey": (170, 170, 170),
    "dark_gray": (85, 85, 85),
    "dark_grey": (85, 85, 85),
    "blue": (85, 85, 255),
    "green": (85, 255, 85),
    "aqua": (85, 255, 255),
    "red": (255, 85, 85),
    "light_purple": (255, 85, 255),
    "yellow": (255, 255, 85),
    "white": (255, 255, 255),
    "reset": None,
}

@dataclass
class TextSegment:
    """渲染器使用的一段带 Minecraft 样式的文本。"""

    text: str
    color: Optional[tuple[int, int, int]] = None
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False


@dataclass
class MotdLine:
    """MOTD 的一行；换行在解析阶段转换为多个实例。"""

    segments: list[TextSegment] = field(default_factory=list)

    def plain_text(self) -> str:
        """获取纯文本内容"""
        return "".join(s.text for s in self.segments)


def parse_mc_color(color_str: str) -> Optional[tuple[int, int, int]]:
    """
    解析 Minecraft 颜色字符串
    支持: 单字符代码(§a), hex(#FF0000), 颜色名称(red)
    """
    if not color_str:
        return None
    normalized = str(color_str).lower()
    if len(normalized) == 1:
        return MC_COLOR_CODES.get(normalized)
    if normalized.startswith("#") and len(normalized) == 7:
        try:
            return (
                int(normalized[1:3], 16),
                int(normalized[3:5], 16),
                int(normalized[5:7], 16),
            )
        except ValueError:
            return None
    return MC_COLOR_NAMES.get(normalized)


_HEX_DIGITS = frozenset("0123456789abcdef")


def parse_section_sign_text(
    text: str,
    default_color: Optional[tuple[int, int, int]] = None,
) -> list[TextSegment]:
    """
    解析包含 § 格式代码的文本
    §0-§f: 旧版固定颜色代码
    §#RRGGBB: 本插件为自定义备注保留的扩展颜色语法，不是 Minecraft
        1.16+ 原版的十六进制颜色表示法
    §k: 随机字符(obfuscated, 忽略)
    §l: 粗体
    §m: 删除线
    §n: 下划线
    §o: 斜体
    §r: 重置
    """
    segments: list[TextSegment] = []
    current_text: list[str] = []
    current_color = default_color
    current_bold = False
    current_italic = False
    current_underline = False
    current_strikethrough = False

    def flush() -> None:
        nonlocal current_text
        if current_text:
            segments.append(TextSegment(
                text="".join(current_text),
                color=current_color,
                bold=current_bold,
                italic=current_italic,
                underline=current_underline,
                strikethrough=current_strikethrough,
            ))
            current_text = []

    i = 0
    while i < len(text):
        if text[i] == "§" and i + 1 < len(text):
            flush()
            code = text[i + 1].lower()
            if code == "#" and i + 7 < len(text):
                # 插件扩展：§#RRGGBB，例如 §#ffcd1a → (255,205,26)。
                hex_raw = text[i + 2:i + 8]
                if all(ch.lower() in _HEX_DIGITS for ch in hex_raw):
                    current_color = parse_mc_color(f"#{hex_raw}")
                    current_bold = False
                    current_italic = False
                    current_underline = False
                    current_strikethrough = False
                    i += 8
                    continue
                # 解析失败按普通字符处理 §#
                i += 2
            elif code in MC_COLOR_CODES:
                current_color = MC_COLOR_CODES[code]
                # Java 版颜色代码会清除之前启用的样式。
                current_bold = False
                current_italic = False
                current_underline = False
                current_strikethrough = False
                i += 2
            elif code == "l":
                current_bold = True
                i += 2
            elif code == "m":
                current_strikethrough = True
                i += 2
            elif code == "n":
                current_underline = True
                i += 2
            elif code == "o":
                current_italic = True
                i += 2
            elif code == "r":
                current_color = default_color
                current_bold = False
                current_italic = False
                current_underline = False
                current_strikethrough = False
                i += 2
            else:
                # §k (obfuscated) 及其他未识别代码忽略
                i += 2
        else:
            current_text.append(text[i])
            i += 1

    flush()
    return segments


def _split_motd_lines(segments: list[TextSegment]) -> list[MotdLine]:
    """按换行拆分文本段，并复制样式到被切开的片段。"""
    lines: list[MotdLine] = []
    current: list[TextSegment] = []

    for segment in segments:
        parts = segment.text.split("\n")
        for index, part in enumerate(parts):
            if part:
                current.append(TextSegment(
                    text=part,
                    color=segment.color,
                    bold=segment.bold,
                    italic=segment.italic,
                    underline=segment.underline,
                    strikethrough=segment.strikethrough,
                ))
            if index < len(parts) - 1:
                lines.append(MotdLine(segments=current))
                current = []

    lines.append(MotdLine(segments=current))
    return lines


def _parse_component_motd(parsed: Motd) -> list[TextSegment]:
    """将 JSON Chat Component 的 mcstatus token 直接转换为渲染文本段。

    WebColor 是 JSON component 的 RGB 颜色，不存在等价的原版 ``§#RRGGBB``
    表示。这里直接写入 ``TextSegment.color``，并保留 JSON component 继承的
    既有样式；Java Legacy 颜色代码则按游戏规则清除样式。
    """
    segments: list[TextSegment] = []
    current_color: Optional[tuple[int, int, int]] = None
    current_bold = False
    current_italic = False
    current_underline = False
    current_strikethrough = False

    for component in parsed.simplify().parsed:
        if isinstance(component, str):
            if component:
                segments.append(TextSegment(
                    text=component,
                    color=current_color,
                    bold=current_bold,
                    italic=current_italic,
                    underline=current_underline,
                    strikethrough=current_strikethrough,
                ))
        elif isinstance(component, WebColor):
            # mcstatus 的 to_minecraft() 会丢弃 WebColor，因此不能先转 § 文本。
            current_color = component.rgb
        elif isinstance(component, JavaMinecraftColor):
            current_color = MC_COLOR_CODES.get(component.value)
            current_bold = False
            current_italic = False
            current_underline = False
            current_strikethrough = False
        elif isinstance(component, JavaFormatting):
            if component is JavaFormatting.BOLD:
                current_bold = True
            elif component is JavaFormatting.ITALIC:
                current_italic = True
            elif component is JavaFormatting.UNDERLINED:
                current_underline = True
            elif component is JavaFormatting.STRIKETHROUGH:
                current_strikethrough = True
            elif component is JavaFormatting.RESET:
                current_color = None
                current_bold = False
                current_italic = False
                current_underline = False
                current_strikethrough = False
        # TranslationTag 与无效格式没有可渲染文本，按 mcstatus transformer 语义忽略。
    return segments


def parse_motd(description: Motd | str | list[Any] | dict[str, Any]) -> list[MotdLine]:
    """使用 mcstatus 规范化任意 Java MOTD，再转换为图片渲染模型。

    Legacy 字符串使用 mcstatus 规范化后生成的原版 ``§`` 代码交给 Legacy
    解析器；JSON component 则直接把 WebColor 转成 RGB ``TextSegment``。
    两条路径只在逐行渲染模型上汇合，避免把 WebColor 伪装为分节符文本。
    """
    parsed = description if isinstance(description, Motd) else Motd.parse(description)
    if isinstance(parsed.raw, str):
        segments = parse_section_sign_text(parsed.simplify().to_minecraft())
    else:
        segments = _parse_component_motd(parsed)
    return _split_motd_lines(segments)


def parse_custom_note_text(text: str) -> list[TextSegment]:
    """
    解析自定义备注文本，支持:
    1. § 分节符格式代码
    2. <color:#hex>...</color> 标签语法
    """
    # 先解析 <color:#hex> 标签
    result_segments: list[TextSegment] = []
    pattern = re.compile(r"<color:([^>]+)>(.*?)</color>", re.DOTALL)

    last_end = 0
    for match in pattern.finditer(text):
        # 标签前的文本
        if match.start() > last_end:
            prefix = text[last_end:match.start()]
            result_segments.extend(parse_section_sign_text(prefix))

        color_str = match.group(1).strip()
        inner_text = match.group(2)
        color = parse_mc_color(color_str)

        # 内部文本可能还包含 § 代码
        inner_segments = parse_section_sign_text(inner_text)
        for seg in inner_segments:
            if seg.color is None:
                seg.color = color
            result_segments.append(seg)

        last_end = match.end()

    # 剩余文本
    if last_end < len(text):
        remaining = text[last_end:]
        result_segments.extend(parse_section_sign_text(remaining))

    return result_segments


def _default_icon_base64() -> str:
    """读取内置图标；状态接口无 favicon 时仍向渲染器提供有效图片。"""
    image_path = Path(__file__).resolve().parent.parent / "resource" / "default_icon.png"
    return base64.b64encode(image_path.read_bytes()).decode("ascii")


async def get_server_status(host: str) -> Optional[dict[str, Any]]:
    """查询 Java 服务器状态，失败时记录原因并返回 ``None``。"""
    try:
        server = await JavaServer.async_lookup(host)
        status = await server.async_status(version=767)

        # sample 可能为 None；保留服务端给出的原始玩家顺序。
        players_list = [player.name for player in (status.players.sample or [])]
        if host == CSU_HOST:
            players_list = await fetch_players_names(CSU_PLAYERS_URL)

        icon_data = (
            status.icon.partition(",")[2] if status.icon and "," in status.icon
            else status.icon or _default_icon_base64()
        )

        return {
            "players_list": players_list,
            "latency": int(status.latency),
            "plays_max": status.players.max,
            "plays_online": status.players.online,
            "server_version": status.version.name,
            "icon_base64": icon_data,
            "host": host,
            "motd_lines": parse_motd(status.motd),
        }
    except (socket.gaierror, ConnectionRefusedError) as e:
        logger.error(f"连接服务器失败: {e}")
        return None
    except asyncio.TimeoutError:
        logger.error("获取服务器状态超时")
        return None
    except Exception as e:
        logger.error(f"获取服务器状态时发生未知错误: {e}")
        return None


async def fetch_players_names(url: str) -> list[str]:
    """读取 CSU 地图玩家列表，并过滤用于地图同步的 ``bot_`` 账号。"""
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise ValueError(f"请求失败，状态码: {response.status}")
            data = await response.json()
            return [
                player["name"]
                for player in data.get("players", [])
                if not player["name"].startswith("bot_")
            ]
