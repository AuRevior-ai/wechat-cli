# First Real User 0.6.1 Stable OTA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish stable `0.6.1` from exact canonical source and prove the first real external device upgrades from `0.6.0` to `0.6.1` through the production OTA path without manual binary replacement.

**Architecture:** Keep the accepted Board 7 production architecture unchanged. Make only the stable version metadata transition in source, integrate it through ordinary Git/hosted CI, publish a new immutable stable release through the existing least-privilege production workflow, then use human-only release-state control and the existing Launcher background-download/pending-update transaction on the single real stable device.

**Tech Stack:** Python 3.12, unittest, TypeScript/Vitest, GitHub Actions/GitHub App, Cloudflare Worker/D1/R2/Access, Ed25519, Windows Launcher 0.2.0.

**Design:** `docs/superpowers/specs/2026-08-17-first-real-user-061-stable-ota-design.md`

**Starting canonical main:** `131e1eba4d17d11445e61aea5ebb81c80555e913`

---

## Global invariants

1. Preserve `v0.6.1-canary.1` and `rel_prod_0_6_1_canary_1` exactly; never rename, rewrite, delete, or channel-mutate them.
2. Do not change Launcher `0.2.0`, shortcut/install UX, Worker source/deployment, credentials, Access topology, or license/device counts.
3. No production release workflow may run from an unmerged SHA. Production source must equal exact canonical `main` and pass canonical-main CI.
4. Automation may upload/read/register releases only. `release.update` remains human-only.
5. New `rel_prod_0_6_1` must first exist as disabled + paused. Human enable occurs only after immutable GitHub/R2/D1 reconciliation passes.
6. Never expose complete license, device token, Access credential, admin session, signing key, `.env`, or private-key material.
7. No manual file copy/replacement on the real-user computer. The accepted path is Launcher background download -> pending update -> next-start apply -> health -> commit/rollback.
8. Keep current local untracked `nul` untouched and excluded from every commit.
9. On any production/candidate failure, preserve evidence and stop external exposure; never replace immutable `v0.6.1` bytes in place.

---

## Task 1 — TDD stable version contract

**Files:**
- Modify first: `tests/test_version_metadata.py`
- Modify first: `tests/test_main.py`
- Modify first: `tests/test_windows_packaging.py`
- Then modify: `wechat_cli/version.py`
- Then modify: `pyproject.toml`

- [ ] **Step 1: Change version tests first**

Require:

```python
self.assertEqual("0.6.1", APP_VERSION)
self.assertEqual("0.6.1", project_version)
self.assertEqual(project_version, APP_VERSION)
self.assertEqual("0.2.0", LAUNCHER_VERSION)
```

Rename the canary-specific version tests to stable-release wording. Change CLI output expectation to `0.6.1`. Change Windows packaging metadata expectation to `version = "0.6.1"`.

- [ ] **Step 2: Prove RED**

Run:

```powershell
python -m unittest tests.test_version_metadata tests.test_main tests.test_windows_packaging -v
```

Expected before implementation: failures specifically because source/package metadata still says `0.6.1-canary.1` / `0.6.1.dev1`.

- [ ] **Step 3: Make the minimal implementation**

`wechat_cli/version.py`:

```python
APP_VERSION = "0.6.1"
LAUNCHER_VERSION = "0.2.0"
```

Leave `production_build_id()` unchanged.

`pyproject.toml`:

```toml
# Stable runtime SemVer and Python distribution version are identical.
version = "0.6.1"
```

Do not alter the historical canary compatibility mapping in `scripts/package_windows_app.py`.

- [ ] **Step 4: Prove GREEN**

Run the same focused test command and require zero failures.

- [ ] **Step 5: Verify no unauthorized behavior diff**

Use Git diff to require source/product changes are limited to stable version metadata and corresponding tests/design/plan. No Launcher logic, installer logic, Worker, workflow, Access, shortcut, or credential source change.

---

## Task 2 — Full local release-source verification and commit

- [ ] **Step 1: Run full Python suite**

```powershell
python -m unittest discover -s tests
```

Require zero failures; record actual run/skip counts.

- [ ] **Step 2: Run Worker verification**

```powershell
cd services/license-update-worker
npm run typecheck
npm test -- --run
cd ../..
```

Require typecheck PASS and all Vitest tests PASS.

- [ ] **Step 3: Run release/workflow guards**

```powershell
python -m unittest tests.test_release_workflow tests.test_workflow_policy -v
python scripts/verify_workflow_policy.py
python scripts/verify_no_tracked_secrets.py
git diff --check
```

Require all PASS.

- [ ] **Step 4: Stage exact reviewed files only**

Expected implementation set:

```text
wechat_cli/version.py
pyproject.toml
tests/test_version_metadata.py
tests/test_main.py
tests/test_windows_packaging.py
docs/superpowers/plans/2026-08-17-first-real-user-061-stable-ota.md
```

The already committed design stays in ancestry. `nul` remains untracked.

- [ ] **Step 5: Commit stable source**

Commit message:

```text
release: prepare stable 0.6.1
```

No amend/rebase/squash/history rewrite.

---

## Task 3 — Canonical source integration

- [ ] **Step 1: Exact remote preflight**

Require remote `main` still equals the expected canonical base or reconcile any new legitimate main movement before push. Ensure no existing open PR/remote branch collision for this exact release branch.

- [ ] **Step 2: Ordinary branch push**

Use structured `git_push_preview`/`git_push` when available. If the known HTTPS credential executor defect recurs, do not retry blindly; request one exact mechanical ordinary push from the user.

- [ ] **Step 3: Create PR**

PR title:

```text
release: prepare stable 0.6.1
```

Base `main`; head `release/0.6.1-first-real-user-ota`.

- [ ] **Step 4: Require hosted CI success**

Accept only checks bound to the exact PR head SHA.

- [ ] **Step 5: History-preserving merge**

Require CLEAN/MERGEABLE, remote main unchanged from premerge readback, and all required checks successful. Merge normally; no squash/rebase/force.

- [ ] **Step 6: Exact canonical-main CI**

Read back the merge commit as remote `main`; require the push-triggered CI run with exact `headSha` to complete SUCCESS.

---

## Task 4 — Production preflight and immutable `0.6.1` publication

All operations before workflow dispatch are read-only.

- [ ] **Step 1: Fresh D1 preflight**

Prove:

```text
rel_prod_0_6_1 does not exist
stable license count = 1
stable active device count = 1
我爸的电脑 is active and still reports App 0.6.0 / Launcher 0.2.0
rel_prod_0_6_0 remains enabled/unpaused/rollout 0
rel_prod_0_6_1_canary_1 remains disabled/paused/rollout 100
internal beta canary license/device remains one/one
```

- [ ] **Step 2: Fresh GitHub provenance collision preflight**

Prove no existing `v0.6.1` release/tag exists in `AuRevior-ai/wechat-cli-releases`. Confirm repository Immutable Releases remains enabled.

- [ ] **Step 3: Dispatch existing production publish workflow**

Use exact canonical main SHA with:

```text
version = 0.6.1
channel = stable
release_notes = First real-user stable OTA verification from 0.6.0 to 0.6.1.
```

Do not deploy Worker and do not change release state during this workflow.

- [ ] **Step 4: Require workflow success**

Require exact input/source canonical identity, Python/Worker verification, build, source-version check, signing, R2 readiness, immutable GitHub provenance, automation registration and read-only reconcile all PASS.

- [ ] **Step 5: Fresh publication reconcile**

Require exactly one `rel_prod_0_6_1`:

```text
version = 0.6.1
channel = stable
enabled = false
paused = true
rollout_percentage = workflow default/registered value before human mutation
distribution_backend = r2
```

Require D1 package/manifest SHA and size equal GitHub asset digests and fresh R2 download hashes. Require `v0.6.1` published, private repository provenance, `prerelease=false`, native `isImmutable=true`.

Require automation audit for the new release contains only `release.package_ready` and `release.register`; automation `release.update` successful count remains zero.

---

## Task 5 — Human-only enable for the single stable user

This task mutates only `rel_prod_0_6_1` release state after Task 4 reconciliation passes.

- [ ] **Step 1: Obtain a fresh human Access-backed admin session using the existing approved admin flow**

Do not expose the session value in tool output or docs.

- [ ] **Step 2: Set rollout to 100 through the human admin route**

Target exactly `rel_prod_0_6_1`.

- [ ] **Step 3: Enable and unpause exactly `rel_prod_0_6_1` through human admin state operations**

Do not alter `rel_prod_0_6_0`, beta canary state, license channel, device binding, or any credential.

- [ ] **Step 4: Read-only state/audit reconcile**

Require:

```text
rel_prod_0_6_1 enabled=true paused=false rollout=100
successful state mutations actor_type=admin / actor_id=production-primary-admin
automation release.update successful count=0
stable licenses/devices remain 1/1
beta canary unchanged
```

Then stop server-side changes. The next state transition happens on the user's father's computer.

---

## Task 6 — First real external stable OTA acceptance

- [ ] **Step 1: User starts current 0.6.0 normally while online**

No manual `--download-update` is required for normal-path acceptance: successful start spawns background update checking.

- [ ] **Step 2: Wait briefly for background preparation**

The user may leave the app open briefly. Server-side read-only evidence may be checked for update/download activity if available. Do not copy binaries manually.

- [ ] **Step 3: User fully closes WeChat CLI**

Allow the background downloader to finish before closing if evidence indicates it is still active.

- [ ] **Step 4: User starts WeChat CLI again through the installed launcher/start script**

Expected Launcher behavior:

```text
load pending update
switch current pointer to 0.6.1
start candidate
health check exact 0.6.1
commit transaction
start/open application
```

If candidate health fails, require automatic rollback to `0.6.0` and stop further exposure.

- [ ] **Step 5: Real-user local confirmation**

Confirm the application opens successfully after the update and reports/behaves as `0.6.1`; Launcher remains `0.2.0`. No manual binary replacement occurred.

- [ ] **Step 6: Production read-only acceptance**

After the next online validation, require `我爸的电脑` reports:

```text
last_app_version = 0.6.1
last_launcher_version = 0.2.0
status = active
```

Require stable license/device counts 1/1, beta canary unchanged, release states unchanged from Task 5, and no unexpected new license/device/credential/deployment/audit mutation.

---

## Task 7 — Acceptance record and closure

**Create:** `docs/superpowers/governance/2026-08-17-first-real-user-061-stable-ota-acceptance.md`

Record only safe evidence:

```text
canonical source/merge SHA and CI run
release ID/version/channel/state
GitHub release/asset IDs and public digests/sizes
R2/D1 reconciliation
human-only release-state audit
device safe ID/name and before/after version
Launcher version
update transaction outcome if observable without secret disclosure
canary isolation
explicit non-actions
```

Never record complete license/session/device-token/private-key values.

Run:

```powershell
python scripts/verify_no_tracked_secrets.py
git diff --check
```

Commit the docs-only acceptance record locally. Canonical integration of this final acceptance document may proceed through ordinary PR/CI/history-preserving merge under the user's continuing authorization; no further production mutation is implied.

---

## Completion condition

This plan is complete only when the real external stable device has upgraded from `0.6.0` to `0.6.1` via the production OTA mechanism, remained healthy, and the production readback confirms the expected version while all canary, identity, authorization and population boundaries remain intact.
