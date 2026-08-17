# Board 7 Production Canary E2E Acceptance

Date: 2026-08-17
Gate: B7-G7 Production Canary E2E
Status: ACCEPTED COMPLETE — MANDATORY STOP BEFORE B7-G8

## Canonical implementation lineage

B7-G7 entered from the accepted B7-G6 production automation state and exercised the real production control plane, Windows Launcher, production D1/R2, and private GitHub provenance path. Production defects discovered by the real canary were repaired only through reviewed source changes, hosted CI, and history-preserving merges.

The accepted G7 implementation lineage ends at canonical production source:

`8afbc7a074a0cc1cbefa7d9f53da82caa38a9e42`

Exact canonical-main CI run `31979247562` passed.

Relevant G7 integration checkpoints were:

- production Access/login-path source repair integrated through PR #19, producing canonical main `1e197cf5d2caef923488dadbc53d0f4f8f26a1ba`;
- schema-v2 production installer channel metadata repair `a7d84fa3f88178bfcfa5ad3700a26d87c8fb15d6`, merged through PR #20 as `428c55e756e74eb562e1387c5e708cea9bdad2f9`;
- embedded Launcher trust-profile runtime-name repair `687fe4d8f378e93adec53e1fe0d037a4b6b4ad74`, merged through PR #21 as `ca57dd13d18d4129481ba8761f769c0bf4869ced`;
- internal canary source version `25fd3c238761b0b59d9d7ba6842efdaae14db2fc`, merged through PR #22 as `8afbc7a074a0cc1cbefa7d9f53da82caa38a9e42`.

The retained historical checkout at `D:\use_as_desktop\Wechat__CLI\wechat-cli` remained untouched at frozen SHA `a579a25cb7f16e6fdf88d618252b4a5cbffef53d` with its pre-existing `?? NUL`.

## Task 32 — exact production 0.6.0 baseline installer

The final accepted 0.6.0 baseline installer was rebuilt from exact canonical source `ca57dd13d18d4129481ba8761f769c0bf4869ced` after the installer and embedded-trust repairs. Earlier artifacts from superseded source SHAs were rejected as final evidence rather than reused.

Repo-external evidence root:

`D:\use_as_desktop\Wechat__CLI\production-evidence-20260816\board7-g7-canary-ca57dd13d18d`

Accepted artifact evidence:

- bootstrap ZIP SHA-256 `b8e8d944143bc445b7b1eed889c290a4a00162cb64469aafc0a796a80bf3f135`;
- update ZIP size `14290893` and SHA-256 `54613ffc2ffdff214e9e375f6ebf8a8e04e73ec5f9246a4bf051f5a6cb3bac85`;
- installer SHA-256 `aaa9b0dbde0b850725fc989a9816538544a1ce459cf0ac1cf2629268099a4bf5`;
- runtime Build ID `prod-060-ca57dd13d18d`;
- application `0.6.0` and Launcher `0.2.0`;
- independent artifact verifier passed manifest signature verification, safe extraction, and real extracted application version execution.

The final Launcher archive contains only the canonical runtime trust filename:

`wechat_cli\launcher\deployment-trust-profile.json`

Its safe embedded trust fields reconcile to schema 2 / `private_controlled` / production / stable / `https://wechat-cli-api.aurevior-devspace.com`, with production release/lease key IDs and an empty Windows publisher policy.

Authenticode readback remains `NotSigned`, with no signer or timestamper. This is accepted only under the already-approved Private / Controlled Distribution profile. No claim is made that SHA-256 or Ed25519 is equivalent to Authenticode publisher identity.

## Tasks 33 and 33A — exactly one canary license and human stable-release control

Production contains exactly one internal canary license:

- license ID `lic_epPwkKlncMPfpLw5aOfzyEDn`;
- hint `MVQ7`;
- status `active`;
- `maximum_devices=1`;
- `release_channel=beta`.

The complete license key remains only in repo-external restricted storage and is not recorded here.

Exactly one production canary device was activated. A real second-device attempt through the Launcher UI was rejected; post-attempt D1 remained exactly one device. The Worker implementation rejects a new device at the one-device limit with `DEVICE_LIMIT_REACHED`, while the Launcher UI intentionally maps activation exceptions to the generic non-secret `LIC-ACTIVATE-FAILED` presentation.

The already-registered stable `rel_prod_0_6_0` was human-enabled through a fresh Access-backed admin session while the number of stable real-user licenses remained zero. Its hashes/provenance stayed unchanged. At G7 closure the stable release remains enabled/unpaused with rollout 0, but there are still zero active stable licenses, so no real-user exposure was introduced.

## Task 34 — initial production install, activation, offline lease, diagnostics

The final marked canary installation is:

`D:\use_as_desktop\Wechat__CLI\production-canary-20260816\board7-g7-ca57dd13d18d\LocalAppData\WeChatCliWeb`

The canonical 0.6.0 baseline was installed successfully and the existing encrypted DPAPI license state was moved into the rebuilt canonical sandbox byte-for-byte. DPAPI readback proved that it remained the same production canary license/device identity; no second backend device was created.

Initial production acceptance proved:

- real 0.6.0 health on the marked installation;
- exact Build ID `prod-060-ca57dd13d18d`;
- production API and embedded-trust identity;
- exactly one active beta license/device and zero active stable licenses;
- seven-day offline lease duration exactly `604800` seconds;
- valid/expiring/expired boundaries using injected time only;
- no Windows system-clock mutation.

Diagnostics acceptance used the same real canary device state. The submitted bundle was 806 bytes, SHA-256 `0aa78dd2...`, and the local sensitive-value scan returned no findings. Production metadata proved diagnostics-consent v1, approximately 15-minute upload TTL, seven-day retention, and an opaque R2 object identity. Fresh human admin access then proved download byte-for-byte equality, delete, idempotent second delete, retained deleted relationship/audit metadata, and post-delete `DIAGNOSTIC_NOT_FOUND` behavior.

No license key, device token, admin session token, or other secret was written into governance evidence.

## Task 35 — immutable internal beta 0.6.1-canary.1

The internal candidate source uses exact runtime SemVer:

`0.6.1-canary.1`

Python package metadata uses the explicit PEP 440 companion `0.6.1.dev1`; the product/update protocol, manifest, ZIP, GitHub tag, and D1 release remain exact SemVer `0.6.1-canary.1`. Production Build ID remains under the approved Board 7 lineage format `prod-060-<12-char-source-sha>`.

Candidate publication workflow run:

`31979899871`

Exact source SHA:

`8afbc7a074a0cc1cbefa7d9f53da82caa38a9e42`

The workflow published and registered exactly one beta candidate without machine release-state authority.

Production D1 candidate identity:

- release ID `rel_prod_0_6_1_canary_1`;
- version `0.6.1-canary.1`;
- channel `beta`;
- manifest SHA-256 `6960eb52c02ecaabb07bcfbe18687ae325378bb3f42d76939cfef1d9541a7b9b`;
- package SHA-256 `a356552d1bc3461028806663f93d4af44860e18bd6731da8ae6d328b01dd6d90`;
- package size `15193192`;
- distribution backend `r2`;
- R2 object key `releases/beta/rel_prod_0_6_1_canary_1/a356552d1bc3461028806663f93d4af44860e18bd6731da8ae6d328b01dd6d90.zip`;
- GitHub repository `AuRevior-ai/wechat-cli-releases`;
- GitHub Release ID `371463634`;
- package Asset ID `517349597`.

Initial automated registration terminal state was exactly:

`enabled=false / paused=true / rollout=0`

Automation audit for this candidate contains package-ready/register operations only and no automation `release.update`.

The release provenance repository reports native Immutable Releases `enabled=true`. The newly created `v0.6.1-canary.1` release independently reports `immutable=true`, `draft=false`, and `prerelease=true`.

GitHub assets remain:

- package Asset ID `517349597`, size `15193192`, SHA-256 `a356552d1bc3461028806663f93d4af44860e18bd6731da8ae6d328b01dd6d90`;
- manifest Asset ID `517349618`, size `938`, SHA-256 `6960eb52c02ecaabb07bcfbe18687ae325378bb3f42d76939cfef1d9541a7b9b`;
- signature Asset ID `517349630`, size `64`, SHA-256 `f093e13a2c457f4b9791d66e22cba8b75c628d5ddc67d28e7fcb993db063db76`.

This is the first later production release after the approved `v0.6.0` native-immutability exception, and it satisfies the mandatory native immutability requirement.

## Task 36 — human-only candidate visibility

A fresh Access-backed production human session authenticated principal `production-primary-admin`. Human state operations only then changed the named candidate:

1. `enabled=true / paused=false`;
2. `rollout_percentage=100`.

The second operation was required because Worker selection treats rollout 0 as non-selectable. Since production beta population intentionally contains exactly one internal canary license, 100% here means visibility to that sole internal beta canary rather than a real-user percentage rollout.

D1 readback after enable proved:

- candidate enabled/unpaused/100;
- exactly one active beta license;
- zero active stable licenses.

Both successful `release.update` events were attributed to `production-primary-admin`, not the automation identity.

## Task 37 — real update, controlled fault rollback, exact suppression

### Channel alignment

The 0.6.0 baseline arrived through a stable controlled installer while the internal entitlement was beta. Board 6 intentionally requires the client request channel to match the authenticated license channel and rejects mismatch with `UPDATE_CHANNEL_MISMATCH`.

G7 therefore reused the already-accepted Board 5 alignment primitive: `CurrentVersion + InstallLayout.save_current()` changed only the marked canary's local update-request channel from stable to beta. Current version, previous version, manifest hash, and activation timestamp were preserved. No license-channel mutation API was added or used.

### Healthy real update

The installed production Launcher then executed a real `--download-update` path. It selected exactly `rel_prod_0_6_1_canary_1`, downloaded from the Worker/R2 path, verified the signed manifest, exact size/hash, safely extracted the candidate, and wrote pending state.

Downloaded package evidence:

- size `15193192`;
- SHA-256 `a356552d1bc3461028806663f93d4af44860e18bd6731da8ae6d328b01dd6d90`;
- pending manifest SHA-256 `6960eb52c02ecaabb07bcfbe18687ae325378bb3f42d76939cfef1d9541a7b9b`;
- extracted runtime version `0.6.1-canary.1`;
- Build ID `prod-060-8afbc7a074a0`.

After an exact PID/path preflight, only the marked 0.6.0 canary process tree was stopped to free port 8787. Installed Launcher `--apply-update` then committed transaction:

`txn_V6SpOeAxKZBXqj8cjlzRcDIE`

Terminal healthy-update evidence:

- transaction `committed`;
- current `0.6.1-canary.1`;
- previous `0.6.0`;
- channel `beta`;
- pending state absent;
- sole 8787 listener belongs to `versions\0.6.1-canary.1\wechat-cli.exe`;
- health `status=ok`, version `0.6.1-canary.1`, Build ID `prod-060-8afbc7a074a0`.

### Controlled local health-failure acceptance

G7 is authorized for exactly one candidate, so no second remote fault release was created. The immutable GitHub release, R2 object, D1 release row, and downloaded ZIP were kept unchanged.

A separate repo-external fault sandbox was created:

`D:\use_as_desktop\Wechat__CLI\production-canary-20260816\board7-g7-fault-8afbc7a0\LocalAppData\WeChatCliWeb`

It reused the exact same encrypted DPAPI canary state and the exact 0.6.0 baseline, used isolated non-trust port 18788, and began with no candidate/pending/transaction/failed registry. D1 remained exactly one device. The fault sandbox independently validated 0.6.0 and downloaded the same immutable candidate; its ZIP again matched size/hash `15193192 / a356552d...`.

Only after that remote-byte verification, the sandbox's already-extracted candidate executable was locally replaced with the trusted 0.6.0 executable while the candidate app manifest continued to declare `0.6.1-canary.1`. The original downloaded ZIP was left untouched. This deliberately caused the launched candidate path to report health version 0.6.0 when the transaction expected `0.6.1-canary.1`.

Real fault transaction:

`txn_EQgWx9tO_OJMFvAlqrnFQhaI`

Terminal rollback evidence:

- transaction `rolled_back`;
- failure reason `application health check timed out: application health version does not match the update`;
- current restored to 0.6.0/beta;
- candidate process count 0;
- 18788 listener belongs to restored `versions\0.6.0\wechat-cli.exe`;
- restored health `0.6.0 / prod-060-ca57dd13d18d / ok`;
- healthy primary canary on 8787 remained `0.6.1-canary.1 / prod-060-8afbc7a074a0 / ok`.

The failed registry recorded the exact identity:

`0.6.1-canary.1|6960eb52c02ecaabb07bcfbe18687ae325378bb3f42d76939cfef1d9541a7b9b`

### Exact failed-candidate suppression

Before a fresh post-failure check, D1 contained exactly two download tickets for the candidate: one for the healthy primary canary preparation and one for the fault sandbox preparation.

The fault sandbox then ran another production `--download-update` carrying the exact failed-release identity. It returned successfully with no new pending state and did not refresh the existing pending timestamp. D1 candidate ticket count remained exactly 2, proving server-side exact suppression created no new ticket.

For local suppression, the restored 0.6.0 process was stopped and `--apply-update` was invoked again while the old pending file still existed. The Launcher left transaction `txn_EQgWx9tO_OJMFvAlqrnFQhaI` unchanged in `rolled_back`, did not switch the pointer, and restarted only 0.6.0. Candidate process count remained zero. The fault sandbox was then stopped and retained as evidence.

## Task 38 — human pause/disable and preserved provenance

Task 38 preflight reconfirmed candidate enabled/unpaused/100, exactly one beta license/device, zero stable licenses, and unchanged GitHub immutable provenance.

The first atomic human pause/disable attempt correctly failed closed with `ADMIN_RECENT_AUTH_REQUIRED` and made no state change. A new clean-room Access-backed session was then established for the same `production-primary-admin` principal.

One human Admin API PATCH submitted only:

`enabled=false / paused=true`

No rollout field was submitted. D1 terminal state is now:

- `enabled=0`;
- `paused=1`;
- `rollout_percentage=100`;
- manifest/package hashes and GitHub/R2 identities unchanged.

The successful terminal audit is a single `release.update` by `production-primary-admin` with metadata:

`{"enabled":false,"paused":true}`

Fresh GitHub readback still reports repository Immutable Releases enabled and candidate `immutable=true`; all three asset IDs/sizes/digests are unchanged.

A direct remote R2 object read after pause/disable returned exactly:

- size `15193192`;
- SHA-256 `a356552d1bc3461028806663f93d4af44860e18bd6731da8ae6d328b01dd6d90`.

The production canary license/device is intentionally preserved as the designated long-lived internal canary. No revoke or unbind cleanup was performed.

Finally, the healthy primary canary was cleanly restarted after the candidate was disabled/paused. Port 8787 is owned by the exact `versions\0.6.1-canary.1\wechat-cli.exe` path, health is `0.6.1-canary.1 / prod-060-8afbc7a074a0 / ok`, and D1 shows the sole active device's latest validation at app `0.6.1-canary.1`, Launcher `0.2.0`.

## Authority and exposure invariants

G7 acceptance preserves the Board 7 authorization model:

- production automation remains limited to `releases:upload`, `releases:read`, and `releases:register`;
- automation performed no `release.update` state mutation;
- release enable/rollout/pause/disable were human-session operations only;
- exactly one production beta canary license exists;
- exactly one production canary device exists;
- zero production stable real-user licenses exist;
- no second beta candidate or fault release was published;
- no production GitHub release/tag/asset or R2 provenance byte was deleted or rewritten;
- `v0.6.1-canary.1` is natively immutable;
- the existing `v0.6.0` native-immutability exception remains the one approved G6 exception and was not mutated;
- no commercial Authenticode identity/signature was introduced or claimed;
- no public distribution or third-party activation occurred.

## Accepted terminal state and mandatory stop

B7-G7 is accepted complete.

Accepted terminal production state:

- accepted implementation main before governance closure: `8afbc7a074a0cc1cbefa7d9f53da82caa38a9e42`;
- exact implementation-main CI: `31979247562` PASS;
- production Worker remains the accepted B7-G5 Worker lineage;
- stable `0.6.0`: enabled/unpaused/rollout 0, with zero stable licenses;
- internal beta `0.6.1-canary.1`: disabled/paused/rollout 100;
- candidate GitHub release: private prerelease, native immutable, preserved assets;
- candidate R2 package: preserved, exact size/hash verified after final disable;
- one beta canary license/device: active and preserved;
- marked primary canary runtime: healthy `0.6.1-canary.1`;
- fault sandbox: stopped and retained as evidence;
- no real Private user issuance occurred.

**Mandatory STOP: B7-G8 has not started. No first real stable user license, real Private customer issuance, or G8 recovery/controlled-release mutation may occur without crossing the explicit B7-G8 gate.**
