# Board 7 Recovery / Controlled Release Pre-License Acceptance

Date: 2026-08-17
Gate: B7-G8 First Controlled Release & Recovery Gate
Scope: Tasks 39–42 only
Status: ACCEPTED THROUGH TASK 42 — MANDATORY STOP BEFORE TASK 43 FIRST REAL PRIVATE LICENSE

## Entry boundary

B7-G8 entered only after B7-G7 governance closure merged history-preserving through PR #23.

Fresh entry readback:

- canonical remote `main`: `c24783ff9150fba465747d4592bc845f1ab2e485`;
- PR #23 state: merged;
- exact canonical-main CI run `31987868264`: success for the same SHA;
- retained historical checkout `D:\use_as_desktop\Wechat__CLI\wechat-cli` was not modified or cleaned;
- no real stable production license existed at G8 entry.

The G8 work branch is `board7/production-recovery-g8`, created from exact canonical main `c24783ff9150fba465747d4592bc845f1ab2e485` after a clean-worktree preflight.

## Fresh production reconciliation

Production D1 readback at G8 entry proved:

- stable `rel_prod_0_6_0`: version `0.6.0`, channel `stable`, `enabled=1`, `paused=0`, rollout `0`;
- internal beta `rel_prod_0_6_1_canary_1`: version `0.6.1-canary.1`, channel `beta`, `enabled=0`, `paused=1`, rollout `100`;
- active beta licenses: exactly `1`;
- active stable licenses: exactly `0`;
- active devices: exactly `1`;
- automation principal `release-automation-production`: active with only `releases:upload`, `releases:read`, `releases:register`.

Fresh release-state audit readback contained only human-admin state changes. The accepted candidate enable, rollout, and terminal pause/disable events are attributed to `production-primary-admin`; no automation `release.update` event exists.

## Task 39 — human-only release state and controlled rollout

Task 39 is accepted without manufacturing additional production state mutations.

Real G7 production evidence already exercised the named candidate through fresh human Access/recent-auth for:

- enable/unpause;
- rollout change to 100 for the sole internal beta canary;
- terminal pause/disable.

G8 fresh readback proved those operations remain human-attributed and that the automation principal still lacks `releases:state`.

Fresh focused Worker tests:

- `test/automation_routes.test.ts`;
- `test/automation_auth.test.ts`;
- `test/admin.test.ts`.

Result: `3 files / 27 tests PASS`.

These tests include the stronger invariant that an `access_service` or legacy identity remains unable to mutate release state even if a synthetic configuration accidentally gives it `releases:state`; normal state mutation requires session authentication mode.

Fresh live ingress evidence:

- production API `/v1/health`: HTTP 200;
- API host `/v1/admin/releases`: Worker-level `INGRESS_NOT_ALLOWED`;
- Admin host `/v1/admin/releases` without a human session: HTTP 401;
- Admin host `/v1/automation/releases` without a Service Token: HTTP 403;
- production workers.dev URL: HTTP 404.

No stable real-user population exists, so G8 does **not** fabricate `25 -> 50 -> 100` rollout evidence. The future stable rollout policy remains unexercised until population makes percentage evidence meaningful.

No release-state mutation was performed merely for Task 39 ceremony.

## Task 40 — Worker last-known-good recovery drill

### Accepted LKG identity

The current production deployment remains:

- Worker Version ID `ceedf5c8-111c-41e8-83f2-72733225352c`;
- deployment percentage `100`;
- accepted G5 source lineage `f760355779d05f59d1bcc81bd3dec40d38872be2`;
- production D1 `011b3c26-bbe6-4bb7-8af7-39f1e6d46932`;
- production R2 buckets `wechat-cli-diagnostics-production` and `wechat-cli-releases-production`;
- public API origin `https://wechat-cli-api.aurevior-devspace.com`;
- Admin origin `https://wechat-cli-admin.aurevior-devspace.com`;
- `workers_dev=false`.

Current Worker version metadata still reports the exact production audiences, resource bindings, V1 selector metadata, `lease-key-production-01`, and production origins. Secret bindings were inspected only by name/type; no secret values were read.

### Why no new Worker version was created

A path-limited Git comparison from accepted G5 source `f760355...` to accepted G7 implementation main `8afbc7a0...` produced zero differences for:

- `services/license-update-worker`;
- `scripts/deploy_worker.py`;
- `.github/workflows/deploy-production-worker.yml`.

G7 governance closure from `8afbc7a0...` to current canonical main `c24783ff...` is docs-only. Therefore current canonical main carries the same Worker/deploy semantics already running as the accepted production LKG.

Strong Authorization explicitly says a harmless same-functionality/new-version Worker may be created only when technically necessary for a meaningful recovery drill. Creating another version here would be mutation solely for ceremony, so G8 intentionally did not redeploy.

### Recovery primitive verification

The production deploy workflow was re-read and requires:

- manual `workflow_dispatch`;
- exact 40-character `source_sha`;
- checkout of the requested SHA;
- independent GitHub branch readback;
- `requested_sha == checked_out_sha == current main`;
- fresh Python and Worker tests;
- production trust-profile materialization;
- atomic Worker secret-bundle materialization;
- fail-closed production preflight before deploy.

Fresh focused deployment/workflow verification ran:

`python -m unittest tests.test_worker_deployment_policy tests.test_worker_deployment_preflight tests.test_worker_deployment_actions tests.test_workflow_policy -v`

Result: `50/50 PASS`.

Fresh production preflight also passed using only the production trust public profile and required Secret **names**, returning safe metadata for:

- environment `production`;
- Worker `wechat-cli-license-update`;
- D1 `wechat-cli-license-production`;
- R2 buckets `wechat-cli-diagnostics-production` and `wechat-cli-releases-production`;
- the nine required runtime Secret names.

Live health/ingress evidence remained normal after this read-only drill.

Task 40 therefore accepts the standard LKG recovery primitive as:

`redeploy exact current canonical main through deploy-production-worker.yml`

when a real newer/bad Worker version exists. Cloudflare provider-side version rollback remains non-standard and was not exercised.

## Task 41 — bad-release propagation and forward-fix

The named controlled candidate remains:

- release `rel_prod_0_6_1_canary_1`;
- `enabled=0`;
- `paused=1`;
- rollout `100`;
- package SHA-256 `a356552d1bc3461028806663f93d4af44860e18bd6731da8ae6d328b01dd6d90`;
- package size `15193192`.

Fresh source inspection of `selectRelease()` proves release selection reads only `enabled=1` rows and then independently skips paused, zero-rollout, failed-version, or exact failed-release identities. Download authorization also rechecks `enabled=1` and `paused=0`; an already-issued ticket fails closed with `UPDATE_PAUSED` if release state is later stopped.

Fresh GitHub provenance readback for Release ID `371463634` proved:

- tag `v0.6.1-canary.1`;
- `draft=false`;
- `prerelease=true`;
- `immutable=true`;
- package asset ID `517349597`, size `15193192`, digest equal to the accepted package SHA;
- manifest asset ID `517349618`, size `938`, accepted digest retained;
- signature asset ID `517349630`, size `64`, accepted digest retained.

Fresh direct production R2 readback downloaded the immutable candidate package to a system temporary file, computed:

- size `15193192`;
- SHA-256 `a356552d1bc3461028806663f93d4af44860e18bd6731da8ae6d328b01dd6d90`;

and then deleted only the local temporary copy. The remote R2 object was not mutated.

The long-lived canary remained healthy after the candidate had been disabled/paused:

- `status=ok`;
- version `0.6.1-canary.1`;
- Build ID `prod-060-8afbc7a074a0`;
- `license_session_valid=true`.

This proves pause/disable stops **new propagation** but does not force-downgrade an already committed healthy client. Post-commit remediation is a new immutable forward-fix `0.6.x` release, not rewriting or deleting the accepted candidate.

No second candidate, fault release, rollback mutation, or forced client downgrade was created in G8.

## Task 42 — credential emergency-revoke runbook

Task 42 is runbook verification only. No production V1 Secret, signing key, Access identity, GitHub App credential, or Cloudflare API token was revoked, rotated, retired, or deleted.

The accepted production rotation sequence remains:

`add new independent version -> overlap readers/trust -> switch writer/signer -> prove new output -> rollback before retirement -> re-switch -> wait real validity/offline window -> separately authorize retirement`.

### Runtime Worker credential classes

Current live Worker metadata reports all versioned selector families at V1/current-readable V1 and `CONTACT_ENCRYPTION_KEY_VERSION=1`, plus `LEASE_SIGNING_KEY_ID=lease-key-production-01`.

Production-specific revoke consequences:

| Credential class | Emergency consequence / required safe path |
|---|---|
| `LICENSE_KEY_PEPPER_V1` | Removing V1 readability breaks lookup/verification of license keys produced under V1. Add overlap first; do not retire until all required V1 license-key verification paths are migrated or intentional invalidation is approved. |
| `DEVICE_TOKEN_PEPPER_V1` | Removing V1 immediately invalidates existing device-token verification for V1 tokens, interrupting online validation/update/diagnostics authorization. Overlap/new issuance must precede retirement unless forced logout is explicitly desired. |
| `ADMIN_SESSION_PEPPER_V1` | Removing a readable HMAC version immediately invalidates outstanding human admin sessions. Emergency revoke is a valid forced-session-logout tool, but normal rotation requires overlap and fresh session proof before retirement. |
| `CONTACT_LOOKUP_PEPPER_V1` | Changing/removing without an accepted lookup migration makes existing contact lookup digests unreachable. Maintain readable overlap/migration semantics before retirement. |
| `CONTACT_ENCRYPTION_KEY_V1` | Must not be removed while encrypted rows still depend on it unless data inaccessibility is explicitly accepted. Re-encrypt/migrate rows first and prove rollback before destructive retirement. |
| `DOWNLOAD_TICKET_SECRET_V1` | Removing V1 immediately invalidates outstanding V1 download tickets. Normal retirement waits through the accepted ticket lifetime or proves all V1 tickets expired; emergency revoke may intentionally invalidate them. |
| `DIAGNOSTIC_UPLOAD_SECRET_V1` | Removing V1 invalidates outstanding V1 diagnostic upload authorization. Normal rotation overlaps and waits through upload-session validity; emergency revoke may intentionally terminate pending uploads. |
| `RATE_LIMIT_PEPPER_V1` | Rotation changes rate-limit identity digests/buckets and may reset continuity for existing counters. Switch with versioned overlap according to policy; do not silently delete V1 merely for the drill. |
| `LEASE_SIGNING_PRIVATE_KEY` / `lease-key-production-01` | Server signer replacement alone does not revoke already embedded client trust. Introduce a new lease key with client/public-key overlap, prove new leases and rollback, then wait through offline lease validity before separate trust retirement. |

### GitHub / Access / release-publishing credential classes

Fresh GitHub production Environment metadata showed these exact secret names, without reading values:

- `CLOUDFLARE_API_TOKEN`;
- `PRODUCTION_ACCESS_CLIENT_ID`;
- `PRODUCTION_ACCESS_CLIENT_SECRET`;
- `PRODUCTION_RELEASE_SIGNING_PRIVATE_KEY`;
- `PRODUCTION_WORKER_SECRETS_JSON`;
- `RELEASE_PUBLISHER_APP_PRIVATE_KEY`.

Consequences and recovery:

| Credential class | Emergency consequence / required safe path |
|---|---|
| Cloudflare API token | Revocation prevents new Worker deployment/config mutation through the production workflow but does not itself stop the already deployed Worker runtime. Replace under the production Environment boundary before the next deploy. |
| Access Service Token client ID/secret | Revocation immediately stops machine automation from reaching `/v1/automation/*`; existing runtime/device traffic and human `wcas` administration remain separate. Replace the Access identity and then reconcile the exact automation identity allowlist/principal before resuming publication. |
| Release signing private key / `release-key-production-01` | Compromise requires stopping new signing, creating a new independent release key, distributing trust overlap to clients, proving new signed artifacts and rollback, and only then separately retiring old trust. Existing immutable old releases cannot be rewritten as a revocation mechanism. |
| GitHub App private key / App ID `4608862` | Revocation stops private provenance publication through the App. Existing immutable GitHub provenance and R2 runtime objects remain. Replace the App credential within the exact selected release repository boundary before new publication. |
| Atomic Worker Secret bundle | Treat compromise by individual contained secret class, not by blind whole-bundle deletion. Prepare a complete replacement bundle, validate every selector/dependency, then deploy atomically so partial Secret state is never introduced. |

Fresh Environment variables still identify production API/Admin origins, provenance repository `AuRevior-ai/wechat-cli-releases`, publisher App ID `4608862`, and trust public key IDs `lease-key-production-01` / `release-key-production-01`.

A fresh direct GitHub App installation query was not possible with the ordinary `gh` user token because the installation endpoints require App-authorized credentials. G8 deliberately did not broaden credentials to satisfy this read-only drill. The accepted G4 installation evidence remains authoritative, and the same App ID/private-key Environment boundary subsequently produced the successful immutable G7 candidate publication.

## Explicit actions not performed in Tasks 39–42

G8 Tasks 39–42 did **not**:

- create, activate, revoke, suspend, or mutate any production license;
- create or bind any additional production device;
- enable/resume/pause/disable any release merely for ceremony;
- change any rollout percentage;
- create a new Worker version or redeploy the same-functionality Worker;
- use Cloudflare provider-side version rollback;
- publish a new release or alter immutable GitHub provenance;
- modify/delete the candidate R2 object;
- rotate, revoke, retire, or delete any production V1 Secret/key;
- expose any private key, token, session, license key, or Secret value;
- activate a real third-party device;
- perform any Public / Formal Authenticode operation.

## Task 43 — first controlled Private production license

The user separately authorized the exact first real Private production issuance gate. A fresh human Access session authenticated `production-primary-admin`, after a duplicate preflight proved zero existing stable production licenses and an absent target CSV/config path.

Exactly one license was then created through the human Admin batch endpoint with:

- purpose: `first-controlled-private-production-license`;
- release channel: `stable`;
- maximum devices: `1`;
- count: `1`.

Safe readback identity:

- license ID `lic_moOphTS-64IW4bvaqNurnuI0`;
- key hint `JFEV`;
- status `active`;
- revision `1`;
- active stable device count `0`;
- created by `production-primary-admin` at `2026-08-17T03:05:00.931Z`.

The successful `license.batch_create` audit recorded only `count=1`, `maximum_devices=1`, and `release_channel=stable`. The complete key was never printed or copied into governance evidence. It exists only in:

`D:\\use_as_desktop\\Wechat__CLI\\production-secrets-20260815\\board7-g8-first-private-license\\production-stable-private-license-01.csv`

The new evidence directory, CSV, and fresh DPAPI admin config were explicitly ACL-hardened after creation so only `AUREVIOR\\28276`, `BUILTIN\\Administrators`, and `NT AUTHORITY\\SYSTEM` retain access. No third-party delivery, activation, or device binding occurred.

## Accepted G8 terminal state

B7-G8 Tasks 39–43 are accepted complete.

Current controlled state is:

- canonical main `c24783ff9150fba465747d4592bc845f1ab2e485`;
- exact main CI `31987868264` PASS;
- production Worker LKG `ceedf5c8-111c-41e8-83f2-72733225352c` at 100%;
- stable `0.6.0`: enabled/unpaused/rollout 0;
- exactly one active stable Private license exists, maximum devices 1, with zero bound/active stable devices;
- beta `0.6.1-canary.1`: disabled/paused/rollout 100;
- exactly one active beta canary license/device preserved;
- long-lived canary healthy on `0.6.1-canary.1`;
- immutable GitHub/R2 candidate provenance preserved;
- production V1 credential material retained; no retirement performed;
- no license key was sent to a third party and no real third-party device was activated.

**MANDATORY STOP — request B7-G9 Final Production Closure authorization before entering Tasks 44–50.**
