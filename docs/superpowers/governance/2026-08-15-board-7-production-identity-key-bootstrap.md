# Board 7 Production Identity & Key Bootstrap

Date: 2026-08-15
Gate: B7-G4 Production Identity & Key Bootstrap
Status: READY FOR SOURCE INTEGRATION

## Canonical entry boundary

B7-G3 Production Infrastructure Provision is accepted complete through history-preserving PR #4 merge:

`8188384ce40f6239d8cebf8471def267faf74cde`

Post-merge canonical-main CI run `31887583720` completed successfully for that exact SHA. B7-G4 starts from that exact canonical source on isolated branch `board7/production-identity-key-bootstrap`.

Historical boundaries remain distinct:

- historical frozen pre-integration main: `a579a25cb7f16e6fdf88d618252b4a5cbffef53d`;
- retained local main checkout remains physically at that historical frozen SHA with its pre-existing untracked `NUL`;
- current canonical remote main entering B7-G4: `8188384ce40f6239d8cebf8471def267faf74cde`.

## B7-G3 accepted production infrastructure

The canonical B7-G3 evidence is `docs/superpowers/governance/2026-08-15-board-7-production-inventory.md`.

Accepted safe state includes:

- D1 `wechat-cli-license-production`, ID `011b3c26-bbe6-4bb7-8af7-39f1e6d46932`;
- R2 `wechat-cli-releases-production`;
- R2 `wechat-cli-diagnostics-production`;
- migrations `0001` through `0008` complete;
- clean-room business/identity/audit counts all zero before B7-G4 identity creation;
- exact production API/Admin origins and custom-domain declarations;
- exact Zero Trust issuer/JWKS;
- distinct human and automation Access applications/audiences;
- human app bound to the approved single-identity Allow policy;
- automation app with no policy and therefore deny-by-default;
- production application Worker still undeployed.

## Task 19 — exact runtime Secret inventory freeze

The required production Worker Secret names were derived directly from the exact canonical source selectors and `deployment-policy.json` rather than copied from prose.

Exact initial V1 inventory:

```text
ADMIN_SESSION_PEPPER_V1
CONTACT_ENCRYPTION_KEY_V1
CONTACT_LOOKUP_PEPPER_V1
DEVICE_TOKEN_PEPPER_V1
DIAGNOSTIC_UPLOAD_SECRET_V1
DOWNLOAD_TICKET_SECRET_V1
LEASE_SIGNING_PRIVATE_KEY
LICENSE_KEY_PEPPER_V1
RATE_LIMIT_PEPPER_V1
```

All version selectors are V1-only at this gate. The derived inventory explicitly excludes:

```text
GITHUB_RELEASE_READ_TOKEN
ADMIN_TOKEN_PEPPER
```

No runtime Secret value is recorded in this document or repository.

## Secret provisioning sequencing clarification

B7-G4 must not deploy application Worker code. Current Wrangler behavior for individual Secret mutation creates a new Worker version/deployment, which would cross the B7-G4/B7-G5 gate boundary.

The accepted production deployment capability already supports a repo-external atomic secrets-file mechanism. Therefore the safe gate interpretation is:

1. B7-G4 generates fresh production runtime Secret material and stores it only in a restricted repo-external credential directory.
2. B7-G4 verifies the exact required Secret-name inventory and material format without uploading application Worker code.
3. B7-G5 performs the first production Worker deployment from the exact approved canonical main while atomically injecting the repo-external Secret set through the already accepted deployment mechanism.
4. No `wrangler secret put` operation is used to create a placeholder/early production Worker version during B7-G4.

This preserves the higher-priority design invariant that production application Worker deployment starts only in B7-G5 while still producing fresh independent production Secret material in B7-G4.

## Production material helper

A production-specific helper is implemented under TDD:

`scripts/board7_prepare_production_material.py`

Its scope is local preparation only. It performs no Cloudflare, GitHub, D1, Worker, release, license, or rollout mutation.

The helper generates exactly:

- the nine required runtime Secret values above;
- independent `lease-key-production-01` Ed25519 material;
- independent `release-key-production-01` Ed25519 material;
- the corresponding public-key registry;
- a real schema-v2 `private_controlled` production trust profile using the exact production API origin and empty Windows publisher policy;
- fresh production fingerprint salt;
- human principal SQL for `production-primary-admin` with the exact approved non-wildcard scope matrix;
- safe metadata containing names/IDs/public keys only.

The helper intentionally does not generate a legacy admin token, `ADMIN_TOKEN_PEPPER`, or `GITHUB_RELEASE_READ_TOKEN`.

The exact automation principal is not finalized by this first material-generation step because its verified external identity is the B7-G4 Cloudflare Access Service Token client ID, which does not exist until that token is created.

Output requirements:

- repo-external directory only;
- exclusive create / no overwrite;
- sensitive values never printed;
- Windows ACL inheritance removed and access restricted to current user, SYSTEM, and Administrators;
- release private key remains publisher-side, not Worker runtime;
- Worker runtime material is reserved for B7-G5 atomic deployment.

TDD evidence at helper introduction:

`python -m unittest -q tests.test_board7_production_material`

Result: 5 tests passed.

## Principal contract

Human principal ID:

`production-primary-admin`

Exact human scopes:

```text
licenses:read
licenses:write
devices:read
devices:write
releases:upload
releases:read
releases:register
releases:state
diagnostics:read
diagnostics:delete
contacts:rotate
```

Automation principal ID:

`release-automation-production`

Exact automation scopes after Service Token identity finalization:

```text
releases:upload
releases:read
releases:register
```

No wildcard scope is permitted. No standing legacy production admin token is created.

## Executed B7-G4 work

All ten planned B7-G4 bootstrap steps are now complete on the cloud/local side:

1. fresh repo-external production material generated through the tested helper;
2. safe output set and ACL evidence verified without exposing private values;
3. exact human production principal inserted into clean-room production D1;
4. exact Cloudflare Access Service Token created;
5. exact Service Auth policy bound only to that token;
6. production automation identity finalized in source and D1 with the approved three-scope matrix;
7. dedicated GitHub App created and installed only on the release provenance repository;
8. the source repository `production` GitHub Environment populated with the approved credential/variable boundary;
9. first identity-complete production preflight passed with the real repo-external trust profile and exact nine-name Secret inventory;
10. read-only D1 / GitHub bootstrap reconcile passed.

Fresh production D1 state after bootstrap remains `licenses=0`, `devices=0`, `releases=0`, `admin_principals=1`, `admin_sessions=0`, `automation_principals=1`. The human principal has the exact eleven approved scopes. The automation principal has only `releases:upload`, `releases:read`, and `releases:register`; no wildcard and no `releases:state` capability exist.

The dedicated GitHub App is `wechat-cli-release-publisher`, App ID `4608862`. Read-only installation verification proved repository selection is `selected`, with exactly one selected repository: `AuRevior-ai/wechat-cli-releases`. Effective permissions are `contents: write` plus GitHub-required `metadata: read` only.

The `production` GitHub Environment remains restricted to branch `main`. Exact Environment Secret names present are `CLOUDFLARE_API_TOKEN`, `PRODUCTION_ACCESS_CLIENT_ID`, `PRODUCTION_ACCESS_CLIENT_SECRET`, `PRODUCTION_RELEASE_SIGNING_PRIVATE_KEY`, and `RELEASE_PUBLISHER_APP_PRIVATE_KEY`. Exact non-secret variables present are `CLOUDFLARE_ACCOUNT_ID`, `PRODUCTION_ADMIN_ORIGIN`, `PRODUCTION_API_ORIGIN`, `PRODUCTION_TRUST_PROFILE_JSON`, `RELEASE_PROVENANCE_OWNER`, `RELEASE_PROVENANCE_REPOSITORY`, `RELEASE_PROVENANCE_REPOSITORY_NAME`, and `RELEASE_PUBLISHER_APP_ID`. No private value is recorded in source.

Fresh local closure verification after identity/config finalization:

- Python full suite: 699 tests / 2 expected skips / 0 failures;
- Worker typecheck: PASS;
- Worker Vitest: 18 files / 130 tests PASS;
- deployment/workflow focused suite: 48/48 PASS;
- workflow source policy: PASS;
- tracked sensitive-value scan: PASS;
- `git diff --check`: PASS;
- real production preflight with the repo-external trust profile: PASS.

No Worker application deployment, release publication, license creation, rollout, or Public / Formal Authenticode action occurred in B7-G4.

B7-G4 becomes accepted complete only after this exact reviewed G4 head passes hosted branch/PR CI, is history-preserving merged into canonical `main`, and fresh remote-main readback matches the resulting merge commit. B7-G5 must deploy only from that post-G4 canonical main.
