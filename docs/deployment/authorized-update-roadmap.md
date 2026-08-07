# WeChat CLI 授权更新项目总路线图

> Repository-wide current-state summary: [`docs/PROJECT_STATE.md`](../PROJECT_STATE.md). This roadmap remains authoritative for the fixed seven-board licensing, update, release, and deployment program.

更新时间：2026-08-05 20:08 +08:00  
状态来源：本文件为七板块状态、检查点和下一步动作的唯一权威记录。  
实施状态：**板块 4 Task 2 已获授权；正在准备安全创建并保存真实 staging 测试许可证。**

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
| 4 | 首次测试许可证与测试发布 | **进行中** | Task 1 基线冻结已完成；下一项是创建 staging 测试许可证 |
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
- 当前状态：`enabled=True`、`paused=False`、`rollout_percentage=100`。

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

- 创建并安全保存一张 staging 测试许可证；
- 三设备上限和第四设备拒绝；
- 在线验证、离线租约、设备重命名、解绑与重新激活；
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

- 源码提交：`e36ab47d27bbff7360cbfc1a9038d47e9e18ce48`
- 发布仓库提交：`2b9fa385b86df83f7968239a1029d4d59f020027`
- staging Worker 版本：`04a61d9a-d513-4484-83af-e926dbe835f3`
- D1 无待执行迁移，8 个预期 Secret 名称全部存在
- Worker 中 `rel_staging_050` 恰好一条，GitHub 中 `v0.5.0` Draft 恰好一个
- GitHub 三个资产状态均为 `uploaded`，ID 与固定发布证据一致
- 发布仓库干净；源码仓库仅有本次外部记忆文档尚未提交
- 仓库外安全目录文件和 ACL 正常，管理员明文令牌已删除

Task 2 已于 2026-08-05 20:12 +08:00 获得独立明确授权；当前正在执行安全创建前检查。

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

Task 1 已完成。当前唯一允许推进的下一项是 Task 2：

1. 已说明用途、安全保存方式和不可逆影响；
2. 已于 2026-08-05 20:12 +08:00 取得独立明确授权；
3. 创建 `stable` 通道、最多 3 台设备的许可证；
4. 将完整许可证直接保存到仓库外受限文件，不在聊天或 Git 中展示；
5. 只记录许可证 ID、提示尾号、最大设备数和创建时间。

当前不得提前构建或发布 0.5.1，不制作 staging bootstrap，也不开始 Windows 真实端到端验收。
