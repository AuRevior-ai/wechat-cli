# Board 5 Windows Process-Tree Rollback Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Windows rollback stop the full PyInstaller application process tree, fail closed until port 18787 is released, and prevent residual candidate processes from producing false-positive restored health.

**Architecture:** Keep the existing `ApplicationProcessManager` / `LocalApplicationRuntime` / `LauncherService` boundaries. Add a Windows-only process-tree terminator to `ApplicationProcessManager`, add bounded port-release verification to `LocalApplicationRuntime.stop()`, and make `LauncherService.start()` treat candidate-stop failure as a rollback state restoration that must not launch the previous app. Rebuild only the Launcher and re-run the existing beta fault in a fresh repo-external RollbackRepairSandbox.

**Tech Stack:** Python 3, `unittest`, Windows `taskkill.exe`, sockets, PyInstaller, existing Board 5 staging Worker/GitHub prerelease.

---

## File map

- `wechat_cli/launcher/process.py`: Windows process-tree termination and post-stop port-release guard.
- `wechat_cli/launcher/service.py`: rollback orchestration when candidate stop fails.
- `tests/test_launcher_process.py`: RED/GREEN coverage for Windows tree-stop and port-release semantics.
- `tests/test_launcher_service.py`: RED/GREEN coverage for fail-closed rollback when candidate stop fails.
- `docs/PROJECT_STATE.md`: post-fix / post-real-acceptance evidence only after verification.
- `docs/deployment/authorized-update-roadmap.md`: Board 5 status/evidence after real acceptance.

No new production modules are required.

### Task 1: Windows process-tree stop and port-release guard

**Files:**
- Modify: `tests/test_launcher_process.py`
- Modify: `wechat_cli/launcher/process.py`

- [ ] **Step 1: Add a failing Windows tree-stop test**

Add a test that patches `os.name` to `nt`, injects a fake tree terminator into `ApplicationProcessManager`, stops a `FakeProcess` with a known PID, and asserts the terminator receives exactly that PID and the original `FakeProcess.wait()` is called. The old implementation must fail because no tree terminator exists.

Target shape:

```python
def test_windows_stop_terminates_entire_process_tree(self):
    calls = []
    process = FakeProcess([], shell=False)
    process.pid = 4242
    manager = ApplicationProcessManager(
        popen=lambda *_args, **_kwargs: None,
        tree_terminator=lambda pid: calls.append(pid),
    )
    with patch("wechat_cli.launcher.process.os.name", "nt"):
        manager.stop(process, timeout_seconds=1)
    self.assertEqual([4242], calls)
```

- [ ] **Step 2: Run the RED test**

Run:

`python -m unittest tests.test_launcher_process.LauncherProcessTests.test_windows_stop_terminates_entire_process_tree -v`

Expected: FAIL because `ApplicationProcessManager` does not accept/use `tree_terminator`.

- [ ] **Step 3: Add a failing tree-terminator failure test**

Add a test where the injected tree terminator raises `OSError("tree stop failed")`; `manager.stop()` must propagate an exception and must not report success.

- [ ] **Step 4: Add failing port-release tests**

Make `LocalApplicationRuntime` accept an injectable `port_probe` callable. Add one test where the probe transitions from occupied to free and stop succeeds, and one where it remains occupied until timeout and stop raises. Use short injected timeout/interval values so tests stay fast.

Target behavior:

```python
runtime = LocalApplicationRuntime(
    layout,
    port=8787,
    process_manager=manager,
    port_probe=lambda _port: True,
    stop_timeout_seconds=0.01,
    stop_interval_seconds=0.001,
)
with self.assertRaises(OSError):
    runtime.stop(process)
```

- [ ] **Step 5: Run the process RED set**

Run:

`python -m unittest tests.test_launcher_process -v`

Expected: new tests FAIL for missing tree-stop / port-release behavior; existing tests remain otherwise healthy.

- [ ] **Step 6: Implement minimal Windows tree termination**

In `ApplicationProcessManager.__init__`, add an injectable `tree_terminator` defaulting to a private helper. The helper must execute:

```python
subprocess.run(
    ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
    check=True,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    shell=False,
)
```

Windows `stop()` must call the tree terminator for `process.pid`, then wait for the original Popen to become terminal. Non-Windows keeps the existing `terminate -> wait -> kill-on-timeout` behavior.

- [ ] **Step 7: Implement bounded port-release verification**

Add a private default port probe using `socket.create_connection(("127.0.0.1", port), timeout=...)`: connection success means occupied; connection refusal/error means free. `LocalApplicationRuntime.stop()` must call `process_manager.stop()` and then poll until the port is free. If still occupied at the bounded stop timeout, raise `OSError("application port did not release after process stop")`. Clear `_process` only after successful release.

- [ ] **Step 8: Run GREEN process tests**

Run:

`python -m unittest tests.test_launcher_process -v`

Expected: all launcher process tests PASS.

### Task 2: Fail-closed rollback orchestration on candidate-stop failure

**Files:**
- Modify: `tests/test_launcher_service.py`
- Modify: `wechat_cli/launcher/service.py`

- [ ] **Step 1: Add stop-failure support to the test fake**

Extend `FakeRuntime` with `stop_error: Exception | None = None`; when set, `stop()` records the process and raises that exception.

- [ ] **Step 2: Add a failing rollback stop-failure test**

Create a pending unhealthy candidate and a `FakeRuntime(unhealthy_versions={"0.5.0"}, stop_error=OSError("candidate port still occupied"))`.

Assert after `service.start()`:

```python
self.assertEqual(LauncherStatus.FAILED, result.status)
self.assertEqual("0.4.2", layout.load_current().current_version)
self.assertEqual(["0.5.0"], [item["version"] for item in runtime.starts])
self.assertTrue(
    UpdateTransactionEngine(layout).failed_versions.is_failed("0.5.0", "22" * 32)
)
self.assertIn("candidate port still occupied", result.reason)
```

The old implementation must fail because it swallows candidate-stop failure and starts the previous version.

- [ ] **Step 3: Run the RED service test**

Run:

`python -m unittest tests.test_launcher_service.LauncherServiceTests.test_candidate_stop_failure_rolls_pointer_back_but_does_not_start_previous -v`

Expected: FAIL with old `ROLLED_BACK` / previous-start behavior.

- [ ] **Step 4: Implement minimal fail-closed orchestration**

In the candidate health exception branch:

1. Capture any exception from `self.runtime.stop(process)` into `stop_error` instead of discarding it.
2. Always call `self.transactions.rollback(...)` so pointer and failed registry are restored/recorded.
3. If `stop_error` is not `None`, return `LauncherResult(LauncherStatus.FAILED, version=restored.current_version, license_state=authorization.state, reason=f"candidate stop failed after update health failure: {stop_error}")` without starting previous version.
4. Only enter the existing previous-version start/health path when candidate stop succeeded.

Do not change successful rollback semantics.

- [ ] **Step 5: Run GREEN service tests**

Run:

`python -m unittest tests.test_launcher_service -v`

Expected: all launcher service tests PASS, including existing successful rollback regression.

### Task 3: Focused and full verification, then rebuild Launcher

**Files:**
- No additional production files unless tests expose a defect.
- Build output remains existing ignored build output; do not commit binaries.

- [ ] **Step 1: Run focused launcher/update tests**

Run:

`python -m unittest tests.test_launcher_process tests.test_launcher_service tests.test_update_transaction tests.test_launcher_cli -v`

Expected: PASS.

- [ ] **Step 2: Run Windows packaging/build contract tests**

Run:

`python -m unittest tests.test_windows_packaging -v`

Expected: PASS.

- [ ] **Step 3: Run Python full suite**

Run the project’s established full Python test command (currently `python -m unittest discover -s tests -v` unless repository state shows a canonical alternative).

Expected: no failures; platform skips allowed only if already expected.

- [ ] **Step 4: Run diff and sensitive checks**

Run `git diff --check`, inspect `git status --short`, `git diff --stat`, and targeted diff for `process.py`, `service.py`, and their tests. Scan changed production/docs files for token/password/license/device-token patterns; expected zero sensitive values.

- [ ] **Step 5: Commit the code repair locally**

Commit only the intended implementation/tests with a message such as:

`fix: stop windows launcher process trees`

No push/merge.

- [ ] **Step 6: Rebuild Launcher only**

Run:

`python npm/scripts/build.py win32-x64 --target launcher`

Verify the resulting `wechat-cli-launcher.exe` exists and record size/SHA-256. Do not rebuild or replace the frozen 0.5.1 app bytes.

### Task 4: Fresh RollbackRepairSandbox real acceptance

**Files / external evidence:**
- Create repo-external: `D:\use_as_desktop\Wechat__CLI\board5-windows-e2e\rollback-repair`
- Preserve old `...\rollback` evidence unchanged.
- Update docs only after acceptance evidence is complete.

- [ ] **Step 1: Preflight live external state read-only**

Confirm GitHub Release `368572125` remains `draft=false / prerelease=true`, assets/digests unchanged, tag points to `2b9fa385...`, and Worker `rel_board5_bad_052_01` remains beta / enabled / unpaused / rollout 100. Confirm stable 0.5.1 listener/health/session valid.

- [ ] **Step 2: Create a new marked RollbackRepairSandbox**

Copy from the successful stable install using the tested Board 5 sandbox helper so runtime/cache and stable `license-state.dat` are not inherited. Set current channel to beta through `CurrentVersion + InstallLayout.save_current()`.

Copy only the already-authorized beta DPAPI state needed for the same beta license into the new sandbox; do not copy old `failed-versions.json`, pending state, candidate directory, or transaction failure evidence.

- [ ] **Step 3: Replace only the new sandbox Launcher**

Copy the freshly rebuilt `wechat-cli-launcher.exe` into the new RollbackRepairSandbox launcher directory. Verify its size/SHA-256 and leave stable Launcher untouched.

- [ ] **Step 4: Real one-byte and full download preflight**

Using the new sandbox beta state, verify update selection returns `rel_board5_bad_052_01` and 1-byte Worker probe returns HTTP 206 with `bytes 0-0/14268937`. Then run the real Launcher `--download-update` in D:-isolated environment and verify frozen ZIP/manifest/candidate hashes and current still 0.5.1/beta.

- [ ] **Step 5: Real apply/rollback**

Temporarily stop the exact stable listener tree to free 18787. Run the rebuilt Launcher `--apply-update` in the new sandbox. Verify:

- transaction state `rolled_back`;
- failure reason is candidate health version mismatch;
- current restored to 0.5.1;
- failed registry records candidate version + frozen manifest hash;
- no process from `versions/0.5.2-board5bad.1` remains;
- the sole 18787 listener path belongs to `versions/0.5.1/wechat-cli.exe` inside RollbackRepairSandbox;
- health is `0.5.1 / staging-051-20260808.1 / ok / license_session_valid=true`.

- [ ] **Step 6: Verify version-level server suppression**

Run one subsequent beta update check from the same RollbackRepairSandbox using its failed versions. Expected: no fault update is offered. Record evidence explicitly as **version-level server suppression**; local registry remains version + manifest hash.

- [ ] **Step 7: Restore stable and stop repair sandbox**

Stop only the exact RollbackRepairSandbox app process tree, restore stable 0.5.1, and verify the sole 18787 listener/path/health/session belongs to stable. Preserve RollbackRepairSandbox evidence; no cleanup.

- [ ] **Step 8: Update canonical docs and commit acceptance evidence**

Update `docs/PROJECT_STATE.md` and `docs/deployment/authorized-update-roadmap.md` with safe metadata only. Run `git diff --check`, sensitive scan, fresh external read-only reconcile, and commit locally. Do not disable fault release yet; fault-disable remains a separate gate.

---

## Completion boundary

This plan is complete only when automated RED/GREEN evidence and a fresh RollbackRepairSandbox prove the orphan child is gone, the restored listener is genuinely the previous version, license session is valid, and version-level suppression works. No production mutation, fault-disable, cleanup, push, or merge is included.