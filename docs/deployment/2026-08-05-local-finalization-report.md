# WeChat CLI Web 0.5.0 本地最终收尾报告

> **Historical snapshot:** This report records the local-finalization state on 2026-08-05. For the current repository state, read [`docs/PROJECT_STATE.md`](../PROJECT_STATE.md); for the later licensing and update program state, read [`authorized-update-roadmap.md`](authorized-update-roadmap.md).

日期：2026-08-05
阶段：板块 1——本地最终收尾
结论：**已完成，可进入板块 2：建立两个私有 GitHub 仓库**

## 1. 阶段目标

本阶段负责在不连接真实 Cloudflare、GitHub 或生产域名的前提下，完成自动更新与授权系统的本地实现、测试、构建、安装迁移、安全检查和 Windows GUI 烟雾验收。

本阶段不包含：

- 创建或配置真实 GitHub 私有仓库；
- 创建 Cloudflare Worker、D1 或 R2 生产/测试资源；
- 写入真实 GitHub Token、Cloudflare Token、管理员 Token 或发布私钥；
- Windows 正式代码签名；
- 真实公网环境下的端到端更新发布。

## 2. 已完成范围

### 2.1 许可证与设备授权

- 永久许可证激活；
- 每张许可证最多三台设备；
- 随机设备 ID；
- 基于 Windows MachineGuid 和当前用户 SID 的不可逆设备指纹；
- 设备令牌日常验证；
- 七天签名离线租约；
- 在线暂停、吊销、解绑和设备停用；
- 系统时间回拨检测；
- Windows 当前用户 DPAPI 本地加密存储；
- Launcher 与应用的二次授权；
- 一次性、短时、版本绑定的启动会话。

### 2.2 更新与回滚

- Ed25519 签名更新清单；
- SHA-256 更新包完整性验证；
- 防目录穿越和防覆盖的 ZIP 安全解压；
- 可恢复的断点下载；
- 下载票据只放在请求头中，不进入 URL；
- 版本目录和原子 `current.json` 切换；
- 更新事务、启动健康检查、失败隔离和自动回滚；
- 当前版本与上一版本保留；
- 失败版本和清单摘要组合抑制重复安装。

### 2.3 Windows Launcher 与 WebView2

- 独立 Windows Launcher；
- 本地 WebView2 激活和错误窗口；
- 本地静态资源与严格 CSP；
- 禁止任意远程页面导航；
- 原生桥接白名单；
- WebView2 Runtime 注册表检测；
- 缺失时使用微软官方 Evergreen Bootstrapper；
- Launcher 单实例互斥；
- 应用进程启动、停止和健康检查。

### 2.4 Web 管理界面

- “许可证与更新”页面；
- 授权状态和离线剩余时间；
- 当前版本、启动器版本、发布通道和待安装版本；
- 设备列表、设备重命名和非当前设备解绑；
- 更新下载与待安装状态；
- 本地诊断包生成入口；
- 诊断提交保留明确同意步骤。

### 2.5 管理、发布与 Worker

- Cloudflare Worker TypeScript 工程；
- D1 数据库迁移；
- R2 诊断存储接口；
- 许可证、设备、更新、下载票据、管理员、发布和诊断 API；
- AES-256-GCM 联系人加密和版本化密钥轮换；
- 管理员 CLI；
- 本地 Demo 初始化工具；
- Ed25519 发布清单构建器；
- 私有 GitHub Release 客户端；
- 发布注册、启用、暂停和失败恢复逻辑；
- 幂等、速率限制、审计和定时清理。

### 2.6 Windows 安装与迁移

- Launcher 与版本目录安装结构；
- 从旧版 0.4.2 安装布局迁移；
- 原子安装事务记录；
- 重复安装；
- 修复入口；
- 卸载入口；
- 默认保留用户微信数据；
- Bootstrap ZIP 和独立更新 ZIP。

## 3. 最终验证结果

### 3.1 Python

- 共收集并运行：**465 项**；
- 通过：**463 项**；
- 平台条件跳过：**2 项**；
- Python 源码编译检查通过；
- Python Wheel 构建通过；
- Wheel 中包含 Launcher UI、Web UI、授权、更新、管理员和发布模块。

### 3.2 Cloudflare Worker

在隔离临时环境中完成：

- TypeScript 类型检查通过；
- Vitest：**17 项通过**；
- 三轮 D1 迁移通过；
- Wrangler dry-run 打包通过；
- 本地端到端 API 验收通过，包括：
  - 许可证创建；
  - 三设备上限；
  - 离线租约；
  - 暂停和吊销；
  - 更新检查和短期下载票据；
  - 失败版本抑制；
  - 诊断上传与删除；
  - 日志敏感字段检查。

### 3.3 Windows 构建产物

构建版本：`0.5.0`
本地构建号：`0.5.0-local-20260805.1`

已实际生成并验证：

- `wechat-cli.exe`；
- `wechat-cli-launcher.exe`；
- `wechat-cli-web-bootstrap-win32-x64-0.5.0.zip`；
- `wechat-cli-app-0.5.0-win-x64.zip`。

Launcher 归档确认包含：

- `pywebview`；
- EdgeChromium 后端；
- x64 `WebView2Loader.dll`。

构建脚本已增加依赖预检：缺少 `pywebview` 或其他必要构建依赖时，会在覆盖任何 EXE 前直接失败，不再生成半成品。

### 3.4 安装和 GUI 烟雾测试

- 0.4.2 迁移测试通过；
- 重复安装测试通过；
- 安装事务清理通过；
- 卸载测试通过；
- 更新清单签名验证通过；
- 更新包 SHA-256 验证通过；
- 安全解压通过；
- 打包应用启动及健康检查通过；
- 打包 Launcher 修复模式通过；
- 打包后的真实 WebView2 激活窗口测试通过：
  - 在隔离 `LOCALAPPDATA` 下完成 Bootstrap 安装；
  - 成功创建可见窗口 `WeChat CLI Launcher`；
  - 测试后 Launcher 进程及临时目录已清理。

### 3.5 产物摘要

- Bootstrap ZIP：`269a21b13448945f9ecc3ec5177c3d8ea8f223ca25501a8a1c969881e6adb070`
- Update ZIP：`4253a61a316061ca127468dbd6f15decd467790693ab5b20b0e84f61cca50f7f`
- `wechat-cli.exe`：`4dbf9a25029c336b9e4149d9c82b9ae15b067ae8d5dde7c10f208fbe4bbe8684`
- `wechat-cli-launcher.exe`：`2e74504d5388284d0884220f6d007b76c5b009426959dce76195501d3aa833f3`

这些摘要仅对应本地 Demo 构建。后续重新构建、替换配置或正式签名后摘要会改变。

## 4. 安全检查

最终构建产物和源码范围已扫描，未发现真实：

- 发布私钥；
- GitHub Token；
- Cloudflare Token；
- 管理员 Token；
- 设备令牌；
- 永久许可证；
- 联系人明文数据库；
- MachineGuid 或 SID 原始值。

当前本地构建继续使用 `.invalid` API 占位域名和 Demo 公钥配置，不会误连真实服务。

## 5. 非阻塞事项与后续风险

### 5.1 根目录意外文件 `NUL`

根目录仍存在一个 152 字节的未跟踪文件 `NUL`，内容仅为 Git 换行警告。它不影响构建或测试，但会干扰部分 Windows 命令行工具，应在能够可靠执行 Windows 特殊文件名删除的环境中清除，并确认 Git 状态不再显示它。

**后续状态：** 当前工作树已不再显示该 `NUL` 文件；本段保留为报告日期当时的历史记录。

### 5.2 未签名 EXE

`wechat-cli.exe` 和 `wechat-cli-launcher.exe` 当前均为 `NotSigned`。这是 Demo 阶段的预期状态；正式发布前必须完成 Windows 代码签名。

### 5.3 云端尚未验收

本阶段只完成本地 Worker 和模拟私有发布验收。真实 Cloudflare staging、私有 GitHub Release、跨网络下载和真实更新回滚将在后续阶段执行。

**后续状态：** 后续路线图记录板块 2 和板块 3 已完成，并记录了 0.5.0 私有 Draft Release 和 staging Worker 发布登记。该结论属于后续人工验收记录，不改变本报告在 2026-08-05 本地收尾时点的范围。

### 5.4 未提交工作树

自动更新功能目前仍位于工作区未提交修改中。原有以下用户修改保持独立，没有回退或覆盖：

- `wechat_cli/core/invite_stats.py`
- `tests/test_invite_stats.py`

后续整理 Git 提交时必须继续将它们与自动更新变更分开处理。

**后续状态：** 自动更新实现和邀请统计修复后来已拆分提交；当前状态以项目状态页和 Git 历史为准。

## 6. 阶段结论

板块 1 的功能实现和本地验收已达到进入下一阶段的条件。

下一阶段应建立两个私有 GitHub 仓库，并准备最小权限凭据：

1. 私有源码仓库；
2. 独立私有发布仓库；
3. Worker 只读发布仓库凭据；
4. 本地发布 CLI 写入发布仓库的凭据。

在真实仓库和凭据准备完成前，不应部署 Cloudflare staging，也不应把本地 Demo 私钥或占位配置直接用于生产。
