from typing import List, Optional, Dict, Any
from pathlib import Path
import astrbot.core.message.components as Comp
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api import logger, AstrBotConfig
try:
    # GreedyStr 用于吸收命令剩余全部参数（v4.13+ 支持）
    from astrbot.core.star.filter.command import GreedyStr
except ImportError:
    GreedyStr = str
from .script.get_img import set_custom_font_path
from .script.get_server_info import get_server_status
from .script.get_img import generate_server_info_image, merge_server_info_images
from .script.bar_chart import generate_bar_chart_image
from .script.json_operate import (
    read_json, add_data, del_data, update_data, 
    get_all_servers, get_server_info, get_server_by_name,
    update_server_status, auto_cleanup_servers,
    append_trend_point, get_trend_history, get_all_trend_histories
)
from .script.preset_manager import get_preset_manager
import asyncio
import re
from datetime import datetime, timedelta

HELP_INFO = """
MC 服务器管理帮助

/mchelp
显示本帮助。

【查询】
/mc
查询本群已保存的所有服务器，并合并生成一张状态长图。

/mcget <名称或ID>
查看服务器地址。

/mclist
列出本群所有服务器的 ID、名称和地址。

【服务器管理】
/mcadd <服务器名称> <服务器地址> [True]
添加服务器。地址查询失败时，末尾加 True 可跳过预查询强制添加。
示例：/mcadd 生存服 127.0.0.1:25565

/mcup <名称或ID> [新名称] [新地址]
更新名称或地址，至少填写一项。
示例：/mcup 1 新生存服

/mcdel <名称或ID>
删除服务器。支持使用 ID 或原名称。

/mcalias <名称或ID> [别名]
设置显示别名；省略别名则清除别名。别名支持空格。
示例：/mcalias 1 我的生存服务器

/mcnote <名称或ID> [备注]
设置备注；省略备注则清除备注。备注支持空格、换行、§ 颜色代码和 <color:#hex> 标签。
示例：/mcnote 1 §a欢迎来到服务器

【显示与样式】
/mctoggle <players|notes|time|id>
切换玩家列表、备注、查询时间或服务器序号的显示状态。
再次执行同一选项即可恢复；可选项：players、notes、time、id。

/mcpreset [名称]
不填名称：查看当前和可用 preset；填写 rich 或 simple：切换图片样式。

【在线人数趋势】
/mcdata [名称或ID] [小时数]
查看在线人数柱状图，小时数范围为 1～168，默认 24 小时。
不填参数查看全部服务器；只填数字且该数字不是服务器 ID 时，数字会被当作小时数。
示例：/mcdata、/mcdata 48、/mcdata 1 72

/mccleanup
手动清理连续 10 天未成功查询的服务器。
"""

@register("astrbot_mcgetter_enhanced", "薄暝", "查询mc服务器信息和玩家列表,在线人数柱状图,渲染为图片(修改自QiChen的mcgetter)", "1.5.0")
class MyPlugin(Star):
    """Minecraft服务器信息查询插件"""
    
    def __init__(self, context: Context, config: AstrBotConfig = None):
        """
        初始化插件

        Args:
            context: 插件上下文
            config: 插件配置（来自 _conf_schema.json）
        """
        super().__init__(context)
        logger.info("MyPlugin 初始化完成")
        # 应用自定义字体配置（未配置则使用系统默认加载逻辑）
        font_path = (config or {}).get("font_path", "") if config else ""
        bold_font_path = (config or {}).get("bold_font_path", "") if config else ""
        heavier_font_weight = (config or {}).get("heavier_font_weight", False) if config else False
        set_custom_font_path(font_path, bold_font_path, heavier_font_weight)
        if font_path:
            logger.info(f"已设置自定义字体: {font_path}")
        if heavier_font_weight:
            logger.info("已启用整体加重字体：常规使用 SemiBold，粗体使用 Bold")
        # 启动每小时柱状图数据采样后台任务（单例，默认对所有已配置服务器启用）
        self._trend_task: Optional[asyncio.Task] = None
        if getattr(self, "_trend_task", None) is None:
            self._trend_task = asyncio.create_task(self._bar_data_loop())

    @filter.command("mchelp")
    async def get_help(self, event: AstrMessageEvent) -> MessageEventResult:
        """
        显示帮助信息

        Args:
            event: 消息事件

        Returns:
            包含帮助信息的消息结果
        """
        yield event.plain_result(HELP_INFO)

    @filter.command("mc")
    async def mcgetter(self, event: AstrMessageEvent) -> Optional[MessageEventResult]:
        """
        查询所有保存的服务器信息

        Args:
            event: 消息事件

        Returns:
            包含服务器信息图片的消息结果，如果出错则返回None
        """
        logger.info("开始执行 mc 命令")
        try:
            json_path = await self.get_event_json_path(event)
            logger.info(f"JSON文件路径: {json_path}")
            
            json_data = await read_json(json_path)
            logger.info(f"读取到的JSON数据: {json_data}")
            
            if not json_data or not json_data.get("servers"):
                logger.warning("JSON数据为空或没有服务器")
                yield event.plain_result("请先使用 /mcadd 添加服务器")
                return
            
            rendered_images: list[str] = []
            last_query_time: Optional[datetime] = None
            servers = json_data.get("servers", {})
            # 按 ID 升序遍历
            for server_id, server_info in sorted(servers.items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else 1_000_000_000):
                try:
                    logger.info(f"正在处理服务器: {server_info['name']} (ID: {server_id}), 信息: {server_info}")
                    mcinfo_img = await self.get_img(
                        server_info['name'], server_info['host'], server_id, str(json_path),
                        suppress_query_time=True, suppress_title=True,
                    )
                    if mcinfo_img:
                        rendered_images.append(mcinfo_img)
                        last_query_time = datetime.now()
                        logger.info(f"成功加入合并图，服务器名称: {server_info['name']} (ID: {server_id})")
                    else:
                        logger.warning(f"获取服务器 {server_info['name']} (ID: {server_id}) 的图片失败")
                except Exception as e:
                    logger.error(f"处理服务器 {server_info['name']} (ID: {server_id}) 时出错: {e}")
                    continue

            message_chain: List[Comp.Image] = []
            if rendered_images:
                merged_image = await merge_server_info_images(
                    rendered_images,
                    last_query_time or datetime.now(),
                    preset_name=json_data.get("preset"),
                    display_override=json_data.get("display") or None,
                )
                message_chain.append(Comp.Image.fromBase64(merged_image))

            # 查询更新完成后再执行自动清理，避免误删刚成功的服务器
            deleted_servers = await auto_cleanup_servers(json_path)
            if deleted_servers:
                cleanup_message = "自动清理完成，以下服务器因10天未查询成功已被删除:\n"
                for server in deleted_servers:
                    last_success_date = datetime.fromtimestamp(server['last_success_time']).strftime('%Y-%m-%d %H:%M:%S')
                    cleanup_message += f"• {server['name']} (ID: {server['id']}) - 地址: {server['host']} - 最后成功: {last_success_date}\n"
                # 先发送查询结果，再提示清理
                if message_chain:
                    yield event.chain_result(message_chain)
                yield event.plain_result(cleanup_message.strip())
                return

            if message_chain:
                logger.info("成功生成一张合并状态图")
                yield event.chain_result(message_chain)
            else:
                logger.warning("没有可用的服务器信息")
                yield event.plain_result("没有可用的服务器信息，请检查服务器是否在线")
                
        except Exception as e:
            logger.error(f"执行 mc 命令时出错: {e}")
            yield event.plain_result("查询服务器信息时发生错误")

    @filter.command("mcadd")
    async def mcadd(self, event: AstrMessageEvent, name: str, host: str, force: bool = False) -> MessageEventResult:
        """
        添加新的服务器

        Args:
            event: 消息事件
            name: 服务器名称
            host: 服务器地址
            force: 是否强制添加（跳过预查询检查）

        Returns:
            操作结果消息
        """
        logger.info(f"开始执行 mcadd 命令: {name} -> {host}, force: {force}")
        
        try:
            # 检查host合法性
            if not re.match(r'^[a-zA-Z0-9.:-]+$', host):
                yield event.plain_result("服务器地址格式不正确，只能包含字母、数字和符号.:-")
                return
            elif not force and await get_server_status(host) is None:
                yield event.plain_result("预查询失败，请检查服务器是否在线或地址是否正确，或在完整的/mcadd命令后加上True 强制添加")
                return
                
            json_path = await self.get_event_json_path(event)
            
            # 检查当前地址是否已存在
            try:
                json_data = await read_json(json_path)
                servers = json_data.get("servers", {})
                if servers:
                    for server_id, server_info in servers.items():
                        if server_info['host'] == host:
                            yield event.plain_result(f"已存在相同地址的服务器 {server_info['name']} (ID: {server_id})")
                            return
            except Exception as e:
                logger.error(f"检查服务器地址时出错: {e}")
                yield event.plain_result("检查服务器地址时发生错误")
                return
                
            if await add_data(json_path, name, host):
                # 获取新添加的服务器ID
                json_data = await read_json(json_path)
                servers = json_data.get("servers", {})
                for server_id, server_info in servers.items():
                    if server_info['name'] == name and server_info['host'] == host:
                        yield event.plain_result(f"成功添加服务器 {name} (ID: {server_id})")
                        return
                yield event.plain_result(f"成功添加服务器 {name}")
            else:
                yield event.plain_result(f"无法添加 {name}，请检查是否已存在")
                
        except Exception as e:
            logger.error(f"执行 mcadd 命令时出错: {e}")
            yield event.plain_result("添加服务器时发生错误")

    @filter.command("mcdel")
    async def mcdel(self, event: AstrMessageEvent, identifier: str) -> MessageEventResult:
        """
        删除指定的服务器（支持通过名称或ID删除）

        Args:
            event: 消息事件
            identifier: 要删除的服务器名称或ID

        Returns:
            操作结果消息
        """
        logger.info(f"开始执行 mcdel 命令: {identifier}")
        try:
            json_path = await self.get_event_json_path(event)
            
            if await del_data(json_path, identifier):
                yield event.plain_result(f"成功删除服务器 {identifier}")
            else:
                yield event.plain_result(f"无法删除 {identifier}，请检查是否存在")
                
        except Exception as e:
            logger.error(f"执行 mcdel 命令时出错: {e}")
            yield event.plain_result("删除服务器时发生错误")

    @filter.command("mcget")
    async def mcget(self, event: AstrMessageEvent, identifier: str) -> MessageEventResult:
        """
        获取指定服务器的信息（支持通过名称或ID查找）
        """
        logger.info(f"开始执行 mcget 命令: {identifier}")
        try:
            json_path = await self.get_event_json_path(event)
            
            server_info = await get_server_info(json_path, identifier)
            if not server_info:
                yield event.plain_result(f"没有找到服务器 {identifier}")
                return
                
            yield event.plain_result(f"{server_info['name']} (ID: {server_info['id']}) 的地址是:")
            yield event.plain_result(f"{server_info['host']}")
            
        except Exception as e:
            logger.error(f"执行 mcget 命令时出错: {e}")
            yield event.plain_result("获取服务器信息时发生错误")

    @filter.command("mcup")
    async def mcup(self, event: AstrMessageEvent, identifier: str, new_name: Optional[str] = None, new_host: Optional[str] = None) -> MessageEventResult:
        """
        更新服务器信息（支持通过名称或ID更新）

        Args:
            event: 消息事件
            identifier: 要更新的服务器名称或ID
            new_name: 新的服务器名称（可选）
            new_host: 新的服务器地址（可选）

        Returns:
            操作结果消息
        """
        logger.info(f"开始执行 mcup 命令: {identifier}, new_name: {new_name}, new_host: {new_host}")
        
        try:
            if not new_name and not new_host:
                yield event.plain_result("请提供要更新的信息（新名称或新地址）")
                return
                
            # 如果提供了新地址，检查格式
            if new_host and not re.match(r'^[a-zA-Z0-9.:-]+$', new_host):
                yield event.plain_result("服务器地址格式不正确，只能包含字母、数字和符号.:-")
                return
                
            json_path = await self.get_event_json_path(event)
            
            if await update_data(json_path, identifier, new_name, new_host):
                # 获取更新后的服务器信息
                updated_info = await get_server_info(json_path, identifier)
                if updated_info:
                    yield event.plain_result(f"成功更新服务器信息: {updated_info['name']} (ID: {updated_info['id']})")
                else:
                    yield event.plain_result(f"成功更新服务器 {identifier}")
            else:
                yield event.plain_result(f"无法更新 {identifier}，请检查是否存在或名称是否冲突")
                
        except Exception as e:
            logger.error(f"执行 mcup 命令时出错: {e}")
            yield event.plain_result("更新服务器信息时发生错误")

    @filter.command("mclist")
    async def mclist(self, event: AstrMessageEvent) -> MessageEventResult:
        """
        列出所有服务器及其ID
        """
        logger.info("开始执行 mclist 命令")
        try:
            json_path = await self.get_event_json_path(event)
            
            servers = await get_all_servers(json_path)
            if not servers:
                yield event.plain_result("没有保存的服务器")
                return
                
            server_list = "当前保存的服务器列表:\n"
            for server_id, server_info in sorted(servers.items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else 1_000_000_000):
                server_list += f"ID: {server_id}, 名称: {server_info['name']}, 地址: {server_info['host']}\n"
                
            yield event.plain_result(server_list.strip())
            
        except Exception as e:
            logger.error(f"执行 mclist 命令时出错: {e}")
            yield event.plain_result("获取服务器列表时发生错误")

    @filter.command("mccleanup")
    async def mccleanup(self, event: AstrMessageEvent) -> MessageEventResult:
        """
        手动触发自动清理（删除10天未查询成功的服务器）
        """
        logger.info("开始执行 mccleanup 命令")
        try:
            json_path = await self.get_event_json_path(event)
            
            deleted_servers = await auto_cleanup_servers(json_path)
            if deleted_servers:
                cleanup_message = "自动清理完成，以下服务器因10天未查询成功已被删除:\n"
                for server in deleted_servers:
                    last_success_date = datetime.fromtimestamp(server['last_success_time']).strftime('%Y-%m-%d %H:%M:%S')
                    cleanup_message += f"• {server['name']} (ID: {server['id']}) - 地址: {server['host']} - 最后成功: {last_success_date}\n"
                yield event.plain_result(cleanup_message.strip())
            else:
                yield event.plain_result("没有需要清理的服务器")
                
        except Exception as e:
            logger.error(f"执行 mccleanup 命令时出错: {e}")
            yield event.plain_result("自动清理时发生错误")

    @filter.command("mcdata")
    async def mcdata(self, event: AstrMessageEvent, identifier: Optional[str] = None, hours: int = 24) -> Optional[MessageEventResult]:
        """输出当前群全部或指定服务器最近N小时（默认24）的在线人数柱状图。"""
        try:
            json_path = await self.get_event_json_path(event)
            servers = await get_all_servers(str(json_path))
            if not servers:
                yield event.plain_result("当前群无已配置服务器，请先使用 /mcadd 添加。")
                return

            logger.info(f"mcdata 参数: identifier={identifier!r}, hours={hours!r}")

            # 解析参数：
            # - 单参数为纯数字且没有同ID服务器时 → 作为小时数（全部服务器）
            # - 否则 → 作为服务器名称/ID（统一转为字符串）
            if identifier is not None:
                ident_str = str(identifier)
                if ident_str.isdigit():
                    maybe = await get_server_info(str(json_path), ident_str)
                    if maybe is None:
                        # 视为小时数
                        try:
                            hours = int(ident_str)
                            identifier = None
                        except Exception:
                            identifier = ident_str
                    else:
                        identifier = ident_str
                else:
                    identifier = ident_str

            # 规范化 hours 范围
            try:
                hours = int(hours)
            except Exception:
                hours = 24
            hours = max(1, min(168, hours))
            logger.info(f"mcdata 解析后: target={'ALL' if not identifier else identifier}, hours={hours}")

            images: List[Comp.Image] = []
            if identifier:
                # 单服务器模式
                try:
                    sinfo = await get_server_info(str(json_path), identifier)
                    if not sinfo:
                        yield event.plain_result(f"没有找到服务器 {identifier}")
                        return
                    sid = str(sinfo.get("id"))
                    name = sinfo.get("name", f"ID:{sid}")
                    # 与 mc 行为对齐：当前不可达则跳过
                    host = sinfo.get("host")
                    status_now = await get_server_status(host) if host else None
                    if not status_now:
                        yield event.plain_result(f"{name} 当前不可达，已跳过")
                        return
                    hist = await get_trend_history(str(json_path), sid, hours=hours)
                    img_b64 = generate_bar_chart_image(hist or [], name, hours=hours)
                    images.append(Comp.Image.fromBase64(img_b64))
                except Exception as ie:
                    logger.error(f"mcdata 单服生成失败: id={identifier}, hours={hours}, err={ie}")
                    raise
            else:
                # 全部服务器模式
                try:
                    all_hist = await get_all_trend_histories(str(json_path), hours=hours)
                    for sid, sinfo in sorted(servers.items(), key=lambda kv: int(kv[0]) if str(kv[0]).isdigit() else 1_000_000_000):
                        name = sinfo.get("name", f"ID:{sid}")
                        host = sinfo.get("host")
                        # 与 mc 行为对齐：当前不可达则跳过该服
                        try:
                            status_now = await get_server_status(host) if host else None
                        except Exception as ie:
                            logger.debug(f"mcdata 全服检测失败: {name} host={host} err={ie}")
                            status_now = None
                        if not status_now:
                            continue
                        hist = all_hist.get(str(sid), [])
                        img_b64 = generate_bar_chart_image(hist or [], name, hours=hours)
                        images.append(Comp.Image.fromBase64(img_b64))
                except Exception as ie:
                    logger.error(f"mcdata 全服生成失败: hours={hours}, err={ie}")
                    raise

            if images:
                yield event.chain_result(images)
            else:
                yield event.plain_result("暂无柱状图数据，稍后再试。")
        except Exception as e:
            logger.error(f"生成柱状图失败: {e}")
            yield event.plain_result("生成柱状图失败，请稍后再试。")

    async def get_img(
        self,
        server_name: str,
        host: str,
        server_id: Optional[str] = None,
        json_path: Optional[str] = None,
        suppress_query_time: bool = False,
        suppress_title: bool = False,
    ) -> Optional[str]:
        """
        获取服务器信息图片

        Args:
            server_name: 服务器名称
            host: 服务器地址
            server_id: 服务器ID（可选）
            json_path: JSON文件路径（用于更新状态）
            suppress_query_time: 合并图片时关闭子图的重复时间戳
            suppress_title: 合并图片时关闭子图的重复顶部标题

        Returns:
            图片的base64编码字符串，如果获取失败则返回None
        """
        logger.info(f"开始获取服务器 {server_name} 的图片，主机地址: {host}")
        try:
            info = await get_server_status(host)
            if not info:
                logger.error(f"无法获取服务器 {server_name} 的状态信息")
                # 更新查询失败状态
                if json_path and server_id:
                    await update_server_status(json_path, server_id, False)
                return None

            # 更新查询成功状态
            if json_path and server_id:
                await update_server_status(json_path, server_id, True)

            # 默认对所有服务器记录小时数据：出现异常记录到日志便于排查
            try:
                if json_path and server_id:
                    await append_trend_point(json_path, str(server_id), int(datetime.now().timestamp()), int(info['plays_online']))
            except Exception as e:
                logger.warning(f"追加柱状图数据失败 group={json_path}, sid={server_id}: {e}")

            info['server_name'] = server_name
            # 如果有服务器ID，则在名称前添加ID（默认开启，可在群内通过 /mctoggle id 关闭）
            show_id = True

            # 读取群配置（preset、显示选项、别名、备注）
            preset_name = None
            note_text = None
            alias_name = None
            display_override = None
            if json_path:
                try:
                    json_data = await read_json(json_path)
                    preset_name = json_data.get("preset")
                    display_override = json_data.get("display") or None
                    show_id = json_data.get("show_id", True)
                    # 查找服务器别名和备注
                    if server_id:
                        servers = json_data.get("servers", {})
                        srv = servers.get(str(server_id), {})
                        alias_name = srv.get("alias")
                        note_text = srv.get("note")
                except Exception as e:
                    logger.debug(f"读取群配置失败: {e}")

            if suppress_query_time:
                display_override = dict(display_override or {})
                display_override["show_query_time"] = False

            # 使用别名作为显示名称
            base_name = alias_name if alias_name else server_name
            display_name = f"[{server_id}]{base_name}" if (server_id and show_id) else base_name

            mcinfo_img = await generate_server_info_image(
                players_list=info['players_list'],
                latency=info['latency'],
                server_name=display_name,
                plays_max=info['plays_max'],
                plays_online=info['plays_online'],
                server_version=info['server_version'],
                icon_base64=info['icon_base64'],
                host_address=info.get('host', host),
                preset_name=preset_name,
                motd_lines=info.get('motd_lines'),
                note_text=note_text,
                group_name=None,
                display_override=display_override,
                suppress_preset_title=suppress_title,
            )
            logger.info(f"成功生成服务器 {server_name} 的图片")
            return mcinfo_img
            
        except Exception as e:
            logger.error(f"获取服务器 {server_name} 的图片时出错: {e}")
            # 更新查询失败状态
            if json_path and server_id:
                await update_server_status(json_path, server_id, False)
            return None

    async def _get_group_config(self, json_path: str) -> Dict[str, Any]:
        """读取群配置"""
        try:
            data = await read_json(json_path)
            return data
        except Exception:
            return {}

    async def _save_group_config(self, json_path: str, config: Dict[str, Any]) -> bool:
        """保存群配置"""
        try:
            data = await read_json(json_path)
            data.update(config)
            from .script.json_operate import write_json
            await write_json(json_path, data)
            return True
        except Exception as e:
            logger.error(f"保存群配置失败: {e}")
            return False

    @filter.command("mcpreset")
    async def mcpreset(self, event: AstrMessageEvent, name: Optional[str] = None) -> MessageEventResult:
        """查看/切换图片样式preset"""
        try:
            json_path = await self.get_event_json_path(event)
            pm = get_preset_manager()

            if name is None:
                # 查看当前 preset 和可用列表
                config = await self._get_group_config(str(json_path))
                current = config.get("preset", pm.get_default_name())
                available = pm.list_presets()
                msg = f"当前 preset: {current}\n可用 preset: {', '.join(available)}\n默认 preset: {pm.get_default_name()}"
                yield event.plain_result(msg)
            else:
                # 切换 preset
                available = pm.list_presets()
                if name not in available:
                    yield event.plain_result(f"preset '{name}' 不存在，可用: {', '.join(available)}")
                    return
                config = await self._get_group_config(str(json_path))
                config["preset"] = name
                if await self._save_group_config(str(json_path), config):
                    yield event.plain_result(f"已切换为 preset: {name}")
                else:
                    yield event.plain_result("切换 preset 失败")
        except Exception as e:
            logger.error(f"执行 mcpreset 命令时出错: {e}")
            yield event.plain_result("切换 preset 时发生错误")

    @filter.command("mcnote")
    async def mcnote(self, event: AstrMessageEvent, identifier: str, note_text_arg: GreedyStr = "") -> MessageEventResult:
        """设置/清除服务器自定义备注"""
        try:
            json_path = await self.get_event_json_path(event)

            # 查找服务器
            sinfo = await get_server_info(str(json_path), identifier)
            if not sinfo:
                yield event.plain_result(f"没有找到服务器 {identifier}")
                return

            sid = str(sinfo.get("id"))
            note_text = note_text_arg.strip() if note_text_arg and note_text_arg.strip() else None

            # 更新服务器备注
            data = await read_json(str(json_path))
            servers = data.get("servers", {})
            if sid in servers:
                if note_text:
                    servers[sid]["note"] = note_text
                    yield event.plain_result(f"已设置服务器 {sinfo['name']} 的备注")
                else:
                    servers[sid].pop("note", None)
                    yield event.plain_result(f"已清除服务器 {sinfo['name']} 的备注")
                data["servers"] = servers
                from .script.json_operate import write_json
                await write_json(str(json_path), data)
            else:
                yield event.plain_result("更新备注失败")
        except Exception as e:
            logger.error(f"执行 mcnote 命令时出错: {e}")
            yield event.plain_result("设置备注时发生错误")

    @filter.command("mcalias")
    async def mcalias(self, event: AstrMessageEvent, identifier: str, alias_text_arg: GreedyStr = "") -> MessageEventResult:
        """设置服务器显示别名"""
        try:
            json_path = await self.get_event_json_path(event)

            sinfo = await get_server_info(str(json_path), identifier)
            if not sinfo:
                yield event.plain_result(f"没有找到服务器 {identifier}")
                return

            sid = str(sinfo.get("id"))
            alias_text = alias_text_arg.strip() if alias_text_arg and alias_text_arg.strip() else None

            data = await read_json(str(json_path))
            servers = data.get("servers", {})
            if sid in servers:
                if alias_text:
                    servers[sid]["alias"] = alias_text
                    yield event.plain_result(f"已设置服务器 {sinfo['name']} 的别名为: {alias_text}")
                else:
                    servers[sid].pop("alias", None)
                    yield event.plain_result(f"已清除服务器 {sinfo['name']} 的别名")
                data["servers"] = servers
                from .script.json_operate import write_json
                await write_json(str(json_path), data)
            else:
                yield event.plain_result("更新别名失败")
        except Exception as e:
            logger.error(f"执行 mcalias 命令时出错: {e}")
            yield event.plain_result("设置别名时发生错误")

    @filter.command("mctoggle")
    async def mctoggle(self, event: AstrMessageEvent, option: str) -> MessageEventResult:
        """切换显示选项：players/notes/time/id"""
        try:
            json_path = await self.get_event_json_path(event)

            option = option.lower()
            valid_options = {
                "players": "display:show_players",
                "notes": "display:show_notes",
                "time": "display:show_query_time",
                "id": "show_id",
            }

            if option not in valid_options:
                yield event.plain_result(f"无效选项，可选: {', '.join(valid_options.keys())}")
                return

            target = valid_options[option]
            data = await read_json(str(json_path))

            if option == "id":
                # 序号开关存放在群配置顶层
                current = data.get("show_id", True)
                data["show_id"] = not current
                from .script.json_operate import write_json
                await write_json(str(json_path), data)
            else:
                config_key = target.split(":", 1)[1]
                display = data.get("display", {})
                current = display.get(config_key, True)
                display[config_key] = not current
                data["display"] = display
                from .script.json_operate import write_json
                await write_json(str(json_path), data)

            state = "开启" if not current else "关闭"
            option_names = {"players": "玩家列表", "notes": "备注", "time": "查询时间", "id": "序号显示"}
            yield event.plain_result(f"已{state}{option_names[option]}")
        except Exception as e:
            logger.error(f"执行 mctoggle 命令时出错: {e}")
            yield event.plain_result("切换显示选项时发生错误")

    async def get_json_path(self, group_id: Optional[str]) -> Path:
        """
        获取群组的JSON配置文件路径

        Args:
            group_id: 群组ID，不能为空且不能包含路径分隔符

        Returns:
            JSON文件的Path对象
        """
        normalized_group_id = str(group_id or "").strip()
        if not normalized_group_id:
            raise ValueError("无法获取有效群组ID，拒绝创建未命名配置文件")
        if (
            normalized_group_id in {".", ".."}
            or "/" in normalized_group_id
            or "\\" in normalized_group_id
            or "\x00" in normalized_group_id
        ):
            raise ValueError("群组ID包含非法路径字符")

        data_path = StarTools.get_data_dir("astrbot_mcgetter")
        json_path = data_path / f'{normalized_group_id}.json'
        json_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info(f"群号 {normalized_group_id} 的 JSON 文件路径: {json_path}")
        return json_path

    async def get_event_json_path(self, event: AstrMessageEvent) -> Path:
        """为群聊或私聊事件生成隔离的持久化配置路径。"""
        try:
            group_id = event.get_group_id()
        except Exception:
            group_id = None
        if str(group_id or "").strip():
            return await self.get_json_path(group_id)

        sender_getter = getattr(event, "get_sender_id", None)
        try:
            sender_id = sender_getter() if callable(sender_getter) else None
        except Exception:
            sender_id = None
        if not str(sender_id or "").strip():
            raise ValueError("无法获取群组ID或私聊发送者ID")
        return await self.get_json_path(f"private_{sender_id}")

    async def _bar_data_loop(self):
        """每小时扫描所有群配置，按 host 去重采样一次并写回所有群，保证跨群一致。"""
        while True:
            try:
                data_dir = StarTools.get_data_dir("astrbot_mcgetter")
                host_map: Dict[str, list] = {}
                if data_dir.exists():
                    # 先构建 host → [(json_path, sid), ...] 的映射
                    for p in data_dir.glob("*.json"):
                        try:
                            data = await read_json(str(p))
                            servers = data.get("servers", {})
                            for sid, sinfo in servers.items():
                                host = (sinfo or {}).get("host")
                                if not host:
                                    continue
                                host_map.setdefault(str(host), []).append((str(p), str(sid)))
                        except Exception as e:
                            logger.warning(f"数据采样预处理失败: {p.name}: {e}")

                # 逐 host 采样一次，并写回所有关联群文件
                now_ts = int(datetime.now().timestamp())
                for host, targets in host_map.items():
                    try:
                        status = await get_server_status(host)
                        if status and isinstance(status.get("plays_online"), int):
                            cnt = int(status["plays_online"])
                            for json_path, sid in targets:
                                try:
                                    await append_trend_point(json_path, sid, now_ts, cnt)
                                except Exception as ie:
                                    logger.debug(f"写入柱状图数据失败 host={host} file={json_path} sid={sid}: {ie}")
                    except Exception as ie:
                        logger.debug(f"host 采样失败 host={host}: {ie}")

                # 计算距离下个整点的秒数
                now = datetime.now()
                next_hour = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
                sleep_seconds = max(10, int((next_hour - now).total_seconds()))
                await asyncio.sleep(sleep_seconds)
            except Exception as e:
                logger.error(f"数据采样循环异常: {e}")
                await asyncio.sleep(300)
