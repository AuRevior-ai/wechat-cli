# Board 6 B6-G7 Staging Key Rotation Drill Preflight

> **B6-G7 ACCEPTED COMPLETE — G7-M0 through G7-M5 executed, cleanup complete, final staging reconciliation passed; B6-G8 is not entered.**
>
> Date: 2026-08-14
>
> Branch: `board6/security-delivery-preparation`
>
> Preflight HEAD: `e52efd4164efd61cce7725e49fc99d443eb121e5`
>
> This document does not authorize any Secret write/delete, selector switch, Worker deployment, D1 write, Access/session issuance, key generation, signing operation, or production action by itself.

## 1. Gate boundary

The user approved entry into **B6-G7 Staging Key Rotation Drill Gate** for staging only. The approved Board 6 design adds an additional fail-closed rule: every staging Secret/key add, switch, rollback, re-switch, and retire must be listed by exact key class/version before mutation.

The initial checkpoint performed only read-only discovery and local verification. The user subsequently approved the exact G7-M0 through G7-M5 staging mutation matrix. Execution remains bounded to that matrix: no V1 retirement, no production, no push/merge, and no B6-G8 entry are authorized.

Hard exclusions remain:

- no production resource/Secret/Worker/D1/R2 mutation;
- no push/merge/tag rewrite;
- no Board 5 or JD25 mutation;
- no commercial Authenticode/provider action;
- no deletion of existing V1 material merely to satisfy a checklist;
- no raw Secret/private-key/license/device/session value in tracked evidence.

## 2. Fresh live staging baseline

Current Worker version remains:

`6f2aad56-12cb-4d8e-8af5-9dceefbe1a49`

The live Worker bindings report all version selectors at version 1:

- `ADMIN_SESSION_PEPPER_CURRENT_VERSION=1`
- `ADMIN_SESSION_PEPPER_READABLE_VERSIONS=1`
- `DOWNLOAD_TICKET_SECRET_CURRENT_VERSION=1`
- `DOWNLOAD_TICKET_SECRET_READABLE_VERSIONS=1`
- `CONTACT_ENCRYPTION_KEY_VERSION=1`
- all other versioned HMAC/token selectors also remain `1` / readable `1`
- `LEASE_SIGNING_KEY_ID=lease-key-staging-01`

Fresh Secret-name readback contains V1 names only for the Board 6 versioned purposes. In particular, none of these proposed G7 names exists yet:

- `ADMIN_SESSION_PEPPER_V2`
- `DOWNLOAD_TICKET_SECRET_V2`
- `CONTACT_ENCRYPTION_KEY_V2`

The current repo-external staging public trust files contain exactly:

- release key: `release-key-staging-01`
- lease key: `lease-key-staging-01`

No key-02 public trust is currently active.

## 3. Fresh D1 dependency inventory

Read-only remote D1 queries returned `rows_written=0` and `changed_db=false`.

Current version dependency counts:

- licenses: version 1 — 1 active, 4 revoked;
- devices: version 1 — 5 active, 3 unbound;
- admin sessions: version 1 — 2 revoked, 0 active;
- download tickets: none;
- license contacts: none.

The single existing Access-mapped principal is `admin_board6_g5_primary`, currently revoked. Its original exact terminal state is:

- status: `revoked`
- revoked_at: `2026-08-14 11:18:29`
- scopes: `licenses:read`, `licenses:write`, `devices:read`, `devices:write`, `releases:upload`, `releases:read`, `releases:write`, `diagnostics:read`, `diagnostics:delete`

Its existing scopes do **not** include `contacts:rotate`.

This principal is the only current mapping for the already accepted Access identity. A G7 browser-backed admin session therefore cannot be created through a fresh duplicate principal without changing the unique identity mapping. If used, the existing principal must be temporarily restored under the exact matrix below, then returned to the exact pre-G7 terminal state.

## 4. Fresh local rotation readiness verification

Fresh focused Python verification:

```text
python -m unittest tests.test_license_lease tests.test_update_crypto tests.test_admin_client tests.test_admin_cli -v
=> 35 / 35 PASS
```

This includes explicit tests that old/new lease signing keys and old/new release signing keys are both accepted during public-key overlap and that old trust is rejected only after explicit retirement.

Fresh Worker verification:

```text
npm run typecheck
=> PASS

npm test -- --run
=> 14 files / 92 tests PASS
```

The first attempted focused Python command was accidentally launched from the Worker subdirectory and failed only because `tests.*` was not importable from that working directory. It performed no mutation. The same focused suite was immediately rerun from repository root and passed 35/35.

## 5. Rotation strategy

B6-G7 will use dedicated disposable G7 evidence and will not use JD25, Board 5 credentials, or the retained G5 release as mutation targets.

One representative is selected per required mechanism:

1. HMAC pepper overlap: `ADMIN_SESSION_PEPPER_V1 -> V2`.
2. Symmetric token secret overlap: `DOWNLOAD_TICKET_SECRET_V1 -> V2`.
3. Contact encryption migration: `CONTACT_ENCRYPTION_KEY_V1 -> V2`.
4. Lease signing trust overlap: `lease-key-staging-01 <-> lease-key-staging-02`.
5. Release signing trust overlap: `release-key-staging-01 <-> release-key-staging-02`.

`LICENSE_KEY_PEPPER`, `DEVICE_TOKEN_PEPPER`, `RATE_LIMIT_PEPPER`, `CONTACT_LOOKUP_PEPPER`, and `DIAGNOSTIC_UPLOAD_SECRET` are not selected as the representative live rotation in this gate and remain unchanged.

## 6. Exact staging mutation approval matrix

### G7-M0 — temporary admin/test boundary

Purpose: create only the disposable test objects required for the drill.

Exact D1 principal transition:

- principal: `admin_board6_g5_primary`
- temporarily change status `revoked -> active`
- temporarily set `revoked_at -> NULL`
- temporarily add only `contacts:rotate` to the existing scope set
- after G7 cleanup, restore the exact original scope set, status `revoked`, and original `revoked_at=2026-08-14 11:18:29`

Allowed disposable objects after a fresh Access login:

- short-lived G7 admin sessions only;
- one or two explicitly G7-marked test licenses as needed;
- at most one G7 test device per test license;
- fixed synthetic contact data only, never user PII;
- G7 download tickets only.

Cleanup order must be `unbind disposable device -> revoke disposable license`, then revoke G7 admin sessions, then restore the principal's exact pre-G7 state.

No G5 session is revived.

### G7-M1 — admin session HMAC overlap

Secret add:

- add `ADMIN_SESSION_PEPPER_V2` with fresh independent high-entropy staging-only material.

Selector states to exercise, always keeping both versions readable once V2 exists:

1. overlap baseline: current `1`, readable `1,2`;
2. switch: current `2`, readable `1,2`;
3. rollback: current `1`, readable `1,2`;
4. re-switch/final: current `2`, readable `1,2`.

Acceptance:

- create a short-lived G7 session while current=1;
- after switching to current=2, the V1 session remains valid;
- create a second session and prove its D1 `token_secret_version=2`;
- rollback to current=1 and prove both readable versions remain accepted until their normal session expiry/revoke;
- re-switch to V2;
- revoke all G7 sessions at cleanup.

Retirement:

- **do not delete `ADMIN_SESSION_PEPPER_V1` in B6-G7**.

Execution evidence (2026-08-15): **PASS**.

- G7-M0 temporarily restored `admin_board6_g5_primary` to `active`, cleared `revoked_at`, and added only `contacts:rotate`; exact pre-G7 restoration remains deferred to G7 cleanup.
- Disposable stable G7 license `lic_2nMbqQVARoMtRRw2ycszoHBy` (`CZ7T`, maximum devices 1) was created; no JD25, Board 5, or retained G5 license was mutated.
- `ADMIN_SESSION_PEPPER_V2` was provisioned staging-only without exposing the Secret value.
- A V1 G7 session remained accepted after the writer switched to `ADMIN_SESSION_PEPPER_CURRENT_VERSION=2` with readable versions `1,2`.
- A new G7 session was then issued with D1 `token_secret_version=2`; V1 and V2 sessions both successfully executed administrator reads while the writer was on V2.
- Rollback deployment `8e46b22f-7716-4fad-bd8b-2eb8e27beb8d` set the writer back to current `1` while keeping readable `1,2`; the already-issued V2 session remained accepted.
- Re-switch deployment `b48b137a-81be-42d7-a39a-e2e827f5393c` restored the final staging state to current `2`, readable `1,2`; both V1 and V2 G7 sessions remained accepted.
- `ADMIN_SESSION_PEPPER_V1` was not deleted or removed from readable versions. Production was not deployed or mutated.

### G7-M2 — download-ticket symmetric secret overlap

Secret add:

- add `DOWNLOAD_TICKET_SECRET_V2` with fresh independent staging-only material.

Selector states:

1. overlap baseline: current `1`, readable `1,2`;
2. switch: current `2`, readable `1,2`;
3. rollback: current `1`, readable `1,2`;
4. re-switch/final: current `2`, readable `1,2`.

Acceptance:

- activate a disposable stable G7 device with a version eligible for an existing accepted staging update;
- issue a V1 download ticket before the switch;
- after current=2, prove the pre-switch V1 ticket still authorizes a bounded package read;
- issue a new ticket and prove its D1 `secret_version=2` and successful bounded download;
- rollback to current=1 while both versions remain readable, then re-switch to V2.

Retirement:

- **do not delete `DOWNLOAD_TICKET_SECRET_V1` in B6-G7**; V1 ticket validity is time-bounded and retirement can be considered only after the accepted ticket lifetime has elapsed or all V1 tickets are proven expired.

Execution evidence (2026-08-15): **PASS**.

- `DOWNLOAD_TICKET_SECRET_V2` was provisioned staging-only without exposing its value.
- Overlap deployment `11f93bca-119e-4018-9eeb-c80199c9447c` established current `1`, readable `1,2`.
- The disposable G7 device for license `lic_2nMbqQVARoMtRRw2ycszoHBy` received a V1 ticket for `rel_staging_051`; after switch deployment `1f8b37a9-ffd8-470e-9f3e-8f488d30e824` set current `2`, readable `1,2`, that same V1 ticket still authorized a one-byte HTTP 206 range read with `Content-Range: bytes 0-0/14268929`.
- A new ticket issued on V2 was independently recorded in D1 with `secret_version=2` and also passed the same one-byte bounded read; the preceding ticket row remained `secret_version=1` for the same G7 device and release.
- Rollback deployment `7410a853-f44f-472b-816d-a2ae7e630f8a` restored current `1`, readable `1,2`; the already-issued V2 ticket still authorized the bounded read.
- Re-switch deployment `cefce80d-8693-4035-a75e-c76138725c98` restored the final M2 state to current `2`, readable `1,2`.
- `DOWNLOAD_TICKET_SECRET_V1` was not deleted or removed from readable versions; production was not deployed or mutated.

### G7-M3 — contact encryption V1/V2 migration and rollback

Secret add:

- add `CONTACT_ENCRYPTION_KEY_V2` with fresh independent staging-only material.

Selector transitions:

1. baseline `CONTACT_ENCRYPTION_KEY_VERSION=1`;
2. switch to `2`;
3. rollback to `1`;
4. re-switch/final to `2`.

Acceptance:

- create one disposable G7 license contact under V1 using fixed synthetic data;
- after switching to V2, run the bounded/idempotent `contacts rotate` API until the row reports `encryption_key_version=2`;
- rollback to V1 and rotate the same synthetic row back to version 1;
- re-switch to V2 and rotate it to version 2 again;
- contact lookup pepper remains version 1 throughout this drill to isolate encryption-key behavior.

Retirement:

- **do not delete `CONTACT_ENCRYPTION_KEY_V1` in B6-G7**. The drill proves reversible migration first; physical removal is a distinct destructive credential action.

Execution evidence (2026-08-15): **PASS, including a staging-only compatibility repair discovered by the drill**.

- `CONTACT_ENCRYPTION_KEY_V2` was provisioned staging-only and a dedicated synthetic, non-PII contact license `lic_uOvB_-XclaPAr_exrvt3dW7M` was created under V1 with no device activation.
- The initial V2 deployment `561ccb5c-d124-4f41-91fc-2c121a78a8ee` exposed a real staging defect: D1 correctly stored `ciphertext` and `iv` as BLOBs, but D1 returned BLOB query values to the Worker as ordinary JavaScript byte arrays while `databaseBytes()` accepted only `ArrayBuffer`/typed-array views. The rotate route failed closed with `CONTACT_ENCRYPTION_STATE_INVALID`; no contact row was partially rewritten.
- TDD reproduced the exact failure with a D1-style `number[]` BLOB value. The minimal repair accepts only integer arrays whose elements are all in `0..255`, preserving fail-closed behavior for malformed values. Focused Worker tests passed 8/8, TypeScript typecheck passed, and the full Worker suite passed 14 files / 93 tests.
- Repair deployment `c49a144a-0e15-4b99-b548-b6e451deed4b` then rotated the single synthetic row from encryption V1 to V2 successfully; independent D1 readback showed `encryption_key_version=2`, `lookup_secret_version=1`, and unchanged BLOB lengths 166/12.
- Rollback deployment `26307a75-36e6-47b2-8130-b92b78a05113` restored `CONTACT_ENCRYPTION_KEY_VERSION=1`; after fresh recent-auth the same row rotated back to `1/1`, independently confirmed in D1 with unchanged BLOB lengths.
- Final re-switch deployment `f736276a-e560-41ad-956b-c95531700792` restored `CONTACT_ENCRYPTION_KEY_VERSION=2`; the same row rotated again to `2/1`, independently confirmed in D1. Contact lookup pepper stayed V1 for the entire drill.
- `CONTACT_ENCRYPTION_KEY_V1` was not deleted. Production was not deployed or mutated.

### G7-M4 — lease signing trust overlap and rollback

New staging-only key identity:

- `lease-key-staging-02`

Repo-external artifacts only:

- generate a fresh Ed25519 lease private key outside the repository;
- create a G7-only non-secret overlap public-key registry/profile containing both `lease-key-staging-01` and `lease-key-staging-02`;
- do not overwrite the accepted G4/G5 staging profile as part of preflight.

Live Worker switch sequence:

1. capture a disposable-device lease signed by `lease-key-staging-01`;
2. update `LEASE_SIGNING_PRIVATE_KEY` to the key-02 private material and `LEASE_SIGNING_KEY_ID=lease-key-staging-02`;
3. deploy staging through the fail-closed deployment wrapper;
4. validate the disposable device and prove the new lease reports key ID 02 and verifies under the overlap registry;
5. independently prove the captured key-01 lease still verifies under the same overlap registry;
6. rollback `LEASE_SIGNING_PRIVATE_KEY` and `LEASE_SIGNING_KEY_ID` to exact key-01 state and redeploy;
7. prove a fresh lease again reports key ID 01.

Final live state for B6-G7:

- **key-01 remains the active live lease signer**.
- key-02 remains staged repo-external evidence only.

Reason: existing accepted staging client trust currently contains only `lease-key-staging-01`. Leaving the Worker on key-02 before a client trust-overlap rollout would intentionally break those clients.

Retirement:

- key-01 public trust/private recovery material is **not retired**. Maximum offline lease duration is seven days, and the gate must not fake elapsed time.

Execution evidence (2026-08-15): **PASS**.

- Repo-external `.dev.vars` recovery material for `LEASE_SIGNING_PRIVATE_KEY` was independently parsed in memory and its derived Ed25519 public key matched the accepted `lease-key-staging-01` registry entry exactly before any live switch.
- Fresh repo-external `lease-key-staging-02` private material and G7-only overlap registry/profile were generated without overwriting accepted key-01 trust files; independent validation showed the private key matched the key-02 public entry while key-01 remained unchanged in overlap trust.
- A pre-switch disposable-device lease was captured from live key-01 and verified with `key_id=lease-key-staging-01`, status active, and exact duration 604800 seconds.
- The deployment wrapper was extended by TDD to accept only a repo-external, non-symlink `--secrets-file` path without reading or printing Secret contents; repository-local secrets files fail closed before Wrangler invocation. Deployment-focused verification passed 26/26 tests.
- Atomic key-02 deployment `cd2cef96-713b-47c5-8763-4e1e427d6cb8` applied `LEASE_SIGNING_PRIVATE_KEY` key-02 material and `LEASE_SIGNING_KEY_ID=lease-key-staging-02` in the same Wrangler deploy. A fresh live lease then verified as key-02, while the exact captured key-01 lease simultaneously remained valid under the overlap registry; both leases were active with 604800-second duration.
- Atomic rollback deployment `633945cb-0103-4fb0-9ccf-7a9c797e6de5` restored the original key-01 private material and `LEASE_SIGNING_KEY_ID=lease-key-staging-01` in the same deploy. Independent live readback confirmed key-01 active with the final M1/M2/M3 selector states unchanged.
- A post-rollback fresh live lease verified under the accepted key-01-only registry with `key_id=lease-key-staging-01`, status active, duration 604800 seconds, proving exact rollback success.
- No lease key retirement, production mutation, release publication, push, or merge occurred. Key-02 remains repo-external staged evidence only.

### G7-M5 — release signing trust overlap and rollback

New staging-only key identity:

- `release-key-staging-02`

Repo-external artifacts only:

- generate a fresh Ed25519 release private key outside the repository;
- use a G7-only non-secret overlap public-key registry/profile containing `release-key-staging-01` and `release-key-staging-02`.

Acceptance sequence:

1. verify an existing immutable staging manifest signed by `release-key-staging-01` under the overlap registry;
2. locally prepare a G7-only manifest/signature for a frozen test package using `release-key-staging-02`; do not publish/register/enable it;
3. verify the key-02 manifest under the overlap registry;
4. rollback the local staging publisher signer to key-01 and prepare/verify a second local-only probe if needed to prove rollback.

Final state:

- existing staging release publisher remains on `release-key-staging-01`;
- no GitHub Release, R2 release object, Worker release row, or enabled release is created solely for this key-rotation proof;
- key-02 remains repo-external staged evidence.

Retirement:

- `release-key-staging-01` trust is **not retired** because immutable existing staging release manifests use key-01 and accepted clients currently trust only key-01.

Execution evidence (2026-08-15): **PASS**.

- The retained repo-external `release-signing-key.pem` was independently confirmed to be an Ed25519 private key whose derived public key exactly matches accepted `release-key-staging-01` trust.
- Existing immutable `rel_staging_051` manifest verification under key-01 passed before the probe.
- A unique frozen B6-G5 package was selected by exact accepted manifest size/hash match: 14268501 bytes and SHA-256 `afffc22fe2f5ba478ae680aa60de20006095c0cb71a26b3b157f48c00ea3f6b9`.
- Fresh repo-external `release-key-staging-02` and a G7-only overlap registry/profile containing key-01 + key-02 were generated without modifying accepted trust files.
- Local-only key-02 probe `rel_board6_g7_m5_key02_probe` produced a 64-byte Ed25519 signature and verified under overlap trust; a second local-only key-01 rollback probe also produced a 64-byte signature and verified under the same overlap trust.
- The retained key-01 publisher file and accepted key-01-only registry were byte/logically unchanged after the probes. No GitHub, R2, Worker release row, enablement, production, push, or merge mutation occurred.

## 7. Safe deployment discipline

Any selector/key-ID change must use the existing staging-only fail-closed deployment path. Each deployment must be preceded by:

- exact `wrangler.jsonc` diff review;
- deployment preflight against environment `staging`;
- confirmation that production placeholder/resources remain untouched;
- current secret-name readback showing every readable version referenced by selectors exists.

No raw Secret value may be printed. Secret values are generated/transferred only through local protected input or repo-external restricted files.

## 8. Emergency-revoke interpretation

The drill will document but will **not execute** destructive emergency retirement against shared V1 state.

- HMAC/ticket version emergency revoke: remove V1 from readable versions only after accepting that all V1 credentials/tickets immediately fail.
- Contact encryption emergency revoke: V1 cannot be removed while any row still has `encryption_key_version=1` unless data loss/inaccessibility is explicitly accepted.
- Lease key emergency revoke: removing key-01 trust requires clients to receive a trust profile that no longer accepts key-01; server-side key replacement alone cannot revoke trust already embedded in installed clients.
- Release key emergency revoke: same client-trust constraint applies; existing signed manifests remain cryptographically valid to clients that still trust the old public key.

This distinction is important: server-side signing-key compromise response and already-installed client trust revocation are related but not identical operations.

## 9. Gate closure

B6-G7 is **accepted complete**. The exact approved G7-M0 through G7-M5 staging mutation matrix was executed and then reconciled back to the intended terminal state.

Final live Worker Version ID is `633945cb-0103-4fb0-9ccf-7a9c797e6de5`. Independent Worker-version readback confirms:

- `ADMIN_SESSION_PEPPER_CURRENT_VERSION=2`, readable `1,2`;
- `DOWNLOAD_TICKET_SECRET_CURRENT_VERSION=2`, readable `1,2`;
- `CONTACT_ENCRYPTION_KEY_VERSION=2`;
- `CONTACT_LOOKUP_PEPPER_CURRENT_VERSION=1`, readable `1`;
- `LEASE_SIGNING_KEY_ID=lease-key-staging-01`;
- V1 and V2 Secret names required by the selected drills remain provisioned; no V1 retirement occurred.

Final D1 cleanup/reconciliation confirms:

- disposable G7 device `dev_b6g7_fb0f0be6e4a23583c0cd062c5cf6010c` is `unbound`;
- both disposable G7 licenses are `revoked` at revision 2;
- all nine sessions for `admin_board6_g5_primary` are `revoked` (the two historical G5 sessions plus all seven G7-created sessions); there are zero active sessions for that principal;
- `admin_board6_g5_primary` is restored exactly to the pre-G7 terminal state: `status=revoked`, original nine scopes without `contacts:rotate`, and `revoked_at=2026-08-14 11:18:29`;
- the synthetic contact row remains encrypted at version 2 with lookup secret version 1, while its disposable parent license is revoked.

Fresh closure verification passed Python 648 tests with 2 expected skips and zero failures; Worker TypeScript typecheck passed; Worker Vitest passed 14 files / 93 tests; deployment-preflight tests passed 26/26. The drill also produced two narrowly scoped TDD repairs: D1 BLOB `number[]` normalization for contact rotation, and staging-only atomic repo-external `--secrets-file` support in the fail-closed deployment wrapper.

No production mutation, commercial signing action, release publication/registration/enablement, V1 credential/public-trust retirement, push, merge, or B6-G8 action occurred. The next possible Board 6 step is B6-G8 and requires separate authorization.
