# Board 7 — Production Automation & Controlled Launch Design

> **FINAL BOARD 7 DESIGN — Private / Controlled Distribution**
>
> Date: 2026-08-15
>
> Design baseline: Board 6 closure `740ddabc5808a6a68c2dd812ae81c039b17d23b4` (`docs: complete board 6 security delivery preparation`).
>
> This document authorizes no implementation or external side effect by itself. Production remains fail-closed, unprovisioned, and undeployed until the separately named Board 7 gates are approved and executed.

## 1. Current state and scope

The Authorized Update Program enters Board 7 with Board 1–3 complete and Board 4–6 accepted complete. Board 6 closed under **Private / Controlled Distribution**. Commercial Authenticode remains deferred optional hardening for a future Public / Formal Distribution profile.

Frozen boundaries at Board 7 design entry:

- Board 6 worktree: `C:\Users\28276\.devspace\worktrees\wechat-cli-f3860a02`
- Board 6 closure branch: `board6/security-delivery-preparation`
- Board 6 closure HEAD: `740ddabc5808a6a68c2dd812ae81c039b17d23b4`
- frozen main: `a579a25cb7f16e6fdf88d618252b4a5cbffef53d`
- Board 5 accepted evidence: `67d3dec0fd1c4a02c87be1ab79c4f78ea63f49d6`
- Board 6 worktree historical residue: `?? NUL`, preserved and untouched
- main historical residue: its own `?? NUL`, preserved and untouched

Board 6 already accepted the update protocol, R2 runtime distribution, immutable GitHub provenance, short-lived human admin sessions, diagnostics retention, versioned secret rotation, Windows transactional update/rollback, embedded Launcher trust, and staging/production deployment isolation. Board 7 does not redesign those mechanisms. It converts the accepted staging system into an auditable clean-room production system with least-privilege automation and a controlled first launch.

## 2. Goals

Board 7 must deliver all of the following before the seven-board program can close:

1. A clean-room production Cloudflare environment with no staging business-data migration.
2. One production Worker service exposed only through two exact custom hostnames: public/native API and privileged Admin/Automation.
3. Runtime Host + Path authorization inside the Worker, independent of DNS, Cloudflare routes, Access, and browser Origin checks.
4. Cryptographically and semantically distinct human and machine Access identities.
5. A release capability model in which automation may upload/read/register but **cannot change release state**.
6. A second, code-level human-only control on release enable/pause/disable/rollout.
7. A production secret/key lifecycle that begins with fresh production V1 material and does not copy staging material or staging selector numbers.
8. GitHub Actions for CI, production Worker deployment, and production release preparation with pinned dependencies, minimal permissions, exact canonical-main enforcement, and concurrency controls.
9. A private cross-repository GitHub provenance publisher identity with least privilege.
10. A production Launcher trust profile for `private_controlled`, App `0.6.0`, Launcher `0.2.0`, and exact source provenance.
11. An internal production canary path that validates initial installation on `0.6.0` and a real update/fault path using `0.6.1-canary.1` before any real Private user issuance.
12. Explicit Worker deployment rollback, release propagation rollback, and client transaction rollback/forward-fix policy.
13. Production diagnostics/log-redaction acceptance and minimal recovery evidence.
14. A final production acceptance report and canonical closure of the original seven-board program.

## 3. Non-goals

Board 7 does not include:

- Public / Formal Distribution activation.
- Commercial Authenticode provider selection, payment, KYC, certificate/managed-key provisioning, or real Authenticode signing.
- A public installer download portal.
- Migration of staging licenses, devices, admin sessions, diagnostics, releases, or synthetic acceptance data into production.
- Reuse of staging private keys, HMAC peppers, ticket secrets, or contact-encryption material.
- A standing production legacy admin token path.
- An automation identity that can enable, pause, disable, or change rollout state.
- Forced remote downgrade of an update that already committed successfully.
- Destructive cleanup of Board 5/6 evidence, repo-external acceptance artifacts, or either historical `NUL` entry.
- Squash/rebase/amend/history rewrite of the Board 5/6 security lineage.

## 4. Considered production approaches

### Option A — Fully autonomous CI production

CI builds, deploys, publishes, registers, and enables releases automatically.

**Rejected.** It gives one machine identity the ability to create a candidate and make it immediately eligible for real users. A CI credential compromise would cross both preparation and launch boundaries.

### Option B — Conservative automation with human launch authority (**selected**)

CI may test, build, sign the Ed25519 manifest, prepare R2 transport, publish immutable provenance, deploy a specifically approved Worker commit, and register releases disabled/paused. Human Access sessions remain the only normal mechanism that can change release state.

**Selected because** it meets Board 7 automation goals without collapsing preparation and launch authority into one credential domain.

### Option C — Mostly manual production

CI runs tests only; production deploy/release preparation remain operator-local.

**Rejected as the target state.** It preserves too much operator drift and does not complete the Board 7 automation goal. Repo-external manual signing/provisioning remains an explicit fail-closed fallback only when the GitHub production secret boundary cannot meet the required security properties.

## 5. Threat model

Board 7 specifically defends against:

- accidental deployment to production from local/default/staging configuration;
- production access through `workers.dev` or an unexpected hostname;
- API-host access to privileged admin/machine routes;
- Admin-host use as an unnecessary public-client ingress;
- human Access JWT accepted as machine identity, or Service Token JWT accepted as human identity;
- a GitHub Actions credential being able to enable a production release;
- a workflow deploying an arbitrary feature/PR/detached SHA;
- mutable third-party GitHub Action tags changing privileged workflow behavior;
- staging Secret/key/data leakage into production;
- release-signing private key exposure to unrelated workflow jobs or post-key untrusted Actions;
- runtime GitHub read credential reappearing in production even though R2 is the runtime backend;
- production break-glass material becoming a normal standing secret;
- different production bytes reusing the historical `0.5.1` / Launcher `0.1.0` identities;
- deleting immutable provenance or R2 release bytes as a rollback mechanism;
- logs containing Authorization, license keys, device tokens, admin sessions, contact plaintext, diagnostic bodies, private keys, or Secrets.

The design does not claim to protect an already-compromised Windows host from an attacker with arbitrary local administrator write/execute capability. The Private / Controlled profile also explicitly accepts the absence of Windows-recognized commercial publisher identity for first installation.

## 6. Production topology

Production uses exactly one Worker service:

```text
Worker: wechat-cli-license-update
```

and two exact custom hostnames resolved from a provisioning-time `<BASE_DOMAIN>`:

```text
API:   api.<BASE_DOMAIN>
Admin: admin.<BASE_DOMAIN>
```

`<BASE_DOMAIN>` is a design symbol during B7-G0/B7-G1 and may remain an explicit fail-closed sentinel in source configuration. **Before B7-G3 performs any domain/resource provisioning, the exact base domain must be frozen and included in the approved mutation matrix.** B7-G1 must prove the unresolved symbol cannot pass production preflight.

Production requires:

```text
workers_dev = false
api_origin != admin_origin
```

No production `workers.dev` fallback is permitted.

Production resource inventory:

```text
Worker:          wechat-cli-license-update
D1:              wechat-cli-license-production
R2 releases:     wechat-cli-releases-production
R2 diagnostics:  wechat-cli-diagnostics-production
API hostname:    api.<BASE_DOMAIN>
Admin hostname:  admin.<BASE_DOMAIN>
```

Staging resources retain their existing names and identities and are not renamed or repurposed.

## 7. Production ingress preflight contract

The fail-closed deployment preflight is expanded from the Board 6 staging-centric Access checks to a symmetric production contract.

A production preflight must reject unless all are true:

```text
workers_dev == false
api_origin != admin_origin
api hostname is in the exact production custom-domain route set
admin hostname is in the exact production custom-domain route set
embedded Launcher api_base_url == exact production API origin
production Access issuer is exact
production JWKS origin == issuer origin
human Access audience is exact
machine Access audience is exact
human audience != machine audience
no staging hostname appears in production Worker/trust/deployment config
no production hostname appears in staging Worker/trust/deployment config
production D1/R2 identities are non-placeholder and distinct from staging
production required Secret inventory is exactly derivable and present by name
production runtime does not require GitHub release-read credential
production normal runtime does not require legacy admin pepper
```

Separate Access applications/audiences are the selected production model:

```text
Human Access app       -> admin.<BASE_DOMAIN>/v1/admin/*
Automation Access app  -> admin.<BASE_DOMAIN>/v1/automation/*
```

They share the production Access team issuer/JWKS origin but must have distinct application audiences.

## 8. Worker runtime Host + Path firewall

Cloudflare routing and Access policy are not the final authorization boundary. The Worker itself must classify every production `/v1/*` request by exact request hostname and path before route handlers execute.

### API hostname

Allowed current route classes are limited to the native/public surface:

```text
/v1/health
/v1/licenses/*
/v1/devices/*
/v1/updates/*
/v1/diagnostics/*
```

The conceptual download class is currently implemented as `/v1/updates/download`; Board 7 does **not** open an unused `/v1/downloads/*` alias merely to match a naming sketch.

The API hostname must reject:

```text
/v1/admin/*
/v1/automation/*
all other unclassified /v1 paths
```

### Admin hostname

Allowed privileged route classes:

```text
/v1/admin/*
/v1/automation/*
```

Public client routes are denied by default on the Admin hostname. A narrowly justified exception would require a later design amendment; none is part of Board 7.

### Unexpected hosts

In production, any unexpected host, any staging host, and any `*.workers.dev` hostname is denied before privileged handlers. Privileged-path attempts return 403 fail-closed. The existing browser `Origin` policy remains a separate defense and must not be used as a substitute for Host authority.

Staging receives an explicit staging host policy in source so production hostnames cannot be accepted there; this is a source-level guard, not a staging cloud mutation under B7-G1.

## 9. Human administrator identity

Human administration retains the Board 6 accepted flow:

```text
Cloudflare Access human JWT
-> exact issuer/audience/signature/time validation
-> normalized verified email identity
-> active admin_principals row
-> challenge-bound one-time code
-> 30-minute wcas session
-> exact scope check
-> <=10-minute recent-auth requirement for high-risk routes
```

Normal production admin requests use `authMode == "session"`.

Production legacy admin authentication remains default-off. `ADMIN_TOKEN_PEPPER` is not part of the normal production required Secret inventory. A future break-glass event is a separate temporary authorization specifying reason, exact principal/scopes, start, hard expiry, and cleanup/rotation actions. No standing fallback endpoint is introduced.

## 10. Machine automation identity

GitHub Actions never uses a human `wcas` session and never enters the human one-time-code flow.

Machine authentication uses a dedicated Cloudflare Access Service Token application and JWT path:

```text
Access Service Token
-> Cf-Access-Jwt-Assertion
-> exact production issuer/JWKS
-> exact automation audience
-> signature + exp/nbf/iat validation
-> configured machine-specific identity claim
-> exact allowlisted service-token client identity
-> active automation principal
-> exact machine scope check
```

The exact external service-token identity value does not exist during design. B7-G4 records the provisioned safe identity metadata and stores the allowed identity in the approved production non-secret configuration; the service-token secret itself remains outside repository/docs/logs.

Human and machine identity configuration is deliberately separate:

```text
ACCESS_HUMAN_AUDIENCES
ACCESS_HUMAN_IDENTITY_CLAIM
ACCESS_AUTOMATION_AUDIENCES
ACCESS_AUTOMATION_IDENTITY_CLAIM
ACCESS_AUTOMATION_IDENTITIES
```

The existing `ACCESS_AUDIENCES` staging field may remain a staging compatibility input while B7-G1 introduces the split. **Production must not accept the compatibility fallback.**

Machine identities use a distinct `automation_principals` table rather than being inserted into human `admin_principals`. B7-G1 introduces migration `0008_automation_identity.sql`: it creates the machine-principal table and migrates the `audit_events.actor_type` constraint to admit `automation` while preserving every existing audit row. Audit records must distinguish `actor_type=automation`; production automation must never appear as a human `admin` actor.

## 11. Human and machine route separation

Human routes remain under:

```text
/v1/admin/*
```

Machine release-preparation routes are introduced under:

```text
/v1/automation/releases
/v1/automation/releases/:releaseId/package
```

The automation surface contains only the minimum operations required by the publisher:

- upload exact R2 package bytes/readiness;
- read release metadata required for reconcile;
- register/finalize a release disabled/paused.

There is **no automation release-state PATCH route**.

Human admin release routes remain available for operator review/state control, but release registration is moved to the narrower `releases:register` capability rather than generic `releases:write`.

## 12. Capability matrix

Board 7 replaces the overloaded `releases:write` production model with:

```text
releases:upload
releases:read
releases:register
releases:state
```

Selected initial production authorization matrix:

| Capability | Primary human admin | Release automation |
|---|---:|---:|
| `licenses:read` | yes | no |
| `licenses:write` | yes | no |
| `devices:read` | yes | no |
| `devices:write` | yes | no |
| `releases:upload` | yes | yes |
| `releases:read` | yes | yes |
| `releases:register` | yes | yes |
| `releases:state` | yes | **no** |
| `diagnostics:read` | yes | no |
| `diagnostics:delete` | yes | no |
| `contacts:rotate` | yes | no |
| principal management | no standing HTTP scope in Board 7 | no |

Initial logical principals:

```text
human principal:      production-primary-admin
machine principal:    release-automation-production
```

The human principal maps to the separately approved verified production email identity and receives exactly the scope set shown above, with no wildcard. Principal bootstrap/revoke remains a separately authorized D1/identity operation rather than a new standing self-service HTTP administration API.

The automation principal receives exactly `releases:upload`, `releases:read`, and `releases:register`, with no wildcard.

## 13. Human-only release-state enforcement

Scope separation is necessary but insufficient. Every endpoint capable of changing any of:

```text
enabled
paused
rollout_percentage
```

must enforce both:

```text
required scope == releases:state
authMode == human short-lived session
```

A machine identity must be rejected even if a future configuration mistake accidentally gives it `releases:state`.

Production legacy break-glass state mutation is also excluded from the normal route contract. If a future incident explicitly authorizes break-glass use, the incident authorization must state whether release-state mutation is permitted; Board 7 does not silently treat break-glass as equivalent to a human Access session.

This creates the root invariant:

> **Machine automation cannot enable a production release by capability, route, or authentication mode.**

## 14. Clean-room production data bootstrap

Production D1 is created empty and receives **migrations only**. No staging database export/import or row copy is permitted.

Before any production identity is inserted, read-only acceptance must prove the clean-room state has:

```text
0 staging licenses
0 staging devices
0 staging admin sessions
0 staging diagnostics
0 Board 4 release rows
0 Board 5 release rows
0 Board 6 release rows
0 JD25 data
0 G5 synthetic data
0 G7 synthetic data
```

The first production business rows are created only under separately authorized gates:

- B7-G4: approved human and automation principals only;
- B7-G7: one internal production canary license/device and canary release evidence;
- B7-G8: first real Private user licenses only after canary acceptance.

Every production business row must have an explainable Board 7 origin and audit trail.

## 15. Production Secret and key lifecycle

Production does not inherit staging selector numbers. It begins its own lifecycle at V1 with fresh independent random material.

The required runtime Secret inventory is not maintained as a hand-copied authoritative list. The deployment preflight derives it from:

1. `deployment-policy.json` versioned secret prefixes;
2. exact production current/readable selectors;
3. `CONTACT_ENCRYPTION_KEY_VERSION`;
4. non-versioned production-required runtime secrets such as the lease signer private key.

Initial production selectors are all current/readable V1. Representative exact names:

```text
LICENSE_KEY_PEPPER_V1
DEVICE_TOKEN_PEPPER_V1
ADMIN_SESSION_PEPPER_V1
CONTACT_LOOKUP_PEPPER_V1
CONTACT_ENCRYPTION_KEY_V1
DOWNLOAD_TICKET_SECRET_V1
DIAGNOSTIC_UPLOAD_SECRET_V1
RATE_LIMIT_PEPPER_V1
LEASE_SIGNING_PRIVATE_KEY
```

Trust key identities are independent:

```text
lease-key-production-01
release-key-production-01
```

`release-key-production-01` is publisher-side, not a Worker runtime Secret. Its public key enters the embedded Launcher trust profile.

Production normal runtime must not require:

```text
GITHUB_RELEASE_READ_TOKEN
ADMIN_TOKEN_PEPPER
```

The R2 backend removes production runtime GitHub read-token need. Legacy admin material remains absent unless a separately approved temporary break-glass event provisions it.

No production V1 material is retired during first launch. Production rotation starts only after launch acceptance and follows the Board 6 overlap/switch/rollback model under its own future production rotation gate.

## 16. GitHub and Cloudflare credential model

### Cloudflare production deployment

The privileged deploy workflow uses a scoped Cloudflare API Token plus Account ID. Global API keys are prohibited. The token is restricted to the exact account/zone/resources required by Worker deployment/readback.

### Cloudflare Access automation

The release workflow uses a dedicated Access Service Token credential to reach `/v1/automation/*`. It cannot mint or impersonate a human `wcas` session.

### GitHub cross-repository provenance

The source workflow `GITHUB_TOKEN` is not assumed to have write access to the private release provenance repository.

Selected default publisher identity:

```text
GitHub App: wechat-cli-release-publisher
installation scope: release provenance repository only
```

Its installation token is short-lived and permissions are limited to the release/content write operations actually required plus metadata read. Issues, PR administration, Actions administration, repository administration, and unrelated repositories are out of scope.

A fine-grained PAT is a separately approved fallback, not the default design.

### GitHub Environment

A production GitHub Environment is defense in depth, not the root release-control boundary. If the account cannot provide an acceptable private Environment Secret boundary, the privileged CI gate fails closed and production signing/provisioning falls back to an explicitly approved repo-external manual path. It does not downgrade production private keys into ordinary repository secrets merely to achieve automation.

## 17. CI/CD workflow architecture

Board 7 introduces three principal workflows.

### `ci.yml`

Triggers:

- pull requests;
- ordinary pushes as repository policy allows;
- optional manual dispatch.

Credentials: none of the production credential set.

Minimum checks:

- Python full suite;
- Worker typecheck;
- full Vitest;
- deployment policy/preflight tests;
- Windows packaging/version/trust-profile tests;
- sensitive-value scan;
- repository diff/check equivalents.

Default permissions:

```yaml
permissions:
  contents: read
```

### `deploy-production-worker.yml`

Trigger: `workflow_dispatch` only.

Input: full exact canonical main SHA.

Sequence:

```text
validate requested SHA shape
checkout exact SHA
prove checkout SHA == requested SHA
prove requested SHA == approved/current canonical main deployment target
fresh full tests
production preflight
exact D1/R2/domain/Access/trust reconcile
atomic Worker deploy
fresh health + route-isolation + read-only binding/version reconcile
record Worker Version ID + full source SHA + config identity
```

This workflow cannot create releases, licenses, installer distribution, or release enablement.

### `publish-production-release.yml`

Trigger: `workflow_dispatch` only.

Inputs:

```text
full exact canonical main SHA
SemVer
channel
release notes
```

Sequence:

```text
canonical-main proof
fresh tests
Windows build
artifact verification
production Ed25519 manifest signing
R2 upload/readiness via automation route
private GitHub immutable provenance publication
Worker register disabled/paused via automation route
read-only reconcile
STOP
```

It contains no enable/resume/rollout-raise/license-creation operation.

## 18. Workflow supply-chain hardening

All external third-party GitHub Actions used by privileged workflows are pinned to an immutable full commit SHA. Mutable references such as `@main`, `@master`, or version tags are not production security roots.

Privileged workflows require:

- explicit minimal `permissions`;
- `workflow_dispatch` rather than arbitrary PR execution;
- no production credentials in untrusted fork/PR contexts;
- separate concurrency groups:
  - `production-worker`
  - `production-release`
- no arbitrary shell/source fetched from untrusted branches after credentials are injected;
- signing private key is injected only after all required third-party Actions have completed.

## 19. Release-signing key in CI

`release-key-production-01` is the only production release private key considered for GitHub production Environment Secret storage under the current profile.

Rules:

- visible only to the signing job;
- build/test jobs cannot read it;
- materialized only into a runner temporary file;
- removed in unconditional cleanup/finally handling;
- never uploaded as an artifact;
- never printed or included in debug output;
- logs record only signing key ID and public verification evidence;
- after private-key injection, no arbitrary/untrusted third-party Action runs;
- it is not co-located with the lease signer private key.

`lease-key-production-01` remains a Worker runtime/bootstrap credential domain and is provisioned/rotated only under production identity/key gates.

## 20. Git source lifecycle and canonical-main enforcement

The Board 7 design/governance commit is a docs-only child of Board 6 closure `740ddab`. The implementation worktree is created from that design commit, so its ancestry is exactly the Board 6 closure lineage while retaining the Board 7 design documents.

Recommended implementation branch:

```text
board7/production-automation-controlled-launch
```

Lifecycle:

```text
Board 7 design/governance commit
-> fresh Board 7 worktree from that docs-only descendant of 740ddab
-> B7-G1 local implementation
-> fresh security audit
-> B7-G2 separately authorized branch push
-> separately authorized PR
-> separately authorized merge preserving history
-> exact canonical main readback
-> production workflows may target only merged canonical main
```

No squash, rebase, amend, or history rewrite is part of the design.

Production workflows must prove:

```text
requested_sha == checked_out_sha == approved canonical main deployment SHA
```

A feature-branch SHA, unmerged Board 7 worktree SHA, PR head, or detached orphan commit is rejected even if its tests pass.

## 21. Production deployment trust profile

The first production Launcher embeds schema-v2 trust:

```text
schema_version=2
distribution_profile=private_controlled
environment=production
api_base_url=https://api.<BASE_DOMAIN>
expected_channel=stable
fingerprint_salt=<fresh production value>
release_public_keys={release-key-production-01: <public key>}
lease_public_keys={lease-key-production-01: <public key>}
windows_publisher_policy=""
```

The exact base domain, fingerprint salt, and public keys are resolved under the separately approved production bootstrap gates. They never come from staging.

Mutable external Launcher configuration cannot override environment, distribution profile, API origin, channel policy, fingerprint salt, release trust, lease trust, or publisher policy.

Required negative acceptance:

- staging Launcher cannot be reconfigured into production;
- production Launcher cannot be redirected to staging;
- production trust profile rejects staging hostnames;
- staging policy rejects production hostnames where environment-specific trust is evaluated.

## 22. App, Launcher, and Build ID strategy

The first production application version is:

```text
0.6.0
```

The first production Launcher version is:

```text
0.2.0
```

The Launcher bump is required because its accepted behavior materially differs from historical 0.1.0: Windows file-URL normalization, pre-load deadlock repair, process-tree termination/port release, embedded deployment trust, pywebview compatibility boundary, Authenticode capability, distribution-profile support, and production trust anchoring.

Production Build ID:

```text
prod-060-<12-char-main-sha>
```

Acceptance/provenance records always include the complete source commit hash in addition to the human-readable Build ID.

Different production bytes must never reuse the historical immutable `0.5.1` or Launcher `0.1.0` identities.

## 23. Private first-install trust trade-off

The Private / Controlled profile deliberately does not claim commercial Windows publisher identity.

Initial installer trust is:

```text
controlled authenticated private delivery
+ out-of-band SHA-256 verification
+ embedded production Ed25519 release trust
+ embedded production lease trust
```

SHA-256 is an integrity comparison and is **not** represented as equivalent to Authenticode publisher identity. Where practical, installer bytes and expected SHA-256 are communicated through distinct trusted channels.

Unknown Publisher / SmartScreen friction remains an accepted Private-profile trade-off. A public download portal and commercial publisher identity remain future Public / Formal Distribution work.

## 24. Production release lifecycle

The accepted Board 6 lifecycle remains authoritative:

```text
build immutable bytes
-> verify build
-> Ed25519-sign manifest
-> create/upload private GitHub Draft for inspection
-> R2 exact package readiness
-> prove R2 hash/size/transport readiness while candidate is non-selectable
-> publish immutable private GitHub provenance/tag with make_latest=false
-> reconcile provenance against R2 bytes
-> Worker register/finalize with enabled=false, paused=true
-> STOP
-> separate human state gate may enable
```

The implementation must preserve the exact persisted terminal state:

```text
enabled=false
paused=true
```

after automated registration.

GitHub provenance and R2 release objects are not deleted as normal rollback mechanisms.

## 25. Internal canary lifecycle

The first production installation baseline is `0.6.0`. A meaningful update test therefore uses a second internal-only candidate:

```text
0.6.0 -> 0.6.1-canary.1
```

Before any canary license exists, B7-G6 uses the production release automation path to publish/register the exact canonical-main **stable `0.6.0` release** and must leave it in the automated terminal state:

```text
enabled=false
paused=true
```

B7-G7 then creates exactly one internal canary license with:

```text
release_channel=beta
maximum_devices=1
```

The canary license is deliberately beta from creation and is never channel-mutated. The current product has no normal license-channel mutation API, and Board 7 does not add one merely for acceptance. The `0.6.0` baseline reaches the canary machine through the controlled private installer, not through release selection, so the beta entitlement does not need to select the stable `0.6.0` row. After the canary license exists, a fresh human Access session separately enables the named stable `0.6.0` release; no stable real-user license exists yet, so this proves human-only first-release state control without exposing the release to a real-user population.

The same beta canary license can then select the internal-only beta `0.6.1-canary.1` candidate without changing entitlement or creating a second canary license. Real Private user licenses are created later as stable licenses only after canary/recovery acceptance.

No real Private user license is created before canary acceptance.

Canary acceptance covers:

1. private delivery and SHA-256 verification of the `0.6.0` installer;
2. clean production installation;
3. activation and one-device enforcement;
4. production health and server-authoritative channel;
5. seven-day lease/offline boundaries without changing system time;
6. diagnostics consent/upload/read/delete lifecycle;
7. internal beta visibility of `0.6.1-canary.1` only to the canary license;
8. real update to the canary candidate;
9. controlled fault/health failure and transactional rollback behavior;
10. exact failed-candidate suppression;
11. candidate pause/disable and terminal reconcile.

A percentage canary is not used for the first production launch because the production population is intentionally only the one internal license.

## 26. Later controlled rollout

After real Private users exist, a normal stable update first passes internal beta canary. Then the default controlled stable sequence is:

```text
25% -> 50% -> 100%
```

Each increase is a separate human state mutation with read-only reconciliation of health, audits, failed-release evidence, and diagnostics signals before the next step.

If the population grows enough that 25% is too coarse, the preferred sequence becomes:

```text
10% -> 25% -> 50% -> 100%
```

Automation never raises rollout percentage.

## 27. Rollback model

Three rollback classes remain separate.

### Worker deployment rollback — one selected method

The production standard is:

> **Redeploy the exact recorded last-known-good canonical main commit through the same fail-closed production deployment workflow.**

Cloudflare Worker Version IDs are recorded as evidence/readback identifiers, not used as the primary rollback primitive.

The rollback workflow must require the recorded full last-known-good main SHA, run production preflight, use the accepted production config identity, deploy, and read back the new Worker Version ID. This keeps source/config provenance explicit and exercises the same guardrails as forward deployment.

Secret/key rollback remains a separate credential operation; code redeploy does not silently change Secret values.

### Release propagation rollback

A bad release is:

```text
pause + disable
```

Immutable GitHub provenance remains. R2 bytes remain. No normal rollback deletes them.

### Client binary rollback

If the candidate fails the pre-commit health gate, the existing transactional Launcher rollback restores the prior application.

If the update committed successfully and a later business defect is discovered, production does **not** force remote downgrade. The response is:

```text
pause/disable bad release
-> build and publish a forward-fix next 0.6.x release
```

## 28. Diagnostics, privacy, and logging

Production retains the Board 6 diagnostics policy:

- explicit consent;
- maximum 20 MiB;
- 15-minute upload-session TTL;
- no more than seven-day cloud content retention;
- opaque R2 object path;
- admin-controlled audited download/delete;
- local bundle not silently deleted.

Before production observability is enabled beyond the minimum, Board 7 adds log-redaction acceptance proving none of the following enter Worker logs:

```text
Authorization header
license key
device token
admin session
Access Service Token secret
contact plaintext
diagnostic body/payload
private key
Worker/GitHub/Cloudflare Secret value
```

Observability/log sampling is an explicit privacy/operations sub-gate. Maximum logging is not a default launch setting.

## 29. Backup and recovery minimums

Board 7 does not build a separate disaster-recovery platform. It establishes enough evidence to recover deterministically:

- D1 export/snapshot before an approved destructive schema/data mutation;
- GitHub provenance is immutable and not normally deleted;
- production R2 release objects are immutable and never overwritten;
- production trust profile/public-key registry has a restricted repo-external frozen copy;
- lease/release recovery private material remains in restricted repo-external secure storage and never in repository/docs/logs;
- every accepted Worker deployment records:
  - Worker Version ID;
  - full canonical main source commit;
  - production config identity/digest;
- every accepted release records exact manifest/package hashes, key ID, provenance IDs, and rollout terminal state;
- current/readable Secret selectors are recorded by safe metadata only.

An incident runbook must be able to answer: last-known-good Worker/source, applicable D1 recovery point, last accepted release, and key selector/trust state.

## 30. Production key rotation and emergency-revoke handoff

First launch does not retire any production V1 material. After launch, production rotation follows the Board 6 proven pattern:

```text
add new independent version
-> overlap readers/trust
-> switch writer/signer
-> prove new output
-> rollback before retirement
-> re-switch
-> wait real validity/offline window
-> separately authorize retirement
```

Emergency revoke semantics remain purpose-specific:

- removing a readable HMAC/ticket version immediately invalidates its outstanding credentials;
- contact encryption key cannot be removed while rows still depend on it unless data inaccessibility is explicitly accepted;
- lease/release public-key revocation requires an installed-client trust update; server-side signer replacement alone does not revoke already embedded trust.

## 31. Gate matrix

### B7-G0 — Production Design & Source Gate

This document, its implementation plan, current-state wording repair, internal review, and docs-only local commit. No product code or external mutation.

### B7-G1 — Local Production Hardening Gate

Local TDD only:

- production Host/Path firewall;
- production Access preflight contract;
- human/machine identity split;
- automation principal/audit model;
- release scope split;
- human-only release-state enforcement;
- production config/trust-profile source definitions;
- App `0.6.0` / Launcher `0.2.0` / production Build-ID logic;
- GitHub workflow source definitions and workflow-policy tests;
- production secret-inventory derivation;
- production deployment/release automation definitions that remain unexecuted.

No cloud/GitHub external mutation.

### B7-G2 — Source Integration Gate

Fresh audit, then separately authorized push, PR, and merge preserving history. Exact canonical main readback. Still no production deploy. Push, PR, and merge are separate sub-gates; one does not authorize the next.

### B7-G3 — Production Infrastructure Provision Gate

Freeze the exact base domain, then create exact production D1/R2 resources and API/Admin DNS/Access application identities/policies. No Board 7 application Worker is deployed. If Cloudflare requires a serving Worker script before a custom-domain route can be attached, G3 records/reserves the hostname/DNS/Access identity and defers serving route attachment to B7-G5 rather than deploying a placeholder application.

Because the production D1 ID and Access audiences do not exist before G3, G3 ends with a safe non-secret source-configuration finalization containing the exact approved resource/domain/audience identities. Any push/PR/merge needed to put that config on canonical main is a separately approved **B7-G3 source-config sub-gate**; production deployment remains forbidden until that exact config is present on canonical main.

### B7-G4 — Production Identity & Key Bootstrap Gate

Fresh production runtime Secrets, `lease-key-production-01`, `release-key-production-01`, human admin principal, automation principal, Access Service Token identity, approved GitHub App/workflow identities. No real-user license.

### B7-G5 — Production Worker Deploy Gate

Production source config has exact resolved resource/domain values on canonical main; deploy exact approved main commit through production workflow; health, Host/Path, Access, D1/R2, and environment-isolation acceptance. No release enable.

### B7-G6 — CI/CD Automation Acceptance Gate

Real CI/deploy/release-preparation automation acceptance, including proof that machine identity can upload/read/register but cannot change release state. The selected first release-preparation acceptance target is the exact canonical-main stable `0.6.0` production release, which must finish `enabled=false` / `paused=true`. Its immutable provenance/R2/registration mutations are explicitly enumerated in the B7-G6 authorization matrix; B7-G6 does not enable it.

### B7-G7 — Production Canary E2E Gate

Create exactly one internal **beta** production license/device (`maximum_devices=1`), then separately use a fresh human Access session to enable the already registered stable `0.6.0` release while there are still no stable real-user licenses. Install the controlled `0.6.0` baseline directly, then use the same beta canary license for `0.6.1-canary.1` internal beta update/fault/rollback/diagnostics acceptance. Do not add a license-channel mutation path and do not create a second canary license. No real Private user issuance.

### B7-G8 — First Controlled Release & Recovery Gate

Human-only release state operations, pause/resume/rollout controls, bad-release suppression, last-known-good Worker redeploy drill, credential revoke runbook acceptance, and only after canary success the first separately authorized real Private user issuance.

### B7-G9 — Final Production Closure

Fresh full verification and production read-only reconciliation, final acceptance report, canonical state/roadmap closure, local governance commit. No new production mutation merely to satisfy closure.

## 32. Exact side-effect boundaries

Board 7 design approval does not authorize implementation or any external effect.

The following require explicit later authorization in their named gates:

- creating production D1/R2/Worker/domain/Access resources;
- DNS/custom-domain mutation;
- creating any production Secret or private key;
- creating human/automation production principals;
- Access Service Token creation;
- GitHub App installation or credential provisioning;
- GitHub Actions Environment/Secret writes;
- source branch push;
- PR creation;
- merge to main;
- production Worker deployment;
- GitHub release/provenance publication;
- production R2 upload;
- production license/device creation;
- release enable/pause/resume/rollout mutation;
- production key rotation/revoke/retirement;
- Public/Formal Authenticode procurement or use.

A gate approval never implies the next gate.

## 33. Acceptance criteria

Board 7 cannot close unless all are proven with fresh evidence:

### Safety

- machine has no route/capability/auth-mode path to release-state mutation;
- API host cannot reach admin/automation handlers;
- Admin host rejects unnecessary public API routes;
- production `workers.dev` bypass is impossible;
- human and machine Access assertions cannot be confused by audience/identity/auth-mode;
- production has no staging data or Secret/key reuse;
- production CI rejects non-main/unmerged SHA;
- cross-repo publisher is least privilege;
- release signing private key is visible only to the signing job and not to later untrusted Actions;
- production runtime has no GitHub release-read credential dependency;
- normal production has no legacy admin Secret dependency.

### Consistency

- App `0.6.0`;
- first stable production `0.6.0` release is automation-published/registered disabled+paused and only later human-enabled;
- the sole internal canary license is beta from creation and is never channel-mutated;
- Launcher `0.2.0`;
- `distribution_profile=private_controlled`;
- empty `windows_publisher_policy`;
- R2 runtime distribution;
- immutable private GitHub provenance;
- clean-room production D1;
- human-only release-state mutation;
- exact production API/Admin host split;
- first real update candidate `0.6.1-canary.1` is internal-only.

### Operational acceptance

- exact canonical-main source deploy;
- Worker health/route/Access acceptance;
- automated disabled/paused release registration;
- internal canary install/activation/offline/update/rollback/diagnostics acceptance;
- pause/disable and forward-fix semantics accepted;
- last-known-good Worker redeploy drill accepted;
- recovery evidence recorded.

## 34. Deferred Public / Formal Authenticode

Commercial Authenticode remains explicitly deferred. Board 7 Private / Controlled closure does not require or claim:

- provider selection;
- payment/subscription;
- KYC;
- managed/HSM signing key;
- real certificate;
- non-empty publisher policy;
- real Authenticode signature on production artifacts.

If Public / Formal Distribution is later activated, it requires a new design/authorization covering provider, publisher identity, fees, KYC, managed signing material, non-empty `windows_publisher_policy`, signing order, timestamping, verification, and acceptance.

## 35. Board 7 closure definition

Board 7 is `accepted complete` only after B7-G0 through B7-G9 have independently passed. At closure:

- production is live only on the exact API/Admin custom hostnames;
- production remains Private / Controlled Distribution;
- internal canary acceptance is complete;
- real Private issuance has begun only after canary approval;
- CI/CD is auditable and cannot autonomously enable a release;
- source deployed to production is exact merged canonical main;
- production D1/R2/Secrets/keys are independent of staging;
- recovery/rollback evidence exists;
- final production acceptance report and canonical roadmap state are committed;
- the original seven-board Authorized Update Program is accepted complete.

## 36. B7-G0 authorization boundary and next gate

This design phase permits only read-only inspection, design/spec and implementation-plan authoring, canonical current-wording repair, local governance verification, and a docs-only local commit.

It does not authorize product-code changes, production/GitHub/Cloudflare mutations, main changes, push/PR/merge, key generation, release publication, license creation, or deployment.

After B7-G0 docs closure, the first implementation authorization is:

> **B7-G1 Local Production Hardening Gate** — local TDD for production Host/Path firewall, Access preflight, human/machine identity split, release capability split, human-only release-state enforcement, production config/trust-profile source definitions, App/Launcher version bump, production Secret-inventory derivation, and GitHub workflow source definitions/tests. No cloud/production/GitHub external mutation.
