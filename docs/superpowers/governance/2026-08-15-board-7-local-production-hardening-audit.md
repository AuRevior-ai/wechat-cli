# Board 7 — B7-G1 Local Production Hardening Audit

Date: 2026-08-15

Gate: `B7-G1 Local Production Hardening`

Status: **accepted complete locally; mandatory stop before B7-G2**

Distribution profile: **Private / Controlled Distribution**

## 1. Scope and authorization boundary

B7-G1 was executed only in the isolated local Board 7 worktree:

`C:\Users\28276\.devspace\worktrees\wechat-cli-f3860a02-3dba6705`

Branch:

`board7/production-automation-controlled-launch`

The gate authorized local source, tests, workflow source and governance only. It did **not** authorize GitHub push/PR/merge/workflow dispatch, Cloudflare/DNS/Access/D1/R2 mutation, production Secret/key generation or provisioning, production deploy, release publication/registration, production license issuance, release-state mutation, tag creation, or commercial Authenticode activity. None of those actions were performed.

## 2. Lineage

B7-G1 began from exact B7-G0 design baseline:

`496f1c7847b5deb6c3870060113d7e89bab52f4c`

Fresh closure lineage checks:

- implementation HEAD: `b8551d05677ea5f5fccaf842c0214e49c70eb638`
- branch: `board7/production-automation-controlled-launch`
- merge-base with Board 6 closure `740ddabc5808a6a68c2dd812ae81c039b17d23b4`: exact `740ddabc5808a6a68c2dd812ae81c039b17d23b4`
- merge-base with B7-G0 design baseline: exact `496f1c7847b5deb6c3870060113d7e89bab52f4c`
- worktree status before governance edits: clean
- `git diff --check`: PASS

Implementation commits after B7-G0:

1. `130f00c` — `feat: enforce worker host path authority`
2. `0418ec8` — `feat: separate release automation identity`
3. `b167024` — `feat: separate release preparation from release state`
4. `26794ed` — `feat: define production deployment security contract`
5. `8a8842a` — `feat: define guarded production worker deployment`
6. `e6f9c10` — `feat: establish production 0.6 launcher lineage`
7. `cdc842b` — `feat: freeze private production trust profile contract`
8. `ee83f9e` — `feat: freeze private production trust profile contract`
9. `3a7d9d7` — `fix: keep direct build imports worktree local`
10. `42ec7d5` — `feat: define controlled production workflows`
11. `b87a7ca` — `fix: deny automation rollout authority`
12. `863c1d6` — `fix: keep automation rollout human controlled`
13. `b8551d0` — `docs: bind release provenance to exact repositories`

Implementation delta from B7-G0 through `b8551d0`: 56 files changed, 4717 insertions, 808 deletions.

## 3. Local hardening delivered

### 3.1 Production Host/Path authority

The Worker now applies an ingress authority classifier before route handlers. Production separates exact API and Admin authorities and rejects privileged paths on the public API host. The machine automation surface is also privileged and therefore restricted to the Admin authority.

Production source remains intentionally unresolved and fail-closed:

- `workers_dev=false`
- `routes=[]`
- `PUBLIC_API_ORIGIN=REPLACE_WITH_PRODUCTION_API_ORIGIN`
- `ACCESS_ADMIN_ORIGIN=REPLACE_WITH_PRODUCTION_ADMIN_ORIGIN`

### 3.2 Independent human and machine identity

Migration `0008_automation_identity.sql` introduces independent `automation_principals` and extends audit actor typing to `automation` while preserving historical audit rows/indexes.

Human and machine Access verification share the strict cryptographic verifier but use separate production audiences and identity configuration. Production does not fall back to the staging compatibility audience.

### 3.3 Release capability split

The machine route surface contains only:

- `PUT /v1/automation/releases/:releaseId/package`
- `POST /v1/automation/releases`
- `GET /v1/automation/releases`

There is no machine PATCH/state route.

Human release-state mutation requires both:

- scope `releases:state`
- `authMode=session`

Legacy/break-glass or service identities cannot satisfy that state gate.

A later B7-G1 self-audit closed a subtler authority path: automation registration now rejects caller-controlled rollout percentage/seed and fixes the stored candidate rollout to zero with server-generated seed. The Python automation client also strips rollout fields. The production signing CLI does not expose rollout control and emits a zero-rollout manifest. Machine automation therefore cannot functionally choose `enabled`, `paused`, or `rollout_percentage`; human state authorization remains the only path to launch exposure.

### 3.4 Production deployment contract

Production preflight now validates the exact production ingress/Access/trust contract and derives its Secret inventory from version selectors plus policy.

Current production required Secret names are exactly:

- `ADMIN_SESSION_PEPPER_V1`
- `CONTACT_ENCRYPTION_KEY_V1`
- `CONTACT_LOOKUP_PEPPER_V1`
- `DEVICE_TOKEN_PEPPER_V1`
- `DIAGNOSTIC_UPLOAD_SECRET_V1`
- `DOWNLOAD_TICKET_SECRET_V1`
- `LEASE_SIGNING_PRIVATE_KEY`
- `LICENSE_KEY_PEPPER_V1`
- `RATE_LIMIT_PEPPER_V1`

The production inventory explicitly excludes `GITHUB_RELEASE_READ_TOKEN` and legacy `ADMIN_TOKEN_PEPPER`.

The production deploy wrapper accepts only an explicit production target plus a full lowercase 40-character source SHA, runs fail-closed preflight before invoking Wrangler, validates any secrets file as repo-external without reading/printing its contents, and has only fake-runner coverage under B7-G1. No real deploy was invoked.

### 3.5 New production lineage and trust profile

Current product identity on the Board 7 implementation lineage is:

- application `0.6.0`
- Launcher `0.2.0`
- local default build ID `dev`
- production build ID derived deterministically as `prod-060-<first 12 chars of exact canonical source SHA>`

Private production Launcher trust requires schema v2, `distribution_profile=private_controlled`, `stable`, empty Windows publisher policy, exact key identities `release-key-production-01` and `lease-key-production-01`, and exact API-origin agreement.

Commercial Authenticode remains deferred optional Public / Formal Distribution hardening and is not a B7-G1 blocker.

### 3.6 Controlled workflow source

Tracked workflow source now defines:

- ordinary CI with no production credential references;
- a manual production Worker deploy workflow;
- a manual production release preparation workflow.

External Actions are allowlisted and pinned to immutable full commit SHAs. Privileged workflows require `workflow_dispatch`, production Environment protection, concurrency serialization, and an explicit source SHA that must equal both the checked-out commit and the observed canonical `main` commit before privileged operations can continue.

The release workflow preserves the Board 6 publication order:

`build -> verify -> sign -> R2 readiness -> immutable GitHub provenance -> disabled registration -> read-only reconcile`

The release signing private key is scoped to one signing step. After that marker no third-party Action step is allowed. Publication re-verifies the prepared manifest/signature/package under the production public trust profile before using machine preparation authority.

Source provenance and release-repository provenance are independent exact commits: the source commit is recorded in release provenance text, while the GitHub release tag targets an exact commit that actually exists in the private release repository.

No workflow was dispatched in B7-G1.

## 4. Fresh closure verification

All completion evidence below was re-run in the correct isolated Board 7 worktree.

### Python

Command:

`python -m unittest -q`

Result:

- 687 tests run
- 2 expected skips
- 0 failures
- PASS

### Worker

Commands:

- `npm run typecheck`
- `npm test -- --run`

Result:

- TypeScript typecheck PASS
- 18 Vitest files PASS
- 130 tests PASS

### Deployment/workflow focused gate

Focused unittest modules covering deployment policy/preflight/actions, workflow policy, two-phase production release, automation client, and tracked-sensitive scanning:

- 58 tests run
- 0 failures
- PASS

Additional policy tools:

- `python scripts/verify_workflow_policy.py` -> PASS for all three tracked workflows
- `python scripts/verify_no_tracked_secrets.py` -> `tracked sensitive-value scan: PASS`

### Static safety readback

Fresh source inspection proved:

- automation routes are upload/register/read only;
- no machine release-state route exists;
- human state route requests `releases:state` then applies the session-only authority assertion;
- Host/Path authority is invoked in `src/index.ts` before route handlers;
- production `workers_dev=false`;
- production routes remain empty;
- production API/Admin origins remain unresolved sentinels;
- production Secret inventory excludes runtime GitHub read and legacy admin-token secrets;
- current shared versions are application `0.6.0` and Launcher `0.2.0`.

## 5. Production domain freeze decision

The exact production base domain is **not frozen in B7-G1**.

This is deliberate and matches the approved Board 7 design: `<BASE_DOMAIN>` remains a design symbol through B7-G0/B7-G1, and source configuration must remain an explicit fail-closed sentinel. Before any B7-G3 domain/resource provisioning, the exact base domain must be frozen inside that separately approved production mutation matrix.

Therefore B7-G1 ends with unresolved `REPLACE_WITH_PRODUCTION_API_ORIGIN` / `REPLACE_WITH_PRODUCTION_ADMIN_ORIGIN`, empty production routes, and a preflight that refuses unresolved production identity.

## 6. Remaining production-only unknowns

B7-G1 intentionally does not resolve or create:

- exact production base domain, API/Admin hostnames or DNS/custom-domain routes;
- production D1 ID;
- production R2 resources;
- production Access human/automation application audiences and exact identities;
- production Secret values;
- production lease/release private keys or fingerprint salt;
- GitHub production Environment configuration/approvals/secrets/vars;
- GitHub App installation/permissions and release-repository branch provenance target;
- any real production Worker version;
- any production release/license/device/canary state.

Those are later separately gated production/bootstrap operations.

## 7. External-side-effect proof and final gate state

B7-G1 performed no Cloudflare mutation, no GitHub hosted write, no workflow dispatch, no production provisioning, no production Secret/key generation, no release publication/registration/state change, no license/device creation, no push/PR/merge/tag mutation, and no commercial signing action.

Canonical B7-G1 conclusion:

```text
Board 6 accepted complete
Board 7 B7-G0 design/spec + plan complete
Board 7 B7-G1 Local Production Hardening accepted complete locally
production fail-closed / unprovisioned / undeployed
next gate = B7-G2 Source Integration
```

**Mandatory stop:** do not push, create a PR, merge, or provision production without the separately approved B7-G2 sub-gates.
