# Board 6 Source Integration Provenance

Date: 2026-08-12
Gate: B6-G0 Source Integration Gate
Branch: `board6/security-delivery-preparation`
Worktree: `C:\Users\28276\.devspace\worktrees\wechat-cli-f3860a02`
Frozen main base: `a579a25cb7f16e6fdf88d618252b4a5cbffef53d`
Board 5 accepted-complete evidence HEAD: `67d3dec0fd1c4a02c87be1ab79c4f78ea63f49d6`

## 1. Purpose

Board 6 must not merge Board 5 wholesale. Board 5 contains accepted product fixes, local acceptance tooling, sandbox helpers, governance records, and historical evidence. This document freezes the local source-integration decision before replaying product changes onto a fresh branch from the exact frozen main base.

No entry in this document authorizes cloud, staging, production, credential, signing, release, push, or main-merge operations.

## 2. Input-state note

Before the Board 6 worktree was created, the Board 5 worktree remained at exact accepted-complete HEAD `67d3dec0fd1c4a02c87be1ab79c4f78ea63f49d6`. Its only working-tree difference was the two user-approved Board 6 design/plan drafts created during the preceding design gate; there was no tracked product-code drift.

Their frozen pre-integration SHA-256 values were:

- `docs/superpowers/specs/2026-08-12-board-6-security-delivery-preparation-design.md` -> `032b23fd485c39700ffcb5d319832b78c6812edc38afc99d4696a4aeaa9775d0`
- `docs/superpowers/plans/2026-08-12-board-6-security-delivery-preparation.md` -> `9faa73f733fa714a49accc91b532471e097ea28f8224d6317908ad57a0261b89`

The main checkout was verified at exact `a579a25cb7f16e6fdf88d618252b4a5cbffef53d` with only the intentionally preserved `?? NUL` entry. The new Board 6 worktree was created from that exact main commit and passed the frozen-main test baseline before source replay: Python 476 run / 2 expected skips / 0 failures, Worker typecheck PASS, Vitest 17/17.

## 3. Direct product candidates

### 3.1 `84b8a99fda1210d1ee02db92afe2444d37df10c9` — `feat: add 0.5.1 update-only packaging`

Classification: **direct product candidate**.

Files and rationale:

- `npm/scripts/build.py` — adds app-only build selection required by the accepted 0.5.1 product/update path.
- `scripts/package_windows_app.py` — adds update-only packaging behavior needed by later release/update work.
- `scripts/verify_local_update_artifacts.py` — strengthens reusable release-artifact verification.
- `wechat_cli/version.py`, `pyproject.toml`, `CHANGELOG.md` — carries the accepted 0.5.1 product/version baseline.
- `tests/test_verify_local_update_artifacts.py`, `tests/test_windows_packaging.py`, `tests/test_version_metadata.py` and related client/main tests — product regression evidence for the above behavior.

This commit is based directly on frozen main `a579a25...`, so it is the intended first replay.

### 3.2 `56d065eeb739076fc4511a8ce1dff494577df500` — `fix: normalize launcher file urls on windows`

Classification: **direct product candidate**.

Files and rationale:

- `wechat_cli/launcher/webview.py` — Windows Launcher navigation/security compatibility fix exposed by real Board 5 UI acceptance.
- `tests/test_launcher_ui_contract.py` — regression contract for the normalization behavior.

The change is product-facing and not acceptance-tool-specific.

### 3.3 `706bcbeb5bd34a86f08ba14f41b454c8923a4f10` — `fix: avoid launcher before-load deadlock`

Classification: **direct product candidate**.

Files and rationale:

- `wechat_cli/launcher/webview.py` — prevents the real Windows `before_load` deadlock/self-destroy behavior found during Board 5.
- `tests/test_launcher_ui_contract.py` — freezes the pre-load URL lookup contract.

Board 6 C-domain design explicitly carries this implementation forward while later isolating/pinning the pywebview backend dependency.

### 3.4 `a771ab424b3182385b9840206989d7ee0d57f61c` — `fix: identify launcher update downloads`

Classification: **direct product candidate**.

Files and rationale:

- `wechat_cli/update/download.py` — adds the accepted project User-Agent to updater downloads.
- `tests/test_update_download.py` — proves the transport identity contract.

The change is required by the real update path and is independent of Board 5 sandbox tooling.

### 3.5 `8a1fdb04964bd5281cc2c3c23a122c6f336a5069` — `fix: proxy private release asset redirects`

Classification: **temporary direct product candidate during GitHub -> R2 migration**.

Files and rationale:

- `services/license-update-worker/src/updates.ts` — manual redirect handling, initial GitHub-host validation, and Authorization stripping across redirects.
- `services/license-update-worker/test/updates.test.ts` — regression coverage for credential non-forwarding and redirect behavior.

Board 6 A3/A4 plans to migrate runtime package distribution to R2, but this adapter remains necessary for legacy GitHub-backed rows until that migration is accepted.

### 3.6 `c4d44ee9b1613a31f66fe078ef5656edf6d6cf84` — `test: expose safe release upstream status`

Classification: **direct product/security-observability candidate**.

Files and rationale:

- `services/license-update-worker/src/updates.ts` — surfaces only safe GitHub upstream HTTP status in error details.
- `services/license-update-worker/test/updates.test.ts` — proves no URL/header/token is exposed.

This is retained as bounded operational evidence while the legacy GitHub backend exists.

### 3.7 `fc667cfdf7f1838bf7dad821e4e1854ce4b05f4f` — `test: log safe release upstream failures`

Classification: **direct product/security-observability candidate**.

Files and rationale:

- `services/license-update-worker/src/updates.ts` — logs a minimal structured upstream failure event containing safe status only.
- `services/license-update-worker/test/updates.test.ts` — verifies the logging boundary.

The implementation is deliberately retained only while legacy GitHub runtime transport remains supported.

### 3.8 `29aba6bc0c8469dc8b5dc512d6831c5385246431` — `fix: stop windows launcher process trees`

Classification: **direct critical product candidate**.

Files and rationale:

- `wechat_cli/launcher/process.py` — Windows process-tree termination and bounded port-release verification.
- `wechat_cli/launcher/service.py` — fail-closed rollback orchestration when candidate stop fails.
- `tests/test_launcher_process.py`, `tests/test_launcher_service.py` — regression coverage for the real Board 5 orphan-process rollback failure.

This repair is mandatory product behavior for any later signed-update acceptance.

## 4. Explicit non-product / non-wholesale candidates

### 4.1 `ad753f62a39faf94bbdd89ee03f8f7fd065c57ba` — `test: add board 5 acceptance boundaries`

Classification: **do not wholesale integrate**.

Files:

- `scripts/board5_common.py`
- `tests/test_board5_common.py`
- Board 5 roadmap/project-state evidence updates.

Reason: this commit creates a Board 5 acceptance-specific helper and governance state. Production packaging must not depend on a historical board helper. The generic path-safety behavior is handled separately by Board 6 D1 work rather than importing the whole commit.

### 4.2 `538ae3a4ccb63bc159fbb15f760c7cc7f231f306` — `test: add board 5 staging acceptance tools`

Classification: **do not wholesale integrate**.

Files:

- `scripts/board5_offline_acceptance.py`
- `scripts/board5_prepare_fault_package.py`
- `scripts/board5_prepare_launcher_config.py`
- `scripts/board5_prepare_sandbox.py`
- their Board 5-specific tests.

Reason: these files exist to reproduce/accept Board 5 staging/offline/fault sandboxes. They are evidence tooling, not product runtime/build dependencies.

### 4.3 `52e07b8c6752c3ba671a6407b32c140ec68a48d9` — `test: add board 5 update download probe`

Classification: **do not wholesale integrate**.

Files:

- `scripts/board5_update_download_probe.py`
- `tests/test_board5_update_download_probe.py`

Reason: the probe is specific to Board 5 live acceptance and its frozen staging path. Product transport changes from `8a1fdb0/c4d44ee/fc667cf` are integrated directly instead.

### 4.4 `28415ca325164c5d40939e75c1b0743259322a4b` — `feat: add isolated bootstrap-only packaging`

Classification: **selective behavior port only; do not blind cherry-pick**.

Files:

- `scripts/package_windows_app.py`
- `tests/test_windows_packaging.py`

Reason: the generic bootstrap-only packaging behavior is useful, but the commit's parent includes the Board 5 acceptance helper lineage. Board 6 will reconstruct/port the reusable behavior with production-oriented tests while removing the `package_windows_app.py -> board5_common` dependency. This avoids importing acceptance-only ownership into the production packaging path.

## 5. Replay rules

1. Replay only the eight direct product candidates listed in section 3, in the approved order.
2. Inspect each cherry-pick diff before moving forward.
3. Run the commit-relevant focused tests after each replay.
4. If a conflict or failed focused test reveals an unapproved dependency on an intermediate Board 5 commit, stop and classify that dependency before adding anything else.
5. Do not resolve a dependency by merging the Board 5 branch or by cherry-picking an acceptance-only commit.
6. `28415ca` is not part of the blind replay sequence; reusable behavior is deferred to the separately planned generic packaging cleanup.
7. No push, main merge, cloud/staging/production mutation, credential operation, signing operation, or release operation is authorized by this provenance record.
