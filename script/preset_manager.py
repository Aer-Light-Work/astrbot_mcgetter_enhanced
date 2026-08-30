"""图片生成 preset 的加载、回退与访问。"""

import copy
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from astrbot.api import logger


# 内置默认 preset 配置（当 YAML 文件不存在时使用）
BUILTIN_PRESETS: Dict[str, Dict[str, Any]] = {
    "rich": {
        "name": "丰富样式",
        "style": "rich",
        "title": "Minecraft Server Status",
        "colors": {
            "background": [15, 15, 15],
            "title": [255, 255, 255],
            "text": [220, 220, 220],
            "accent": [85, 255, 85],
            "player_count": [85, 255, 85],
            "version": [170, 170, 170],
            "latency_good": [85, 255, 85],
            "latency_warn": [255, 170, 0],
            "latency_bad": [255, 85, 85],
            "timestamp": [120, 120, 120],
            "motd_colors": {
                "0": [0, 0, 0],
                "1": [0, 0, 170],
                "2": [0, 170, 0],
                "3": [0, 170, 170],
                "4": [170, 0, 0],
                "5": [170, 0, 170],
                "6": [255, 170, 0],
                "7": [170, 170, 170],
                "8": [85, 85, 85],
                "9": [85, 85, 255],
                "a": [85, 255, 85],
                "b": [85, 255, 255],
                "c": [255, 85, 85],
                "d": [255, 85, 255],
                "e": [255, 255, 85],
                "f": [255, 255, 255],
            },
        },
        "display": {
            "show_icon": True,
            "show_version": True,
            "show_address": False,
            "show_latency": True,
            "show_players": True,
            "show_motd": True,
            "show_notes": False,
            "show_query_time": True,
        },
        "fonts": {
            "group_title_size": 44,
            "title_size": 26,
            "text_size": 22,
            "small_size": 18,
        },
        "layout": {
            "width": 1177,
            "padding": 30,
            "icon_size": 100,
            "line_spacing": 8,
        },
    },
    "simple": {
        "name": "简洁样式",
        "style": "simple",
        "colors": {
            "background": [34, 34, 34],
            "title": [255, 255, 255],
            "text": [255, 255, 255],
            "accent": [85, 255, 85],
            "latency_good": [85, 255, 85],
            "latency_warn": [255, 170, 0],
            "latency_bad": [255, 85, 85],
        },
        "display": {
            "show_icon": True,
            "show_version": True,
            "show_address": True,
            "show_latency": True,
            "show_players": True,
            "show_motd": False,
            "show_notes": False,
            "show_query_time": False,
        },
        "fonts": {
            "title_size": 30,
            "text_size": 20,
            "small_size": 18,
        },
        "layout": {
            "width": 600,
            "padding": 20,
            "icon_size": 64,
            "line_spacing": 5,
        },
    },
}


class PresetManager:
    """管理 preset 配置的加载和访问"""

    def __init__(self, preset_dir: Optional[Path] = None):
        self._presets: Dict[str, Dict[str, Any]] = {}
        self._default_preset_name: str = "rich"

        if preset_dir is None:
            preset_dir = Path(__file__).resolve().parent.parent / "resource"

        self._preset_file = preset_dir / "presets.yaml"
        self._load_presets()

    def _load_presets(self) -> None:
        """从 YAML 文件加载 presets，失败则使用内置默认值"""
        if self._preset_file.exists():
            try:
                with open(self._preset_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                if data and "presets" in data:
                    self._presets = data["presets"]
                    self._default_preset_name = data.get("default_preset", "rich")
                    logger.info(
                        f"从 {self._preset_file} 加载了 {len(self._presets)} 个 preset"
                    )
                    return
            except Exception as e:
                logger.warning(f"加载 preset 文件失败: {e}，使用内置默认值")

        # 使用内置默认值
        # preset 可能被调用方按群组覆盖；内置嵌套配置必须彼此独立。
        self._presets = copy.deepcopy(BUILTIN_PRESETS)
        logger.info(f"使用内置默认 presets: {list(self._presets.keys())}")

    def get_preset(self, name: Optional[str] = None) -> Dict[str, Any]:
        """获取指定 preset，不存在则返回默认 preset"""
        if name is None:
            name = self._default_preset_name
        if name in self._presets:
            return self._presets[name]
        logger.warning(f"Preset '{name}' 不存在，使用默认 preset '{self._default_preset_name}'")
        return self._presets[self._default_preset_name]

    def list_presets(self) -> List[str]:
        """列出所有可用 preset 名称"""
        return list(self._presets.keys())

    def get_default_name(self) -> str:
        """获取默认 preset 名称"""
        return self._default_preset_name

    def reload(self) -> None:
        """重新加载 preset 文件"""
        self._load_presets()


# 全局单例
_preset_manager: Optional[PresetManager] = None


def get_preset_manager() -> PresetManager:
    """获取全局 PresetManager 单例"""
    global _preset_manager
    if _preset_manager is None:
        _preset_manager = PresetManager()
    return _preset_manager
