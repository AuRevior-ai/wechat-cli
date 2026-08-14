# Board 6 Security & Delivery Preparation Implementation Plan

> **APPROVED IMPLEMENTATION PLAN — B6-G0 through B6-G5 complete; B6-G6 Phase A provider-neutral readiness repair/research complete; real provider procurement/signing remains separately gated; every later gate remains independently authorized.**
>
> Approved seed content SHA-256: `9faa73f733fa714a49accc91b532471e097ea28f8224d6317908ad57a0261b89`. The exact approved seed remains retained, untracked and untouched, in the Board 5 evidence worktree. This tracked canonical copy originates from that exact seed and contains only the explicitly authorized B6-G0 governance/status corrections plus the approved lifecycle and Access/JWT/break-glass revisions.
>
> **For agentic workers:** REQUIRED SUB-SKILL after gate approval: use `superpowers:executing-plans` or `superpowers:subagent-driven-development` task-by-task. This document does not authorize any pending gate by itself.

**Goal:** Integrate the Board 5 product lineage onto a fresh Board 6 branch and harden update trust, administrator security, Windows delivery integrity, diagnostics/privacy, key rotation, and staging/production boundaries to a production-ready design while keeping production deployment and Board 7 separate.

**Architecture:** Start from frozen main, selectively replay only product-relevant Board 5 changes, then implement security controls in four independent domains. Local TDD and schema design come before any staging mutation. Staging infrastructure, staging behavior, real code signing, key-rotation drill, and closure are five separate post-local gates; production provisioning/deployment remains Board 7.

**Tech Stack:** Python 3.12, PyInstaller, pywebview/WebView2, Windows DPAPI/WinTrust or PowerShell Authenticode verification, TypeScript, Hono, Cloudflare Workers/D1/R2/Access, GitHub Releases, Ed25519, SHA-256, Vitest, unittest.

**Design source:** `docs/superpowers/specs/2026-08-12-board-6-security-delivery-preparation-design.md`

**Current execution status (2026-08-14):** Board 5 accepted-complete evidence remains frozen at `67d3dec0fd1c4a02c87be1ab79c4f78ea63f49d6`; frozen main remains `a579a25cb7f16e6fdf88d618252b4a5cbffef53d`. Board 6 runs on `board6/security-delivery-preparation`. B6-G0 source integration is complete through `c1d045895a044dbb4c9998a787c77775654074fa`; B6-G1 Update Trust Local Gate is complete through `bdc98afc0d945c4c86f1e3b21686d2fe798ccdd1`; B6-G2 Admin & Data Security Local Gate is complete through `e0c91df`; B6-G3 Windows Integrity Local Gate is complete through implementation HEAD `1a074472360907be10d336729c3c28e0584b00f3`, with pre-staging security audit `d73cf3f`. B6-G3 local commits are `4b7fbfe` (exact pywebview pin + pre-load adapter), `a1dc6bd` (embedded Launcher deployment trust profile), `9b54710` (Authenticode/runtime/signing-provider boundary), `8d7493e` (production-capable signed installer target), and `1a07447` (fail-closed Worker deployment preflight). Fresh B6-G3 verification passed Python 607 run / 2 expected skips / 0 failures, Worker typecheck, Vitest 13 files / 89 tests, implementation diff/static trust-boundary checks, and targeted non-test sensitive-shape scanning. No Access app/policy, staging migration/deploy, real Secret mutation, credential rotation, real code-signing identity use, release action, cloud/production mutation, push, or merge occurred. B6-G4 Staging Infrastructure Gate is complete. The dedicated `wechat-cli-releases-staging` R2 bucket is live; D1 migrations `0004`–`0007` are applied with none pending; all seven Board 6 `_V1` staging Secret names are provisioned while legacy compatibility names remain; the Access application protects `wechat-cli-admin-staging.aurevior-devspace.com/v1/admin/login/start`; exact staging issuer/JWKS/AUD/email-identity/admin-origin vars are deployed; and Worker Version ID `14a19ea3-5a96-408b-a4e3-0a8d8e4ebe2c` is live on workers.dev plus the admin custom domain. B6-G4 local commits are `14db869`, `332c41a`, and `86da5a5`; closure evidence is `docs/superpowers/governance/2026-08-14-board-6-staging-infrastructure-gate.md`. Fresh pre-deploy verification passed Python 612 run / 2 expected skips / 0 failures, Worker typecheck, Vitest 89/89, deployment tests 27/27 and Wrangler dry-run. Post-deploy reconcile confirms both health origins 200/staging, Access login start 302 on the custom domain and 403 on workers.dev, all historical release rows unchanged, and `admin_principals` / `admin_sessions` still 0 at B6-G4 closure; B6-G5 later provisioned one scoped principal and short-lived sessions for acceptance, then revoked the G5 principal/sessions at cleanup with zero active sessions remaining. Production D1 remains a replacement placeholder and production routes remain intentionally empty, so production remains fail closed. **B6-G5 Staging Behavior Acceptance is accepted complete with evidence `docs/superpowers/governance/2026-08-14-board-6-staging-behavior-acceptance.md`; current staging Worker Version after G5 repairs is `6f2aad56-12cb-4d8e-8af5-9dceefbe1a49`. B6-G6 Phase A provider-neutral readiness repair/research is complete locally at `9f4ad0f` + `e9cb67b`, with provider decision draft `docs/superpowers/governance/2026-08-14-board-6-code-signing-provider-decision.md`; fresh Phase A verification passed Python 630 run / 2 expected skips / 0 failures, Worker typecheck, Vitest 92/92, signing-focused 103/103 and a real read-only Microsoft-signed system probe. Real provider selection/procurement, payment/application, identity verification, key provisioning, concrete signer adapter, staging publisher-policy mutation and actual signing remain pending separate explicit user approval; B6-G7/B6-G8 are not entered and Board 7 remains unstarted.** The completed-gate task checklists below remain the approved execution map; authoritative completion evidence is the Board 6 commit lineage, gate verification, pre-staging audit, and canonical project/roadmap state.

---

## 0. Execution invariants

These rules apply to every future task in this plan.

1. Do not implement any task until the corresponding authorization gate is explicitly approved.
2. Do not modify frozen main directly. Board 6 work starts from a fresh managed worktree based exactly on `a579a25cb7f16e6fdf88d618252b4a5cbffef53d`.
3. Do not merge the Board 5 branch wholesale.
4. Do not rewrite Board 5 evidence/history.
5. Do not push, merge to main, create production resources, mutate production, buy/apply for a code-signing identity, rotate a real credential, publish a release, or enable a release unless a later explicit gate says so.
6. Every implementation task follows RED -> GREEN -> focused tests -> full relevant tests -> `git diff --check` -> commit.
7. Every cloud/staging task begins with exact read-only preflight and ends with read-only reconcile.
8. Secrets are never printed, committed, copied into docs, or embedded in test fixtures.
9. Board 7 remains unstarted when Board 6 closes.

---

# Phase 0 — B6-G0 Source Integration Gate

## Task 0.1: Create the isolated Board 6 integration lineage

**Gate:** **B6-G0 Source Integration Gate**

**Files:** none initially; Git/worktree operation only.

- [ ] **Step 1: Verify frozen inputs read-only**

Run from the existing Board 5 workspace:

```powershell
git status --short
git rev-parse HEAD
git -C D:\use_as_desktop\Wechat__CLI\wechat-cli rev-parse HEAD
git -C D:\use_as_desktop\Wechat__CLI\wechat-cli status --short
```

Expected:

```text
Board 5 HEAD = 67d3dec0fd1c4a02c87be1ab79c4f78ea63f49d6
Board 5 worktree = clean
main HEAD = a579a25cb7f16e6fdf88d618252b4a5cbffef53d
main status = only the intentionally preserved ?? NUL
```

If any value differs, STOP before creating a worktree.

- [ ] **Step 2: Create a fresh managed worktree from frozen main**

Use DevSpace `open_workspace(mode="worktree", baseRef="a579a25cb7f16e6fdf88d618252b4a5cbffef53d")` on the main repository path. Name the branch `board6/security-delivery-preparation` if the DevSpace implementation allows explicit naming; otherwise record the generated branch and do not rename it without approval.

Expected: new worktree HEAD exactly `a579a25...`, clean.

- [ ] **Step 3: Record the source integration provenance matrix**

Create:

`docs/superpowers/governance/2026-08-12-board-6-source-integration-provenance.md`

Required entries:

```text
84b8a99 -> direct product candidate: 0.5.1/update-only packaging baseline
56d065e -> direct product candidate: Windows file URL normalization
706bcbe -> direct product candidate: before-load deadlock repair
a771ab4 -> direct product candidate: identify Launcher update downloads
8a1fdb0 -> temporary product candidate during GitHub->R2 migration
c4d44ee -> safe upstream status diagnostics
fc667cf -> safe upstream failure logging
29aba6b -> process-tree/port-release repair

ad753f6 -> do not wholesale integrate; Board 5 acceptance helper
538ae3a -> do not wholesale integrate; Board 5 acceptance tooling
52e07b8 -> do not wholesale integrate; Board 5 probe
28415ca -> selectively port generic bootstrap-only behavior; remove board5_common dependency
```

The document must contain file-level rationale, not only commit labels.

- [ ] **Step 4: Commit provenance only**

```powershell
git add docs/superpowers/governance/2026-08-12-board-6-source-integration-provenance.md
git diff --cached --check
git commit -m "docs: define board 6 source integration provenance"
```

No push.

---

## Task 0.2: Selectively integrate the audited product lineage

**Gate:** B6-G0 continues.

**Files:** product/test files touched by the selected commits. No Board 5 sandbox/probe scripts are to become production dependencies.

- [ ] **Step 1: Replay `84b8a99` and product fixes one at a time**

Preferred sequence:

```text
84b8a99
56d065e
706bcbe
a771ab4
8a1fdb0
c4d44ee
fc667cf
29aba6b
```

After each replay/cherry-pick, inspect the exact diff and run the commit’s focused tests. Do not continue after a conflict until the conflict is reviewed against the Board 5 accepted behavior.

- [ ] **Step 2: Reject acceptance-only imports**

Run:

```powershell
rg -n "board5_common|board5_prepare|board5_update_download_probe|board5_offline_acceptance" scripts wechat_cli npm services
```

Expected: production paths may still reveal the known `package_windows_app.py -> board5_common` dependency before Task 1, but no new runtime/Worker dependency on Board 5 acceptance scripts is introduced.

- [ ] **Step 3: Run integrated-baseline verification**

```powershell
python -m unittest discover -s tests
cd services/license-update-worker
npm run typecheck
npm test -- --run
cd ../..
git diff --check
git status --short
```

Expected: zero failures; only known platform skips.

- [ ] **Step 4: Commit the integrated product baseline**

Use one or more provenance-preserving local commits. If cherry-picks preserve the original hashes, no squash is required. If selective ports are needed, commit with a message identifying the source commit(s), for example:

```text
chore: integrate board 5 product baseline for board 6
```

No merge to main and no push.

---

# Phase 1 — Local integration cleanup and A-domain trust

## Task 1: Extract generic packaging output-boundary utility

**Design:** D1

**Gate:** **B6-G0**

**Files:**
- Create: `scripts/packaging_paths.py`
- Modify: `scripts/package_windows_app.py`
- Modify: `tests/test_windows_packaging.py`
- Modify or retain only if required for historical Board 5 tests in the Board 6 branch: `scripts/board5_common.py`
- Test: `tests/test_packaging_paths.py`

- [ ] **Step 1: Write RED tests for generic path policy**

Create `tests/test_packaging_paths.py` with cases equivalent to:

```python
from pathlib import Path
import tempfile
import unittest

from scripts.packaging_paths import PackagingPathError, assert_outside_repository

class PackagingPathTests(unittest.TestCase):
    def test_repository_root_is_rejected(self):
        with self.assertRaises(PackagingPathError):
            assert_outside_repository(REPOSITORY_ROOT, repository_root=REPOSITORY_ROOT)

    def test_repository_child_is_rejected(self):
        with self.assertRaises(PackagingPathError):
            assert_outside_repository(REPOSITORY_ROOT / "dist", repository_root=REPOSITORY_ROOT)

    def test_external_path_is_allowed(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "artifacts"
            self.assertEqual(
                target.resolve(),
                assert_outside_repository(target, repository_root=REPOSITORY_ROOT),
            )
```

Use the repository’s existing test helper to resolve `REPOSITORY_ROOT`; do not hard-code a developer-specific path.

- [ ] **Step 2: Run RED**

```powershell
python -m unittest tests.test_packaging_paths -v
```

Expected: FAIL because `scripts.packaging_paths` does not exist.

- [ ] **Step 3: Implement the generic utility**

Create `scripts/packaging_paths.py` with one responsibility:

```python
class PackagingPathError(ValueError):
    pass


def assert_outside_repository(path: Path, *, repository_root: Path) -> Path:
    resolved = Path(path).resolve(strict=False)
    root = Path(repository_root).resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError:
        return resolved
    raise PackagingPathError("packaging output must be outside the repository")
```

Preserve or tighten the Board 5 behavior around symlinks/reparse points if existing tests prove stricter semantics; the final implementation must follow the stronger existing contract.

- [ ] **Step 4: Switch production package script to generic utility**

`package_windows_app.py` must import only from `scripts.packaging_paths` (with the same direct-execution fallback pattern if needed). Remove the production import from `board5_common`.

- [ ] **Step 5: Run focused tests**

```powershell
python -m unittest tests.test_packaging_paths tests.test_windows_packaging tests.test_board5_common -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add scripts/packaging_paths.py scripts/package_windows_app.py tests/test_packaging_paths.py tests/test_windows_packaging.py scripts/board5_common.py tests/test_board5_common.py
git diff --cached --check
git commit -m "refactor: separate packaging path safety from board 5"
```

---

## Task 2: Make update channel server-authoritative

**Design:** A1

**Gate:** **B6-G1 Update Trust Local Gate**

**Files:**
- Modify: `services/license-update-worker/src/updates.ts`
- Modify: `services/license-update-worker/test/updates.test.ts`
- Modify if error enum/documentation is needed: `wechat_cli/update/errors.py`
- Modify: `tests/test_update_client.py` only if client error mapping changes.

- [ ] **Step 1: Add RED Worker tests**

Add tests proving:

```text
stable license + stable request -> normal selection
stable license + beta request -> 409 UPDATE_CHANNEL_MISMATCH, zero ticket insert
beta license + stable request -> same failure
selection uses authenticated license channel, not a mutable request variable
```

The test must inspect D1 calls or route result sufficiently to prove no download ticket is created on mismatch.

- [ ] **Step 2: Run RED**

```powershell
cd services/license-update-worker
npm test -- --run test/updates.test.ts
```

Expected: mismatch tests FAIL under current behavior.

- [ ] **Step 3: Implement the boundary**

In `/v1/updates/check`, after parsing request channel:

```ts
const requestedChannel = validTargetValue(request, "channel", ["stable", "beta"]);
const effectiveChannel = authenticated.license.release_channel;
if (requestedChannel !== effectiveChannel) {
  throw new ApiError(
    "UPDATE_CHANNEL_MISMATCH",
    "更新通道与许可证授权不匹配。",
    { status: 409, retryable: false },
  );
}
```

Pass `effectiveChannel` into `selectRelease()` and audit/response fields.

- [ ] **Step 4: Run focused Worker tests and typecheck**

```powershell
npm run typecheck
npm test -- --run test/updates.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add services/license-update-worker/src/updates.ts services/license-update-worker/test/updates.test.ts wechat_cli/update/errors.py tests/test_update_client.py
git diff --cached --check
git commit -m "fix: enforce licensed update channel"
```

---

## Task 3: Introduce exact failed-release identity with legacy compatibility

**Design:** A2

**Gate:** B6-G1 continues.

**Files:**
- Modify: `wechat_cli/update/models.py`
- Modify: `wechat_cli/update/client.py`
- Modify: `wechat_cli/update/transaction.py` or the actual failed-registry owner identified by current code
- Modify: `wechat_cli/launcher/cli.py`
- Modify: `services/license-update-worker/src/updates.ts`
- Modify: `services/license-update-worker/test/updates.test.ts`
- Modify: relevant Python tests for failed registry/client.

- [ ] **Step 1: Freeze request schema in tests**

New request shape:

```json
{
  "failed_releases": [
    {
      "version": "0.5.2",
      "manifest_sha256": "64-lowercase-hex"
    }
  ],
  "failed_versions": ["0.5.1"]
}
```

During migration both fields are allowed. New Launcher sends `failed_releases`; `failed_versions` is retained only for compatibility testing of old clients.

- [ ] **Step 2: RED tests**

Worker cases:

```text
exact version+manifest match -> suppressed
same version + different manifest -> not suppressed by failed_releases
legacy failed_versions version -> suppressed for old client
invalid SHA -> 400
more than bounded entries -> 400
```

Python cases:

```text
failed registry serializes exact pair
client sends exact pairs
legacy response/client compatibility remains intact
```

- [ ] **Step 3: Run RED**

```powershell
python -m unittest tests.test_update_client tests.test_update_transaction -v
cd services/license-update-worker
npm test -- --run test/updates.test.ts
```

Expected: new exact-pair cases FAIL.

- [ ] **Step 4: Implement bounded exact-pair parser**

Worker internal type:

```ts
interface FailedReleaseIdentity {
  version: string;
  manifest_sha256: string;
}
```

Normalize SHA to lowercase, bound list size, validate semver + 64 hex. `selectRelease()` skips when either:

```text
legacy failedVersions contains release.version
OR
failedReleases contains (release.version, release.manifest_sha256)
```

New clients should send an empty legacy list after migration.

- [ ] **Step 5: Enforce release version immutability at registration**

Before inserting a Worker release, query same `channel + version`. If an existing row has a different `manifest_sha256`, return a conflict such as `RELEASE_VERSION_IMMUTABLE`. Exact idempotent replay remains supported through existing nonce/idempotency semantics.

- [ ] **Step 6: Run focused tests and full A-domain regression**

```powershell
python -m unittest tests.test_update_client tests.test_update_transaction tests.test_update_models -v
cd services/license-update-worker
npm run typecheck
npm test -- --run
```

- [ ] **Step 7: Commit**

```powershell
git add wechat_cli/update wechat_cli/launcher/cli.py tests services/license-update-worker/src/updates.ts services/license-update-worker/src/admin.ts services/license-update-worker/test
git diff --cached --check
git commit -m "feat: suppress exact failed update manifests"
```

---

# Phase 2 — Local R2 distribution and B-domain security

## Task 4: Add dual release-distribution model and private R2 package backend

**Design:** A3, A4, B1

**Gate:** B6-G1 continues; this task is local-only and MUST NOT create an R2 bucket or deploy Worker changes.

**Files:**
- Create: `services/license-update-worker/migrations/0004_release_distribution.sql`
- Modify: `services/license-update-worker/src/types.ts`
- Create: `services/license-update-worker/src/distribution.ts`
- Modify: `services/license-update-worker/src/updates.ts`
- Modify: `services/license-update-worker/src/admin.ts`
- Modify: `services/license-update-worker/wrangler.jsonc` only with safe binding declarations that do not provision resources
- Modify: `wechat_cli/admin/client.py`
- Modify: `wechat_cli/release/publisher.py`
- Modify: `wechat_cli/release/builder.py` if registration payload changes
- Create/modify Worker tests and Python publisher/admin tests.

- [ ] **Step 1: Define migration RED expectations**

`releases` gains non-destructive distribution fields, for example:

```sql
ALTER TABLE releases ADD COLUMN distribution_backend TEXT NOT NULL DEFAULT 'github'
  CHECK (distribution_backend IN ('github', 'r2'));
ALTER TABLE releases ADD COLUMN distribution_object_key TEXT;
```

Do not remove existing GitHub columns; they remain provenance fields and migration compatibility.

- [ ] **Step 2: Add RED tests for R2 backend and lifecycle ordering**

Prove:

```text
existing github row still downloads through legacy adapter
r2 row reads exact object key from RELEASES binding
r2 object missing -> 404/502 fail closed
R2 bytes/size metadata mismatch -> release state invalid
production environment + github backend -> rejected by config/policy
r2 download makes zero GitHub fetches
publisher/orchestrator cannot publish immutable GitHub provenance before R2 transport readiness succeeds
R2 readiness failure leaves GitHub release as Draft/unpublished and leaves candidate non-selectable/disabled
release enable is never coupled to readiness or provenance publication
```

- [ ] **Step 3: Implement `distribution.ts` abstraction**

Interface shape:

```ts
export interface DistributionRequest {
  backend: "github" | "r2";
  objectKey?: string;
  githubRepository?: string;
  githubAssetId?: string;
  range?: string;
  ifRange?: string;
}

export async function fetchReleasePackage(
  env: Env,
  request: DistributionRequest,
): Promise<Response> { /* backend dispatch */ }
```

The GitHub adapter keeps the Board 5 redirect protections for legacy rows. The R2 adapter performs no outbound fetch.

- [ ] **Step 4: Add staged package upload API model locally**

Add an admin route that accepts a package stream only for a pre-authorized release-preparation operation, validates declared hash/size, stores to `RELEASES`, and returns safe object metadata. It must require a dedicated scope such as `releases:upload`, idempotency nonce, content-length bound, and never accept an arbitrary object key from the caller.

Recommended opaque object key generated server-side:

```text
releases/<channel>/<release_id>/<package_sha256>.zip
```

The upload route is local code only until B6-G4/G5.

- [ ] **Step 5: Update registration payload**

For new R2 rows, Worker registration records:

```text
distribution_backend = r2
distribution_object_key = server-issued key
GitHub repository/release/asset metadata = provenance metadata
package hash/size = signed manifest values
```

Registration/finalization must refuse R2 enablement if the object does not exist or object metadata/hash/size does not match. Any preparation row used before immutable provenance publication must be structurally non-selectable and non-enableable.

- [ ] **Step 6: Update publisher sequencing locally**

Do not publish anything. Refactor publisher orchestration so future lifecycle is ordered exactly as:

```text
build/sign immutable bytes
-> GitHub Draft upload/inspect only
-> R2 upload + exact hash/size + target transport-readiness verification
-> publish immutable GitHub provenance/tag with make_latest=false
-> reconcile published provenance against the already-readied R2 object
-> Worker register/finalize disabled/paused
-> separate independently authorized enable
```

The orchestration API must make “R2 transport ready” an explicit prerequisite for GitHub publication. A failed R2 readiness check must not invoke the GitHub publish action. All external clients are dependency-injected so tests use fakes.

- [ ] **Step 7: Run tests**

```powershell
python -m unittest tests.test_release_publisher tests.test_admin_client tests.test_release_builder -v
cd services/license-update-worker
npm run typecheck
npm test -- --run
```

- [ ] **Step 8: Commit**

```powershell
git add services/license-update-worker/migrations/0004_release_distribution.sql services/license-update-worker/src services/license-update-worker/test services/license-update-worker/wrangler.jsonc wechat_cli/admin wechat_cli/release tests
git diff --cached --check
git commit -m "feat: add private r2 release distribution backend"
```

### B6-G1 completion evidence — 2026-08-12

B6-G1 was separately authorized and completed locally. The plan checkboxes above are retained as the approved execution map rather than rewritten after execution; the authoritative evidence is:

```text
Task 2: a23b6ff fix: enforce licensed update channel
Task 3: 988a504 feat: suppress exact failed update manifests
Task 4: bdc98af feat: add private r2 release distribution backend

Fresh gate verification:
Python: 510 run / 2 expected skips / 0 failures
Worker typecheck: PASS
Vitest: 5 files / 40 tests PASS
git diff e25f2ae..bdc98af --check: PASS
non-test sensitive-shape scan: 0 target matches
Board 6 worktree after implementation commits: clean
```

Task 2 makes the authenticated license channel authoritative and rejects client-channel mismatch before release selection/ticket creation. Task 3 adds exact `(version, manifest_sha256)` failure identity while retaining bounded legacy `failed_versions` compatibility and rejects channel/version manifest replacement. Task 4 adds the local R2 distribution schema/backend, exact R2 package preparation/readiness checks, byte-range support, production rejection of the legacy GitHub runtime backend, and the corrected future lifecycle `Draft inspection -> R2 readiness -> immutable GitHub provenance -> disabled/paused registration -> independently authorized enable`.

This local gate created no R2 bucket, applied no staging migration, deployed no Worker, changed no real Secret/credential, published/registered/enabled no real release, signed no real artifact, and performed no push or merge.

---

## Task 5: Add short-lived administrator sessions and Access-authenticated login abstraction

**Design:** B2

**Gate:** **B6-G2 Admin & Data Security Local Gate**

**Files:**
- Create: `services/license-update-worker/migrations/0005_admin_sessions.sql`
- Create: `services/license-update-worker/src/admin_login.ts`
- Modify: `services/license-update-worker/src/auth.ts`
- Modify: `services/license-update-worker/src/admin.ts`
- Modify: `services/license-update-worker/src/index.ts`
- Modify: `services/license-update-worker/src/types.ts`
- Create: `wechat_cli/admin/session.py`
- Modify: `wechat_cli/admin/config.py`
- Modify: `wechat_cli/admin/client.py`
- Modify: `wechat_cli/admin/cli.py`
- Add Worker and Python tests.

- [ ] **Step 1: Define non-secret schema**

Migration tables:

```sql
CREATE TABLE admin_principals (
  id TEXT PRIMARY KEY,
  identity TEXT NOT NULL UNIQUE,
  display_name TEXT,
  scopes_json TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active','revoked')),
  created_at TEXT NOT NULL,
  revoked_at TEXT
);

CREATE TABLE admin_login_codes (
  id TEXT PRIMARY KEY,
  principal_id TEXT NOT NULL REFERENCES admin_principals(id),
  challenge_digest TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  used_at TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE admin_sessions (
  id TEXT PRIMARY KEY,
  token_id TEXT NOT NULL UNIQUE,
  token_digest TEXT NOT NULL,
  principal_id TEXT NOT NULL REFERENCES admin_principals(id),
  scopes_json TEXT NOT NULL,
  authenticated_at TEXT NOT NULL,
  expires_at TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active','revoked')),
  created_at TEXT NOT NULL,
  last_used_at TEXT,
  revoked_at TEXT
);
```

Legacy `admin_tokens` remains in schema for local migration/e2e evidence and possible explicitly authorized temporary recovery use; it is not dropped. Production policy defaults legacy admin authentication to disabled on every admin route.

- [ ] **Step 2: RED tests for Access JWT cryptographic identity verification**

Do not make live Cloudflare calls in unit tests. Define an injected `AdminIdentityVerifier` whose production implementation verifies Cloudflare Access JWT assertions cryptographically. The verifier contract must:

```text
accept identity only from the exact configured Access-protected ingress/header
never trust identity/email/issuer/audience from request body or query
use an explicit asymmetric JOSE algorithm allowlist; reject none and algorithm/key-type confusion
fetch/cache JWKS only from the exact configured HTTPS Access team-domain/issuer endpoint
ignore/reject token-supplied jku/x5u/arbitrary key URLs
select key by kid; unknown kid allows at most one bounded JWKS refresh, then fails closed
verify JWT signature cryptographically
require exact issuer and exact configured Access application audience
allow a bounded audience allowlist only during an explicitly planned rotation window
validate required exp/nbf/iat with small bounded clock skew
require stable sub plus expected verified identity claim and map normalized identity to enabled admin_principals
never log/store the raw Access JWT
on JWKS outage, use only bounded non-expired cached keys already tied to the exact issuer; cache miss/unknown kid/stale cache fails closed
```

RED cases must cover valid signature, wrong key/signature, disallowed algorithm, wrong issuer, wrong audience, expired token, future `nbf`, missing/invalid `iat`, malformed/missing claims, unknown `kid` refresh behavior, malicious `jku`/`x5u`, and JWKS outage/cache behavior.

- [ ] **Step 3: RED tests for PKCE-like challenge flow and default-off break-glass policy**

Prove:

```text
login start requires cryptographically verified Access identity
one-time code expires quickly
code is challenge-bound
code cannot replay
session token stored only as digest
session absolute expiry = 30 minutes
high-risk route fails if authenticated_at older than 10 minutes
principal revoke invalidates session
scope checks remain exact
production legacy wcadmin auth is denied by default on every admin route
there is no permanently reachable production legacy fallback endpoint
temporary break-glass enablement requires explicit policy inputs: reason, operator/principal, exact scopes, start and hard expiry
break-glass auto-expires/fails closed and enable/use/disable are auditable
```

- [ ] **Step 4: Implement session token format**

Use a distinct prefix such as:

```text
wcas_<public-id>.<secret>
```

HMAC with `ADMIN_SESSION_PEPPER_V1` under the rotation framework introduced in Task 8; until Task 8 lands, structure the verifier so the pepper provider is injectable and version-aware from day one.

- [ ] **Step 5: Add loopback browser login to CLI**

`wechat_cli/admin/session.py` responsibilities:

```text
generate verifier/challenge
start random 127.0.0.1 loopback callback on ephemeral port
open Access login URL in default browser
validate callback state/code
exchange code+verifier
persist short-lived session in DPAPI config
never log session token
```

`AdminConfig` schema v2 stores environment/API origin and short-lived session token/expiry; it must not silently migrate a production legacy token into a normal session.

- [ ] **Step 6: Keep legacy auth isolated and production break-glass default-off**

Local e2e may continue `Admin wcadmin_...`. Staging migration can temporarily accept both modes only behind an explicit staging environment policy. Production policy must reject legacy authentication on **all** admin routes by default and must not expose a standing fallback endpoint.

If a future production incident requires legacy break-glass, enabling it is a separate temporary authorization/configuration gate that specifies reason, authorized operator/principal, exact scopes, start time and hard expiry/maintenance window. The policy must auto-expire/disable and audit enable/use/disable. Any credential revoke/rotation after use remains separately gated.

- [ ] **Step 7: Run focused tests**

```powershell
python -m unittest tests.test_admin_config tests.test_admin_client tests.test_admin_cli tests.test_admin_session -v
cd services/license-update-worker
npm run typecheck
npm test -- --run
```

- [ ] **Step 8: Commit**

```powershell
git add services/license-update-worker/migrations/0005_admin_sessions.sql services/license-update-worker/src wechat_cli/admin tests services/license-update-worker/test
git diff --cached --check
git commit -m "feat: add short lived administrator sessions"
```

---

## Task 6: Make Origin policy and admin rate limits explicit

**Design:** B3, B4

**Gate:** B6-G2 continues.

**Files:**
- Create: `services/license-update-worker/src/security_policy.ts`
- Modify: `services/license-update-worker/src/index.ts`
- Modify: `services/license-update-worker/src/admin.ts`
- Modify: `services/license-update-worker/src/service.ts`
- Modify: `services/license-update-worker/src/types.ts`
- Add/modify Worker tests.

- [ ] **Step 1: RED tests for Origin deny contract**

Prove:

```text
native admin/update/license/diagnostic routes with unexpected Origin -> denied
same routes without Origin -> preserve normal behavior
no sensitive route emits Access-Control-Allow-Origin: *
OPTIONS cannot accidentally grant wildcard sensitive access
Access login route has only exact configured origin behavior if browser CORS is required
```

- [ ] **Step 2: Implement central policy helper**

Example interface:

```ts
export function assertNativeApiOriginAllowed(request: Request): void;
export function exactCorsHeaders(origin: string, allowedOrigin: string): Headers;
```

Apply native-origin rejection in middleware by route class rather than duplicating checks in every handler.

- [ ] **Step 3: RED tests for rate classes**

Define named classes:

```text
admin-login = 5 / 300 sec / IP
admin-read = 120 / 60 sec / principal plus IP safety limit
admin-write = 30 / 60 sec / principal
admin-high-risk = 10 / 60 sec / principal
```

Test cross-endpoint aggregation within the same class.

- [ ] **Step 4: Separate rate-limit key material**

Change `enforceRateLimit()` to use a `RATE_LIMIT_PEPPER` provider, not `DEVICE_TOKEN_PEPPER`. Task 8 will version the actual Secret name; local tests inject a fixed fake value.

- [ ] **Step 5: Map every admin route to a class**

Reads -> `admin-read`; create/status/update/rename standard mutations -> `admin-write`; release enable/disable, license revoke, diagnostic delete, key rotation -> `admin-high-risk`.

- [ ] **Step 6: Run Worker verification**

```powershell
cd services/license-update-worker
npm run typecheck
npm test -- --run
```

- [ ] **Step 7: Commit**

```powershell
git add services/license-update-worker/src services/license-update-worker/test
git diff --cached --check
git commit -m "feat: enforce explicit worker ingress policy"
```

---

## Task 7: Separate diagnostic upload TTL from privacy retention

**Design:** B6

**Gate:** B6-G2 continues.

**Files:**
- Create: `services/license-update-worker/migrations/0006_diagnostics_retention.sql`
- Modify: `services/license-update-worker/src/diagnostics.ts`
- Modify: `services/license-update-worker/src/index.ts`
- Modify: `services/license-update-worker/src/admin.ts`
- Modify: `wechat_cli/diagnostics_upload.py`
- Modify: `wechat_cli/web/server.py`
- Modify: `wechat_cli/web/static/index.html`
- Modify: `wechat_cli/web/static/app.js`
- Add/modify diagnostics tests.

- [ ] **Step 1: Define migration**

Add:

```sql
ALTER TABLE diagnostic_submissions ADD COLUMN upload_expires_at TEXT;
ALTER TABLE diagnostic_submissions ADD COLUMN retention_expires_at TEXT;
ALTER TABLE diagnostic_submissions ADD COLUMN consent_version TEXT;
```

Migration/backfill logic in application treats legacy `expires_at` as upload expiry and gives legacy complete rows a conservative bounded retention policy without extending existing data beyond policy.

- [ ] **Step 2: RED tests for lifecycle split**

```text
upload token/session expires at 15m
complete object retention expires at completed_at + 7d
scheduler does not delete a complete object merely because upload TTL passed
scheduler deletes at retention expiry and marks row deleted
manual admin delete is immediate/idempotent
diagnostics object path contains no license_id/device_id
R2 custom metadata contains no license_id/device_id
```

- [ ] **Step 3: Change object key**

New object key:

```text
diagnostics/YYYY-MM-DD/<submission_id>.zip
```

Custom metadata:

```text
submission_id
sha256
```

D1 retains license/device relationship.

- [ ] **Step 4: Add consent version**

Client submits a fixed contract version such as `diagnostics-consent-v1`. UI text must say: explicit upload, maximum 7-day cloud retention, support may delete earlier, local copy remains until the user deletes it.

- [ ] **Step 5: Keep local deletion user-controlled**

After successful upload, offer a local deletion action. Do not silently delete the generated ZIP.

- [ ] **Step 6: Run tests**

```powershell
python -m unittest tests.test_diagnostics tests.test_diagnostics_upload tests.test_web_license_management -v
cd services/license-update-worker
npm run typecheck
npm test -- --run
```

- [ ] **Step 7: Commit**

```powershell
git add services/license-update-worker/migrations/0006_diagnostics_retention.sql services/license-update-worker/src wechat_cli/diagnostics_upload.py wechat_cli/web tests services/license-update-worker/test
git diff --cached --check
git commit -m "feat: enforce diagnostic retention policy"
```

---

## Task 8: Add purpose-separated, version-aware secret rotation framework

**Design:** B5

**Gate:** B6-G2 continues. This task changes code/schema only; it must not add/switch a real staging Secret.

**Files:**
- Create: `services/license-update-worker/src/secret_versions.ts`
- Create: `services/license-update-worker/migrations/0007_secret_versions.sql`
- Modify: `services/license-update-worker/src/types.ts`
- Modify: `services/license-update-worker/src/auth.ts`
- Modify: `services/license-update-worker/src/licenses.ts`
- Modify: `services/license-update-worker/src/diagnostics.ts`
- Modify: `services/license-update-worker/src/updates.ts`
- Modify: `services/license-update-worker/src/service.ts`
- Modify: `services/license-update-worker/src/admin.ts`
- Modify: `services/license-update-worker/wrangler.jsonc`
- Add Worker tests.

- [ ] **Step 1: Define version metadata schema**

At minimum add version fields to rows whose public ID allows direct lookup before digest verification:

```text
devices.token_secret_version
admin_sessions.token_secret_version
download_tickets.secret_version
```

For license-key lookup, store each license’s key-digest version and support computing bounded candidate digests over the configured active lookup versions during rotation overlap.

- [ ] **Step 2: Add a typed secret provider**

Example shape:

```ts
interface VersionedSecretSet {
  currentVersion: number;
  readableVersions: number[];
  value(version: number): string;
}
```

Reject duplicate/empty/unbounded version sets at startup/request use.

- [ ] **Step 3: Split purposes**

New logical secret classes:

```text
LICENSE_KEY_PEPPER_Vn
DEVICE_TOKEN_PEPPER_Vn
ADMIN_SESSION_PEPPER_Vn
CONTACT_LOOKUP_PEPPER_Vn
CONTACT_ENCRYPTION_KEY_Vn
DOWNLOAD_TICKET_SECRET_Vn
DIAGNOSTIC_UPLOAD_SECRET_Vn
RATE_LIMIT_PEPPER_Vn
```

Do not reuse one class for another purpose.

- [ ] **Step 4: RED/GREEN overlap tests**

Prove old-version credentials continue verifying during overlap, new writes use current version, retirement makes the retired version fail, and emergency disable can remove a compromised version immediately.

- [ ] **Step 5: Add lease/release signing-key rotation acceptance helpers**

No private key is stored in source. Add tests that Launcher trusts old+new public keys concurrently, then fails old after trust retirement. Worker lease signer uses one current private key/id while the Launcher profile can carry overlap trust.

- [ ] **Step 6: Run Worker + Python crypto/config tests**

```powershell
cd services/license-update-worker
npm run typecheck
npm test -- --run
cd ../..
python -m unittest tests.test_launcher_config tests.test_update_crypto tests.test_license_lease -v
```

- [ ] **Step 7: Commit**

```powershell
git add services/license-update-worker/migrations/0007_secret_versions.sql services/license-update-worker/src services/license-update-worker/test services/license-update-worker/wrangler.jsonc wechat_cli tests
git diff --cached --check
git commit -m "feat: add versioned security secret rotation"
```

---

# Phase 3 — C-domain Windows integrity and D-domain deployment guard

## Task 9: Pin pywebview and isolate the pre-load URL compatibility boundary

**Design:** C1

**Gate:** **B6-G3 Windows Integrity Local Gate**

**Files:**
- Modify: `pyproject.toml`
- Modify lock/dependency metadata if repository policy has a lock for Python dependencies
- Create: `wechat_cli/launcher/webview_compat.py`
- Modify: `wechat_cli/launcher/webview.py`
- Modify: `tests/test_launcher_ui_contract.py`

- [ ] **Step 1: RED test the adapter contract**

Define `PreloadUrlReader`/function that returns current pre-load URL or raises `WebViewUnavailable`. Tests cover backend available, backend missing, invalid URL, and no use of loaded-gated public accessor.

- [ ] **Step 2: Pin the accepted dependency**

Change:

```text
pywebview>=6.2,<7
```

to the exact Board 5 accepted version:

```text
pywebview==6.2.1
```

Do not upgrade the installed package in this task unless the gate separately authorizes dependency installation; this change is source metadata first.

- [ ] **Step 3: Move internal/backend call into adapter**

`LauncherWindow` calls only the adapter. Keep fail-closed navigation behavior.

- [ ] **Step 4: Run tests**

```powershell
python -m unittest tests.test_launcher_ui_contract tests.test_version_metadata -v
```

- [ ] **Step 5: Commit**

```powershell
git add pyproject.toml wechat_cli/launcher/webview.py wechat_cli/launcher/webview_compat.py tests/test_launcher_ui_contract.py tests/test_version_metadata.py
git diff --cached --check
git commit -m "fix: pin launcher webview compatibility boundary"
```

---

## Task 10: Embed the trust-critical deployment profile in Launcher

**Design:** C3, D3

**Gate:** B6-G3 continues.

**Files:**
- Create: `wechat_cli/launcher/trust_profile.py`
- Modify: `wechat_cli/launcher/config.py`
- Modify: `wechat_cli/launcher/service.py`
- Modify: `npm/scripts/build.py`
- Modify: `scripts/package_windows_app.py`
- Create: `scripts/build_deployment_trust_profile.py` if generation is separated
- Add tests for launcher config/build/packaging.

- [ ] **Step 1: Define immutable profile model**

Recommended schema:

```python
@dataclass(frozen=True)
class DeploymentTrustProfile:
    schema_version: int
    environment: str
    api_base_url: str
    expected_channel: str
    fingerprint_salt: str
    release_public_keys: Mapping[str, str]
    lease_public_keys: Mapping[str, str]
    windows_publisher_policy: str
```

Production profile rejects `beta`, loopback, staging hostname, or missing publisher policy.

- [ ] **Step 2: RED tests**

Prove external `launcher-config.json` cannot override:

```text
api_base_url
environment/channel trust policy
release keys
lease keys
fingerprint salt
publisher policy
```

External config remains allowed to contain only operational values such as port/UI/logging.

- [ ] **Step 3: Embed profile as a PyInstaller resource**

Build injects a generated JSON resource or Python module into Launcher. The source of public-key material is repo-external during real environment builds; unit tests use fake public keys.

- [ ] **Step 4: Add environment mismatch fail-close**

Launcher refuses profile/config combinations that mix staging and production.

- [ ] **Step 5: Run tests**

```powershell
python -m unittest tests.test_launcher_config tests.test_launcher_service tests.test_windows_packaging -v
```

- [ ] **Step 6: Commit**

```powershell
git add wechat_cli/launcher npm/scripts/build.py scripts tests
git diff --cached --check
git commit -m "feat: embed launcher deployment trust profile"
```

---

## Task 11: Add Authenticode verification and signing-provider abstraction

**Design:** C2, C4

**Gate:** B6-G3 continues. Only disposable test certificates/mocks are allowed under this gate; no real certificate purchase/application/use.

**Files:**
- Create: `wechat_cli/windows/authenticode.py`
- Create: `scripts/sign_windows_artifacts.py`
- Modify: `wechat_cli/launcher/service.py`
- Modify: `wechat_cli/launcher/process.py` only if verification belongs at process-start boundary
- Modify: `npm/scripts/build.py`
- Modify: `scripts/package_windows_app.py`
- Add tests.

- [ ] **Step 1: Define publisher policy model**

Example:

```python
@dataclass(frozen=True)
class AuthenticodePolicy:
    required: bool
    expected_subject: str | None
    expected_thumbprints: frozenset[str]
```

Staging test profile may use a disposable test thumbprint. Production profile requires the production publisher identity.

- [ ] **Step 2: RED tests for candidate verification**

```text
unsigned candidate rejected when policy required
invalid signature rejected
valid signature/wrong publisher rejected
valid expected publisher accepted
verification failure happens before subprocess start
```

Use injected verifier/fakes for deterministic unit tests. Add a Windows-only integration test path using a disposable self-signed test cert only when the local gate explicitly allows creating such a temporary cert.

- [ ] **Step 3: Implement Windows verification**

Preferred implementation uses Windows trust APIs/PowerShell `Get-AuthenticodeSignature` in a bounded subprocess only if a stable native API wrapper is not already available. Normalize result into explicit statuses and fail closed on parser/command error.

Do not trust only the certificate thumbprint if the design later chooses a managed certificate renewal chain; allow policy to support publisher subject + configured accepted leafs during rotation.

- [ ] **Step 4: Add signing provider interface**

`scripts/sign_windows_artifacts.py` accepts explicit file paths and a provider mode; it never discovers credentials automatically and never prints secrets. Local tests use a fake/test provider.

- [ ] **Step 5: Enforce build/sign/package order**

Plan contract:

```text
build EXEs
sign EXEs
verify signatures
package signed bytes
hash package
Ed25519-sign update manifest
```

Package script must reject a production profile if required signatures are absent.

- [ ] **Step 6: Run tests**

```powershell
python -m unittest tests.test_windows_authenticode tests.test_launcher_service tests.test_launcher_process tests.test_windows_packaging -v
```

- [ ] **Step 7: Commit**

```powershell
git add wechat_cli/windows/authenticode.py scripts/sign_windows_artifacts.py wechat_cli/launcher npm/scripts/build.py scripts/package_windows_app.py tests
git diff --cached --check
git commit -m "feat: verify windows publisher integrity"
```

---

## Task 12: Build a production-capable signed bootstrap installer target

**Design:** C4

**Gate:** B6-G3 continues.

**Files:**
- Create: `packaging/windows/bootstrap_installer.py` or the repository-appropriate installer source
- Modify: `npm/scripts/build.py`
- Modify: `scripts/package_windows_app.py`
- Modify: `tests/test_windows_packaging.py`
- Add installer-specific tests.

- [ ] **Step 1: Freeze installer behavior contract in tests**

The installer must preserve current accepted user-local semantics:

```text
install only into intended user-local root
atomic current/previous layout creation
Launcher/app bytes exact to packaged artifacts
no silent production credential/config generation
repair/uninstall behavior remains explicit
rollback on partial install
```

- [ ] **Step 2: Add installer build target**

The installer is an EXE suitable for Authenticode signing. It may reuse existing PowerShell logic internally, but production distribution is the signed EXE, not an unsigned ZIP/script entrypoint.

- [ ] **Step 3: Add signing hook and verification**

Installer joins the same signing pipeline as app and Launcher. Its signature is verified before final packaging/publish acceptance.

- [ ] **Step 4: Keep ZIP bootstrap as non-production compatibility output**

Mark ZIP bootstrap metadata/documentation as local/staging compatibility only. Production package selection rejects it.

- [ ] **Step 5: Run packaging tests**

```powershell
python -m unittest tests.test_windows_packaging tests.test_windows_installer -v
```

- [ ] **Step 6: Commit**

```powershell
git add packaging/windows npm/scripts/build.py scripts/package_windows_app.py tests
git diff --cached --check
git commit -m "feat: add signed windows bootstrap target"
```

---

## Task 13: Add fail-closed deployment/environment preflight

**Design:** D3, D4

**Gate:** B6-G3 local tooling portion; no deployment.

**Files:**
- Create: `scripts/deploy_worker.py`
- Modify: `services/license-update-worker/wrangler.jsonc`
- Create: `services/license-update-worker/deployment-policy.json` or equivalent validated source file
- Add: `tests/test_worker_deployment_policy.py`

- [ ] **Step 1: RED tests for accidental-production prevention**

Prove deployment preflight fails when:

```text
environment missing
local/default Worker name equals production name
production D1/R2 ID is placeholder
staging and production resource identifiers collide
production workers_dev exposure is true
trust-profile environment/API origin mismatches target env
required binding/secret declarations missing
```

- [ ] **Step 2: Rename top-level local Worker identity in source config**

Safe source intent:

```text
local/default -> wechat-cli-license-update-local
staging -> wechat-cli-license-update-staging
production -> wechat-cli-license-update
```

This is a source config change only; do not deploy it under the local gate.

- [ ] **Step 3: Make production workers.dev fail closed**

Production deployment policy requires `workers_dev=false` and a custom route/hostname before production deploy can pass. Do not invent/provision the actual production domain in Board 6 local implementation.

- [ ] **Step 4: Implement wrapper**

Invocation must require explicit environment:

```powershell
python scripts/deploy_worker.py preflight --environment staging
```

Actual future deploy mode must require a second explicit action and must print only safe target metadata before executing Wrangler.

- [ ] **Step 5: Run tests**

```powershell
python -m unittest tests.test_worker_deployment_policy -v
```

- [ ] **Step 6: Commit**

```powershell
git add scripts/deploy_worker.py services/license-update-worker/wrangler.jsonc services/license-update-worker/deployment-policy.json tests/test_worker_deployment_policy.py
git diff --cached --check
git commit -m "feat: fail closed worker environment deployment"
```

---

# Phase 4 — Local Board 6 security baseline verification

## Task 14: Run complete local verification and produce the pre-staging audit

**Gate:** completion of B6-G0/G1/G2/G3; this task is local/read-only + docs.

**Files:**
- Create: `docs/superpowers/governance/2026-08-12-board-6-pre-staging-security-audit.md`

- [ ] **Step 1: Full Python**

```powershell
python -m unittest discover -s tests
```

Expected: zero failures; exact count recorded.

- [ ] **Step 2: Worker**

```powershell
cd services/license-update-worker
npm run typecheck
npm test -- --run
cd ../..
```

Expected: zero failures; exact Vitest count recorded.

- [ ] **Step 3: Static trust-boundary checks**

```powershell
rg -n "from scripts\.board5_common|from board5_common" scripts/package_windows_app.py npm wechat_cli services
rg -n "Access-Control-Allow-Origin.*\*" services/license-update-worker/src
rg -n "GITHUB_RELEASE_READ_TOKEN" services/license-update-worker/src
rg -n "DEVICE_TOKEN_PEPPER.*rate|rate.*DEVICE_TOKEN_PEPPER" services/license-update-worker/src
rg -n "DOWNLOAD_TICKET_SECRET.*diagnostic|diagnostic.*DOWNLOAD_TICKET_SECRET" services/license-update-worker/src
```

Expected after implementation:

```text
no production packaging dependency on board5_common
no wildcard CORS
production runtime path does not require GITHUB_RELEASE_READ_TOKEN for R2 backend
rate limiting uses separate key material
diagnostics upload uses separate key material
```

Any legacy migration adapter references must be explicitly classified in the audit.

- [ ] **Step 4: Sensitive-value scan**

Scan all changed non-test source/docs for real token/private-key/license/device-token shapes. Test fixtures may contain synthetic format strings but must be classified.

- [ ] **Step 5: Git diff review**

```powershell
git status --short
git diff --check
git diff --stat
git log --oneline --decorate -20
```

- [ ] **Step 6: Write pre-staging audit**

Record:

```text
integrated source provenance
all local security controls
exact tests/counts
remaining staging-only unknowns
deferred real signing identity
no cloud/staging/production mutations performed under local gates
```

- [ ] **Step 7: Commit audit**

```powershell
git add docs/superpowers/governance/2026-08-12-board-6-pre-staging-security-audit.md
git diff --cached --check
git commit -m "docs: record board 6 pre staging security audit"
```

### Mandatory STOP

After Task 14, STOP and request **B6-G4 Staging Infrastructure Gate**. Do not deploy or mutate staging based on local test success.

---

# Phase 5 — Future staging gates (not authorized by the current approval)

## Task 15: B6-G4 staging infrastructure preparation

**Gate:** **B6-G4 Staging Infrastructure Gate** — explicit cloud mutation approval required.

**Allowed only after approval:** staging-only R2 release bucket/binding, Access test application/policy, required new staging Secrets, staging D1 migrations, safe staging Worker config/deployment required to make Board 6 controls testable.

**Must remain excluded:** production, release publication/enablement, real code-signing procurement, existing unrelated staging release mutation.

- [ ] **Step 1: Read-only cloud preflight**

Resolve exact current staging Worker/D1/R2/Secret names and verify production resources are not targets. Never output Secret values.

- [ ] **Step 2: Create a dedicated staging release-distribution R2 bucket**

Target logical name:

```text
wechat-cli-releases-staging
```

If that exact name is unavailable, STOP for user review rather than silently choosing another production-like name.

- [ ] **Step 3: Bind it as `RELEASES` in staging only**

Do not bind/modify production.

- [ ] **Step 4: Apply Board 6 D1 migrations to staging**

Apply 0004–0007 in order through the fail-closed staging deploy/migration wrapper. Record migration results, no table contents containing secrets.

- [ ] **Step 5: Add staging-only new Secrets**

Only the exact secrets required by the approved staging design, such as version-1 session/diagnostic/rate-limit keys, may be added. Each write is a credential mutation and must be included explicitly in the B6-G4 authorization matrix.

Do not rotate/remove existing secrets in this task.

- [ ] **Step 6: Create staging Access login boundary**

Create only the staging Access application/policy/audience required for short-lived admin login. Record safe IDs/domains, never tokens/secrets. Bind the Worker verifier to the exact staging issuer/team domain, application audience, protected hostname/header contract and bounded JWKS cache policy defined in B2. Staging workers.dev or alternate ingress must not become an unprotected identity bypass.

- [ ] **Step 7: Deploy Board 6 Worker to staging through wrapper**

Preflight must identify exact staging Worker and refuse production identifiers.

- [ ] **Step 8: Read-only reconcile**

Verify staging health/environment, binding presence, migrations, and that existing Board 5 releases remain unchanged/disabled as recorded.

### Mandatory STOP

Request **B6-G5 Staging Behavior Acceptance Gate**.

---

## Task 16: B6-G5 staging behavior acceptance

**Gate:** **B6-G5 Staging Behavior Acceptance Gate**

This gate must explicitly enumerate every remote write. If a new staging acceptance release is required, publication/register/enable operations must be separately listed; do not infer release authorization from general behavior-testing approval.

- [x] **Step 1: Channel trust acceptance**

Use newly created disposable Board 6 test licenses/devices, not JD25 or retired Board 5 licenses. Verify aligned stable/beta behavior and mismatch rejection with zero ticket creation.

- [x] **Step 2: Exact failed-release acceptance**

Use a controlled staging candidate pair proving exact `(version, manifest_sha256)` suppression. Do not reuse historical Board 5 fault release unless the gate explicitly says so.

- [x] **Step 3: R2 distribution and immutable provenance acceptance**

A separately authorized staging acceptance release, if needed, must follow this exact order:

```text
create/upload GitHub Draft for inspection only
store the exact signed runtime package in staging R2
prove R2 object hash/size and target Worker transport/range readiness while candidate is non-selectable/disabled
only after R2 readiness, publish immutable GitHub provenance/tag with make_latest=false
reconcile published GitHub assets/tag against the already-readied R2 object
register/finalize Worker candidate disabled/paused
prove Worker download uses R2 with zero GitHub runtime fetch
then enable only under an explicitly approved release-enable sub-gate
```

A readiness failure must leave GitHub provenance unpublished and the candidate ineligible. A post-publication/pre-enable rollback keeps immutable provenance intact and leaves the Worker candidate disabled/paused.

- [x] **Step 4: Admin session and Access cryptographic identity acceptance**

Prove real staging Access login, exact staging issuer/audience/hostname binding, one-time code binding, 30-minute session metadata, scope behavior, high-risk recent-auth requirement, revoke, and no normal long-lived admin token use. Reconfirm the cryptographic negative-test suite for signature/key/algorithm/issuer/audience/time/claim/JWKS behaviors. Verify staging legacy mode is only present if separately enabled by explicit staging policy and that the production policy artifact remains default-off with no permanent legacy fallback endpoint.

- [x] **Step 5: Origin/rate acceptance**

Verify unexpected Origin fail-close, no wildcard CORS, and 429 behavior for controlled limits without causing denial against shared/production traffic.

- [x] **Step 6: Diagnostics retention acceptance**

Use a disposable diagnostic object. Verify opaque R2 path, upload TTL independent from retention TTL, admin download/delete, and scheduled/forced test cleanup through an acceptance-safe mechanism. Do not wait seven real days; use deterministic injectable clock in staging acceptance tooling if the implementation provides it, without changing system time.

- [x] **Step 7: Reconcile and revoke disposable test credentials**

Cleanup only the Board 6 test licenses/devices/releases/objects named in the approved gate. Preserve evidence summaries.

### Mandatory STOP

B6-G5 is accepted complete. Do not proceed to real code signing until **B6-G6** separately approves the provider/identity choice, any payment/application, identity verification, key provisioning, and actual signing operation.

---

## Task 17: B6-G6 real code-signing procurement and staging-signed acceptance

**Gate:** **B6-G6 Code Signing Procurement & Real Staging Signing Gate**

Approval must separately cover the vendor/identity choice, any payment/application, identity verification, key provisioning, and actual signing operation. No such action is implied by this plan.

- [ ] **Step 1: Select the signing provider against the approved design**

Required properties:

```text
non-exportable/hardware-backed or managed signing key
Windows Authenticode support
timestamping support
automation path with least privilege
auditable signing events
publisher identity suitable for formal distribution
```

- [ ] **Step 2: Provision only after explicit approval**

Never copy private key material into the repository or generic `.env` files.

- [ ] **Step 3: Sign a staging app, Launcher, and installer**

Run build -> sign -> verify -> package -> SHA -> Ed25519 manifest signing in that order.

- [ ] **Step 4: Verify Windows signatures independently**

Use Windows trust verification and record only public certificate metadata: subject, issuer, validity, thumbprint/public identity, timestamp status.

- [ ] **Step 5: Run one explicitly authorized signed staging update acceptance**

Prove candidate Authenticode verification happens before process launch and that wrong/unsigned test candidates fail closed.

### Mandatory STOP

Request **B6-G7 Staging Key Rotation Drill Gate**.

---

## Task 18: B6-G7 staging key-rotation drill

**Gate:** **B6-G7 Staging Key Rotation Drill Gate**

Each Secret add/switch/retire is an explicit staging credential mutation. The approval matrix must list the exact key class/version affected.

- [ ] **Step 1: Choose one non-destructive representative rotation per mechanism**

At minimum prove:

```text
HMAC pepper overlap (e.g. admin session)
symmetric token secret overlap (diagnostic or download ticket)
contact encryption version migration
lease signing trust overlap
release signing trust overlap
```

- [ ] **Step 2: Add new version, do not retire old yet**

Read-only verify both versions available by metadata only.

- [ ] **Step 3: Switch writers/current signer**

Prove new output uses new version while old credentials/leases remain valid during overlap.

- [ ] **Step 4: Exercise rollback before retirement**

Switch back to prior current version and prove continuity.

- [ ] **Step 5: Re-switch and retire old only where the gate explicitly authorizes retirement**

For lease/release keys, respect maximum offline/update acceptance windows before retirement; if the real window cannot be elapsed during Board 6, retirement remains deferred with documented acceptance instead of faking elapsed time.

- [ ] **Step 6: Reconcile and document emergency-revoke behavior**

No production rotation.

### Mandatory STOP

Request **B6-G8 Board 6 Closure Gate**.

---

# Phase 6 — B6-G8 closure

## Task 19: Final Board 6 verification and acceptance report

**Gate:** **B6-G8 Board 6 Closure Gate**

**Files:**
- Create: `docs/deployment/2026-08-12-board-6-security-delivery-preparation-report.md`
- Modify: `docs/PROJECT_STATE.md`
- Modify: `docs/deployment/authorized-update-roadmap.md`
- Modify: this plan only to check completed items/evidence.

- [ ] **Step 1: Fresh full local verification**

```powershell
python -m unittest discover -s tests
cd services/license-update-worker
npm run typecheck
npm test -- --run
cd ../..
git diff --check
git status --short
```

Record exact counts.

- [ ] **Step 2: Fresh staging read-only reconcile**

Verify accepted Board 6 staging state without mutation:

```text
server-authoritative channel behavior evidence
R2 distribution backend and immutable GitHub provenance
admin Access/session state
Origin/rate policy
secret-version metadata/rotation evidence
diagnostics retention policy
real signed staging artifact/public certificate metadata
staging/production isolation guard
all disposable Board 6 test resources in their approved terminal states
```

- [ ] **Step 3: Reverify immutable historical boundaries**

Board 5 evidence worktree/commit remains unchanged; main remains at its separately authorized state; no production resources were mutated under Board 6 unless the user explicitly expanded scope in a later approval.

- [ ] **Step 4: Sensitive-value scan**

Zero real credentials/private keys/complete license keys/device tokens/admin sessions in tracked docs/source.

- [ ] **Step 5: Write Board 6 acceptance report**

Required sections:

```text
scope and authorization matrix
source integration provenance
A-domain acceptance
B-domain acceptance
C-domain signing/integrity acceptance
D-domain staging/production isolation acceptance
staging cloud mutations actually performed
credential rotations actually performed
real signing identity public metadata only
deferred items
explicit actions not performed
Board 7 entry conditions
```

- [ ] **Step 6: Update roadmap only if every Board 6 exit condition is met**

If any required signing/staging/rotation/integration acceptance remains incomplete, canonical status must stay `Board 6 in progress` and list the exact blocker. Do not claim Board 6 complete early.

- [ ] **Step 7: Commit closure docs locally**

```powershell
git add docs/PROJECT_STATE.md docs/deployment/authorized-update-roadmap.md docs/deployment/*board-6* docs/superpowers/plans/2026-08-12-board-6-security-delivery-preparation.md
git diff --cached --check
git commit -m "docs: complete board 6 security delivery preparation"
```

No push/merge.

- [ ] **Step 8: STOP**

Board 7 remains unstarted. Present Board 6 closure evidence and request a separate Board 7 design/production gate. Do not provision/deploy production automatically.

---

# 20. Plan-to-design coverage matrix

| Design risk | Plan task(s) |
|---|---|
| A1 channel trust | Task 2, 16 |
| A2 failed-candidate identity | Task 3, 16 |
| A3 release lifecycle | Task 4, 15, 16 |
| A4 redirect/runtime transport | Task 4, 16 |
| B1 GitHub read credential | Task 4, 15, 16 |
| B2 short-lived admin auth | Task 5, 15, 16 |
| B3 CORS/origin | Task 6, 16 |
| B4 rate limiting | Task 6, 16 |
| B5 key rotation | Task 8, 15, 18 |
| B6 diagnostics data policy | Task 7, 15, 16 |
| C1 pywebview dependency | Task 9 |
| C2 Authenticode | Task 11, 17 |
| C3 embedded trust profile | Task 10, 16, 17 |
| C4 signed installer/runtime verification | Task 11, 12, 17 |
| D1 packaging dependency | Task 1 |
| D2 source integration debt | Task 0.1, 0.2 |
| D3 staging/production isolation | Task 10, 13, 15 |
| D4 ingress/domain/China boundary | Task 13, 15, Board 7 entry conditions |

# 21. Current next implementation authorization request

The design/plan are approved and **B6-G0 through B6-G5 are complete**. B6-G4 staging infrastructure closure is recorded in `docs/superpowers/governance/2026-08-14-board-6-staging-infrastructure-gate.md`; the live staging Worker Version ID is `14a19ea3-5a96-408b-a4e3-0a8d8e4ebe2c`. B6-G5 closure is recorded in `docs/superpowers/governance/2026-08-14-board-6-staging-behavior-acceptance.md`. This completion does not authorize real code-signing procurement/use, production mutation, push, or merge.

The B6-G6 entry audit is recorded in `docs/superpowers/governance/2026-08-14-board-6-code-signing-entry-readiness.md`. Under the separately approved Phase A, provider-neutral local readiness repair/research is now complete at `9f4ad0f` + `e9cb67b`, and the provider decision draft is `docs/superpowers/governance/2026-08-14-board-6-code-signing-provider-decision.md`. This Phase A completion does **not** enter Task 17 real procurement/signing: real provider/publisher selection, any payment/application/identity verification/key provisioning, provider software installation, concrete signer adapter implementation, staging publisher-policy mutation, and actual signing remain unperformed.

The **first and only next authorization request** is now:

> **B6-G6 Real Signing Provider Approval** — the next authorization must name the selected provider/vendor, publisher identity, exact plan/tier and expected fee, account/subscription action, identity-verification action, required signer installation, managed/HSM key provisioning, staging publisher-policy public identity, concrete `WindowsSigningProvider` adapter, actual staging app + Launcher + installer signing, and one signed staging update acceptance. Production, Board 5 assets/JD25, push/merge, and unrelated cloud resources remain excluded.

Phase A is complete but the real B6-G6 signing gate is **not** implied by it or by any prior blanket continuation approval. Task 17 still requires separate explicit authorization of the selected provider/vendor and publisher identity, exact plan/tier/fee, payment/application, identity verification, signing-tool installation, managed/HSM key provisioning, concrete signer adapter, staging publisher-policy mutation, actual signing, and one signed staging update acceptance. B6-G7 and B6-G8 remain not entered; Board 7 remains unstarted.
