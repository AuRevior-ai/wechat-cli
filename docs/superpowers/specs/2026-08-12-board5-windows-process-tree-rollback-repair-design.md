# Board 5 Windows Process-Tree Rollback Repair Design

日期：2026-08-12
状态：**设计待用户书面审阅批准；未进入 implementation。**

## 1. 背景与目标

Board 5 rollback acceptance 已经证明 fault candidate 的发布、beta 选择、下载、验签、安全解包和 transaction rollback 状态机能够进入预期路径，但真实 Windows/PyInstaller 进程回收暴露了一个必须修复的缺陷。

当前目标不是扩大 Board 5 功能范围，而是让已经设计好的 rollback contract 在真实 Windows one-file PyInstaller 进程模型下成立：candidate health 失败后，Launcher 必须真正停止 candidate 的整个进程树，确认应用端口已经释放，再恢复并验证 previous version。任何停止失败都必须 fail closed，不能把残留 candidate 的 health 误认为 restored version 的 health。

## 2. 已确认的真实证据

### 2.1 fault 可见性 blocker 已解除

经独立授权，GitHub fault Release ID `368572125` 已从 private Draft 发布为 private prerelease：

- tag：`v0.5.2-board5bad.1`
- `draft=false`
- `prerelease=true`
- `make_latest=false`
- tag 指向 release-repository commit `2b9fa385b86df83f7968239a1029d4d59f020027`
- 三个既有 asset 的 ID、size、digest 未变化

发布后真实 Worker one-byte probe 返回 HTTP 206，`Content-Range=bytes 0-0/14268937`，package/manifest hash 与冻结 fault candidate 一致。

### 2.2 rollback 状态机已命中预期 fault

真实 `--download-update` 成功完成：

- current pointer 在下载后仍为 `0.5.1 / beta`
- pending release：`rel_board5_bad_052_01`
- pending version：`0.5.2-board5bad.1`
- pending manifest SHA-256：`2d29da32cb05e1a373ddab58725f2810e1d81489ad769a0ed6094458eb71fdaa`
- ZIP size/SHA-256：`14268937` / `96111ad0fff5827a93e81d826de150ea616eb4c907b20ada9a420967f8ffaf82`
- candidate EXE size/SHA-256：`14483951` / `dbbdf8ec70ddcf8d36145f099b0cb4ce3292c61e205c3ac7ae4db01fbc8907d1`
- candidate EXE 自己的 `--version` 输出仍为 `0.5.1`

随后真实 `--apply-update` 产生新的 transaction：

- from：`0.5.1`
- to：`0.5.2-board5bad.1`
- state：`rolled_back`
- failure reason：`application health version does not match the update`
- current pointer 已恢复 `0.5.1`
- failed registry 已记录 `0.5.2-board5bad.1`

这证明 fault candidate 本身和 health mismatch 设计正确。

### 2.3 真正失败点：PyInstaller child 被遗留

rollback 结束现场同时存在：

- candidate 目录 `versions/0.5.2-board5bad.1/wechat-cli.exe` 的孤儿 child，继续监听 `127.0.0.1:18787`
- restored `versions/0.5.1/wechat-cli.exe` 进程也已创建，但没有取得监听端口
- 两个进程各自的原 parent PID 均已退出

当时 `/api/health` 虽返回 `version=0.5.1`，但监听进程实际来自 candidate 目录，并且 `license_session_valid=false`。因此 Launcher 的 restored health check 读取到了残留 candidate child 的响应，形成 false-positive rollback health。

随后异常 RollbackSandbox 进程被精确停止，stable sandbox 已通过生产 `LauncherService + LocalApplicationRuntime + DPAPI state` 恢复；当前 stable 监听路径属于 `versions/0.5.1/wechat-cli.exe`，health 为 `0.5.1 / staging-051-20260808.1 / ok / license_session_valid=true`。

## 3. 根因

根因位于 `wechat_cli/launcher/process.py` 的 Windows process lifecycle：

1. `ApplicationProcessManager.start()` 对 PyInstaller one-file EXE 返回一个 `subprocess.Popen` parent。
2. 真实应用随后产生 PyInstaller child；实际 web server 由 child 持有。
3. `ApplicationProcessManager.stop()` 当前只对 Popen parent 调用 `terminate()`，超时后才对同一个 parent 调用 `kill()`。
4. parent 退出后 child 变为 orphan，继续持有 18787。
5. `LocalApplicationRuntime.stop()` 当前没有验证端口是否真的释放。
6. `LauncherService.start()` 在 candidate health 失败分支中会捕获并忽略 `runtime.stop()` 的异常，然后继续启动 previous version；因此即使未来 stop 明确失败，也可能继续产生 false-positive restored health。

现有 `tests/test_launcher_process.py` 只验证单个 Popen 的 terminate/kill 行为，没有覆盖 Windows/PyInstaller process-tree 语义，也没有端口释放 contract。

## 4. 已选择方案

采用此前比较过的 **方案 B：Windows process-tree termination + port-release fail-closed verification**。

不采用仅修 parent 的方案 A，因为它缺少第二道真实性检查；不采用 Windows Job Object 方案 C，因为 Board 5 尾声引入 ctypes/native Job Object 生命周期会扩大实现和验证范围。

## 5. 设计

### 5.1 Windows 下终止整个 app process tree

`ApplicationProcessManager.stop()` 保持跨平台 API 不变。

在 Windows：

1. 读取原始 Popen PID；PID 只能作为整数参数使用。
2. 在 parent 仍存在时，通过 Windows 系统提供的 process-tree termination 能力终止该 PID 及全部 descendants。实现计划优先使用 `taskkill.exe /PID <pid> /T /F`，必须 `shell=False`，不得拼接 shell 字符串。
3. tree termination 返回后等待原始 Popen 进入终态。
4. 如果 tree termination 本身失败或原始 Popen 在限定时间内仍未结束，抛出明确异常；不得静默返回成功。

非 Windows 继续保持现有 `terminate -> wait -> timeout 时 kill` 逻辑，不改变 Linux/macOS 行为。

测试必须通过可注入/可 patch 的 process-tree terminator，不能依赖单元测试真实杀系统进程。

### 5.2 `LocalApplicationRuntime.stop()` 增加端口释放 contract

process manager 报告 stop 完成后，runtime 必须等待 `127.0.0.1:<configured port>` 进入“不再接受连接”的状态。

要求：

- 有短、有限的 timeout 和轮询 interval；
- 端口在 timeout 内释放：stop 成功；
- 端口持续占用：抛出明确异常；
- 不因为 `/api/health` 版本字段看起来正确就认为 stop 成功；端口占用本身就是阻断条件。

这样即使未来出现新的打包器/子进程行为，Launcher 也不会在旧 listener 仍存在时启动 restored app。

### 5.3 stop failure 必须在 rollback orchestration 中 fail closed

`LauncherService.start()` 的 candidate health-failure 分支调整为：

1. 捕获 candidate health failure。
2. 尝试停止 candidate。
3. 无论 candidate stop 成功与否，都要把 update transaction 标记 rollback、恢复 previous pointer，并记录 failed version，以避免 current pointer 留在 fault candidate。
4. **只有 candidate stop + port release 成功时**，才允许启动 previous version 并执行 restored health check。
5. candidate stop/port release 失败时：
   - 不启动 previous version；
   - 返回 `LauncherStatus.FAILED`，而不是 `ROLLED_BACK`；
   - reason 必须明确包含 candidate stop/port release failure；
   - 让操作人员看到 fail-closed 状态，而不是读取残留 listener 的 health。

restored version 自身启动或 health 失败时继续返回 `FAILED`，保持现有安全语义。

### 5.4 成功 rollback 的真实性要求

只有同时满足以下条件，Launcher 才能返回 `ROLLED_BACK`：

- transaction 已恢复 previous pointer；
- failed registry 已记录 candidate version + manifest hash；
- candidate process tree 已退出；
- application port 在 candidate stop 后真实释放；
- restored process 启动成功；
- restored process 的 health 严格匹配 restored version；
- restored session 有效。

## 6. TDD 验证设计

implementation 必须遵循 RED -> GREEN：

1. **Windows tree-stop RED**：新增测试证明 Windows stop 必须调用 tree terminator，且 target 是原 Popen PID；当前实现应失败。
2. **tree-stop failure RED**：tree terminator 失败时 stop 必须抛异常，不能回落成静默成功。
3. **port-release RED**：process manager stop 后端口仍被占用时 `LocalApplicationRuntime.stop()` 必须失败；端口释放后才成功。
4. **rollback stop-failure RED**：candidate health 失败 + candidate stop 失败时，transaction/current 必须 rollback，但 previous app 不得启动，result 必须是 `FAILED`。
5. **successful rollback regression**：candidate stop 成功、端口释放后，previous app 才启动并返回 `ROLLED_BACK`。
6. 保持现有 launcher/process/update transaction tests 全绿。

实现完成后至少运行：

- `tests/test_launcher_process.py`
- launcher service / update transaction 相关 focused tests
- Board 5 fault/rollback 相关 tests
- Python full suite
- `git diff --check`
- targeted sensitive-shape scan

## 7. 真实 Windows re-acceptance

代码通过后，不覆盖 stable sandbox，也不删除当前失败证据。

创建一个新的 repo-external **RollbackRepairSandbox** 作为修复后验收环境：

- 来源仍是成功 stable 0.5.1 安装；
- channel 通过正式 `CurrentVersion + InstallLayout.save_current()` 设为 beta；
- 使用当前 beta license 的受限 DPAPI state，不在聊天或日志暴露 license key/device token；
- 不复用当前 RollbackSandbox 的 `failed-versions.json`、pending、candidate directory 或 transaction failure state；原失败现场完整保留。

只替换新 RollbackRepairSandbox 中的 Launcher 为本分支 TDD 修复后重新构建的 Launcher；stable sandbox 与 frozen app 0.5.1 bytes 均不修改。

真实重验必须重新经过：

`0.5.1 beta -> update check -> fault 0.5.2-board5bad.1 -> signed full download -> safe extraction -> pointer switch -> candidate health mismatch -> candidate tree fully stopped -> rollback -> restored 0.5.1 listener/path/health/session -> subsequent beta update check`

最后一次 beta update check 必须证明 candidate version 不再被服务端提供，并且证据措辞必须是 **version-level server suppression**。本地 failed registry 仍按 version + manifest hash 记录；不得误写成 Worker 按 manifest hash suppression。

## 8. 外部状态与 gate 边界

本修复设计不授权新的 GitHub/Cloudflare/production mutation。

真实 re-acceptance 复用当前已经存在且已启用的：

- private prerelease `v0.5.2-board5bad.1`
- Worker `rel_board5_bad_052_01`：beta / rollout 100 / enabled=true / paused=false

在修复验收完成前：

- 不修改 fault release assets；
- 不修改 `rel_staging_050/051`；
- 不执行 fault disable；
- 不 cleanup 当前 RollbackSandbox 失败证据；
- 不 push/merge；
- 不触碰 production。

成功完成 rollback re-acceptance 后，仍需要独立 **fault-disable gate** 才能将 `rel_board5_bad_052_01` 恢复为 `enabled=false / paused=true / rollout=100`。

## 9. 非目标

本修复不处理：

- Board 6 license/channel trust-boundary gap；
- GitHub release authorization 模型；
- Windows Job Object 架构升级；
- Launcher 版本号升级；
- app 0.5.1/0.5.2 fault bytes 重建；
- stable sandbox 更新；
- 当前失败 RollbackSandbox 的 cleanup；
- production deployment。

## 10. 完成标准

本修复只有在以下全部成立时才可称为完成：

1. 新增测试先在旧实现上按预期 RED，再在修复后 GREEN；
2. Windows process-tree stop 与 port-release guard 都有自动化覆盖；
3. stop failure 不再能产生 false-positive `ROLLED_BACK`；
4. fresh RollbackRepairSandbox 真实 fault update 完成自动 rollback；
5. rollback 后唯一 18787 listener 路径属于 restored `versions/0.5.1/wechat-cli.exe`；
6. restored health=`0.5.1 / staging-051-20260808.1 / ok / license_session_valid=true`；
7. transaction=`rolled_back`，failure reason 为 candidate health version mismatch；
8. failed registry 记录 candidate version + frozen manifest hash；
9. subsequent beta check 证明 version-level server suppression；
10. stable sandbox 最终恢复并 fresh health/session 通过；
11. full verification、diff check、敏感扫描通过；
12. fault release 仍保持 enabled/unpaused，直到之后独立 disable gate；
13. 无 production、push、merge、cleanup 越权动作。
