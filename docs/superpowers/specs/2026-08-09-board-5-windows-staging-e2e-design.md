# Board 5 Windows Staging E2E Design

日期：2026-08-09
状态：**设计已获批准；2026-08-09 Board 5 Local implementation gate 已获批准，仅授权 Task 1–3 的本地代码/测试实现。bootstrap build/install、许可证、Windows E2E、外部写入、cleanup、push/merge/tag 仍未授权。**

## 1. 目标

Board 5 在一台真实 Windows 主机上，以完全隔离的本地安装/用户数据环境和真实 staging 云端资源，完成从 0.5.0 bootstrap 到 0.5.1 在线更新、真实 Launcher 重启安装、health check、真实离线启动、确定性七天租约边界和独立故障候选自动回滚的端到端验收。

Board 5 必须同时证明两件事：

1. 正常路径真实成立：`staging bootstrap -> 0.5.0 -> 授权 -> update check -> private download -> 0.5.1 -> restart -> health`。
2. 失败路径真实成立：独立 beta fault candidate 能通过合法发布/下载/解包链进入待切换状态，但因运行时 health contract 不满足而自动恢复 0.5.1，并记录 failed-version suppression。

Board 5 不承担生产发布、正式代码签名、生产域名、正式凭据和 Git 集成。

## 2. 冻结边界

### 2.1 Board 4 完成快照

Board 4 完成快照固定为：

- branch：`task5/0.5.1-update-validation`
- HEAD：`8c7464f058a9edf520b4c97e02b63835a3c0901c`
- worktree：`C:\Users\28276\.devspace\worktrees\wechat-cli-1ec755b9`

Board 5 不再向该 worktree 写入任何文件。

### 2.2 Board 5 开发 worktree

Board 5 文档和后续实现使用独立 worktree：

- path：`C:\Users\28276\.devspace\worktrees\wechat-cli-1ec755b9-46a6ab4b`
- branch：`board5/windows-staging-e2e`
- base：`8c7464f058a9edf520b4c97e02b63835a3c0901c`

Board 5 implementation、tests、acceptance tooling、spec/plan/report 只能写入该 worktree。

### 2.3 0.5.0 build-source worktree

bootstrap 内的 0.5.0 app 与 Launcher 0.1.0 只能来自冻结 main 基线：

- SHA：`a579a25cb7f16e6fdf88d618252b4a5cbffef53d`
- temporary build-source path：`C:\Users\28276\.devspace\worktrees\wechat-cli-1ec755b9-54a1291f`
- state：detached HEAD

这个 worktree 只承担源代码/二进制来源，不承载 Board 5 代码改动或提交。

main checkout `D:\use_as_desktop\Wechat__CLI\wechat-cli` 不修改；其未跟踪 `NUL` 必须保留。

## 3. staging bootstrap 配置来源

Board 5 不允许复用 Demo launcher config，不允许手工复制公钥值，也不把 staging 环境配置提交到 Git。

正式 staging launcher config 必须由一个最小 Board 5 工具从以下非敏感来源组装：

- API URL：`https://wechat-cli-license-update-staging.aurevior-ai.workers.dev`
- channel：`stable`
- Board 5 专用 loopback application port，默认建议 `18787`
- Board 5 固定、非敏感 staging fingerprint salt
- 仓库外已验收的 Launcher 公钥注册文件中的：
  - `release-key-staging-01`
  - `lease-key-staging-01`

输出文件必须位于仓库外受限 Board 5 artifact/config 目录，例如：

`D:\use_as_desktop\Wechat__CLI\staging-secrets-20260805\board5\launcher-config.board5-staging.json`

生成后必须使用生产实现 `LauncherConfig.load()` 重新加载并 fail closed 校验。工具日志只能输出 config path、SHA-256、API host、channel、port 和 key IDs，不输出公钥值。

## 4. bootstrap-only / external-output 构建边界

当前 `scripts/package_windows_app.py` 的完整 `create_package()` 会同时创建 bootstrap 和 update ZIP。Board 5 禁止依赖操作人员“不要碰旧文件”，必须在代码层增加显式隔离能力。

Board 5 implementation 必须以 TDD 增加：

1. `--bootstrap-only`：只组装 bootstrap directory/ZIP，绝不调用 `create_update_package()`。
2. `--output-dir`：所有 Board 5 bootstrap 输出写入显式仓库外目录，默认不得落入仓库 `dist/`。
3. `--source-root`：允许从冻结 `a579a25` worktree读取 packaging templates、版本文件和 source metadata。
4. `--binary-root`：允许使用冻结 build-source worktree实际构建出的 `wechat-cli.exe` 与 `wechat-cli-launcher.exe`。
5. fail closed：bootstrap-only 模式下若检测到目标 update ZIP 将被创建/覆盖，直接失败。
6. 所有 Board 5 repo-external 输出边界统一复用 `assert_outside_repository(path)`：必须拒绝 `path == repository root`、repository 任意子目录，以及 symlink/resolve 后最终进入 repository 的路径；bootstrap output、launcher config output、fault package output 不得各写一套略有差异的判断。

Board 5 每次 bootstrap build 前后都必须只读核验 main checkout 中固定 0.5.0 update ZIP：

- size：`14291197`
- SHA-256：`406b72c14ad186141f373087595f7723e143b9638bf298fde23b6bb0ae057523`

任何漂移都终止 Board 5。

Board 5 不允许重新发布或替换该固定 0.5.0 update ZIP。

## 5. Windows 隔离环境

Board 5 使用当前 Windows 用户，因此许可证本地状态继续由真实 current-user DPAPI 保护；不使用 test protector。

只改变 Board 5 子进程环境，不修改用户全局环境变量。每个真实 installer/Launcher/app 进程必须同时覆盖：

- `LOCALAPPDATA=<Board5Root>\LocalAppData`
- `APPDATA=<Board5Root>\UserProfile\AppData\Roaming`
- `USERPROFILE=<Board5Root>\UserProfile`
- `HOME=<Board5Root>\UserProfile`
- `TEMP=<Board5Root>\Temp`
- `TMP=<Board5Root>\Temp`

原因：安装、license state、update cache 位于 `%LOCALAPPDATA%\WeChatCliWeb`，但传统应用配置仍使用 `~/.wechat-cli`。只隔离 `LOCALAPPDATA` 不足以保护日常用户数据。

### 5.1 installer flags

Board 5 installer 固定使用：

- `-NoStart`
- `-NoShortcuts`
- `-SkipProcessStop`

这防止安装脚本停止日常 WeChat CLI 进程或修改真实桌面/开始菜单。

### 5.2 WebView2

真实安装前先只读检测系统 WebView2 Runtime：

- 已存在：Board 5 installer 使用 `-SkipWebView2Check`，不下载/安装系统组件。
- 不存在：Board 5 立即停止，另行请求系统级 WebView2 安装授权。

Board 5 计划本身不包含安装 WebView2 的隐含授权。

## 6. 两张 Board 5 专用 staging 许可证

Board 5 不再修改 Board 4 `JD25` 许可证。

必须使用两张新的 staging 测试许可证：

### 6.1 stable license

用途仅限正常成功链：

`bootstrap 0.5.0 -> activation -> stable 0.5.1 update -> offline acceptance`

要求：

- `release_channel=stable`
- 独立 license ID / hint
- 完整许可证只保存到仓库外受限文件，不进入 shell history、Git 或聊天记录

### 6.2 beta license

用途仅限 RollbackSandbox / fault release：

- `release_channel=beta`
- 与 stable license 完全独立的 device/license state
- fault test 结束后进入独立清理授权门槛

### 6.3 channel trust boundary

Worker 当前 `/v1/updates/check` 会使用客户端 request 中的 `channel` 做 release selection，但没有强制 `authenticated.license.release_channel == request.channel`。

Board 5 **不得依赖这个缺口**。正常环境使用 stable license + stable current channel；RollbackSandbox 使用 beta license + beta current channel。两边必须一致。

该缺口作为 Board 6 production trust-boundary 风险记录，不在 Board 5 中借用或修复，除非后续另行批准范围变更。

## 7. stable 0.5.0 -> 0.5.1 真实 E2E

### 7.1 安装与激活

1. 从 `a579a25` build-source 构建真实 0.5.0 app + Launcher 0.1.0。
2. 使用仓库外 staging launcher config 创建 bootstrap-only ZIP。
3. 在 Board 5 隔离环境安装 bootstrap；不启动、不创建快捷方式、不停止用户日常进程。
4. 只读验证：
   - `current_version=0.5.0`
   - Launcher `0.1.0`
   - config host/channel/key IDs 正确
   - 安装根属于 Board 5 `LOCALAPPDATA`
5. 使用 stable Board 5 license 在真实 Launcher UI 完成首次激活；完整许可证由用户从安全文件粘贴，避免进入 CLI 参数/history。
6. 验证真实 current-user DPAPI `state/license-state.dat` 已建立，不读取/打印其明文。
7. 启动 0.5.0，`/api/health` 必须严格验证 `product=wechat-cli-web`、`version=0.5.0`、`status=ok`。冻结 `a579a25` 的 runtime `BUILD_ID` 默认来自 `WECHAT_CLI_BUILD_ID` 或 `dev`；Board 5 不为制造证据一致而给真实 E2E 人为注入 `WECHAT_CLI_BUILD_ID`。bootstrap/package `app-manifest.json` 继续使用历史 build label `0.5.0-local-20260805.1`，真实 runtime `build_id` 作为独立历史观测值记录；若实际为 `dev`，如实记录。0.5.1 runtime 仍必须严格为 `staging-051-20260808.1`。

### 7.2 更新、下载、重启安装

真实更新链必须经过 staging Worker 与 private GitHub asset：

1. 0.5.0 发起 stable update check。
2. Worker 选择既有 `rel_staging_051`；Board 5 不修改该 release。
3. 客户端取得短期 download ticket。
4. 从 private GitHub release asset 下载真实 0.5.1 package。
5. 验证 Ed25519 manifest、package SHA-256、size、安全解包。
6. 当前 0.5.0 session 不应被更新下载打断。
7. `pending-update.json` 准备完成后退出并重新运行真实 Launcher。
8. Launcher 原子切换到 0.5.1，启动应用并等待 health。
9. health 必须精确报告 0.5.1。
10. transaction commit 后：
    - current `0.5.1`
    - previous `0.5.0`
    - current manifest SHA-256 = `be111f0a786821319fb96f82f1748b4a75003b7c5fb296c48ec87b3355a3fd62`

真实下载 package 必须仍为：

- size：`14268929`
- SHA-256：`0ddbb0b402cc9d98ed001391c1a618527d165e328a1f4f1534d80e6b984956c0`

`rel_staging_050` / `rel_staging_051` 的 enabled/paused/rollout/hash/GitHub mapping 在 Board 5 中始终只读。

## 8. Offline acceptance 与七天时钟边界

Board 5 不修改 Windows 系统时钟，不断开整台机器网络。

采用两层证据：

### 8.1 真实 Launcher 网络不可达启动

从成功的 stable 0.5.1 安装创建独立 OfflineSandbox，保留其真实 current-user DPAPI license state，但将 sandbox launcher config 的 API URL 通过受控工具改成确定不可达的 localhost HTTPS endpoint。

工具必须：

- 确认目标路径属于 Board 5 OfflineSandbox；
- 解析原始 config；
- 保留 channel、port、公钥 registry、fingerprint salt；
- 只替换 API authority；
- 再次 `LauncherConfig.load()` 验证。

随后运行真实 Launcher，证明在线验证网络失败时仍使用同一份真实签名 lease，进入 `offline_valid` 并成功启动 0.5.1。

### 8.2 相同真实 DPAPI state 的确定性时间验证

Board 5 专用验收工具使用 current-user DPAPI 读取 **同一份真实 OfflineSandbox `license-state.dat`**，但只能输出安全摘要。

使用正式 `verify_signed_lease()` / `TrustedTimeState` 逻辑验证：

- signature/key ID 正确；
- `offline_until - 1s` 仍允许；
- `offline_until + 1s` 为 `offline_expired`；
- 约 4 分钟的小幅 wall-clock correction 允许；
- 约 10 分钟的显著 rollback 返回 `OFFLINE_LEASE_DENIED`。

报告必须表述为“真实网络不可达 Launcher 启动 + 相同真实 DPAPI state 的生产策略确定性时钟边界”，不得写成“等待了真实七天”。

如以后要求直接修改 Windows 系统时钟，必须另行申请管理员级授权，并且不属于默认 Board 5 退出条件。

## 9. RollbackSandbox 与 beta fault release

### 9.1 不利用 channel trust-boundary 缺口

RollbackSandbox 从已成功更新到 0.5.1 的安装副本开始，但不能沿用 stable license 伪装 beta 客户端。

必须：

1. 创建独立 RollbackSandbox 副本；
2. 不复制 stable `license-state.dat`，或在复制阶段明确排除该文件；
3. 使用 beta Board 5 license 重新走真实 Launcher activation，建立新的 DPAPI beta authorization state；
4. sandbox `CurrentVersion.channel` 必须通过受控状态工具变为 `beta`；
5. beta license `release_channel=beta` 与 update request channel 必须一致。

### 9.2 禁止手工编辑 current.json

不得直接文本编辑 `RollbackSandbox\state\current.json`。

新增最小 Board 5 state tool，复用正式 `CurrentVersion` / `InstallLayout` 解析和持久化逻辑。执行 channel 切换前必须 fail closed 验证：

- install root 属于 Board 5 RollbackSandbox；
- `current_version == 0.5.1`；
- `previous_version == 0.5.0`；
- `manifest_sha256 == be111f0a786821319fb96f82f1748b4a75003b7c5fb296c48ec87b3355a3fd62`；
- 0.5.0 / 0.5.1 version directories 都存在。

只允许创建一个新的 `CurrentVersion`，保留 current/previous/activated_at/manifest hash，仅把 channel 从 stable 变为 beta，再通过 `InstallLayout.save_current()` 原子写回。

### 9.3 fault candidate

推荐故障候选版本：`0.5.2-board5bad.1`

推荐 Worker release ID：`rel_board5_bad_052_01`

channel：`beta`

fault package 不损坏 PE，不注入恶意代码。它使用已经验收的真实 0.5.1 `wechat-cli.exe`，但 package `app-manifest.json` 声明版本 `0.5.2-board5bad.1`。

因此：

- package structure 合法；
- ZIP hash 合法；
- signed release manifest 合法；
- private download 合法；
- safe extraction 合法；
- EXE 可以真实启动；
- 但 Launcher 等待 `0.5.2-board5bad.1` health，EXE 实际报告 `0.5.1`，从而确定性触发 health mismatch。

这个方式专门验证“候选可启动但不满足运行时版本契约 -> rollback”，不依赖随机损坏。

### 9.4 fault publication lifecycle

fault release 必须使用全新 private GitHub Draft / asset IDs / D1 release row，绝不修改 `v0.5.0`、`v0.5.1`、`rel_staging_050` 或 `rel_staging_051`。

生命周期：

1. local prepare/sign only；
2. 经独立授权创建 fault Draft + 三 assets；
3. Worker register：`enabled=false`, `paused=true`, rollout 100；
4. 后验只读核验；
5. 经独立授权 enable：`enabled=true`, `paused=false`；
6. beta RollbackSandbox 真实 download/switch/health fail；
7. 自动 rollback 到 0.5.1；
8. `failed-versions.json` 记录 fault candidate；
9. 再执行一次 beta update check，验证同版本不再被提供；
10. 经独立授权将 fault release 恢复为 `enabled=false`, `paused=true`。

fault GitHub Draft 和 D1 row 默认保留为不可用验收证据，不自动删除。

## 10. failed-version suppression 的准确语义

当前本地 `FailedVersionRegistry` 的 key 是：

`version + manifest_sha256`

但 `failed_versions()` 发送给 Worker 的只有 version；Worker selection 也只按 version 排除。

因此 Board 5 只能声称并验证：

> 某个失败版本在该客户端后续 update check 中不再被服务端提供。

不得声称：

> Worker 实现了 manifest-hash 级 suppression。

version-only server suppression 与 channel trust boundary 一并进入 Board 6 security review。

## 11. 清理设计

### 11.1 staging 数据

Board 5 验收完成后：

- stable Board 5 license：经独立授权 revoke；必要设备进入明确 unbound/revoked 状态；
- beta Board 5 license：经独立授权 revoke；
- fault release：经独立授权保持 `enabled=false`, `paused=true`；
- fault GitHub Draft + Worker row 默认保留，不自动删除；
- `rel_staging_050` / `rel_staging_051` 不属于清理对象。

### 11.2 本机数据

Board 5 repo-external artifact root 在后续 **Bootstrap build gate** 首次真实初始化时，必须同时创建 `.board5-acceptance-root`（或设计等价且由共享 guard 验证的 marker）。当前 Local implementation gate 只实现/测试 marker 与 guard 逻辑，不创建真实 artifact root 或 marker。

完成证据归档后，只有获得独立删除授权才能物理删除：

- Board 5 LocalAppData root；
- Board 5 UserProfile/.wechat-cli；
- Board 5 Temp；
- OfflineSandbox；
- RollbackSandbox；
- repo-external Board 5 bootstrap/fault temporary artifacts。

禁止运行可能针对日常环境的通用 uninstall；清理工具必须先验证目标路径属于 Board 5 root。任何缺少正确 marker 的 artifact/root 目录都必须 fail closed，禁止删除。

main checkout、Board 4 worktree、真实 `%LOCALAPPDATA%\WeChatCliWeb`、真实 `%USERPROFILE%\.wechat-cli` 和 main `NUL` 全部不动。

## 12. 授权门槛

设计/计划批准不等于实施授权。Board 5 按以下阶段申请授权：

1. **Local implementation gate**：只在 Board 5 worktree 用 TDD 实现 bootstrap-only/config/sandbox/offline/evidence tooling；不得 build/install/cloud write。
2. **Bootstrap build gate**：从 `a579a25` build-source 构建 0.5.0 app + Launcher 0.1.0，并生成 repo-external staging bootstrap；不得安装。
3. **Stable license gate**：创建一张 Board 5 stable staging license；不得安装/激活。
4. **Stable install/activation gate**：只在 Board 5 隔离 Windows root 安装 bootstrap 并激活 stable license。
5. **Stable E2E gate**：执行真实 stable 0.5.0 -> 0.5.1 check/download/restart/health；`rel_staging_050/051` 只读。
6. **Offline acceptance gate**：创建 OfflineSandbox 并执行真实网络不可达启动与确定性时间边界；不修改系统时钟。
7. **Beta license gate**：创建 Board 5 beta staging license。
8. **Fault local prepare gate**：本地构造并签名 fault candidate；不得发布。
9. **Fault publish/register gate**：创建独立 GitHub Draft + 三 assets + Worker disabled/paused row。
10. **Fault enable/rollback gate**：短时 enable fault release 并执行 beta RollbackSandbox rollback/suppression 验收。
11. **Fault disable gate**：恢复 fault release 为 disabled/paused。
12. **Cloud cleanup gate**：revoke Board 5 stable/beta licenses、整理设备状态；不删除 Board 4 release/license evidence。
13. **Local cleanup gate**：删除 Board 5 本地测试 roots/artifacts。

任何 GitHub/Cloudflare 写阶段都必须：

- 写前只读 duplicate/hash/state preflight；
- 写后只读 reconcile；
- ambiguous write 失败后禁止盲目 retry；
- 先查真实远端状态再决定后续动作。

push、merge、tag、Board 4 worktree 删除始终不包含在 Board 5 阶段授权中。

## 13. Board 5 验收证据

最终报告建议：

`docs/deployment/2026-08-xx-board-5-windows-e2e-report.md`

允许记录：

- source/base commits；
- worktree/branch 名称；
- bootstrap SHA-256 / size / member summary；
- launcher config SHA-256、API host、channel、port、key IDs；
- stable/beta license ID、hint、status、channel；
- 安全化 device identifiers；
- 0.5.0 / 0.5.1 health version/build ID；
- package/manifest hashes；
- Release/Asset IDs；
- audit request IDs；
- `current.json` 非敏感字段；
- rollback reason；
- failed candidate version + manifest SHA；
- 测试数量和 Git 状态；
- 每个外部写入门槛的授权/后验状态。

禁止记录：

- 完整许可证；
- device token；
- DPAPI 明文；
- raw lease bytes/signature；
- release/lease 公钥值；
- release private key；
- GitHub/Admin tokens；
- MachineGuid；
- SID；
- `.env` / Cookie。

## 14. Board 6 风险移交

Board 5 完成时必须把以下两项明确移交 Board 6 security review：

1. Worker update check 没有强制 `license.release_channel == request.channel`。
2. 本地 failed registry 按 `version + manifest_sha256` 保存，但发给 Worker/服务端排除只有 version，服务端不是 manifest-hash 级 suppression。

Board 5 不依赖第 1 项缺口，不夸大第 2 项语义。

## 15. Board 5 退出条件

只有以下全部成立才能把 Board 5 标记为完成：

- staging bootstrap 可证明来自 `a579a25` 的 0.5.0 app + Launcher 0.1.0；
- staging config 来源、API host、release/lease key IDs 验证通过；
- 固定 0.5.0 update ZIP 前后 size/hash 完全未变；
- 本机所有 Board 5 安装/状态/用户数据均位于隔离 root；
- stable Board 5 license 在真实 Launcher 中激活并使用真实 DPAPI；
- 0.5.0 health 成功；
- 真实 staging 下载的 0.5.1 package size/hash 与 Board 4 冻结证据一致；
- 重启后 0.5.1 health 成功；
- `current=0.5.1`, `previous=0.5.0`, manifest hash 正确；
- 真实网络不可达 Launcher 使用相同真实 lease 成功 offline 启动；
- 同一真实 DPAPI state 的 7 天过期/小幅修正/显著回拨边界验证通过；
- beta RollbackSandbox 使用独立 beta license，未利用 channel trust-boundary 缺口；
- fault candidate 经真实 staging download/switch 后因 health mismatch 自动恢复 0.5.1；
- failed-version version-level suppression 被真实复验；
- fault release 最终 `enabled=false`, `paused=true`；
- Board 5 stable/beta license 和设备进入明确记录的清理状态；
- `rel_staging_050` / `rel_staging_051` 前后关键字段完全一致；
- Board 4 worktree 保留且干净；
- main 仍冻结在 `a579a25`，未跟踪 `NUL` 保留；
- 无 push、merge、tag 或生产动作；
- Board 5 acceptance report 与 roadmap/project state 完成收口。

## 16. 当前授权状态

截至本文写入：

- Board 5 设计方向：已批准；
- 本文三项用户修订：已纳入并冻结；
- Board 5 worktree/branch 创建：已授权并完成；
- `a579a25` temporary build-source worktree 创建：已授权并完成；
- design/spec 与 implementation plan 文档写入/本地提交：已授权；
- Board 5 Local implementation gate：**已授权**，范围仅限按 TDD 实施 Task 1–3 的本地代码与测试；
- bootstrap build/install/license/release/cloud/E2E/cleanup：**均未授权**；
- push/merge/tag：**未授权**。
