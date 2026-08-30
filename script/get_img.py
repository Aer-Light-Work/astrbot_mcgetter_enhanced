"""服务器状态图片的字体回退、文本绘制与布局实现。"""

import base64
import io
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont
from astrbot.api import logger

from .get_server_info import (
    TextSegment, MotdLine, parse_custom_note_text, parse_section_sign_text, MC_COLOR_CODES
)
from .preset_manager import get_preset_manager

# 自定义字体文件路径（可通过 set_custom_font_path 设置，默认为空使用系统加载逻辑）
_custom_font_path: Optional[str] = None
_custom_bold_font_path: Optional[str] = None


class UniFontHex:
    """GNU UniFont .hex 的按需位图字形读取器。"""

    def __init__(self, path: Path):
        self.path = path
        self._offsets: Dict[int, int] = {}
        self._glyphs: Dict[int, Tuple[int, int, bytes]] = {}
        self._indexed = False

    def _ensure_index(self) -> None:
        if self._indexed:
            return
        try:
            with self.path.open("rb") as source:
                while True:
                    offset = source.tell()
                    line = source.readline()
                    if not line:
                        break
                    codepoint, separator, _ = line.partition(b":")
                    if separator:
                        try:
                            self._offsets[int(codepoint, 16)] = offset
                        except ValueError:
                            pass
        except OSError as error:
            logger.warning(f"UniFont 索引加载失败: {self.path}: {error}")
        self._indexed = True

    def glyph(self, char: str) -> Optional[Tuple[int, int, bytes]]:
        codepoint = ord(char)
        self._ensure_index()
        if codepoint not in self._offsets:
            return None
        if codepoint not in self._glyphs:
            try:
                with self.path.open("rb") as source:
                    source.seek(self._offsets[codepoint])
                    _, hex_data = source.readline().decode("ascii").strip().split(":", 1)
                data = bytes.fromhex(hex_data)
                # UniFont .hex 的每行固定 16 行，高度为 16；每行字节数决定宽度。
                if len(data) % 16:
                    return None
                self._glyphs[codepoint] = (len(data) // 16 * 8, 16, data)
            except (OSError, UnicodeDecodeError, ValueError):
                return None
        return self._glyphs[codepoint]


_unifont = UniFontHex(Path(__file__).resolve().parent.parent / "resource" / "unifont_all-17.0.05.hex")


class RenderFont:
    """一个字号下的主 TrueType 字体、粗体字体与 UniFont 回退集合。"""

    def __init__(self, regular: ImageFont.ImageFont, bold: Optional[ImageFont.ImageFont], size: int):
        self.regular = regular
        self.bold = bold
        self.size = size

    @staticmethod
    def _has_glyph(font: ImageFont.ImageFont, char: str) -> bool:
        if char.isspace():
            return True
        try:
            # Pillow 对未覆盖字符会给出与 U+FFFF 相同的 .notdef mask。
            mask = font.getmask(char)
            missing_mask = font.getmask("\uffff")
            return (mask.size, bytes(mask)) != (missing_mask.size, bytes(missing_mask))
        except Exception:
            return False

    def source_for(self, char: str, bold: bool = False) -> str:
        font = self.bold if bold and self.bold is not None else self.regular
        if self._has_glyph(font, char):
            return "ttf-bold" if bold and self.bold is not None else "ttf"
        return "unifont" if _unifont.glyph(char) else "ttf"

    def advance(self, char: str, bold: bool = False) -> int:
        source = self.source_for(char, bold)
        if source == "unifont":
            glyph = _unifont.glyph(char)
            return max(1, round(glyph[0] * self.size / 16)) if glyph else 0
        font = self.bold if source == "ttf-bold" else self.regular
        width = int(round(font.getlength(char)))
        # 没有真实粗体文件时，draw_segments 会在右侧复制一个整数像素。
        if bold and self.bold is None:
            width += 1
        return width

    def ascent(self) -> int:
        try:
            return self.regular.getmetrics()[0]
        except Exception:
            return self.size


def set_custom_font_path(
    font_path: Optional[str], bold_font_path: Optional[str] = None, heavier_font_weight: bool = False,
) -> None:
    """
    设置自定义字体路径，None/空字符串 则恢复系统默认加载逻辑
    bold_font_path: 粗体字体文件路径（可选）。未指定时自动在同目录下查找 SemiBold/Bold 变体
    heavier_font_weight: 开启时以 SemiBold 作为常规字体、Bold 作为粗体字体
    """
    global _custom_font_path, _custom_bold_font_path
    if font_path:
        original_path = str(font_path)
        _custom_font_path = (
            _find_font_variant(original_path, ("SemiBold",)) if heavier_font_weight else None
        ) or original_path
        if bold_font_path:
            _custom_bold_font_path = str(bold_font_path)
        elif heavier_font_weight:
            _custom_bold_font_path = _find_font_variant(original_path, ("Bold",))
        else:
            _custom_bold_font_path = _guess_bold_font_path(original_path)
    else:
        _custom_font_path = None
        _custom_bold_font_path = None


def _find_font_variant(regular_path: str, variants: Tuple[str, ...]) -> Optional[str]:
    """从同一字体族中查找指定字重的非斜体字体文件。"""
    try:
        base = Path(regular_path)
        directory = base.parent
        if not directory.exists():
            return None
        prefix = base.stem.replace("-Regular", "").replace("Regular", "").strip("-")
        candidates = []
        for variant in variants:
            candidates.extend(directory.glob(f"*{prefix}*{variant}*"))
        for candidate in sorted(set(candidates)):
            if candidate.suffix.lower() not in {".ttf", ".ttc", ".otf"}:
                continue
            if "italic" not in candidate.stem.lower():
                return str(candidate)
    except Exception:
        pass
    return None


def _guess_bold_font_path(regular_path: str) -> Optional[str]:
    """从常规字体路径猜测同目录下的粗体变体（SemiBold / Bold）"""
    return _find_font_variant(regular_path, ("SemiBold", "Bold"))


async def load_font(font_size, bold: bool = False):
    """加载字体，bold=True 时优先加载粗体字体文件"""
    # 粗体：优先使用粗体字体文件
    if bold and _custom_bold_font_path:
        try:
            return ImageFont.truetype(_custom_bold_font_path, font_size)
        except OSError as e:
            logger.warning(f"粗体字体加载失败: {_custom_bold_font_path}: {e}，回退到常规字体")

    # 用户自定义字体路径优先
    if _custom_font_path:
        try:
            return ImageFont.truetype(_custom_font_path, font_size)
        except OSError as e:
            logger.warning(f"自定义字体加载失败: {_custom_font_path}: {e}，回退到系统默认字体")

    # 尝试多路径加载
    font_paths = [
        Path(__file__).resolve().parent.parent / 'resource' / 'msyh.ttf',
        'msyh.ttf',  # 当前目录
        '/usr/share/fonts/zh_CN/msyh.ttf',  # Linux常见路径
        'C:/Windows/Fonts/msyh.ttc',  # Windows路径
        '/System/Library/Fonts/Supplemental/Songti.ttc'  # macOS路径
    ]

    for path in font_paths:
        try:
            return ImageFont.truetype(str(path), font_size)
        except OSError:
            continue

    # 全部失败时使用默认字体（添加中文支持）
    try:
        return ImageFont.load_default().font_variant(size=font_size)
    except:
        return ImageFont.load_default()


async def load_render_font(font_size: int) -> RenderFont:
    """加载一组用于实际绘制、测量与 UniFont 回退的字体。"""
    regular = await load_font(font_size)
    bold = await load_font(font_size, bold=True)
    # load_font 在没有粗体变体时会回退常规字体；此时描边模拟比伪装为真粗体更准确。
    if bold is regular or getattr(bold, "path", None) == getattr(regular, "path", None):
        bold = None
    return RenderFont(regular, bold, font_size)


async def fetch_icon(icon_base64: Optional[str] = None) -> Optional[Image.Image]:
    """处理Base64编码的服务器图标，无图标时返回默认图标占位"""
    if not icon_base64:
        return load_default_icon()

    try:
        # 去除可能的Base64前缀
        if "," in icon_base64:
            icon_base64 = icon_base64.split(",", 1)[1]
        icon_data = base64.b64decode(icon_base64)
        return Image.open(io.BytesIO(icon_data)).convert("RGBA")
    except Exception as e:
        logger.warning(f"Base64 图标解码失败: {e}")
        return load_default_icon()


def load_default_icon() -> Optional[Image.Image]:
    """加载默认占位图标"""
    try:
        path = Path(__file__).resolve().parent.parent / 'resource' / 'default_icon.png'
        return Image.open(path).convert("RGBA")
    except Exception as e:
        logger.warning(f"默认图标加载失败: {e}")
        return None


def _as_render_font(font: ImageFont.ImageFont | RenderFont) -> RenderFont:
    return font if isinstance(font, RenderFont) else RenderFont(font, None, getattr(font, "size", 16))


def measure_text(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont | RenderFont, bold: bool = False,
) -> int:
    """以最终实际使用的字体（含 UniFont 回退）测量文本宽度。"""
    render_font = _as_render_font(font)
    return sum(render_font.advance(char, bold) for char in text)


def _seg_width(draw: ImageDraw.ImageDraw, seg: TextSegment, font: ImageFont.ImageFont | RenderFont) -> int:
    """按最终粗体/回退字体测量单个文本段。"""
    return measure_text(draw, seg.text, font, seg.bold)


def _font_runs(text: str, font: RenderFont, bold: bool) -> Iterable[Tuple[str, str]]:
    """按实际字体来源合并连续字符，避免逐字符调用 Pillow。"""
    current_source: Optional[str] = None
    current_text = ""
    for char in text:
        source = font.source_for(char, bold)
        if current_source is not None and source != current_source:
            yield current_source, current_text
            current_text = ""
        current_source = source
        current_text += char
    if current_source is not None:
        yield current_source, current_text


def _draw_unifont_char(
    image: Image.Image, x: int, y: int, char: str, font: RenderFont, color: Tuple[int, int, int], bold: bool,
) -> int:
    glyph = _unifont.glyph(char)
    if glyph is None:
        return 0
    width, height, data = glyph
    bitmap = Image.frombytes("1", (width, height), data)
    scaled_width = max(1, round(width * font.size / 16))
    scaled_height = max(1, round(height * font.size / 16))
    bitmap = bitmap.resize((scaled_width, scaled_height), Image.Resampling.NEAREST)
    # UniFont 的 16px 字高以基线为参考，与当前 TrueType 字体基线对齐。
    glyph_y = y + font.ascent() - scaled_height
    colored = Image.new("RGB", bitmap.size, color)
    image.paste(colored, (x, glyph_y), bitmap.convert("L"))
    if bold:
        image.paste(colored, (x + 1, glyph_y), bitmap.convert("L"))
    return scaled_width


def draw_segments(
    draw: ImageDraw.ImageDraw,
    x: int, y: int,
    segments: List[TextSegment],
    font: ImageFont.ImageFont | RenderFont,
    default_color: Tuple[int, int, int],
    bold_font: Optional[ImageFont.ImageFont] = None,
) -> int:
    """
    绘制带格式的文本段，返回绘制后的 x 坐标
    粗体优先使用粗体字体文件（bold_font），否则回退描边模拟；下划线/删除线用线条绘制
    """
    render_font = _as_render_font(font)
    if bold_font is not None:
        render_font.bold = bold_font
    image = draw._image
    current_x = x
    for seg in segments:
        if not seg.text:
            continue

        color = seg.color if seg.color else default_color
        segment_x = current_x

        for source, run in _font_runs(seg.text, render_font, seg.bold):
            if source == "unifont":
                for char in run:
                    current_x += _draw_unifont_char(image, current_x, y, char, render_font, color, seg.bold)
                continue
            active_font = render_font.bold if source == "ttf-bold" else render_font.regular
            if seg.bold and source == "ttf" and render_font.bold is None:
                # 不使用 stroke_width：描边会在字形四周制造抗锯齿光晕。
                # 仅向右复制一个整数像素，模拟增加字重并保持边缘收敛。
                draw.text((current_x, y), run, font=active_font, fill=color)
                draw.text((current_x + 1, y), run, font=active_font, fill=color)
            else:
                draw.text((current_x, y), run, font=active_font, fill=color)
            current_x += measure_text(draw, run, render_font, seg.bold)

        text_width = _seg_width(draw, seg, render_font)

        # 下划线
        if seg.underline:
            baseline_y = y + render_font.size - 2
            draw.line(
                [(segment_x, baseline_y), (segment_x + text_width, baseline_y)],
                fill=color, width=1
            )

        # 删除线
        if seg.strikethrough:
            mid_y = y + render_font.size // 2
            draw.line(
                [(segment_x, mid_y), (segment_x + text_width, mid_y)],
                fill=color, width=1
            )

    return current_x


def draw_segments_centered(
    draw: ImageDraw.ImageDraw,
    center_x: int, y: int,
    segments: List[TextSegment],
    font: ImageFont.ImageFont | RenderFont,
    default_color: Tuple[int, int, int],
    bold_font: Optional[ImageFont.ImageFont] = None,
) -> int:
    """居中绘制文本段"""
    total_width = sum(_seg_width(draw, seg, font) for seg in segments if seg.text)
    start_x = center_x - total_width // 2
    return draw_segments(draw, start_x, y, segments, font, default_color, bold_font)


def draw_segments_right_aligned(
    draw: ImageDraw.ImageDraw,
    right_x: int, y: int,
    segments: List[TextSegment],
    font: ImageFont.ImageFont | RenderFont,
    default_color: Tuple[int, int, int],
    bold_font: Optional[ImageFont.ImageFont] = None,
) -> int:
    """右对齐绘制文本段"""
    total_width = sum(_seg_width(draw, seg, font) for seg in segments if seg.text)
    start_x = right_x - total_width
    return draw_segments(draw, start_x, y, segments, font, default_color, bold_font)


def wrap_segments_to_lines(
    draw: ImageDraw.ImageDraw,
    segments: List[TextSegment],
    font: ImageFont.ImageFont | RenderFont,
    max_width: int,
) -> List[List[TextSegment]]:
    """将文本段按最大宽度折行"""
    lines: List[List[TextSegment]] = []
    current_line: List[TextSegment] = []
    current_width = 0

    for seg in segments:
        if not seg.text:
            continue
        seg_width = _seg_width(draw, seg, font)

        if current_width + seg_width <= max_width:
            current_line.append(seg)
            current_width += seg_width
        else:
            if current_line:
                lines.append(current_line)
            # 如果单个段就超过宽度，按字符折行
            if seg_width > max_width:
                remaining = seg.text
                while remaining:
                    chunk = ""
                    chunk_w = 0
                    for ch in remaining:
                        ch_w = measure_text(draw, ch, font, seg.bold)
                        if chunk_w + ch_w <= max_width:
                            chunk += ch
                            chunk_w += ch_w
                        else:
                            break
                    if not chunk:
                        chunk = remaining[0]
                    lines.append([TextSegment(
                        text=chunk, color=seg.color, bold=seg.bold,
                        italic=seg.italic, underline=seg.underline,
                        strikethrough=seg.strikethrough,
                    )])
                    remaining = remaining[len(chunk):]
                current_line = []
                current_width = 0
            else:
                current_line = [seg]
                current_width = seg_width

    if current_line:
        lines.append(current_line)

    return lines


def split_segments_by_newline(segments: List[TextSegment]) -> List[List[TextSegment]]:
    """将带 \\n 的 segments 按换行符拆分为多行，保留各段颜色/格式"""
    lines: List[List[TextSegment]] = []
    current: List[TextSegment] = []

    for seg in segments:
        if "\n" in seg.text:
            parts = seg.text.split("\n")
            for i, part in enumerate(parts):
                if part:
                    current.append(TextSegment(
                        text=part,
                        color=seg.color,
                        bold=seg.bold,
                        italic=seg.italic,
                        underline=seg.underline,
                        strikethrough=seg.strikethrough,
                    ))
                if i < len(parts) - 1:
                    if current:
                        lines.append(current)
                        current = []
        else:
            current.append(seg)

    if current:
        lines.append(current)

    return lines


async def generate_server_info_image(
    players_list: list,
    latency: int,
    server_name: str,
    plays_max: int,
    plays_online: int,
    server_version: str,
    icon_base64: Optional[str] = None,
    host_address: Optional[str] = None,
    preset_name: Optional[str] = None,
    motd_lines: Optional[list] = None,
    note_text: Optional[str] = None,
    group_name: Optional[str] = None,
    display_override: Optional[dict] = None,
) -> str:
    """生成服务器信息图片并返回base64编码"""

    # 获取 preset 配置
    pm = get_preset_manager()
    preset = pm.get_preset(preset_name)
    # 群级显示选项覆盖 preset 默认值
    if display_override:
        merged = dict(preset)
        display = dict(preset.get("display", {}))
        display.update(display_override)
        merged["display"] = display
        preset = merged
    style_type = preset.get("style", "simple")

    if style_type == "rich":
        return await _generate_rich_image(
            players_list, latency, server_name, plays_max, plays_online,
            server_version, icon_base64, host_address, preset,
            motd_lines, note_text, group_name,
        )
    else:
        return await _generate_simple_image(
            players_list, latency, server_name, plays_max, plays_online,
            server_version, icon_base64, host_address, preset,
        )


async def _generate_simple_image(
    players_list: list,
    latency: int,
    server_name: str,
    plays_max: int,
    plays_online: int,
    server_version: str,
    icon_base64: Optional[str] = None,
    host_address: Optional[str] = None,
    preset: Optional[dict] = None,
) -> str:
    """简洁样式（原有逻辑）"""
    if preset is None:
        preset = get_preset_manager().get_preset("simple")

    colors = preset.get("colors", {})
    display = preset.get("display", {})
    fonts_cfg = preset.get("fonts", {})
    layout_cfg = preset.get("layout", {})

    BG_COLOR = tuple(colors.get("background", [34, 34, 34]))
    TEXT_COLOR = tuple(colors.get("text", [255, 255, 255]))
    ACCENT_COLOR = tuple(colors.get("accent", [85, 255, 85]))
    LATENCY_GOOD = tuple(colors.get("latency_good", [85, 255, 85]))
    LATENCY_WARN = tuple(colors.get("latency_warn", [255, 170, 0]))
    LATENCY_BAD = tuple(colors.get("latency_bad", [255, 85, 85]))

    title_font = await load_render_font(fonts_cfg.get("title_size", 30))
    text_font = await load_render_font(fonts_cfg.get("text_size", 20))
    small_font = await load_render_font(fonts_cfg.get("small_size", 18))

    server_icon = await fetch_icon(icon_base64) if display.get("show_icon", True) else None

    icon_size = layout_cfg.get("icon_size", 64) if server_icon else 0
    padding = layout_cfg.get("padding", 20)
    img_width = layout_cfg.get("width", 600)

    base_y = padding
    text_x = padding + icon_size + padding

    # 测量
    tmp_img = Image.new("RGB", (img_width, 10), color=BG_COLOR)
    tmp_draw = ImageDraw.Draw(tmp_img)

    name_line_height = 40
    version_text = f"版本: {server_version}"
    addr_text = f"  地址: {host_address}" if host_address and display.get("show_address", True) else ""
    version_addr_text = version_text + addr_text
    latency_text = f"延迟: {latency}ms"
    allowed_left_width = max(60, img_width - padding - text_x)

    # 简单折行
    def wrap_text_simple(text, font, max_w):
        if not text:
            return [text] if text else []
        lines = []
        current = ""
        for ch in text:
            trial = current + ch
            if measure_text(tmp_draw, trial, font) <= max_w:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = ch
        if current:
            lines.append(current)
        return lines

    version_addr_lines = wrap_text_simple(version_addr_text, text_font, allowed_left_width)
    online_title = f"在线玩家 ({plays_online}/{plays_max})"
    online_title_height = 40

    players_area_max_width = img_width - padding - (text_x + 20)

    def wrap_players_simple(players, font, max_w):
        if not players:
            return []
        lines = []
        current = ""
        sep = " • "
        for name in players:
            part = name if not current else current + sep + name
            if measure_text(tmp_draw, part, font) <= max_w:
                current = part
            else:
                if current:
                    lines.append(current)
                if measure_text(tmp_draw, name, font) > max_w:
                    for chunk in wrap_text_simple(name, font, max_w):
                        lines.append(chunk)
                    current = ""
                else:
                    current = name
        if current:
            lines.append(current)
        return lines

    players_lines = wrap_players_simple(players_list or [], small_font, players_area_max_width)
    line_height = 30

    calc_y = base_y
    calc_y += name_line_height
    calc_y += max(len(version_addr_lines), 1) * 40
    calc_y += online_title_height
    calc_y += max(len(players_lines), 1) * line_height
    img_height = calc_y + padding

    img = Image.new("RGB", (img_width, img_height), color=BG_COLOR)
    draw = ImageDraw.Draw(img)

    if server_icon:
        icon_mask = Image.new("L", (icon_size, icon_size), 0)
        mask_draw = ImageDraw.Draw(icon_mask)
        mask_draw.rounded_rectangle((0, 0, icon_size, icon_size), radius=10, fill=255)
        server_icon_resized = server_icon.resize((icon_size, icon_size))
        img.paste(server_icon_resized, (padding, base_y), icon_mask)

    draw_segments(draw, text_x, base_y, [TextSegment(text=server_name, bold=True)], title_font, ACCENT_COLOR)
    base_y += 40

    for i, line in enumerate(version_addr_lines):
        draw_segments(draw, text_x, base_y, [TextSegment(text=line)], text_font, TEXT_COLOR)
        base_y += 40

    draw_segments(draw, text_x, base_y, [TextSegment(text=online_title, bold=True)], text_font, ACCENT_COLOR)
    lat_w = measure_text(draw, latency_text, text_font, bold=True)
    latency_color = LATENCY_GOOD if latency < 100 else LATENCY_WARN if latency < 200 else LATENCY_BAD
    draw_segments(draw, img_width - padding - lat_w, base_y, [TextSegment(text=latency_text, bold=True)], text_font, latency_color)
    base_y += 40

    if players_lines:
        for line in players_lines:
            draw_segments(draw, text_x + 20, base_y, [TextSegment(text=line)], small_font, TEXT_COLOR)
            base_y += line_height
    else:
        draw_segments(draw, text_x + 20, base_y, [TextSegment(text="暂无玩家在线")], small_font, TEXT_COLOR)
        base_y += line_height

    draw.rounded_rectangle(
        [10, 10, img.width - 10, img.height - 10],
        radius=10, outline=ACCENT_COLOR, width=2
    )

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


async def _generate_rich_image(
    players_list: list,
    latency: int,
    server_name: str,
    plays_max: int,
    plays_online: int,
    server_version: str,
    icon_base64: Optional[str] = None,
    host_address: Optional[str] = None,
    preset: Optional[dict] = None,
    motd_lines: Optional[list] = None,
    note_text: Optional[str] = None,
    group_name: Optional[str] = None,
) -> str:
    """
    丰富样式布局（参考图）：
    ┌────────────────────────────────────────────┐
    │              -群名称-（居中加粗大字）          │
    │ [图标] 服务器名称(加粗)          4/23333     │
    │        MOTD行1                  版本号       │
    │        MOTD行2                  延迟         │
    │ 玩家1                                        │
    │ 玩家2                                        │
    │                         2026-08-16 18:00:35 │
    └────────────────────────────────────────────┘
    MOTD 说明：单行过长会自动按左栏可用宽度折行；
               多行(\n)各行分别折行，依次向下排列。
    说明：图标为直角（无圆角）、与左侧文本垂直居中对齐；
         在线人数与版本/延迟同字号；时间戳粗体贴右下角。
    """
    if preset is None:
        preset = get_preset_manager().get_preset("rich")

    colors = preset.get("colors", {})
    display = preset.get("display", {})
    fonts_cfg = preset.get("fonts", {})
    layout_cfg = preset.get("layout", {})

    BG_COLOR = tuple(colors.get("background", [15, 15, 15]))
    TITLE_COLOR = tuple(colors.get("title", [255, 255, 255]))
    TEXT_COLOR = tuple(colors.get("text", [220, 220, 220]))
    PLAYER_COUNT_COLOR = tuple(colors.get("player_count", [85, 255, 85]))
    VERSION_COLOR = tuple(colors.get("version", [170, 170, 170]))
    LATENCY_GOOD = tuple(colors.get("latency_good", [85, 255, 85]))
    LATENCY_WARN = tuple(colors.get("latency_warn", [255, 170, 0]))
    LATENCY_BAD = tuple(colors.get("latency_bad", [255, 85, 85]))
    TIMESTAMP_COLOR = tuple(colors.get("timestamp", [120, 120, 120]))

    group_title_size = fonts_cfg.get("group_title_size", 44)
    title_size = fonts_cfg.get("title_size", 26)      # 服务器别名大小（与 MOTD 差距不宜过大）
    text_size = fonts_cfg.get("text_size", 22)        # MOTD / 版本 / 延迟 大小
    small_size = fonts_cfg.get("small_size", 18)

    img_width = layout_cfg.get("width", 1177)
    padding = layout_cfg.get("padding", 30)
    icon_size = layout_cfg.get("icon_size", 100)
    line_spacing = layout_cfg.get("line_spacing", 8)

    group_title_font = await load_render_font(group_title_size)
    title_font = await load_render_font(title_size)
    text_font = await load_render_font(text_size)
    small_font = await load_render_font(small_size)
    group_title_bold_font = None
    title_bold_font = None
    text_bold_font = None
    small_bold_font = None

    # 服务器图标：缺失或解码失败时 fetch_icon 会回退到内置默认图标。
    server_icon = await fetch_icon(icon_base64) if display.get("show_icon", True) else None

    # 解析备注
    note_segments = None
    if note_text and display.get("show_notes", False):
        note_segments = parse_custom_note_text(note_text)

    # MOTD 行
    motd_lines = motd_lines or []
    show_motd = display.get("show_motd", True)

    # 左栏文本起始 x（名称/MOTD 区域）
    name_x = padding + icon_size + 15 if server_icon else padding
    # 右栏（人数/版本/延迟）右对齐的右边界
    right_x = img_width - padding
    # 动态测量右栏最大文本宽度（人数/版本/延迟，均为 text_font）
    tmp_measure_img = Image.new("RGB", (img_width, 10), color=BG_COLOR)
    tmp_measure_draw = ImageDraw.Draw(tmp_measure_img)
    right_col_width = max(
        measure_text(tmp_measure_draw, f"{plays_online}/{plays_max}", text_font, bold=True),
        measure_text(tmp_measure_draw, server_version, text_font, bold=True),
        measure_text(tmp_measure_draw, f"{latency}ms", text_font, bold=True),
    )
    # 左栏 MOTD 最大可用宽度：不超过右栏左边界，并预留 20px 间隔，
    # 避免 MOTD 过长时波及右侧版本号和延迟
    motd_max_width = max(60, (right_x - right_col_width - 20) - name_x)
    # 对 MOTD 折行：单行过长自动换行到下一行，多行(\n)各行分别折行
    motd_wrapped_lines: List[List[TextSegment]] = []
    if show_motd:
        tmp_img = Image.new("RGB", (img_width, 10), color=BG_COLOR)
        tmp_draw = ImageDraw.Draw(tmp_img)
        for motd_line in motd_lines:
            motd_wrapped_lines.extend(
                wrap_segments_to_lines(tmp_draw, motd_line.segments, text_font, motd_max_width)
            )

    # 行高
    #   name_line_h = title_size + line_spacing   （别名行高）
    #   motd_line_h = text_size + line_spacing    （每行 MOTD 行高）
    # 头部文本总高 = name_line_h + 2 * motd_line_h（右栏版本+延迟占两行）
    #   → 默认值 = (26+8) + 2*(22+8) = 94
    # layout/icon_size 建议设为略大于该总高（默认取 100），
    # 图标与文本会自动在头部区域内垂直居中。
    # 调整方法：先改 fonts/title_size、fonts/text_size、layout/line_spacing，
    # 再按上式计算总高并更新 layout/icon_size。
    name_line_h = title_size + line_spacing
    motd_line_h = text_size + line_spacing
    small_line_h = small_size + 6

    # 头部区域行数：名称行 + max(MOTD折行后总行数, 2)（右栏版本+延迟占两行）
    header_text_h = name_line_h + max(len(motd_wrapped_lines), 2) * motd_line_h
    header_h = max(icon_size, header_text_h)
    # 图标与文本在头部区域内垂直居中偏移量
    header_text_offset_y = (header_h - header_text_h) // 2
    header_icon_offset_y = (header_h - icon_size) // 2

    # 底部区域（玩家列表/备注）
    bottom_lines: List[List[TextSegment]] = []
    if note_segments:
        tmp_img = Image.new("RGB", (img_width, 10), color=BG_COLOR)
        tmp_draw = ImageDraw.Draw(tmp_img)
        # 先按 \n 拆分为多行，再对每行按宽度折行
        note_lines = split_segments_by_newline(note_segments)
        for note_line in note_lines:
            bottom_lines.extend(
                wrap_segments_to_lines(
                    tmp_draw, note_line, small_font, img_width - 2 * padding - 20
                )
            )
    elif display.get("show_players", True):
        players = players_list or []
        max_items = 10
        shown = players[:max_items]
        if shown:
            for name in shown:
                # 玩家名可能包含 § 颜色/格式代码，需要正常解析渲染
                if "§" in name:
                    # 只有颜色/格式代码没有文本时（如 §7），parse 返回空列表，
                    # 渲染为空行（遵循原版规律，行高保留）
                    name_segments = parse_section_sign_text(name)
                else:
                    name_segments = [TextSegment(text=name, color=TEXT_COLOR)]
                bottom_lines.append(name_segments)
            if len(players) > max_items:
                bottom_lines.append([TextSegment(
                    text=f"…… 等共 {len(players)} 名玩家", color=TIMESTAMP_COLOR
                )])
        else:
            bottom_lines.append([TextSegment(text="暂无玩家在线", color=TEXT_COLOR)])

    bottom_h = len(bottom_lines) * small_line_h if bottom_lines else 0

    # 计算总高度
    y = padding
    group_title_h = 0
    if group_name:
        group_title_h = group_title_size + 16
    total_height = (
        padding
        + group_title_h
        + header_h
        + 14                      # 头部与底部间隔
        + bottom_h
        + (small_size + 10 if display.get("show_query_time", True) else 0)
        + padding
    )
    img_height = total_height

    # 创建画布
    img = Image.new("RGB", (img_width, img_height), color=BG_COLOR)
    draw = ImageDraw.Draw(img)

    right_x = img_width - padding

    # 1. 群名称标题（居中、加粗、大字号）
    if group_name:
        draw_segments_centered(
            draw, img_width // 2, y,
            [TextSegment(text=group_name, color=TITLE_COLOR, bold=True)],
            group_title_font, TITLE_COLOR,
            group_title_bold_font,
        )
        y += group_title_h

    # 2. 头部区域：图标 + 名称/MOTD + 右栏人数/版本/延迟
    header_top = y

    if server_icon:
        # 直角图标（无圆角）：以自身 alpha 通道作为蒙版直接粘贴
        server_icon_resized = server_icon.resize((icon_size, icon_size))
        img.paste(
            server_icon_resized, (padding, header_top + header_icon_offset_y),
            server_icon_resized,
        )

    text_top = header_top + header_text_offset_y

    # 左栏：服务器名称（加粗）
    draw_segments(
        draw, name_x, text_top,
        [TextSegment(text=server_name, color=TITLE_COLOR, bold=True)],
        title_font, TITLE_COLOR,
        title_bold_font,
    )

    # 左栏：MOTD 行（紧跟名称行下方；过长已按 motd_max_width 折行）
    if show_motd:
        for i, line_segs in enumerate(motd_wrapped_lines):
            draw_segments(
                draw, name_x, text_top + name_line_h + i * motd_line_h,
                line_segs, text_font, TEXT_COLOR,
                text_bold_font,
            )

    # 右栏：在线人数、版本号、延迟（均用 text_font，与版本/延迟保持同字号）
    draw_segments_right_aligned(
        draw, right_x, text_top,
        [TextSegment(text=f"{plays_online}/{plays_max}", color=PLAYER_COUNT_COLOR, bold=True)],
        text_font, PLAYER_COUNT_COLOR,
        text_bold_font,
    )
    draw_segments_right_aligned(
        draw, right_x, text_top + name_line_h,
        [TextSegment(text=server_version, color=VERSION_COLOR, bold=True)],
        text_font, VERSION_COLOR,
        text_bold_font,
    )
    latency_color = LATENCY_GOOD if latency < 100 else LATENCY_WARN if latency < 200 else LATENCY_BAD
    draw_segments_right_aligned(
        draw, right_x, text_top + name_line_h + motd_line_h,
        [TextSegment(text=f"{latency}ms", color=latency_color, bold=True)],
        text_font, latency_color,
        text_bold_font,
    )

    y = header_top + header_h + 14

    # 3. 底部区域：玩家列表（每人一行）/ 备注
    for line_segs in bottom_lines:
        draw_segments(draw, padding + 5, y, line_segs, small_font, TEXT_COLOR, small_bold_font)
        y += small_line_h

    # 4. 查询时间（右下角，粗体，减短右下留白更贴近边缘）
    if display.get("show_query_time", True):
        from datetime import datetime
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        draw_segments_right_aligned(
            draw, img_width - 10, img_height - small_size - 6,
            [TextSegment(text=time_str, color=TIMESTAMP_COLOR, bold=True)],
            small_font, TIMESTAMP_COLOR,
            small_bold_font,
        )

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")
