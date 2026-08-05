# WeChat CLI 自动更新、许可证与发布系统设计

- 状态：已批准，进入实施
- 设计日期：2026-08-04
- 目标版本：WeChat CLI Web 0.5.0、Launcher 0.1.0
- 更新协议：schema_version 1
- API 版本：v1
- 首发平台：Windows x86-64
- 首发通道：stable

## 1. 背景与目标

当前 WeChat CLI Web 以 Windows 解压包形式分发，程序默认安装到 `%LOCALAPPDATA%\WeChatCliWeb`，桌面快捷方式直接启动应用。后续版本需要具备接近正式桌面产品的许可证、自动更新、回滚和发布能力，同时保留现有微信数据与业务功能。

本设计的首要目标是建立一个真实可运行的 Demo 闭环：

```text
管理员生成许可证
→ 用户最后手动安装一次带 Launcher 的迁移安装包
→ 首次激活并绑定设备
→ 正常启动 WeChat CLI Web
→ 发布新的私有 GitHub Release
→ 客户端启动时发现更新并在后台下载
→ 下次启动安装新版本
→ 健康检查成功后提交版本
→ 健康检查失败时自动回滚
```

Demo 面向中国大陆用户，但当前域名尚未备案、尚无自有服务器。首版采用 Cloudflare Worker、D1、R2 和私有 GitHub Releases 快速验证完整体系；正式公开分发和中国大陆生产部署另行规划。

## 2. 已确认的产品决策

### 2.1 许可证

- 许可证为永久密钥，每张最多绑定 3 台有效设备。
- 用户可以在 WeChat CLI Web 的“许可证与更新”页面查看和解绑设备。
- 查看和解绑其他设备必须由一台已经在线验证的设备发起，并携带当前设备令牌；仅凭永久许可证密钥不能管理设备。
- 首次激活提交永久许可证密钥，成功后获得设备令牌；日常启动只使用设备令牌验证。
- 许可证密钥首次输入一次，并通过 Windows DPAPI 加密保存在当前 Windows 用户范围内。
- 在线验证成功后允许离线使用 7 天；超过 7 天必须重新联网验证。
- 服务端明确返回吊销、停用、解绑或令牌无效时，不能回退到旧离线租约，立即锁定业务功能。
- 完全离线的设备无法即时获知远程解绑或吊销，最多可继续使用当前租约剩余时间，但不会超过 7 天。
- 设备解绑后立即释放槽位，不设置冷却期或次数限制。

### 2.2 设备识别

- 主设备标识是 Launcher 首次安装时生成的高熵随机设备 ID。
- 辅助设备指纹只使用 Windows `MachineGuid` 和当前用户 SID。
- 原始值永不上传；客户端只上传带协议前缀和盐版本计算出的不可逆摘要。
- 辅助指纹只用于识别“可能是同一电脑、同一 Windows 用户的重新安装”，不是唯一认证凭证。
- 不采集主板 UUID、磁盘序列号等硬件序列信息。

### 2.3 更新体验

- 每次启动只自动检查一次更新。
- 发现更新后自动后台下载，不中断当前会话。
- 下载、签名、哈希和解压检查全部完成后，提示“更新已就绪”。
- 用户本次会话无需退出；下次启动时 Launcher 优先安装待更新版本。
- 新版本通过 `/api/health` 后提交版本切换；失败则自动回滚。
- 本地只保留当前版本和上一个版本。
- 协议预留 stable/beta 通道，Demo 只启用 stable。
- 协议预留灰度、暂停推送和分批比例，Demo 固定向 100% 符合条件的 stable 设备发布。
- 协议预留强制更新字段，Demo 不启用强制更新。
- 协议预留 Launcher 最低版本和自更新字段，Demo 只更新应用，不实际自更新 Launcher。

### 2.4 发布与运维

- 源码和发布资产分别存放在两个私有 GitHub 仓库。
- 私有 GitHub Releases 存放应用 ZIP、更新清单和清单签名。
- Cloudflare Worker 负责许可证 API、设备 API、更新检查和私有 Release 下载代理。
- D1 保存许可证、设备、发布和审计元数据。
- 私有 R2 仅保存用户主动提交的脱敏诊断包。
- Demo 由本地发布命令构建、签名、上传和登记；后续迁移到 GitHub Actions。
- 更新清单签名私钥 Demo 阶段只保存在管理员本机；迁移 CI 后改存 GitHub Actions Secret。
- Demo 可使用未签名 Windows 可执行文件；正式公开分发前安装器和可执行文件必须代码签名。

### 2.5 管理与隐私

- Demo 使用管理员 CLI，不建设 Web 管理后台。
- 管理员 CLI 使用长期管理员 API Token；正式版升级为管理员登录和短期令牌。
- CLI 支持单个生成许可证和批量生成、导出 CSV。
- 许可证可关联可选邮箱、微信号、其他联系方式和备注。
- 联系方式在 D1 中使用 AES-256-GCM 加密，密钥保存在 Worker Secret，并支持密钥版本轮换。
- 默认不上传日志或遥测。
- 用户遇到问题时，可主动生成诊断包；默认只保存本机，只有再次确认后才上传。

## 3. 非目标

Demo 不实现：

- macOS、Linux 或 ARM 平台；
- Windows 后台服务；
- 完整商业 DRM、强反调试或强反破解；
- 支付、自动续费、用户自助购买；
- 企业集中部署和远程控制；
- Launcher 自我替换；
- beta 实际发布、灰度实际放量、强制更新实际阻断；
- 多管理员身份体系；
- 自动遥测；
- 微信聊天数据云端上传；
- 中国大陆生产域名备案和正式生产迁移。

## 4. 总体架构

```text
用户点击桌面快捷方式
          │
          ▼
┌──────────────────────────────┐
│ Launcher                     │
│ - DPAPI 本地状态             │
│ - 许可证验证与离线租约       │
│ - 更新检查、下载和安装       │
│ - 版本切换、健康检查和回滚   │
│ - WebView2 激活与错误界面    │
└──────────────┬───────────────┘
               │ 一次性启动会话
               ▼
┌──────────────────────────────┐
│ WeChat CLI Web               │
│ - 现有微信业务               │
│ - 二次验证启动会话           │
│ - /api/health                │
│ - 许可证与更新页面           │
│ - 设备管理和诊断生成         │
└──────────────┬───────────────┘
               │ HTTPS
               ▼
┌──────────────────────────────┐
│ Cloudflare Worker            │
│ - 激活、验证和设备管理       │
│ - 离线租约签发               │
│ - 更新检查与下载票据         │
│ - 私有 GitHub Asset 代理     │
│ - 管理员 API                 │
│ - 诊断上传与下载鉴权         │
└───────┬──────────┬───────────┘
        │          │
        ▼          ▼
 Cloudflare D1   私有 R2
 许可证/设备     诊断包
        │
        ▼
私有 GitHub Release 仓库
应用 ZIP / manifest / signature
```

### 4.1 信任边界

- 应用更新清单由发布私钥签名，客户端只内置更新公钥。
- 离线许可证租约由 Worker 中另一套独立私钥签名，客户端内置租约公钥。
- 更新签名密钥与租约签名密钥必须隔离。
- Worker 只持有私有 Release 只读凭证，不能创建或覆盖 Release。
- 本地发布工具持有仅限发布仓库的写入凭证。
- 客户端永不接触 GitHub Token、管理员 Token 或 Worker Secret。
- Worker、D1、GitHub、HTTPS 均不是更新程序的最终信任根；客户端仍须验证签名和 ZIP 哈希。
- 微信聊天数据、数据库密钥和原始设备标识不发送到许可证服务。

## 5. Windows 本地结构与进程关系

### 5.1 目录结构

```text
%LOCALAPPDATA%\WeChatCliWeb\
├─ launcher\
│  ├─ wechat-cli-launcher.exe
│  ├─ launcher-config.json
│  └─ webui\
├─ versions\
│  ├─ 0.4.2\
│  │  └─ wechat-cli.exe
│  └─ 0.5.0\
│     └─ wechat-cli.exe
├─ state\
│  ├─ current.json
│  ├─ pending-update.json
│  ├─ update-status.json
│  ├─ failed-versions.json
│  ├─ license-state.dat
│  └─ device-identity.dat
├─ runtime\
│  ├─ launch-session.json
│  └─ locks\
├─ cache\
│  ├─ downloads\
│  └─ staging\
└─ logs\
   ├─ launcher.log
   ├─ updater.log
   └─ rollback.log
```

微信相关用户数据继续保存在现有用户数据目录，例如 `%USERPROFILE%\.wechat-cli\`。更新、回滚、修复和版本清理不得修改该目录。

### 5.2 版本指针

桌面和开始菜单快捷方式始终指向：

```text
launcher\wechat-cli-launcher.exe
```

`state\current.json` 指定当前和上一版本：

```json
{
  "current_version": "0.5.0",
  "previous_version": "0.4.2",
  "channel": "stable",
  "activated_at": "2026-08-04T14:30:00Z",
  "manifest_sha256": "..."
}
```

修改状态文件时先写临时文件，完成内容校验后在同一磁盘卷内原子替换，避免断电形成半写入状态。不依赖 Windows 符号链接。

### 5.3 Launcher 模式

Demo 可由一个 Launcher 可执行文件承载不同模式：

```text
wechat-cli-launcher.exe
wechat-cli-launcher.exe --activate
wechat-cli-launcher.exe --download-update
wechat-cli-launcher.exe --apply-update
wechat-cli-launcher.exe --repair
```

Launcher 和 WeChat CLI Web 均设置当前 Windows 用户范围内的单实例锁。重复点击快捷方式时，Launcher 检测现有服务健康状态；健康则直接打开网页，不启动第二个 Web 服务。

### 5.4 启动顺序

```text
1. 获取 Launcher 单实例锁
2. 检查目录与 current.json 完整性
3. 恢复或处理未完成的更新事务
4. 存在 pending-update 时优先尝试安装
5. 读取 DPAPI 加密许可证状态
6. 使用设备令牌尝试在线验证
7. 网络不可达时检查 7 天离线租约
8. 授权失败时打开 WebView2 许可证窗口
9. 授权成功时生成一次性启动会话
10. 启动 current_version 对应应用
11. 调用 /api/health
12. 健康检查通过后确认本次启动或更新
13. 检查 stable 更新
14. 有新版本时启动独立后台下载进程
15. 打开浏览器进入 WeChat CLI Web
```

### 5.5 一次性启动会话

Launcher 每次启动应用前生成短期会话，防止普通用户直接执行 `versions\<version>\wechat-cli.exe` 绕过入口。

会话至少包含：

```json
{
  "session_id": "随机值",
  "app_version": "0.5.0",
  "device_id": "脱敏标识",
  "lease_hash": "...",
  "issued_at": "...",
  "expires_at": "...",
  "nonce": "...",
  "signature": "..."
}
```

约束：

- 有效期约 2 分钟；
- 绑定目标应用版本与随机 nonce；
- 只能使用一次；
- 由 DPAPI 保护的 Launcher 本地密钥签名；
- 应用验证后立即消费并删除；
- 无效或过期时只开放受限许可证页面。

该机制是防止普通入口绕过，不宣称能抵抗管理员权限下的二进制补丁或反编译。

## 6. 许可证、设备与离线租约

### 6.1 凭证分层

```text
永久许可证密钥
→ 首次激活或恢复激活

设备令牌
→ 每次启动的在线验证、设备管理、更新检查

离线授权租约
→ 网络不可达时最多继续使用 7 天

一次性启动会话
→ Launcher 启动本地应用
```

永久许可证密钥和设备令牌都不得以明文保存在服务端数据库。

### 6.2 激活流程

```text
用户输入永久许可证密钥
→ Launcher 生成或读取随机设备 ID
→ 计算 MachineGuid + SID 辅助摘要
→ POST /v1/licenses/activate
→ Worker 验证许可证状态与设备数量
→ 创建、恢复或拒绝设备记录
→ 返回设备令牌和签名离线租约
→ DPAPI 原子保存本地状态
```

激活请求可以携带设备显示名称、应用版本和 Launcher 版本。设备名称只作为管理标签，不参与认证。

### 6.3 三设备限制

- 相同随机设备 ID 再次激活：恢复原设备，不增加槽位。
- 设备 ID 不同但辅助指纹完全匹配：标记为疑似同一设备重新安装。
- 自动恢复必须同时具备正确永久许可证、原设备未封禁、指纹无冲突等条件。
- 达到 3 台上限时拒绝新增设备，并展示脱敏设备列表。
- 激活数量判断和设备插入必须采用原子数据库操作，不能被并发请求突破。

### 6.4 在线验证与错误分类

Launcher 每次启动调用 `/v1/devices/validate`。

明确服务器拒绝包括：

- 许可证吊销或暂停；
- 设备解绑或停用；
- 设备令牌无效；
- 服务端签名的版本阻断状态。

以上状态立即锁定，不能使用旧租约。

无法确认服务器状态包括：

- 无网络；
- DNS 或连接超时；
- TLS 建连失败；
- Cloudflare 服务暂时不可用。

只有后一类错误允许检查尚未过期的本地租约。HTTP 401、403 或有效签名的业务拒绝不能伪装成断网。

### 6.5 离线租约

在线验证成功后，Worker 签发 Ed25519 租约：

```json
{
  "schema_version": 1,
  "license_id": "lic_...",
  "device_id": "dev_...",
  "license_revision": 4,
  "device_revision": 2,
  "issued_at": "2026-08-04T15:00:00Z",
  "offline_until": "2026-08-11T15:00:00Z",
  "nonce": "...",
  "key_id": "lease-key-2026-01"
}
```

客户端验证签名、设备绑定、租约版本和有效期。系统时间明显早于最近可信服务器时间时，要求联网验证；运行中优先参考单调时钟。该措施只防止简单回拨，不等同于强 DRM。

### 6.6 本地 DPAPI 状态

`license-state.dat` 至少保护：

- 永久许可证密钥；
- 设备令牌；
- 随机设备 ID；
- 当前离线租约；
- Launcher 本地签名密钥；
- 最近可信时间检查点。

使用当前 Windows 用户作用域，不使用整机作用域。DPAPI 解密失败时进入恢复激活流程。

### 6.7 用户设备管理

当前设备在线验证后才能获取设备列表和解绑其他设备。解绑请求包含当前设备令牌、目标设备 ID 和一次性 nonce。

- 当前设备不能通过同一接口解绑自己；
- 解绑立即释放槽位；
- 被解绑设备下次在线验证立即失效；
- 完全离线设备最多继续使用当前租约剩余时间；
- 不设置解绑次数或冷却时间。

## 7. 更新清单、签名与下载

### 7.1 发布资产

每个版本包含：

```text
wechat-cli-app-0.5.0-win-x64.zip
manifest-0.5.0.json
manifest-0.5.0.sig
```

签名针对 `manifest.json` 原始 UTF-8 字节生成，客户端验证下载到的原始字节，不重新序列化 JSON。

### 7.2 更新清单

```json
{
  "schema_version": 1,
  "product": "wechat-cli-web",
  "release_id": "rel_...",
  "version": "0.5.0",
  "channel": "stable",
  "published_at": "2026-08-04T15:00:00Z",
  "platform": "windows",
  "architecture": "x86_64",
  "package": {
    "filename": "wechat-cli-app-0.5.0-win-x64.zip",
    "size": 84213760,
    "sha256": "...",
    "format": "zip"
  },
  "compatibility": {
    "minimum_app_version": "0.4.2",
    "minimum_launcher_version": "0.1.0",
    "maximum_launcher_version": null
  },
  "install": {
    "entrypoint": "wechat-cli.exe",
    "health_endpoint": "/api/health",
    "health_timeout_seconds": 30
  },
  "rollout": {
    "enabled": true,
    "percentage": 100,
    "seed": "stable-0.5.0",
    "paused": false
  },
  "update_policy": {
    "forced": false,
    "force_after": null,
    "minimum_allowed_version": null
  },
  "launcher_update": null,
  "release_notes": {
    "summary": "...",
    "url": null
  },
  "signing": {
    "algorithm": "Ed25519",
    "key_id": "release-key-2026-01"
  }
}
```

Demo 固定：`channel=stable`、`percentage=100`、`forced=false`、`launcher_update=null`。

### 7.3 安装信任条件

客户端只有同时满足以下条件才准备安装：

1. Ed25519 清单签名有效；
2. 产品、平台、架构匹配；
3. 版本和兼容性规则通过；
4. ZIP 文件大小和 SHA-256 匹配；
5. ZIP 内 `app-manifest.json` 与外部清单一致；
6. ZIP 路径安全检查通过；
7. 该版本和清单摘要未被标记为失败；
8. 切换后的 `/api/health` 返回匹配版本。

### 7.4 更新检查

```http
POST /v1/updates/check
Authorization: Bearer <device-token>
```

请求包含当前应用版本、Launcher 版本、stable 通道、平台、架构和失败版本摘要。Worker 在返回更新前先验证许可证、设备、发布状态、通道和兼容性。

有更新时返回原始清单字节、签名和短期下载票据。客户端仍须自行验签。

### 7.5 灰度预留

正式版可基于：

```text
SHA-256(rollout.seed + license_id + device_id) mod 100
```

稳定分桶。Demo 固定 100%，只保留协议和数据字段。

### 7.6 下载票据与代理

下载票据是短期高熵凭证，绑定 release、license、device、文件哈希、文件大小和失效时间。

票据放在请求头而不是 URL：

```http
GET /v1/updates/download
Authorization: Download <short-lived-ticket>
```

Worker 只按已登记的 GitHub Asset ID 读取私有资产，不接受客户端提供任意仓库路径或资产 ID。票据在有效期内允许断点续传。

### 7.7 下载与安全解压

```text
下载到 cache\downloads\<version>.zip.part
→ 支持续传并校验远端标识
→ 完成后重命名为 .zip
→ 验证清单签名
→ 验证文件大小和 SHA-256
→ 检查 ZIP 成员
→ 解压到随机 staging 目录
→ 验证 app-manifest.json 和入口文件
→ 同卷原子移动到 versions\<version>
→ 写入 pending-update.json
```

禁止：

- `../` 路径穿越；
- 绝对路径、盘符路径和 UNC 路径；
- 指向目标目录外的链接；
- 异常单文件大小、总解压体积和压缩比；
- 直接解压到正式版本目录。

## 8. 更新事务、健康检查与回滚

### 8.1 待安装状态

准备完成后写入 `state\pending-update.json`。当前会话继续使用旧版本，页面显示“已下载，将在下次启动安装”。

### 8.2 事务状态

```text
prepared
→ switching
→ starting
→ health_checking
→ committed
```

失败路径：

```text
health_checking
→ rolling_back
→ rolled_back
```

只有健康检查成功后才删除 pending 状态并提交版本。

### 8.3 健康检查

Launcher 轮询：

```http
GET http://127.0.0.1:8787/api/health
```

预期响应至少包含：

```json
{
  "status": "ok",
  "product": "wechat-cli-web",
  "version": "0.5.0",
  "build_id": "20260804.1",
  "config_loaded": true,
  "license_session_valid": true,
  "core_modules": {
    "server": "ok",
    "storage": "ok",
    "routes": "ok"
  }
}
```

Demo 不要求微信已登录、微信数据库当前可读、账号已选择或聊天扫描完成，避免业务环境导致错误回滚。

### 8.4 自动回滚

健康检查失败时：

```text
停止新版本
→ 原子恢复 current.json
→ 启动 previous_version
→ 验证旧版健康状态
→ 标记新版本为 failed
→ 保留回滚日志和错误编号
```

相同 `version + manifest_sha256` 失败后不自动反复安装。只有用户主动重试、清单摘要变化或发布更高版本时才重新尝试。

### 8.5 断电恢复

Launcher 根据事务日志判断：

- 尚未切换：继续旧版；
- 已切换但未确认：恢复旧版；
- 已提交：继续新版；
- 状态损坏：根据最近成功记录进入修复模式。

正常更新只允许升级。降级只允许自动回滚到 Launcher 已记录的上一版本。

## 9. Worker API 与 D1 模型

### 9.1 API 分区

公共健康接口：

```http
GET /health
```

许可证和设备：

```http
POST  /v1/licenses/activate
POST  /v1/devices/validate
GET   /v1/devices
PATCH /v1/devices/{device_id}
POST  /v1/devices/{device_id}/unbind
```

更新：

```http
POST /v1/updates/check
POST /v1/updates/download-ticket
GET  /v1/updates/download
```

诊断：

```http
POST /v1/diagnostics/submissions
PUT  /v1/diagnostics/submissions/{submission_id}/content
POST /v1/diagnostics/submissions/{submission_id}/complete
```

管理员：

```http
POST  /v1/admin/licenses
POST  /v1/admin/licenses/batch
GET   /v1/admin/licenses
GET   /v1/admin/licenses/{license_id}
PATCH /v1/admin/licenses/{license_id}
GET   /v1/admin/licenses/{license_id}/devices
PATCH /v1/admin/devices/{device_id}
POST  /v1/admin/releases
PATCH /v1/admin/releases/{release_id}
GET   /v1/admin/diagnostics
GET   /v1/admin/diagnostics/{submission_id}
DELETE /v1/admin/diagnostics/{submission_id}
```

改变状态的请求携带 `Idempotency-Key`，超时重试不能重复创建设备、许可证或发布记录。

### 9.2 统一错误

```json
{
  "error": {
    "code": "DEVICE_LIMIT_REACHED",
    "message": "该许可证已绑定三台设备",
    "retryable": false,
    "request_id": "req_...",
    "details": {
      "maximum_devices": 3
    }
  }
}
```

客户端只按稳定错误码处理逻辑，不匹配中文错误文本。

### 9.3 Secret

Worker Secret 至少包含：

```text
LICENSE_KEY_PEPPER
DEVICE_TOKEN_PEPPER
ADMIN_TOKEN_PEPPER
CONTACT_LOOKUP_PEPPER
CONTACT_ENCRYPTION_KEY_V1
LEASE_SIGNING_PRIVATE_KEY
DOWNLOAD_TICKET_SECRET
GITHUB_RELEASE_READ_TOKEN
```

普通变量和源码仓库不得包含这些值。

### 9.4 核心表

#### licenses

```text
id, key_digest, key_hint, status, max_devices,
release_channel, revision, created_at, updated_at,
suspended_at, revoked_at, created_by_admin_id
```

#### license_contacts

```text
license_id, ciphertext, iv, encryption_key_version,
email_lookup_digest, wechat_lookup_digest,
other_lookup_digest, updated_at
```

#### devices

```text
id, license_id, client_install_id_digest, fingerprint_digest,
display_name, status, token_id, token_secret_digest,
token_version, device_revision, first_activated_at,
last_validated_at, last_app_version, last_launcher_version,
disabled_at, unbound_at
```

#### releases

```text
release_id, version, channel, manifest, manifest_signature,
package_sha256, package_size, github_repository,
github_release_id, github_asset_id, github_asset_name,
rollout_percentage, rollout_seed, paused, enabled, published_at
```

#### download_tickets

```text
ticket_id, ticket_digest, release_id, license_id, device_id,
expected_sha256, expected_size, expires_at, created_at,
last_used_at, revoked_at
```

#### admin_tokens

```text
id, token_id, token_digest, display_name, scopes_json,
status, created_at, last_used_at, revoked_at
```

#### audit_events

```text
id, actor_type, actor_id, action, target_type, target_id,
result, request_id, metadata_json, created_at
```

#### idempotency_records

```text
scope, idempotency_key, request_digest, response_status,
response_body, expires_at
```

#### diagnostic_submissions

```text
id, license_id, device_id, object_key, size, sha256,
client_version, launcher_version, status, submitted_at,
expires_at, downloaded_at
```

### 9.5 密钥与令牌摘要

许可证密钥和设备令牌均包含足够随机熵。服务端使用带 Pepper 的 HMAC-SHA-256 摘要，不保存明文。

设备令牌采用可索引 ID 和 Secret 分离格式：

```text
wcdt_<token_id>.<token_secret>
```

管理员 Token 类似：

```text
wcadmin_<token_id>.<token_secret>
```

数据库通过 token_id 定位记录，再常量时间比较 Secret 摘要。

### 9.6 联系方式加密

联系方式主体作为 JSON 使用 AES-256-GCM 加密，每条记录使用随机 IV，AAD 绑定 `license_id`、密钥版本和数据结构版本。

邮箱、微信号等需要精确搜索的字段另存 HMAC 查询摘要。自由文本备注只加密，不支持模糊检索。

密钥轮换时并存 V1、V2：新写入使用新密钥，旧记录读取或批量迁移时重新加密，确认全部迁移后才能删除旧密钥。

### 9.7 审计与限流

审计记录管理员创建、暂停和吊销许可证，用户激活和解绑设备，发布启用或暂停，诊断下载或删除。不得记录密钥、Token、联系方式明文、原始指纹或 GitHub 凭证。

激活、异常高频验证、管理员接口、下载票据和诊断提交均需限流。正常的每次启动一次验证不应触发限流。

## 10. 管理员 CLI 与发布 CLI

### 10.1 管理员 CLI

命令入口：

```text
wechat-admin
```

配置和认证：

```text
wechat-admin config set-api-url https://api.example.com
wechat-admin auth set-token
wechat-admin auth status
```

Token 通过 DPAPI 保存，不写入项目 `.env`。

许可证：

```text
wechat-admin license create
wechat-admin license create --email user@example.com
wechat-admin license batch-create --count 100 --output licenses-2026-08.csv
wechat-admin license show lic_...
wechat-admin license suspend lic_...
wechat-admin license resume lic_...
wechat-admin license revoke lic_...
```

明文许可证只在创建时返回一次。批量 CSV 默认拒绝覆盖已有文件，并明确提示包含敏感密钥。

设备：

```text
wechat-admin device list --license lic_...
wechat-admin device disable dev_...
wechat-admin device enable dev_...
wechat-admin device unbind dev_...
```

发布：

```text
wechat-admin release list
wechat-admin release show rel_...
wechat-admin release enable rel_...
wechat-admin release pause rel_...
wechat-admin release set-rollout rel_... --percentage 100
```

### 10.2 本地发布 CLI

```text
wechat-release publish \
  --version 0.5.0 \
  --channel stable \
  --package dist/wechat-cli-app-0.5.0-win-x64.zip \
  --notes release-notes.md
```

流程：

```text
检查 Git 工作区状态
→ 检查版本号与 app-manifest.json
→ 计算 ZIP SHA-256
→ 生成 manifest.json
→ 使用本机 Ed25519 私钥签名
→ 创建私有 GitHub Release
→ 上传 ZIP、manifest、signature
→ 调用 Worker 管理 API 登记 Release
→ 默认保持未启用
→ 管理员显式 enable
```

发布上传和正式推送分开，支持 `publish`、`enable`、`pause`。

本地发布写凭证和 Worker 只读凭证必须分离，且只授权发布仓库。

## 11. Launcher、Web 页面与安装器交互

### 11.1 Launcher WebView2

Launcher 使用本地 HTML/CSS/JavaScript，不加载远程 UI。

主要状态：

- 初始化和环境检查；
- 未激活；
- 正在验证；
- 在线授权有效；
- 离线租约有效或即将到期；
- 许可证吊销、设备解绑或租约过期；
- 更新安装、健康检查、回滚和修复。

WebView2 仅暴露白名单原生接口：

```text
get_ui_state()
activate_license(license_key, device_name)
retry_validation()
start_application()
retry_update()
open_log_folder()
open_external_help(topic)
close_launcher()
```

许可证和设备令牌不得返回 JavaScript。禁止任意外部导航、任意文件读取和命令执行。

### 11.2 WebView2 Runtime

安装器优先使用系统已有 Microsoft Edge WebView2 Runtime。缺失时从微软官方来源下载安装。下载失败时不继续半安装，并提供明确错误和手动安装入口。

### 11.3 WeChat CLI Web 页面

新增一级页面“许可证与更新”：

```text
许可证与更新
├─ 许可证状态
├─ 当前设备
├─ 其他设备
├─ 应用更新
└─ 诊断与支持
```

页面显示许可证末四位、设备数、最近验证、离线剩余时间、当前版本、Launcher 版本和 stable 通道。不得显示完整许可证或设备令牌。

更新状态包括：

- 已是最新版本；
- 正在下载；
- 网络中断、等待恢复；
- 已下载、下次启动安装；
- 安全校验失败；
- 新版本启动失败、已自动回滚。

### 11.4 诊断包

默认不上传。生成前明确列出包含和排除内容。

包含：

- Launcher 和应用版本；
- Windows 与 WebView2 版本；
- 启动、更新和回滚日志；
- HTTP 状态码和错误类型；
- 脱敏设备标识；
- 安装目录结构摘要。

排除：

- 微信聊天记录和数据库；
- 数据库密钥；
- 完整许可证密钥；
- 设备令牌；
- 管理员和 GitHub Token；
- 联系方式；
- 原始 MachineGuid 和 SID。

界面提供两个独立动作：

```text
仅保存到本机
同意并提交给开发者
```

上传前再次扫描敏感模式并最终确认。R2 私有桶默认保留 30 天，管理员访问也必须经过 Worker 鉴权。

### 11.5 日志脱敏

日志写入前即脱敏，诊断包生成时进行第二次扫描。至少遮盖：

- 许可证格式；
- 设备和管理员 Token；
- GitHub Token 常见格式；
- Authorization、Cookie；
- URL 中的 ticket、token、key；
- 联系方式；
- Windows 用户目录名称。

### 11.6 安装器和 0.4.2 迁移

用户需要最后手动运行一次新的迁移安装包。

```text
检测旧版 app\wechat-cli.exe
→ 停止旧版服务
→ 创建迁移备份
→ 安装 Launcher
→ 将旧应用迁移为 versions\0.4.2
→ 创建 current.json
→ 重建快捷方式
→ 验证安装状态
→ 打开许可证激活窗口
```

迁移成功前不删除旧程序和旧快捷方式。失败时恢复旧入口并保留日志，不修改 `%USERPROFILE%\.wechat-cli\`。

安装器默认安装到 `%LOCALAPPDATA%\WeChatCliWeb`，通常不需要管理员权限；安装 WebView2 Runtime 时可能触发系统权限确认。

### 11.7 修复与卸载

修复可处理快捷方式、`current.json`、中断下载、未完成事务、Launcher 文件、版本目录和 WebView2 Runtime。修复不得重置许可证、解绑设备、删除微信数据或绕过签名。

卸载默认删除程序、缓存、快捷方式和运行日志，默认保留 `%USERPROFILE%\.wechat-cli\`。删除微信相关本地数据必须是未默认选中的独立选项。

## 12. Demo 范围与验收

### 12.1 Demo 实现范围

- Windows x86-64 Launcher；
- 0.4.2 迁移安装；
- 永久许可证和三设备上限；
- 设备列表、重命名、解绑；
- 设备令牌和 7 天离线租约；
- stable 启动检查和后台下载；
- Ed25519 清单签名与 SHA-256；
- 版本化目录、原子切换和自动回滚；
- `/api/health`；
- 管理员 CLI 和发布 CLI；
- 联系方式加密；
- 主动诊断提交；
- 本地自动化测试和真实 staging 端到端验收；
- Demo 安装包。

### 12.2 三层测试环境

1. 纯本地自动化测试：模拟 Worker、临时数据库、静态资产、可控时钟和故障注入。
2. 本地集成环境：真实 Launcher、本地 Worker/D1、测试签名、公用临时目录。
3. 真实 staging：独立 Worker、D1、R2、私有发布仓库、测试许可证和测试密钥。

staging 与 production 不复用任何 Pepper、加密密钥、签名私钥、GitHub Token 或管理员 Token。

### 12.3 核心自动化测试

许可证与设备：

- 单个和批量创建；
- 明文不落库；
- 正确、错误和吊销密钥；
- 相同设备重复激活；
- 三台成功、第四台拒绝；
- 解绑释放槽位；
- 并发激活不能突破上限；
- 幂等请求不重复创建。

离线租约：

- 签发和验签；
- 篡改有效期失败；
- 7 天内断网允许，过期拒绝；
- 明确吊销不能回退旧租约；
- 网络超时可回退有效租约；
- HTTP 401/403 不能当作网络错误；
- 时间回拨和本地状态损坏处理。

更新安全：

- 正确签名和哈希；
- 清单、签名、ZIP 篡改；
- 产品、平台、架构和版本不匹配；
- ZIP 路径穿越和异常解压体积；
- 下载票据过期、跨设备复用；
- 未登记 Asset 不能代理。

更新事务：

- 断点续传；
- 当前会话不强制退出；
- 下次启动安装；
- 健康成功提交；
- 超时、错误版本和进程退出自动回滚；
- 各事务阶段中断恢复；
- 失败版本不循环；
- 仅保留当前和上一版本；
- 用户微信数据目录不变。

安装与隐私：

- 全新安装和 0.4.2 迁移；
- WebView2 已安装、缺失和下载失败；
- 磁盘、权限、快捷方式和迁移恢复；
- 许可证和 Token 不进入日志或 JavaScript；
- 诊断默认不上传且不包含微信数据；
- 日志脱敏和稳定错误编号。

### 12.4 真实端到端场景

- 全新安装并激活第一台设备；
- 三台设备上限、第四台拒绝和解绑后重试；
- 第 6 天离线可用、第 8 天拒绝；
- 0.5.0 发现、下载并升级到 0.5.1；
- 篡改 ZIP 或清单被拒绝；
- 发布健康检查失败的 0.5.2，自动回滚到 0.5.1；
- 管理员吊销后，联网启动立即锁定；
- 用户主动提交诊断包，管理员查询、下载和删除。

### 12.5 完成门槛

只有同时满足下列条件才能宣布 Demo 完成：

- 新增测试和现有 WeChat CLI 测试全部通过；
- Worker 类型检查、测试和 D1 迁移通过；
- 安装包可重复构建；
- 仓库敏感信息扫描无私钥、Token 和明文测试许可证；
- 全新安装、0.4.2 迁移、许可证、更新、回滚和诊断本地闭环通过；
- staging Worker、D1、R2 和私有 Release 真实运行；
- 真实 0.5.0 → 0.5.1 更新成功；
- 真实故障版 0.5.2 自动回滚；
- 验收报告记录命令、退出码、测试数量、构建摘要、日志和已知限制。

## 13. 分阶段实施计划基线

本文件批准后，再使用 `writing-plans` Skill 编写可执行计划，不在设计阶段实施代码。

计划阶段建议按以下顺序拆分：

1. 冻结协议、记录现有安装结构和测试基线。
2. 共享协议、清单、错误码、签名与可控时钟。
3. Worker、D1、租约、许可证、设备和管理员 CLI。
4. Launcher DPAPI、WebView2、授权与启动会话。
5. 更新下载、验签、安全解压、事务和回滚。
6. WeChat CLI Web 的 `/api/health`、许可证页面、更新状态和诊断。
7. 安装器、0.4.2 迁移、修复和卸载。
8. staging Cloudflare 与私有 GitHub Release 真实闭环。
9. 回归、敏感信息扫描、安装包和验收报告。

每阶段遵循：

```text
先写失败测试
→ 实现最小能力
→ 运行本阶段测试
→ 运行受影响的现有测试
→ 检查差异
→ 再进入下一阶段
```

创建私有仓库、Cloudflare 资源、Token、Secret 或实际部署属于外部副作用，执行前必须再次取得用户明确授权。

## 14. 风险与实施期验证事项

以下事项不改变已批准架构，但必须在实施计划或原型阶段用真实证据确认：

1. Cloudflare Worker 代理私有 GitHub Release 大文件时的流量、请求时长、Range、缓存和套餐限制。
2. 中国大陆不同网络对 Cloudflare 和 GitHub 代理下载的稳定性；Demo 可接受，正式生产可能需要备案域名和大陆可用对象存储/CDN。
3. Python WebView2 封装库的长期维护、打包体积、运行时检测和杀毒软件兼容性。
4. 未签名 Demo 安装器可能触发 SmartScreen 或安全软件提示。
5. 本地 DPAPI 和一次性会话只能防止普通绕过，不能视为强反破解方案。
6. 完全离线设备不能即时接收吊销或解绑，只能受 7 天租约上限约束。
7. 签名密钥丢失、泄露和轮换需要单独的离线备份与应急手册。

## 15. 需求追踪检查表

- [x] 永久许可证
- [x] 每许可证最多 3 台设备
- [x] 用户可管理设备
- [x] 当前设备令牌授权设备管理
- [x] 7 天离线租约
- [x] 在线吊销立即锁定
- [x] 随机设备 ID + MachineGuid/SID 摘要
- [x] 首次独立 WebView2 激活，日常 Web 页面管理
- [x] 系统 WebView2 优先、缺失时安装器下载
- [x] 双层许可证验证
- [x] 启动时检查一次
- [x] 自动后台下载、下次启动安装
- [x] 版本目录 + current 指针
- [x] `/api/health` 和自动回滚
- [x] 当前版 + 上一版保留
- [x] stable/beta 协议预留，Demo stable
- [x] 灰度协议预留，Demo 100%
- [x] 强制更新协议预留，Demo 不启用
- [x] Launcher 自更新协议预留，Demo 不实施
- [x] Ed25519 清单签名
- [x] 本地私钥发布，未来 GitHub Actions Secret
- [x] 私有 GitHub Releases + Worker 代理
- [x] 两个私有仓库
- [x] D1 许可证与设备元数据
- [x] R2 主动诊断包
- [x] 管理员 CLI
- [x] 单个与批量许可证 CSV
- [x] 联系方式加密和密钥轮换
- [x] 默认不上传日志，主动确认提交
- [x] 最后一次手动迁移安装包
- [x] 本地模拟和真实 staging 双重验收
- [x] Demo 未签名，正式公开版必须代码签名

## 16. 审阅与批准

本设计来源于逐项需求确认和七部分详细设计确认。用户已于 2026-08-04 明确批准书面设计，并授权在不继续逐项申请的情况下开始本地实施。

实施约束：

1. 先编写逐文件、逐测试的实施计划，再按阶段实施；
2. 新增行为遵循测试驱动开发，并在每阶段结束后执行适用验证；
3. 现有 `invite_stats` 未提交修改保持原样，不混入本任务；
4. 不在源码、日志或文档中写入 Token、私钥或许可证密钥；
5. 创建云资源、仓库、令牌和实际部署仅在具备明确凭证与安全条件时执行，并记录真实结果。
