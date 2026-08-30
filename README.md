# AstrBot MC服务器状态获取(Aer改)

## 简介

AstrBot Minecraft服务器信息查询插件，原astrbot_mcgetter_enhanced, 可用于查询Minecraft服务器状态信息并使用图片展示。

原作插件设计了在线人数柱状图、多服务器支持、服务器Ping、玩家列表显示、自动清理等功能。

**注意：本改版并非原版。请不要将本改版独占问题反馈到上游。**

## 功能特性

- **多服务器** - 支持添加、删除、查询多个Minecraft服务器
- **Ping** - 获取服务器在线状态、玩家数量、延迟等信息
- **玩家列表显示** - 显示当前在线玩家列表
- **Rich图片渲染** - 将服务器信息渲染为更为美观的Rich预设图片
- **地址验证** - 自动验证服务器地址格式和连接性
- **分群** - 每个群组独立管理服务器列表
- **自动清理** - 自动删除长时间未查询成功的服务器
- **服务器以ID查询** - 基于ID的服务器管理系统，支持名称和ID双重操作
- ***预设** - 以yaml格式设计的颜色风格编排体系


*\*预设：上游原版插件基于*

## 安装说明
### (推荐)地址获取
1. 在 AstrBot WebUI 找到插件管理页面
2. 点击右下角添加按钮，采用URL
3. 将本仓库URL填入其中
4. 安装

其余可参照其他插件访问，并依照 AstrBot 文档排除故障。

### 手动置入-文件夹
1. 确保已安装 AstrBot
2. 将插件文件放入 AstrBot 插件目录
3. 重启 AstrBot 或重新加载插件
4. 在群聊中使用 `/mchelp` 查看帮助

## 使用方法

### 基础命令

| 命令 | 参数 | 说明 |
|------|------|------|
| `/mchelp` | 无 | 查看命令帮助 |
| `/mc` | 无 | 查询本群所有已保存服务器并生成状态图片 |
| `/mcadd` | 服务器名称 服务器地址 [True] | 添加服务器；加 `True` 可跳过预查询强制添加 |
| `/mcget` | 名称或 ID | 查看服务器地址 |
| `/mcdel` | 名称或 ID | 删除服务器 |
| `/mcup` | 名称或 ID [新名称] [新地址] | 更新服务器名称或地址，至少填写一项 |
| `/mclist` | 无 | 列出服务器 ID、名称和地址 |
| `/mccleanup` | 无 | 手动清理连续 10 天未成功查询的服务器 |
| `/mcdata` | [名称或 ID] [小时数] | 查看在线人数柱状图，默认最近 24 小时 |
| `/mcpreset` | [rich 或 simple] | 查看或切换图片样式 |
| `/mcnote` | 名称或 ID [备注] | 设置/清除服务器备注，备注支持空格和颜色代码 |
| `/mcalias` | 名称或 ID [别名] | 设置/清除服务器显示别名，别名支持空格 |
| `/mctoggle` | players / notes / time / id | 切换玩家列表、备注、查询时间或序号显示 |

除 `/mc`、`/mchelp`、`/mclist`、`/mccleanup` 外，管理命令中的“名称或 ID”均支持两种定位方式。若服务器名称包含空格，建议使用 `mclist` 查看 ID 后使用 ID 操作。

### 详细说明

#### 查看帮助
```text
/mchelp
```
显示按“查询、服务器管理、显示与样式、在线人数趋势”分组的命令说明和示例。

#### 添加服务器
```
/mcadd 服务器名称 服务器地址 [True]
```
- **服务器名称**: 自定义的服务器名称
- **服务器地址**: 服务器IP地址或域名（支持端口号）
- **True**: 可选参数，必须作为第三个参数传入；设为 `True` 时跳过预查询检查强制添加

**示例**:
```
/mcadd Hypixel mc.hypixel.net
/mcadd 本地服务器 127.0.0.1:25565 True
```

#### 查询服务器
```
/mc
```
查询所有已保存的服务器状态，返回包含以下信息的图片：
- 服务器名称和ID
- 在线状态
- 玩家数量（当前/最大）
- 服务器版本
- 延迟
- 在线玩家列表

**自动清理**: 每次执行 `/mc` 命令时会自动清理10天未查询成功的服务器

#### 获取服务器地址
```
/mcget 名称或ID
```
获取指定服务器的地址信息。支持通过名称或ID查找。

#### 删除服务器
```
/mcdel 名称或ID
```
从列表中删除指定的服务器。支持通过名称或ID删除。

#### 更新服务器信息
```
/mcup 名称或ID [新名称] [新地址]
```
更新指定服务器的名称或地址信息，至少填写新名称或新地址中的一项。名称和地址都不填时不会执行更新。

#### 列出所有服务器
```
/mclist
```
显示所有保存的服务器及其ID和地址。

#### 在线人数柱状图
```
/mcdata [名称或ID] [小时数]
```
查看全部服务器或指定服务器最近 N 小时的在线人数柱状图，小时数会限制在 1～168。

```text
/mcdata              # 全部服务器，默认 24 小时
/mcdata 48           # 全部服务器，最近 48 小时
/mcdata GTNH 48      # GTNH，最近 48 小时
/mcdata 2 24         # ID 为 2 的服务器，最近 24 小时
```

当只填写一个纯数字时：如果该数字不是已存在的服务器 ID，则按小时数处理；如果它是服务器 ID，则按服务器 ID 处理。

#### 手动清理
```
/mccleanup
```
手动触发自动清理，删除10天未查询成功的服务器。

#### 切换图片样式
```text
/mcpreset             # 查看当前 preset、可用 preset 和默认 preset
/mcpreset rich        # 切换为 rich 样式
/mcpreset simple      # 切换为 simple 样式
```

#### 设置备注
```text
/mcnote 名称或ID 备注内容
/mcnote 名称或ID       # 清除备注
```
备注参数会吸收命令后的剩余文本，因此可以包含空格；支持 `§` 颜色代码和 `<color:#hex>...</color>` 标签。

#### 设置显示别名
```text
/mcalias 名称或ID 别名
/mcalias 名称或ID       # 清除别名
```
别名参数会吸收命令后的剩余文本，因此可以包含空格。别名只改变图片中的显示名称，不会改变服务器原名称、地址或 ID。

#### 切换显示选项
```text
/mctoggle players       # 切换玩家列表
/mctoggle notes         # 切换备注
/mctoggle time          # 切换查询时间
/mctoggle id            # 切换服务器序号
```
每次执行同一选项都会在开启和关闭之间切换。可用选项只有 `players`、`notes`、`time` 和 `id`。

## 自动清理功能

### 功能特性
- **自动状态记录**: 记录服务器创建时间、最后成功/失败时间、失败次数
- **自动清理规则**: 服务器连续10天未查询成功时自动删除
- **清理时机**: 每次使用 `/mc` 命令时自动触发，或使用 `/mccleanup` 手动触发
- **清理提示**: 删除服务器时显示详细信息（名称、ID、地址、最后成功时间）

### 清理消息示例
```
自动清理完成，以下服务器因10天未查询成功已被删除:
• 过期服务器1 (ID: 2) - 地址: example.com:25565 - 最后成功: 2024-01-01 12:00:00
• 过期服务器2 (ID: 3) - 地址: test.server.com - 最后成功: 2024-01-02 15:30:00
```

## JSON配置系统

### 数据格式
插件使用基于ID的JSON配置系统，支持自动版本迁移：

```json
{
    "version": "2.3",
    "next_id": 5,
    "last_cleanup": 1752028440,
    
    "trends": {
        "1": {"history": [{"ts": 1752024800, "count": 5}, {"ts": 1752028400, "count": 7}]},
        "2": {"history": [{"ts": 1752024800, "count": 0}]}
    },
    "servers": {
        "1": {
            "id": 1,
            "name": "主服务器",
            "host": "main.example.com:25565",
            "created_time": 1752028440,
            "last_success_time": 1752028440,
            "last_failed_time": null,
            "failed_count": 0
        }
    }
}
```

### 主要特性
- **自动版本迁移**: 旧版配置会自动迁移到新版格式
- **ID管理**: 使用递增的数字ID，删除后不重用
- **向后兼容**: 支持通过名称或ID进行操作
- **状态跟踪**: 记录服务器查询状态和时间戳

## 支持的功能

- ✅ 多服务器管理
- ✅ 实时状态查询
- ✅ 玩家列表显示
- ✅ 图片化信息展示
- ✅ 地址格式验证
- ✅ 群组独立配置
- ✅ 强制添加模式
- ✅ 自动清理功能
- ✅ ID管理系统
- ✅ 服务器信息更新
- ✅ 状态跟踪记录

## 技术特性

- **地址验证**: 只允许字母、数字和符号 `.:-` 在服务器地址中
- **预查询检查**: 添加服务器前自动验证连接性
- **错误处理**: 完善的异常处理和用户友好的错误提示
- **日志记录**: 详细的操作日志便于调试
- **异步操作**: 所有操作都是异步的，性能优异
- **数据安全**: 删除操作前会显示详细信息

## 使用场景

### 场景1: 定期维护
```
1. 定期使用 /mc 命令查询服务器
2. 系统自动清理过期服务器
3. 查看清理结果，了解服务器状态
```

### 场景2: 服务器管理
```
1. 使用 /mclist 查看所有服务器
2. 通过 /mcget 获取特定服务器信息
3. 使用 /mcup 更新服务器信息
4. 用 /mcdel 删除不需要的服务器
```

### 场景3: 监控服务器状态（柱状图）
```
1. 添加服务器后系统默认开始按小时记录在线人数
2. 使用 /mcdata 查看全部服务器最近N小时柱状图

#### 柱状图指令使用示例
```
/mcdata              # 全部服务器，默认24小时
/mcdata 24           # 全部服务器，24小时
/mcdata GTNH 48      # 名称为 GTNH 的服务器，48小时
/mcdata 2 24         # ID 为 2 的服务器，24小时
```
3. 结合 /mc 实时状态图，定位波动与问题
```

## 配置参数

### 自动清理配置
- **清理天数**: 10天（可在代码中修改 `AUTO_CLEANUP_DAYS` 常量）
- **清理时机**: 每次 `/mc` 命令执行时
- **清理提示**: 显示被删除服务器的详细信息

### 字体与 Unicode 回退配置

可在 AstrBot 插件配置中设置以下字体选项：

```json
{
  "font_path": "/path/to/YourFont-Regular.ttf",
  "bold_font_path": "/path/to/YourFont-Bold.ttf",
  "heavier_font_weight": false
}
```

| 配置项 | 说明 |
|------|------|
| `font_path` | 常规字体文件路径，支持 `.ttf` / `.ttc`。留空时使用内置或系统默认加载逻辑。 |
| `bold_font_path` | 粗体字体文件路径。`§l`、Rich 标题、服务器名、人数、版本、延迟与时间等需要粗体的内容会优先使用它。留空时自动从 `font_path` 同目录查找字重变体。 |
| `heavier_font_weight` | 默认 `false`，仅在配置 `font_path` 后生效。开启时，常规文本优先使用同字体族的 `SemiBold`，`§l` 和界面粗体优先使用 `Bold`。 |

字体字重选择顺序：

```text
默认模式：Regular → Bold
整体加重模式：SemiBold → Bold
```

- 显式指定的 `bold_font_path` 优先级最高。
- 自动查找会跳过 `Italic` 变体，避免把斜体误作常规或粗体字体。
- 没有可用的真实粗体文件时，会将常规字形向右复制 1px 作为 fallback；不会使用四周扩张的描边，因此可避免明显的边缘光晕。测量、对齐与换行会使用同一实际字重的宽度。

未设置自定义字体时，项目会优先使用系统安装的 Noto Sans。若系统没有 Noto Sans，则直接以 `resource/unifont_all-17.0.05.hex` 完成渲染；即使使用 Noto Sans，遇到其不包含的 Unicode 字符也会按字符切换到 UniFont，以降低缺字方块出现的概率。Minecraft Mod 或资源包定义的私有区图标仍需要对应资源包字体，项目不会尝试还原。

### pytest 测试

```bash
# 首次运行时安装开发依赖
uv pip install --python .venv/bin/python -r requirements-dev.txt

# 聚合运行全部测试；真实服务器不可达时相关用例会跳过
.venv/bin/python -m pytest -v

# 仅运行不依赖真实服务器的回归测试
.venv/bin/python -m pytest -v -m "not real_server"
```

测试已按职责拆分，可按 marker 或文件单独执行：

```bash
# 纯文字解析、字体、字重、UniFont、测量与换行
.venv/bin/python -m pytest -v -m text_rendering

# 使用 mock 数据完成整图渲染
.venv/bin/python -m pytest -v -m image_rendering

# preset 配置与命令 handler
.venv/bin/python -m pytest -v -m presets
.venv/bin/python -m pytest -v -m commands

# 只 ping 真实 Minecraft 服务器，不生成图片
.venv/bin/python -m pytest -v -m server_ping

# 使用真实服务器数据完成 Rich 整图渲染
.venv/bin/python -m pytest -v -m server_rendering

# 也可直接指定模块
.venv/bin/python -m pytest -v tests/test_image_rendering.py
```

图片渲染测试会把生成的 PNG 导出到 `tests/test_output_*.png`（已被 Git 忽略），
可在每次运行后直接检查：mock 数据的 Rich/Simple/备注图片、柱状图，以及真实服务器
的三种字体图片都会保存在这里。

真实服务器地址默认为 `127.0.0.1:43596`，可用逗号分隔的 `MC_TEST_SERVERS` 覆盖。服务器不可达时默认跳过；如需在 CI 或验收环境中严格失败，可设置 `MC_TEST_REQUIRE_SERVER=1`：

```bash
MC_TEST_SERVERS="127.0.0.1:43596,example.com:25565" \
MC_TEST_REQUIRE_SERVER=1 \
.venv/bin/python -m pytest -v -m real_server
```

若要验证 `/mcadd` 的 Java SRV 预查询，可在本机临时提供测试地址；地址不会写入测试文件：

```bash
MC_TEST_SRV_SERVER="your-srv-server.example" \
MC_TEST_REQUIRE_SERVER=1 \
.venv/bin/python -m pytest -v -m srv_lookup
```

真实整图测试会复用同一模块级实时状态，分别输出默认字体、非默认字体和整体加重字体的 Rich 图片，便于人工比较：

```text
tests/test_output_ping_127.0.0.1:43596.png
tests/test_output_ping_127.0.0.1:43596_custom_font.png
tests/test_output_ping_127.0.0.1:43596_heavier_font_weight.png
```

## Presets 图片样式系统

### 简介
插件支持多种图片输出样式（Preset），通过 YAML 配置文件定义，可在群内自由切换。

### 可用样式
| Preset | 名称 | 说明 |
|--------|------|------|
| `rich` | 丰富样式（默认） | 群名称标题 + 服务器图标 + MOTD + 玩家列表 + 时间戳，支持 MC 颜色代码 |
| `simple` | 简洁样式 | 传统绿色边框布局，显示版本/地址/延迟 |

### Preset 相关命令

| 命令 | 参数 | 说明 |
|------|------|------|
| `/mcpreset` | 无 | 查看当前 preset 和可用列表 |
| `/mcpreset` | 名称 | 切换图片样式 preset |
| `/mcnote` | 服务器名称/ID [备注内容] | 设置/清除服务器自定义备注（支持 § 颜色代码和 `<color:#hex>` 标签） |
| `/mcalias` | 服务器名称/ID [别名] | 设置服务器显示别名 |
| `/mctoggle` | players / notes / time / id | 切换玩家列表 / 备注 / 查询时间 / 序号显示 |

### Rich 样式布局

```
┌──────────────────────────────────────────────┐
│              -群名称-（居中加粗大字）            │
│ [图标] 服务器名称(加粗)          4/23333(加粗)  │
│        MOTD行1（带颜色）          版本号(加粗)  │
│        MOTD行2（带颜色）           延迟(加粗)   │
│ 玩家1                                         │
│ 玩家2                                         │
│                          2026-08-16 18:00:35  │
──────────────────────────────────────────────┘
```

- **背景色**: `#0f0f0f`
- **群名称**: 居中、加粗、44px 大字号
- **服务器名称/在线人数/版本号/延迟**: 均加粗显示
- **MOTD**: 紧跟服务器名称下方，支持 Minecraft 原版颜色/格式代码
- **玩家列表**: 每人一行，超过 10 人时省略显示
- **图标**: 无图标时使用 `default_icon.png` 占位

### Minecraft 颜色代码支持

Rich 样式完整支持 Minecraft 原版格式代码：

| 代码 | 效果 | 代码 | 效果 |
|------|------|------|------|
| `§0`-`§f` | 16 种颜色 | `§l` | **粗体** |
| `§m` | ~~删除线~~ | `§n` | <u>下划线</u> |
| `§o` | *斜体* | `§r` | 重置格式 |

同时支持自定义 `<color:#hex>文字</color>` 标签语法（用于备注）。

### （重要）改版新增：自定义 Preset

编辑 `resource/presets.yaml` 可添加自定义样式，支持配置：
- 颜色方案（背景、标题、文字、延迟等）
- Rich 顶部标题（`title`，默认 `Minecraft Server Status`）
- 显示/隐藏各信息字段
- 字体大小
- 布局参数（宽度、内边距、图标尺寸等）

注意预设存在`rich`的style与`simple`的style. 其中`simple`对应原版插件提供的布局，而`rich`则提供近似与MC游戏内风格的布局。

Tip: 但`rich`风格的玩家列表仍然遵循放在MOTD以下的方式，只是以一行一个玩家名的原版风格展现。

本改版建议优先使用更为美观的`rich`风格，除非服务器需要更简洁的表现形式。


## 版本信息

- **插件版本**: 1.5.0
- **JSON格式版本**: 2.3
- **兼容性**: 兼容原插件数据

## 注意事项

### 1. 数据安全
- 删除操作不可逆，请谨慎使用
- 建议定期备份重要的服务器配置
- 清理前会显示详细的删除信息

### 2. 时间计算
- 基于Unix时间戳计算
- 精确到秒级别
- 自动处理时区问题

### 3. 性能考虑
- 清理操作是异步的，不会阻塞其他功能
- 只在必要时执行清理（有服务器需要清理时）
- 清理结果会缓存，避免重复计算

## 故障排除

### 常见问题

**Q: 为什么服务器没有被自动清理？**
A: 检查服务器的 `last_success_time` 是否真的超过10天，或者使用 `/mccleanup` 手动触发

**Q: 如何查看服务器的查询状态？**
A: 使用 `/mclist` 查看所有服务器，或直接查看JSON配置文件

**Q: 可以修改清理天数吗？**
A: 可以，修改 `script/json_operate.py` 中的 `AUTO_CLEANUP_DAYS` 常量

**Q: 清理操作会影响正常使用吗？**
A: 不会，清理操作是异步的，不会阻塞其他功能

**Q: 如何恢复被删除的服务器？**
A: 被删除的服务器无法自动恢复，需要重新使用 `/mcadd` 添加

**Q: 支持通过ID操作吗？**
A: 是的，所有命令都支持通过名称或ID进行操作

## 最佳实践

### 1. 定期维护
- 每周使用 `/mc` 命令查询一次所有服务器
- 定期使用 `/mccleanup` 手动清理
- 关注清理结果，及时处理问题

### 2. 服务器管理
- 及时删除不再使用的服务器
- 定期检查服务器状态
- 保持服务器列表的整洁

### 3. 监控建议
- 关注失败次数较多的服务器
- 定期检查最后成功时间
- 根据清理结果调整服务器配置

## 支持

- [AstrBot 帮助文档](https://astrbot.app)
- [GitHub Issues](https://github.com/xiaxoi68/astrbot_mcgetter_enhanced/issues)
### TODO

- [ ] 定时自动查询功能

## 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 贡献

欢迎提交 Issue 和 Pull Request 来改进这个插件！

## 鸣谢
- 原作者[exynos967](https://github.com/exynos967), 提供了这样一个简洁的MC服务器状态查询插件。
- [XruiDD](https://github.com/XruiDD)的Spark团队，其服务器查询插件渲染效果提供了`rich`预设的灵感。并激发了我创作preset系统修改这个插件。
- [PyMine团队](https://github.com/py-mine), 设计了本插件查询MC服务器所用的Python库[mcstatus](https://github.com/py-mine/mcstatus)

如果你喜欢这个改版的话，也请多多支持上面几位！

---

<div align="center">

**Made with ❤️ for Minecraft Community**

</div>
