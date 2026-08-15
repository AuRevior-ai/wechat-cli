# 板块 4：首次测试许可证与测试发布计划

> Repository-wide current state: [`docs/PROJECT_STATE.md`](../../PROJECT_STATE.md). This file is the active execution plan for board 4 and its checkboxes remain the detailed progress record for this board.

> **计划状态：已批准，执行中。** 用户已明确批准本计划；Task 1、Task 2、Task 3、Task 4 已完成。Task 5 brainstorming 设计已批准，详细实施子计划见 `2026-08-08-board-4-task-5-051-update.md`。当前先冻结 Task 3/4 最新 `main` 基线；Task 5 只允许在该冻结 HEAD 派生的新隔离 DevSpace worktree 中实施。后续发布登记和启用等外部副作用仍按各自门槛单独授权。

**板块目标：** 在不进入 Windows 安装验收的前提下，用真实 staging Worker、D1、私有 GitHub Release 和 staging 密钥，完成一张测试许可证、许可证与设备服务基础验收，以及 0.5.0 基线发布和 0.5.1 测试更新发布，为板块 5 的 Windows 真实端到端验收准备可信输入。

**边界：** 本板块验证云端许可证、设备、租约和发布服务的真实连通性；不安装 staging bootstrap，不在真实 Windows 安装目录执行更新，不验证 Launcher 自动安装或回滚。上述内容属于板块 5。

**安全原则：** 明文许可证只生成一次并保存在仓库外受限目录；不输出或提交 Token、私钥、管理员令牌、`.env` 内容或完整许可证；任何 GitHub 发布、Worker 发布登记或启用动作在执行前单独取得明确授权。

---

## 当前检查点

### 已完成

- [x] 板块 1 本地最终收尾完成。
- [x] 板块 2 两个私有 GitHub 仓库和最小权限凭据完成。
- [x] 板块 3 Cloudflare staging Worker、D1、R2、Secret 和迁移完成。
- [x] 管理员 CLI 和发布 CLI 凭据已存入当前 Windows 用户 DPAPI。
- [x] staging 专用 Lease 和 Release Ed25519 密钥已生成。
- [x] `rel_staging_050` manifest、signature 和 ZIP 哈希已本地验证。
- [x] GitHub 私有 Draft Release `v0.5.0` 已创建并上传三个资产。
- [x] Worker 已登记并启用 `rel_staging_050`。

### 固定证据

- Release ID：`rel_staging_050`
- Version：`0.5.0`
- Manifest SHA-256：`6f76cbc3052bea1e25fb8ecf53b5d1a88b16b27c40ebd341388d25e9514c1fed`
- Package SHA-256：`406b72c14ad186141f373087595f7723e143b9638bf298fde23b6bb0ae057523`
- Package size：`14291197`
- Worker 状态：`enabled=True`、`paused=False`、`rollout_percentage=100`

---

## Task 1：冻结板块边界并保存基线

**只读检查：**

- 源码仓库与发布仓库 Git 状态；
- staging Worker 部署状态；
- D1 迁移状态；
- Worker Secret 名称；
- `rel_staging_050` Worker 记录；
- GitHub Draft Release 和三个资产元数据；
- staging 安全目录中的必要文件是否存在，但不读取或显示秘密内容。

**动作：**

- [x] 记录当前源码提交、Worker 版本 ID、Release ID、资产 ID 和哈希。
- [x] 确认两个 Git 仓库工作树干净，或记录与板块外部记忆相关的现有修改。
- [x] 确认 `rel_staging_050` 不重复发布、不重复登记。
- [x] 更新总路线图中的板块 4 起始检查点。

### Task 1 基线证据（2026-08-05）

- 源码提交：`e36ab47d27bbff7360cbfc1a9038d47e9e18ce48`
- 发布仓库提交：`2b9fa385b86df83f7968239a1029d4d59f020027`
- 源码工作树：仅有本次外部记忆文档尚未提交；无实现文件修改
- 发布仓库工作树：干净
- staging Worker 当前部署版本：`04a61d9a-d513-4484-83af-e926dbe835f3`
- D1：无待执行迁移
- Worker Secret：8 个预期名称全部存在
- Worker 中 `rel_staging_050` 记录数：1
- GitHub 中 `v0.5.0` Release 数：1，Release ID `365469593`，Draft 为 `True`
- GitHub 资产数：3，ID 分别为 `502527074`、`502527130`、`502527173`
- 三个资产状态均为 `uploaded`，大小分别为 `14291197`、`911`、`64`
- 安全目录仍有 `.dev.vars`、`bootstrap-admin.sql`、Launcher 公钥/模板、README 和发布私钥；管理员明文令牌已删除
- 安全目录 ACL 仅允许当前用户、SYSTEM 和管理员组

**退出条件：已满足。** 基线可重复识别，没有重复发布、重复登记或需要先处理的遗留云端状态。

## Task 2：创建并安全保存一张 staging 测试许可证

**预期动作：**

- 使用管理员 CLI 创建一张 `stable` 通道、最多 3 台设备的测试许可证；
- 不绑定真实客户邮箱；使用明确标记为 staging 的测试联系人，或不填写联系人；
- 将明文许可证直接写入仓库外受限文件，不在终端、聊天和 Git 中长期展示；
- 记录许可证 ID、提示尾号、最大设备数和创建时间，不记录完整许可证。

**安全门槛：**

- [x] 创建命令执行前再次取得用户对“创建真实 staging 测试许可证”的明确授权（2026-08-05 20:12 +08:00）。
- [x] 目标文件位于仓库外安全目录并使用 `CreateNew` 拒绝覆盖已有文件。
- [x] 文件 ACL 仅允许当前用户、SYSTEM 和管理员组。
- [x] 创建后检查 Git 状态和敏感信息扫描结果。

### Task 2 验收证据（2026-08-08）

- License ID：`lic_ptrqZVAxh2NI8h5RM6gnGiiL`
- License hint：`JD25`
- 状态：`active`
- 最大设备数：3
- 发布通道：`stable`
- D1 创建时间：`2026-08-08T09:07:57.146Z`
- D1 只读查询确认该许可证记录数恰好为 1
- 明文许可证保存于仓库外受限文件 `staging-secrets-20260805/staging-test-license-01.txt`
- 非敏感 metadata 保存于 `staging-secrets-20260805/staging-test-license-01.metadata.json`
- 两个文件 ACL 均仅允许当前用户、SYSTEM 和管理员组
- 完整许可证未进入 Git、路线图、计划或聊天记录
- 当前源码工作树只有本轮状态文档更新；没有实现文件变更

**退出条件：已满足。** 一张可用的测试许可证已安全保存，完整值未进入仓库或聊天记录。

## Task 3：许可证和设备服务真实验收

**验收方式：** 采用用户批准的方案 A：新增专用 `scripts/staging_license_acceptance.py`，复用 `LicenseApiClient` 和可控合成测试身份，不进入 Launcher/UI，不调用管理员 API，不创建额外许可证，不触碰 Release、诊断、许可证状态或 Windows 安装目录。

### Task 3 设计确认（2026-08-08）

- 用户已批准方案 A：独立 staging 许可证/设备验收工具。
- 工具只读取仓库外现有测试许可证文件；许可证正文只进入进程内存，不写日志、不写 JSON 报告、不进入异常文本。
- 每次运行生成 4 个独立的合成测试设备 ID 与 64 位十六进制 fingerprint，显示名固定使用 `STAGING-ACCEPTANCE-01..04`，不读取 MachineGuid、SID 或真实计算机名。
- 设备 Token 只保留在进程内存；输出只包含许可证 ID、hint、设备 ID 的缩略形式、设备数量、状态、稳定错误码和 UTC 时间。
- 第 1/2/3 台激活成功后，以第 1 台 Token 执行在线 validate 和设备列表；第 4 台首次激活必须得到 `DEVICE_LIMIT_REACHED`。
- 将第 2 台重命名为 `STAGING-ACCEPTANCE-RENAMED`，解绑第 3 台，再用第 4 台身份重新激活，最终确认 active 设备数恢复为 3。
- 工具不自动清理这 3 台最终 active 测试设备；其状态作为后续 Task 4/板块 5 的可控输入，清理动作另行授权。
- 实现前先补失败测试，覆盖 Cloudflare 所需应用专用 `User-Agent`、永久许可证仅用于 activate、后续请求只用 device token、敏感值不出现在输出中、第四台拒绝与解绑后重新激活流程。
- 2026-08-08 只读探测已确认现有 `UrllibJsonTransport` 使用 Python 默认请求特征时会被 Cloudflare 返回 HTTP 403；因此 Task 3 的最小实现包含为许可证 transport 设置 `WeChatCliLicense/<APP_VERSION>` User-Agent。该修复同时是未来真实 Launcher 连接 staging 的必要条件。

### Task 3 实现检查点（2026-08-08）

- [x] 新增 `scripts/staging_license_acceptance.py`，只覆盖许可证/设备服务，不调用管理员 API、Release、诊断或 Windows Launcher。
- [x] 为 `UrllibJsonTransport` 增加 `WeChatCliLicense/0.5.0` User-Agent；修复前真实 staging `/v1/health` 探测为 Cloudflare HTTP 403，修复后为 HTTP 200、`environment=staging`。
- [x] 先写失败测试并确认红灯：User-Agent 缺失测试失败，验收工具模块不存在测试报错。
- [x] 定向许可证/验收测试 13 项通过。
- [x] Python 全量 469 项运行，467 通过、2 项平台条件跳过。
- [x] 工具输出与状态文档敏感模式扫描未发现完整许可证、设备 Token、管理员令牌或 GitHub Token。
- [x] 工具使用稳定 `license_id + run_id` 派生测试设备身份，并在发现未知 active 设备时拒绝继续，避免误操作其他状态。

**首次真实设备激活属于外部副作用。** 用户已于 2026-08-08 17:27 +08:00 明确授权“运行 Task 3 staging 设备验收”；用户随后在本机终端执行获批命令，Task 3 已完成真实 staging 写入和只读 D1 核验。

**场景：**

- [x] 使用第一台测试设备身份激活许可证。
- [x] 验证激活后返回设备 Token 和签名租约；租约签名与约七天有效期的独立验证留给 Task 4。
- [x] 验证后续在线验证只使用设备 Token，不再次发送永久许可证；由客户端实现约束、定向测试和真实 validate 成功共同确认。
- [x] 使用第二、第三台设备身份激活成功。
- [x] 验证第四台设备被稳定错误码 `DEVICE_LIMIT_REACHED` 拒绝。
- [x] 列出设备并确认设备数量、状态和显示名称。
- [x] 重命名第二台设备并验证结果。
- [x] 解绑第三台非当前设备并验证名额立即释放。
- [x] 再激活第四台新设备并确认恢复到三台上限。

### Task 3 真实 staging 验收证据（2026-08-08）

- 客户端报告：`ok=true`，`run_id=board4-task3-20260808`，`checked_at=2026-08-08T09:29:52.428054Z`。
- 设备安全缩略 ID：`dev_stg_26…8ae2`、`dev_stg_33…d187`、`dev_stg_c0…973e`、`dev_stg_7f…01cc`。
- 第四台首次激活：`DEVICE_LIMIT_REACHED`。
- 在线 validate：成功；签名租约字段存在。
- 重命名：成功；D1 持久化为 `STAGING-ACCEPTANCE-RENAMED`。
- 解绑/重新激活：成功；最终 active 设备数为 3。
- D1 聚合：历史设备 4 条，`active=3`，`unbound=1`。
- 最终 active：设备 1、2、4；设备 3 为 `unbound`。
- 激活成功审计 request ID：`b0dc1ecf-e732-47f9-8b53-e7c87f2312aa`、`7f6c5735-5ee9-46bd-a4c5-d84124c88a46`、`620afa4b-b2d1-4d49-925c-9704f8c8639b`、`9a1bbabd-1b2c-4d49-b1ec-14fff51f5c41`。
- 重命名审计 request ID：`66d76931-eec3-45e2-a357-8f8cd30f48d7`。
- 解绑审计 request ID：`1367cdc9-d8f0-4477-bcc3-013b45ed99c1`。
- 完整许可证、设备 Token 和完整 fingerprint 均未写入计划或输出。

**记录：** 只记录设备 ID 的安全缩略信息、状态、错误码、request ID 和时间，不记录 Token 或完整设备指纹。

**退出条件：已满足。** 三设备上限、第四台拒绝、重命名、解绑和重新激活均有真实 staging 证据。

## Task 4：在线验证与离线租约服务验收

**本板块范围：** 验证 API、签名和策略数据，不进行 Windows Launcher 真实断网启动；后者留到板块 5。

### Task 4 最小验收设计（2026-08-08）

- Task 3 为避免泄漏没有持久化 device token；Worker 也只保存 token 摘要，无法只读恢复旧 token。
- `/v1/devices/validate` 会更新 D1 的 `last_validated_at`、客户端版本字段并写 `device.validate` 审计，因此真实在线 validate 本身也是云端写入。
- 为取得新的真实 staging 租约，新增独立 `scripts/staging_lease_acceptance.py`：使用 Task 3 的同一 `license_id + run_id` 派生设备 1，先重复激活该已有设备一次以刷新 token，再立即 validate 一次。不会新增设备名额，也不触碰设备 2/3/4。
- 工具只读取仓库外许可证文件、非敏感 metadata 和 `launcher-public-keys.json`；device token、永久许可证、租约原文和签名只存在于进程内存，不落盘、不输出。
- 使用 `lease-key-staging-01` 对 validate 返回的租约字节做 Ed25519 独立验签，并验证 license/device 绑定、`status=active`、`server_time == issued_at` 和精确 7 天（604800 秒）有效期。
- 使用真实租约的 issued/offline-until 时间作为可控时钟输入，验证 `offline_valid`、`offline_expiring`、`offline_expired`；再用 `TrustedTimeState` 验证 5 分钟容差内的小修正允许、明显回拨以 `OFFLINE_LEASE_DENIED` 拒绝。
- 本地实现和测试完成后暂停；运行真实 staging 工具前必须单独取得对“重复激活设备 1 + validate 一次”的明确授权。
- 暂停、恢复、吊销许可证仍是后续独立外部副作用，不包含在该授权内。

### Task 4 本地实现检查点（2026-08-08）

- [x] 新增 `scripts/staging_lease_acceptance.py`，只重复激活 Task 3 的现有设备 1 并 validate 一次；不新增设备、不改许可证状态、不碰 Release、诊断或 Windows Launcher。
- [x] CLI 强制要求 `--confirm-cloud-mutation`；缺少该参数时，在读取许可证文件或建立网络客户端前返回 `CLOUD_MUTATION_NOT_CONFIRMED` 并退出 2。
- [x] 新增 `tests/test_staging_lease_acceptance.py`，先观察模块不存在的红灯，再实现最小能力。
- [x] 本地定向租约/时钟测试 9 项通过；许可证、Task 3/Task 4 staging 验收相关回归 24 项通过。
- [x] Python 全量 471 项运行，469 通过、2 项平台条件跳过。
- [x] 公钥文件确认包含 `lease-key-staging-01`；真实公钥只用于验签，不包含私钥。
- [x] Task 4 真实 staging 工具已运行成功；新增且仅新增预期的设备 1 重复激活与一次 validate 审计。

**真实租约验收门槛：已完成。** 用户于 2026-08-08 17:51 +08:00 明确授权“对 Task 3 现有设备 1 重复激活一次，并在线 validate 一次”，随后在本机终端执行获批命令并得到 `ok=true`。该授权只覆盖这两个调用；暂停、恢复或吊销许可证仍需后续分别授权。

**场景：**

- [x] 在线验证返回 active 许可证、active 设备和新的签名租约。
- [x] 使用 `lease-key-staging-01` 对返回租约做客户端公钥验证。
- [x] 验证租约期限为精确七天（604800 秒），设备和许可证绑定字段正确。
- [x] 使用项目可控时钟测试租约有效、临近过期、已过期和系统时钟明显回拨场景。
- [ ] 暂停测试许可证，验证下一次在线请求立即拒绝。
- [ ] 恢复许可证后重新验证。
- [ ] 吊销测试许可证的破坏性场景推迟到本板块末尾，或另建第二张一次性许可证，避免提前破坏后续 0.5.1 验收。

### Task 4 真实租约验收证据（2026-08-08）

- 客户端输出：`ok=true`，设备缩略 ID `dev_stg_26…8ae2`。
- 签名：`signature_verified=true`，`key_id=lease-key-staging-01`。
- `issued_at=2026-08-08T09:56:21.927Z`，`offline_until=2026-08-15T09:56:21.927Z`，`duration_seconds=604800`。
- 状态边界：`offline_valid`、`offline_expiring`、`offline_expired`。
- 小幅时钟修正允许；明显回拨拒绝码：`OFFLINE_LEASE_DENIED`。
- D1 只读核验：许可证与设备 1 均保持 `active`，设备 1 `last_validated_at=2026-08-08T09:56:21.830Z`，版本仍为 app `0.5.0` / launcher `0.1.0`。
- 新增审计 request ID：`device.activate` = `72c1d50b-5542-4b9b-a7f9-ade395e80833`；`device.validate` = `ac834a2a-a5df-43cb-9b4d-ef82de2158c0`。
- 完整许可证、device token、租约原文、签名和 nonce 均未落盘或写入外部记忆。

### Task 4 暂停/恢复在线优先策略设计（2026-08-08）

- 用户已批准方案 A：新增独立 `scripts/staging_license_status_acceptance.py`，不把管理员状态变更混入租约验签工具。
- 工具在单个进程内先对 Task 3 设备 1 做一次重复激活，device token 只驻留内存；随后使用 Windows 当前用户 DPAPI 中已有管理员配置，不读取或输出管理员 Token 明文。
- 工具必须校验管理员配置的 `api_base_url` 与命令行指定 staging URL 完全一致，避免把 staging 许可证 ID 误操作到其他环境。
- suspend 前先通过管理员只读查询确认目标许可证当前为 `active`；如不是 `active`，立即停止，不尝试状态变更。
- suspend 请求一旦开始发送，即把恢复标记设为必需。无论 suspend 返回成功、异常、超时或响应丢失，`finally` 都必须尝试把许可证恢复为 `active`，覆盖“服务端已写入但客户端未收到响应”的不确定状态。
- suspend 明确成功后，使用暂停前同一 device token 调用 `/v1/devices/validate`，必须得到稳定错误码 `LICENSE_SUSPENDED`；任何其他错误码或意外成功均判为验收失败，但仍先恢复许可证。
- 恢复 `active` 成功后，再使用同一 device token validate 一次，必须重新成功并返回签名租约；证明在线明确状态优先于暂停前仍未过期的本地租约，且恢复后原设备会话可继续使用。
- 如果恢复 `active` 失败，工具必须返回独立 `RESTORE_FAILED`/恢复风险结果，不能用原测试失败覆盖这一更高优先级风险；此时停止一切后续动作并要求人工只读核验许可证状态。
- CLI 必须显式要求 `--confirm-cloud-mutation`，缺失时在读取敏感配置或建立网络客户端前拒绝执行。
- 输出只允许许可证 ID/hint、设备缩略 ID、状态、稳定错误码、是否恢复成功和 UTC 时间；不得输出永久许可证、device token、管理员 Token、租约原文/签名或完整 fingerprint。
- 工具不执行 `revoked`，不触碰 Release、诊断、设备 2/3/4 或 Windows Launcher。真实运行前仍需对 `active → suspended → active` 单独取得明确授权。
- 状态接口响应不返回 request ID；真实运行完成后继续通过 D1 `audit_events` 只读查询收集 `license.suspended`、`device.validate` 拒绝证据（如有审计）和 `license.active` 的 request ID。

### Task 4 暂停/恢复工具本地实现检查点（2026-08-08）

- [x] 新增 `scripts/staging_license_status_acceptance.py`，单进程持有设备 1 token，并复用现有 `AdminApiClient`、`LicenseApiClient`、DPAPI `AdminConfigStorage`；未自建管理员鉴权协议。
- [x] 管理员配置必须与显式 `--base-url` 完全匹配；目标许可证在任何状态写入前通过管理员只读查询确认恰好一条且为 `active`。
- [x] suspend 请求开始发送前设置强制恢复标记；正常失败、异常成功、响应丢失/超时语义均通过 fake client 测试确认最终仍尝试恢复 `active`。
- [x] 恢复失败独立提升为 `RESTORE_FAILED`，不会被原始验收错误覆盖；输出不包含永久许可证、device token 或管理员 Token。
- [x] 正常路径测试确认：同一 device token 在 suspended 时必须得到 `LICENSE_SUSPENDED`，恢复 `active` 后同一 token 再次 validate 成功并返回签名租约。
- [x] 新增 `tests/test_staging_license_status_acceptance.py`；先观察模块不存在的红灯，再实现最小能力。专用状态/恢复测试 5 项通过。
- [x] 管理员、许可证、Task 3/Task 4 租约与状态工具相关回归 27 项通过。
- [x] Python 全量 476 项运行，474 通过、2 项平台条件跳过；既有 `missing pywebview` 构建提示未形成测试失败。
- [x] CLI 缺少 `--confirm-cloud-mutation` 时，在读取许可证/DPAPI 配置或建立网络客户端前返回 `CLOUD_MUTATION_NOT_CONFIRMED` 并退出 2。
- [x] `git diff --check` 通过；新工具和状态文档未匹配真实管理员 Token、永久许可证或 device token；发布仓库保持干净。
- [x] 真实 staging 状态工具已运行成功：客户端返回 `ok=true`、`suspended_rejection_code=LICENSE_SUSPENDED`、`restore_succeeded=true`、`restored_validation_ok=true`。

**真实状态验收：已完成。** 用户于 2026-08-08 18:20 +08:00 明确授权真实 staging `active → suspended → 在线 LICENSE_SUSPENDED → active → 同 token revalidate`，随后在本机终端执行获批命令并返回成功。D1 只读核验确认最终许可证为 `active`、revision=3、`suspended_at=NULL`、`revoked_at=NULL`；设备 1 恢复后再次 validate 成功。吊销继续推迟，不作为 Task 4 退出条件。

**退出条件：已满足。** 暂停前已取得并独立验签的真实租约有效至 `2026-08-15T09:56:21.927Z`，但在许可证被暂停后，同一设备 token 的在线 validate 仍立即得到 `LICENSE_SUSPENDED`；恢复 `active` 后同一 token 再次 validate 成功。由此确认在线服务器状态优先于客户端尚未过期的离线租约。不可逆吊销继续推迟，不影响后续板块输入。

### Task 4 真实状态证据（2026-08-08）

- 客户端状态验收：`ok=true`；`suspended_rejection_code=LICENSE_SUSPENDED`；`restore_succeeded=true`；`restored_validation_ok=true`。
- D1 最终许可证：`status=active`，revision=3，`updated_at=2026-08-08T10:23:26.079Z`，`suspended_at=NULL`，`revoked_at=NULL`。
- 设备 1 最终状态：`active`；恢复后 `last_validated_at=2026-08-08T10:23:26.931Z`。
- `license.suspended` 审计 request ID：`24f68caa-2b83-42dc-90d5-d35df4153911`。
- `license.active` 审计 request ID：`ba926744-e8c6-4512-92de-5767b6ede9e0`。
- 恢复后的 `device.validate` 审计 request ID：`dc2198d3-be66-4abc-a239-4e384a9d3a65`。
- 暂停期间的拒绝发生在 Worker 的 active-license 鉴权阶段，因此不会写成功 `device.validate` 审计；客户端稳定错误码是该拒绝的验收证据。

## Task 5：设计并构建 0.5.1 测试更新

**设计门槛：已满足。** 用户已完成并批准 brainstorming，固定如下：

- 0.5.1 是纯更新链路验证包，不增加业务可见功能；
- `APP_VERSION=0.5.1`，Launcher 保持 `0.1.0`；默认 BUILD_ID 为 `staging-051-20260808.1`，同时保留 `WECHAT_CLI_BUILD_ID` 显式覆盖；
- `npm/scripts/build.py` 增加 app-only 目标，只构建 `wechat-cli.exe`，不构建 Launcher；
- `scripts/package_windows_app.py` 增加 update-only 模式，只生成 `wechat-cli-app-0.5.1-win-x64.zip`，不要求 launcher config，不制作 bootstrap；
- 0.5.0 固定 ZIP 必须保持原大小与 SHA-256，不得原地覆盖；
- staging bootstrap 明确留到板块 5；
- Task 5 不创建、上传、登记或启用 0.5.1 Release，Task 6 外部副作用继续单独授权；
- 实施必须位于从冻结后最新 `main` HEAD 派生的隔离 DevSpace worktree/分支中，不在 `main` checkout 直接修改版本/build/packaging。

**实施子计划：** `docs/superpowers/plans/2026-08-08-board-4-task-5-051-update.md`。

**实施原则：**

- [ ] 先写或更新版本相关测试并观察预期失败。
- [ ] 只做获批的最小 0.5.1 变更。
- [ ] 构建新的 `wechat-cli-app-0.5.1-win-x64.zip`，不得修改 0.5.0 固定产物。
- [ ] 运行全量 Python 测试、Worker 测试和适用的 Windows 产物验证。
- [ ] 记录 0.5.1 ZIP 大小和 SHA-256。
- [ ] 确认源码仓库无秘密和意外构建文件。

**退出条件：** 0.5.1 产物可复现、测试通过、与 0.5.0 并存且未覆盖旧产物。

## Task 6：准备、发布并登记 `rel_staging_051`

**本地准备：**

- [ ] 使用 `release-key-staging-01` 生成 0.5.1 manifest 和 Ed25519 signature。
- [ ] 独立验证 manifest 字节、signature、公钥、ZIP 哈希和包内版本。
- [ ] 在仓库外准备目录保存 manifest 与 signature。

**外部发布：**

- [ ] 发布前取得“创建 0.5.1 私有 Draft Release”的明确授权。
- [ ] 创建 GitHub Draft Release 并上传 ZIP、manifest、signature。
- [ ] 在 Worker 中登记 `rel_staging_051`，初始保持 `enabled=False`、`paused=True`。
- [ ] 核对 GitHub 资产和 Worker 记录一致。
- [ ] 启用前取得独立授权。
- [ ] 启用后核对 `enabled=True`、`paused=False`。

**退出条件：** `rel_staging_051` 已安全发布并具备供板块 5 使用的可信资产和 Worker 记录。

## Task 7：板块 4 收尾与进入板块 5 的门槛

**最终验证：**

- [ ] 重新运行所有受影响的定向测试和全量测试。
- [ ] 重新检查两个仓库 Git 状态。
- [ ] 扫描源码、文档和构建产物，确认没有 Token、私钥、明文许可证和管理员令牌。
- [ ] 汇总测试许可证状态、设备验收、租约验收、0.5.0/0.5.1 发布状态、哈希和 request ID。
- [ ] 创建板块 4 验收报告。
- [ ] 更新 `docs/deployment/authorized-update-roadmap.md`，将板块 4 标记为已完成。

**板块 5 进入条件：**

- 测试许可证仍为可用状态；
- 设备名额和测试数据处于已记录、可清理状态；
- 0.5.0 与 0.5.1 的私有资产、签名、公钥和 Worker 状态均确认；
- staging bootstrap 的独立制作方案已写成板块 5 计划；
- 用户明确批准板块 5 计划。

---

## 不属于本计划的事项

以下工作明确留到后续板块：

- 制作并安装真实 staging bootstrap；
- 在 Windows 安装目录激活许可证；
- Launcher 启动、后台下载、下次启动安装；
- 制造故障版本并验证自动回滚；
- 真实断网七天启动；
- Windows 代码签名、正式域名、备案和生产资源；
- GitHub Actions 自动化发布。

## 批准记录

- 计划创建时间：2026-08-05
- 用户批准时间：2026-08-05 20:01 +08:00
- 当前状态：**已批准，执行中**
- Task 1 状态：**已完成**
- Task 2 状态：**已完成**
- Task 2 独立授权：已取得
- Task 3 状态：**已完成**
- Task 4 真实租约验收授权时间：2026-08-08 17:51 +08:00
- Task 4 暂停/恢复真实 staging 授权时间：2026-08-08 18:20 +08:00
- Task 4 状态：**已完成**
- Task 3/4 冻结实现提交：`5d65a9c`（license transport User-Agent）、`cc540dd`（staging 验收工具与测试）
- Task 3/4 最终冻结验证：Python 476 项运行、474 通过、2 跳过；Worker typecheck 通过、Vitest 17/17；`git diff --check` 通过；敏感值形态扫描 0 命中；发布仓库干净；D1 只读状态与 Task 4 记录一致且 `rows_written=0`
- 当前执行点：先提交 Task 3/4 状态文档并单独提交 Task 5 子计划到 `main`（不 push）；随后基于冻结后的最新 `main` HEAD 创建隔离 DevSpace worktree/分支实施 Task 5。主 checkout 的未跟踪 `NUL` 保留且不得纳入提交
