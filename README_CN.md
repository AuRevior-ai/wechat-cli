<div align="center">

# WeChat CLI

**面向用户与 AI Agent 的本地微信数据访问工具，并包含产品化的 Windows 0.5.0 路线。**

[![npm version](https://img.shields.io/npm/v/@canghe_ai/wechat-cli.svg)](https://www.npmjs.com/package/@canghe_ai/wechat-cli)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-lightgrey.svg)](https://github.com/AuRevior-ai/wechat-cli)

聊天记录 · 联系人 · 会话 · 收藏 · 统计 · 导出

[English](README.md)

作者：**Au Revior**

</div>

---

## ✨ 功能亮点

- **AI 优先的本地数据访问** — 提供结构化 JSON、文本导出、搜索、统计和 AI 素材包。
- **本机网页控制台** — 包含聊天整理、邀请统计、导出和本地管理界面。
- **Windows 0.5.0 产品线** — 包含 WebView2 Launcher、设备授权、签名更新、健康检查和自动回滚。
- **15 个主命令** — 覆盖初始化、查询、统计、导出、AI 资料包、本地媒体处理和 Web 控制台。
- **本地优先处理** — 微信数据库访问与聊天处理在本机完成；诊断上传只有在用户明确操作后才会发生。
- **只读消息访问** — 工具不会发送、修改或删除微信消息。

---

## 分发渠道与版本线

| 渠道 | 当前仓库版本 | 可用方式 |
|---|---:|---|
| Python/源码与 Windows 产品线 | 0.5.0 | 源码安装；Windows 授权版通过私有发布系统分发 |
| 现有 npm 包装层 | 0.2.4 | 已有 npm 包，目前携带 macOS arm64 平台包 |

两条版本线目前不同步。npm 徽章显示的是 npm 渠道版本，不代表 Windows/Python 主工程版本。

## 📥 安装（给人类看）

AI Agent 请直接移步到“安装（给 Agent 看）”

### 现有 npm 渠道（0.2.4）

```bash
npm install -g @canghe_ai/wechat-cli
```

> 该命令安装现有 npm 0.2.4 版本线，目前携带 macOS arm64 平台包；它不会安装 Windows/Python 0.5.0 产品线。

**更新到最新版本：**

```bash
npm update -g @canghe_ai/wechat-cli
```

### 现有 Python 包渠道

```bash
pip install wechat-cli
```

需要 Python >= 3.10。包索引中已发布的版本可能与当前仓库版本不同。

### 从源码安装

```bash
git clone https://github.com/AuRevior-ai/wechat-cli.git
cd wechat-cli
pip install -e .
```

---

## 📥 安装（给 Agent 看）

直接将在你的 Claude Code 或者 OpenClaw 中输入以下提示即可：

```bash
帮我配置并安装：npm install -g @canghe_ai/wechat-cli
```

比如在 Claude Code 中输入：

![install-claude-code-1](image/install-claude-code-1.png)

注意：请先确保有 node.js 环境。没雨可以让你的 cc 安装环境。

## 🚀 快速开始

### 第一步 — 初始化

确保微信正在运行，然后：

```bash
# macOS/Linux: 可能需要 sudo 权限
sudo wechat-cli init

# Windows: 在有足够权限的终端中运行
wechat-cli init
```

这一步会自动检测微信数据目录、提取加密密钥，并保存到 `~/.wechat-cli/`。

![init-claude-code-1](image/init-claude-code-1.png)

如果是 mac，需要执行 sudo 命令，然后需要输入密码：

![init-claude-code-code-2](image/init-claude-code-2.png)

特别注意，如果你本地有登录微信多个账号，会有多份数据需要你做选择，选择你当前登录的微信账号（默认是第一个）：

![init-claude-code-3](image/init-claude-code-3.png)

这里不确定自己现在的登录微信号，可以找到该文件夹，然后按照修改时间排序，你就可以看到了。（）

![init-claude-code-4](image/init-claude-code-4.png)

#### macOS：提前开启终端的完全磁盘访问权限

在执行 `init` 之前，请确保已为终端开启**完全磁盘访问权限**：

1. 打开 **系统设置 → 隐私与安全性 → 完全磁盘访问权限**
2. 添加你使用的终端应用（如 Terminal、iTerm2 或 IDE 内置终端）
3. 开启后重启终端

未开启此权限会导致工具无法访问微信数据目录，密钥提取将失败。

#### macOS 遇到 `task_for_pid failed` 错误？

在某些 macOS 系统上，即使使用了 `sudo`，`init` 也可能报 `task_for_pid failed`。这是 macOS 的安全策略限制了进程内存访问。

**WeChat CLI 会自动尝试修复此问题**——对微信重新签名以获取必要权限（会保留微信原有权限）。按提示操作即可：

1. 工具会自动对微信重新签名
2. 完全退出微信（不是最小化）
3. 重新打开微信并登录
4. 再次执行 `sudo wechat-cli init`

如果自动签名失败，可以手动执行：

```bash
# 先退出微信，然后：
sudo codesign --force --sign - --entitlements /dev/stdin /Applications/WeChat.app <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.get-task-allow</key>
    <true/>
</dict>
</plist>
EOF
```

> **温馨提示：** 重新签名是安全的，**不会**导致封号或账号异常。但可能影响微信的部分功能或自动更新。如果发现任何功能异常（如搜一搜无法使用），或想更新到微信最新版，直接从[微信官网](https://mac.weixin.qq.com/)重新下载安装即可，**无需重新执行 init**，已有的配置和密钥不受影响。

### 第二步 — 开始使用

```bash
wechat-cli sessions                        # 最近会话
wechat-cli history "张三" --limit 20       # 聊天记录
wechat-cli search "截止日期" --chat "项目组" # 搜索消息
```

---

## 🤖 AI 工具集成

WeChat CLI 专为 AI Agent 设计，所有命令默认输出结构化 JSON。

### Claude Code

在项目的 `CLAUDE.md` 中添加：

```markdown
## WeChat CLI

你可以使用 `wechat-cli` 查询我的本地微信数据。

常用命令：
- `wechat-cli sessions --limit 10` — 列出最近会话
- `wechat-cli history "名称" --limit 20 --format text` — 读取聊天记录
- `wechat-cli search "关键词" --chat "聊天名"` — 搜索消息
- `wechat-cli contacts --query "名称"` — 搜索联系人
- `wechat-cli unread` — 显示未读会话
- `wechat-cli new-messages` — 获取上次以来的新消息
- `wechat-cli members "群名"` — 列出群成员
- `wechat-cli stats "聊天名" --format text` — 聊天统计
- `wechat-cli invite-stats "群名" --format text` — 群邀请统计与拉新排行
- `wechat-cli ai-package "聊天名" --output chat-ai.zip` — 生成可供 AI 使用的文字与媒体资料包
- `wechat-cli media export PATH --output-dir exported-media` — 处理聊天记录返回的本地媒体路径
- `wechat-cli web --open` — 启动本机网页控制台
```

然后在对话中可以直接问 Claude：
- "帮我看看微信有没有未读消息"
- "在项目群里搜索关于截止日期的消息"
- "看看这周 AI 群里谁发言最多？"

### OpenClaw / MCP 集成

WeChat CLI 兼容任何能执行 shell 命令的 AI 工具：

```bash
# 获取最近会话
wechat-cli sessions --limit 5

# 读取指定聊天
wechat-cli history "张三" --limit 30 --format text

# 带过滤条件搜索
wechat-cli search "报告" --type file --limit 10

# 监控新消息（适合定时任务）
wechat-cli new-messages --format text
```

---

## 📖 命令一览

### `sessions` — 最近会话

```bash
wechat-cli sessions                        # 最近 20 个会话
wechat-cli sessions --limit 10             # 最近 10 个
wechat-cli sessions --format text          # 纯文本输出
```

### `history` — 聊天记录

```bash
wechat-cli history "张三"                  # 最近 50 条消息
wechat-cli history "张三" --limit 100 --offset 50
wechat-cli history "交流群" --start-time "2026-04-01" --end-time "2026-04-03"
wechat-cli history "张三" --type link      # 只看链接
wechat-cli history "张三" --format text
```

**选项：** `--limit`、`--offset`、`--start-time`、`--end-time`、`--type`、`--format`

### `ai-package` — AI 聊天资料包

```bash
wechat-cli ai-package "群名" --start-time "2026-07-29" --end-time "2026-07-29" --output group-ai.zip
wechat-cli ai-package "张三" --output contact-ai.zip --no-transcribe-voice
```

ZIP 中包含 `聊天记录.txt`、`清单.json` 和相对路径的 `素材/` 目录。工具会递归展开合并转发，收集本地图片和微信表情，并可将 SILK 语音解码为 WAV；默认使用经过 SHA-256 校验的离线识别组件转写语音。

**选项：** `--start-time`、`--end-time`、`--output`、`--transcribe`、`--no-transcribe-voice`、`--include-copy-data`

### `search` — 搜索消息

```bash
wechat-cli search "Claude"                 # 全局搜索
wechat-cli search "Claude" --chat "交流群"  # 指定聊天搜索
wechat-cli search "开会" --chat "群A" --chat "群B"  # 多个聊天
wechat-cli search "报告" --type file        # 只搜文件
```

**选项：** `--chat`（可多次指定）、`--start-time`、`--end-time`、`--limit`、`--offset`、`--type`、`--format`

### `contacts` — 联系人搜索与详情

```bash
wechat-cli contacts --query "李"           # 搜索联系人
wechat-cli contacts --detail "张三"        # 查看详情
wechat-cli contacts --detail "wxid_xxx"    # 通过 wxid 查看
```

详情包括：昵称、备注、微信号、个性签名、头像 URL、账号类型。

### `members` — 群成员列表

```bash
wechat-cli members "AI交流群"              # 成员列表
wechat-cli members "AI交流群" --format text
```

### `stats` — 聊天统计

```bash
wechat-cli stats "AI交流群"
wechat-cli stats "张三" --start-time "2026-04-01" --end-time "2026-04-03"
wechat-cli stats "AI交流群" --format text
```

返回：消息总数、类型分布、发言 Top 10、24 小时活跃分布。

### `invite-stats` — 群邀请统计

统计“某人邀请某人加入群聊”和“通过扫描某人分享的二维码加入群聊”等系统提示，按唯一被邀请人数从多到少排行：

```powershell
wechat-cli invite-stats "群名"
wechat-cli invite-stats "群名" --format text
wechat-cli invite-stats "群名" --format csv --output invite-stats.csv
wechat-cli invite-stats "群名" --start-time "2026-07-23" --end-time "2026-07-28"
wechat-cli invite-stats "群名" --bind-identity "历史昵称=wxid_xxx"
```

默认统计本工具当前可见的全部数据库历史。相同邀请者、相同被邀请者只计一个唯一拉新人，但每次邀请事件都保留在明细中；自己扫码等没有邀请来源的提示保留为“来源不明”，不计入排行。

身份只使用当前群成员资料做精确匹配；相似昵称不会自动合并。无法唯一确认的历史昵称会标记为“身份待确认”，可用可重复的 `--bind-identity` 参数手工绑定稳定账号。Web 端在侧边栏“群聊成员邀请统计”页面提供相同的摘要、排行、关系明细和 CSV 下载，并明确提示统计范围从微信数据库记载的日子开始。

### Web `聊天记录` — 选择、整理与复制

Web 端把记录读取和 AI 材料整理合并在“聊天记录”页面：

1. 输入群名、联系人名称或账号，在自动载入的最近会话下拉列表中搜索并选择。
2. 使用日历选择开始日期和结束日期；日期按整天计算。
3. 点击“读取聊天记录”，网页会从本机读取该范围内的聊天内容。
4. “复制”会得到包含总结任务和完整记录的 AI 输入文本；“复制精简信息”只保留会话范围、时间、发言人、消息类型和正文。

为避免超大群聊拖慢页面，网页最多预览前 200 条，但两种复制都会包含已读取的全部记录；单次最多读取 50,000 条。聊天记录页不会加载远程头像或远程媒体。该功能只整理本机数据，不调用外部 AI，也不会主动上传聊天记录。把复制结果粘贴给哪个 AI，由用户自行决定。Web 各功能的结果彼此隔离：切换到其他功能不会继续显示上一项功能的结果，切回时会恢复该功能上一次的结果。

### `export` — 导出聊天记录

```bash
wechat-cli export "张三" --format markdown              # 输出到 stdout
wechat-cli export "张三" --format txt --output chat.txt  # 输出到文件
wechat-cli export "群聊" --start-time "2026-04-01" --limit 1000
```

**选项：** `--format markdown|txt`、`--output`、`--start-time`、`--end-time`、`--limit`

### `favorites` — 微信收藏

```bash
wechat-cli favorites                       # 最近收藏
wechat-cli favorites --type article        # 只看文章
wechat-cli favorites --query "计算机网络"    # 搜索收藏
```

**类型：** text、image、article、card、video

### `unread` — 未读会话

```bash
wechat-cli unread                          # 所有未读会话
wechat-cli unread --limit 10 --format text
```

### `new-messages` — 增量新消息

```bash
wechat-cli new-messages                    # 首次: 返回未读消息 + 保存状态
wechat-cli new-messages                    # 后续: 仅返回上次以来的新消息
```

状态保存在 `~/.wechat-cli/last_check.json`，删除此文件可重置。

### `media` — 处理本地媒体

用于处理 `history --media` 返回的本地媒体路径；图片 `.dat` 文件会在可能时解码为可查看格式。

```bash
wechat-cli media export PATH
wechat-cli media export PATH --output-dir exported-media --format text
```

**选项：** `--output-dir`、`--format json|text`

### `web` — 启动本机网页控制台

```bash
wechat-cli web
wechat-cli web --port 8787 --open
```

界面绑定在本机。**选项：** `--port`、`--open`

---

## 🔍 消息类型过滤

`--type` 选项（适用于 `history` 和 `search`）：

| 值 | 说明 |
|---|------|
| `text` | 文本消息 |
| `image` | 图片 |
| `voice` | 语音 |
| `video` | 视频 |
| `sticker` | 表情 |
| `location` | 位置 |
| `link` | 链接/应用消息 |
| `file` | 文件 |
| `call` | 音视频通话 |
| `system` | 系统消息 |

---

## 💻 系统要求

- 源码安装需要 Python >= 3.10。
- 初始化和密钥提取需要本机已安装并运行微信客户端。
- 进程内存访问需要对应平台的权限。

当前记录的 macOS 兼容基线为 macOS 26.3.1 或更高版本、微信 Mac 版不高于 4.1.8.100；其他客户端版本可能需要额外兼容工作。

---

## 🖥️ 平台支持

| 平台 | 源码能力 | 当前打包渠道 |
|---|---|---|
| Windows x86-64 | 支持；读取 `Weixin.exe` 进程内存 | 0.5.0 Windows 产品与私有更新流程 |
| macOS Apple Silicon | 支持 | 现有 npm 0.2.4 arm64 平台包 |
| macOS Intel | 源码支持需要 x86-64 二进制 | 当前仓库未记录可用的 npm 捆绑平台包 |
| Linux | 通过 `/proc/<pid>/mem` 支持，通常需要 root | 源码安装 |

---

## 🔧 工作原理

微信将聊天数据存储在本地的 SQLCipher 加密 SQLite 数据库中。WeChat CLI：

1. **提取密钥** — 扫描微信进程内存获取加密密钥（`init`）
2. **即时解密** — 透明页级 AES-256-CBC 解密，带缓存
3. **本地查询与处理** — 核心聊天访问在本机完成；0.5.0 产品线会连接配置的授权与更新服务，诊断上传需要用户明确操作

---

## 📄 开源协议

[Apache License 2.0](LICENSE)

源码许可证不代表所有打包版本或私有更新资产都可以公开下载。Windows 授权分发及其私有发布服务属于独立交付渠道。

---

## ⚖️ 免责声明

本项目为个人使用的本地数据查询工具，请注意：

- **只读不写** — 本工具仅读取本地存储的数据，不会发送、修改或删除任何消息
- **本地优先** — 核心聊天查询和资料处理在本机完成。0.5.0 产品线会连接配置的授权与更新服务；诊断上传只有在用户明确操作后才会发生
- **不破坏微信生态** — 本工具不会干扰微信正常运行，不会自动化任何操作，不违反微信使用协议
- **风险自担** — 本项目仅供个人学习研究使用，使用者需确保遵守当地法律法规

---

## 开发记录

- [当前项目状态](docs/PROJECT_STATE.md)
- [版本变更记录](CHANGELOG.md)
- [授权更新路线图](docs/deployment/authorized-update-roadmap.md)
- [已批准设计](docs/superpowers/specs/)
- [实施计划](docs/superpowers/plans/)——历史计划不是当前进度看板

---

## 🙏 致谢

本项目基于 [wechat-decrypt](https://github.com/ylytdeng/wechat-decrypt) 开发，该仓库提供了微信数据库解密和数据解析的核心能力。

---

## ⭐ Star History

[![Star History Chart](https://api.star-history.com/svg?repos=AuRevior-ai/wechat-cli&type=Date)](https://star-history.com/#AuRevior-ai/wechat-cli&Date)
