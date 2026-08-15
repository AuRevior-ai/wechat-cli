# Board 7 Production Identity & Key Bootstrap

Date: 2026-08-15
Gate: B7-G4 Production Identity & Key Bootstrap
Status: IN PROGRESS

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

## Remaining B7-G4 work

Before B7-G4 can be accepted complete:

1. generate the real repo-external production material through the tested helper;
2. verify safe metadata/public-key/trust-profile/ACL evidence without exposing private values;
3. insert the exact human production principal into clean-room production D1;
4. create the exact Cloudflare Access Service Token `wechat-cli-release-automation-production`;
5. record its safe client identity and bind only that identity to the automation Access Service Auth policy;
6. finalize `ACCESS_AUTOMATION_IDENTITIES` and the exact automation principal row;
7. create/install the dedicated GitHub App `wechat-cli-release-publisher` only on the release provenance repository, or hard-stop if the required secure identity boundary is unavailable;
8. configure the `production` GitHub Environment credential boundary if available without security downgrade, otherwise use only an already-designed secure repo-external fallback;
9. run the first identity-complete production preflight with the real repo-external trust profile and exact safe Secret-name inventory;
10. perform read-only credential/bootstrap reconcile.

No Worker application deployment, release publication, license creation, rollout, or Public / Formal Authenticode action occurs in B7-G4.
