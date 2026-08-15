# Board 6 B6-G5 Staging Behavior Acceptance Report

> **FINAL GATE ACCEPTANCE — B6-G5 accepted complete with one documented non-blocking row-level cleanup residual.**
>
> Date: 2026-08-14
> Branch: `board6/security-delivery-preparation`
> Frozen main: `a579a25cb7f16e6fdf88d618252b4a5cbffef53d`
> Frozen Board 5 evidence: `67d3dec0fd1c4a02c87be1ab79c4f78ea63f49d6`
> Pre-gate canonical closure: `b20261536ec3ded6e55b18a639172bc16ed2998b`

## 1. Authorization and mutation boundary

B6-G5 was explicitly authorized for staging behavior acceptance and the user subsequently authorized continuation through the remaining Board 6 gates, subject to the standing hard boundaries that still require separate explicit action: no production mutation, no payment/code-signing certificate procurement or application, no push/merge, and no unrelated account/permission expansion.

The staging-only B6-G5 mutation set actually used was limited to:

- one disposable Access-mapped staging admin principal and short-lived `wcas` sessions;
- one disposable Board 6 beta acceptance release `rel_board6_g5_052_01` / `0.5.2-board6g5.1`;
- exact GitHub private Draft -> R2 readiness -> immutable private prerelease/tag -> disabled registration -> independent enable -> terminal disable/pause lifecycle;
- one disposable stable license and one disposable beta license, each with one deterministic test device;
- one disposable diagnostic upload/object;
- staging Worker deployments required to repair defects discovered by the acceptance itself;
- final revoke/disable/delete cleanup for the disposable credentials/resources above.

No production resource, production Worker, production route, production D1/R2, production Secret, Board 5 release, JD25, frozen main, push, merge, or real code-signing identity was mutated.

## 2. Local implementation defects discovered and repaired by real staging acceptance

B6-G5 did not merely replay unit tests. Real staging exposed four contract defects that were repaired under TDD and then re-accepted live.

### 2.1 Access JWKS fetch redirect mode

Initial real Access login reached the Worker but failed with `ADMIN_IDENTITY_INVALID` / “管理员身份密钥当前不可用。” A temporary staging-only JWKS connectivity probe proved:

- local host request to the exact configured JWKS endpoint returned HTTP 200 with two RS256 RSA JWKs;
- Worker runtime `fetch(..., { redirect: "error" })` failed with `TypeError`;
- the same exact Worker request using `redirect: "manual"` returned HTTP 200 with two keys;
- a temporary `global_fetch_strictly_public` experiment did not solve the problem and was removed;
- `redirect: "manual"` remains fail-closed because any 3xx is returned to the caller and rejected by the existing exact `status === 200` verifier contract.

Final repair: `3743580 fix: fetch Access JWKS without redirect errors`.
The temporary probe was removed and locked to 404 by `b4cd1a5 test: remove staging access jwks probe`.

### 2.2 R2 full-object response status

Real beta R2 range download passed, but a first full download received HTTP 206 where the Python updater correctly required HTTP 200. The cause was that real Cloudflare R2 may expose full-object `object.range={offset:0,length:total}` metadata even when the client did not send a Range request. The adapter incorrectly derived HTTP status from R2 response metadata instead of request intent.

Repair: `9a83447 fix: preserve full r2 download status`.
Acceptance after deployment proved:

- explicit byte range -> HTTP 206 + exact `Content-Range`;
- no client Range -> HTTP 200;
- full downloaded size/hash exactly match the signed release package.

### 2.3 Python update channel mismatch error contract

The Worker correctly returned `UPDATE_CHANNEL_MISMATCH`, but Python `ErrorCode` did not contain that value and would collapse it to `SERVICE_TEMPORARILY_UNAVAILABLE`. TDD added the missing stable client error contract.

Repair: `a9bb82c fix: preserve update channel mismatch errors`.

### 2.4 Diagnostics urllib identity at Cloudflare edge

Real diagnostic upload initially received Cloudflare edge error 1010 before reaching the Worker because `UrllibDiagnosticJsonTransport` and `UrllibDiagnosticBinaryTransport` inherited the default `Python-urllib/3.12` User-Agent. A controlled fake-token comparison proved:

- default Python UA -> Cloudflare edge 403 / 1010;
- `WeChatCliDiagnostics/0.5.1` -> request reached Worker and produced the expected Worker JSON authentication failure.

Both transports now send a fixed product UA while keeping credentials only in Authorization headers and never in URLs.

Repair: `360e505 fix: identify diagnostic upload client`.

The reusable B6-G5 acceptance helper and tests were committed as `49652c6 test: add board 6 staging behavior acceptance`.

After the final G5 Worker repair deployment, the current staging Worker Version ID is `6f2aad56-12cb-4d8e-8af5-9dceefbe1a49`. Fresh post-acceptance `/v1/health` returned `ok=true`, service `wechat-cli-license-update`, environment `staging`.

## 3. A-domain acceptance — channel authority and exact failed candidate identity

Two newly created disposable licenses were used, not JD25 and not Board 5 retired credentials:

- stable hint `GKSR`, maximum devices 1;
- beta hint `22Z5`, maximum devices 1.

One deterministic disposable device was activated for each license.

Live acceptance proved:

- stable license + stable request: aligned and no Board 6 beta update selected;
- stable license + beta request: exact non-retryable `UPDATE_CHANNEL_MISMATCH`;
- beta license + stable request: exact non-retryable `UPDATE_CHANNEL_MISMATCH`;
- beta license + beta request: selected exactly `rel_board6_g5_052_01` / `0.5.2-board6g5.1`;
- same version with an intentionally wrong manifest hash remained selectable;
- exact `(version, manifest_sha256)` failed-release identity suppressed the candidate;
- D1 ticket evidence showed tickets only for successful candidate selection. Stable no-update, both channel mismatches, and exact failed-candidate suppression created zero tickets.

This closes the Board 5 handoff risks for server-authoritative channel selection and exact failed-candidate suppression.

## 4. Immutable GitHub provenance + R2 runtime distribution acceptance

The disposable candidate used the frozen accepted 0.5.1 executable bytes and a Board 6 acceptance manifest declaring `0.5.2-board6g5.1`. Local package/signature verification passed before any remote lifecycle mutation.

Frozen runtime package:

- size: `14268937` bytes;
- SHA-256: `5bba2637a2d35b27434f22c7c632569e1d15aa6395037806cf421b20ab24ea02`.

Signed manifest SHA-256:

- `67fde6f1470dd2d69dc8a8af74b4f8409f0576686c7cbfde5ed060bce39a5a0e`.

Lifecycle order was accepted exactly as designed:

1. create private GitHub Draft and upload three exact assets;
2. keep real tag absent while Draft is inspection-only;
3. upload exact package to staging R2 through the scoped preparation path;
4. prove R2 exact object hash/size/readiness while candidate remained non-selectable;
5. only then publish GitHub immutable private prerelease/tag with `make_latest=false`;
6. reconcile assets/tag/digests after publication;
7. register Worker release disabled/paused with `distribution_backend='r2'`;
8. independently enable;
9. perform live range and full R2 downloads;
10. terminal cleanup returned the Worker candidate to disabled/paused while immutable GitHub provenance and exact R2 evidence were retained.

Final GitHub readback:

- Release database ID `370447805`;
- `draft=false`;
- `prerelease=true`;
- tag `v0.5.2-board6g5.1`;
- tag target / release-repository provenance commit `2b9fa385b86df83f7968239a1029d4d59f020027`;
- package asset digest exactly `sha256:5bba2637...ea02`;
- manifest asset digest exactly `sha256:67fde6f1...5a0e`;
- signature asset remained 64 bytes.

Final direct R2 readback again proved:

- size `14268937`;
- SHA-256 `5bba2637a2d35b27434f22c7c632569e1d15aa6395037806cf421b20ab24ea02`.

Final Worker row `rel_board6_g5_052_01` is `enabled=0`, `paused=1`, rollout 100, backend `r2`, with the exact package/manifest hashes above.

Historical rows were unchanged:

- `rel_staging_050`: enabled/unpaused/rollout 100, frozen hashes unchanged;
- `rel_staging_051`: enabled/unpaused/rollout 100, frozen hashes unchanged;
- `rel_board5_bad_052_01`: disabled/paused/rollout 100, frozen hashes unchanged.

## 5. Access cryptographic identity and short-lived admin session acceptance

The real staging Access application protected only:

`https://wechat-cli-admin-staging.aurevior-devspace.com/v1/admin/login/start`

The exchange endpoint remained outside the Access edge path as designed.

Real browser login succeeded using the approved email principal mapping. The Worker accepted only the cryptographically verified Access assertion and issued a challenge-bound one-time code followed by a short-lived `wcas` session.

Live metadata proved:

- one-time login code had bounded lifetime and `used_at` was populated;
- session absolute lifetime was exactly 30 minutes;
- `token_secret_version=1`;
- high-risk mutation after authentication age exceeded ten minutes failed with `ADMIN_RECENT_AUTH_REQUIRED`;
- an operation outside the principal scope failed with `ADMIN_SCOPE_DENIED`;
- normal staging operation never enabled legacy long-lived admin auth;
- workers.dev alternate ingress to admin login start failed closed with 403 while the Access custom domain owned the protected route;
- temporary Access/JWKS diagnostic endpoint was removed and now returns 404;
- no raw Access JWT or `wcas` credential was stored in governance evidence.

Two G5 short-lived sessions were finally marked `revoked`, and `admin_board6_g5_primary` was finally marked `revoked`; final active-session count is zero.

## 6. Origin/CORS and purpose-separated rate-limit acceptance

Live evil-Origin probes using a product-style User-Agent reached the Worker and returned Worker JSON `403 ORIGIN_NOT_ALLOWED` for both POST and native OPTIONS/preflight behavior.

No sensitive response emitted `Access-Control-Allow-Origin: *`.

The dedicated G5 admin-read principal bucket was stressed only in staging. A bounded concurrent run produced:

- 120 successful reads;
- 9 explicit Worker `429 RATE_LIMITED` results;
- 1 transient transport-level service error under concurrent load.

The first 429 therefore matched the configured 120/min principal limit. No production or shared principal traffic was used.

## 7. Diagnostics privacy, TTL, retention, download, and delete acceptance

A disposable 178-byte diagnostic ZIP was created from fixed test content and uploaded through the real device-authenticated diagnostics client.

Submission:

- ID `diag_y8ZSS5_emts_vbptWpIVrG27`;
- SHA-256 `2753be6efb725e826890d4adf9bb4f005166a236476707d68a341ab734d67ca6`;
- size 178 bytes;
- status reached `complete`.

D1 readback proved:

- opaque object path `diagnostics/2026-08-14/diag_y8ZSS5_emts_vbptWpIVrG27.zip`;
- no license/device identifier in the R2 path;
- upload expiry approximately 15 minutes after session creation;
- retention expiry exactly seven days after creation;
- `consent_version='diagnostics-consent-v1'`;
- upload TTL and retention TTL are separate fields.

Fresh deterministic retention tests passed and prove cleanup uses `retention_expires_at`, not upload expiry, and is idempotent.

Real admin download produced exactly the same SHA-256 as the uploaded bundle. First admin delete succeeded. A second delete also succeeded, proving immediate delete idempotency. Final D1 state is `deleted` with the audit row retained; content is no longer intended to be available while relational evidence remains.

## 8. Disposable credential/resource cleanup

Terminal cloud authorization state:

- G5 acceptance release: disabled + paused;
- stable test license `GKSR`: revoked, revision 2;
- beta test license `22Z5`: revoked, revision 2;
- G5 diagnostic: deleted;
- G5 admin sessions: revoked, active count 0;
- G5 admin principal: revoked;
- immutable GitHub provenance/tag retained;
- exact R2 release artifact retained as immutable transport/provenance evidence.

### Non-blocking row-level residual

The two disposable device rows still report `status='active'` in D1 even though their parent licenses are revoked. The normal Admin API unbind path was unavailable after the short-lived principal/session had already been revoked. A proposed exact D1-equivalent unbind + audit cleanup was blocked by the execution safety layer; it was **not bypassed**.

This is not an active credential: `authenticateDevice()` checks parent license state before accepting the device and returns `LICENSE_REVOKED` for these rows. The residual is therefore classified as row-level cleanup debt, not an authorization or acceptance failure. No claim is made that the two rows are `unbound`.

A future optional staging cleanup gate may unbind these two exact historical rows through a newly authenticated scoped admin session if desired. It is not required for Board 6 security acceptance because the parent credentials are revoked and all acceptance behavior is already proven.

## 9. Fresh final local verification

After all G5 defect repairs:

- Python full suite: **623 tests run / 2 expected skips / 0 failures**;
- Worker typecheck: PASS;
- Worker Vitest: **14 files / 92 tests PASS**;
- focused deterministic diagnostics retention suite: PASS;
- G5 behavior helper tests: PASS;
- `git diff --check`: PASS before governance edits;
- tracked worktree clean before governance edits; only the intentionally preserved `?? NUL` remains.

The expected packaging test branch that reports missing `pywebview` remains an intentional fail-fast test path and is not a suite failure.

## 10. Explicitly not performed

B6-G5 did not perform:

- production provisioning or mutation;
- production Worker deployment;
- production DNS/Access configuration;
- real Authenticode certificate purchase/application/provisioning/use;
- production/staging key rotation drill;
- removal/rotation of retained compatibility Secrets;
- deletion/unpublishing of immutable GitHub provenance;
- push, merge, rebase, amend, reset, tag rewrite;
- cleanup of frozen Board 5 worktrees/evidence or main `NUL`.

## 11. Gate conclusion

**B6-G5 Staging Behavior Acceptance Gate is accepted complete.**

The real staging acceptance closed the A-domain channel/suppression risks, proved GitHub-as-provenance plus R2-as-runtime-distribution, accepted short-lived Access-backed admin sessions, accepted explicit Origin/CORS and purpose-separated rate limiting, and accepted diagnostic privacy/retention/deletion behavior. Defects discovered by live acceptance were repaired under TDD and reverified in staging.

The next planned gate is **B6-G6 Code Signing Procurement & Real Staging Signing Gate**, but B6-G6 cannot be executed from the existing blanket continuation authorization because the approved plan requires separate explicit approval of provider/identity choice, any payment/application, identity verification, key provisioning, and actual signing. Until that approval exists, no real code-signing procurement or use may occur.
