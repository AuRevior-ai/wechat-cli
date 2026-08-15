# WeChat CLI Board 4 首次测试许可证与测试发布验收报告

> **Acceptance snapshot:** 本报告记录 2026-08-09 Board 4 收尾时点。当前仓库状态以后续 [`docs/PROJECT_STATE.md`](../PROJECT_STATE.md) 为准；七板块顺序与进入门槛以后续 [`authorized-update-roadmap.md`](authorized-update-roadmap.md) 为准。

日期：2026-08-09
阶段：板块 4——首次测试许可证与测试发布
结论：**板块 4 验收通过；可进入板块 5 的独立计划/设计门槛，但板块 5 尚未开始。**

## 1. 范围与边界

Board 4 的目标是在不进行真实 Windows 安装更新的前提下，用真实 staging Worker、D1、私有 GitHub Release 和 staging 密钥验证：

- 一张真实 staging 测试许可证；
- 三设备上限、激活、验证、重命名、解绑/重绑；
- 七天离线租约、Ed25519 验签和时钟回拨策略；
- 在线许可证状态优先于仍未过期的离线租约；
- 固定 0.5.0 基线发布；
- 0.5.1 测试更新的 app-only 构建、签名、私有资产、Worker 登记与 enable；
- Board 5 所需的可信更新输入。

本阶段明确不包含：

- staging bootstrap 制作或安装；
- Windows 安装目录中的真实 0.5.0 → 0.5.1 自动更新；
- Launcher 自动安装或故障回滚；
- Windows 代码签名；
- Git push 或 Task 5 分支 merge；
- production 资源、域名或正式上线。

## 2. Git 与工作区基线

### 2.1 冻结 main

- main checkout HEAD：`a579a25cb7f16e6fdf88d618252b4a5cbffef53d`；
- main checkout 唯一未跟踪项仍为用户要求保留的 `NUL`；
- `NUL` 未提交、未删除；
- main 中固定 0.5.0 ZIP 保持不变：
  - 文件：`dist/wechat-cli-app-0.5.0-win-x64.zip`
  - size：`14291197`
  - SHA-256：`406b72c14ad186141f373087595f7723e143b9638bf298fde23b6bb0ae057523`

### 2.2 隔离 Task 5/6/7 分支

- worktree：`C:\Users\28276\.devspace\worktrees\wechat-cli-1ec755b9`；
- branch：`task5/0.5.1-update-validation`；
- 精确基线：冻结 main `a579a25`；
- 0.5.1 实现提交：`84b8a99`；
- Task 5 本地验收记录：`b2e6ee1`；
- Task 6 签名准备记录：`556906e`；
- Draft/登记记录：`b0fc28b`；
- Release enable 记录：`41cffcb`；
- 本阶段截至报告生成前未 push、未 merge。

发布仓库：

- `AuRevior-ai/wechat-cli-releases`；
- 本地 HEAD：`2b9fa385b86df83f7968239a1029d4d59f020027`；
- 工作树在最终只读检查时 clean。

## 3. 许可证与设备真实 staging 验收

### 3.1 测试许可证

当前 live D1 只读核验：

- License ID：`lic_ptrqZVAxh2NI8h5RM6gnGiiL`；
- hint：`JD25`；
- status：`active`；
- release channel：`stable`；
- max devices：`3`；
- revision：`3`；
- `suspended_at=NULL`；
- `revoked_at=NULL`。

完整许可证仍只保存在仓库外受限文件中，本报告不记录其值。

### 3.2 设备上限与生命周期

Task 3 真实 staging 验收已证明：

- 第 1/2/3 台设备激活成功；
- 第 4 台首次激活返回稳定错误码 `DEVICE_LIMIT_REACHED`；
- 在线 validate 成功；
- 设备列表成功；
- rename 成功；
- unbind 成功；
- 解绑后重绑成功。

Board 4 收尾时 live D1 状态：

- 历史设备共 4 条；
- `active`：3；
- `unbound`：1；
- 设备 1 仍 active，最近一次 Task 4 恢复后 validate 成功；
- 所有记录仍显示 app `0.5.0` / Launcher `0.1.0`，符合 Board 5 尚未执行真实更新的边界。

## 4. 离线租约与在线状态优先策略

### 4.1 七天租约

Task 4 已完成真实 staging 租约验收：

- signing key ID：`lease-key-staging-01`；
- 独立 Ed25519 公钥验签成功；
- `issued_at=2026-08-08T09:56:21.927Z`；
- `offline_until=2026-08-15T09:56:21.927Z`；
- duration：`604800` 秒；
- `offline_valid` / `offline_expiring` / `offline_expired` 边界符合策略；
- 小幅时钟修正允许；
- 明显时钟回拨返回 `OFFLINE_LEASE_DENIED`。

### 4.2 在线状态优先

用户独立授权并执行的真实状态序列：

`active → suspended → 同一 device token 在线 validate → LICENSE_SUSPENDED → active → 同一 token revalidate 成功`

最终 D1 只读核验确认许可证恢复为 active，设备 1 继续可用。

关键审计 request IDs：

- `license.suspended`：`24f68caa-2b83-42dc-90d5-d35df4153911`；
- `license.active`：`ba926744-e8c6-4512-92de-5767b6ede9e0`；
- 恢复后的 `device.validate`：`dc2198d3-be66-4abc-a239-4e384a9d3a65`。

结论：在线服务器许可证状态确实优先于尚未过期的本地离线租约。

## 5. 0.5.0 固定基线发布

Worker / D1 当前只读记录：

- release ID：`rel_staging_050`；
- version：`0.5.0`；
- channel：`stable`；
- manifest SHA-256：`6f76cbc3052bea1e25fb8ecf53b5d1a88b16b27c40ebd341388d25e9514c1fed`；
- package SHA-256：`406b72c14ad186141f373087595f7723e143b9638bf298fde23b6bb0ae057523`；
- package size：`14291197`；
- rollout：`100`；
- `enabled=true`；
- `paused=false`。

GitHub 私有 Draft：

- tag：`v0.5.0`；
- Release ID：`365469593`；
- package Asset ID：`502527074`，size `14291197`；
- manifest Asset ID：`502527130`，size `911`；
- signature Asset ID：`502527173`，size `64`；
- 三资产当前均为 `uploaded`。

## 6. 0.5.1 测试更新

### 6.1 本地产物

Task 5 使用 app-only / update-only 路径构建：

- `APP_VERSION=0.5.1`；
- `LAUNCHER_VERSION=0.1.0`；
- 默认 `BUILD_ID=staging-051-20260808.1`；
- 未重建 Launcher；
- 未制作 bootstrap；
- 不需要 `pywebview`。

最终 ZIP：

- 文件：`wechat-cli-app-0.5.1-win-x64.zip`；
- size：`14268929`；
- SHA-256：`0ddbb0b402cc9d98ed001391c1a618527d165e328a1f4f1534d80e6b984956c0`；
- ZIP 成员严格只有：
  - `app-manifest.json`
  - `wechat-cli.exe`

最终 fresh update-only verifier 再次通过：

- real ZIP hash 校验通过；
- disposable Ed25519 签名/验签通过；
- safe extraction 通过；
- 解包后真实 EXE `--version` 返回 `0.5.1`。

Task 5 既有真实 EXE loopback health 证据：

- `version=0.5.1`；
- `build_id=staging-051-20260808.1`；
- `status=ok`。

### 6.2 staging 签名资产

本地签名准备：

- release ID：`rel_staging_051`；
- signing key ID：`release-key-staging-01`；
- channel：`stable`；
- minimum app：`0.5.0`；
- minimum Launcher：`0.1.0`；
- rollout：`100`；
- signed manifest metadata `published_at=2026-08-08T12:44:04Z`；
- manifest SHA-256：`be111f0a786821319fb96f82f1748b4a75003b7c5fb296c48ec87b3355a3fd62`；
- package SHA-256：`0ddbb0b402cc9d98ed001391c1a618527d165e328a1f4f1534d80e6b984956c0`。

独立使用对应 staging 公钥验签成功。私钥内容从未写入 Git 或本报告。

### 6.3 GitHub Draft 与 Worker

GitHub 私有 Draft：

- tag：`v0.5.1`；
- Release ID：`367353041`；
- package Asset ID：`506974337`，size `14268929`；
- manifest Asset ID：`506974359`，size `911`；
- signature Asset ID：`506974373`，size `64`；
- 三资产当前均为 `uploaded`。

Worker / D1 当前状态：

- release ID：`rel_staging_051`；
- version：`0.5.1`；
- channel：`stable`；
- manifest/package hashes 与本地批准值一致；
- package size：`14268929`；
- GitHub Release/asset 映射一致；
- rollout：`100`；
- `enabled=true`；
- `paused=false`。

关键审计：

- `release.register` request ID：`08e7af6c-98ac-4e29-9282-7b806f93c0da`；
- `release.update` enable request ID：`626ff686-df79-4281-b1af-18bbabbac434`。

Worker 中的 `published_at=2026-08-09T01:54:20.521Z` 表示登记时间；签名 manifest 中的 `published_at=2026-08-08T12:44:04Z` 表示签名元数据时间。两者不同是当前实现行为，已纳入验收事实。

## 7. Task 7 最终验证

### 7.1 Python 与 Worker

2026-08-09 fresh verification：

- Python：**489 项运行，487 通过，2 跳过**；
- Worker `npm run typecheck`：通过；
- Worker Vitest：**3 files / 17 tests 全部通过**。

Python 测试输出中的 `missing pywebview` 来自既有完整 Windows Launcher build 的 fail-closed 测试场景，不是 Task 5 app-only build 失败。

### 7.2 live staging / GitHub 只读复核

最终 D1 查询确认：

- 测试许可证 active；
- 3 active + 1 unbound device；
- `rel_staging_050` 与 `rel_staging_051` 均 `enabled=1`、`paused=0`、rollout 100；
- Task 4 / Task 6 关键审计 request IDs 全部存在且 result=success；
- 所有最终 D1 查询均 `changes=0`、`changed_db=false`、`rows_written=0`。

最终 GitHub 只读复核确认：

- `v0.5.0` 与 `v0.5.1` 都仍为 private Draft；
- 各自均恰好保留 package/manifest/signature 三项已上传资产；
- Release ID、Asset ID、名称和大小与 Worker/路线图记录一致。

### 7.3 敏感信息检查

- 非 tests 的 tracked 源码/文档：目标敏感形态扫描 0 命中；
- 仓库外 prepared 0.5.1 manifest/signature 目录：目标敏感形态扫描 0 命中；
- 宽泛 GitHub-token 形态只命中 4 个单元测试 fixture 文件；
- private-key block 形态：0；
- device-token/device-ID 长形态：0。

没有读取或记录真实 GitHub Token、管理员 Token、release 私钥、完整许可证或 device token。

## 8. 已知限制与后续门槛

- Task 5/6/7 工作仍位于隔离分支，未 merge 到 frozen main，也未 push；
- main checkout 仍保留未跟踪 `NUL`，按用户要求不得删除或提交；
- GitHub `v0.5.0` / `v0.5.1` 仍是私有 Draft；
- 当前已有 0.5.0 bootstrap 仍是 Demo 配置，不能直接用于真实 staging 安装；
- staging bootstrap 明确属于 Board 5；
- Windows EXE 尚未代码签名；
- production D1 配置仍有 replacement placeholder；
- Board 5 需要独立设计/计划批准后才能开始；
- Board 5 开始前不得把本报告理解为已完成真实 Windows 0.5.0 → 0.5.1 更新或回滚。

## 9. 结论

Board 4 的七个 Task 已满足其计划内退出条件：

1. 基线冻结完成；
2. 真实 staging 测试许可证完成；
3. 真实许可证/设备服务验收完成；
4. 真实租约与在线优先策略验收完成；
5. 0.5.1 app-only/update-only 构建完成；
6. 0.5.1 签名、私有 Draft、三资产、Worker 登记与 enable 完成；
7. 最终测试、live 状态复核、安全扫描和验收报告完成。

因此 **Board 4 可以标记为已完成**。

下一阶段是 **Board 5：Windows 真实端到端验收**。进入 Board 5 前仍必须单独完成 staging bootstrap 方案设计/计划并取得用户批准；当前不执行任何 Board 5 动作。
