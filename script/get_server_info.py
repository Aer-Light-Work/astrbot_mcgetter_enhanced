import asyncio
import aiohttp
import mcstatus
from mcstatus import JavaServer, motd
from mcstatus.responses.base import BaseStatusResponse
from mcstatus.responses import java as java_responses
from mcstatus.motd import components as motd_components
import socket
import base64
from pathlib import Path
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from astrbot.api import logger

csu_host = 'csu-mc.org'
csu_get_players = 'https://map.magicalsheep.cn/tiles/players.json'

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

# Minecraft 格式化代码
MC_FORMAT_CODES = {
    "k": "obfuscated",
    "l": "bold",
    "m": "strikethrough",
    "n": "underline",
    "o": "italic",
    "r": "reset",
}

VANILLA_COLOR_NAMES = {
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
    """一段带格式的文本"""
    text: str
    color: Optional[Tuple[int, int, int]] = None
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False


@dataclass
class MotdLine:
    """MOTD 的一行，包含多个 TextSegment"""
    segments: List[TextSegment] = field(default_factory=list)

    def plain_text(self) -> str:
        """获取纯文本内容"""
        return "".join(s.text for s in self.segments)


def parse_mc_color(color_str: str) -> Optional[Tuple[int, int, int]]:
    """
    解析 Minecraft 颜色字符串
    支持: 单字符代码(§a), hex(#FF0000), 颜色名称(red)
    """
    if not color_str:
        return None
    color_str = str(color_str).lower()
    # 单字符代码
    if len(color_str) == 1 and color_str in MC_COLOR_CODES:
        return MC_COLOR_CODES[color_str]
    # hex 颜色
    if color_str.startswith("#") and len(color_str) == 7:
        try:
            return (
                int(color_str[1:3], 16),
                int(color_str[3:5], 16),
                int(color_str[5:7], 16),
            )
        except ValueError:
            pass
    # 颜色名称
    color_names = {
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
    return color_names.get(color_str)


def parse_component(component: motd.components, default_color: Optional[Tuple[int, int, int]] = None) -> List[TextSegment]:
    """
    递归解析 Minecraft Chat Component 为 TextSegment 列表
    支持 dict 格式和 mcstatus 的 Component 对象
    """
    segments: List[TextSegment] = []

    if component is None:
        return segments

    # 纯字符串
    if isinstance(component, str):
        return parse_section_sign_text(component, default_color)

    # dict 格式
    if isinstance(component, dict):
        return _parse_component_dict(component, default_color)

    # mcstatus Component 对象（有 text, extra, color 等属性）
    if hasattr(component, "text") or hasattr(component, "extra"):
        comp_dict = {}
        if hasattr(component, "text"):
            comp_dict["text"] = component.text
        if hasattr(component, "extra"):
            comp_dict["extra"] = component.extra
        if hasattr(component, "color"):
            comp_dict["color"] = component.color
        if hasattr(component, "bold"):
            comp_dict["bold"] = component.bold
        if hasattr(component, "italic"):
            comp_dict["italic"] = component.italic
        if hasattr(component, "underlined"):
            comp_dict["underlined"] = component.underlined
        if hasattr(component, "strikethrough"):
            comp_dict["strikethrough"] = component.strikethrough
        return _parse_component_dict(comp_dict, default_color)

    return segments


def _parse_component_dict(comp: Dict[str, Any], default_color: Optional[Tuple[int, int, int]] = None) -> List[TextSegment]:
    """解析单个 component dict"""
    segments: List[TextSegment] = []

    # 继承父级格式
    color = parse_mc_color(comp.get("color", "")) or default_color
    bold = comp.get("bold", False)
    italic = comp.get("italic", False)
    underline = comp.get("underlined", False)
    strikethrough = comp.get("strikethrough", False)

    # 处理 text 字段
    text = comp.get("text", "")
    if text:
        # 检查 text 中是否包含 § 代码
        if "§" in text:
            segments.extend(parse_section_sign_text(text, color))
        else:
            segments.append(TextSegment(
                text=text,
                color=color,
                bold=bold,
                italic=italic,
                underline=underline,
                strikethrough=strikethrough,
            ))

    # 处理 extra 字段（子元素）
    extras = comp.get("extra", [])
    if isinstance(extras, list):
        for child in extras:
            # 子元素继承当前格式作为默认值
            child_segments = parse_component(child, default_color=color)
            # 但子元素自身的格式属性会覆盖
            if isinstance(child, dict):
                for seg in child_segments:
                    if "bold" in child:
                        seg.bold = bool(child["bold"])
                    if "italic" in child:
                        seg.italic = bool(child["italic"])
                    if "underlined" in child:
                        seg.underline = bool(child["underlined"])
                    if "strikethrough" in child:
                        seg.strikethrough = bool(child["strikethrough"])
                    if "color" in child:
                        seg.color = parse_mc_color(str(child["color"])) or seg.color
            segments.extend(child_segments)

    return segments


_HASHESX = "0123456789abcdef"


def parse_hex_color(digits: str) -> Optional[Tuple[int, int, int]]:
    """将 6 位十六进制字符串（RRGGBB）解析为 RGB 元组"""
    digits = digits.lower()
    if len(digits) == 6 and all(ch in _HASHESX for ch in digits):
        return (
            int(digits[0:2], 16),
            int(digits[2:4], 16),
            int(digits[4:6], 16),
        )
    return None


def parse_section_sign_text(text: str, default_color: Optional[Tuple[int, int, int]] = None) -> List[TextSegment]:
    """
    解析包含 § 格式代码的文本
    §0-§f: 旧版固定颜色代码
    §#RRGGBB: 1.16+ 十六进制颜色（支持更多颜色）
    §k: 随机字符(obfuscated, 忽略)
    §l: 粗体
    §m: 删除线
    §n: 下划线
    §o: 斜体
    §r: 重置
    """
    segments: List[TextSegment] = []
    current_text: List[str] = []
    current_color = default_color
    current_bold = False
    current_italic = False
    current_underline = False
    current_strikethrough = False

    def flush():
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
                # 1.16+ 十六进制颜色：§#RRGGBB，例如 §#ffcd1a → (255,205,26)
                hex_raw = text[i + 2:i + 8]
                if len(hex_raw) == 6 and all(ch.lower() in _HASHESX for ch in hex_raw):
                    rgb = parse_hex_color(hex_raw)
                    if rgb is not None:
                        current_color = rgb
                        i += 8
                        continue
                # 解析失败按普通字符处理 §#
                i += 2
            elif code in MC_COLOR_CODES:
                current_color = MC_COLOR_CODES[code]
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


def parse_with_mcstatus(motd: list[motd_components.ParsedMotdComponent]) -> List[MotdLine]:
    # debug usage
    # logger.info(motd)

    lines : List[MotdLine] = []

    if '\n' in motd:

        # This is a really dumb way to iterate and split list into two parts. But it'll work.
        part1_list : List[motd_components.ParsedMotdComponent] = []
        part2_list : List[motd_components.ParsedMotdComponent] = []
        final_list : List[List[motd_components.ParsedMotdComponent]] = []

        passed_changeline = False
        for member in motd:
            if (member != '\n') and (passed_changeline == False):
                part1_list.append(member)
            elif (member == '\n') and (passed_changeline == False):
                passed_changeline = True
            elif passed_changeline:
                part2_list.append(member)

        final_list.append(part1_list)
        final_list.append(part2_list)

    else:
        final_list : List[motd_components.ParsedMotdComponent] = motd
    
    current_line_segments : List[TextSegment] = []

    for thisline in final_list:
        format_indication : motd_components.JavaFormatting | None = None
        format_flags = {
            "bold": False,
            "italic": False,
            "underline": False,
            "strikethrough": False
        }
        color_indication : Tuple[int, int, int] | None = None
        default_color: Tuple[int, int, int] = (255, 255, 255)

        for index, seg in enumerate(thisline):
            if seg.__class__ == motd_components.JavaFormatting:
                format_indication = seg
                if seg == motd_components.JavaFormatting.RESET:
                    format_indication= None
                    color_indication = default_color
                    format_flags = {
                        "bold": False,
                        "italic": False,
                        "underline": False,
                        "strikethrough": False
                    }
                elif seg == motd_components.JavaFormatting.BOLD:
                    format_flags["bold"] = True
                elif seg == motd_components.JavaFormatting.ITALIC:
                    format_flags["italic"] = True
                elif seg == motd_components.JavaFormatting.UNDERLINED:
                    format_flags["underline"] = True
                elif seg == motd_components.JavaFormatting.STRIKETHROUGH:
                    format_flags["strikethrough"] = True
            elif seg.__class__ == motd_components.JavaMinecraftColor:
                # 还原 若在格式代码后使用颜色代码则重置格式保留颜色的特性
                if format_indication != None:
                    format_indication= None
                    format_flags = {
                        "bold": False,
                        "italic": False,
                        "underline": False,
                        "strikethrough": False
                    }

                color_indication = MC_COLOR_CODES.get(seg)
            elif seg.__class__ == motd_components.WebColor:
                # 还原 若在格式代码后使用颜色代码则重置格式保留颜色的特性
                if format_indication != None:
                    format_indication= None
                    format_flags = {
                        "bold": False,
                        "italic": False,
                        "underline": False,
                        "strikethrough": False
                    }

                color_indication = seg.rgb
            elif type(seg) is str:
                if format_indication == None:
                    current_line_segments.append(TextSegment(
                        text=seg,
                        color=color_indication
                    ))
                else:
                    current_line_segments.append(TextSegment(
                        text=seg,
                        color=color_indication,
                        bold=format_flags.bold,
                        italic=format_flags.italic,
                        underline=format_flags.underline,
                        strikethrough=format_flags.strikethrough
                    ))
        
        lines.append(MotdLine(segments=current_line_segments))
        current_line_segments = []
    
    # 确保至少有一行
    if not lines:
        lines.append(MotdLine(segments=[]))

    return lines


def manual_parse_motd(description: str) -> List[MotdLine]:
    """
    解析 MOTD 为 MotdLine 列表
    按 \n 分行
    """
    # 先获取所有 segments
    all_segments = parse_component(description)

    # 按换行符分割
    lines: List[MotdLine] = []
    current_line_segments: List[TextSegment] = []

    for seg in all_segments:
        if "\n" in seg.text:
            parts = seg.text.split("\n")
            for idx, part in enumerate(parts):
                if part:
                    current_line_segments.append(TextSegment(
                        text=part,
                        color=seg.color,
                        bold=seg.bold,
                        italic=seg.italic,
                        underline=seg.underline,
                        strikethrough=seg.strikethrough,
                    ))
                if idx < len(parts) - 1:
                    # 换行
                    if current_line_segments:
                        lines.append(MotdLine(segments=current_line_segments))
                    current_line_segments = []
        else:
            current_line_segments.append(seg)

    if current_line_segments:
        lines.append(MotdLine(segments=current_line_segments))

    # 确保至少有一行
    if not lines:
        lines.append(MotdLine(segments=[]))

    return lines


def parse_custom_note_text(text: str) -> List[TextSegment]:
    """
    解析自定义备注文本，支持:
    1. § 分节符格式代码
    2. <color:#hex>...</color> 标签语法
    """
    # 先解析 <color:#hex> 标签
    result_segments: List[TextSegment] = []
    pattern = re.compile(r'<color:([^>]+)>(.*?)</color>', re.DOTALL)

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


async def get_server_status(host):
    try:
        # 调用mcstatus获取服务器信息
        server : JavaServer = await JavaServer.async_lookup(host)
        # 使用异步方法查询服务器状态
        status : java_responses.JavaStatusResponse = await server.async_status(version=767)
        players_list : list = []
        latency : int = int(status.latency)
        plays_max : int = status.players.max
        plays_online : int = status.players.online
        server_version : str = status.version.name

        # 保存服务器图标
        if status.icon:
            icon_data = status.icon.split(",")[1]
        else:
            image_path = Path(__file__).resolve().parent.parent / 'resource' / 'default_icon.png'
            with open(image_path, 'rb') as image_file:
                # 读取图片文件内容
                image_data = image_file.read()
                # 对图片数据进行 Base64 编码
                base64_encoded = base64.b64encode(image_data)
            # 将编码后的字节数据转换为字符串
            icon_data = base64_encoded.decode('utf-8')

        # 查询服务器状态
        if status.players.sample:
            for player in status.players.sample:
                players_list.append(player.name)
        
        #自定义查询
        if host == csu_host:
                players_list = await fetch_players_names(csu_get_players)
                
        # 修改：相较于原版，这里保持服务器返回的玩家原顺序，不进行重排

        server_motd_object : mcstatus.motd.Motd = status.motd
        parsed_motd : mcstatus.motd.Motd = server_motd_object.parsed
        print(parsed_motd)
        

        # 原版风格的解析，用分节符来标识颜色； Legacy用
        # vanillastr_server_motd : str = status.motd.to_minecraft()

        # 调用 mcstatus提供的方法来更合理的parse.
        # 目前先采用其他方法兼容的格式，也就是Vibe出来的MotdLine和Segements
        motd_lines : List[MotdLine] = parse_with_mcstatus(parsed_motd)

        # Legacy：手工解析 MOTD
        # motd_lines = manual_parse_motd(vanillastr_server_motd)
        
        return {
            "players_list": players_list,  # 玩家昵称列表
            "latency": latency,  # 延迟
            "plays_max": plays_max,  # 最大玩家数
            "plays_online": plays_online,  # 在线玩家数
            "server_version": server_version,  # 服务器游戏版本
            "icon_base64": icon_data,  # 服务器图标base64
            "host": host,  # 服务器录入地址（用于渲染显示）
            "motd_lines": motd_lines,  # 解析后的 MOTD 行
        }

    except (socket.gaierror, ConnectionRefusedError) as e:
        logger.error(f"连接服务器失败: {e}")
        return None
    except asyncio.TimeoutError:
        logger.error(f"获取服务器状态超时")
        return None
    except Exception as e:
        logger.error(f"获取服务器状态时发生未知错误: {e}")
        return None


async def main():
    host = "csu-mc.org"  # 请替换为实际的服务器地址
    result = await get_server_status(host)
    if result:
        print(result['players_list'])
    else:
        print("未获取到服务器状态信息")


# 为csu定制
async def fetch_players_names(url: str) -> list[str]:
    """
    异步获取并解析玩家名称列表并且屏蔽bot_开头的玩家名称

    :param url: 数据接口URL
    :return: 玩家名称列表
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            # 检查响应状态码
            if response.status != 200:
                raise ValueError(f"请求失败，状态码: {response.status}")

            # 解析JSON数据
            data = await response.json()

            # 提取所有name字段
            names = [player["name"] for player in data.get("players", [])]

            # 使用正则表达式过滤掉以 'bot_' 开头的名称
            pattern = re.compile(r'^bot_')

            filtered_names = [name for name in names if not pattern.match(name)]

            return filtered_names


if __name__ == "__main__":
    asyncio.run(main())
