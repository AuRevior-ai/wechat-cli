# Board 5 Windows Staging E2E Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This repository/session does not assume subagent concurrency; execute single-threaded unless the user explicitly changes that constraint.

**Goal:** Build a fail-closed Board 5 staging acceptance harness that proves real Windows bootstrap 0.5.0 -> licensed startup -> real private 0.5.1 update -> restart/health, real offline startup, and an isolated beta fault candidate rollback without modifying Board 4 releases or the user's daily installation.

**Architecture:** Keep two frozen source lines: Board 5 tooling lives on `board5/windows-staging-e2e` from `8c7464f`, while bootstrap 0.5.0 app + Launcher 0.1.0 binaries come only from detached `a579a25`. Add narrowly scoped packaging/config/sandbox/offline/fault helpers with strict root/hash/channel validation. Every install, license, GitHub, Cloudflare, fault-enable, cleanup, push, and merge action remains behind an explicit user gate.

**Tech Stack:** Python 3.12, `unittest`, PyInstaller build scripts, Windows PowerShell installer, current-user Windows DPAPI, Ed25519 release/lease verification, Cloudflare Worker/D1, private GitHub Releases, existing `wechat_cli` Launcher/update/release modules.

**Approved design:** `docs/superpowers/specs/2026-08-09-board-5-windows-staging-e2e-design.md`

---

## Global invariants

These invariants apply to every task:

- Board 4 snapshot `task5/0.5.1-update-validation@8c7464f` is read-only.
- Board 5 worktree: `C:\Users\28276\.devspace\worktrees\wechat-cli-1ec755b9-46a6ab4b`, branch `board5/windows-staging-e2e`.
- 0.5.0 build-source worktree: `C:\Users\28276\.devspace\worktrees\wechat-cli-1ec755b9-54a1291f`, detached `a579a25cb7f16e6fdf88d618252b4a5cbffef53d`.
- main checkout remains untouched, including untracked `NUL`.
- Fixed 0.5.0 update ZIP reference remains size `14291197`, SHA-256 `406b72c14ad186141f373087595f7723e143b9638bf298fde23b6bb0ae057523`.
- Board 4 0.5.1 update ZIP reference remains size `14268929`, SHA-256 `0ddbb0b402cc9d98ed001391c1a618527d165e328a1f4f1534d80e6b984956c0`.
- Board 4 0.5.1 ZIP internal `wechat-cli.exe` remains size `14483951`, SHA-256 `dbbdf8ec70ddcf8d36145f099b0cb4ce3292c61e205c3ac7ae4db01fbc8907d1`.
- Board 4 0.5.1 signed manifest SHA-256 remains `be111f0a786821319fb96f82f1748b4a75003b7c5fb296c48ec87b3355a3fd62`.
- `rel_staging_050` and `rel_staging_051` are read-only throughout Board 5.
- No command may print a complete license, device token, DPAPI plaintext, release private key, GitHub/Admin token, raw lease bytes/signature, MachineGuid, SID, `.env`, or Cookie.
- No ambiguous external write is retried until remote state is reconciled read-only.
- Push and merge are never implied by a Board 5 task approval.

---

### Task 1: Freeze Board 5 execution boundaries and preflight helpers

**Files:**
- Create: `scripts/board5_common.py`
- Create: `tests/test_board5_common.py`
- Modify: `docs/PROJECT_STATE.md`
- Modify: `docs/deployment/authorized-update-roadmap.md`

**Purpose:** Centralize Board 5 root/path/hash guards so later tools cannot accidentally target the normal installation or Board 4 worktrees.

**Authorization gate:** Local implementation only. Before executing this task, obtain explicit approval to modify Board 5 source/tests. No build, install, license, GitHub, Cloudflare, or cleanup writes are included.

- [x] **Step 1: Reconfirm clean baselines**

Run in Board 5 worktree:

```powershell
python -m unittest discover -s tests
git status --short
git rev-parse HEAD
git merge-base HEAD 8c7464f
```

Expected before implementation:

```text
Ran 489 tests
OK (skipped=2)
working tree clean
merge-base = 8c7464f058a9edf520b4c97e02b63835a3c0901c
```

Run in build-source worktree:

```powershell
git status --short
git rev-parse HEAD
```

Expected:

```text
working tree clean
a579a25cb7f16e6fdf88d618252b4a5cbffef53d
```

- [x] **Step 2: Write failing path-boundary tests**

Create `tests/test_board5_common.py` with tests equivalent to:

```python
from pathlib import Path
import tempfile
import unittest

from scripts.board5_common import (
    BOARD4_MANIFEST_051_SHA256,
    FIXED_UPDATE_050_SHA256,
    assert_board5_root,
    assert_expected_file_sha256,
    assert_outside_repository,
)


class Board5CommonTests(unittest.TestCase):
    def test_board5_root_requires_marker_and_rejects_normal_localappdata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "board5"
            root.mkdir()
            (root / ".board5-acceptance-root").write_text("board5\n", encoding="utf-8")
            self.assertEqual(root.resolve(), assert_board5_root(root))
            with self.assertRaises(ValueError):
                assert_board5_root(Path.home() / "AppData" / "Local")

    def test_known_board4_hash_constants_are_exact(self):
        self.assertEqual(
            "406b72c14ad186141f373087595f7723e143b9638bf298fde23b6bb0ae057523",
            FIXED_UPDATE_050_SHA256,
        )
        self.assertEqual(
            "be111f0a786821319fb96f82f1748b4a75003b7c5fb296c48ec87b3355a3fd62",
            BOARD4_MANIFEST_051_SHA256,
        )
```

- [x] **Step 3: Run the new tests and verify RED**

Run:

```powershell
python -m unittest tests.test_board5_common
```

Expected: FAIL because `scripts.board5_common` does not exist.

- [x] **Step 4: Implement the minimal shared guard module**

Create `scripts/board5_common.py` with a narrow API:

```python
from __future__ import annotations

import hashlib
from pathlib import Path

BOARD5_MARKER = ".board5-acceptance-root"
FIXED_UPDATE_050_SIZE = 14291197
FIXED_UPDATE_050_SHA256 = "406b72c14ad186141f373087595f7723e143b9638bf298fde23b6bb0ae057523"
UPDATE_051_SIZE = 14268929
UPDATE_051_SHA256 = "0ddbb0b402cc9d98ed001391c1a618527d165e328a1f4f1534d80e6b984956c0"
UPDATE_051_EXE_SIZE = 14483951
UPDATE_051_EXE_SHA256 = "dbbdf8ec70ddcf8d36145f099b0cb4ce3292c61e205c3ac7ae4db01fbc8907d1"
BOARD4_MANIFEST_051_SHA256 = "be111f0a786821319fb96f82f1748b4a75003b7c5fb296c48ec87b3355a3fd62"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_board5_root(path: Path) -> Path:
    root = path.resolve(strict=True)
    marker = root / BOARD5_MARKER
    if not marker.is_file() or marker.read_text(encoding="utf-8") != "board5\n":
        raise ValueError("target is not an initialized Board 5 acceptance root")
    return root


def assert_expected_file_sha256(path: Path, expected_sha256: str, expected_size: int | None = None) -> None:
    if path.is_symlink() or not path.is_file():
        raise AcceptanceError("expected a regular file")
    if expected_size is not None and path.stat().st_size != expected_size:
        raise AcceptanceError("file size drift detected")
    if sha256_file(path) != expected_sha256:
        raise AcceptanceError("file hash drift detected")


def assert_outside_repository(path: Path) -> Path:
    resolved = path.resolve()
    repository_root = ROOT.resolve()
    if resolved == repository_root or repository_root in resolved.parents:
        raise AcceptanceError("output path must be outside the repository")
    return resolved
```

Do not put actual secure root paths or credentials in this module. The helper must evaluate the resolved target so symlinked paths that end inside the repository are rejected.

- [x] **Step 5: Run focused tests and verify GREEN**

Run:

```powershell
python -m unittest tests.test_board5_common
```

Expected: PASS.

- [x] **Step 6: Record Board 5 implementation gate state**

Update `docs/PROJECT_STATE.md` and `docs/deployment/authorized-update-roadmap.md` only after the user authorizes Task 1 implementation. Record:

```text
Board 5 design/plan approved; local tooling implementation started in board5/windows-staging-e2e.
No bootstrap build/install/license/cloud write has been authorized or executed.
```

- [x] **Step 7: Verify and commit Task 1**

Run:

```powershell
python -m unittest tests.test_board5_common
python -m unittest discover -s tests
git diff --check
git status --short
```

Expected full suite: 489 existing tests plus new Board 5 tests, all passing except the same two platform skips.

Commit only Task 1 files:

```powershell
git add scripts/board5_common.py tests/test_board5_common.py docs/PROJECT_STATE.md docs/deployment/authorized-update-roadmap.md
git commit -m "test: add board 5 acceptance boundaries"
```

---

### Task 2: Add bootstrap-only and external-output packaging

**Files:**
- Modify: `scripts/package_windows_app.py`
- Modify: `tests/test_windows_packaging.py`

**Purpose:** Allow Board 5 to package 0.5.0 bootstrap bytes sourced from `a579a25` without regenerating any update ZIP and without writing Board 5 deliverables into repository `dist/`.

**Authorization gate:** Same local-implementation gate as Task 1. This task changes packaging code/tests only; it does not build the Board 5 bootstrap.

- [x] **Step 1: Write failing bootstrap-only tests**

Add tests that construct temporary source/binary/output roots and assert:

```python
def test_bootstrap_only_writes_only_bootstrap_to_external_output(self):
    package_dir, bootstrap_zip = create_bootstrap_package(
        launcher_config_path=config,
        source_root=source_root,
        binary_root=binary_root,
        output_dir=output_root,
        version="0.5.0",
        build_id="0.5.0-local-20260805.1",
    )
    self.assertTrue(package_dir.is_dir())
    self.assertTrue(bootstrap_zip.is_file())
    self.assertEqual([], list(output_root.glob("wechat-cli-app-*.zip")))


def test_bootstrap_only_refuses_repository_outputs(self):
    for output_dir in (ROOT, ROOT / "dist", ROOT / "foo"):
        with self.subTest(output_dir=output_dir):
            with self.assertRaises(AcceptanceError):
                create_bootstrap_package(
                    launcher_config_path=config,
                    source_root=source_root,
                    binary_root=binary_root,
                    output_dir=output_dir,
                    version="0.5.0",
                    build_id="0.5.0-local-20260805.1",
                )


def test_bootstrap_only_allows_repository_external_output(self):
    create_bootstrap_package(
        launcher_config_path=config,
        source_root=source_root,
        binary_root=binary_root,
        output_dir=output_root,
        version="0.5.0",
        build_id="0.5.0-local-20260805.1",
    )


def test_bootstrap_only_never_calls_update_packager(self):
    with patch("scripts.package_windows_app.create_update_package") as update:
        create_bootstrap_package(
            launcher_config_path=config,
            source_root=source_root,
            binary_root=binary_root,
            output_dir=output_root,
            version="0.5.0",
            build_id="0.5.0-local-20260805.1",
        )
        update.assert_not_called()
```

Also add CLI parser coverage for:

```text
--bootstrap-only
--output-dir
--source-root
--binary-root
--version
--build-id
```

- [x] **Step 2: Run focused tests and verify RED**

Run:

```powershell
python -m unittest tests.test_windows_packaging
```

Expected: new tests fail because bootstrap-only API/CLI does not exist.

- [x] **Step 3: Refactor path helpers without changing legacy behavior**

Change the hard-coded globals into parameterized helpers while keeping default behavior for existing callers. Introduce signatures equivalent to:

```python
def _source_path(source_root: Path, relative: str) -> Path:
    path = source_root / relative
    if path.is_symlink() or not path.exists():
        raise FileNotFoundError(path)
    return path


def _binary_path(name: str, *, binary_root: Path | None = None) -> Path:
    root = binary_root or (ROOT / "npm" / "platforms" / PLATFORM / "bin")
    path = root / name
    if path.is_symlink() or not path.is_file():
        raise FileNotFoundError(f"Missing binary: {path}")
    return path


def copy_package_files(
    package_dir: Path,
    *,
    launcher_config_path: str | Path,
    version: str,
    build_id: str | None = None,
    source_root: Path = ROOT,
    binary_root: Path | None = None,
) -> None:
    launcher_config = _validate_launcher_config(launcher_config_path)
    resolved_build_id = build_id or runpy.run_path(str(source_root / "wechat_cli" / "version.py"))["BUILD_ID"]
    # Existing copy logic then reads templates from source_root and binaries from binary_root.
    # Keep this body small by reusing the existing manifest/copy helpers rather than duplicating packaging behavior.
```

`_app_manifest()` must accept an explicit `build_id` so a 0.5.0 build-source manifest is not derived from the Board 5 branch's 0.5.1 `version.py`.

- [x] **Step 4: Implement `create_bootstrap_package()`**

Add a dedicated function whose contract returns only `(package_dir, bootstrap_zip)`:

```python
def create_bootstrap_package(
    *,
    launcher_config_path: str | Path,
    source_root: Path,
    binary_root: Path,
    output_dir: Path,
    version: str,
    build_id: str,
) -> tuple[Path, Path]:
    resolved_output = assert_outside_repository(output_dir)
    resolved_output.mkdir(parents=True, exist_ok=True)
    output_dir = resolved_output
    package_dir = output_dir / f"{PACKAGE_STEM}-{version}"
    if package_dir.exists():
        raise FileExistsError(f"bootstrap directory already exists: {package_dir}")
    package_dir.mkdir()
    copy_package_files(
        package_dir,
        launcher_config_path=launcher_config_path,
        version=version,
        build_id=build_id,
        source_root=source_root,
        binary_root=binary_root,
    )
    bootstrap_zip = Path(
        shutil.make_archive(
            str(output_dir / f"{PACKAGE_STEM}-{version}"),
            "zip",
            root_dir=package_dir.parent,
            base_dir=package_dir.name,
        )
    )
    return package_dir, bootstrap_zip
```

Do not call `create_update_package()` from this function.

- [x] **Step 5: Add the fail-closed CLI path**

CLI behavior:

```text
--bootstrap-only requires --launcher-config --source-root --binary-root --output-dir --version --build-id
--bootstrap-only rejects repository-contained output paths
--bootstrap-only never invokes build_binary()
--update-only retains existing behavior
legacy full packaging retains existing behavior for non-Board-5 callers
```

- [x] **Step 6: Verify focused + full tests**

Run:

```powershell
python -m unittest tests.test_windows_packaging
python -m unittest discover -s tests
git diff --check
```

Expected: all tests pass, same two existing skips.

- [x] **Step 7: Commit Task 2**

```powershell
git add scripts/package_windows_app.py tests/test_windows_packaging.py
git commit -m "feat: add isolated bootstrap-only packaging"
```

---

### Task 3: Add staging config, sandbox-state, offline-state, and fault-package acceptance tools

**Files:**
- Create: `scripts/board5_prepare_launcher_config.py`
- Create: `scripts/board5_prepare_sandbox.py`
- Create: `scripts/board5_offline_acceptance.py`
- Create: `scripts/board5_prepare_fault_package.py`
- Create: `tests/test_board5_prepare_launcher_config.py`
- Create: `tests/test_board5_prepare_sandbox.py`
- Create: `tests/test_board5_offline_acceptance.py`
- Create: `tests/test_board5_prepare_fault_package.py`

**Purpose:** Provide minimal fail-closed helpers so Board 5 never manually edits launcher config/current.json, never reads secrets into logs, and can build a deterministic health-mismatch fault ZIP from known-good 0.5.1 bytes.

**Authorization gate:** Local-implementation only. These tools may be implemented/tested with temporary fake data, but must not read the real staging secrets directory or write Board 5 real artifacts until later gates.

Use these shared definitions in the new scripts so later snippets have one stable interface:

```python
class AcceptanceError(RuntimeError):
    pass


def safe_device_hint(device_id: str) -> str:
    return hashlib.sha256(device_id.encode("utf-8")).hexdigest()[:12]
```

No raw device ID is included in JSON evidence.

- [x] **Step 1: Write failing config-generator tests**

Tests must prove the tool:

```python
result = build_launcher_config(
    public_keys_file=public_keys,
    api_base_url="https://staging.example.test",
    channel="stable",
    port=18787,
    fingerprint_salt="board5-staging-v1",
    output_path=output,
)
self.assertEqual("stable", LauncherConfig.load(output).channel)
self.assertEqual({"release-key-staging-01"}, set(result.release_key_ids))
self.assertEqual({"lease-key-staging-01"}, set(result.lease_key_ids))
self.assertNotIn(public_key_base64, result.safe_summary_json)
```

Reject missing/unexpected key IDs, symlink input, overwrite, non-HTTPS API URL, and repository-contained output. Repository boundary checks must reuse `assert_outside_repository()` rather than duplicating path logic.

- [x] **Step 2: Implement config generation with production validation**

The implementation must select only the approved key IDs and call `LauncherConfig.load(output_path)` before reporting success. Safe output schema:

```python
{
    "ok": True,
    "config_sha256": sha256_file(output_path),
    "api_host": "wechat-cli-license-update-staging.aurevior-ai.workers.dev",
    "channel": "stable",
    "port": 18787,
    "release_key_ids": ["release-key-staging-01"],
    "lease_key_ids": ["lease-key-staging-01"],
}
```

- [x] **Step 3: Write failing RollbackSandbox state tests**

Tests must create a temporary Board 5 marker root and a real `InstallLayout`, then assert that channel switching is rejected unless all preconditions are exact:

```python
expected = CurrentVersion(
    current_version="0.5.1",
    previous_version="0.5.0",
    channel="stable",
    activated_at="2026-08-09T12:00:00Z",
    manifest_sha256=BOARD4_MANIFEST_051_SHA256,
)
layout.save_current(expected)
changed = switch_rollback_sandbox_to_beta(layout.root, board5_root)
self.assertEqual("beta", changed.channel)
self.assertEqual("0.5.1", changed.current_version)
self.assertEqual("0.5.0", changed.previous_version)
self.assertEqual(BOARD4_MANIFEST_051_SHA256, changed.manifest_sha256)
```

Negative tests must cover wrong current version, wrong previous version, wrong hash, missing version directories, no Board 5 marker, and target outside RollbackSandbox.

- [x] **Step 4: Implement RollbackSandbox preparation without text-editing JSON**

Use the actual repository type name `InstallLayout` together with `CurrentVersion`:

```python
current = layout.load_current()
if current.current_version != "0.5.1":
    raise AcceptanceError("RollbackSandbox current version is not 0.5.1")
if current.previous_version != "0.5.0":
    raise AcceptanceError("RollbackSandbox previous version is not 0.5.0")
if current.manifest_sha256 != BOARD4_MANIFEST_051_SHA256:
    raise AcceptanceError("RollbackSandbox manifest evidence drifted")
changed = CurrentVersion(
    current_version=current.current_version,
    previous_version=current.previous_version,
    channel="beta",
    activated_at=current.activated_at,
    manifest_sha256=current.manifest_sha256,
)
layout.save_current(changed)
```

The sandbox-copy helper must exclude `state/license-state.dat`, `runtime/`, and transient download/cache content so beta activation creates a new independent DPAPI license state.

- [x] **Step 5: Write failing offline acceptance tests**

The offline tool must accept an explicit sandbox install root and injected `now` only in test/library APIs. It must load `state/license-state.dat` through `WindowsDpapiProtector` in real execution and use production `verify_signed_lease()` / `TrustedTimeState`.

Safe result schema:

```python
{
    "ok": True,
    "license_id": state.license_id,
    "device_hint": safe_device_hint(state.device_id),
    "lease_key_id": "lease-key-staging-01",
    "duration_seconds": 604800,
    "offline_valid_before_expiry": True,
    "offline_expired_after_expiry": True,
    "small_clock_correction_allowed": True,
    "rollback_rejection_code": "OFFLINE_LEASE_DENIED",
}
```

Tests must ensure complete license key, device token, raw lease bytes/signature, and DPAPI plaintext are absent from serialization.

- [x] **Step 6: Implement offline state verification**

Use exact boundary calculations and return only the rejection code:

```python
valid_at = lease.offline_until_datetime - timedelta(seconds=1)
expired_at = lease.offline_until_datetime + timedelta(seconds=1)
if lease.client_state_at(valid_at) == ClientLicenseState.OFFLINE_EXPIRED:
    raise AcceptanceError("lease expired before offline_until")
if lease.client_state_at(expired_at) != ClientLicenseState.OFFLINE_EXPIRED:
    raise AcceptanceError("lease remained valid after offline_until")
trusted.assert_not_rolled_back(server_time - timedelta(minutes=4))
try:
    trusted.assert_not_rolled_back(server_time - timedelta(minutes=10))
except UpdateError as exc:
    if exc.code != ErrorCode.OFFLINE_LEASE_DENIED:
        raise
    rollback_code = exc.code.value
else:
    raise AcceptanceError("significant wall-clock rollback was not rejected")
```

Real execution must refuse non-Windows environments and paths outside a marked Board 5 sandbox.

- [x] **Step 7: Write failing fault-package tests**

Given a known-good 0.5.1 EXE in a temporary input path, assert output ZIP members are exactly:

```text
wechat-cli.exe
app-manifest.json
```

and `app-manifest.json` is:

```json
{
  "product": "wechat-cli-web",
  "version": "0.5.2-board5bad.1",
  "platform": "windows",
  "architecture": "x86_64",
  "entrypoint": "wechat-cli.exe",
  "build_id": "staging-051-20260808.1"
}
```

The EXE input must match the frozen Board 4 internal EXE evidence exactly: size `14483951`, SHA-256 `dbbdf8ec70ddcf8d36145f099b0cb4ce3292c61e205c3ac7ae4db01fbc8907d1`. The tool must refuse overwrite and repository-contained output.

- [x] **Step 8: Implement deterministic fault-package assembly**

Implement the candidate by copying the frozen EXE bytes unchanged:

```python
def prepare_fault_package(known_good_exe: Path, output: Path) -> Path:
    assert_expected_file_sha256(
        known_good_exe,
        UPDATE_051_EXE_SHA256,
        UPDATE_051_EXE_SIZE,
    )
    if output.exists():
        raise FileExistsError(output)
    output = assert_outside_repository(output)
    with tempfile.TemporaryDirectory(prefix="board5-fault-") as tmp:
        assembly = Path(tmp)
        shutil.copy2(known_good_exe, assembly / "wechat-cli.exe")
        manifest = {
            "product": "wechat-cli-web",
            "version": "0.5.2-board5bad.1",
            "platform": "windows",
            "architecture": "x86_64",
            "entrypoint": "wechat-cli.exe",
            "build_id": "staging-051-20260808.1",
        }
        (assembly / "app-manifest.json").write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(assembly / "wechat-cli.exe", "wechat-cli.exe")
            archive.write(assembly / "app-manifest.json", "app-manifest.json")
    return output
```

Do not patch, corrupt, or execute arbitrary binary transformation.

- [x] **Step 9: Run Task 3 focused + full tests**

```powershell
python -m unittest \
  tests.test_board5_prepare_launcher_config \
  tests.test_board5_prepare_sandbox \
  tests.test_board5_offline_acceptance \
  tests.test_board5_prepare_fault_package
python -m unittest discover -s tests
git diff --check
```

Expected: all new tests pass; full suite passes with only the same two platform skips.

- [x] **Step 10: Commit Task 3**

```powershell
git add scripts/board5_*.py tests/test_board5_*.py
git commit -m "test: add board 5 staging acceptance tools"
```

---

### Task 4: Build and verify the repo-external staging bootstrap

**Files:**
- No source modification expected after Tasks 1-3.
- Repo-external outputs only under the approved Board 5 artifact root.
- Update evidence in: `docs/PROJECT_STATE.md`, `docs/deployment/authorized-update-roadmap.md` after verification.

**Purpose:** Produce the real 0.5.0/Launcher 0.1.0 staging bootstrap from `a579a25` without installing it and without changing the fixed 0.5.0 update ZIP.

**Authorization gate:** Obtain a new explicit **Bootstrap build gate** approval before any command in this task that builds binaries or writes repo-external bootstrap artifacts.

- [x] **Step 1: Read-only preflight**

Verify:

```powershell
# Board 5 branch
git status --short
git rev-parse HEAD

# build-source
git status --short
git rev-parse HEAD

# frozen runtime metadata source (read-only)
Get-Content 'C:\Users\28276\.devspace\worktrees\wechat-cli-1ec755b9-54a1291f\wechat_cli\version.py'

# main fixed artifact
Get-Item 'D:\use_as_desktop\Wechat__CLI\wechat-cli\dist\wechat-cli-app-0.5.0-win-x64.zip' | Select-Object Length
Get-FileHash -Algorithm SHA256 'D:\use_as_desktop\Wechat__CLI\wechat-cli\dist\wechat-cli-app-0.5.0-win-x64.zip'
```

Expected fixed artifact exactly `14291197` / `406b72c14ad186141f373087595f7723e143b9638bf298fde23b6bb0ae057523`.

Read-only check WebView2 presence and Python build dependencies. Confirm frozen `a579a25` has `APP_VERSION="0.5.0"`, `LAUNCHER_VERSION="0.1.0"`, and `BUILD_ID = os.environ.get("WECHAT_CLI_BUILD_ID", "dev")`. If `pywebview` or another launcher build dependency is missing, STOP and request separate local dependency-provisioning authorization. Do not silently `pip install`.

- [x] **Step 2: Initialize the repo-external Board 5 artifact root and generate launcher config**

After build-gate approval, create the Board 5 repo-external artifact root and immediately create its `.board5-acceptance-root` marker with the exact marker content expected by `assert_board5_root()`. Do not create this root/marker during the Local implementation gate. Every later local cleanup must refuse deletion if the marker is absent or invalid.

Then invoke the Board 5 config tool against the existing repo-external public-key registry. The command must not print key values. Example shape:

```powershell
python scripts/board5_prepare_launcher_config.py `
  --public-keys-file D:\use_as_desktop\Wechat__CLI\staging-secrets-20260805\launcher-public-keys.json `
  --api-url https://wechat-cli-license-update-staging.aurevior-ai.workers.dev `
  --channel stable `
  --port 18787 `
  --fingerprint-salt board5-staging-v1 `
  --output D:\use_as_desktop\Wechat__CLI\staging-secrets-20260805\board5\launcher-config.board5-staging.json `
  --json
```

Expected safe JSON: config hash/host/channel/port/key IDs only.

- [x] **Step 3: Build 0.5.0 app + Launcher 0.1.0 in the detached build-source worktree**

Run only in `a579a25` worktree:

```powershell
python npm/scripts/build.py win32-x64
```

Expected binaries under that worktree's `npm/platforms/win32-x64/bin/`. Verify `wechat-cli.exe --version` reports 0.5.0 and Launcher metadata remains 0.1.0. Do **not** inject `WECHAT_CLI_BUILD_ID` into the real build merely to make runtime health match package metadata; the frozen source's runtime build ID must remain an observed historical value.

- [x] **Step 4: Package bootstrap-only from the Board 5 tool**

Run from Board 5 worktree, pointing inputs to `a579a25`:

```powershell
python scripts/package_windows_app.py `
  --bootstrap-only `
  --launcher-config D:\use_as_desktop\Wechat__CLI\staging-secrets-20260805\board5\launcher-config.board5-staging.json `
  --source-root C:\Users\28276\.devspace\worktrees\wechat-cli-1ec755b9-54a1291f `
  --binary-root C:\Users\28276\.devspace\worktrees\wechat-cli-1ec755b9-54a1291f\npm\platforms\win32-x64\bin `
  --output-dir D:\use_as_desktop\Wechat__CLI\staging-secrets-20260805\board5\bootstrap `
  --version 0.5.0 `
  --build-id 0.5.0-local-20260805.1
```

`--build-id 0.5.0-local-20260805.1` is the bootstrap/package `app-manifest.json` historical build label only. It does not alter the frozen EXE runtime `BUILD_ID`.

Expected: bootstrap directory + one bootstrap ZIP only; no update ZIP.

- [x] **Step 5: Verify bootstrap bytes and source provenance**

Use `scripts/verify_windows_bootstrap.py` only if it can target the repo-external bootstrap without touching daily environment. Add/read-only verifier options first if necessary under a separate local implementation amendment; do not improvise installer execution.

At minimum verify ZIP members, 0.5.0 manifest, Launcher config safe fields, binary hashes, and source commits. For the real 0.5.0 runtime health evidence, strictly verify product/version/status and record the runtime `build_id` separately as observed; if it is `dev`, record `dev`. For 0.5.1, continue to require runtime `build_id=staging-051-20260808.1` exactly.

- [x] **Step 6: Recheck the fixed 0.5.0 update ZIP**

Repeat size/SHA query. Expected unchanged exactly.

If drifted: STOP Board 5 and report; do not overwrite/restore automatically.

- [x] **Step 7: Record evidence and commit documentation only**

Update non-sensitive status docs with bootstrap ZIP SHA/size/config SHA and source commits. Then:

```powershell
git diff --check
git add docs/PROJECT_STATE.md docs/deployment/authorized-update-roadmap.md
git commit -m "docs: record board 5 staging bootstrap"
```

No push/merge.

---

### Task 5: Create stable license and execute real 0.5.0 -> 0.5.1 Windows E2E

**Files:**
- Board 5 source should remain unchanged unless a verified defect is found; any defect starts `systematic-debugging` and requires scope review before code changes.
- Repo-external Board 5 acceptance roots and safe evidence files only.
- Later update: `docs/PROJECT_STATE.md`, roadmap, Board 5 report draft.

**Purpose:** Prove the normal production-like staging update chain using a new stable license and the existing read-only `rel_staging_051`.

**Authorization gates:** Separate approvals for (A) stable license creation, (B) isolated bootstrap installation/activation, and (C) stable real E2E download/restart/health. Do not combine them implicitly.

- [x] **Step 1: Stable license creation preflight**

Read-only confirm Board 4 license remains unchanged and no Board 5 stable license marker/metadata already exists. Confirm Worker health and `rel_staging_050/051` current hashes/status read-only.

- [x] **Step 2: After explicit stable-license approval, create exactly one stable license**

Use the existing admin CLI with `release_channel=stable` and `maximum_devices=1`. Save the complete key once to a new repo-external restricted file; do not echo it in chat/logs/history.

Record only:

```text
license_id
license_hint
release_channel=stable
status=active
maximum_devices
audit request_id
```

If response/write status is ambiguous: do not retry; reconcile by admin/D1 read-only lookup.

- [x] **Step 3: Prepare the isolated Windows root**

After explicit install/activation approval, create a repo-external root with marker:

```text
D:\use_as_desktop\Wechat__CLI\board5-windows-e2e\stable\
  .board5-acceptance-root
  LocalAppData\
  UserProfile\AppData\Roaming\
  UserProfile\.wechat-cli\
  Temp\
```

Construct a child-process environment only:

```python
env.update({
    "LOCALAPPDATA": str(root / "LocalAppData"),
    "APPDATA": str(root / "UserProfile" / "AppData" / "Roaming"),
    "USERPROFILE": str(root / "UserProfile"),
    "HOME": str(root / "UserProfile"),
    "TEMP": str(root / "Temp"),
    "TMP": str(root / "Temp"),
})
```

Do not change user/system environment variables globally.

- [x] **Step 4: Read-only WebView2 preflight**

If Runtime exists, installer must include `-SkipWebView2Check`.

If missing: STOP and request separate system-component installation authorization.

- [x] **Step 5: Install bootstrap into the isolated root**

Run the bootstrap installer with exactly:

```text
-NoStart -NoShortcuts -SkipProcessStop -SkipWebView2Check
```

and the isolated environment.

Immediately verify no shortcut was created, no daily install directory changed, and Board 5 `current.json` is 0.5.0/stable.

- [x] **Step 6: Activate stable license through the real Launcher UI**

The user pastes the complete key from the secure file into the real isolated Launcher. Do not put the key on the command line.

Post-activation verify safely:

```text
state/license-state.dat exists
DPAPI envelope is not plaintext JSON
license ID/hint matches Board 5 stable metadata
Worker device row is active
lease key ID = lease-key-staging-01
```

Never print decrypted state.

- [x] **Step 7: Verify real 0.5.0 health**

Launch the real isolated Launcher/app and query only loopback `/api/health`.

Expected:

```json
{"product":"wechat-cli-web","version":"0.5.0","status":"ok"}
```

Capture safe build ID separately.

- [x] **Step 8: Stable update preflight before external download**

After separate Stable E2E approval, read-only reconfirm `rel_staging_051`:

```text
enabled=true
paused=false
rollout=100
package size=14268929
package sha256=0ddbb0b402cc9d98ed001391c1a618527d165e328a1f4f1534d80e6b984956c0
manifest sha256=be111f0a786821319fb96f82f1748b4a75003b7c5fb296c48ec87b3355a3fd62
GitHub release/asset mapping unchanged
```

- [x] **Step 9: Trigger one real update check/download**

Use the installed Launcher/app update entrypoint, not a synthetic HTTP client. Confirm current 0.5.0 session remains alive during download.

Post-download verify:

```text
pending-update.json exists
candidate=0.5.1
package size/hash exact
signed manifest verifies under release-key-staging-01
safe extraction produced versions\0.5.1
```

- [x] **Step 10: Restart Launcher and verify atomic 0.5.1 activation**

Close the isolated app/Launcher cleanly and restart it once.

Expected:

```text
LauncherResult UPDATED or equivalent UI success state
/api/health version=0.5.1
current.json current_version=0.5.1
current.json previous_version=0.5.0
manifest_sha256=be111f0a786821319fb96f82f1748b4a75003b7c5fb296c48ec87b3355a3fd62
update transaction committed
```

- [x] **Step 11: Reconcile Board 4 releases read-only**

Confirm `rel_staging_050/051` state/hash/mapping are unchanged from Task 5 preflight. Any change not caused by an authorized Board 5 action stops acceptance.

- [x] **Step 12: Record stable-E2E evidence and commit docs**

Record only safe metadata, then local commit:

```powershell
git diff --check
git add docs/PROJECT_STATE.md docs/deployment/authorized-update-roadmap.md
git commit -m "docs: record board 5 stable windows e2e"
```

---

### Task 6: Verify offline lease and isolated beta fault rollback

**Files:**
- Use Task 3 tools; source modifications only if a verified defect is found.
- Repo-external `OfflineSandbox` / `RollbackSandbox`.
- Later update acceptance docs.

**Purpose:** Prove real offline startup from real DPAPI state and real staging rollback via a separate beta license/fault release without exploiting the Worker channel mismatch.

**Authorization gates:** Separate approvals for Offline acceptance, beta license creation, local fault preparation, fault publish/register, fault enable/rollback, and fault disable.

#### Part A: Offline acceptance

- [x] **Step 1: Create OfflineSandbox only after explicit offline-acceptance approval**

Copy the successful stable 0.5.1 Board 5 install/user state into a new marked OfflineSandbox. Do not touch the successful stable evidence root.

- [x] **Step 2: Make only the sandbox API unreachable through a controlled config tool**

Use `board5_prepare_launcher_config.py` or a dedicated safe mode to preserve keys/channel/port/salt while changing only API authority to a deterministic unused localhost HTTPS endpoint, such as `https://127.0.0.1:65534` after verifying that port is not listening.

Re-load with `LauncherConfig.load()` before launch.

- [x] **Step 3: Start the real Launcher and verify real offline fallback**

Expected:

```text
network validation fails
verified cached lease accepted
offline state = offline_valid
real 0.5.1 app health succeeds
```

- [x] **Step 4: Run deterministic boundary validation against the same DPAPI state**

Run:

```powershell
python scripts/board5_offline_acceptance.py `
  --board5-root D:\use_as_desktop\Wechat__CLI\board5-windows-e2e\offline `
  --expected-lease-key-id lease-key-staging-01 `
  --json
```

Expected safe result:

```text
duration_seconds=604800
offline_until-1s allowed
offline_until+1s expired
4-minute correction allowed
10-minute rollback -> OFFLINE_LEASE_DENIED
```

Do not alter Windows system time.

#### Part B: Beta license and RollbackSandbox

- [x] **Step 5: Create exactly one beta license after explicit beta-license approval**

Use `release_channel=beta` and `maximum_devices=1`. Store complete key only in a new repo-external restricted file. Record safe license metadata/audit ID only.

- [x] **Step 6: Prepare RollbackSandbox from successful 0.5.1 install**

Use `scripts/board5_prepare_sandbox.py`; do not copy stable `license-state.dat`. It must verify:

```text
current=0.5.1
previous=0.5.0
manifest=be111f0a786821319fb96f82f1748b4a75003b7c5fb296c48ec87b3355a3fd62
version dirs 0.5.0 and 0.5.1 exist
sandbox root marker valid
```

It then writes beta channel through `CurrentVersion` + `InstallLayout.save_current()` only.

- [x] **Step 7: Activate the beta license in the real RollbackSandbox Launcher**

User pastes the beta key from its secure file into the sandbox UI. Verify Worker/D1 safe metadata shows beta license and active beta device. This proves `license.release_channel=beta` and request/current channel beta are aligned; do not rely on the Worker channel trust-boundary gap.

#### Part C: Fault candidate and publication

- [x] **Step 8: Prepare the local fault ZIP only after explicit local-fault-prepare approval**

Use the approved 0.5.1 EXE bytes and candidate version `0.5.2-board5bad.1`:

```powershell
python scripts/board5_prepare_fault_package.py `
  --known-good-exe D:\use_as_desktop\Wechat__CLI\board5-windows-e2e\stable\LocalAppData\WeChatCliWeb\versions\0.5.1\wechat-cli.exe `
  --candidate-version 0.5.2-board5bad.1 `
  --build-id staging-051-20260808.1 `
  --output D:\use_as_desktop\Wechat__CLI\staging-secrets-20260805\board5\fault\wechat-cli-app-0.5.2-board5bad.1-win-x64.zip `
  --json
```

Verify the EXE bytes are unchanged and output members are exactly EXE + app-manifest.

Use existing release builder/prepare path to sign a **beta** release locally with new ID `rel_board5_bad_052_01`. No publish yet.

- [x] **Step 9: Fault publish/register preflight**

Before external write, read-only confirm:

```text
GitHub fault tag does not exist
D1 rel_board5_bad_052_01 does not exist
rel_staging_050/051 unchanged
prepared package/manifest hashes match approved local values
release repo clean
```

Any duplicate/unknown/drift -> STOP.

- [x] **Step 10: After explicit publish/register approval, create only the fault Draft/3 assets and disabled/paused Worker row**

Expected initial state:

```text
channel=beta
enabled=false
paused=true
rollout=100
```

No `--enable` in the publication command.

Post-write read-only reconcile GitHub Release/asset IDs and D1 hashes/mapping/audit request ID.

- [x] **Step 11: After explicit fault-enable approval, enable only the fault release**

Change:

```text
enabled false -> true
paused true -> false
rollout remains 100
```

Do not modify `rel_staging_050/051`.

- [x] **Step 12: Run one real beta update/download/restart in RollbackSandbox**

Expected chain:

```text
beta update selects 0.5.2-board5bad.1
signed download succeeds
safe extraction succeeds
pointer switches from 0.5.1 to candidate
candidate EXE starts but /api/health reports 0.5.1
health version mismatch triggers rollback
current restored to 0.5.1
failed-versions registry records candidate version + manifest hash
```

Rollback health of restored 0.5.1 must pass.

- [x] **Step 13: Verify version-level failed suppression accurately**

Execute one subsequent beta update check from the same RollbackSandbox. Expected: `0.5.2-board5bad.1` is not offered because client sends that version in `failed_versions`.

Evidence wording must say **version-level server suppression**. Do not describe this as server manifest-hash-level suppression.

- [x] **Step 14: After explicit fault-disable approval, disable/pause the fault release**

Expected final state:

```text
enabled=false
paused=true
rollout=100
```

Keep fault Draft/D1 row as disabled acceptance evidence unless a later explicit deletion approval says otherwise.

- [x] **Step 15: Record Task 6 evidence and Board 6 risks**

Update docs with:

```text
channel trust-boundary gap exists but was not used
failed registry local key is version+manifest hash; Worker suppression is version only
```

Commit docs locally; no push/merge.

---

### Task 7: Cleanup, full verification, acceptance report, and Board 5 closure

**Files:**
- Create: `docs/deployment/2026-08-12-board-5-windows-e2e-report.md`
- Modify: `docs/PROJECT_STATE.md`
- Modify: `docs/deployment/authorized-update-roadmap.md`
- Modify: `docs/superpowers/plans/2026-08-09-board-5-windows-staging-e2e.md` only to check completed steps/evidence after execution.

**Purpose:** Put all Board 5 remote/local state into an explicit terminal condition, prove Board 4 baselines remained unchanged, and produce a non-sensitive acceptance snapshot.

**Authorization gates:** Cloud cleanup and local deletion are separate. Final verification/reporting itself is read-only/local-doc work and can proceed after prior tasks, but must not infer permission to revoke/delete.

- [x] **Step 1: Read-only final state snapshot before cleanup**

Capture safe state for:

```text
stable Board 5 license/device
beta Board 5 license/device
rel_staging_050
rel_staging_051
fault release
GitHub v0.5.0 Draft / v0.5.1 published private release / fault private prerelease and assets
key audit request IDs
Board 5 stable/offline/rollback roots
```

- [x] **Step 2: After explicit Cloud cleanup approval, revoke Board 5 licenses and normalize test devices**

Only stable/beta Board 5 licenses/devices are cleanup targets. `JD25`, `rel_staging_050`, and `rel_staging_051` are not targets.

2026-08-12 completion evidence: the Cloud Cleanup Gate was explicitly approved. Both Board 5 licenses were changed to `revoked` at revision 2. The agent-side environment blocked the exact device-unbind writes before execution, so the user ran the existing Admin CLI against the same approved target set; fresh readback then proved both associated Board 5 test device rows were `unbound`, and both licenses reported `active_devices=0`. No D1-direct-write workaround or credential extraction was used. JD25, `rel_staging_050/051`, fault release state, GitHub release/assets/tags and local evidence roots were then reconciled read-only and remained unchanged.

The license-status and device-unbind Admin CLI responses do not expose request IDs in the retained output. The non-interactive Wrangler/D1 audit lookup lacks `CLOUDFLARE_API_TOKEN`, so the closure records this evidence limitation rather than reading or expanding a credential.

- [x] **Step 3: Confirm fault release is disabled/paused**

If already `enabled=false/paused=true`, do nothing. If not, STOP and request/confirm the fault-disable authorization; never silently mutate it during cleanup.

- [x] **Step 4: Run final code/test verification**

Run in Board 5 worktree:

```powershell
python -m unittest discover -s tests
cd services/license-update-worker
npm run typecheck
npm test -- --run
cd ../..
git diff --check
git status --short
```

If Worker dependencies are absent, restore only with the repository-tracked lockfile and a separately permitted local dependency step; do not mutate `package.json`/lockfile.

Expected: Python all pass with only known platform skips; Worker typecheck pass; Vitest 17/17 or later exact expected count after approved tests.

Phase A pre-cleanup baseline passed at Python 529 run / 2 expected skips / 0 failures, Worker typecheck PASS, Vitest 3 files / 21 tests. After device cleanup completed, the required fresh final rerun again passed at **Python 529 run / 2 expected skips / 0 failures, Worker typecheck PASS, Vitest 3 files / 21 tests**.

- [x] **Step 5: Reverify immutable Board 4/main evidence**

Read-only prove:

```text
main HEAD = a579a25cb7f16e6fdf88d618252b4a5cbffef53d
main status retains only intended untracked NUL
Board 4 worktree HEAD = 8c7464f and clean
fixed 0.5.0 update ZIP size/hash unchanged
rel_staging_050/051 state/hash/mapping unchanged
v0.5.0 Draft assets, v0.5.1 published-private assets, and fault prerelease assets unchanged
```

- [x] **Step 6: Create the Board 5 acceptance report**

Phase A created `docs/deployment/2026-08-12-board-5-windows-e2e-report.md` as a DRAFT. After cleanup and fresh final verification, it was converted to the **FINAL ACCEPTANCE / Board 5 accepted complete** report while retaining the initial rollback failure, TDD repair and fresh re-acceptance history.

Use exact final filename with the real completion date. Required sections:

```text
scope and authorization boundary
dual source baselines
bootstrap/config provenance
stable license + isolated install evidence
0.5.0 health
real 0.5.1 download/hash/restart/health
offline real-start + deterministic time-boundary evidence
beta license + RollbackSandbox channel alignment
fault Draft/Worker lifecycle
rollback evidence and exact failure reason
version-level suppression wording
cleanup state
Board 6 risk handoff
full tests/Git status
explicit list of actions not performed (push/merge/production/system-clock change)
```

- [x] **Step 7: Update roadmap/project state to Board 5 complete only if every exit condition is met**

If any exit condition is incomplete, canonical status must remain `Board 5 functional Windows E2E accepted; Task 7 closure pending` (or equivalent wording) and list the exact missing gate/evidence. Do not claim `Board 5 accepted complete` early.

- [x] **Step 8: Sensitive-value scan and diff review**

Run scans over staged Board 5 docs/source. Broad fixture-shaped test strings must be classified, not mistaken for real secret leakage. Non-test source/docs and repo-external evidence summaries must have zero real credential/private-key/license/device-token hits.

Run:

```powershell
git diff --check
git status --short
git diff --stat
git diff -- docs/PROJECT_STATE.md docs/deployment/authorized-update-roadmap.md docs/deployment/*board-5* docs/superpowers/plans/2026-08-09-board-5-windows-staging-e2e.md
```

- [x] **Step 9: Commit Board 5 closure docs locally**

```powershell
git add docs/PROJECT_STATE.md docs/deployment/authorized-update-roadmap.md docs/deployment/2026-08-12-board-5-windows-e2e-report.md docs/superpowers/plans/2026-08-09-board-5-windows-staging-e2e.md
git commit -m "docs: complete board 5 windows e2e acceptance"
```

No push/merge.

- [ ] **Step 10: Local physical cleanup only after separate deletion approval**

Delete only marked Board 5 roots/artifacts after evidence is committed and verified. The cleanup operation must refuse any path without `.board5-acceptance-root` and must never target:

```text
real %LOCALAPPDATA%\WeChatCliWeb
real %USERPROFILE%\.wechat-cli
main checkout
Board 4 worktree
release repo
staging-secrets root outside the Board 5 subdirectory
```

After deletion, perform read-only existence checks and report exactly what remains.

This step is optional and separately gated. Until such deletion approval is granted, keep it `[ ]` and record the roots/artifacts as `retained pending optional separately authorized local cleanup`.

---

## Board 5 completion checklist

Board 5 is complete only when all are true:

- [x] staging bootstrap proven from `a579a25` 0.5.0 app + Launcher 0.1.0
- [x] real staging config validated with approved release/lease key IDs
- [x] fixed 0.5.0 update ZIP unchanged
- [x] all Windows install/user data isolated under Board 5 roots
- [x] stable Board 5 license activated using real DPAPI
- [x] real 0.5.0 health passed
- [x] real private 0.5.1 download size/hash matched Board 4 evidence
- [x] real restart installed 0.5.1 and health passed
- [x] current/previous/manifest state exact
- [x] real network-unavailable offline Launcher startup passed
- [x] same real DPAPI state passed seven-day and rollback deterministic boundaries
- [x] beta license + beta RollbackSandbox channel alignment proved
- [x] independent fault candidate rolled back to 0.5.1 after health mismatch
- [x] subsequent same-version candidate suppression proved at version level
- [x] fault release final state disabled/paused
- [x] Board 5 stable/beta license/device cleanup state recorded
- [x] `rel_staging_050/051` unchanged
- [x] Board 4 worktree and main/NUL unchanged
- [x] Board 6 risk handoff records channel/suppression semantics plus the additional Board 5 visibility, credential, redirect, packaging, pywebview and integration risks
- [x] full tests/verifiers/Git checks passed
- [x] acceptance report committed locally
- [x] no push/merge/production/system-clock mutation occurred; GitHub tag creation was limited to the separately authorized v0.5.1/fault publish gates, and no tag modification occurred during closure

## Execution protocol

This plan is intentionally gated. Approval of the plan itself authorizes **none** of Tasks 1-7 implementation actions. Begin each side-effect class only after the user grants the matching gate described above.

For code implementation Tasks 1-3, use single-threaded `executing-plans` plus `test-driven-development`. For any failure, switch to `systematic-debugging` before changing code. Before any completion claim or checkpoint commit, use `verification-before-completion`.
