# WeChat CLI Board 5 Windows Staging E2E Acceptance Report

> **FINAL ACCEPTANCE / Board 5 accepted complete**
>
> This document is the final Board 5 Task 7 closure report dated 2026-08-12. It records the completed functional/E2E acceptance, the approved Cloud Cleanup Gate, the terminal stable/beta license/device state, and the fresh post-cleanup verification used to close Board 5. Local physical cleanup remains optional and separately gated; it is not a Board 5 acceptance blocker.

日期：2026-08-12
阶段：Board 5 — Windows 真实端到端验收
最终结论：**Board 5 accepted complete. Board 6 remains unstarted.**

## 1. Scope and authorization boundary

Board 5 的目标是在真实 Windows 环境和真实 staging 资源上证明：

- repo-external staging bootstrap 可以从冻结 0.5.0 source 构建并隔离安装；
- 真实 current-user DPAPI license activation 成立；
- 真实 stable `0.5.0 -> 0.5.1` private-release update/download/verify/restart/health 链成立；
- 网络不可达时真实 cached lease 可进入 offline-valid，并对同一真实 DPAPI state 验证 7 天边界与 clock rollback policy；
- 独立 beta fault candidate 可以完成合法下载/验签/解包/切换，因 runtime health mismatch 自动回滚；
- Windows PyInstaller process-tree defect 被真实暴露、TDD 修复并在 fresh sandbox 重验；
- failed-version suppression 的服务端语义被准确证明为 **version-level**；
- fault release 最终回到 disabled/paused。

Board 5 不包含生产上线、main integration、push、merge、后续 Board 6 实现或未经单独授权的物理清理。

2026-08-12 closure audit first completed a read-only/local-doc Phase A, then proceeded only after the separately approved **Board 5 Cloud Cleanup Gate**. The cleanup target set stayed restricted to the two Board 5 stable/beta test licenses and their associated test devices. Phase A itself performed no cloud mutation; the later approved cleanup revoked both Board 5 licenses and unbound exactly their two Board 5 test devices. No JD25, release, GitHub asset/tag, PAT, Cloudflare Secret, production, local-sandbox deletion, push, merge, or history-rewrite action was included.

## 2. Source and Git baselines

### 2.1 Board 4 frozen baseline

Fresh 2026-08-12 read-only verification:

- worktree：`C:\Users\28276\.devspace\worktrees\wechat-cli-1ec755b9`
- branch：`task5/0.5.1-update-validation`
- HEAD：`8c7464f058a9edf520b4c97e02b63835a3c0901c`
- working tree：clean

Board 4 worktree remains frozen and is not a Board 5 cleanup target.

### 2.2 Board 5 branch

Phase A pre-corrective baseline:

- worktree：`C:\Users\28276\.devspace\worktrees\wechat-cli-1ec755b9-46a6ab4b`
- branch：`board5/windows-staging-e2e`
- pre-Phase-A HEAD：`42b9f42ae466ec05dc9eb2177f12a0a79cf3f654`
- pre-Phase-A working tree：clean
- pre-Phase-A last commit：`42b9f42 docs: record board 5 fault disable`

The Phase A corrective docs commit will advance this branch locally; no amend/rebase/reset is permitted or performed.

### 2.3 0.5.0 build-source

Fresh read-only verification:

- worktree：`C:\Users\28276\.devspace\worktrees\wechat-cli-1ec755b9-54a1291f`
- detached HEAD：`a579a25cb7f16e6fdf88d618252b4a5cbffef53d`
- working tree：clean

This worktree is retained as immutable 0.5.0 app/Launcher source provenance.

### 2.4 0.5.0 hotfix-source

Fresh read-only verification:

- worktree：`C:\Users\28276\.devspace\worktrees\wechat-cli-5827e12d`
- detached HEAD：`0dd2485e5a834c8dea511dd630fea3ba0abcc55a`
- working tree：clean
- retained commit chain:
  - `6753a24 fix: normalize launcher file urls on windows`
  - `143c93c fix: avoid launcher before-load deadlock`
  - `0dd2485 fix: identify launcher update downloads`

This detached worktree records the frozen-0.5.0 Launcher-side acceptance hotfix provenance used during the real stable E2E. It is Board 5 evidence and is retained; it is not deleted during closure.

### 2.5 main and release repository

Fresh read-only verification:

- main path：`D:\use_as_desktop\Wechat__CLI\wechat-cli`
- main HEAD：`a579a25cb7f16e6fdf88d618252b4a5cbffef53d`
- main status：only `?? NUL`
- `NUL` remains intentionally untracked and untouched
- release repo path：`D:\use_as_desktop\Wechat__CLI\wechat-cli-releases`
- release repo HEAD：`2b9fa385b86df83f7968239a1029d4d59f020027`
- release repo working tree：clean

## 3. Bootstrap and launcher-config provenance

The Board 5 staging bootstrap was built only after its independent build gate. Recorded and previously verified provenance:

- 0.5.0 source：detached `a579a25`
- application version：`0.5.0`
- Launcher version：`0.1.0`
- real 0.5.0 app size/SHA-256：`14484577` / `fe70396252d4cab1cf355e34bb7479233ba2fd1d0ba1866132ab9e0c9f19f971`
- initial Launcher size/SHA-256：`20153234` / `f45d3bb655193e74f433edd38a50dfbdf7b96a3820ad5929a37405d48bb49df1`
- staging launcher config SHA-256：`5002d155f3968a0d44a20b070e1b28ce569497b88d9748ba8a606b0201395e9d`
- config channel：`stable`
- loopback port：`18787`
- approved release key ID：`release-key-staging-01`
- approved lease key ID：`lease-key-staging-01`
- bootstrap ZIP size/SHA-256：`34192856` / `5985fc2e835ab7e45da227f2d62770bc248ecf09525b511fa76e3bf3ae082d8d`
- package manifest historical build label：`0.5.0-local-20260805.1`
- frozen runtime build observation：`dev`

The config was generated from the repo-external public-key registry and reloaded through production `LauncherConfig.load()`; public-key values are not recorded here.

The fixed Board 4 0.5.0 update ZIP was never overwritten. Fresh Phase A verification:

- path：`D:\use_as_desktop\Wechat__CLI\wechat-cli\dist\wechat-cli-app-0.5.0-win-x64.zip`
- size：`14291197`
- SHA-256：`406b72c14ad186141f373087595f7723e143b9638bf298fde23b6bb0ae057523`

## 4. Stable Board 5 license and isolated installation

Fresh final Admin CLI post-cleanup state:

- license ID：`lic_NGcs-flk8nRqfkbm5TFqewHV`
- hint：`9C4A`
- channel：`stable`
- status：`revoked`
- maximum devices：`1`
- active devices：`0`
- revision：`2`
- associated Board 5 device safe hint：`19b980ca5169`
- associated device terminal state：`unbound`
- `unbound_at=2026-08-12T08:10:31.452Z`

Historical creation audit evidence:

- action：`license.batch_create`
- request ID：`28e0e326-805d-4bff-add0-ab25fcc43400`

The complete license key remains only in the restricted repo-external Board 5 CSV and is not recorded in this report.

The isolated stable root exists and still carries a valid `.board5-acceptance-root` marker. Fresh Phase A current state:

- channel：`stable`
- current version：`0.5.1`
- previous version：`0.5.0`
- manifest SHA-256：`be111f0a786821319fb96f82f1748b4a75003b7c5fb296c48ec87b3355a3fd62`

Real activation used the Launcher UI and current-user DPAPI; acceptance verified the local state was a `WCLIC1` protected envelope rather than plaintext JSON. No DPAPI plaintext, complete license, device token, MachineGuid, or SID is recorded here.

## 5. Stable 0.5.0 -> 0.5.1 real update acceptance

The real isolated 0.5.0 application first passed health with product `wechat-cli-web`, version `0.5.0`, status `ok`, and a valid license session.

The stable update then used the real installed application/Launcher path, staging Worker, short-lived download ticket, private GitHub release asset, Ed25519 manifest verification, SHA-256 verification, safe extraction, restart/apply and health verification.

Frozen 0.5.1 evidence:

- Worker release：`rel_staging_051`
- version：`0.5.1`
- channel：`stable`
- package size：`14268929`
- package SHA-256：`0ddbb0b402cc9d98ed001391c1a618527d165e328a1f4f1534d80e6b984956c0`
- manifest SHA-256：`be111f0a786821319fb96f82f1748b4a75003b7c5fb296c48ec87b3355a3fd62`
- extracted EXE size/SHA-256：`14483951` / `dbbdf8ec70ddcf8d36145f099b0cb4ce3292c61e205c3ac7ae4db01fbc8907d1`
- transaction final state：`committed`
- current：`0.5.1`
- previous：`0.5.0`

Fresh Phase A stable health:

- status：`ok`
- product：`wechat-cli-web`
- version：`0.5.1`
- build ID：`staging-051-20260808.1`
- config loaded：`true`
- license session valid：`true`
- core modules：server/storage/routes all `ok`

## 6. Private GitHub Draft visibility blocker and resolved distribution model

Board 5 discovered a real distribution blocker rather than treating Draft metadata as equivalent to a downloadable release.

### 6.1 v0.5.1

Historical blocker:

- the private `v0.5.1` Release was initially Draft;
- the real updater path reached GitHub but received upstream 403 for the Draft asset;
- downloader/Worker credential-leak issues were separately fixed (`a771ab4`, `8a1fdb0`) before the visibility problem was isolated.

Resolution under a separate publish gate:

- Release database ID：`367353041`
- current `draft=false`
- current `prerelease=false`
- target：`main`
- real `refs/tags/v0.5.1` fresh read-only target：`2b9fa385b86df83f7968239a1029d4d59f020027`

Fresh asset state:

- package Asset ID `506974337`, size `14268929`, digest `sha256:0ddbb0b402cc9d98ed001391c1a618527d165e328a1f4f1534d80e6b984956c0`
- manifest Asset ID `506974359`, size `911`, digest `sha256:be111f0a786821319fb96f82f1748b4a75003b7c5fb296c48ec87b3355a3fd62`
- signature Asset ID `506974373`, size `64`, digest `sha256:8f602142ffb380004282028b46bba1472d9b842531f3e67effbe268a5bfd0cec`

### 6.2 v0.5.0

Fresh read-only state:

- Release database ID：`365469593`
- `draft=true`
- `prerelease=false`
- target：`main`
- no real Git ref for `refs/tags/v0.5.0` (fresh 404), consistent with the retained Draft evidence model

Fresh assets:

- package Asset ID `502527074`, size `14291197`, digest `sha256:406b72c14ad186141f373087595f7723e143b9638bf298fde23b6bb0ae057523`
- manifest Asset ID `502527130`, size `911`, digest `sha256:6f76cbc3052bea1e25fb8ecf53b5d1a88b16b27c40ebd341388d25e9514c1fed`
- signature Asset ID `502527173`, size `64`, digest `sha256:2c07efc7faf3c47f2303059ae53f8d4a429ef85b6eb057804f84682f39ff4f89`

## 7. Offline acceptance

The preserved OfflineSandbox exists with a valid marker and fresh current state:

- channel：`stable`
- current：`0.5.1`
- previous：`0.5.0`
- manifest SHA：`be111f0a786821319fb96f82f1748b4a75003b7c5fb296c48ec87b3355a3fd62`

The real acceptance used an unreachable local HTTPS API authority while preserving the same release/lease keys, channel, port and fingerprint salt. The real Launcher successfully used the same current-user DPAPI lease and started 0.5.1 in `offline_valid` state.

Deterministic checks against that same real DPAPI state proved:

- lease key ID：`lease-key-staging-01`
- exact duration：`604800` seconds
- `offline_until - 1s` allowed
- `offline_until + 1s` expired
- 4-minute clock correction allowed
- 10-minute rollback rejected with `OFFLINE_LEASE_DENIED`

Windows system time was not changed.

## 8. Beta license and channel alignment

Fresh final Admin CLI post-cleanup state:

- license ID：`lic_XUMv4Qor5S1WXr-lWOTd9L1m`
- hint：`WYW2`
- channel：`beta`
- status：`revoked`
- maximum devices：`1`
- active devices：`0`
- revision：`2`
- associated Board 5 device safe hint：`7ecd4bc40420`
- associated device terminal state：`unbound`
- `unbound_at=2026-08-12T08:10:34.661Z`

Historical creation audit:

- action：`license.batch_create`
- request ID：`be22ec6c-d222-4a69-bda1-6750c592b4f5`

The preserved original RollbackSandbox and fresh RollbackRepairSandbox both exist with valid markers. Fresh current state for both is beta `0.5.1`, previous `0.5.0`, with the frozen `be111f...` manifest SHA.

Board 5 explicitly aligned beta license + beta current/request channel and did not exploit the Worker channel trust-boundary gap.

## 9. Fault release lifecycle

Fault candidate:

- release ID：`rel_board5_bad_052_01`
- version：`0.5.2-board5bad.1`
- channel：`beta`
- package size：`14268937`
- package SHA-256：`96111ad0fff5827a93e81d826de150ea616eb4c907b20ada9a420967f8ffaf82`
- signed manifest SHA-256：`2d29da32cb05e1a373ddab58725f2810e1d81489ad769a0ed6094458eb71fdaa`
- package executable bytes intentionally remain the known-good 0.5.1 EXE bytes; the declared candidate version creates a deterministic runtime health-version mismatch.

Lifecycle accepted under separate gates:

1. local prepare/sign only;
2. private GitHub Draft + three assets;
3. Worker register disabled/paused;
4. fault enable;
5. Draft visibility blocker discovered;
6. publish as private prerelease;
7. real fault download/apply/rollback attempt;
8. process-tree defect discovered;
9. TDD process-tree repair;
10. fresh RollbackRepairSandbox real re-acceptance;
11. version-level suppression verification;
12. final fault disable/paused.

Fresh Phase A Worker state:

- `enabled=false`
- `paused=true`
- rollout=`100`
- package/manifest hashes unchanged

Fresh GitHub state:

- Release database ID：`368572125`
- `draft=false`
- `prerelease=true`
- target：`main`
- real `refs/tags/v0.5.2-board5bad.1` target：`2b9fa385b86df83f7968239a1029d4d59f020027`

Fresh assets:

- package Asset ID `510139118`, size `14268937`, digest `sha256:96111ad0fff5827a93e81d826de150ea616eb4c907b20ada9a420967f8ffaf82`
- manifest Asset ID `510139294`, size `957`, digest `sha256:2d29da32cb05e1a373ddab58725f2810e1d81489ad769a0ed6094458eb71fdaa`
- signature Asset ID `510139303`, size `64`, digest `sha256:912b457f0149cdcc0d33ad46f4c937bf2fd6a042e2a13cb5ad5002081ae48a58`

## 10. First rollback failure and process-tree root cause

The first real rollback attempt correctly reached the intended fault path:

- full signed fault package downloaded and verified;
- safe extraction succeeded;
- candidate pointer switched;
- health failed because the candidate declared `0.5.2-board5bad.1` but the EXE reported `0.5.1`;
- transaction state became `rolled_back`;
- current pointer restored to `0.5.1`;
- failed registry recorded the candidate.

However, that first acceptance **failed** at the real Windows process boundary. The PyInstaller child from the candidate survived after the Popen parent exited and continued listening on port 18787. The restored 0.5.1 process could not obtain the port, so health was read from the residual candidate path. This failure remains part of Board 5 history and is not erased from the acceptance record.

Root cause was traced to:

- `ApplicationProcessManager.stop()` terminating only the Popen parent;
- no Windows process-tree termination contract;
- no bounded port-release verification;
- rollback orchestration previously tolerating candidate-stop failure before attempting restored startup.

## 11. TDD repair and fresh rollback re-acceptance

Repair commit:

- `29aba6bc0c8469dc8b5dc512d6831c5385246431`
- title：`fix: stop windows launcher process trees`

The repair added:

- Windows `taskkill.exe /PID <pid> /T /F` tree termination with `shell=False`;
- bounded loopback port-release verification;
- fail-closed rollback orchestration when candidate stop fails.

RED tests first demonstrated the missing tree-stop/port-release/stop-failure semantics; GREEN verification then passed.

Recorded repaired Launcher:

- size：`20168420`
- SHA-256：`a9ae3633f96d08880f1ab4a2e45c946a5d9733a9dd2ed12eabb11acf4c1d1ef7`

Fresh RollbackRepairSandbox real acceptance proved:

- fault full download hashes remained frozen;
- real apply transaction ended `rolled_back` for the expected candidate health version mismatch;
- candidate process count after rollback was zero;
- the sole restored listener belonged to RollbackRepairSandbox `versions/0.5.1/wechat-cli.exe`;
- health was `0.5.1 / staging-051-20260808.1 / ok / license_session_valid=true`;
- local failed registry recorded candidate version + frozen manifest hash;
- subsequent beta update check sent the failed version and returned no update.

The accurate service-side conclusion is **version-level server suppression**. The local registry still keys on `version + manifest_sha256`; the Worker does not provide manifest-hash-level suppression.

## 12. Current Worker release snapshot

Fresh 2026-08-12 Admin CLI read-only state:

### `rel_staging_050`

- version：`0.5.0`
- channel：`stable`
- enabled=`true`
- paused=`false`
- rollout=`100`
- package size：`14291197`
- package SHA：`406b72c14ad186141f373087595f7723e143b9638bf298fde23b6bb0ae057523`
- manifest SHA：`6f76cbc3052bea1e25fb8ecf53b5d1a88b16b27c40ebd341388d25e9514c1fed`

### `rel_staging_051`

- version：`0.5.1`
- channel：`stable`
- enabled=`true`
- paused=`false`
- rollout=`100`
- package size：`14268929`
- package SHA：`0ddbb0b402cc9d98ed001391c1a618527d165e328a1f4f1534d80e6b984956c0`
- manifest SHA：`be111f0a786821319fb96f82f1748b4a75003b7c5fb296c48ec87b3355a3fd62`

### `rel_board5_bad_052_01`

- version：`0.5.2-board5bad.1`
- channel：`beta`
- enabled=`false`
- paused=`true`
- rollout=`100`
- package size：`14268937`
- package SHA：`96111ad0fff5827a93e81d826de150ea616eb4c907b20ada9a420967f8ffaf82`
- manifest SHA：`2d29da32cb05e1a373ddab58725f2810e1d81489ad769a0ed6094458eb71fdaa`

`rel_staging_050` and `rel_staging_051` are not Board 5 cleanup targets and must remain unchanged.

## 13. Cloud cleanup completion

The Board 5 Cloud Cleanup Gate was explicitly approved on 2026-08-12. The target set remained restricted to the two Board 5 test licenses and their associated Board 5 test devices.

Final live Admin readback proves the cleanup reached its intended terminal state:

- stable Board 5 license `lic_NGcs-flk8nRqfkbm5TFqewHV` / hint `9C4A`: `revoked`, revision `2`, active devices `0`;
- stable Board 5 device safe hint `19b980ca5169`: `unbound`, `unbound_at=2026-08-12T08:10:31.452Z`;
- beta Board 5 license `lic_XUMv4Qor5S1WXr-lWOTd9L1m` / hint `WYW2`: `revoked`, revision `2`, active devices `0`;
- beta Board 5 device safe hint `7ecd4bc40420`: `unbound`, `unbound_at=2026-08-12T08:10:34.661Z`.

The two device unbind operations were executed by the user through the existing Admin CLI after the agent-side environment blocked the same exact writes before execution. The subsequent fresh Admin readback is the authoritative completion evidence. No D1-direct-write workaround, credential extraction, or broader mutation was used.

Board 4 license was explicitly excluded and remains unchanged:

- `lic_ptrqZVAxh2NI8h5RM6gnGiiL` / hint `JD25`
- channel：`stable`
- status：`active`
- active devices：`3`
- revision：`3`

The Admin success response for license-status updates does not expose an audit request ID. A read-only Wrangler/D1 audit query was attempted, but the non-interactive shell had no `CLOUDFLARE_API_TOKEN`; it failed closed without reading or expanding any credential. The report therefore records the exact safe post-state evidence and this request-ID limitation.

JD25, `rel_staging_050`, `rel_staging_051`, GitHub releases/assets, PAT, Cloudflare Secrets and local evidence roots remained outside the cleanup target set.

Fresh post-cleanup read-only reconcile confirmed:

- JD25 remains `active`, revision `3`, with 3 active + 1 unbound historical device rows;
- `rel_staging_050` remains enabled/unpaused/rollout 100 with frozen package SHA `406b72c...`;
- `rel_staging_051` remains enabled/unpaused/rollout 100 with frozen package SHA `0ddbb0b...`;
- `rel_board5_bad_052_01` remains disabled/paused/rollout 100 with frozen package/manifest hashes;
- GitHub `v0.5.0` remains Draft, `v0.5.1` remains published private, and the fault release remains private prerelease; all three sets of asset sizes/digests are unchanged;
- Board 4 remains `8c7464f` clean; build-source remains detached `a579a25` clean; hotfix-source remains detached `0dd2485` clean; main remains `a579a25 + ?? NUL`; release repo remains `2b9fa38` clean;
- fixed 0.5.0 ZIP remains exactly 14291197 bytes / SHA-256 `406b72c14ad186141f373087595f7723e143b9638bf298fde23b6bb0ae057523`;
- the existing stable loopback process still reports 0.5.1 / `staging-051-20260808.1` / ok / `license_session_valid=true`; this existing-session observation is not used to override the authoritative revoked license state.

## 14. Board 6 risk handoff

Board 6 remains **unstarted**. The following risks are recorded for later independent brainstorming/design/security review only:

1. **Update channel trust boundary** — Worker `/v1/updates/check` does not currently enforce `license.release_channel == request.channel`.
2. **Failed-version suppression granularity** — local registry uses `version + manifest_sha256`, but `failed_versions` sent to Worker contains only version; service-side suppression is version-level.
3. **GitHub Draft visibility semantics** — real E2E proved private Draft assets are not a valid direct distribution model for the current updater; staging/prod visibility policy, Draft vs published private responsibilities, tag timing and `make_latest` policy need formal definition.
4. **GitHub release read credential** — staging uses dedicated fine-grained PAT `GITHUB_RELEASE_READ_TOKEN`; lifecycle, least privilege, rotation, backup/recovery, production replacement and long-lived-PAT strategy need review. The real token must never enter docs.
5. **Worker redirect trust boundary** — initial URL is restricted to `https://api.github.com`, redirects are manual, and Authorization is removed before redirect; redirect targets currently require HTTPS but are not otherwise host-allowlisted.
6. **Packaging production dependency** — `scripts/package_windows_app.py` directly imports `scripts.board5_common.assert_outside_repository`, creating a generic packaging dependency on a Board 5 acceptance helper.
7. **pywebview internal/backend API dependency** — `LauncherWindow._current_url_before_load()` uses `window.gui.get_current_url(uid)` to avoid the `before_load` public-API deadlock; real Windows behavior is accepted, but compatibility/support and version-lock/integration coverage require review.
8. **Source integration debt** — main remains at `a579a25`; Board 5 branch contains real product fixes including `56d065e`, `706bcbe`, `a771ab4`, `8a1fdb0`, `29aba6b` and related Worker/packaging changes. A separate integration strategy is required before Board 6; no merge/push is authorized now.

## 15. Fresh final post-cleanup verification

The required final verification was freshly rerun on 2026-08-12 **after** both Board 5 devices were unbound.

### Python

Command:

`python -m unittest discover -s tests`

Result:

- `Ran 529 tests`
- `OK (skipped=2)`
- 527 passed / 2 expected platform skips / 0 failures

The output still includes the expected legacy/full-build `missing pywebview` fail-closed scenario inside test coverage; the full suite passed.

### Worker

Commands:

- `npm run typecheck`
- `npm test -- --run`

Results:

- typecheck：PASS
- Vitest：3 files passed
- tests：21 passed

### Cloud terminal state and release invariants

Fresh Admin readback after cleanup:

- stable Board 5 license `9C4A`: `revoked`, revision 2, active devices 0; associated Board 5 device `unbound`;
- beta Board 5 license `WYW2`: `revoked`, revision 2, active devices 0; associated Board 5 device `unbound`;
- Board 4 `JD25`: still `active`, revision 3, active devices 3;
- `rel_staging_050`: enabled/unpaused/rollout 100, frozen package SHA unchanged;
- `rel_staging_051`: enabled/unpaused/rollout 100, frozen package SHA unchanged;
- `rel_board5_bad_052_01`: disabled/paused/rollout 100, frozen package/manifest hashes unchanged.

Fresh GitHub readback:

- `v0.5.0` / Release ID `365469593`: still Draft; package/manifest/signature asset IDs, sizes and digests unchanged; no real `refs/tags/v0.5.0` ref exists;
- `v0.5.1` / Release ID `367353041`: published private release, not prerelease; all three asset IDs/sizes/digests unchanged; tag still targets `2b9fa385b86df83f7968239a1029d4d59f020027`;
- `v0.5.2-board5bad.1` / Release ID `368572125`: private prerelease; all three asset IDs/sizes/digests unchanged; tag still targets `2b9fa385b86df83f7968239a1029d4d59f020027`.

### Git and immutable evidence

Fresh final read-only verification:

- Board 4 worktree `8c7464f058a9edf520b4c97e02b63835a3c0901c`, clean — including after the user ran the Admin cleanup commands from that directory;
- build-source detached `a579a25cb7f16e6fdf88d618252b4a5cbffef53d`, clean;
- hotfix-source detached `0dd2485e5a834c8dea511dd630fea3ba0abcc55a`, clean;
- main `a579a25cb7f16e6fdf88d618252b4a5cbffef53d` with only the intentionally retained `?? NUL`;
- release repo `2b9fa385b86df83f7968239a1029d4d59f020027`, clean;
- fixed 0.5.0 ZIP remains exactly `14291197` bytes / SHA-256 `406b72c14ad186141f373087595f7723e143b9638bf298fde23b6bb0ae057523`.

The pre-existing stable loopback process still reports `0.5.1 / staging-051-20260808.1 / ok / license_session_valid=true`. This is treated only as retained local-process evidence; the authoritative cloud state is the revoked license plus unbound device, and no new online validation was performed after cleanup.

Final closure diff/safety review also passed: `git diff --check` returned clean; the four closure documents contained zero complete `dev_...` device-ID shapes and zero real credential/private-key/complete-license/device-token shapes.

## 16. Actions not performed during Board 5 closure

The closure did **not** perform:

- any JD25 mutation;
- any `rel_staging_050` or `rel_staging_051` mutation;
- any fault release mutation after the previously authorized final fault-disable gate;
- GitHub release deletion, asset deletion/reupload, publish/unpublish, or tag modification;
- PAT deletion/rotation;
- Cloudflare Secret mutation;
- production mutation;
- Windows system-clock mutation;
- main modification or `NUL` deletion/commit/rename;
- Board 4/build-source/hotfix-source deletion or modification;
- Board 5 local sandbox/artifact physical cleanup;
- Git push;
- Git merge;
- history rewrite.

The only Cloud Cleanup Gate writes were the already-approved Board 5 stable/beta license revocations and their two associated test-device unbind operations.

## 17. Closure status

Functional/E2E acceptance is complete and preserved, including the initial rollback failure, root-cause analysis, TDD repair and fresh rollback re-acceptance. Cloud cleanup is complete, and the required fresh post-cleanup verification passed.

**Board 5 accepted complete.**

Board 6 remains **unstarted**. The next program action is only an independent Board 6 brainstorming/design gate that incorporates the eight risk-handoff items above; this report does not authorize Board 6 implementation, production mutation, merge, push, tag modification, credential rotation, or deployment.

Local physical cleanup is optional and remains a **separate deletion gate**. The marked Board 5 roots/artifacts are retained pending optional separately authorized local cleanup; this retention does not block Board 5 acceptance.
