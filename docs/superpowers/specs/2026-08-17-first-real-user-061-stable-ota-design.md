# First Real User 0.6.1 Stable OTA Design

Date: 2026-08-17
Status: APPROVED DIRECTION — pending written-spec review before implementation

## 1. Goal

Perform the first real external-user production OTA for the already activated stable device `dev_a9eXbN7k-X9Xar75-_K5sWCKm4kelEJr` (`我爸的电脑`), upgrading the installed application from stable `0.6.0` to a new stable `0.6.1` release while keeping Launcher `0.2.0` unchanged.

This run is intentionally a pure OTA-chain verification. It must not include desktop-shortcut work, installer UX changes, unrelated product features, or permission/scope expansion.

## 2. Current accepted baseline

Canonical source before this release branch: `131e1eba4d17d11445e61aea5ebb81c80555e913`.

Production baseline:

- stable release `rel_prod_0_6_0`: enabled, unpaused, rollout 0;
- internal beta candidate `rel_prod_0_6_1_canary_1`: disabled, paused, rollout 100, immutable GitHub provenance retained;
- exactly one active beta canary license/device remains internal;
- stable license `lic_moOphTS-64IW4bvaqNurnuI0`: active, maximum devices 1;
- exactly one active stable device exists, named `我爸的电脑`;
- the stable device last reported App `0.6.0` / Launcher `0.2.0`;
- first install, close/reopen, and Windows reboot acceptance have passed on that real external device.

## 3. Release identity

The new release is a distinct production release:

- version: `0.6.1`;
- channel: `stable`;
- release ID: `rel_prod_0_6_1`;
- GitHub tag: `v0.6.1`;
- Launcher minimum/current version: `0.2.0`;
- minimum app version: `0.6.0`;
- distribution backend: R2;
- GitHub provenance: private and natively immutable;
- initial registration state: disabled + paused;
- release-state mutation: human-only.

`v0.6.1-canary.1` is historical internal-canary provenance and must not be renamed, converted, deleted, overwritten, or channel-mutated.

## 4. Source change boundary

The source change is deliberately minimal.

Required runtime/package metadata changes:

1. `wechat_cli/version.py`
   - `APP_VERSION`: `0.6.1-canary.1` -> `0.6.1`;
   - `LAUNCHER_VERSION` remains `0.2.0`;
   - `production_build_id()` remains unchanged for this release to avoid introducing a second independent build-identity change during the first external OTA.

2. `pyproject.toml`
   - project version: `0.6.1.dev1` -> `0.6.1`;
   - update comment to describe stable runtime/package parity.

3. Tests that currently freeze the internal-canary version must be changed first under TDD to require stable `0.6.1`.

The existing `scripts/package_windows_app.py` compatibility mapping for historical `0.6.1-canary.1 -> 0.6.1.dev1` may remain because `read_version()` already defaults stable runtime versions to identical PEP 440 versions. No packaging behavior change is required.

No other product behavior is authorized by this release.

## 5. TDD and local verification

Before implementation, version-contract tests are changed to expect stable `0.6.1` and must fail against the current canary source.

After the minimal version changes, run at least:

- version metadata focused tests;
- CLI version-output tests;
- Windows packaging version tests;
- production workflow policy tests;
- full Python suite;
- Worker typecheck and full Vitest suite;
- workflow policy verifier;
- tracked sensitive-value scan;
- `git diff --check`.

The source branch must then be integrated into canonical `main` through ordinary push, PR, hosted CI, and a history-preserving merge. No production release workflow may run from an unmerged SHA.

## 6. Production publish sequence

After exact canonical-main CI passes for the stable-version source commit/merge:

1. fresh production preflight proves:
   - no existing `rel_prod_0_6_1` D1 row;
   - no existing `v0.6.1` GitHub release/tag collision;
   - current stable device still reports `0.6.0`;
   - current canary remains isolated and unchanged.

2. run `publish-production-release.yml` manually with:
   - exact canonical main SHA;
   - version `0.6.1`;
   - channel `stable`;
   - concise private release notes identifying this as the first real-user stable OTA verification.

3. workflow must:
   - build exact application bytes from canonical main;
   - verify source `APP_VERSION == 0.6.1`;
   - sign the manifest with the existing production Ed25519 release key;
   - publish immutable private GitHub provenance;
   - upload exact R2 runtime bytes;
   - register `rel_prod_0_6_1` through automation;
   - leave it disabled + paused;
   - perform no license/device/release-state mutation.

4. read-only reconcile GitHub/R2/D1 hashes, asset IDs, release identity, native immutability, and automation audit before any human enable.

## 7. Human release-state gate

Only after publication reconciliation passes, use a fresh human Access-backed admin session to make the exact stable `0.6.1` release eligible.

For this first real external OTA:

- target release: only `rel_prod_0_6_1`;
- set rollout to 100;
- enable and unpause through human admin state operations only;
- automation must still have zero successful `release.update` events;
- do not modify the stable license channel or device binding;
- do not touch beta canary release state.

Because production currently contains exactly one stable license/device, rollout 100 exposes the new stable release only to that current stable population. Creating additional stable licenses is outside this run.

## 8. Real-user OTA behavior

The installed Launcher already performs background update checking after a successful normal launch.

Expected real sequence on `我爸的电脑`:

1. start the currently installed `0.6.0` normally while online;
2. Launcher validates the license or uses the accepted authorization path and starts the app;
3. Launcher spawns the background `download-update` flow;
4. the production Worker selects stable `0.6.1` for the stable license;
5. package/manifest/signature download and verification complete;
6. `pending-update.json` is prepared locally;
7. close the currently running app;
8. start WeChat CLI again;
9. Launcher applies the pending update before launching the application;
10. new `0.6.1` health must pass;
11. transaction commits and the application starts on `0.6.1`.

No direct file copying or manual replacement of installed binaries is allowed during acceptance.

## 9. Failure behavior

If `0.6.1` fails download, signature/hash verification, extraction, launch, or health acceptance:

- do not delete evidence;
- do not force the installed pointer;
- Launcher must keep or restore `0.6.0` according to the existing update transaction contract;
- failed release identity must be recorded/suppressed as designed;
- stable `0.6.1` must be human-paused/disabled before any further external-user attempt if the failure is release-related;
- any repair requiring product behavior changes returns to systematic debugging + TDD and a new reviewed canonical commit before republishing a new immutable version.

Immutable `v0.6.1` bytes must never be replaced in place after publication. A bad published release is forward-fixed by a new version.

## 10. Acceptance evidence

The first real stable OTA is accepted only when all of the following are freshly proven:

- exact canonical-main source and CI passed;
- `v0.6.1` GitHub release is private, published, and natively immutable;
- D1/R2/GitHub package and manifest identities reconcile;
- automation only performed package-ready/register behavior;
- release-state changes were human-only;
- `我爸的电脑` obtains the stable update through the production update service;
- the installed application becomes `0.6.1` without manual binary replacement;
- Launcher remains `0.2.0`;
- post-update health succeeds;
- production D1 later records the stable device on App `0.6.1` / Launcher `0.2.0` after its next online validation;
- the internal beta canary remains unchanged;
- stable license/device counts remain exactly one/one;
- no additional license, device, credential, deployment, or public-distribution side effect occurs.

## 11. Explicitly out of scope

This OTA does not authorize:

- desktop or Start-menu shortcut changes;
- installer rebuild for user-experience improvements;
- Launcher version bump;
- a second real stable license/device;
- public distribution;
- commercial Authenticode;
- credential rotation/retirement;
- Worker deployment;
- production topology/Access changes;
- deletion/cleanup of historical evidence, worktrees, `NUL`, or the current untracked `nul` artifact.

## 12. Completion boundary

Successful completion means the first real external stable device has moved from `0.6.0` to `0.6.1` through the production OTA path, with server-side and local acceptance evidence.

After that, desktop-shortcut UX can be designed as a separate installer/Launcher improvement rather than being mixed into this first OTA proof.
