# Board 7 — Production Automation & Controlled Launch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Authorization rule:** this plan is an execution map, not blanket authorization. Every gate and every named external side-effect sub-gate must be separately approved before execution.

**Goal:** Convert the Board 6 accepted Private / Controlled staging system into a clean-room production system with exact API/Admin ingress, least-privilege human/machine authorization, auditable GitHub Actions, internal canary acceptance, and controlled production launch without giving automation release-enable authority.

**Architecture:** Preserve the Board 6 R2-runtime/GitHub-provenance/update-integrity model. Add production Host/Path authority, a dedicated Access Service Token automation identity and machine route surface, narrower release capabilities, human-only release-state enforcement, clean-room production V1 secrets/keys, canonical-main-only workflows, and a one-device production canary before real Private issuance. Local TDD and source integration precede every cloud mutation.

**Tech Stack:** Python 3.12, TypeScript/Hono, Cloudflare Workers/D1/R2/Access, GitHub Actions/GitHub App, PyInstaller/WebView2, Ed25519, SHA-256, unittest, Vitest, Wrangler.

**Design source:** `docs/superpowers/specs/2026-08-15-board-7-production-automation-controlled-launch-design.md`

**Board 6 closure base:** `740ddabc5808a6a68c2dd812ae81c039b17d23b4`

---

## 0. Global execution invariants

1. Do not implement a gate until that gate is explicitly authorized.
2. The current B7-G0 docs commit is a descendant of exact Board 6 closure `740ddab`; B7-G1 implementation starts from that docs commit so the lineage retains the formal Board 7 design while remaining based on the exact Board 6 closure.
3. Preserve Board 5 evidence `67d3dec0fd1c4a02c87be1ab79c4f78ea63f49d6`, frozen main `a579a25cb7f16e6fdf88d618252b4a5cbffef53d`, and both historical `NUL` entries until a separate cleanup authorization.
4. No reset, rebase, amend, squash-history rewrite, force push, tag rewrite, or destructive cleanup.
5. Every local code task follows RED -> verify RED -> minimal GREEN -> focused verification -> relevant full verification -> `git diff --check` -> local commit.
6. No production resource/Secret/key/principal, DNS/Access mutation, production deploy, release publication, production R2 upload, license creation, release state mutation, push, PR, or merge is inferred from a previous gate.
7. Every cloud gate begins with exact read-only preflight and ends with independent read-only reconcile.
8. Secret/private-key/license/device/session values never enter tracked files, docs, logs, shell history output, or test fixtures.
9. Production workflow input must resolve to exact canonical main; no worktree-only/PR-head/unmerged source may deploy.
10. Machine automation must never acquire a functional path to `enabled`, `paused`, or `rollout_percentage` mutation.
11. Production remains `private_controlled` with empty Windows publisher policy. Commercial Authenticode remains deferred.
12. Stop immediately at every **Mandatory STOP** below even if later tasks appear mechanically ready.

---

# Phase 1 — B7-G1 Local Production Hardening Gate

**Gate boundary:** local worktree/code/tests/docs only. No Cloudflare/GitHub external mutation, no production resources, no production Secret/key generation, no push/PR/merge.

## Task 1: Create the isolated Board 7 implementation lineage

**Files:** none initially; Git/worktree operation only after B7-G1 approval.

- [ ] **Step 1: Verify the design baseline read-only**

Run from the Board 6/design workspace:

```powershell
git rev-parse HEAD
git log -2 --format="%H %P %s"
git status --short
```

Require:

```text
HEAD = the B7-G0 docs/design commit reported by canonical project state
that commit's ancestry includes exact 740ddabc5808a6a68c2dd812ae81c039b17d23b4
status = only historical ?? NUL
```

Also read-only verify main and Board 5 evidence remain frozen at their recorded commits.

- [ ] **Step 2: Open a fresh managed worktree from the B7-G0 design commit**

Use DevSpace worktree mode with the exact design commit as `baseRef`. Record the returned path/workspace ID. Recommended branch name:

```text
board7/production-automation-controlled-launch
```

If the worktree system chooses a generated branch name, record it and do not rename it without need.

- [ ] **Step 3: Verify the new worktree boundary**

```powershell
git rev-parse HEAD
git status --short
git merge-base HEAD 740ddabc5808a6a68c2dd812ae81c039b17d23b4
```

The merge-base must be `740ddab` and there must be no copied `NUL` mutation introduced by tooling.

### Mandatory STOP on mismatch

Do not implement product code if the lineage/base/status differs.

---

## Task 2: Add production Host/Path authority firewall

**Files:**
- Create: `services/license-update-worker/src/ingress_policy.ts`
- Modify: `services/license-update-worker/src/index.ts`
- Modify: `services/license-update-worker/src/types.ts`
- Modify: `services/license-update-worker/wrangler.jsonc`
- Test: `services/license-update-worker/test/ingress_policy.test.ts`
- Modify: `services/license-update-worker/test/security_policy.test.ts` only where Origin-vs-Host composition needs coverage.

- [ ] **Step 1: Write RED tests for exact production host/path classification**

Cover at least:

```text
production API host + /v1/health -> allowed
production API host + /v1/licenses/activate -> allowed
production API host + /v1/devices/validate -> allowed
production API host + /v1/updates/check -> allowed
production API host + /v1/updates/download -> allowed
production API host + /v1/diagnostics/sessions -> allowed
production API host + /v1/admin/releases -> 403
production API host + /v1/automation/releases -> 403
production Admin host + /v1/admin/releases -> allowed to auth layer
production Admin host + /v1/automation/releases -> allowed to auth layer
production Admin host + /v1/licenses/activate -> 403
production workers.dev host + privileged route -> 403
staging host + production privileged route under production env -> 403
unknown host -> 403 for /v1/*
local environment retains test/local compatibility only through explicit local policy
```

Use fake hosts such as `api.prod.example.test` and `admin.prod.example.test`; do not encode the future real domain in tests.

- [ ] **Step 2: Run RED**

```powershell
cd services/license-update-worker
npm test -- --run test/ingress_policy.test.ts
```

Expected: FAIL because the host/path firewall does not exist.

- [ ] **Step 3: Implement a small route-authority classifier**

Create an interface shaped like:

```ts
export type IngressClass = "api" | "admin";

export function assertWorkerHostPathAllowed(
  request: Request,
  env: Env,
): IngressClass;
```

Production derives exact hosts only from validated HTTPS origin vars:

```text
PUBLIC_API_ORIGIN
ACCESS_ADMIN_ORIGIN
```

Do not trust `X-Forwarded-Host` as an authority source. Use the URL hostname Cloudflare presents to the Worker.

API route prefixes are exactly the current native surface. Do not create an unused `/v1/downloads/*` alias; `/v1/updates/download` remains the actual download endpoint.

- [ ] **Step 4: Run firewall before Origin middleware and before route handlers**

In `src/index.ts`, production request ordering becomes:

```text
request ID/security headers
-> Host/Path firewall
-> Origin/CORS policy
-> handler authentication/authorization
```

- [ ] **Step 5: Add safe source configuration fields**

Add `PUBLIC_API_ORIGIN` to staging/production non-secret vars. The production source value remains intentionally fail-closed until the exact base domain is frozen under B7-G1; production deployment remains impossible while it is unresolved.

- [ ] **Step 6: Run GREEN + regression**

```powershell
npm run typecheck
npm test -- --run test/ingress_policy.test.ts test/security_policy.test.ts
npm test -- --run
```

Expected: all pass.

- [ ] **Step 7: Commit**

```powershell
git add services/license-update-worker/src/ingress_policy.ts services/license-update-worker/src/index.ts services/license-update-worker/src/types.ts services/license-update-worker/wrangler.jsonc services/license-update-worker/test/ingress_policy.test.ts services/license-update-worker/test/security_policy.test.ts
git diff --cached --check
git commit -m "feat: enforce worker host path authority"
```

---

## Task 3: Add independent machine Access identity and automation principal schema

**Files:**
- Create: `services/license-update-worker/migrations/0008_automation_identity.sql`
- Create: `services/license-update-worker/src/access_identity.ts`
- Create: `services/license-update-worker/src/automation_auth.ts`
- Modify: `services/license-update-worker/src/admin_login.ts`
- Modify: `services/license-update-worker/src/types.ts`
- Modify: `services/license-update-worker/src/service.ts`
- Test: `services/license-update-worker/test/automation_auth.test.ts`
- Modify: `services/license-update-worker/test/admin_login.test.ts`
- Modify: `services/license-update-worker/test/admin_login_routes.test.ts`
- Add/modify a migration test following the repository's existing migration-test pattern.

- [ ] **Step 1: RED-test migration semantics**

The migration must create:

```sql
CREATE TABLE automation_principals (
  id TEXT PRIMARY KEY,
  identity TEXT NOT NULL UNIQUE,
  display_name TEXT,
  scopes_json TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active','revoked')),
  created_at TEXT NOT NULL,
  revoked_at TEXT
);
```

It must migrate the `audit_events.actor_type` CHECK to include `automation` while preserving all existing rows and indexes.

Test an existing database with representative historical audit rows, apply `0008`, and prove row counts/content are unchanged while a new automation audit insert succeeds.

- [ ] **Step 2: Extract the reusable Access JWT verifier without behavior change**

Move the cryptographic `AccessJwtVerifier` and JWKS fetch/cache logic from `admin_login.ts` into `access_identity.ts`. Human login continues using the same strict RS256/issuer/JWKS/audience/time/jku/x5u contract.

Run existing human login tests immediately after extraction; they must remain green before machine auth is added.

- [ ] **Step 3: Write RED machine identity tests**

Prove:

```text
valid service assertion + exact automation audience + allowlisted machine identity + active automation principal -> accepted
human audience on machine route -> rejected
machine audience on human login verifier -> rejected
unknown/non-allowlisted machine identity -> rejected
revoked automation principal -> rejected
machine principal wildcard scope -> rejected by bootstrap/policy validation
wrong issuer/signature/kid/time -> rejected
missing machine configuration -> fail closed
production cannot fall back to ACCESS_AUDIENCES staging compatibility
```

- [ ] **Step 4: Implement `AuthenticatedAutomation`**

Add a distinct type:

```ts
export interface AuthenticatedAutomation {
  id: string;
  identity: string;
  scopes: Set<string>;
  authMode: "access_service";
  authenticatedAt: string;
}
```

Machine authentication reads `Cf-Access-Jwt-Assertion`, validates the automation audience/claim/allowlist, maps to `automation_principals`, and never creates an admin login code or `wcas` session.

- [ ] **Step 5: Split production Access configuration**

Add non-secret fields:

```text
ACCESS_HUMAN_AUDIENCES
ACCESS_HUMAN_IDENTITY_CLAIM
ACCESS_AUTOMATION_AUDIENCES
ACCESS_AUTOMATION_IDENTITY_CLAIM
ACCESS_AUTOMATION_IDENTITIES
```

Staging human flow may retain `ACCESS_AUDIENCES`/`ACCESS_IDENTITY_CLAIM` compatibility. Production human auth must require the new human fields; machine auth always requires automation fields.

- [ ] **Step 6: Extend audit typing**

`writeAudit()` accepts `actorType: "automation"` after migration/schema support. Machine actions record automation principal ID and safe identity metadata only; raw Access JWT/service-token credentials are never persisted.

- [ ] **Step 7: Run GREEN/full Worker verification**

```powershell
cd services/license-update-worker
npm run typecheck
npm test -- --run test/admin_login.test.ts test/admin_login_routes.test.ts test/automation_auth.test.ts
npm test -- --run
```

- [ ] **Step 8: Commit**

```powershell
git add services/license-update-worker/migrations/0008_automation_identity.sql services/license-update-worker/src/access_identity.ts services/license-update-worker/src/automation_auth.ts services/license-update-worker/src/admin_login.ts services/license-update-worker/src/types.ts services/license-update-worker/src/service.ts services/license-update-worker/test
git diff --cached --check
git commit -m "feat: separate release automation identity"
```

---

## Task 4: Split release capabilities and add machine-only automation routes

**Files:**
- Create: `services/license-update-worker/src/release_operations.ts`
- Create: `services/license-update-worker/src/automation.ts`
- Modify: `services/license-update-worker/src/admin.ts`
- Modify: `services/license-update-worker/src/index.ts`
- Modify: `services/license-update-worker/src/security_policy.ts`
- Modify: `services/license-update-worker/src/types.ts`
- Modify: `wechat_cli/admin/client.py` only for human scope semantics if needed
- Create: `wechat_cli/release/automation_client.py`
- Modify: `wechat_cli/release/publisher.py`
- Test: `services/license-update-worker/test/automation_routes.test.ts`
- Modify: `services/license-update-worker/test/admin.test.ts`
- Modify: `services/license-update-worker/test/admin_session.test.ts`
- Modify: `tests/test_release_publisher.py`
- Create: `tests/test_release_automation_client.py`

- [ ] **Step 1: RED-test scope split**

Require:

```text
human POST /v1/admin/releases requires releases:register
human PATCH /v1/admin/releases/:id requires releases:state
releases:register alone cannot PATCH state
releases:state alone cannot register
machine principal has upload/read/register only
machine route cannot accept wcas human session
admin route cannot accept machine assertion as human admin
```

- [ ] **Step 2: RED-test second-layer human-only state enforcement**

Construct an authenticated identity object with `authMode="access_service"` and even an accidental `releases:state` scope. Prove every state-changing operation still returns 403 because only `authMode="session"` is accepted for normal release-state mutation.

Also prove `legacy_break_glass` is not silently treated as normal human state authority.

- [ ] **Step 3: Extract shared release operations**

Move upload/read/register implementation details into internal functions with no authentication decisions, for example:

```ts
prepareReleasePackage(...)
registerDisabledRelease(...)
listReleaseMetadata(...)
updateReleaseStateHumanOnly(...)
```

The shared register function must always persist `enabled=0`, `paused=1`.

- [ ] **Step 4: Register machine routes only under `/v1/automation/*`**

Exact machine surface:

```text
PUT  /v1/automation/releases/:releaseId/package
POST /v1/automation/releases
GET  /v1/automation/releases
```

No PATCH/enable/pause/resume/rollout machine route exists.

- [ ] **Step 5: Add release automation Python client**

`wechat_cli/release/automation_client.py` carries only machine publication calls and accepts an injected transport/credential-header provider. It must not expose `update_release()`.

Update `publish_signed_release()` protocol typing so automation client can satisfy upload/register while state mutation remains outside publisher orchestration.

- [ ] **Step 6: Prove publisher remains state-blind**

Existing and new tests must prove:

```text
R2 readiness precedes GitHub publication
GitHub publication precedes disabled registration
publisher never calls state mutation
registration result remains enabled=false, paused=true
```

- [ ] **Step 7: Run verification**

```powershell
python -m unittest tests.test_release_publisher tests.test_release_automation_client tests.test_admin_client -v
cd services/license-update-worker
npm run typecheck
npm test -- --run test/automation_routes.test.ts test/admin.test.ts test/admin_session.test.ts
npm test -- --run
```

- [ ] **Step 8: Commit**

```powershell
git add services/license-update-worker/src services/license-update-worker/test wechat_cli/release/automation_client.py wechat_cli/release/publisher.py wechat_cli/admin/client.py tests/test_release_publisher.py tests/test_release_automation_client.py tests/test_admin_client.py
git diff --cached --check
git commit -m "feat: separate release preparation from release state"
```

---

## Task 5: Make production Secret inventory and Access ingress preflight exact

**Files:**
- Modify: `services/license-update-worker/deployment-policy.json`
- Modify: `services/license-update-worker/wrangler.jsonc`
- Modify: `scripts/deploy_worker.py`
- Modify: `services/license-update-worker/src/types.ts`
- Modify: `tests/test_worker_deployment_policy.py`
- Modify: `tests/test_worker_deployment_preflight.py`

- [ ] **Step 1: RED-test production Access/route contract**

Add cases for:

```text
production requires exactly API + Admin custom-domain routes
workers_dev must be false
PUBLIC_API_ORIGIN and ACCESS_ADMIN_ORIGIN must be exact HTTPS origins and distinct
API route host must equal PUBLIC_API_ORIGIN host
Admin route host must equal ACCESS_ADMIN_ORIGIN host
Launcher api_origin must equal PUBLIC_API_ORIGIN
human and automation Access audiences required and distinct
issuer/JWKS exact same production team-domain origin
production rejects ACCESS_AUDIENCES compatibility-only configuration
production config rejects any staging hostname
staging config rejects any production hostname once exact domain is frozen
```

- [ ] **Step 2: RED-test exact Secret derivation**

For initial production V1 selectors, expected required runtime names are exactly:

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

Explicitly assert production inventory does **not** include:

```text
GITHUB_RELEASE_READ_TOKEN
ADMIN_TOKEN_PEPPER
```

Change `Env.ADMIN_TOKEN_PEPPER` and `Env.GITHUB_RELEASE_READ_TOKEN` to optional and make their respective legacy/GitHub code paths fail closed when invoked without the value.

- [ ] **Step 3: Upgrade deployment policy schema**

Add production-specific route/Access rules to policy rather than scattering magic assumptions. The policy remains non-secret and reviewable.

- [ ] **Step 4: Keep production config non-deployable until the exact domain is frozen**

The checked-in production source configuration may carry an explicit replacement sentinel before the domain decision. Preflight must classify it as a placeholder and fail closed. **Do not invent a domain.** B7-G1 may close with this deliberate fail-closed sentinel because no production provisioning/deploy is authorized yet.

- [ ] **Step 5: Prove the unresolved symbol cannot become a deployment target**

Add a test that the symbolic/replacement production API/Admin host configuration fails production preflight before any Wrangler runner invocation. The exact `<BASE_DOMAIN>` must be supplied and approved at the start of B7-G3, before any domain/resource provisioning.

- [ ] **Step 6: Run deployment-policy verification**

```powershell
python -m unittest tests.test_worker_deployment_policy tests.test_worker_deployment_preflight -v
```

Expected: all pass; production preflight still fails against unprovisioned D1/resource IDs until B7-G3.

- [ ] **Step 7: Commit**

```powershell
git add services/license-update-worker/deployment-policy.json services/license-update-worker/wrangler.jsonc services/license-update-worker/src/types.ts scripts/deploy_worker.py tests/test_worker_deployment_policy.py tests/test_worker_deployment_preflight.py
git diff --cached --check
git commit -m "feat: define production deployment security contract"
```

---

## Task 6: Add a production deployment action definition without executing it

**Files:**
- Modify: `scripts/deploy_worker.py`
- Modify: `tests/test_worker_deployment_preflight.py`
- Create or modify: `tests/test_worker_deployment_actions.py`

- [ ] **Step 1: RED-test production deployment action safety**

Prove the function refuses unless:

```text
environment == production
production preflight succeeds
exact source/main SHA is supplied by caller and validated by the workflow layer
secrets file, if used, is a repo-external non-symlink regular file
no raw Secret content is read or printed by the wrapper
```

Prove staging deploy behavior remains unchanged.

- [ ] **Step 2: Implement `deploy_production_worker()` as a typed local capability**

It invokes exactly:

```text
wrangler deploy --env production --config <exact config>
```

only after successful preflight. It may accept the same repo-external atomic `--secrets-file` mechanism as staging. Do not add an implicit default environment.

- [ ] **Step 3: Keep invocation unexecuted under B7-G1**

Unit tests use a fake runner and inspect argv. No real Wrangler production deploy is called.

- [ ] **Step 4: Run tests**

```powershell
python -m unittest tests.test_worker_deployment_preflight tests.test_worker_deployment_actions -v
```

- [ ] **Step 5: Commit**

```powershell
git add scripts/deploy_worker.py tests/test_worker_deployment_preflight.py tests/test_worker_deployment_actions.py
git diff --cached --check
git commit -m "feat: define guarded production worker deployment"
```

---

## Task 7: Bump production lineage versions and enforce production Build ID

**Files:**
- Modify: `wechat_cli/version.py`
- Modify: `pyproject.toml`
- Modify: `tests/test_version_metadata.py`
- Modify: version-dependent product tests that assert the shared constants rather than historical fixture versions
- Modify: `npm/scripts/build.py`
- Modify: packaging tests as required

- [ ] **Step 1: RED-test new shared versions**

Require:

```text
APP_VERSION == 0.6.0
pyproject version == 0.6.0
LAUNCHER_VERSION == 0.2.0
```

Historical acceptance fixtures may continue naming 0.5.1/0.1.0 when they intentionally model older artifacts; do not blindly replace historical fixture semantics.

- [ ] **Step 2: RED-test production Build ID helper**

Introduce a helper that accepts a full 40-character lowercase source SHA and returns:

```text
prod-060-<first 12 chars>
```

Reject malformed/short/untrusted commit strings. Packaging/provenance metadata separately records the full SHA.

- [ ] **Step 3: Implement version bump and Build ID contract**

`WECHAT_CLI_BUILD_ID` explicit override remains possible for tests/local tooling, but privileged production workflow must derive and pass the deterministic Build ID from the validated main SHA rather than accept arbitrary operator text.

- [ ] **Step 4: Run focused/full Python**

```powershell
python -m unittest tests.test_version_metadata tests.test_main tests.test_windows_packaging -v
python -m unittest discover -s tests
```

- [ ] **Step 5: Commit**

```powershell
git add wechat_cli/version.py pyproject.toml npm/scripts/build.py tests
git diff --cached --check
git commit -m "feat: establish production 0.6 launcher lineage"
```

---

## Task 8: Freeze production trust-profile build contract

**Files:**
- Modify: `wechat_cli/launcher/trust_profile.py`
- Modify: `wechat_cli/launcher/config.py` only if additional environment cross-checks are needed
- Modify: `scripts/deploy_worker.py`
- Modify: `npm/scripts/build.py`
- Modify: `tests/test_launcher_config.py`
- Modify: `tests/test_worker_deployment_preflight.py`
- Modify: `tests/test_windows_packaging.py`

- [ ] **Step 1: RED-test exact Private production profile**

A valid production profile must be schema v2 and contain:

```text
distribution_profile=private_controlled
environment=production
api_base_url=exact production API HTTPS origin
expected_channel=stable
non-empty production fingerprint salt
release-key-production-01 public key
lease-key-production-01 public key
windows_publisher_policy=""
```

Reject any staging host, beta channel, schema-v1 private production profile, mutable override, loopback, or different API origin.

- [ ] **Step 2: RED-test cross-environment non-interchangeability**

Prove production Launcher/profile cannot be redirected to the existing staging API and staging profile cannot be treated as production solely by changing mutable config.

- [ ] **Step 3: Keep real production key material outside source**

B7-G1 tests use deterministic fake public keys. The real repo-external production profile is generated only after B7-G4 creates the production key identities. No private key or real fingerprint salt is committed.

- [ ] **Step 4: Run verification**

```powershell
python -m unittest tests.test_launcher_config tests.test_worker_deployment_preflight tests.test_windows_packaging -v
```

- [ ] **Step 5: Commit**

```powershell
git add wechat_cli/launcher/trust_profile.py wechat_cli/launcher/config.py scripts/deploy_worker.py npm/scripts/build.py tests/test_launcher_config.py tests/test_worker_deployment_preflight.py tests/test_windows_packaging.py
git diff --cached --check
git commit -m "feat: freeze private production trust profile contract"
```

---

## Task 9: Add GitHub Actions source definitions and workflow policy tests

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/deploy-production-worker.yml`
- Create: `.github/workflows/publish-production-release.yml`
- Create: `scripts/verify_workflow_policy.py`
- Create: `tests/test_workflow_policy.py`
- Modify: release/build CLI only where a non-interactive workflow entrypoint is required; no credential discovery logic.

- [ ] **Step 1: Write RED workflow-policy tests**

Parse workflow YAML/text and require:

```text
ci.yml has no production secret references and permissions contents:read
deploy/publish are workflow_dispatch only for privileged execution
all external uses: references are full 40-char commit SHA pins
privileged workflows have explicit minimal permissions
production-worker and production-release concurrency groups exist
no pull_request_target privileged production workflow
no release-state/enable/resume/rollout command appears in publish workflow
no production license creation command appears
release signing key reference appears only in signing job
no arbitrary third-party Action step appears after signing-key injection
```

- [ ] **Step 2: Run RED**

```powershell
python -m unittest tests.test_workflow_policy -v
```

Expected: FAIL because workflows/verifier do not exist.

- [ ] **Step 3: Implement `ci.yml`**

Use only immutable Action SHA pins and minimal permissions. Include Python, Worker, deployment, trust/version, packaging, and sensitive-scan checks. It receives no production Secret.

- [ ] **Step 4: Implement deployment workflow source**

`deploy-production-worker.yml` accepts a full SHA input, validates shape, checks out exact SHA, and runs a repository script that proves exact canonical-main identity before invoking the production deployment wrapper. Under B7-G1 it is source only and is never dispatched.

- [ ] **Step 5: Implement release-preparation workflow source**

`publish-production-release.yml` accepts full SHA/SemVer/channel/notes and encodes the required order:

```text
validate main SHA -> tests -> build -> verify -> sign -> R2 readiness -> GitHub provenance -> disabled registration -> reconcile
```

No state mutation step exists.

- [ ] **Step 6: Add canonical-main verification helper**

Create a small repository script if needed, e.g. `scripts/verify_canonical_main.py`, that takes requested SHA, checked-out SHA, and an observed canonical-main SHA supplied by the workflow, requires exact equality, and emits safe metadata only. Tests use fake SHAs and never call GitHub.

- [ ] **Step 7: Run verification**

```powershell
python -m unittest tests.test_workflow_policy -v
python scripts/verify_workflow_policy.py
```

Run the full relevant Python/Worker suites after workflow-related CLI changes.

- [ ] **Step 8: Commit**

```powershell
git add .github/workflows scripts/verify_workflow_policy.py scripts/verify_canonical_main.py tests/test_workflow_policy.py
git diff --cached --check
git commit -m "feat: define controlled production workflows"
```

---

## Task 10: B7-G1 full local audit and closure

**Files:**
- Create: `docs/superpowers/governance/2026-08-15-board-7-local-production-hardening-audit.md`
- Modify: `docs/PROJECT_STATE.md`
- Modify: `docs/deployment/authorized-update-roadmap.md`

- [ ] **Step 1: Fresh full Python**

```powershell
python -m unittest discover -s tests
```

Record exact run/skip/failure counts.

- [ ] **Step 2: Fresh Worker verification**

```powershell
cd services/license-update-worker
npm run typecheck
npm test -- --run
cd ../..
```

Record exact file/test counts.

- [ ] **Step 3: Deployment/workflow focused verification**

```powershell
python -m unittest tests.test_worker_deployment_policy tests.test_worker_deployment_preflight tests.test_worker_deployment_actions tests.test_workflow_policy -v
python scripts/verify_workflow_policy.py
```

- [ ] **Step 4: Static safety checks**

Prove source shape contains:

```text
/v1/automation/* only for upload/read/register
no machine state route
state endpoint requires releases:state + human session authMode
production required secrets exclude GITHUB_RELEASE_READ_TOKEN and ADMIN_TOKEN_PEPPER
production workers_dev=false
production host firewall exists before handlers
App/Launcher versions are 0.6.0/0.2.0
```

- [ ] **Step 5: Sensitive-value scan and Git review**

```powershell
git diff --check
git status --short
git diff --stat
git log --oneline --decorate -25
```

Scan changed non-test source/docs/workflows for private-key blocks, real credential/token/license shapes, and accidental external IDs. Synthetic test values must be clearly test-only.

- [ ] **Step 6: Write the local-hardening audit**

Record exact commits, tests, domain freeze decision, remaining production-only unknowns, and proof that B7-G1 created no external side effect.

- [ ] **Step 7: Commit audit/state locally**

```powershell
git add docs/superpowers/governance/2026-08-15-board-7-local-production-hardening-audit.md docs/PROJECT_STATE.md docs/deployment/authorized-update-roadmap.md
git diff --cached --check
git commit -m "docs: record board 7 local production hardening"
```

### Mandatory STOP — request B7-G2

Do not push, create a PR, merge, or provision production.

---

# Phase 2 — B7-G2 Source Integration Gate

This phase contains GitHub writes. Approval of B7-G2 entry does not automatically authorize all three writes; use separate sub-gates.

## Task 11: Reverify source lineage before any hosted write

- [ ] **Step 1: Read-only immutable boundary check**

Verify:

```text
Board 7 local branch/worktree clean
Board 7 HEAD descends from B7-G0 docs commit and 740ddab
frozen main still at the expected pre-integration state unless a separately recorded change exists
Board 5 evidence unchanged
no NUL cleanup occurred
full local verification evidence still current
```

- [ ] **Step 2: Produce exact source-integration impact summary**

List commits that would enter main, changed paths, and confirm no production secrets/environment values are tracked.

### Mandatory STOP — request **B7-G2A Branch Push Authorization**

## Task 12: Push Board 7 branch only

After B7-G2A approval:

- [ ] Push exactly the reviewed Board 7 branch to the configured source repository using the approved ordinary push path.
- [ ] Read back remote branch SHA and require exact equality with local HEAD.
- [ ] No tag, release, deployment, or main write.

### Mandatory STOP — request **B7-G2B PR Creation Authorization**

## Task 13: Create PR only

After B7-G2B approval:

- [ ] Create one PR from the exact Board 7 branch into canonical `main`.
- [ ] PR body records Board 6 closure ancestry, B7-G1 local verification, Private / Controlled profile, no production effects yet, and no squash/rebase requirement.
- [ ] Read back PR head/base SHAs and checks.

### Mandatory STOP — request **B7-G2C Merge Authorization**

## Task 14: Merge preserving history and verify canonical main

After B7-G2C approval:

- [ ] Merge using a history-preserving method approved for this repository; do not squash/rebase the Board 5/6/7 security lineage.
- [ ] Read back remote `main` exact SHA.
- [ ] Verify Board 7 commit ancestry is present.
- [ ] Run or read required post-merge CI checks.
- [ ] Record the resulting canonical main SHA as the only eligible source for production workflows.

### Mandatory STOP — request B7-G3

No production Cloudflare resource exists yet.

---

# Phase 3 — B7-G3 Production Infrastructure Provision Gate

**External effects:** Cloudflare production resource/domain/Access creation only. No application Worker deployment. No production Secret/private-key generation. No human/machine principal rows yet.

## Task 15: Exact production inventory preflight

**Files after approved local recording:**
- Create/update: `docs/superpowers/governance/2026-08-15-board-7-production-inventory.md`

- [ ] Resolve exact current canonical main SHA and the approved exact base domain from B7-G1.
- [ ] Read-only verify the intended Worker/D1/R2/domain names do not collide with staging or unrelated resources.
- [ ] Verify no existing production D1/R2 object with the exact target name contains data that would be overwritten.
- [ ] Record only safe resource/domain metadata; no tokens/secrets.

### Mandatory STOP if any exact resource already exists unexpectedly

Do not silently reuse or delete it.

## Task 16: Provision clean-room D1 and R2 resources

After the exact B7-G3 mutation matrix is approved:

- [ ] Create D1 `wechat-cli-license-production`.
- [ ] Create R2 `wechat-cli-releases-production`.
- [ ] Create R2 `wechat-cli-diagnostics-production`.
- [ ] Record safe resource IDs/names.
- [ ] Apply migrations `0001` through current Board 7 migration in order to production D1 only.
- [ ] Run clean-room queries proving no staging/business rows exist.

No staging data import/export-to-production operation is permitted.

## Task 17: Provision exact API/Admin ingress identities and Access applications

- [ ] Freeze the exact approved `<BASE_DOMAIN>` before the first write.
- [ ] Create/reserve the exact `api.<BASE_DOMAIN>` and `admin.<BASE_DOMAIN>` DNS/custom-host identities required for production.
- [ ] Keep production `workers_dev=false`.
- [ ] Create human Access application for `/v1/admin/*` using the approved human IdP policy.
- [ ] Create separate automation Access application for `/v1/automation/*` using Service Auth policy.
- [ ] Record exact issuer/JWKS and the two distinct audience IDs as safe metadata.
- [ ] Do not create the Access Service Token credential itself until B7-G4.
- [ ] If Cloudflare cannot attach a custom-domain route until a serving Worker script exists, do **not** deploy a placeholder Board 7 application. Record the exact hostname/DNS/Access identity and defer serving route attachment to B7-G5.

## Task 18: Read-only infrastructure reconcile

Prove:

```text
D1/R2 names/IDs distinct from staging
migrations complete
clean-room business row counts zero
API/Admin host identities exact and distinct
workers.dev production policy disabled
human/automation Access audiences distinct
no application Worker release/canary data exists
```

## Task 18A: Finalize exact non-secret production source configuration

**Files:**
- Modify: `services/license-update-worker/wrangler.jsonc`
- Modify: `services/license-update-worker/deployment-policy.json` only if exact safe identity constraints require it
- Modify: `docs/superpowers/governance/2026-08-15-board-7-production-inventory.md`

- [ ] Replace only approved non-secret production placeholders with the exact D1 ID, API/Admin hostname/origin, issuer/JWKS, and human/automation audience identities created in B7-G3.
- [ ] Do not place Service Token secrets, API tokens, release/lease private keys, or any Worker Secret value in source.
- [ ] Run production config/preflight tests with the safe exact identities. Missing B7-G4 Secret **values** remain a not-yet-provisioned condition; config validation itself must pass and required Secret **names** remain exact.
- [ ] Run full local tests and `git diff --check`.
- [ ] Commit the non-secret configuration locally.

### Mandatory STOP — request **B7-G3A Config Branch Push Authorization**

If approved, push only the reviewed config commit/branch and read back exact SHA.

### Mandatory STOP — request **B7-G3B Config PR Authorization**

If approved, create the exact config-only PR to canonical main and read back head/base.

### Mandatory STOP — request **B7-G3C Config Merge Authorization**

If approved, merge preserving history and read back exact canonical main SHA. B7-G4/B7-G5 must use this updated canonical main.

### Mandatory STOP — request B7-G4

---

# Phase 4 — B7-G4 Production Identity & Key Bootstrap Gate

Every Secret/private-key/principal/Service Token/GitHub App action is an explicit credential or external identity mutation.

## Task 19: Freeze exact production required Secret inventory from source policy

- [ ] Check out/read exact canonical main used for production.
- [ ] Run production preflight with safe declared Secret-name inventory only.
- [ ] Confirm initial selectors are all production V1 and required names exactly match the B7-G1 accepted set.
- [ ] Confirm `GITHUB_RELEASE_READ_TOKEN` and `ADMIN_TOKEN_PEPPER` are not required.

### Mandatory STOP on inventory drift

## Task 20: Generate/provision fresh production runtime material

Under the approved exact B7-G4 matrix:

- [ ] Generate fresh independent values for each required V1 runtime Secret outside source control.
- [ ] Generate fresh `lease-key-production-01` Ed25519 key material outside the repository.
- [ ] Generate fresh `release-key-production-01` Ed25519 key material outside the repository.
- [ ] Provision only runtime-required Worker Secrets to production.
- [ ] Keep release private signing key in its publisher/CI secret domain, not Worker runtime.
- [ ] Create restricted repo-external recovery/public-registry evidence with current-user/SYSTEM/Admin ACLs.
- [ ] Never print private values.

## Task 21: Bootstrap human and machine principals

- [ ] Insert one active human principal mapped to the separately approved production email identity with exactly:

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

- [ ] Insert `release-automation-production` into `automation_principals` with exactly:

```text
releases:upload
releases:read
releases:register
```

- [ ] No wildcard scope.
- [ ] No production legacy admin token/principal is created for normal operation.

## Task 22: Create automation external identities

Use separately approved external-identity mutations:

- [ ] Create one Cloudflare Access Service Token for the automation Access application.
- [ ] Record safe client identity metadata; keep client secret only in the approved production GitHub Environment/credential store.
- [ ] Create/install the dedicated GitHub App `wechat-cli-release-publisher` only on the release provenance repo with exact minimum permissions.
- [ ] Configure production GitHub Environment secrets only if the available GitHub plan/security controls satisfy the design. Otherwise STOP and select the repo-external manual signing fallback; do not downgrade to ordinary repository secrets.

## Task 23: Build the real production trust profile repo-external

Using only public key derivations plus the exact approved production API origin:

```text
schema v2
private_controlled
production
stable
release-key-production-01 public
lease-key-production-01 public
windows_publisher_policy empty
fresh production fingerprint salt
```

Verify no staging key/origin appears.

## Task 24: Read-only credential/bootstrap reconcile

Verify by names/IDs/public metadata only:

- exact Worker Secret names present;
- selectors V1;
- no normal runtime GitHub-read/legacy-admin Secret;
- human principal exact scopes;
- automation principal exact scopes;
- human and automation audiences distinct;
- automation identity allowlist exact;
- production trust profile public keys match the generated private keys without exposing them.

### Mandatory STOP — request B7-G5

---

# Phase 5 — B7-G5 Production Worker Deploy Gate

No release publication or enablement is authorized by this gate.

## Task 25: Final pre-deploy canonical-main and environment check

- [ ] Resolve exact current canonical main SHA approved for deploy.
- [ ] Verify deployment workflow requested SHA == checked-out SHA == current approved main SHA.
- [ ] Run full tests and production preflight using the real repo-external production trust profile and safe Secret-name inventory.
- [ ] Verify production D1/R2/domain/Access resources from B7-G3 exactly match source configuration.
- [ ] Verify staging resource/config readback has not acquired production hostnames/credentials.

## Task 26: Atomic production Worker deployment

After explicit B7-G5 deploy approval:

- [ ] Dispatch/execute only `deploy-production-worker.yml` for the exact reviewed main SHA.
- [ ] Use scoped Cloudflare API credential.
- [ ] Deploy with the production environment and approved atomic Secret mechanism; no raw values logged.
- [ ] Record returned Worker Version ID and full source SHA.

## Task 27: Production ingress/Access/runtime acceptance

Read-only/request acceptance proves:

```text
api host health works
api host native client routes reach handler/auth layer
api host admin/automation routes 403
admin host human routes are Access protected
admin host automation routes are Service Auth protected
admin host public client routes 403
workers.dev production ingress unavailable
unexpected/staging host privileged access fails
human login issues 30-minute wcas session
machine assertion authenticates only automation principal
D1/R2 remain production-only
```

No license/release creation is needed for this gate.

### Mandatory STOP — request B7-G6

---

# Phase 6 — B7-G6 CI/CD Automation Acceptance Gate

This gate may include a specifically approved production provenance/disabled-registration acceptance release, but no release state enablement.

## Task 28: Real CI workflow acceptance

- [ ] Verify `ci.yml` on canonical main with no production credentials exposed.
- [ ] Confirm third-party Action refs remain full SHA pins and permissions are minimal.
- [ ] Confirm privileged workflows cannot be triggered from arbitrary PR heads.

## Task 29: Real production Worker deployment workflow rehearsal

Use a no-op or same-source exact-main deployment only if explicitly approved as a production mutation; otherwise limit this subtask to workflow validation until a later necessary Worker change. Record the chosen evidence without creating an unnecessary production version merely to satisfy a checklist.

## Task 30: Prepare the first stable production `0.6.0` release through automation

This is the selected B7-G6 release-preparation acceptance target. It is a real production provenance/R2/registration mutation and therefore must be explicitly named in the B7-G6 authorization matrix. B7-G6 still does **not** authorize release enablement.

- [ ] Build the exact stable `0.6.0` update package from the approved canonical main SHA; record the full source SHA and deterministic production Build ID.
- [ ] Sign its manifest with `release-key-production-01` in the isolated signing job.
- [ ] Upload the exact package to production R2 via `/v1/automation/.../package`.
- [ ] Prove exact R2 hash/size/transport readiness while the candidate is non-selectable.
- [ ] Publish private immutable GitHub provenance/tag with `make_latest=false` using the GitHub App installation token.
- [ ] Register via `/v1/automation/releases` as the stable `0.6.0` release and prove the persisted terminal state is exactly `enabled=false`, `paused=true`.
- [ ] Reconcile manifest/package hashes, key ID, GitHub provenance IDs, R2 object identity, channel `stable`, version `0.6.0`, and full source SHA.
- [ ] Prove no machine call changed `enabled`, `paused`, or `rollout_percentage` after registration.

## Task 31: Prove machine cannot change release state

Real or safely controlled acceptance must demonstrate:

```text
automation Access assertion + state endpoint -> denied
automation principal + accidental releases:state configuration in isolated test -> still denied by authMode
no /v1/automation state endpoint exists
publisher workflow contains no state mutation
```

If a live denial probe is approved, it must have zero state change and be independently read back.

### Mandatory STOP — request B7-G7

---

# Phase 7 — B7-G7 Production Canary E2E Gate

Only internal canary production data is allowed. No real Private user issuance.

## Task 32: Build and verify production `0.6.0` installer

- [ ] Build from exact canonical main with `APP_VERSION=0.6.0`, Launcher `0.2.0`, and deterministic production Build ID.
- [ ] Embed the accepted production trust profile.
- [ ] Verify package/installer bytes, metadata, source SHA, and SHA-256.
- [ ] Record Private-profile Unknown Publisher/SmartScreen trade-off; do not claim Authenticode.
- [ ] Distribute installer only through the approved controlled channel; provide hash out-of-band where practical.

## Task 33: Create exactly one internal production canary license

After its own explicit license-creation approval:

```text
channel=beta
maximum_devices=1
purpose=internal production canary
```

The license is beta from creation and is never channel-mutated. Board 7 does not add a license-channel mutation API for acceptance. The controlled `0.6.0` installer is the baseline delivery mechanism, so this beta license does not need to select the stable `0.6.0` release row. The same license will later select `0.6.1-canary.1` when that beta candidate is human-enabled.

No second canary license and no real-user license is created.

## Task 33A: Human-enable the already registered stable `0.6.0` release

After a separate **B7-G7 stable-0.6.0 release-state authorization**:

- [ ] Fresh human Access login and satisfy recent-auth.
- [ ] Re-read the exact B7-G6 stable `0.6.0` release and require it is still `enabled=false`, `paused=true` with unchanged hashes/provenance/R2 identity.
- [ ] Human session changes only that named release to the explicitly approved enabled/unpaused state; machine identity is not used.
- [ ] Read back the exact state and audit evidence.
- [ ] Prove there are still zero stable real-user licenses, so enabling this first stable release creates no real-user exposure.

## Task 34: Initial production install/activation/offline/diagnostics acceptance

On the marked canary Windows installation:

- [ ] Install 0.6.0.
- [ ] Activate the single canary device.
- [ ] Prove second-device rejection.
- [ ] Verify production API/health/session and embedded trust.
- [ ] Verify seven-day offline lease boundaries with injected/tested time logic; do not change Windows system time.
- [ ] Verify diagnostics consent, upload, admin read/delete, retention metadata, and log redaction.

## Task 35: Prepare internal beta `0.6.1-canary.1`

This release is internal-only and beta. It must be a distinct version/artifact and must not be represented as 0.6.0.

Publication/register actions are their own explicitly enumerated release mutations. Registration remains disabled/paused until human enable approval.

## Task 36: Human-enable internal canary candidate

After a separate **B7-G7 release-state enable authorization**:

- [ ] Fresh human Access login/recent-auth.
- [ ] Set only the named internal beta release state required for canary visibility.
- [ ] Reconcile exact state.
- [ ] Machine identity is not used.

## Task 37: Real update and rollback/fault acceptance

- [ ] 0.6.0 canary selects `0.6.1-canary.1` only when license/channel are aligned.
- [ ] Download from R2; verify Ed25519 manifest + exact SHA/size.
- [ ] Apply candidate and verify health path.
- [ ] Use a controlled fault behavior to prove transactional rollback when the candidate cannot satisfy health.
- [ ] Prove candidate process tree is gone and prior 0.6.0 owns the listener after rollback.
- [ ] Prove exact failed-candidate suppression.

## Task 38: Disable canary candidate and clean disposable canary acceptance state as approved

- [ ] Human pause+disable the internal fault/canary release as required.
- [ ] Preserve immutable GitHub provenance and R2 bytes.
- [ ] Preserve the one production canary license/device if it remains the designated long-lived operational canary; otherwise cleanup order is device unbind then license revoke under explicit approval.

### Mandatory STOP — request B7-G8

No real Private customer/user issuance before this STOP.

---

# Phase 8 — B7-G8 First Controlled Release & Recovery Gate

## Task 39: Accept human release-state operations and controlled rollout

Use only human `wcas` sessions with recent-auth for:

```text
enable
pause
disable
rollout changes
```

Prove machine denial remains intact.

For later stable releases, exercise a safe rollout-state sequence as population permits. The default future policy is 25 -> 50 -> 100; do not invent percentage evidence if the real population is still too small.

## Task 40: Worker last-known-good recovery drill

Selected rollback method:

```text
redeploy exact recorded last-known-good canonical main commit through deploy-production-worker.yml
```

- [x] Record current accepted Worker Version ID/source/config identity.
- [x] Determine that a harmless newer Worker version is **not technically necessary**; do not create a same-functionality mutation solely for ceremony.
- [x] Reconcile the exact LKG redeploy primitive to canonical-main-only workflow policy; no redundant dispatch is performed when live Worker/deploy source is byte-equivalent to current canonical implementation.
- [x] Run full production preflight.
- [x] Read back the existing accepted LKG Worker Version ID and prove no newer deployment was introduced.
- [x] Prove health/ingress/Access behavior equals the last-known-good source.

Cloudflare provider-side version rollback is not the standard primitive.

## Task 41: Bad-release propagation and forward-fix runbook acceptance

Prove/read through a named controlled candidate:

```text
pause + disable stops new selection
GitHub provenance retained
R2 bytes retained
already committed healthy version is not force-downgraded
forward-fix next 0.6.x is the post-commit remediation path
```

## Task 42: Credential emergency-revoke runbook acceptance

Document production-specific consequences for each secret/key class. Do not actually retire V1 merely for the drill. Any real revoke/rotation mutation requires a separate exact credential matrix.

## Task 43: First real Private user issuance gate

Only after B7-G7 canary PASS and B7-G8 recovery controls PASS:

### Mandatory STOP — request exact real-user license issuance authorization

If approved, create only the explicitly approved number/channel/device-limit of real Private production licenses. Do not batch-create an unspecified pool.

Task 43 accepted evidence: exactly one stable Private production license was created under separate explicit authorization (`count=1`, `maximum_devices=1`, channel `stable`), with zero stable device bindings and no third-party key handoff or activation. Safe governance evidence is retained in `docs/superpowers/governance/2026-08-17-board-7-recovery-controlled-release-prelicense-acceptance.md`; complete key material remains only in ACL-hardened repo-external storage.

### Mandatory STOP — request B7-G9

---

# Phase 9 — B7-G9 Final Production Closure

This phase is read-only/local docs unless a defect forces a separately authorized earlier-gate repair.

## Task 44: Fresh full verification

Run fresh:

```powershell
python -m unittest discover -s tests
cd services/license-update-worker
npm run typecheck
npm test -- --run
cd ../..
python -m unittest tests.test_worker_deployment_policy tests.test_worker_deployment_preflight tests.test_worker_deployment_actions tests.test_workflow_policy -v
python scripts/verify_workflow_policy.py
git diff --check
git status --short
```

Record actual counts.

## Task 45: Fresh production read-only reconcile

Verify without mutation:

```text
exact production Worker Version ID and canonical main SHA
API/Admin host isolation
workers.dev unavailable
human/automation Access audiences and principal scopes
machine cannot change state
D1/R2 identities and clean-room provenance
current/readable Secret selectors by safe metadata
lease/release key IDs and public trust
release states/provenance/R2 hashes
canary license/device state
real Private issuance count/state if authorized
no staging rows/credentials crossed into production
production diagnostics retention/log-redaction evidence
last-known-good recovery record
```

## Task 46: Reverify immutable historical boundaries

Read-only prove:

- Board 5 evidence unchanged;
- Board 6 closure ancestry retained;
- canonical main contains the intended history-preserving Board 7 lineage;
- no historical `NUL` was committed/deleted by Board 7;
- no Public/Formal Authenticode action occurred.

## Task 47: Sensitive-value scan

Scan tracked source/docs/workflows for complete production credential/private-key/license/device/session shapes. Zero real secret material is permitted.

## Task 48: Write final Board 7 / seven-board acceptance report

Create:

`docs/deployment/2026-08-15-board-7-production-automation-controlled-launch-report.md`

Required sections:

```text
scope and authorization matrix
source lineage/main integration
production topology
clean-room data evidence
human/machine identity and scope evidence
Secret/key inventory and independence
CI/CD workflow acceptance
production Worker deployment evidence
0.6.0 / Launcher 0.2.0 installer evidence
0.6.1-canary.1 update/rollback evidence
release-state human-only evidence
controlled user issuance evidence
rollback/recovery evidence
diagnostics/privacy evidence
deferred Authenticode
explicit actions not performed
final program state
```

## Task 49: Update canonical project state and roadmap

Only after every Board 7 mandatory exit condition passes:

```text
Board 7 accepted complete
Authorized Update Program accepted complete
```

If any mandatory production/canary/automation/recovery condition remains incomplete, keep Board 7 in progress and name the exact blocker. Deferred commercial Authenticode is not a blocker for `private_controlled`.

## Task 50: Local closure commit

```powershell
git add docs/PROJECT_STATE.md docs/deployment/authorized-update-roadmap.md docs/deployment/2026-08-15-board-7-production-automation-controlled-launch-report.md docs/superpowers/plans/2026-08-15-board-7-production-automation-controlled-launch.md
git diff --cached --check
git commit -m "docs: complete board 7 production controlled launch"
```

No push/merge is implied by the closure docs commit unless separately authorized.

### Final Mandatory STOP

Present final Board 7 evidence. Do not activate Public / Formal Distribution, buy code signing, perform cleanup, or expand production without a new program/design authorization.

---

# Plan-to-design coverage matrix

| Design requirement | Plan task(s) |
|---|---|
| Production Host/Path firewall | 2 |
| Production Access preflight | 5, 25–27 |
| Human/machine identity split | 3, 21–24, 27 |
| Machine-specific automation routes | 4, 30–31 |
| Release scope split | 4 |
| Human-only release-state enforcement | 4, 31, 36, 39 |
| Clean-room production DB | 15–18 |
| Exact post-provision production config on canonical main | 18A |
| Fresh production V1 secrets/keys | 5, 19–24 |
| No runtime GitHub read/legacy admin Secret | 5, 19, 24 |
| GitHub App publisher | 22, 30 |
| Cloudflare scoped deploy credential | 9, 22, 26 |
| Workflow SHA pins/minimal permissions | 9, 28 |
| Canonical-main-only deploy | 9, 11–14, 25–26 |
| Release signing key isolation | 9, 22, 30 |
| Lease key isolation | 20, 23–24 |
| App 0.6.0 / Launcher 0.2.0 | 7, 32 |
| Private production trust profile | 8, 23, 32 |
| Private first-install trade-off | 32 |
| R2 runtime + GitHub provenance | 4, 30, 35 |
| First stable 0.6.0 automation register + human enable | 30, 33A |
| Single beta canary license without channel mutation | 33–38 |
| Internal 0.6.1-canary.1 update | 35–38 |
| Controlled rollout | 39 |
| Worker rollback by LKG main redeploy | 40 |
| Release pause/disable + forward-fix | 41 |
| Diagnostics/log redaction | 34, 45 |
| Backup/recovery evidence | 40–42, 45, 48 |
| Key rotation/emergency revoke handoff | 42 |
| Source push/PR/merge sub-gates | 11–14 |
| Final closure | 44–50 |
| Deferred Public/Formal Authenticode | global invariants, 46, 48–50 |

# First implementation authorization

After the B7-G0 design/docs commit, the next permissible authorization is exactly:

> **B7-G1 Local Production Hardening Gate** — authorize creation of the fresh Board 7 implementation worktree and local TDD/source changes for production Host/Path firewall, production Access preflight, human/machine identity separation, automation principal/audit schema, release scope split, human-only release-state enforcement, production Secret-inventory derivation, guarded production deployment capability definitions, App `0.6.0` / Launcher `0.2.0` / Build-ID logic, production trust-profile contract, and GitHub workflow source definitions/tests. No Cloudflare/GitHub external mutation, no production resource/Secret/key/principal creation, no push/PR/merge, no release publication, no production license, and no production deploy.
