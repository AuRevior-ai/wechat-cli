# WeChat CLI 授权更新项目总路线图

> Repository-wide current-state summary: [`docs/PROJECT_STATE.md`](../PROJECT_STATE.md). This roadmap remains authoritative for the fixed seven-board licensing, update, release, and deployment program.

更新时间：2026-08-14
状态来源：本文件为七板块状态、检查点和下一步动作的唯一权威记录。
实施状态：**板块 4 Task 1–7 已完成并通过验收。Board 5 Local implementation Task 1–3、Bootstrap build Task 4、stable license creation、isolated bootstrap install/activation 与 stable real 0.5.0→0.5.1 Windows E2E 均已完成。经独立授权，private `v0.5.1` 已发布并完成 stable E2E；Offline acceptance、beta license/alignment、fault local prepare、fault publish/register 与 fault-enable gates 均已完成。fault Draft visibility blocker 也已在独立授权下解除：GitHub Release ID `368572125` 已改为 private prerelease（`draft=false`、`prerelease=true`、`make_latest=false`），真实 `v0.5.2-board5bad.1` tag 指向 release-repository commit `2b9fa385b86df83f7968239a1029d4d59f020027`，三个冻结 asset 未漂移，post-publish one-byte Worker probe 返回 HTTP 206 / `bytes 0-0/14268937`。随后真实 rollback attempt 成功完成 fault full download、验签、安全解包与 pointer rollback；transaction=`rolled_back`，failure reason=`application health version does not match the update`，current 恢复 0.5.1，failed registry 记录 `0.5.2-board5bad.1`。但真实验收未通过：PyInstaller candidate child 在 Popen parent 退出后仍残留并占用 18787，使 restored health 误读残留 candidate listener。异常 RollbackSandbox app 已精确停止，stable 0.5.1 已恢复并 fresh health/session 通过。process-tree repair 已在 `29aba6bc0c8469dc8b5dc512d6831c5385246431` 完成，并通过新的 RollbackRepairSandbox 真实重验：candidate tree 被完整回收，transaction=`rolled_back`，current 恢复 0.5.1，sole listener 路径属于 restored `versions/0.5.1/wechat-cli.exe`，health/session valid；failed registry 记录 candidate version + manifest hash，随后携带 `failed_versions=[0.5.2-board5bad.1]` 的 beta check 返回 no update，证明 **version-level server suppression**。repair sandbox 已停止且 stable 0.5.1 已恢复。最终 fault-disable gate 已在独立授权下完成：一次 Admin API PATCH 同时把 `rel_board5_bad_052_01` 设为 `enabled=false` / `paused=true`，rollout 保持 100；GitHub prerelease/tag/assets 与 stable 050/051 未漂移。Board 5 **accepted complete**。2026-08-12 Cloud Cleanup Gate 已完成：stable/beta 两张 Board 5 license 均为 `revoked`、revision=2、`active_devices=0`，两个关联 Board 5 test device row 均为 `unbound`；fresh post-cleanup reconcile 证明 JD25、stable 050/051、fault disabled/paused、GitHub releases/assets/tags 均未漂移。Fresh final verification 通过 Python 529 run / 2 expected skips / 0 failures、Worker typecheck、Vitest 21/21、immutable Git/worktree checks 与固定 0.5.0 ZIP size/hash 复核。最终验收报告为 `docs/deployment/2026-08-12-board-5-windows-e2e-report.md`。local physical cleanup 仍为可选独立删除 gate；production、push、merge、tag modification 仍未授权。Board 6 已进入 **in progress**：B6-G0 source integration 已完成至 `c1d045895a044dbb4c9998a787c77775654074fa`；B6-G1 Update Trust Local Gate 已完成至 `bdc98afc0d945c4c86f1e3b21686d2fe798ccdd1`，对应 `a23b6ff` server-authoritative channel、`988a504` exact failed-release identity/version immutability、`bdc98af` local R2 distribution/lifecycle model。fresh B6-G1 gate verification 为 Python 510 run / 2 expected skips / 0 failures、Worker typecheck PASS、Vitest 40/40。B6-G2 Admin & Data Security Local Gate 已完成至 `e0c91df`，fresh gate verification 为 Python 524 run / 2 expected skips / 0 failures、Worker typecheck PASS、Vitest 89/89，且无 Access/staging/真实 Secret/cloud/production mutation。B6-G3 Windows Integrity Local Gate 已完成至 `1a07447`，pre-staging security audit=`d73cf3f`，fresh verification 为 Python 607 run / 2 expected skips / 0 failures、Worker typecheck PASS、Vitest 89/89；未执行真实签名、staging/cloud/production mutation。B6-G4 Staging Infrastructure Gate 已完成：`wechat-cli-releases-staging` R2、D1 `0004`–`0007`、七项 `_V1` staging Secret、Access admin custom domain/verifier 与 staging Worker Version `14a19ea3-5a96-408b-a4e3-0a8d8e4ebe2c` 均已 live 并完成 read-only reconcile；B6-G5 Staging Behavior Acceptance 已 accepted complete，证据为 `docs/superpowers/governance/2026-08-14-board-6-staging-behavior-acceptance.md`，live acceptance 已通过 channel authority/exact suppression、GitHub immutable provenance + R2 runtime distribution、Access-backed short-lived admin、Origin/rate 与 diagnostics retention/delete，并修复真实 staging 暴露的 JWKS redirect、R2 full-download status、Python channel mismatch error contract 与 diagnostics UA 缺口。B6-G6 Phase A provider-neutral readiness repair + provider research 已在本地完成：`9f4ad0f` 修复 deterministic Windows PowerShell Authenticode inspection，`e9cb67b` 扩展 complete public signer/timestamp-presence evidence，retained provider research=`docs/superpowers/governance/2026-08-14-board-6-code-signing-provider-decision.md`；fresh Phase A verification 为 Python 630 / 2 skips / 0 failures、Worker typecheck + Vitest 92/92、signing-focused 103/103 与 real system-signed probe PASS。当前已批准切换为 **Private / Controlled Distribution**：商业 Authenticode 不再是当前上线或 Board 6 closure blocker。B6-G6 Phase A 保持完成，`50e7074` 作为 dormant optional SSL.com adapter 保留；real provider procurement/KYC/payment/key provisioning/publisher-policy mutation/actual signing 明确 deferred 到未来 Public / Formal Distribution。下一 mandatory gate 改为 B6-G7；B6-G8 未进入，Board 7 未开始。frozen main 仍为 `a579a25cb7f16e6fdf88d618252b4a5cbffef53d`，Board 5 evidence 仍冻结在 `67d3dec0fd1c4a02c87be1ab79c4f78ea63f49d6`。**

## 1. 使用规则

1. 所有授权、更新、Cloudflare、GitHub Release、Windows 安装和正式上线工作开始前，必须先读取本文件。
2. 先读取 `docs/PROJECT_STATE.md` 获取仓库级当前状态；本文件只负责授权更新专项的七板块状态和外部副作用门槛。
3. 七个板块的名称与顺序固定，不得根据运行手册章节、技术 Task 或聊天摘要重新划分。
4. 每个板块开始前必须有独立计划，并取得用户批准。
5. 每个重要检查点后更新本文件；板块完成时补充验收报告和证据。
6. 本文件只记录非敏感状态。不得写入 Token、私钥、Cookie、明文许可证、管理员令牌或 `.env` 内容。

## 2. 七板块总览

| 编号 | 板块 | 状态 | 当前说明 |
|---|---|---|---|
| 1 | 本地最终收尾 | 已完成 | 本地实现、测试、构建、安装迁移与安全检查已完成 |
| 2 | 建立正式的两个私有 GitHub 仓库 | 已完成 | 源码仓库、发布仓库和最小权限凭据已建立 |
| 3 | 配置 Cloudflare staging 环境 | 已完成 | Worker、D1、R2、Secret、迁移和公网部署已完成 |
| 4 | 首次测试许可证与测试发布 | **已完成** | Task 1–7 全部完成；验收报告已生成，0.5.0/0.5.1 staging 资产与 Worker 状态已最终复核 |
| 5 | Windows 真实端到端验收 | **已完成** | functional E2E、process-tree repair、fresh rollback、version-level suppression、fault disable、Cloud Cleanup Gate、fresh final verification 与 final acceptance report 均已完成 |
| 6 | 安全与正式交付准备 | **进行中** | B6-G0 complete@`c1d0458`；B6-G1 complete@`bdc98af`；B6-G2 complete@`e0c91df`；B6-G3 complete@`1a07447` + audit `d73cf3f`；B6-G4 staging infrastructure complete；B6-G5 staging behavior accepted complete，report=`2026-08-14-board-6-staging-behavior-acceptance.md`，current Worker Version=`6f2aad56...`；B6-G6 Phase A complete，Private / Controlled Distribution amendment approved；commercial Authenticode deferred optional；next mandatory gate=B6-G7；B6-G8 未进入 |
| 7 | 自动化发布与正式上线 | 未开始 | 等待板块 6 完成并另行批准生产动作 |

## 3. 板块 1：本地最终收尾

### 目标

对现有全部改动做最后一次完整检查，完成本地实现、测试、Windows 构建、安装迁移、安全检查和 GUI 烟雾验收。

### 完成证据

- 验收报告：`docs/deployment/2026-08-05-local-finalization-report.md`
- Python 全量测试：465 项通过，2 项平台条件跳过
- Worker 类型检查、测试、本地 D1 迁移和本地 E2E 已通过
- Windows 应用、Launcher、bootstrap 和更新 ZIP 已生成并做本地验证
- 源码与发布相关功能已拆分提交

### 状态

**已完成。**

## 4. 板块 2：建立正式的两个私有 GitHub 仓库

### 目标

建立独立的私有源码仓库和私有发布仓库，并配置最小权限 GitHub 凭据。

### 完成证据

- 私有源码仓库：`AuRevior-ai/wechat-cli`
- 私有发布仓库：`AuRevior-ai/wechat-cli-releases`
- Worker 使用的发布仓库凭据为只读权限
- 本地发布 CLI 使用的凭据仅具备发布仓库必要写权限
- 两个仓库均已建立 `main` 分支远端跟踪

### 状态

**已完成。**

## 5. 板块 3：配置 Cloudflare staging 环境

### 目标

建立独立的 staging Worker、D1、R2、Secret 和公网测试地址，不使用生产资源或本地 Demo 密钥。

### 完成证据

- Worker：`wechat-cli-license-update-staging`
- 公网地址：`https://wechat-cli-license-update-staging.aurevior-ai.workers.dev`
- D1：`wechat-cli-license-staging`
- R2：`wechat-cli-diagnostics-staging`
- D1 迁移全部应用，无待执行迁移
- 首个管理员记录已写入 D1
- 8 项 Worker Secret 已配置，名称检查通过
- 定时任务：`17 * * * *`
- 管理员 API 已通过真实公网请求验证
- Cloudflare staging 配置已提交至源码仓库

### 已知说明

- `workers.dev` 仅用于 staging；正式环境需要稳定自定义域名。
- Preview URLs 当前由 Wrangler 默认启用，生产前需明确决策。

### 状态

**已完成。**

## 6. 板块 4：首次测试许可证与测试发布

> 状态证据说明：仓库内配置、代码、提交和本地产物可直接复验；Worker、D1、Secret、GitHub Release、许可证和设备状态若未重新联网核验，均表示 2026-08-05 路线图记录的最后人工验收状态。

### 原始目标

使用管理员 CLI 完成：

- 创建一张测试许可证；
- 验证最多三台设备限制；
- 测试激活、在线验证和七天离线租约；
- 测试设备重命名和解绑；
- 创建 0.5.0 基线发布；
- 再创建一个测试更新版本，例如 0.5.1；
- 验证许可证、设备和更新服务的基础链路真实连通。

### 当前已完成

- staging 专用密钥材料已生成并保存在仓库外安全目录；
- 管理员 Token 已存入 Windows 当前用户 DPAPI，明文副本已删除；
- 发布仓库 Token 已存入 Windows 当前用户 DPAPI；
- `release-key-staging-01` 的发布签名私钥和 Launcher 公钥已生成；
- 0.5.0 更新 ZIP 已计算并记录固定 SHA-256；
- `rel_staging_050` 的 manifest 和 Ed25519 signature 已本地验证；
- GitHub 私有 Draft Release `v0.5.0` 已创建；
- ZIP、manifest、signature 三项资产已上传；
- Worker 已登记 `rel_staging_050`；
- 当前状态：`enabled=True`、`paused=False`、`rollout_percentage=100`；
- 已创建真实 staging 测试许可证：ID `lic_ptrqZVAxh2NI8h5RM6gnGiiL`，提示 `JD25`，状态 `active`，`stable` 通道，最多 3 台设备；
- 完整许可证只保存在仓库外受限文件 `staging-secrets-20260805/staging-test-license-01.txt`，未写入 Git 或本路线图。

### 固定发布证据

- Release ID：`rel_staging_050`
- 版本：`0.5.0`
- Manifest SHA-256：`6f76cbc3052bea1e25fb8ecf53b5d1a88b16b27c40ebd341388d25e9514c1fed`
- Package SHA-256：`406b72c14ad186141f373087595f7723e143b9638bf298fde23b6bb0ae057523`
- Package size：`14291197`
- GitHub Release ID：`365469593`
- Package Asset ID：`502527074`
- Manifest Asset ID：`502527130`
- Signature Asset ID：`502527173`

### 0.5.1 Draft / Worker 登记证据

- Release ID：`rel_staging_051`
- 版本：`0.5.1`
- Manifest SHA-256：`be111f0a786821319fb96f82f1748b4a75003b7c5fb296c48ec87b3355a3fd62`
- Package SHA-256：`0ddbb0b402cc9d98ed001391c1a618527d165e328a1f4f1534d80e6b984956c0`
- Package size：`14268929`
- GitHub Draft Release：`v0.5.1`
- GitHub Release ID：`367353041`
- Package Asset ID：`506974337`
- Manifest Asset ID：`506974359`
- Signature Asset ID：`506974373`
- Worker：`enabled=true`、`paused=false`、`rollout_percentage=100`
- `release.register` audit request ID：`08e7af6c-98ac-4e29-9282-7b806f93c0da`
- `release.update` enable audit request ID：`626ff686-df79-4281-b1af-18bbabbac434`
- Worker `published_at=2026-08-09T01:54:20.521Z` 为登记时间；签名 manifest 的 `published_at=2026-08-08T12:44:04Z` 为签名元数据时间，两者不同是当前实现行为。

### 板块 4 验收报告

- `docs/deployment/2026-08-09-board-4-test-license-and-release-report.md`
- Task 7 fresh verification：Python 489 run / 487 passed / 2 skipped；Worker typecheck 通过、Vitest 17/17；0.5.1 update-only verifier 通过。
- 最终 live D1：测试许可证 active，设备历史 3 active + 1 unbound；`rel_staging_050` 与 `rel_staging_051` 均 enabled、未暂停、rollout 100；全部最终查询 `rows_written=0`。
- 最终 GitHub：`v0.5.0` / `v0.5.1` 均保持 private Draft，分别恰好三项 uploaded 资产，ID/名称/大小与记录一致。
- 安全扫描：非 tests tracked 源码/文档和 prepared 0.5.1 资产目录目标敏感形态 0 命中；宽泛 GitHub-token 形态仅存在于 4 个单元测试 fixture 文件。

### 当前阻塞与风险

- 当前已有 bootstrap 包仍包含本地 Demo URL 和 `*-demo-01` 公钥，不能作为真实 staging 安装包。
- 不能直接原地重跑现有打包脚本，因为它会覆盖已经发布并固定哈希的 0.5.0 更新 ZIP。
- staging bootstrap 的制作和 Windows 安装属于板块 5；板块 4 只能准备其配置和进入条件，不提前执行板块 5。
- Worker 数据库中的 `published_at` 当前表示登记时间，签名 manifest 中的 `published_at` 表示发布元数据时间；两者不同是当前实现行为，验收报告需明确记录。

### 当前执行点

板块 4 独立计划已于 2026-08-05 20:01 +08:00 获得用户批准：

`docs/superpowers/plans/2026-08-05-board-4-test-license-and-release.md`

Task 1“冻结板块边界并保存基线”已完成，证据如下：

- 功能代码基线：`e36ab47d27bbff7360cbfc1a9038d47e9e18ce48`；后续外部记忆治理只产生文档提交，未改变功能代码
- 发布仓库提交：`2b9fa385b86df83f7968239a1029d4d59f020027`
- staging Worker 版本：`04a61d9a-d513-4484-83af-e926dbe835f3`
- D1 无待执行迁移，8 个预期 Secret 名称全部存在
- Worker 中 `rel_staging_050` 恰好一条，GitHub 中 `v0.5.0` Draft 恰好一个
- GitHub 三个资产状态均为 `uploaded`，ID 与固定发布证据一致
- 发布仓库干净；源码仓库仅有本次外部记忆文档尚未提交
- 仓库外安全目录文件和 ACL 正常，管理员明文令牌已删除

Task 2 已完成，证据如下：

- 创建时间：`2026-08-08T09:07:57.146Z`（本地 +08:00 为 17:07:57）
- D1 只读核验确认该许可证记录数恰好为 1
- License ID：`lic_ptrqZVAxh2NI8h5RM6gnGiiL`
- Hint：`JD25`
- 状态：`active`
- 通道：`stable`
- 最大设备数：3
- 明文许可证文件和非敏感 metadata 文件均位于仓库外安全目录，ACL 仅允许当前用户、SYSTEM 和管理员组
- 仓库和当前外部记忆未发现完整许可证、Token、管理员令牌或私钥泄露

Task 3 已于 2026-08-08 完成真实 staging 验收。用户在本机终端运行专用 headless 工具后返回 `ok=true`；第 1/2/3 台设备激活成功，第 4 台首次激活稳定返回 `DEVICE_LIMIT_REACHED`，在线 validate、设备列表、重命名、解绑和重新激活均成功。随后 D1 只读核验确认共有 4 条历史设备记录，其中 3 条 `active`、1 条 `unbound`，设备 2 的 `STAGING-ACCEPTANCE-RENAMED` 名称和设备 3 的解绑时间均已持久化。

### 状态

**已完成。**

## 7. 板块 5：Windows 真实端到端验收

### 原始目标

在一台或多台 Windows 测试机上完成：

1. 安装 staging bootstrap；
2. 输入许可证激活；
3. 启动应用；
4. 检查并下载 0.5.1；
5. 重启后自动安装；
6. 验证健康检查成功；
7. 制造一个损坏版本；
8. 验证自动回滚到上一版本；
9. 验证断网七天规则。

### 进入条件

- 板块 4 全部完成并有验收报告；
- staging 专用 bootstrap 设计与制作计划获得批准；
- 0.5.0 和 0.5.1 私有 Release 状态、哈希和公钥全部确认；
- 测试许可证与设备状态可控且可清理。

### 状态

**当前状态：Board 5 accepted complete。** stable 0.5.0→0.5.1、Offline acceptance、beta fault lifecycle、process-tree TDD repair、fresh RollbackRepairSandbox re-acceptance、version-level suppression、final fault disable、Cloud Cleanup Gate 与 fresh final verification 均已有真实证据。历史上的 private GitHub Draft visibility blocker 与第一次 rollback orphan-process failure 都已作为保留证据记录，并分别通过 private release/prerelease visibility 修复与 `29aba6b` process-tree TDD repair 后的 fresh sandbox 重验关闭。Cloud cleanup 最终状态：stable/beta 两张 Board 5 license 均 `revoked` / revision 2 / active devices 0，两个关联 Board 5 test device 均 `unbound`；JD25 与 050/051 未变，fault 保持 disabled/paused。最终报告为 `docs/deployment/2026-08-12-board-5-windows-e2e-report.md`。Board 6 已进入进行中状态；B6-G0、B6-G1、B6-G2、B6-G3、B6-G4 均已完成，B6-G5 staging behavior acceptance 也已 accepted complete；B6-G6 Phase A provider-neutral readiness repair/research 已本地完成。经 2026-08-14 用户批准的 Private / Controlled Distribution scope amendment，real commercial Authenticode 已明确 deferred，不再是当前上线/closure blocker；B6-G7 现为 next mandatory gate，B6-G8 未进入，Board 7 未开始。

正式设计：`docs/superpowers/specs/2026-08-09-board-5-windows-staging-e2e-design.md`

正式实施计划：`docs/superpowers/plans/2026-08-09-board-5-windows-staging-e2e.md`

冻结执行边界：

- Board 4 完成快照保持 `task5/0.5.1-update-validation@8c7464f`，不再写入 Board 5 内容；
- Board 5 branch 为 `board5/windows-staging-e2e`，基于 `8c7464f`；
- 临时 0.5.0 build-source worktree detached 在 `a579a25cb7f16e6fdf88d618252b4a5cbffef53d`；
- stable 与 beta Board 5 许可证必须分离，rollback 不得利用现有 channel trust-boundary 缺口；
- RollbackSandbox 不得手工编辑 `current.json`，只能走 `CurrentVersion` / `InstallLayout` 正式状态逻辑；
- failed-version 服务端 suppression 只能按当前实现描述为 version-level，不能描述为 manifest-hash-level；
- Local implementation gate 已完成：`ad753f6`（共享 acceptance boundaries）、`28415ca`（bootstrap-only/external-output）、`538ae3a`（staging acceptance tools）；前置 docs 边界修订为 `c9ec842`。
- Bootstrap build gate 已完成：在明确补充授权后安装 `pywebview 6.2.1`；WebView2 Runtime 只读检测为 `151.0.4129.72`；build-source 保持 detached `a579a25cb7f16e6fdf88d618252b4a5cbffef53d`，构建时 `WECHAT_CLI_BUILD_ID` 未设置。真实 app `wechat-cli.exe` size/SHA-256=`14484577` / `fe70396252d4cab1cf355e34bb7479233ba2fd1d0ba1866132ab9e0c9f19f971`，Launcher `wechat-cli-launcher.exe` size/SHA-256=`20153234` / `f45d3bb655193e74f433edd38a50dfbdf7b96a3820ad5929a37405d48bb49df1`。staging launcher config SHA-256=`5002d155f3968a0d44a20b070e1b28ce569497b88d9748ba8a606b0201395e9d`，safe fields 为 stable / port 18787 / `release-key-staging-01` / `lease-key-staging-01`。bootstrap ZIP size/SHA-256=`34192856` / `5985fc2e835ab7e45da227f2d62770bc248ecf09525b511fa76e3bf3ae082d8d`；ZIP 内 app/Launcher/config hash 与 build-source/package directory 完全一致。package manifest build label=`0.5.0-local-20260805.1`，冻结 runtime contract 单独观察为 `status=ok`、`product=wechat-cli-web`、`version=0.5.0`、`build_id=dev`。因 `verify_windows_bootstrap.py` 会真实 install/reinstall/uninstall，本 gate 明确未运行该 verifier，也未执行任何 installer。
- Stable license creation gate 已完成：创建恰好 1 张 Board 5 stable staging license，ID `lic_NGcs-flk8nRqfkbm5TFqewHV`、hint `9C4A`、status `active`、`maximum_devices=1`。完整 key 仅保存在仓库外受限文件 `staging-secrets-20260805/board5/board5-stable-license-01.csv`；非敏感 metadata 保存于相邻 `.metadata.json`；两文件 ACL 仅当前用户、SYSTEM、Administrators。创建审计 action=`license.batch_create`，request ID=`28e0e326-805d-4bff-add0-ab25fcc43400`。
- Isolated bootstrap install/activation gate 已完成：使用 child-only `LOCALAPPDATA/APPDATA/USERPROFILE/HOME/TEMP/TMP` 与 `-NoStart -NoShortcuts -SkipProcessStop -SkipWebView2Check` 安装到 `board5-windows-e2e/stable`；`current.json` 为 0.5.0/stable，0.5.0 app hash 仍为 `fe70396252d4cab1cf355e34bb7479233ba2fd1d0ba1866132ab9e0c9f19f971`。验收期间验证了两个 Launcher UI defect：Windows `file:` URL 归一化错误（Board 5 commit `56d065e`）与 pywebview `before_load` 中调用 loaded-gated public URL API 导致约 20 秒 deadlock/self-destroy（`706bcbe`）。用户完成真实 UI 激活后，DPAPI state 为 `WCLIC1` envelope 且非明文 JSON；lease key=`lease-key-staging-01`、active、duration=604800 秒。两个旧 Task 5 0.5.1 orphan servers 经单独授权和 PID/path reuse 防护后被停止，随后真实 `/api/health` 精确为 0.5.0/dev/ok 且 `license_session_valid=true`；Worker readback 为 stable license active devices 1/1，device active，app 0.5.0 / Launcher 0.1.0。
- Stable real E2E gate 已获授权并执行到 download path：`rel_staging_051` 与 GitHub Draft/asset 映射 read-only preflight 完全匹配冻结值。Live acceptance 首先暴露 frozen downloader 缺少项目 User-Agent，以及 Worker `redirect:"follow"` 会跨域携带 GitHub Authorization；TDD hotfix 为 `a771ab4` 与 `8a1fdb0`。`a771ab4` 已镜像到 frozen 0.5.0 hotfix source `a579a25 → 6753a24 → 143c93c → 0dd2485`，仅重建隔离 Launcher，size/SHA-256=`20152588` / `83c698d120f429ab8d29bbcb8981e25b927a95cecd895d53259dadd65dcebdcd`，0.5.0 app hash 未变。
- Credential remediation gate 已完成：用户创建的 dedicated fine-grained PAT 限定 `AuRevior-ai/wechat-cli-releases`，并在本机安全验证中得到 `TOKEN_OK`；随后手动写入 staging `GITHUB_RELEASE_READ_TOKEN`。Cloudflare Secret Change Version ID=`1b9d5988-7ac4-47c4-b9f5-ab435bd4d4ea`。Worker diagnostic commits `c4d44ee` / `fc667cf` 只暴露 GitHub upstream HTTP status，不记录 URL/header/token。凭据修复前 upstream=401；有效 token 写入后，同一真实 updater path 到达 GitHub 并返回 upstream=403。Live GitHub readback确认 Release ID `367353041` / `v0.5.1` 仍 `draft=true`、`prerelease=false`，三项 package/manifest/signature asset ID/size/state 全部未漂移。GitHub 文档同时规定 release asset GET 支持 fine-grained `Contents: read`，但 Draft Release 仅对拥有 push access 的用户可见，因此当前 403 与 Draft/read-only 可见性冲突一致。
- Private Draft publish gate 与 stable E2E 均已完成：`v0.5.1` / Release ID `367353041` 已按授权改为 `draft=false`、`prerelease=false`、`make_latest=false`，`refs/tags/v0.5.1` 指向 release-repository commit `2b9fa385b86df83f7968239a1029d4d59f020027`；三项 asset ID/size/digest 均未漂移。`52e07b8` range probe 返回 HTTP 206、exactly one byte、`Content-Range: bytes 0-0/14268929`。真实 0.5.0 `/api/update/check` 启动 installed Launcher 后，旧 0.5.0 PID 在下载全过程保持存活；缓存 ZIP size/SHA-256=`14268929` / `0ddbb0b402cc9d98ed001391c1a618527d165e328a1f4f1534d80e6b984956c0`，manifest SHA-256=`be111f0a786821319fb96f82f1748b4a75003b7c5fb296c48ec87b3355a3fd62` 并通过 `release-key-staging-01` 验签；解包 EXE size/SHA-256=`14483951` / `dbbdf8ec70ddcf8d36145f099b0cb4ce3292c61e205c3ac7ae4db01fbc8907d1` 且 `--version` 为 0.5.1。经 exact PID/path/cmd preflight 后仅停止旧 0.5.0，installed Launcher 在 child-only Board 5 环境中启动一次并正式提交事务；最终 health=`0.5.1/staging-051-20260808.1/ok` 且 license session valid，`current.json` current=0.5.1 / previous=0.5.0 / manifest SHA 精确匹配，pending 清除、transaction committed、0.5.0 与 0.5.1 两目录均存在。最终 reconcile 确认 Worker `rel_staging_050/051` 未漂移，GitHub `v0.5.0` 仍原 Draft，`v0.5.1` 只有已授权的 publish/tag 变化。
- Task 6 Part A Offline acceptance 已完成：新的 marked `board5-windows-e2e/offline` root 复制成功 stable 0.5.1 install/user state，排除 `runtime/cache/logs`；唯一 copy anomaly 是 Windows `Content.IE5` reparse/system 目录，所有 23 个 non-reparse UserProfile files 逐项一致。受控工具生成的 `launcher-config.offline.json` SHA-256=`00502225f67e0f4be1fe255942b17ca73ff6e1625fbc0f522ad136fc5a60abcc`，仅 API authority 改为 unused `https://127.0.0.1:65534`，channel/port/fingerprint salt/release keys/lease keys 与 stable config 完全一致。为保持相同 port 18787，先精确识别并临时停止 stable 0.5.1 PyInstaller parent/child tree；real OfflineSandbox Launcher 成功启动 copied 0.5.1，health=`0.5.1/staging-051-20260808.1/ok`、license session valid，`/api/license`=`offline_valid`/authorized。`board5_offline_acceptance.py` 对同一 DPAPI state 验证 duration=604800、`offline_until-1s` valid、`+1s` expired、4-minute correction allowed、10-minute rollback=`OFFLINE_LEASE_DENIED`；未修改系统时间。随后 OfflineSandbox process tree 被停止，原 stable Launcher 已恢复并再次验证 listener/health 来自 stable 0.5.1。OfflineSandbox 保留为证据，未 cleanup。
- Task 6 Part B beta-license creation gate 已完成：preflight 只读确认 staging 当前无 beta license，目标 `board5-beta-license-01.csv` 与相邻 metadata 均不存在。一次 `batch-create --count 1 --maximum-devices 1 --channel beta` 创建 ID `lic_XUMv4Qor5S1WXr-lWOTd9L1m`、hint `WYW2`、status active、active devices 0；D1 `license.batch_create` audit result=`success`，request ID=`be22ec6c-d222-4a69-bda1-6750c592b4f5`，metadata count=1 / maximum_devices=1 / release_channel=beta，read-only audit query `rows_written=0`。完整 key 仅在仓库外 `staging-secrets-20260805/board5/board5-beta-license-01.csv`；相邻 `.metadata.json` 仅含 safe fields，两文件 `icacls` 只保留当前用户、SYSTEM、Administrators。
- RollbackSandbox beta preparation/activation gate 已完成：新的 marked `board5-windows-e2e/rollback` root 中，`board5_prepare_sandbox.py` 从成功 stable 0.5.1 install 复制 RollbackSandbox，同时排除 `runtime/`、`cache/` 与 `state/license-state.dat`；随后仅通过 `CurrentVersion` + `InstallLayout.save_current()` 将 channel stable→beta，current `0.5.1`、previous `0.5.0` 与 manifest SHA 均保持冻结值。真实 Launcher GUI 激活 `WYW2` 后生成独立 DPAPI state；RollbackSandbox health=`0.5.1/staging-051-20260808.1/ok`、license session valid，local license state authorized/channel beta。Worker/Admin readback 确认 beta license active devices=1，device active，last app `0.5.1` / Launcher `0.1.0`；D1 `device.activate` / `device.validate` success request IDs=`ac579b8c-7d6d-4338-8aa4-6896f56fa21e` / `04539bdc-cc50-4081-bc3a-e7b10793f505`，read-only query `rows_written=0`。未记录完整 device ID/token。验证后 RollbackSandbox process tree 已停止但 DPAPI state 保留，原 stable 0.5.1 已恢复并重新通过 health/session。
- Task 6 Part C local fault package preparation gate 已完成：使用冻结 0.5.1 EXE 原字节（size/SHA-256=`14483951` / `dbbdf8ec70ddcf8d36145f099b0cb4ce3292c61e205c3ac7ae4db01fbc8907d1`）生成 repo-external `wechat-cli-app-0.5.2-board5bad.1-win-x64.zip`，fault ZIP size/SHA-256=`14268937` / `96111ad0fff5827a93e81d826de150ea616eb4c907b20ada9a420967f8ffaf82`，成员恰好 `app-manifest.json` 与 `wechat-cli.exe`；内部 EXE hash/size 与冻结 0.5.1 完全一致，app manifest 仅声明 candidate `0.5.2-board5bad.1`、build ID 仍为 `staging-051-20260808.1`。现有 release prepare 路径本地生成 beta `rel_board5_bad_052_01`，signed manifest size/SHA-256=`957` / `2d29da32cb05e1a373ddab58725f2810e1d81489ad769a0ed6094458eb71fdaa`，signature size=`64`，published_at=`2026-08-11T12:41:00Z`，minimum app=`0.5.1`、minimum Launcher=`0.1.0`、rollout=100、signing key=`release-key-staging-01`。独立只使用 repo-external public-key registry 验证 raw manifest signature、package hash/size 和 app 0.5.1 / Launcher 0.1.0 target compatibility 全部通过；三个本地产物继承 ACL 仅当前用户、SYSTEM、Administrators。此 gate 未执行 GitHub/Worker 写入，也未启动 RollbackSandbox fault update。随后 Step 9 只读 preflight 确认 release repo clean@`2b9fa385b86df83f7968239a1029d4d59f020027`、GitHub `refs/tags/v0.5.2-board5bad.1` 明确 404、D1 `rel_board5_bad_052_01` 不存在，且 `rel_staging_050/051` hash/size/rollout/enabled/paused 均保持冻结值，查询 `rows_written=0`。
- Task 6 Part C fault publish/register gate 已完成：唯一一次现有 publisher 调用未带 `--enable`，创建 private GitHub Draft Release ID `368572125`，tag_name=`v0.5.2-board5bad.1`、`draft=true`、`prerelease=true`、target=`main`。三个 asset 均与冻结本地产物逐字节一致：package ID `510139118` / size `14268937` / SHA-256 `96111ad0fff5827a93e81d826de150ea616eb4c907b20ada9a420967f8ffaf82`；manifest ID `510139294` / size `957` / SHA-256 `2d29da32cb05e1a373ddab58725f2810e1d81489ad769a0ed6094458eb71fdaa`；signature ID `510139303` / size `64` / SHA-256 `912b457f0149cdcc0d33ad46f4c937bf2fd6a042e2a13cb5ad5002081ae48a58`。Draft 未创建真实 Git ref，`refs/tags/v0.5.2-board5bad.1` 后验仍 404。D1 `rel_board5_bad_052_01` 为 version `0.5.2-board5bad.1`、channel beta、rollout 100、`enabled=0`、`paused=1`，GitHub Release/package Asset mapping 与上述 ID 一致；`release.register` audit success request ID=`354aa751-d019-4931-a5f3-23208af084d0`。后验只读 D1 `rows_written=0`，`rel_staging_050/051` 未漂移，release repo 仍 clean。未执行 enable、RollbackSandbox fault update、Draft publish、真实 tag 创建、production、push、merge 或 cleanup。
- Task 6 Part C fault-enable gate 已完成：fresh preflight 确认 `rel_board5_bad_052_01` 为 beta / rollout 100 / `enabled=0` / `paused=1`，且 `rel_staging_050/051` 未漂移；随后唯一一次 `releases enable rel_board5_bad_052_01` 仅将 fault row 改为 `enabled=1`、`paused=0`，rollout、manifest/package hashes、size 与 GitHub mapping 均未变化。D1 `release.update` audit success request ID=`315bdfca-04b0-4745-96ee-c545ecd55fd3`，metadata 仅 `enabled=true` / `paused=false`，后验只读查询 `rows_written=0`。GitHub fault Draft Release ID `368572125` 仍 `draft=true` / `prerelease=true`，三项 asset ID/size/digest 不变，真实 `refs/tags/v0.5.2-board5bad.1` 仍 404；stable 050/051 继续 enabled/unpaused、rollout 100。RollbackSandbox 未启动，stable 0.5.1 health/session fresh 通过。
- Task 6 Part C rollback-acceptance preflight 已获授权但第一次 fail-closed 停止：从保留的 RollbackSandbox DPAPI/beta state 使用生产 `UpdateApiClient` 做只读 update check，精确返回 `rel_board5_bad_052_01` / `0.5.2-board5bad.1`、package size `14268937`、SHA-256 `96111ad0fff5827a93e81d826de150ea616eb4c907b20ada9a420967f8ffaf82`，`failed_versions=[]`，证明 beta license/channel/selection 正确。随后 1-byte Worker download 返回 outer HTTP 502 / `DOWNLOAD_UPSTREAM_FAILED` / safe `upstream_status=403`；同一 Worker boundary 对 published `rel_staging_051` 返回 206，因此 blocker 被收敛为 private Draft asset visibility。
- fault private-prerelease publish + real rollback checkpoint：在独立 publish 授权下，Release ID `368572125` 仅改为 `draft=false` / `prerelease=true` / `make_latest=false`，真实 tag `v0.5.2-board5bad.1` 创建在 `2b9fa385b86df83f7968239a1029d4d59f020027`，三项冻结 asset 未变化；post-publish Worker one-byte probe 返回 HTTP 206 / `bytes 0-0/14268937`。随后真实 `--download-update` 成功准备 fault package，current 仍为 0.5.1/beta；candidate EXE `--version` 仍报告 0.5.1。真实 `--apply-update` 产生 from=0.5.1、to=`0.5.2-board5bad.1`、state=`rolled_back` 的 transaction，failure reason=`application health version does not match the update`，current 恢复 0.5.1，failed registry 记录 candidate。真实验收仍失败：candidate PyInstaller child 在 Popen parent 退出后成为 orphan 并继续持有 18787，restored 0.5.1 child 未取得监听端口，health 实际来自残留 candidate path 且 session invalid。根因已收敛到 `ApplicationProcessManager.stop()` 仅终止 Popen parent、缺少 Windows process-tree/port-release contract，以及 `LauncherService.start()` 对 candidate-stop failure 的静默容忍。异常 RollbackSandbox app 已精确停止，stable 已通过生产 Launcher service path 恢复，当前 listener/path/health 为 stable 0.5.1 / `staging-051-20260808.1` / ok / session valid。
- Windows process-tree repair + fresh rollback re-acceptance checkpoint：修复 commit `29aba6bc0c8469dc8b5dc512d6831c5385246431` 以 TDD 增加 Windows `taskkill.exe /PID <pid> /T /F` process-tree termination、bounded loopback port-release verification，以及 candidate stop failure 时 pointer/failed-registry 回滚但不启动 previous app 的 fail-closed orchestration。RED 新测试先在旧实现上按预期失败；GREEN 验证为 launcher/update focused 28/28、Windows packaging 31/31、Python full suite 529 run / 2 expected skips / 0 failures。修复版 Launcher size/SHA-256=`20168420` / `a9ae3633f96d08880f1ab4a2e45c946a5d9733a9dd2ed12eabb11acf4c1d1ef7`。新的 marked repo-external `board5-windows-e2e/rollback-repair` 从 successful stable 0.5.1 创建，只复用现有 beta DPAPI state 并换入修复 Launcher，未继承旧 failed/pending/candidate/transaction failure state。fresh beta preflight 仍选中 `rel_board5_bad_052_01`，one-byte Worker probe=206 / `bytes 0-0/14268937`；full download 的 ZIP/manifest/candidate hashes 均匹配冻结值。真实 repaired `--apply-update` 产生 transaction `txn_iHrMsmmUllLYh7u6pp079U2e`，state=`rolled_back`，failure reason=`application health check timed out: application health version does not match the update`；current 恢复 0.5.1，post-rollback candidate process count=0，sole 18787 listener 属于 repair `versions/0.5.1/wechat-cli.exe`，health=`0.5.1/staging-051-20260808.1/ok` 且 session valid。local failed registry 精确记录 `0.5.2-board5bad.1|2d29da32cb05e1a373ddab58725f2810e1d81489ad769a0ed6094458eb71fdaa`；同一 beta sandbox 随后发送 `failed_versions=["0.5.2-board5bad.1"]`，Worker 返回 no update / no manifest，证据准确表述为 **version-level server suppression**，而本地 registry 仍为 version + manifest hash。repair 进程随后全部停止且证据保留，stable 0.5.1 已恢复，fresh sole listener/path/health/session 再次通过。
- Final fault-disable checkpoint：fresh preflight 再次确认 `rel_board5_bad_052_01` 为 beta / rollout 100 / `enabled=true` / `paused=false`，stable 050/051、GitHub private prerelease/tag/assets 与 stable health 均未漂移。由于 Admin CLI 的 `disable` 与 `pause` 是两个独立 mutation，本 gate 没有串行调用两个子命令，而是直接复用既有 `AdminApiClient.update_release()` 发出唯一一次 PATCH，同时提交 `enabled=false` 与 `paused=true`，不提交 rollout 字段。Post-write readback 为 fault `enabled=false` / `paused=true` / rollout 100；stable 050/051 完全未变，GitHub Release ID `368572125` 仍 private prerelease、tag/三个 assets 未变，repair sandbox process count=0，stable health=`0.5.1/staging-051-20260808.1/ok` / session valid。Admin response 不返回 request ID；额外 D1 audit read 因当前非交互 Wrangler shell 未加载 `CLOUDFLARE_API_TOKEN` 而 fail closed，未读取或扩展任何 credential。

## 8. 板块 6：安全与正式交付准备

### 原始目标

- 准备 Windows 代码签名证书；
- 为 Launcher、应用和安装器签名；
- 将长期管理员 Token 升级为短期登录机制；
- 限制 Worker CORS、速率和管理员权限；
- 配置密钥轮换和备份流程；
- 确定国内域名、备案和访问方案；
- 制定诊断数据保留与删除策略。

代码签名和备案不影响本地 Demo，但正式交付前必须完成。

### Board 5 → Board 6 risk handoff（已纳入 approved design；B6-G0/B6-G1 本地 gate 已完成，后续 staging acceptance 仍独立 gated）

1. **Update channel trust boundary**：Worker `/v1/updates/check` 当前未强制 `license.release_channel == request.channel`。Board 5 通过 stable license/stable channel 与 beta license/beta channel 显式对齐，没有利用该缺口。
2. **Failed-version suppression granularity**：本地 failed registry key 是 `version + manifest_sha256`，但发给 Worker 的 `failed_versions` 只有 version；真实 Board 5 证据只能证明 **version-level server suppression**，不是 manifest-hash-level suppression。
3. **GitHub Release visibility semantics**：真实 E2E 证明 private GitHub Draft asset 无法满足当前 updater 下载链；`v0.5.1` 与 fault candidate 都需要从 Draft 转为 published private release/prerelease 后才能真实分发。Board 6 必须定义 staging/prod visibility policy、Draft 与 published private Release 的职责、tag creation timing 与 `make_latest` policy。
4. **GitHub release read credential**：staging 当前使用 dedicated fine-grained PAT `GITHUB_RELEASE_READ_TOKEN`。Board 6 必须审查生命周期、最小权限、rotation、backup/recovery、production replacement，以及是否继续采用长期 PAT；文档不得记录真实 token。
5. **Worker redirect trust boundary**：`fetchGithubReleaseAsset()` 已限制 initial URL 为 `https://api.github.com`、manual redirect，并在 redirect 时移除 Authorization，避免 credential leak；但 redirect target 当前只要求 HTTPS，Board 6 security review 需判断是否进一步收紧到明确的 GitHub asset/CDN host allowlist。
6. **Packaging production dependency**：`scripts/package_windows_app.py` 当前直接 import `scripts.board5_common.assert_outside_repository`，形成通用 packaging script 对 Board 5 acceptance helper 的产品路径依赖。Board 6 / integration 前应评估是否提取通用 packaging/path utility。
7. **pywebview backend API dependency**：Board 5 hotfix `LauncherWindow._current_url_before_load()` 使用 `window.gui.get_current_url(uid)` 避免 `before_load` 阶段 public API deadlock；真实 Windows 已验证有效，但依赖 pywebview internal/backend API。Board 6 应评估版本锁定与 integration coverage。
8. **Source integration debt**：main 仍冻结在 `a579a25`，Board 5 branch 已积累真实产品修复，包括 `56d065e`、`706bcbe`、`a771ab4`、`8a1fdb0`、`29aba6b` 及相关 Worker/packaging changes，均未 push/merge。Board 6 开始前必须有独立 integration strategy；当前不得 merge/push。

### 当前 Board 6 canonical 状态

- branch：`board6/security-delivery-preparation`
- frozen main base：`a579a25cb7f16e6fdf88d618252b4a5cbffef53d`
- Board 5 accepted-complete evidence：`67d3dec0fd1c4a02c87be1ab79c4f78ea63f49d6`
- B6-G0：**complete**，source integration 与 generic packaging boundary cleanup 已完成至 `c1d045895a044dbb4c9998a787c77775654074fa`
- B6-G1：**complete**，Task 2/3/4 本地实现完成至 `bdc98afc0d945c4c86f1e3b21686d2fe798ccdd1`；fresh verification = Python 510 / 2 skips / 0 failures + Worker typecheck + Vitest 40/40
- B6-G2：**complete**，Task 5–8 本地实现完成至 `e0c91df`；fresh verification = Python 524 / 2 skips / 0 failures + Worker typecheck + Vitest 89/89；未执行 Access/staging/真实 Secret mutation
- B6-G3：**complete**，Task 9–13 本地实现完成至 `1a07447`，pre-staging audit=`d73cf3f`；fresh verification = Python 607 / 2 skips / 0 failures + Worker typecheck + Vitest 89/89；未执行真实签名或 staging/cloud/production mutation
- B6-G4：**complete**；staging infrastructure report=`docs/superpowers/governance/2026-08-14-board-6-staging-infrastructure-gate.md`；Worker Version=`14a19ea3-5a96-408b-a4e3-0a8d8e4ebe2c`；R2/D1/Secret/Access/custom-domain/deploy reconcile PASS
- B6-G5：**accepted complete**；report=`docs/superpowers/governance/2026-08-14-board-6-staging-behavior-acceptance.md`；current staging Worker Version=`6f2aad56-12cb-4d8e-8af5-9dceefbe1a49`，fresh health=200/staging；G5 release terminal state=disabled/paused，stable/beta disposable licenses 均 revoked，diagnostics=`deleted`，G5 admin sessions/principal 均 revoked 且 active sessions=0；GitHub prerelease/tag 与 exact R2 package 作为 immutable acceptance evidence 保留；两条历史 disposable device row 仍显示 active，但 parent licenses 已 revoked，row-level cleanup residual 已明确记录且不是活跃授权路径
- B6-G6 Phase A：**provider-neutral readiness repair + provider research complete locally；real commercial signing 本身未完成，并已按用户批准的 Private / Controlled Distribution scope 明确 deferred**。readiness evidence=`docs/superpowers/governance/2026-08-14-board-6-code-signing-entry-readiness.md`；provider research=`docs/superpowers/governance/2026-08-14-board-6-code-signing-provider-decision.md`；scope amendment=`docs/superpowers/specs/2026-08-14-board-6-private-distribution-profile-design-amendment.md`。`9f4ad0f` 已修复 deterministic inspector；`e9cb67b` 已扩展 public signer/timestamp-presence evidence；`50e7074` 新增 dormant optional SSL.com adapter，但未配置 provider/account、未做 KYC/payment、未 provision key、未修改 publisher policy、未实际签名。`ebd3378` 进一步实现 explicit schema-v2 `distribution_profile=private_controlled|public_formal`：legacy schema-v1 production 仍强制 publisher，schema-v2 private production 可显式使用空 publisher，mutable external config 不能覆写 distribution profile。fresh amendment verification=Python 646 / 2 skips / 0 failures + Worker typecheck + Vitest 92/92；existing staging trust profile read-only 仍为 schema v1 / legacy / staging / stable / empty publisher，未发生 mutation。当前 profile 明确使用空 `windows_publisher_policy`；远程更新继续依赖 Ed25519 manifest + exact package SHA-256/size + server-authoritative eligibility + safe extraction/rollback/suppression。commercial Authenticode 仅作为未来 Public / Formal Distribution hardening。
- B6-G7：**not entered**；任何 staging key/Secret add/switch/retire 仍需独立 rotation gate。
- B6-G8：**not entered**；Board 6 final closure/report 尚未执行。
- Board 7：**unstarted**；production provisioning/deployment/cutover 仍未授权。
- approved design：`docs/superpowers/specs/2026-08-12-board-6-security-delivery-preparation-design.md`
- approved implementation plan：`docs/superpowers/plans/2026-08-12-board-6-security-delivery-preparation.md`
- source-integration provenance：`docs/superpowers/governance/2026-08-12-board-6-source-integration-provenance.md`
- private distribution design amendment：`docs/superpowers/specs/2026-08-14-board-6-private-distribution-profile-design-amendment.md`
- private distribution plan amendment：`docs/superpowers/plans/2026-08-14-board-6-private-distribution-profile-amendment.md`

B6-G0 已选择性集成审核后的 Board 5 product lineage，未 wholesale merge Board 5 acceptance tooling；D1 generic packaging dependency 已在 `c1d0458` 通过 `scripts/packaging_paths.py` 收口。B6-G1 随后本地关闭 A-domain update trust：Worker 以 authenticated license channel 为 authority；Launcher/Worker 支持 exact `(version, manifest_sha256)` failure identity 且保留 bounded legacy compatibility；同一 channel/version 的 manifest replacement 被拒绝；R2 distribution schema/backend、server-generated object key、exact SHA/size/readiness、Range 206、production GitHub-runtime rejection 与 corrected lifecycle `GitHub Draft inspection -> R2 readiness -> immutable provenance -> disabled/paused registration -> separate enable` 已通过本地测试。B6-G2 又在本地关闭 B-domain 基础实现：Access JWT 使用 RS256/JWKS/issuer/audience/signature/time claims 完整校验；Admin 采用两分钟 one-time code + 30 分钟 `wcas` session，production legacy token 默认关闭且 break-glass 有硬到期与审计；Origin deny/CORS、read/write/high-risk rate class 与十分钟 recent-auth 统一进入中央 policy；diagnostics 明确 consent v1、15 分钟 upload TTL、最长 7 天 cloud retention、opaque R2 metadata 与显式本地删除；license/device/admin-session/contact lookup/download ticket/diagnostic upload/rate-limit 采用 purpose-separated versioned secret selector，release/lease signing public-key overlap/retirement 也有测试。`wrangler.jsonc` 仅记录 version selector，不包含 `_V1` Secret value；B6-G4 已完成七项 staging `_V1` Secret provision/migration，并保留 legacy compatibility names，G5 live acceptance 已在该 fail-closed versioned-secret 配置上完成。Board 6 design/plan 的 approved seed SHA 继续冻结；Board 5 worktree 中原有两份 untracked Board 6 seed 文档继续保留，未经独立 cleanup authorization 不删除。

### 状态

**进行中；B6-G0 complete，B6-G1 complete，B6-G2 complete，B6-G3 complete，B6-G4 complete，B6-G5 accepted complete；B6-G6 Phase A complete；当前 distribution profile=Private / Controlled Distribution；commercial Authenticode deferred optional，不是上线/closure blocker；B6-G7 为 next mandatory gate，B6-G8 not entered；Board 7 unstarted。**

## 9. 板块 7：自动化发布与正式上线

### 原始目标

将本地流程迁移到 GitHub Actions，并建立 production 资源：

- 自动运行测试；
- 自动构建两个 EXE；
- 自动生成更新 ZIP；
- 自动签署 manifest；
- 自动创建私有 GitHub Release；
- 自动注册 Worker 发布；
- 人工确认后启用发布；
- 支持暂停、分批发布和回滚；
- 建立 production D1、R2、Worker 和正式域名。

### 进入条件

- 板块 6 完成；
- 生产资源、域名、凭据和安全方案分别取得明确批准；若届时启用 Public / Formal Distribution，再单独取得商业代码签名批准；
- staging 的真实更新和真实回滚均有独立验收证据。

### 状态

**未开始。**

## 10. 当前下一步

Task 1、Task 2、Task 3 已完成。Task 4 的真实租约/验签/时钟半段也已完成：

1. 用户执行获批的 `scripts/staging_lease_acceptance.py` 后返回 `ok=true`；
2. `lease-key-staging-01` 独立 Ed25519 验签成功；
3. 租约与许可证/设备绑定正确，`duration_seconds=604800`，`offline_until` 比 `issued_at` 精确晚 7 天；
4. `offline_valid`、`offline_expiring`、`offline_expired` 和明显时钟回拨 `OFFLINE_LEASE_DENIED` 均符合预期；
5. D1 只读核验确认设备 1 与许可证仍为 `active`，`last_validated_at=2026-08-08T09:56:21.830Z`；
6. 本次新增审计 request ID：`device.activate` = `72c1d50b-5542-4b9b-a7f9-ade395e80833`，`device.validate` = `ac834a2a-a5df-43cb-9b4d-ef82de2158c0`。

Task 4 已完成真实 staging 在线优先策略验收。用户执行获批的 `scripts/staging_license_status_acceptance.py` 后返回 `ok=true`、`suspended_rejection_code=LICENSE_SUSPENDED`、`restore_succeeded=true`、`restored_validation_ok=true`。随后 D1 只读核验确认许可证最终为 `active`、revision=3、`suspended_at=NULL`、`revoked_at=NULL`，设备 1 仍为 `active` 且恢复后 `last_validated_at=2026-08-08T10:23:26.931Z`。状态审计 request ID：`license.suspended` = `24f68caa-2b83-42dc-90d5-d35df4153911`；`license.active` = `ba926744-e8c6-4512-92de-5767b6ede9e0`；恢复后的 `device.validate` = `dc2198d3-be66-4abc-a239-4e384a9d3a65`。暂停期间在线 validate 在活动许可证检查处被 `LICENSE_SUSPENDED` 拒绝，因此不会产生成功 `device.validate` 审计，这与 Worker 当前实现一致。吊销继续推迟，以保留后续 0.5.1 和板块 5 的测试许可证。

Task 3/4 冻结前最终验证已于 2026-08-08 重新执行：Python 全量 476 项运行、474 通过、2 项跳过；Worker `npm run typecheck` 通过，Vitest 3 个文件/17 项测试全部通过；`git diff --check` 通过；针对待提交 Task 3/4 文件与 Task 5 计划的敏感值形态扫描为 0 命中；发布仓库工作树干净。随后只读 D1 再次确认许可证最终 `active`、revision=3、`suspended_at=NULL`、`revoked_at=NULL`，历史设备 4 条（3 active、1 unbound），设备 1 仍 active，三条 Task 4 审计 request ID 与记录一致，所有查询 `rows_written=0`。

Task 5 brainstorming 已完成并批准：0.5.1 仅用于更新链路验证；Launcher 保持 0.1.0 且不重建；`npm/scripts/build.py` 增加 app-only 目标，`scripts/package_windows_app.py` 增加 update-only 模式；不制作 staging bootstrap，不覆盖 0.5.0 固定 ZIP；默认 BUILD_ID 固定为 `staging-051-20260808.1`，同时保留 `WECHAT_CLI_BUILD_ID` 显式覆盖；Task 5 不创建、上传、登记或启用 0.5.1 Release。详细实施子计划见 `docs/superpowers/plans/2026-08-08-board-4-task-5-051-update.md`。

Task 5 已在 DevSpace managed worktree `C:\Users\28276\.devspace\worktrees\wechat-cli-1ec755b9`、分支 `task5/0.5.1-update-validation` 中完成，本地实现提交为 `84b8a99`，精确基线为冻结 main HEAD `a579a25cb7f16e6fdf88d618252b4a5cbffef53d`。验收证据：Python 489 项运行、487 通过、2 跳过；Worker typecheck 通过、Vitest 17/17；0.5.1 ZIP 大小 `14268929`，SHA-256 `0ddbb0b402cc9d98ed001391c1a618527d165e328a1f4f1534d80e6b984956c0`，成员仅 `app-manifest.json` 与 `wechat-cli.exe`；独立 update-only verifier 完成临时 Ed25519 签名/验签、哈希、安全解包和真实 EXE `--version` 验证；真实 EXE loopback health 返回 `version=0.5.1`、`build_id=staging-051-20260808.1`。Launcher EXE 与 bootstrap 均未在该 worktree 生成。Worker 依赖恢复使用仓库已跟踪的 `package-lock.json`（lockfileVersion 3）和 `npm ci --ignore-scripts --no-audit --no-fund`；此前“Worker 目录没有 lockfile”的判断已核实为错误并由本记录修正。

Task 6 本地签名准备已于 2026-08-08 获得独立授权并完成。`rel_staging_051` 使用 `release-key-staging-01` 生成 manifest/signature；manifest SHA-256=`be111f0a786821319fb96f82f1748b4a75003b7c5fb296c48ec87b3355a3fd62`，package SHA-256=`0ddbb0b402cc9d98ed001391c1a618527d165e328a1f4f1534d80e6b984956c0`。manifest 元数据：version `0.5.1`、channel `stable`、minimum app `0.5.0`、minimum Launcher `0.1.0`、rollout 100、published_at `2026-08-08T12:44:04Z`；ZIP 内 build_id=`staging-051-20260808.1`。独立使用仓库外 Launcher 公钥文件中的对应 release 公钥验签成功，并复核 package hash、ZIP 两成员结构、platform/architecture/entrypoint。两个资产位于仓库外受限 staging secrets 目录，ACL 仅当前用户、SYSTEM、Administrators；敏感形态扫描 0 命中。

Task 6 外部发布/初始登记阶段已于 2026-08-09 获得独立授权并完成。发布前 preflight 确认 GitHub 中不存在 `v0.5.1`、D1 中不存在 `rel_staging_051`、release repo 干净且 prepared 哈希未漂移。随后创建私有 Draft `v0.5.1`（Release ID `367353041`），仅上传已验收 package/manifest/signature 三项资产（Asset IDs `506974337`、`506974359`、`506974373`），并在 staging Worker 登记 `rel_staging_051`。后验只读 D1 确认 version `0.5.1`、channel `stable`、manifest/package hashes 与批准值一致、package size `14268929`、GitHub repository/Release/package asset 映射正确、rollout 100、`enabled=0`、`paused=1`；所有只读 D1 核验均 `rows_written=0`。`release.register` 成功审计 request ID 为 `08e7af6c-98ac-4e29-9282-7b806f93c0da`。GitHub 后验检查确认 Draft 状态与三个资产数量、名称、大小完全匹配。

Task 6 Release enable 已于 2026-08-09 11:11 +08:00 获得独立授权并执行。后验只读 D1 确认 `rel_staging_051` 为 `enabled=1`、`paused=0`、`rollout_percentage=100`，manifest/package hashes、GitHub Release/asset 映射均未变化；成功 `release.update` 审计 request ID 为 `626ff686-df79-4281-b1af-18bbabbac434`。GitHub 按 Release ID 复核确认私有 Draft `v0.5.1` 及三项资产保持原 ID、名称和大小。所有后验 D1 查询均 `rows_written=0`。

Task 7 已于 2026-08-09 完成。fresh verification：Python 489 项运行、487 通过、2 跳过；Worker typecheck 通过、Vitest 17/17；0.5.1 update-only verifier 再次验证真实 ZIP hash、安全解包、Ed25519 信任实现与真实 EXE `--version`。最终只读 D1 确认许可证 active、设备历史 3 active + 1 unbound、`rel_staging_050`/`rel_staging_051` 均 `enabled=1`、`paused=0`、rollout 100，关键 Task 4/6 审计记录全部存在，所有最终查询 `rows_written=0`。最终 GitHub 只读核验确认 `v0.5.0` 与 `v0.5.1` 两个 private Draft 和各自三项资产均与记录一致。Board 4 验收报告已生成：`docs/deployment/2026-08-09-board-4-test-license-and-release-report.md`。

**板块 4 已完成；Board 5 accepted complete；Board 6 in progress。** stable Windows E2E、Offline acceptance、beta alignment、fault prepare/register/enable/private-prerelease publish、process-tree repair 后的 fresh rollback re-acceptance、**version-level server suppression**、final fault disable、Cloud Cleanup Gate 和 fresh final verification 均已完成。Worker `rel_board5_bad_052_01` 保持 `enabled=false`、`paused=true`、rollout 100；stable/beta Board 5 license 均已 revoked 且 active devices 0，两条 Board 5 test device row 均 unbound；JD25、050/051、GitHub release/assets/tags、main/NUL 与固定 0.5.0 ZIP 均已 fresh reconcile 无漂移。B6-G0 source integration 与 packaging boundary cleanup 已完成至 `c1d0458`；B6-G1 Update Trust Local Gate 已完成至 `bdc98af`；B6-G2 Admin & Data Security Local Gate 已完成至 `e0c91df`；B6-G3 Windows Integrity Local Gate 已完成至 `1a07447`，pre-staging security audit=`docs/superpowers/governance/2026-08-13-board-6-pre-staging-security-audit.md`；B6-G4 Staging Infrastructure Gate 与 B6-G5 Staging Behavior Acceptance Gate 均已完成，G5 证据见 `docs/superpowers/governance/2026-08-14-board-6-staging-behavior-acceptance.md`。**B6-G6 Phase A provider-neutral readiness repair + provider research 已本地完成**：deterministic Authenticode inspector/public evidence commits=`9f4ad0f`,`e9cb67b`，retained provider research=`docs/superpowers/governance/2026-08-14-board-6-code-signing-provider-decision.md`，fresh Python 630/2 skips/0 failures + Worker 92/92 + signing-focused 103/103 + real system-signed probe PASS。经 2026-08-14 scope amendment，真正的 B6-G6 commercial/provider identity gate 已从当前必经路径移除并 deferred 为未来 Public / Formal Distribution optional hardening；当前 Private / Controlled Distribution closure 不要求 real signed artifact。`50e7074` 仅为 dormant optional adapter。B6-G7 现为下一 mandatory gate，B6-G8 未进入，Board 7 未开始；production、existing Board 5 releases/JD25、push/merge、main/Board5 cleanup 继续禁止。
