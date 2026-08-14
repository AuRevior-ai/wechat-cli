# Board 6 B6-G7 Staging Key Rotation Drill Preflight

> **READ-ONLY PREFLIGHT COMPLETE — exact staging mutation matrix pending explicit approval.**
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

Therefore this checkpoint performs only read-only discovery and local verification. No staging mutation has occurred yet.

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

## 9. Preflight conclusion

B6-G7 local/read-only preflight is complete and the code paths are ready for a bounded staging drill. No staging mutation occurred during this preflight.

The next required authorization is the exact mutation subgate above:

> **Approve B6-G7 exact staging mutation matrix G7-M0 through G7-M5, including only the named V2 additions, selector/key-ID switch/rollback/re-switch actions, temporary `admin_board6_g5_primary` restoration with exact final-state restoration, disposable G7 test data, and lease/release key-02 repo-external generation. No V1 Secret/public-trust retirement, no production, no push/merge, and no G8 are authorized.**
