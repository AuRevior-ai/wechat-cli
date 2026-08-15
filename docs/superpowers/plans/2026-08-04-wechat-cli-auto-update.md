# WeChat CLI Auto-Update and Licensing Implementation Plan

> **Historical construction plan:** This file records the intended implementation steps at the time. Its unchecked boxes are not the current project progress. Read [`docs/PROJECT_STATE.md`](../../PROJECT_STATE.md) and the relevant specialist roadmap for current status.

## Final result

- Commits: `036cec5`, `0802e55`, `370a9d9`, `ef9e0e9`, and `e36ab47`.
- Delivered the 0.5.0 licensing system, Launcher, signed update and rollback flow, Cloudflare Worker, administrator/release CLIs, Windows packaging, and staging configuration.
- Local acceptance is recorded in [`docs/deployment/2026-08-05-local-finalization-report.md`](../../deployment/2026-08-05-local-finalization-report.md).
- Later cloud and private-release progress belongs to [`docs/deployment/authorized-update-roadmap.md`](../../deployment/authorized-update-roadmap.md) and the active board-4 plan. The unchecked implementation boxes below are historical construction steps, not a current completion measure.

> **Execution mode:** The user approved the written design and authorized autonomous local implementation. Work task-by-task, preserve unrelated local changes, and do not create external cloud resources until the local implementation and staging prerequisites are ready.

**Goal:** Deliver a Windows x86-64 Demo with permanent licenses, up to three devices, seven-day offline leases, a WebView2 launcher, signed background updates, versioned installs, health checks, automatic rollback, administrator/release CLIs, and a real staging path for Cloudflare plus private GitHub Releases.

**Architecture:** Add a thin Python launcher and shared protocol package beside the existing WeChat CLI application. The launcher owns DPAPI state, online/offline authorization, update download, version switching, health checks, and rollback. The application validates a one-time launch session and exposes health, license, update, device, and diagnostic UI/API surfaces. A separate TypeScript Worker service owns license/device/update APIs and D1/R2 persistence. Local tooling creates licenses and signed releases.

**Tech stack:** Python 3.10+, Click, PyCryptodome, `unittest`, stdlib HTTP/ZIP/process primitives, Windows DPAPI/WebView2 integration, TypeScript Cloudflare Workers, D1, R2, GitHub Releases, Ed25519, AES-GCM, SHA-256, PyInstaller.

---

## Task 0: Preserve the baseline and freeze the approved design

**Files:**
- Modify: `docs/superpowers/specs/2026-08-04-wechat-cli-auto-update-design.md`
- Create: `docs/superpowers/plans/2026-08-04-wechat-cli-auto-update.md`
- Inspect only: `wechat_cli/core/invite_stats.py`
- Inspect only: `tests/test_invite_stats.py`

- [x] Record the design as approved and implementation-authorized.
- [x] Record the existing uncommitted `invite_stats` files and exclude them from auto-update edits.
- [ ] Run the current full Python test suite and record the baseline count.
- [ ] Record the current package/build commands and Windows package layout.

## Task 1: Introduce shared version, protocol, and error contracts

**Files:**
- Create: `wechat_cli/version.py`
- Create: `wechat_cli/update/__init__.py`
- Create: `wechat_cli/update/errors.py`
- Create: `wechat_cli/update/models.py`
- Create: `wechat_cli/update/versioning.py`
- Create: `tests/test_update_models.py`
- Create: `tests/test_update_versioning.py`
- Modify: `wechat_cli/main.py`
- Modify: `scripts/package_windows_app.py`

- [ ] Add failing tests for normalized semantic-version parsing and ordering.
- [ ] Add failing tests for manifest parsing, required fields, platform/architecture/product checks, stable channel defaults, and unknown schema rejection.
- [ ] Add stable machine-readable update/license error codes.
- [ ] Centralize application version and product/build metadata.
- [ ] Replace duplicate version literals with the shared source.
- [ ] Run focused tests, then full regression tests.

## Task 2: Add cryptographic primitives and signed manifest verification

**Files:**
- Create: `wechat_cli/update/crypto.py`
- Create: `wechat_cli/update/manifest.py`
- Create: `tests/test_update_crypto.py`
- Create: `tests/test_update_manifest.py`
- Modify: `pyproject.toml` only when a missing dependency is proven necessary.

- [ ] Add failing Ed25519 verification tests using fixed test vectors.
- [ ] Add failing SHA-256 package verification tests.
- [ ] Verify signatures against the original UTF-8 manifest bytes, not reserialized JSON.
- [ ] Support trusted key IDs and reject unknown key IDs.
- [ ] Reject product, platform, architecture, entrypoint, and internal-version mismatches.
- [ ] Keep test private keys under test fixtures only and scan for accidental production-like secrets.

## Task 3: Add safe package extraction and prepared-update state

**Files:**
- Create: `wechat_cli/update/package.py`
- Create: `wechat_cli/update/state.py`
- Create: `tests/test_update_package.py`
- Create: `tests/test_update_state.py`

- [ ] Add tests rejecting `..`, absolute paths, drive paths, UNC paths, unsafe links, duplicate critical files, excessive expansion, and missing metadata.
- [ ] Extract only into a random staging directory.
- [ ] Validate `app-manifest.json`, executable entrypoint, version, product, platform, and architecture.
- [ ] Move prepared versions atomically on the same volume.
- [ ] Write `pending-update.json`, `update-status.json`, `failed-versions.json`, and transaction files atomically.
- [ ] Recover safely from truncated or corrupt state files.

## Task 4: Add version directory switching and rollback transaction engine

**Files:**
- Create: `wechat_cli/update/layout.py`
- Create: `wechat_cli/update/transaction.py`
- Create: `wechat_cli/update/health.py`
- Create: `tests/test_update_layout.py`
- Create: `tests/test_update_transaction.py`
- Create: `tests/test_update_health.py`

- [ ] Model `%LOCALAPPDATA%\WeChatCliWeb` without hard-coding the active user.
- [ ] Add atomic `current.json` switching with current/previous version fields.
- [ ] Add transaction states: prepared, switching, starting, health-checking, committed, rolling-back, rolled-back.
- [ ] Add restart recovery for every interrupted transaction stage.
- [ ] Poll `/api/health` and verify product, version, build, configuration, license session, and core module status.
- [ ] Roll back on timeout, wrong version, process exit, or malformed health response.
- [ ] Retain only current plus previous versions after a successful commit.
- [ ] Prevent repeated installation of the same failed `version + manifest hash`.

## Task 5: Add license/device/offline-lease client models

**Files:**
- Create: `wechat_cli/license/__init__.py`
- Create: `wechat_cli/license/models.py`
- Create: `wechat_cli/license/lease.py`
- Create: `wechat_cli/license/client.py`
- Create: `wechat_cli/license/clock.py`
- Create: `tests/test_license_models.py`
- Create: `tests/test_license_lease.py`
- Create: `tests/test_license_client.py`

- [ ] Add tests for activation, validation, device list, rename, and unbind response contracts.
- [ ] Verify signed seven-day offline leases with a separate trusted key set.
- [ ] Distinguish explicit server rejection from unavailable network/service.
- [ ] Never fall back to an old lease after explicit revoked/suspended/unbound/token-invalid responses.
- [ ] Add a controllable clock and wall-clock rollback detection.
- [ ] Expose stable client states: unactivated, online-valid, offline-valid, expiring, expired, unbound, suspended, revoked, corrupt.

## Task 6: Add Windows local identity and DPAPI credential storage

**Files:**
- Create: `wechat_cli/windows/__init__.py`
- Create: `wechat_cli/windows/dpapi.py`
- Create: `wechat_cli/license/device_identity.py`
- Create: `wechat_cli/license/storage.py`
- Create: `tests/test_device_identity.py`
- Create: `tests/test_license_storage.py`

- [ ] Generate a high-entropy random install/device ID once.
- [ ] Compute an upload-safe fingerprint from protocol prefix, MachineGuid, current-user SID, and salt version without persisting raw values.
- [ ] Bind encrypted state to the current Windows user with DPAPI.
- [ ] Keep license key, device token, lease, local launch-signing key, and trusted-time state out of JSON/logs/URLs/command lines.
- [ ] Provide a non-Windows test backend that requires explicit injection and cannot be used accidentally in production.
- [ ] Handle missing/corrupt/decryption-failed state by entering recovery activation.

## Task 7: Add one-time launch sessions and application authorization gate

**Files:**
- Create: `wechat_cli/license/session.py`
- Create: `tests/test_launch_session.py`
- Modify: `wechat_cli/commands/web.py`
- Modify: `wechat_cli/web/server.py`
- Modify: `tests/test_web_server.py`

- [ ] Create a two-minute, one-use, version-bound, nonce-bound local launch session.
- [ ] Sign it with a DPAPI-protected local launcher key.
- [ ] Consume and delete the session at application startup.
- [ ] Restrict business APIs when the session is missing, expired, replayed, malformed, or signed by another local key.
- [ ] Keep `/api/health` and the restricted license/error page available as needed for recovery.
- [ ] Preserve a documented development/test bypass that is off by default in packaged builds.

## Task 8: Add `/api/health` and local application status APIs

**Files:**
- Create: `wechat_cli/health.py`
- Modify: `wechat_cli/web/server.py`
- Modify: `tests/test_web_server.py`

- [ ] Add a focused failing health endpoint test.
- [ ] Return product, application version, build ID, configuration-loaded state, license-session state, and core module checks.
- [ ] Do not require WeChat login, database readability, account selection, or completed scans for Demo health.
- [ ] Ensure health never returns secrets, filesystem credentials, database keys, or chat data.

## Task 9: Build launcher core without UI

**Files:**
- Create: `wechat_cli/launcher/__init__.py`
- Create: `wechat_cli/launcher/config.py`
- Create: `wechat_cli/launcher/locks.py`
- Create: `wechat_cli/launcher/service.py`
- Create: `wechat_cli/launcher/process.py`
- Create: `wechat_cli/launcher/cli.py`
- Create: `tests/test_launcher_service.py`
- Create: `tests/test_launcher_process.py`
- Modify: `pyproject.toml`

- [ ] Add a `wechat-cli-launcher` entry point.
- [ ] Acquire a per-user launcher single-instance lock.
- [ ] Detect and reuse a healthy existing Web process.
- [ ] Apply pending updates before license validation and application start.
- [ ] Perform one online validation attempt per startup, then valid offline fallback.
- [ ] Generate a launch session and start the current version.
- [ ] Run health checks, commit or roll back, check updates, start background download, and open the browser.
- [ ] Add `--activate`, `--download-update`, `--apply-update`, and `--repair` modes.

## Task 10: Build update HTTP download and resume client

**Files:**
- Create: `wechat_cli/update/client.py`
- Create: `wechat_cli/update/download.py`
- Create: `tests/test_update_client.py`
- Create: `tests/test_update_download.py`

- [ ] Request updates with device token, current version, launcher version, stable channel, platform, architecture, and failed versions.
- [ ] Verify returned signed manifest before using download metadata.
- [ ] Send the short-lived download ticket in an authorization header, never in a URL.
- [ ] Download to `.part`, preserve resumable metadata, and use Range/ETag only when supported.
- [ ] Restart cleanly when the remote file identity changes.
- [ ] Verify expected size and SHA-256 before extraction.
- [ ] Keep update failures isolated from current application startup.

## Task 11: Add WebView2 launcher UI and secure bridge

**Files:**
- Create: `wechat_cli/launcher/webview.py`
- Create: `wechat_cli/launcher/ui/index.html`
- Create: `wechat_cli/launcher/ui/app.css`
- Create: `wechat_cli/launcher/ui/app.js`
- Create: `tests/test_launcher_ui_contract.py`
- Modify: `pyproject.toml`
- Modify: packaging metadata as required.

- [ ] Detect installed WebView2 Runtime.
- [ ] Load only packaged local UI assets.
- [ ] Reject navigation to arbitrary remote pages and open help links in the system browser.
- [ ] Expose only allow-listed native bridge methods.
- [ ] Never return full license/device/admin/GitHub credentials to JavaScript.
- [ ] Implement activation, validation, offline warning, revoked/unbound/corrupt state, install progress, rollback, and repair screens.
- [ ] Provide a testable no-WebView headless state renderer for CI.

## Task 12: Add application license/update/device UI APIs

**Files:**
- Modify: `wechat_cli/web/server.py`
- Modify: `wechat_cli/web/static/index.html`
- Modify: `wechat_cli/web/static/app.js`
- Modify: `wechat_cli/web/static/app.css`
- Modify: `tests/test_web_server.py`

- [ ] Add “许可证与更新” navigation and status cards.
- [ ] Expose only masked license suffix, status, device count, offline deadline, versions, channel, and update state.
- [ ] List/rename/unbind devices through the authenticated launcher/license client boundary.
- [ ] Require a recent online validation and operation nonce for unbind.
- [ ] Show download progress and “install next startup” state.
- [ ] Show stable security-specific errors for signature/hash failures.

## Task 13: Add diagnostic generation, redaction, and optional upload client

**Files:**
- Create: `wechat_cli/diagnostics/__init__.py`
- Create: `wechat_cli/diagnostics/redaction.py`
- Create: `wechat_cli/diagnostics/package.py`
- Create: `wechat_cli/diagnostics/client.py`
- Create: `tests/test_diagnostics_redaction.py`
- Create: `tests/test_diagnostics_package.py`
- Modify: Web UI/API files.

- [ ] Redact license formats, device/admin/GitHub tokens, authorization/cookie headers, sensitive query parameters, contact fields, and Windows usernames before logs are written.
- [ ] Run a second sensitive-value scan while packaging.
- [ ] Include a user-readable `contents.txt`.
- [ ] Default to local save only.
- [ ] Require a separate explicit confirmation before upload.
- [ ] Enforce size limits and preserve the local ZIP when upload fails.

## Task 14: Create the Cloudflare Worker service and D1 migrations

**Files:**
- Create: `services/license-update-worker/package.json`
- Create: `services/license-update-worker/wrangler.jsonc`
- Create: `services/license-update-worker/tsconfig.json`
- Create: `services/license-update-worker/src/**`
- Create: `services/license-update-worker/migrations/*.sql`
- Create: `services/license-update-worker/test/**`

- [ ] Create local/staging/production environment bindings without secrets in source.
- [ ] Implement health, activation, validation, device, update, download, diagnostic, and admin routes.
- [ ] Add HMAC-digested license keys, device/admin tokens, and download tickets.
- [ ] Implement atomic three-device enforcement and idempotency records.
- [ ] Sign offline leases with the separate lease key.
- [ ] Encrypt contacts with AES-256-GCM and exact-match HMAC lookup digests.
- [ ] Store diagnostic objects only in private R2 and metadata in D1.
- [ ] Add request IDs, uniform errors, rate limits, and audit events without secrets.
- [ ] Pass local Worker/D1 tests before any deployment.

## Task 15: Create administrator CLI

**Files:**
- Create: `tools/admin_cli/**`
- Create: `tests/test_admin_cli.py`
- Modify: `pyproject.toml`

- [ ] Add API URL and DPAPI-protected admin-token configuration.
- [ ] Create/show/search/suspend/resume/revoke licenses.
- [ ] Batch-create licenses and write a non-overwriting sensitive CSV.
- [ ] List/enable/disable/unbind devices.
- [ ] List/enable/pause releases and retain 100% stable defaults in Demo.
- [ ] Inspect/download/delete diagnostic submissions through authenticated APIs.
- [ ] Add contact encryption key-rotation commands and status.

## Task 16: Create signed release CLI

**Files:**
- Create: `tools/release_cli/**`
- Create: `tests/test_release_cli.py`
- Modify: `pyproject.toml`

- [ ] Validate version, build metadata, package structure, and clean intended release inputs.
- [ ] Calculate SHA-256 and canonical release metadata.
- [ ] Sign raw manifest bytes with a local Ed25519 private key loaded from a protected path.
- [ ] Create/upload a private GitHub Release using a separate write-scoped token.
- [ ] Register the release in Worker as disabled by default.
- [ ] Require explicit `enable` or `pause` commands as separate actions.
- [ ] Never print or log private keys or GitHub/admin tokens.

## Task 17: Add Windows installer, migration, repair, and uninstall

**Files:**
- Modify: `packaging/windows/install.ps1`
- Modify: `packaging/windows/install-and-start.bat`
- Modify: `packaging/windows/start-wechat-cli-web.bat`
- Modify: `packaging/windows/README-APP.md`
- Modify: `scripts/package_windows_app.py`
- Create: installation transaction/repair scripts only where the existing packaging approach requires them.
- Modify/Create: Windows packaging tests.

- [ ] Detect system WebView2 Runtime and download the official bootstrapper only when missing.
- [ ] Preflight disk space, write access, old process state, and backup location.
- [ ] Migrate old `app\wechat-cli.exe` to `versions\0.4.2` without touching `%USERPROFILE%\.wechat-cli`.
- [ ] Install Launcher, create `current.json`, and point all shortcuts at Launcher.
- [ ] Record install transaction stages and restore the old layout/shortcut on failure.
- [ ] Add repair for current pointer, interrupted transactions, caches, missing launcher, and missing Runtime.
- [ ] Uninstall program files by default while preserving user WeChat data.

## Task 18: Version 0.5.0 integration and local end-to-end tests

**Files:**
- Modify: `pyproject.toml`
- Modify: shared version source and version assertions.
- Create/Modify: end-to-end tests and fixtures.

- [ ] Bump application to 0.5.0 and Launcher to 0.1.0 only after local feature gates pass.
- [ ] Run full unit tests.
- [ ] Build Windows application, launcher, and installer.
- [ ] Verify clean install and 0.4.2 migration in an isolated test location.
- [ ] Verify activation, three-device limit, seven-day offline behavior, update preparation, next-start install, health success, and rollback locally.
- [ ] Scan repository and artifacts for secrets.

## Task 19: Real staging environment and private GitHub Release acceptance

**External side effects:** Cloudflare/GitHub account access, repository/resource creation, secrets, and deployment.

- [ ] Create or select separate private source and release repositories.
- [ ] Create staging Worker, D1, and private R2 resources.
- [ ] Configure staging-only peppers, encryption keys, lease keys, admin token, and GitHub read token.
- [ ] Publish 0.5.1 and verify real 0.5.0 → 0.5.1 update.
- [ ] Publish an intentionally unhealthy 0.5.2 and verify automatic rollback to 0.5.1.
- [ ] Verify online license revocation overrides an unexpired local lease.
- [ ] Verify active diagnostic submission, administrator retrieval, and deletion.
- [ ] Record request IDs, hashes, logs, and known Cloudflare/GitHub limits.

## Task 20: Final hardening and Demo delivery

**Files:**
- Create: deployment, administration, release, rollback, key-recovery, privacy, and acceptance documentation.
- Create: final verification report.

- [ ] Run every focused and full test suite.
- [ ] Run Worker type-check/build/tests and database migrations from empty state.
- [ ] Rebuild all Windows artifacts reproducibly.
- [ ] Verify installation, update, rollback, license, device, diagnostic, and uninstall scenarios.
- [ ] Verify no secrets/private keys/plaintext license exports are tracked.
- [ ] Show relevant source and artifact changes.
- [ ] Report real test commands, counts, exit codes, hashes, external acceptance evidence, and remaining risks.

---

## Execution gates

1. Do not modify or discard the existing `invite_stats` changes.
2. Do not add a dependency merely for convenience; prove the stdlib/PyCryptodome cannot meet the requirement first.
3. Do not install or switch versions until signature, hash, package-safety, and transaction tests pass.
4. Do not enable diagnostic upload until redaction tests pass.
5. Do not deploy the Worker until local Worker/D1 tests pass.
6. Do not claim Demo completion until a real private Release update and a real rollback have both succeeded.
7. Do not commit tokens, secrets, private signing keys, exported license CSVs, or `.env` contents.
