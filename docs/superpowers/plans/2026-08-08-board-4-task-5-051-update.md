# Board 4 Task 5 — 0.5.1 Update-Only Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-only `0.5.1` application update package that proves the `0.5.0 → 0.5.1` update path without rebuilding Launcher, producing a staging bootstrap, overwriting the fixed 0.5.0 ZIP, or performing any Task 6 release side effect.

**Architecture:** Keep the existing full Windows bootstrap path backward-compatible, but add a first-class app-only build target in `npm/scripts/build.py` and a first-class update-only packaging path in `scripts/package_windows_app.py`. Version metadata moves to application `0.5.1`, Launcher remains `0.1.0`, and the default runtime/build identifier becomes `staging-051-20260808.1` while retaining explicit `WECHAT_CLI_BUILD_ID` override support. Task 5 executes only in a DevSpace worktree branched from the frozen latest `main` HEAD.

**Tech Stack:** Python 3, unittest, PyInstaller, Windows packaging ZIPs, existing WeChat CLI update/package verification code, TypeScript/Vitest Worker regression suite.

---

## Approved design and hard boundaries

- Application version: `0.5.1`.
- Launcher version: remains `0.1.0`; Launcher is not rebuilt.
- Default Build ID: `staging-051-20260808.1`.
- `WECHAT_CLI_BUILD_ID` continues to override the default Build ID when explicitly set.
- Release summary reserved for later Task 6: `Authorized update staging 0.5.1`.
- `npm/scripts/build.py` gains an explicit app-only target mode while preserving the existing default Windows app+launcher build behavior.
- `scripts/package_windows_app.py` gains `--update-only`; that mode does not require launcher config and only produces the app update ZIP.
- Target artifact: `dist/wechat-cli-app-0.5.1-win-x64.zip` containing only `wechat-cli.exe` and `app-manifest.json`.
- Existing `dist/wechat-cli-app-0.5.0-win-x64.zip` must remain byte-for-byte unchanged with SHA-256 `406b72c14ad186141f373087595f7723e143b9638bf298fde23b6bb0ae057523`.
- No staging bootstrap is produced in Task 5.
- No GitHub Release is created or uploaded, no Worker release is registered or enabled, and no cloud state is mutated. Those are Task 6 and require separate explicit authorization.
- No push or merge is performed in Task 5.

## File map

**Modify:**
- `wechat_cli/version.py` — application version and default Build ID only; Launcher version stays unchanged.
- `pyproject.toml` — Python package version follows application version.
- `npm/scripts/build.py` — app-only target selection and CLI parsing while retaining current default behavior.
- `scripts/package_windows_app.py` — update-only assembly/package path without Launcher/bootstrap inputs.
- `tests/test_main.py` — current product version assertion.
- `tests/test_version_metadata.py` — shared version/default Build ID and environment-override contract.
- `tests/test_windows_packaging.py` — app-only build and update-only packaging behavior.
- `CHANGELOG.md` — minimal 0.5.1 staging validation entry; explicitly no business feature change.
- `docs/PROJECT_STATE.md`, `docs/deployment/authorized-update-roadmap.md`, and `docs/superpowers/plans/2026-08-05-board-4-test-license-and-release.md` — only after Task 5 implementation and verification evidence exists.

**Do not modify:**
- Launcher source/version behavior beyond retaining `LAUNCHER_VERSION = "0.1.0"`.
- Windows installer/bootstrap templates.
- Published 0.5.0 package contents.
- Release repository.
- Cloudflare/GitHub release state.

---

### Task 1: Version metadata 0.5.1 and deterministic default Build ID

**Files:**
- Modify: `tests/test_main.py`
- Modify: `tests/test_version_metadata.py`
- Modify: `wechat_cli/version.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Write failing current-version and Build-ID tests**

Update the current release assertion to require `0.5.1`. Add assertions equivalent to:

```python
self.assertEqual("0.5.1", version.APP_VERSION)
self.assertEqual("0.1.0", version.LAUNCHER_VERSION)
self.assertEqual("staging-051-20260808.1", version.BUILD_ID)
```

For environment override, load `wechat_cli/version.py` with `WECHAT_CLI_BUILD_ID=override-build` and assert:

```python
self.assertEqual("override-build", loaded["BUILD_ID"])
```

Also assert `pyproject.toml` and runtime `APP_VERSION` both equal `0.5.1`.

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
python -m unittest tests.test_main tests.test_version_metadata -v
```

Expected: failures specifically because the current application/project version is `0.5.0` and the default Build ID is `dev`.

- [ ] **Step 3: Implement only the approved metadata change**

Set in `wechat_cli/version.py`:

```python
APP_VERSION = "0.5.1"
LAUNCHER_VERSION = "0.1.0"
DEFAULT_BUILD_ID = "staging-051-20260808.1"
BUILD_ID = os.environ.get("WECHAT_CLI_BUILD_ID", DEFAULT_BUILD_ID)
```

Set `pyproject.toml` project version to `0.5.1`. Do not change npm package metadata or historical 0.5.0 fixtures.

- [ ] **Step 4: Re-run focused tests and verify GREEN**

Run the same unittest command. Expected: all focused tests pass.

- [ ] **Step 5: Inspect the diff for accidental historical-fixture changes**

Run:

```powershell
git diff -- wechat_cli/version.py pyproject.toml tests/test_main.py tests/test_version_metadata.py
```

Expected: only current product metadata/tests changed; historical update/rollback fixtures remain untouched.

---

### Task 2: First-class app-only Windows build target

**Files:**
- Modify: `tests/test_windows_packaging.py`
- Modify: `npm/scripts/build.py`

- [ ] **Step 1: Write failing tests for target selection**

Add tests requiring an interface equivalent to:

```python
self.assertTrue(build.build_platform("win32-x64", targets=["app"]))
```

with patched dependency checks and subprocess calls, then assert:

```python
dependency_check.assert_called_once_with("app")
self.assertEqual(1, check_call.call_count)
self.assertIn("wechat-cli", " ".join(check_call.call_args.args[0]))
self.assertNotIn("wechat-cli-launcher", " ".join(check_call.call_args.args[0]))
```

Add a separate test confirming default `build_platform("win32-x64")` still preflights `app` and `launcher`. Add CLI/parser coverage so an unknown target is rejected instead of silently falling back.

- [ ] **Step 2: Run packaging tests and verify RED**

Run:

```powershell
python -m unittest tests.test_windows_packaging -v
```

Expected: app-only target tests fail because current `build_platform` has no target selection support.

- [ ] **Step 3: Implement minimal target selection**

Change the build API to the equivalent of:

```python
def build_platform(platform: str, targets: list[str] | None = None):
    os_name, _arch = platform.split("-")
    selected = list(targets) if targets is not None else (
        ["app", "launcher"] if os_name == "win32" else ["app"]
    )
    allowed = {"app", "launcher"}
    if not selected or any(target not in allowed for target in selected):
        raise ValueError("Unknown or empty build target selection")
    if "launcher" in selected and os_name != "win32":
        raise ValueError("The graphical launcher is currently Windows-only")
    # existing preflight/build loop uses selected
```

Expose a CLI option such as `--target app` while preserving old positional platform behavior when the flag is absent. Do not install or require `pywebview` for app-only execution.

- [ ] **Step 4: Re-run packaging tests and verify GREEN**

Run the same focused unittest command. Expected: all packaging tests pass, including the legacy full-build preflight test.

- [ ] **Step 5: Verify app-only dependency preflight does not inspect pywebview**

Run the existing `test_application_build_does_not_require_pywebview` together with the new app-only test. Expected: pass.

---

### Task 3: Update-only packaging without Launcher or bootstrap

**Files:**
- Modify: `tests/test_windows_packaging.py`
- Modify: `scripts/package_windows_app.py`

- [ ] **Step 1: Write failing update-only packaging tests**

Add tests that use a temporary DIST directory and fake `wechat-cli.exe`, and require an API equivalent to:

```python
update_zip = package.create_update_only_package(skip_build=True)
```

Verify:

```python
self.assertEqual("wechat-cli-app-0.5.1-win-x64.zip", update_zip.name)
```

Inspect the ZIP and require exactly:

```python
{"wechat-cli.exe", "app-manifest.json"}
```

Decode `app-manifest.json` and require:

```python
{
    "product": "wechat-cli-web",
    "version": "0.5.1",
    "platform": "windows",
    "architecture": "x86_64",
    "entrypoint": "wechat-cli.exe",
    "build_id": "staging-051-20260808.1",
}
```

Add tests that update-only does not validate/read launcher config or `wechat-cli-launcher.exe`, does not create/remove bootstrap directories/ZIPs, and raises `FileExistsError` if the target 0.5.1 ZIP already exists.

- [ ] **Step 2: Run packaging tests and verify RED**

Run:

```powershell
python -m unittest tests.test_windows_packaging -v
```

Expected: failures because update-only APIs/CLI do not yet exist.

- [ ] **Step 3: Implement minimal update-only assembly**

Add a focused helper that creates a temporary/version assembly directory containing only the app binary and `app-manifest.json`, then writes the versioned update ZIP with no overwrite. Reuse `_app_manifest()` and `create_update_package()` logic where safe, but change `create_update_package()` or its caller so an existing final ZIP is rejected rather than overwritten.

CLI behavior:

```text
python scripts/package_windows_app.py --update-only
```

must not require `--launcher-config`. When build is enabled, it invokes the app-only build target from Task 2. The legacy full bootstrap mode keeps requiring `--launcher-config`.

- [ ] **Step 4: Re-run packaging tests and verify GREEN**

Run the focused packaging suite. Expected: all tests pass.

- [ ] **Step 5: Confirm 0.5.0 protection in tests**

Add/assert that update-only chooses the current `0.5.1` filename and never removes or opens the existing `wechat-cli-app-0.5.0-win-x64.zip` for writing.

---

### Task 4: Changelog and real local 0.5.1 artifact build

**Files:**
- Modify: `CHANGELOG.md`
- Produce locally (do not commit unless repository policy explicitly expects dist assets): `dist/wechat-cli-app-0.5.1-win-x64.zip`

- [ ] **Step 1: Record the pre-build 0.5.0 hash**

Run:

```powershell
Get-FileHash .\dist\wechat-cli-app-0.5.0-win-x64.zip -Algorithm SHA256
```

Expected SHA-256:

```text
406b72c14ad186141f373087595f7723e143b9638bf298fde23b6bb0ae057523
```

Abort Task 5 if it differs.

- [ ] **Step 2: Add a minimal 0.5.1 changelog entry**

State that 0.5.1 is a staging update-chain validation release with no business feature change, app-only build support, and update-only package support. Do not claim publication or hosted availability.

- [ ] **Step 3: Build only the application binary**

Run the newly supported app-only build command for `win32-x64`. Expected: `wechat-cli.exe` is built without building Launcher and without requiring pywebview.

- [ ] **Step 4: Produce the update-only 0.5.1 ZIP**

Run:

```powershell
python scripts\package_windows_app.py --update-only
```

Expected: only `dist\wechat-cli-app-0.5.1-win-x64.zip` is newly produced by the packaging path; no new staging bootstrap is created.

- [ ] **Step 5: Inspect ZIP structure and manifest**

Read the ZIP without extracting into the repository and confirm the two members and metadata values listed in Task 3.

- [ ] **Step 6: Record 0.5.1 size and SHA-256**

Use `Get-Item` and `Get-FileHash`. Record the byte size and hash in Task 5 evidence later.

- [ ] **Step 7: Re-check fixed 0.5.0 SHA-256**

Run the Step 1 hash command again. Expected: exactly the same fixed hash.

---

### Task 5: Full local verification and board-state evidence

**Files:**
- Modify after evidence exists: `docs/PROJECT_STATE.md`
- Modify after evidence exists: `docs/deployment/authorized-update-roadmap.md`
- Modify after evidence exists: `docs/superpowers/plans/2026-08-05-board-4-test-license-and-release.md`

- [ ] **Step 1: Run focused version/build/packaging tests**

Run the affected test modules and require zero failures.

- [ ] **Step 2: Run full Python verification**

Run:

```powershell
python -m unittest discover -s tests -v
```

Expected: zero failures; existing platform-condition skips are allowed.

- [ ] **Step 3: Run Worker regression verification**

From `services/license-update-worker`:

```powershell
npm run typecheck
npm test
```

Expected: typecheck passes and Vitest has zero failures.

- [ ] **Step 4: Run applicable local update artifact verification**

Use `scripts/verify_local_update_artifacts.py` if it can validate an update-only package independently. If it currently requires a bootstrap, stop and return to TDD: first write a failing test for a minimal update-only verification mode, then implement only that mode. Do not generate a bootstrap merely to satisfy the verifier.

- [ ] **Step 5: Run repository safety checks**

Run `git diff --check`, targeted secret-shape scans, source/release repository `git status --short`, and confirm the release repository remains unchanged.

- [ ] **Step 6: Verify prohibited actions did not occur**

Confirm there was no 0.5.1 GitHub Release creation/upload, no Worker release registration/enablement, no staging bootstrap, no Launcher rebuild, no push, and no merge.

- [ ] **Step 7: Update board evidence only from verified results**

Record the focused/full test results, 0.5.1 ZIP size/hash, fixed 0.5.0 hash, build ID, Launcher version, and current execution gate. Mark Task 5 complete only if every exit condition below is satisfied.

---

## Exit conditions

Task 5 is complete only when all are true:

- `0.5.1` contains only the approved version/build-chain changes and no business feature change.
- App-only build and update-only packaging are protected by tests and verified in a real local build.
- Launcher remains `0.1.0`, is not rebuilt, and pywebview is not required for Task 5.
- `dist/wechat-cli-app-0.5.1-win-x64.zip` exists and passes structure/version/build-id/hash checks.
- Package `app-manifest.json` and runtime default Build ID both identify `staging-051-20260808.1` unless an explicit override is under test.
- Fixed 0.5.0 update ZIP remains SHA-256 `406b72c14ad186141f373087595f7723e143b9638bf298fde23b6bb0ae057523`.
- Focused tests, full Python tests, Worker typecheck, and Worker Vitest have zero failures.
- No token, private key, complete license, device token, admin token, or other secret enters Git or artifact logs.
- No staging bootstrap has been created as part of Task 5.
- No 0.5.1 release has been created, uploaded, registered, or enabled.
- No push or merge has occurred.
- Task 6 remains behind a new explicit external-side-effect authorization gate.
