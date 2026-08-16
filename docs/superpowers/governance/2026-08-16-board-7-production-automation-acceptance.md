# Board 7 Production Automation Acceptance

Date: 2026-08-16
Gate: B7-G6 CI/CD Automation Acceptance
Status: ACCEPTED COMPLETE WITH EXPLICIT G6 IMMUTABILITY EXCEPTION

## Canonical entry

B7-G6 entered from the accepted B7-G5 closure lineage. The first G6 release-preparation attempt used canonical main `20335fa7df13e081ce779216e3564f036ec33422`; successive TDD repairs were integrated only through reviewed PRs and history-preserving merges. The accepted G6 production release was ultimately prepared from canonical main:

`c8f404b4d9d627f6530890b2f7a6b2c4f4743645`

Canonical-main CI run `31929765569` passed before the accepted production release-preparation run.

## CI/CD acceptance and repair history

G6 intentionally exercised the real production workflow rather than treating local tests as sufficient evidence. Four earlier attempts failed closed before an accepted release was left behind.

### Attempt 1 — package external-output contract

Workflow run: `31925665587`

The workflow failed before signing/publish because `package_windows_app.py --skip-build --update-only` ignored explicit `--output-dir`, `--version`, and `--build-id` inputs. No GitHub release/tag, D1 release row, or production R2 release object was created.

TDD repair implemented the explicit update-only contract and preserved the default historical behavior when no external output directory is requested. The repair lineage was merged through PR #9; canonical main became `8f7f457034a3f06c188614383a2fefd580edb76b` and post-merge CI run `31926841671` passed.

### Attempts 2 and 3 — production automation request visibility

Workflow runs: `31926930622` and `31927842739`

The workflow reached the machine automation surface but the Python client surfaced only `AUTOMATION_REQUEST_FAILED`. Independent readback proved there was still no GitHub `v0.6.0` release/tag, no D1 `rel_prod_0_6_0`, and no exact R2 package object.

A zero-mutation credential preflight was added first. It proved the GitHub production Environment held a valid Service Token because a PowerShell GET to `/v1/automation/releases` succeeded before signing. That repair merged through PR #10 as canonical main `6e99e8589fdd628f719ddf9a936fd9e2799197f8`; post-merge CI run `31927760201` passed.

A second zero-mutation Python transport probe was then added. It uses the exact production urllib transport to perform a read-only GET and a deliberately invalid one-byte PUT whose invalid SHA must be rejected by the Worker with `400 INVALID_REQUEST` before idempotency, body processing, D1 mutation, or R2 write. This repair merged through PR #11 as canonical main `dc5e25b555186f6f0966cf94f672a42dc250849f`; post-merge CI run `31928784674` passed.

### Attempt 4 — Cloudflare browser signature rejection

Workflow run: `31928872448`

The Python transport probe failed on its GET before any build/sign/publish step. Diagnostic response classification was exact:

- HTTP 403;
- Cloudflare error 1010;
- `browser_signature_banned`.

The production Service Token and Access policy were therefore not the root cause; the failing client shape was Python urllib's default request fingerprint. The existing admin transport already set a product User-Agent while the release automation transport did not.

TDD repair added the stable product User-Agent `WeChatCliReleaseAutomation/0.6.0` to both JSON and binary upload requests without changing Service Token headers, scopes, payloads, R2 logic, or release-state behavior. Repair commit `8789224cd62c78ad17bc8e1a8e5c63fd846c12a1` merged history-preserving through PR #12 as canonical main `c8f404b4d9d627f6530890b2f7a6b2c4f4743645`; post-merge CI run `31929765569` passed.

Fresh pre-integration verification for the final repair passed:

- Python: 706 run / 2 expected skips / 0 failures;
- Worker typecheck: PASS;
- Worker Vitest: 18 files / 132 tests PASS;
- deployment/workflow focused: 50/50 PASS;
- workflow policy: PASS;
- tracked sensitive-value scan: PASS;
- `git diff --check`: PASS.

## Accepted production release-preparation run

Workflow run: `31929835013`

Exact source SHA:

`c8f404b4d9d627f6530890b2f7a6b2c4f4743645`

Every step completed successfully, including:

- exact canonical-main proof;
- zero-mutation production Python automation transport probe;
- fresh Python and Worker verification;
- exact Windows application build;
- update package creation outside the repository;
- version/build/package verification;
- production trust-profile materialization;
- short-lived release-repository GitHub App installation token creation;
- exact release-provenance target resolution;
- Ed25519 release manifest signing with `release-key-production-01`;
- production R2 readiness through the automation route;
- private GitHub release provenance publication;
- disabled/paused production D1 registration;
- final read-only provenance/registration reconcile;
- temporary material cleanup.

## Accepted `0.6.0` production metadata

Production release row:

- release ID: `rel_prod_0_6_0`;
- version: `0.6.0`;
- channel: `stable`;
- manifest SHA-256: `af7c3aad001131f5255a479bb6b94859c7c7772c630b0625b816d0c91900256e`;
- package SHA-256: `7259580fd447028e9ee66827d72f1c481fb41593ba3b12e4e3e5edb52fdfc423`;
- package size: `15191871`;
- distribution backend: `r2`;
- object key: `releases/stable/rel_prod_0_6_0/7259580fd447028e9ee66827d72f1c481fb41593ba3b12e4e3e5edb52fdfc423.zip`;
- GitHub repository: `AuRevior-ai/wechat-cli-releases`;
- GitHub Release ID: `371243689`;
- package Asset ID: `516494905`;
- package asset name: `wechat-cli-app-0.6.0-win-x64.zip`;
- terminal state: `enabled=0`, `paused=1`, `rollout_percentage=0`.

Independent R2 download/readback returned exactly `15191871` bytes with SHA-256 `7259580fd447028e9ee66827d72f1c481fb41593ba3b12e4e3e5edb52fdfc423`, matching D1 and the GitHub package asset digest.

GitHub `v0.6.0` is private, published, non-draft, non-prerelease, and targets release-repository provenance commit `2b9fa385b86df83f7968239a1029d4d59f020027`. The release body records the full production source SHA `c8f404b4d9d627f6530890b2f7a6b2c4f4743645`.

The three release assets are:

- package Asset ID `516494905`, SHA-256 `7259580fd447028e9ee66827d72f1c481fb41593ba3b12e4e3e5edb52fdfc423`;
- manifest Asset ID `516494920`, SHA-256 `af7c3aad001131f5255a479bb6b94859c7c7772c630b0625b816d0c91900256e`;
- signature Asset ID `516494924`, SHA-256 `cb5f15f99aba751869c153fff816453465937168129a3599c209d8e4a479a252`.

## Machine authority acceptance

The production automation principal remains `release-automation-production` with only:

- `releases:upload`;
- `releases:read`;
- `releases:register`.

The Worker exposes automation routes only for package upload, release registration, and release metadata read. No `/v1/automation/*` release-state route exists. Release-state mutation remains on the human admin route and requires `releases:state` plus session authentication mode; controlled tests explicitly reject `access_service` and legacy auth modes even when a synthetic identity is given `releases:state`.

Production D1 audit readback for `rel_prod_0_6_0` contains exactly two successful automation actions:

1. `release.package_ready`, request ID `209866ab-f83c-4ed7-bbef-a151371fc8b3`;
2. `release.register`, request ID `e70b8e90-728c-4216-a3f9-79da512ea242`.

There is no automation `release.update` event for this release. Independent terminal readback remains `enabled=0`, `paused=1`, `rollout_percentage=0`.

## Explicit G6 native GitHub immutability exception

Independent post-publication verification found that GitHub reported the already-published `v0.6.0` release as:

`isImmutable=false`

The release repository's native Immutable Releases setting was also initially disabled. This differs from the Board 7 design phrase "private GitHub immutable provenance" if interpreted as GitHub's native Immutable Releases feature rather than the application's existing no-overwrite/no-normal-delete provenance discipline.

This triggered a Board 7 hard stop before G7. No deletion, republish, tag rewrite, R2 deletion, D1 rewrite, or release-state mutation was performed.

The user explicitly approved option A on 2026-08-16:

- retain the already-correct `v0.6.0` provenance/R2/D1 chain;
- record `v0.6.0` as the one G6 native-immutability governance exception;
- do not delete or republish it;
- enable GitHub native Immutable Releases prospectively for later release publications.

The release repository setting was then changed only from disabled to enabled. Fresh readback is:

- `enabled=true`;
- `enforced_by_owner=false`.

Fresh release readback still correctly reports existing `v0.6.0` as `isImmutable=false`; no retroactive claim is made.

Governance consequence:

- `v0.6.0` remains frozen by Board 7 policy and exact hash/ID evidence, but it is not claimed to have GitHub-native immutable-release enforcement;
- no further mutation to the existing `v0.6.0` tag/assets/release provenance is authorized by this exception;
- every later production release created after this setting change must be independently checked for GitHub-native immutability before its gate can be accepted;
- the first later production release that fails to report native immutability is a hard stop rather than another automatic exception.

## Accepted terminal state

B7-G6 is accepted complete with the explicit `v0.6.0` native GitHub immutability exception above.

Accepted terminal state:

- canonical production source for the prepared release: `c8f404b4d9d627f6530890b2f7a6b2c4f4743645`;
- stable production `0.6.0` exists exactly once;
- package/R2/GitHub/D1 hashes and IDs reconcile;
- D1 release state is `enabled=false`, `paused=true`, `rollout_percentage=0`;
- automation audit contains package-ready + register only;
- automation identity has no release-state capability/path;
- no production license or device was created by G6;
- current `v0.6.0` is the explicitly approved one-time native immutability exception;
- release-repository native Immutable Releases is now enabled for future release publications;
- commercial Authenticode remains deferred under Private / Controlled Distribution.

Next gate: B7-G7 Production Canary E2E. Exactly one internal beta production canary license/device is permitted; no real Private user issuance is permitted. The already registered stable `0.6.0` remains disabled/paused until the authorized human release-state step in G7.
