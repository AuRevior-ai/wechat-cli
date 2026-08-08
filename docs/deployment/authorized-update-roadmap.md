# WeChat CLI 授权更新项目总路线图

> Repository-wide current-state summary: [`docs/PROJECT_STATE.md`](../PROJECT_STATE.md). This roadmap remains authoritative for the fixed seven-board licensing, update, release, and deployment program.

更新时间：2026-08-08 19:18 +08:00
状态来源：本文件为七板块状态、检查点和下一步动作的唯一权威记录。
实施状态：**板块 4 Task 1–4 已完成并完成最终冻结验证；Task 5 设计已批准，当前先冻结最新 `main` 基线，再从该 HEAD 创建隔离 DevSpace worktree 实施 0.5.1 本地构建。**

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
| 4 | 首次测试许可证与测试发布 | **进行中** | Task 1–4 已完成；Task 5 设计已批准，等待以冻结后的最新 `main` HEAD 创建隔离 worktree 后实施 |
| 5 | Windows 真实端到端验收 | 未开始 | 等待板块 4 完成并验收 |
| 6 | 安全与正式交付准备 | 未开始 | 等待板块 5 完成并验收 |
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

### 尚未完成

- 构建 0.5.1；
- 签名、发布并登记 `rel_staging_051`；
- 板块 4 验收报告。

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

**进行中。**

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

**未开始。**

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

### 状态

**未开始。**

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
- 生产资源、域名、凭据、代码签名和安全方案分别取得明确批准；
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

当前唯一允许推进的下一项是：先把 Task 3/4 实现、验收工具/测试、状态文档和 Task 5 子计划冻结提交到 `main`（不得 push），然后基于冻结后的最新 `main` HEAD 创建新的隔离 DevSpace worktree/分支实施 Task 5。主 checkout 中未跟踪的 `NUL` 必须保留且不得纳入提交。Task 6 的发布外部副作用继续单独授权。
