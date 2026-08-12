# Board 6 Security & Delivery Preparation Design

> **APPROVED DESIGN — B6-G0 and B6-G1 local gates complete; B6-G2 pending approval; every later gate remains independently authorized.**
>
> Date: 2026-08-12
>
> Approved seed content SHA-256: `032b23fd485c39700ffcb5d319832b78c6812edc38afc99d4696a4aeaa9775d0`. The exact approved seed remains retained, untracked and untouched, in the Board 5 evidence worktree. This tracked canonical copy originates from that exact seed and contains only the explicitly authorized B6-G0 governance/status corrections plus the approved lifecycle and Access/JWT/break-glass security revisions.
>
> Current authorization boundary: B6-G0 and B6-G1 are complete locally. B6-G2 is **not** authorized. No cloud/staging/production mutation, credential rotation, code-signing purchase/application, release publication, push, merge, reset, rebase, or amend is authorized by this document.

## 1. Goal

Board 6 converts the Board 5 accepted Windows/staging system from an acceptance-grade implementation into a production-ready security architecture without erasing the evidence or lessons from Board 5.

The design is organized into four security domains:

- **A. Update trust boundary**
- **B. Credentials & admin security**
- **C. Windows delivery integrity**
- **D. Integration & production boundary**

Every risk below records current behavior, risk, alternatives, recommended design, acceptance criteria, migration/rollback, and the independent authorization gate required before execution.

## 2. Frozen Board 5 risk handoff mapping

The eight frozen Board 5 handoff risks are covered first and remain traceable:

| Board 5 handoff | Board 6 risk |
|---|---|
| 1. Update channel trust boundary | A1 |
| 2. Failed-version suppression granularity | A2 |
| 3. GitHub Draft visibility semantics | A3 |
| 4. GitHub release read credential | B1 |
| 5. Worker redirect trust boundary | A4 |
| 6. Packaging production dependency on Board 5 helper | D1 |
| 7. pywebview backend/internal API dependency | C1 |
| 8. Source integration debt | D2 |

Additional required Board 6 concerns are covered in B2–B6, C2–C4, and D3–D4.

## 3. Current verified baseline

Board 5 is accepted complete at local evidence commit `67d3dec0fd1c4a02c87be1ab79c4f78ea63f49d6`. Frozen main remains `a579a25cb7f16e6fdf88d618252b4a5cbffef53d`.

Board 6 is **in progress** on `board6/security-delivery-preparation`. B6-G0 source integration and packaging-boundary cleanup are complete through `c1d045895a044dbb4c9998a787c77775654074fa`. B6-G1 Update Trust Local Gate is complete through `bdc98afc0d945c4c86f1e3b21686d2fe798ccdd1`: `a23b6ff` makes the authenticated license channel server-authoritative, `988a504` adds exact failed-release identity plus version immutability, and `bdc98af` adds the local dual GitHub-provenance/R2-distribution model with R2-readiness-before-provenance ordering and separately gated enablement. Fresh local verification passed Python 510 run / 2 expected skips / 0 failures, Worker typecheck, and Vitest 40/40. No staging/cloud/production behavior was changed. **B6-G2 remains pending approval.**

The risk-card “Current behavior” text below records the behavior observed at design time before the corresponding implementation gate. D1/D2 are locally remediated by B6-G0; A1/A2/A3/A4/B1 local update-trust code paths are implemented by B6-G1 but still require their later staging gates for real environment acceptance; B2–B6 and C-domain implementation remain pending later gates.

Relevant design-time implementation facts:

- Worker `/v1/updates/check` authenticates the device and rate-limits by device, but selects releases from the client-provided `channel`; it does not enforce equality with `authenticated.license.release_channel`.
- Worker release suppression receives `failed_versions: string[]`; `selectRelease()` skips by semantic version only.
- Launcher local failed registry records `version + manifest_sha256`.
- Worker download transport authenticates to `api.github.com` with `GITHUB_RELEASE_READ_TOKEN`, follows redirects manually, strips `Authorization` after the first hop, requires HTTPS, but does not constrain the redirect hostname.
- Current publisher creates a private GitHub **Draft**, uploads package/manifest/signature, then registers a disabled/paused Worker release. Board 5 proved Draft assets are not usable by the current private download transport until the release is published.
- Admin API authenticates long-lived `wcadmin_...` credentials against a stored HMAC digest and scopes. The Windows admin CLI protects the long-lived credential with current-user DPAPI.
- `admin_tokens` has status and scopes but no expiration/session model.
- There is no global CORS middleware. Browser cross-origin access is therefore not enabled, but the deny-by-default behavior is implicit rather than an explicit tested contract.
- Rate limiting exists for license activation, update check, diagnostics session creation, and admin license creation. Other admin operations are not centrally rate-limited.
- `enforceRateLimit()` currently derives identity digests using `DEVICE_TOKEN_PEPPER`, coupling two security purposes.
- `DOWNLOAD_TICKET_SECRET` is also used to authenticate diagnostics upload tokens.
- Contact encryption already supports versioned keys and a batch rotation endpoint; other HMAC peppers and ticket secrets are not versioned for overlap rotation.
- Diagnostics are locally generated with explicit consent and redaction. Cloud upload sessions expire after 15 minutes. The same `expires_at` field is also used by scheduled cleanup, so upload-session expiry currently doubles as object retention expiry.
- Diagnostic R2 object keys/custom metadata include license/device identifiers.
- Launcher trusts external `launcher-config.json` for `api_base_url`, `channel`, fingerprint salt, release public keys, and lease public keys. The file is validated structurally but is not separately signed.
- Launcher uses `window.gui.get_current_url(uid)` in `before_load`, an internal/backend pywebview dependency. `pyproject.toml` currently permits `pywebview>=6.2,<7`.
- Windows app and Launcher binaries are not Authenticode-signed. There is no runtime Authenticode verification before an extracted update candidate is launched.
- Current bootstrap is a ZIP plus scripts; there is no signed installer executable.
- `scripts/package_windows_app.py` imports `scripts.board5_common.assert_outside_repository`.
- Main remains frozen at `a579a25...`; Board 5 contains product commits plus acceptance-only commits that must not be merged wholesale.
- `services/license-update-worker/wrangler.jsonc` has distinct staging/production blocks, but the top-level Worker name is the same as the production Worker name and production D1 still contains a placeholder ID.

## 4. Architecture alternatives

### Option 1 — Minimal in-place hardening

Keep GitHub as runtime distribution, retain long-lived admin tokens, add host allowlists, rate limits, Authenticode signing, and deployment checks.

**Pros:** smallest code delta, easiest migration.

**Cons:** Worker still carries a long-lived GitHub credential; GitHub release visibility remains coupled to runtime distribution; static admin credentials remain a high-value daily-use secret; transport complexity remains.

### Option 2 — Layered hardening while retaining GitHub runtime transport

Use a GitHub App or another short-lived GitHub credential, short-lived admin sessions, Authenticode, strict environment profiles, and exact failed-candidate identity.

**Pros:** materially reduces long-lived credential exposure while preserving current release transport.

**Cons:** still depends on GitHub redirect/asset-host semantics at runtime; requires token minting machinery and keeps GitHub availability inside the update serving path.

### Option 3 — Consolidated production trust boundary (**recommended**)

Use GitHub private Releases as immutable provenance/audit artifacts, but move **runtime package distribution to a dedicated private R2 release bucket**. The Worker serves/verifies release bytes from R2 and no longer needs a GitHub read credential for production runtime downloads. Add server-authoritative channel selection, exact failed-candidate identity, short-lived admin sessions, explicit ingress/rate-limit policy, versioned secret rotation, signed Windows artifacts, an embedded deployment trust profile, and fail-closed staging/production tooling.

**Why recommended:** it removes two classes of runtime trust at once: the long-lived GitHub read credential and cross-host GitHub redirect semantics. It also decouples “GitHub Draft/published” from whether an update can be downloaded by clients. GitHub remains the immutable external provenance record rather than the live package transport dependency.

## 5. Authorization-gate vocabulary

The following gate names are used throughout this design. Approval of the design does **not** approve any gate.

- **B6-G0 Source Integration Gate** — local worktree/branch creation and selective local integration only.
- **B6-G1 Update Trust Local Gate** — local code/tests for A-domain trust semantics; no cloud behavior change.
- **B6-G2 Admin & Data Security Local Gate** — local code/tests/migrations for B-domain controls; no cloud mutation.
- **B6-G3 Windows Integrity Local Gate** — local signing abstractions/test certificates/runtime verification/packaging tests; no real certificate acquisition or signing identity use.
- **B6-G4 Staging Infrastructure Gate** — create/change staging-only R2/Access/config/secrets/bindings; explicit cloud mutation.
- **B6-G5 Staging Behavior Acceptance Gate** — deploy/enable Board 6 behavior in staging and run acceptance.
- **B6-G6 Code Signing Procurement & Real Staging Signing Gate** — purchase/apply/provision a real signing identity and use it on staging artifacts.
- **B6-G7 Staging Key Rotation Drill Gate** — staging Secret/key add/switch/retire operations and rotation acceptance.
- **B6-G8 Board 6 Closure Gate** — final read-only/local verification, acceptance report, roadmap state, local closure commit only.
- **Board 7 Production Provision/Deploy Gates** — all production resource creation, production Secret writes, production deployment, production release/cutover remain outside Board 6 unless separately re-scoped by the user.

---

# A. Update trust boundary

## A1. Server-authoritative release channel — frozen handoff #1

**Severity:** High

### Current behavior

`/v1/updates/check` authenticates the device/license, parses client `channel`, and passes that value into `selectRelease()`. `LicenseRow.release_channel` is available but not compared to the request channel.

### Risk

A stable license can request the beta channel if a client/config is modified. Board 5 avoided this by explicit test discipline, not by a server-enforced trust boundary.

### Options

1. Keep client channel authoritative and rely on Launcher config discipline.
2. Require strict equality between `request.channel` and `license.release_channel`.
3. Make `license.release_channel` server-authoritative; client channel becomes an expected-value assertion only.

### Recommended design

Adopt option 3. For compatibility, the current request may continue sending `channel`, but Worker must reject a mismatch with `UPDATE_CHANNEL_MISMATCH`. Release selection must use `authenticated.license.release_channel`, never the client field.

A future API schema may omit client channel entirely; until then, client channel is only a fail-closed expectation check.

### Acceptance criteria

- Stable license + stable request selects only stable releases.
- Stable license + beta request returns `409 UPDATE_CHANNEL_MISMATCH` and creates no ticket.
- Beta license + stable request fails identically.
- Audit metadata records effective server channel.
- Existing Board 5 stable/beta happy paths remain valid when aligned.

### Migration / rollback

Add the equality check before changing any client schema. Old aligned clients continue working. Rollback is a local code revert before staging; after staging acceptance, rollback requires the Staging Behavior Acceptance Gate because relaxing the boundary changes security behavior.

### Independent authorization gate

**B6-G1**, then **B6-G5** for staging activation.

---

## A2. Exact failed-candidate identity — frozen handoff #2

**Severity:** High

### Current behavior

Launcher failed registry stores `version + manifest_sha256`, while Worker receives only `failed_versions: string[]` and suppresses by version.

### Risk

Local and service semantics disagree. A corrected artifact that reuses a version would be suppressed even if its manifest differs; conversely, the service cannot express the exact candidate that failed.

### Options

1. Declare semantic versions immutable and simplify local state to version-only.
2. Send structured `{version, manifest_sha256}` failed candidates and suppress exact pairs.
3. Suppress by Worker `release_id` only.

### Recommended design

Adopt option 2 and also enforce release-version immutability as a release policy. Add `failed_releases` entries containing both version and manifest SHA-256. Worker skips the exact manifest identity. Keep `failed_versions` only as a legacy compatibility input for old clients during migration.

### Acceptance criteria

- Current client schema remains accepted during migration.
- New client sends exact failed candidate identity.
- Same version/different manifest is not accidentally suppressed by the new path.
- Exact failed manifest is suppressed.
- Duplicate registration of an already-used channel/version with different manifest is rejected unless an explicit future migration policy says otherwise.

### Migration / rollback

Dual-read request schema: new `failed_releases`, legacy `failed_versions`. Roll back by continuing legacy interpretation while leaving the new field ignored; no database destructive migration is required for the client-side registry.

### Independent authorization gate

**B6-G1**, then **B6-G5** for staging acceptance.

---

## A3. Release lifecycle and GitHub provenance semantics — frozen handoff #3

**Severity:** High

### Current behavior

Publisher creates a private Draft, uploads package/manifest/signature, then registers the Worker release disabled/paused. Board 5 proved the current GitHub read path cannot serve Draft assets; v0.5.1 and the fault candidate had to be published before runtime download worked.

### Risk

“Draft means inspectable but not published” currently conflicts with “Worker registration assumes package transport exists.” Tag creation timing, `make_latest`, provenance, and client eligibility are separate concepts but not formally separated.

### Options

1. Publish GitHub release before Worker registration and continue GitHub runtime download.
2. Use GitHub App credentials so Worker can attempt Draft access.
3. Decouple provenance from runtime transport: GitHub release lifecycle is provenance; R2 is client distribution.

### Recommended design

Adopt option 3.

Formal lifecycle:

1. Build and sign immutable local artifacts.
2. Create a private GitHub **Draft** and upload package/manifest/signature for inspection only; do not publish or create the immutable tag yet.
3. Upload the exact already-signed package to the target R2 release bucket through the scoped preparation flow and establish **R2 transport readiness** before any GitHub publication. Readiness requires the exact object to exist, package size/hash to match the signed manifest, the Worker R2 adapter/range path to serve the intended object in the target environment, and the candidate to remain non-selectable/disabled.
4. Read-only verify the R2 object, signed manifest, local artifact and GitHub Draft assets all map to the same immutable bytes. A preparation row may exist only if it is structurally ineligible for client selection and enablement.
5. Only after R2 transport readiness is accepted, publish the private GitHub release/prerelease with `make_latest=false` and create the immutable tag pointing to the audited release-repository provenance commit.
6. Read-only verify the now-published GitHub provenance tag/assets/digests still match the already-readied R2 artifact.
7. Register or finalize the Worker release **disabled/paused** with R2 distribution metadata plus the published immutable GitHub provenance metadata. Registration/finalization must not imply enablement.
8. Enable only under an independently authorized release-enable gate.

Board 6 does not change historical v0.5.0/v0.5.1 releases.

### Acceptance criteria

- Draft/published state no longer determines whether Worker can read runtime package bytes.
- **No immutable GitHub provenance publication/tag creation occurs before R2 transport readiness is proven for the exact signed artifact.**
- R2 readiness proves exact size/hash and a working target-environment transport path while the candidate is still non-selectable/disabled.
- Published GitHub provenance is a post-readiness immutable audit record, not a substitute for transport readiness.
- Worker release cannot enable until R2 object size/hash matches the signed manifest and published GitHub provenance has been reconciled.
- GitHub tag is immutable and points to the recorded provenance commit.
- `make_latest` is not used by Worker selection logic.
- Disabled/paused remains the default after registration/finalization.
- Release enable is a separate independently authorized mutation.

### Migration / rollback

Support both `github` and `r2` distribution backends temporarily. Existing Board 5 rows remain GitHub-backed. New Board 6 staging acceptance release uses R2. Before GitHub publication, rollback removes/disables only the unready preparation state under its authorized cleanup policy and never requires unpublishing provenance. After provenance publication but before enable, rollback leaves the immutable provenance record intact and keeps the Worker candidate disabled/paused. Existing GitHub-backed rows remain untouched.

### Independent authorization gate

Local model under **B6-G1**. R2 resource creation/upload requires **B6-G4**. Real staging release lifecycle acceptance requires an additional release-specific approval inside **B6-G5**; Board 6 design approval alone does not authorize a new release.

---

## A4. Runtime asset transport / redirect trust — frozen handoff #5

**Severity:** High

### Current behavior

Initial GitHub URL must be HTTPS on `api.github.com`. Redirects are manual; `Authorization` is stripped before following. Redirect destinations must be HTTPS and cannot contain userinfo, but hostname is otherwise unrestricted.

### Risk

A compromised/misbehaving upstream redirect can send the Worker to an arbitrary HTTPS host. Authorization is protected, but Worker still becomes an unconstrained fetch proxy for a signed-ticket path and depends on external host semantics.

### Options

1. Maintain GitHub transport and add a strict, verified GitHub asset-host allowlist.
2. Maintain GitHub transport but mint short-lived GitHub credentials and validate every redirect hop.
3. Remove GitHub redirects from production runtime by serving package bytes from private R2.

### Recommended design

Adopt option 3 for production. Keep the existing GitHub adapter only as a migration/staging compatibility backend while R2 acceptance is incomplete. Production configuration must reject `distribution_backend=github`.

### Acceptance criteria

- R2-backed download performs no outbound GitHub fetch.
- Production startup/config validation rejects GitHub runtime backend.
- Existing GitHub adapter tests continue proving Authorization stripping until the adapter is retired.
- Download tickets remain bound to release/license/device/hash/size and are revalidated at download time.

### Migration / rollback

Dual backend at first. Staging can roll a new candidate back to existing GitHub-backed 0.5.1 without changing old rows. GitHub adapter removal is a later cleanup after R2 is proven and separately approved.

### Independent authorization gate

**B6-G1** locally, **B6-G4/G5** for staging R2 and behavior.

---

# B. Credentials & admin security

## B1. GitHub release read credential lifecycle — frozen handoff #4

**Severity:** High

### Current behavior

Staging Worker stores a dedicated fine-grained `GITHUB_RELEASE_READ_TOKEN` with private-repository read access. It is long-lived and used at runtime for every GitHub-backed package download.

### Risk

A Worker Secret compromise exposes a reusable GitHub credential. Rotation/recovery is manual, and production replacement is undefined.

### Options

1. Keep fine-grained PAT with strict repo scope and scheduled rotation.
2. Replace PAT with short-lived GitHub App installation tokens.
3. Remove GitHub runtime credential by moving package distribution to R2.

### Recommended design

Adopt option 3. GitHub credentials remain operator/publisher-side provenance credentials, not Worker runtime download credentials. During migration, staging PAT remains unchanged until R2 acceptance; removal/rotation requires its own gate.

### Acceptance criteria

- New R2-backed update succeeds with no `GITHUB_RELEASE_READ_TOKEN` read in the runtime path.
- Production Env type/config does not require the GitHub read token.
- Staging legacy backend remains explicit and disabled for new production releases.
- No credential value appears in docs/logs/tests.

### Migration / rollback

Do not delete the staging PAT during local implementation. After R2 staging acceptance, remove it only under a separately approved Secret-removal action. Rollback before removal simply reselects the legacy backend.

### Independent authorization gate

Code: **B6-G1/B6-G2**. Staging Secret removal/rotation: **B6-G4** plus explicit credential-mutation approval.

---

## B2. Short-lived administrator authentication

**Severity:** Critical

### Current behavior

Admin CLI sends a long-lived `wcadmin_...` bearer-style secret on every admin API request. Worker stores only HMAC digest/scopes/status; CLI stores plaintext only inside a DPAPI-protected local envelope. `admin_tokens` has no expiry.

### Risk

Compromise of the DPAPI-protected credential or process memory grants durable admin capability until manual revoke. Daily-use and recovery credentials are not separated.

### Options

1. Keep static tokens but add expiration and narrower scopes.
2. Use static root token only to mint short-lived application sessions.
3. Use interactive Cloudflare Access identity to mint short-lived Worker admin sessions; retain legacy recovery material only as a **default-off, temporarily authorized break-glass mechanism**, never as a permanently reachable fallback endpoint.

### Recommended design

Adopt option 3.

Production/staging admin login flow:

1. CLI creates a random verifier/challenge and opens an Access-protected login URL.
2. Browser authenticates through Cloudflare Access.
3. Worker accepts the Access identity assertion only from the exact configured Access-protected ingress/header. Identity, email, subject, issuer or audience values supplied in request body/query parameters are never trusted as authentication evidence.
4. The Worker performs full JWT cryptographic verification before mapping any identity:
   - use a JOSE verifier with an explicit asymmetric algorithm allowlist appropriate to the configured Cloudflare Access deployment; reject `none` and algorithm/key-type confusion;
   - obtain JWKS only from the exact configured HTTPS Access team-domain/issuer endpoint; never follow token-controlled `jku`, `x5u` or arbitrary key URLs;
   - select the verification key by `kid`; an unknown `kid` may trigger at most one bounded JWKS refresh, then fails closed;
   - cryptographically verify the signature;
   - require exact configured `iss` and exact configured Access application `aud`; a bounded audience allowlist is permitted only during an explicitly planned audience rotation window;
   - require and validate `exp`, `nbf`, and `iat` using a small bounded clock skew; missing, expired or not-yet-valid assertions fail closed;
   - require stable `sub` plus the expected verified identity claim (for example normalized email), then map that verified identity to an enabled `admin_principals` record;
   - never log or persist the raw Access JWT. Audit only safe principal/assertion metadata needed for traceability;
   - if JWKS retrieval is unavailable, only previously cached, not-expired keys may be used within a bounded cache lifetime. Unknown `kid`, cache miss or stale cache fails closed.
5. After successful cryptographic verification, Worker maps the verified Access identity to an enabled admin principal and creates a one-time login code bound to the CLI challenge.
6. Browser returns the code to a loopback callback on `127.0.0.1`.
7. CLI exchanges code + verifier for a short-lived `wcas_...` session; the one-time code cannot replay.
8. CLI stores only the short-lived session in DPAPI.
9. Worker validates session digest, expiry, scope, principal status, and recent-auth requirement for high-risk mutations.

Legacy `wcadmin_...` is permitted for disposable local e2e only by default. In production it is **disabled by policy/config on every admin route**, with no permanently exposed fallback endpoint. A production break-glass event requires an independent temporary authorization that records reason, authorized operator/principal, exact scopes, start time, hard expiry/maintenance window, and the specific temporary policy change. The mechanism must fail closed and auto-expire/disable; enable/use/disable are audited. Any post-use revoke/rotation is separately authorized as required. Staging migration may temporarily allow legacy auth only under an explicit staging policy and gate; staging permissiveness never becomes a production default.

Recommended session lifetime: 30 minutes absolute; high-risk mutation requires authentication age <=10 minutes.

### Acceptance criteria

- No normal staging/production admin command requires a long-lived admin secret.
- Access assertions are rejected for invalid signature, wrong key, disallowed algorithm, wrong issuer, wrong audience, expired `exp`, future `nbf`, invalid/missing `iat`, missing required identity claims, malformed token, malicious `jku`/`x5u`, and unknown `kid` after the single bounded refresh.
- JWKS outage behavior is fail closed except for bounded, not-expired cached keys already associated with the exact configured issuer; arbitrary key discovery is impossible.
- Production `workers.dev` bypass cannot reach the protected admin identity flow; exact production hostname and Access audience are enforced.
- Expired/revoked sessions fail 401.
- Scope enforcement remains fail closed.
- One-time login codes cannot be replayed and are challenge-bound.
- Production direct legacy `Admin wcadmin_...` use fails by default on all admin routes. There is no permanently open legacy fallback endpoint.
- A break-glass authorization, if explicitly granted, is temporary, scope-bounded, time-bounded, auditable and automatically disabled/expired at the end of the window.
- Admin identity/session issuance/revoke/high-risk actions and break-glass enable/use/disable are audited without storing raw Access JWTs.

### Migration / rollback

Add session auth alongside legacy auth first in local/staging migration code. Staging may temporarily accept both only behind an explicit staging policy while Access cryptographic verification and session flow are proven. Rollback can disable staging session login and retain the existing staging-only legacy path. Production normal operation never enables legacy auth; any production break-glass use is a separate temporary authorization/policy change with hard expiry, not a standing rollback endpoint.

### Independent authorization gate

Local session model: **B6-G2**. Cloudflare Access policy/app creation and staging enablement: **B6-G4/G5**. Break-glass credential generation/rotation requires a separate credential gate.

---

## B3. Explicit CORS and browser-origin policy

**Severity:** Medium

### Current behavior

No global CORS middleware is present, so cross-origin browser reads are not enabled. The policy is implicit and untested.

### Risk

A future middleware/UI change could accidentally add permissive CORS to admin or credential-bearing endpoints. Security depends on absence rather than a documented deny contract.

### Options

1. Leave CORS implicit.
2. Add a global exact-origin allowlist.
3. Explicitly reject browser `Origin` on native-client/admin API routes; allow only narrowly defined browser login/health surfaces.

### Recommended design

Adopt option 3. Admin API, license/device, update, download, and diagnostics upload routes remain non-browser APIs and must not return wildcard ACAO. Requests carrying `Origin` to sensitive native routes are rejected unless a route explicitly opts into an exact first-party origin.

The Access-protected admin login landing route is the only planned browser-facing admin surface.

### Acceptance criteria

- No sensitive route emits `Access-Control-Allow-Origin: *`.
- Unexpected Origin on admin/update/license/diagnostic upload fails closed.
- OPTIONS/preflight behavior is explicitly tested.
- Login route only allows the exact configured first-party origin if CORS is needed at all.

### Migration / rollback

Add tests first. Current CLI/native clients send no Origin, so the policy is backward-compatible. Rollback is local before staging; after staging, relaxing Origin checks requires B6-G5 approval.

### Independent authorization gate

**B6-G2**, then **B6-G5**.

---

## B4. Complete, purpose-separated rate limiting

**Severity:** High

### Current behavior

Rate limits exist on selected endpoints. In `admin.ts`, only license creation currently calls `enforceRateLimit()`. Rate-limit identity HMAC uses `DEVICE_TOKEN_PEPPER`.

### Risk

Other admin reads/writes can be hammered by a valid or stolen session. Reusing `DEVICE_TOKEN_PEPPER` couples device credential rotation to rate-limit identity derivation.

### Options

1. Add ad hoc limits to each missing admin route.
2. Add centralized route-class rate limits using existing `DEVICE_TOKEN_PEPPER`.
3. Add centralized admin/read/write/high-risk/login classes and a dedicated `RATE_LIMIT_PEPPER`.

### Recommended design

Adopt option 3.

Initial limits:

- Login start/exchange: 5 attempts / 5 minutes / IP.
- Authenticated admin read: 120 / minute / admin principal, plus IP safety limit.
- Standard admin mutation: 30 / minute / principal.
- High-risk release/license/key/diagnostic-delete mutation: 10 / minute / principal.
- Existing device/update/diagnostic limits remain unless acceptance data requires tuning.

Rate-limit keys use `RATE_LIMIT_PEPPER`, not device-token material.

### Acceptance criteria

- Every admin mutation is assigned a rate-limit class.
- 429 includes stable retry metadata.
- Limits cannot be bypassed by switching between endpoints in the same class.
- Rotation of device-token pepper does not change rate-limit identity keys.

### Migration / rollback

Introduce `RATE_LIMIT_PEPPER` in local tests first. Staging Secret creation is separate. Rollback can temporarily use the old derivation only in staging while preserving endpoint coverage.

### Independent authorization gate

Local: **B6-G2**. Staging Secret addition/tuning: **B6-G4/G5**.

---

## B5. Versioned key/secret rotation and purpose separation

**Severity:** Critical

### Current behavior

- Contact encryption has explicit key versioning and batch re-encryption support.
- Lease signing uses one current key ID/private key; Launcher can trust multiple public keys.
- Release signing uses key IDs and Launcher can trust multiple public keys.
- License/device/admin HMAC peppers are single active secrets.
- `DOWNLOAD_TICKET_SECRET` signs both update tickets and diagnostic upload tokens.
- Rate-limit identity uses `DEVICE_TOKEN_PEPPER`.

### Risk

Several secrets cannot be rotated without invalidating existing credentials, and unrelated purposes share key material.

### Options

1. Manual replace-and-invalidate rotation.
2. Keep current secrets but document maintenance windows.
3. Add versioned/overlap verification and split each security purpose into independent key material.

### Recommended design

Adopt option 3.

Required key classes:

- `LICENSE_KEY_PEPPER_Vn`
- `DEVICE_TOKEN_PEPPER_Vn`
- `ADMIN_SESSION_PEPPER_Vn`
- `CONTACT_LOOKUP_PEPPER_Vn`
- `CONTACT_ENCRYPTION_KEY_Vn` (existing pattern retained)
- `LEASE_SIGNING_KEY_ID` + overlapping old/new private/public trust transition
- release signing key IDs with overlapping trusted public keys
- `DOWNLOAD_TICKET_SECRET_Vn`
- **new** `DIAGNOSTIC_UPLOAD_SECRET_Vn`
- **new** `RATE_LIMIT_PEPPER_Vn`

Database rows that can be looked up by public token ID store secret-version metadata. License-key lookup, which starts from plaintext license key without row identity, computes digests for the bounded active pepper-version set during overlap. Old versions are retired only after explicit migration/expiry criteria.

Signing-key rotation sequence is add new public trust -> deploy trust overlap -> switch signer -> wait maximum acceptance/offline window -> retire old trust.

### Acceptance criteria

- Rotation can be performed without instantly invalidating active devices/licenses/admin sessions.
- Old/new overlap is bounded and observable.
- Diagnostic token and update ticket secrets are independent.
- Rate-limit and device-token peppers are independent.
- Contact encryption rotation remains resumable/idempotent.
- A documented emergency compromise path can revoke a key version immediately.

### Migration / rollback

Schema first with existing rows marked version 1. Add new Secrets without switching. Verify dual-read. Switch writers. Retire old versions only after staging drill. Rollback returns writers to prior version while both versions remain readable.

### Independent authorization gate

Code/schema: **B6-G2**. Any staging Secret add/switch/retire: **B6-G7**, with each switch/retire explicitly approved. Production rotation is Board 7/production scope.

---

## B6. Diagnostics consent, privacy, retention, and deletion

**Severity:** High

### Current behavior

Local diagnostics are opt-in and redacted. User explicitly generates, then explicitly submits. Worker upload sessions are device-authenticated, limited to 20 MiB, hash/size checked, and use a 15-minute upload token. `diagnostic_submissions.expires_at` is used both for upload-session validity and scheduled R2 retention cleanup. R2 key/custom metadata include license/device IDs.

### Risk

Upload-session TTL and retention policy are conflated; support may lose a valid diagnostic shortly after upload. Conversely, identifiers are unnecessarily present in R2 object paths/metadata. Consent version and cloud retention are not explicit policy fields.

### Options

1. Keep current 15-minute lifecycle.
2. Keep objects until manual admin deletion with a maximum cap.
3. Separate upload expiry from retention expiry, minimize R2 identifiers, and record consent version.

### Recommended design

Adopt option 3.

Policy:

- Upload session: 15 minutes.
- Cloud diagnostic content retention: maximum 7 days from completed upload.
- Admin may delete immediately after use.
- R2 object key: opaque `diagnostics/<YYYY-MM-DD>/<submission_id>.zip`; no license/device ID in path.
- R2 custom metadata: submission ID and content hash only.
- D1 retains relational identifiers needed for authorization/audit; after object deletion, status remains `deleted` for audit while content is gone.
- Client sends a fixed `consent_version`; UI displays maximum retention before submit.
- Local bundle remains local unless user explicitly submits; after successful upload the UI offers local deletion but does not silently delete without user intent.

### Acceptance criteria

- Upload token expires independently of retained object.
- Uploaded object survives the upload window and is deleted no later than retention expiry.
- No license/device identifier appears in new R2 object key/custom metadata.
- Explicit consent remains two-step.
- Scheduled cleanup is idempotent and leaves auditable deleted state.
- Admin download/delete remains scope-controlled and audited.

### Migration / rollback

Add `upload_expires_at`, `retention_expires_at`, and `consent_version` while preserving legacy `expires_at` interpretation for old rows. New rows use the new fields. Rollback continues cleaning legacy rows without deleting new content prematurely.

### Independent authorization gate

Local/schema: **B6-G2**. Staging D1 migration/R2 behavior: **B6-G4/G5**.

---

# C. Windows delivery integrity

## C1. pywebview backend/internal API dependency — frozen handoff #7

**Severity:** Medium-High

### Current behavior

`LauncherWindow._current_url_before_load()` calls `window.gui.get_current_url(uid)` to avoid the public loaded-gated URL call that deadlocked in Board 5. Dependency range is `pywebview>=6.2,<7`.

### Risk

An internal/backend method can change within the allowed minor range. A dependency update could cause Launcher fail-close destruction or reintroduce deadlock without a source-code change.

### Options

1. Keep the range and current internal call.
2. Pin the exact accepted pywebview version and wrap the backend dependency behind a compatibility adapter.
3. Replace the backend call with a documented public API/event contract if a supported pre-load URL path is available.

### Recommended design

Adopt option 2 immediately, with option 3 as the desired exit if verified against the dependency API during implementation. Pin the exact Board 5 accepted pywebview version until internal API use is removed.

Encapsulate URL inspection behind one adapter so the rest of Launcher does not depend on pywebview backend shape.

### Acceptance criteria

- Dependency is exact-pinned while internal API is used.
- Windows EdgeChromium integration test proves no before-load deadlock.
- External navigation destroys/fails closed.
- Missing backend capability fails with explicit diagnostic rather than hanging.

### Migration / rollback

Pin first, then adapter refactor. If a documented API replacement proves unstable, keep the pinned backend adapter; no security regression is needed to roll back.

### Independent authorization gate

**B6-G3**. Any dependency version upgrade beyond the accepted pin requires a separate dependency-upgrade approval/acceptance within B6-G3.

---

## C2. Authenticode publisher identity for app, Launcher, and installer

**Severity:** Critical

### Current behavior

Windows binaries are unsigned. Update integrity is protected by Ed25519 manifest signatures and SHA-256, but Windows does not see a trusted publisher identity and SmartScreen may warn.

### Risk

Initial bootstrap has no OS-recognized publisher identity. A signed update manifest proves possession of the release key, not Microsoft/Windows publisher identity. Formal Windows delivery requires both artifact provenance and platform trust.

### Options

1. Continue only Ed25519/SHA-256.
2. Use an exportable PFX certificate stored as a CI/local secret.
3. Use a hardware-backed or managed non-exportable production code-signing identity, with test certificates for local/staging pipeline development.

### Recommended design

Adopt option 3. Board 6 code must be signing-provider-neutral. Real signing identity/vendor selection occurs only under B6-G6.

Signing order is mandatory:

1. Build app/Launcher/installer.
2. Authenticode-sign Windows executables.
3. Verify Authenticode chain/publisher.
4. Package signed bytes.
5. Compute package SHA-256.
6. Create and Ed25519-sign release manifest.

Authenticode signing must occur **before** package hashing because signing modifies EXE bytes.

### Acceptance criteria

- App, Launcher, and installer each pass Windows signature verification.
- Production policy rejects unsigned/invalid-publisher candidate EXE before process start.
- Signed package SHA exactly matches Ed25519 manifest.
- Private signing key is never committed or exported into normal source artifacts.
- Build logs expose no credential/private-key material.

### Migration / rollback

Develop and test with a disposable test certificate under B6-G3. Real certificate use requires B6-G6. Staging may temporarily accept a pinned test publisher only in staging profile; production profile always requires production publisher identity.

### Independent authorization gate

Local test-signing code: **B6-G3**. Purchase/application/provision/use of real signing identity: **B6-G6**.

---

## C3. Launcher deployment trust profile integrity

**Severity:** Critical

### Current behavior

External `launcher-config.json` contains API origin, channel, fingerprint salt, release public keys, and lease public keys. Structural validation enforces HTTPS and key shape, but the file itself is not authenticated.

### Risk

Local tampering of this file can redirect credentials/API traffic and replace trusted release/lease public keys. Code-signing the Launcher alone does not protect an external mutable trust file.

### Options

1. Rely on filesystem ACLs and installer provenance.
2. Detached-sign `launcher-config.json` with a separate configuration signing key.
3. Embed all trust-critical deployment profile fields inside the signed Launcher artifact; keep external config only for non-security operational values.

### Recommended design

Adopt option 3.

Embed a build-time `DeploymentTrustProfile` inside the Launcher executable containing:

- environment (`staging` or `production`)
- exact API origin
- server-authoritative expected release channel policy
- release public-key registry
- lease public-key registry
- fingerprint salt
- expected Windows publisher identity/policy
- profile schema/version

External launcher config may retain port/UI/logging settings but cannot override trust-critical fields.

### Acceptance criteria

- Editing external config cannot change API origin, trust keys, channel policy, or publisher identity.
- Staging and production profiles are distinguishable and fail if mixed.
- Embedded profile supports overlapping release/lease public keys for rotation.
- Launcher refuses a missing/invalid profile before any credential-bearing network call.

### Migration / rollback

New Launcher supports schema v2 embedded profile and can read legacy config only in explicitly marked local/staging compatibility mode. Existing Board 5 evidence remains untouched. Rollback in staging can use the preserved Board 5 Launcher; production never enables legacy trust config.

### Independent authorization gate

**B6-G3**, staging profile acceptance under **B6-G5**.

---

## C4. Signed bootstrap/installer and runtime candidate verification

**Severity:** High

### Current behavior

Bootstrap delivery is a ZIP containing scripts, app, Launcher, config, and metadata. App/Launcher bytes are hash-checked in acceptance flows, but there is no signed installer executable and no Authenticode check before an extracted update candidate is launched.

### Risk

Initial user install has weak publisher UX and script-based trust. Runtime update verifies package hash/signature but does not independently require Windows publisher identity on the extracted executable.

### Options

1. Sign app/Launcher only and keep ZIP/scripts.
2. Sign PowerShell scripts and keep ZIP.
3. Build a signed bootstrap installer executable that reuses existing user-local installation semantics, and require runtime Authenticode verification for update candidates.

### Recommended design

Adopt option 3. Keep the current install/uninstall semantics as implementation logic, but package them behind a signed bootstrap executable. The signed installer contains or verifies the exact embedded scripts/resources; app and Launcher inside are also individually signed.

Add `wechat_cli/windows/authenticode.py` to verify candidate publisher before Launcher starts a newly extracted app.

### Acceptance criteria

- Initial setup artifact is a signed executable with expected publisher.
- Embedded app and Launcher signatures are valid.
- Update apply refuses unsigned/wrong-publisher candidate even when SHA/Ed25519 checks pass.
- Existing safe extraction/path traversal checks remain intact.
- Installer rollback leaves prior installed version recoverable.

### Migration / rollback

Keep ZIP bootstrap generation temporarily for test/backward compatibility, but mark it non-production. Production distribution only accepts signed installer. Runtime publisher check can be staged with a test publisher profile before real cert use.

### Independent authorization gate

Implementation: **B6-G3**. Real signed artifact: **B6-G6**.

---

# D. Integration & production boundary

## D1. Generic packaging dependency on Board 5 helper — frozen handoff #6

**Severity:** Medium

### Current behavior

`scripts/package_windows_app.py` imports `assert_outside_repository` from `scripts.board5_common`.

### Risk

A generic production packaging path depends on an acceptance-board helper, obscuring ownership and making selective integration difficult.

### Options

1. Keep the import permanently.
2. Duplicate the check inside package script.
3. Extract a generic packaging/path utility and let Board 5 helpers depend on it, not the reverse.

### Recommended design

Adopt option 3. Create a generic packaging utility with fail-closed output-boundary checks. Production packaging imports the generic module. Historical Board 5 scripts remain evidence and may import the generic helper only in the Board 6 integration branch if needed; no historical evidence commit is rewritten.

### Acceptance criteria

- Production package script contains no `board5_*` import.
- Output-inside-repository checks remain equivalent or stricter.
- Packaging tests prove repository root/subpaths are rejected and repo-external output is accepted.

### Migration / rollback

Port behavior with tests before removing the old import. Rollback restores the old local helper only on the Board 6 branch; main remains untouched until integration approval.

### Independent authorization gate

**B6-G0**.

---

## D2. Selective source integration debt — frozen handoff #8

**Severity:** Critical

### Current behavior

Frozen main is `a579a25...`. Board 5 branch contains both product changes and acceptance-only tooling/docs. Product lineage includes 0.5.1 packaging and fixes such as `56d065e`, `706bcbe`, `a771ab4`, `8a1fdb0`, `29aba6b`; acceptance-only commits include Board 5 sandbox/probe helpers.

### Risk

Merging the entire Board 5 branch would import acceptance-specific code/debt into product main. Implementing Board 6 directly on Board 5 would further entangle product and evidence history.

### Options

1. Merge Board 5 branch wholesale into main.
2. Continue Board 6 directly on Board 5 branch.
3. Create a fresh Board 6 integration worktree from frozen main and selectively replay audited product changes, reconstructing generic packaging changes without acceptance-only dependencies.

### Recommended design

Adopt option 3.

Proposed integration classification:

**Direct product candidates:**
- `84b8a99` — 0.5.1/update-only packaging baseline
- `56d065e` — Windows file URL normalization
- `706bcbe` — pre-load deadlock repair
- `a771ab4` — update download identification
- `8a1fdb0` — private asset redirect handling (retained during R2 migration)
- `c4d44ee` / `fc667cf` — safe upstream diagnostics
- `29aba6b` — Windows process-tree/port-release repair

**Do not wholesale integrate as product:**
- `ad753f6` Board 5 acceptance helper boundary
- `538ae3a` Board 5 acceptance tools
- `52e07b8` Board 5 probe helper

`28415ca` bootstrap-only packaging behavior should be ported selectively into generic packaging code while removing the `board5_common` dependency rather than blindly cherry-picking its acceptance coupling.

### Acceptance criteria

- Board 6 starts from a fresh worktree based on exact frozen main.
- Every replayed commit/file has a provenance entry and reason.
- Acceptance-only helpers are not required by production runtime/build paths.
- Full Python/Worker/packaging tests pass on the integrated baseline before Board 6 security changes begin.
- Main remains unchanged until a later explicit merge gate.

### Migration / rollback

Integration happens on a disposable/managed Board 6 worktree. If any replay fails review, discard that Board 6 worktree/branch only after explicit cleanup authorization; main remains frozen and Board 5 evidence remains intact.

### Independent authorization gate

**B6-G0**. Any later merge to main is separately authorized and is not implied by Board 6 completion.

---

## D3. Fail-closed staging / production deployment isolation

**Severity:** Critical

### Current behavior

Wrangler has distinct staging/production env blocks and distinct D1/R2 names. However the top-level Worker name is `wechat-cli-license-update`, the same name used for production, `workers_dev` is globally true, and production D1 contains `REPLACE_WITH_PRODUCTION_D1_ID`.

### Risk

A raw `wrangler deploy` without `--env` can target a production-named Worker with local/default configuration. Placeholder production resources and shared command patterns make operator error a credible production risk.

### Options

1. Rely on operator discipline and documentation.
2. Rename only the top-level dev Worker and keep direct Wrangler commands.
3. Separate environment identities and introduce a fail-closed deployment preflight/wrapper; raw deployment is not an approved production path.

### Recommended design

Adopt option 3.

Required boundary:

- Top-level/local Worker name must not equal production name.
- Staging and production Worker names, D1, diagnostics R2, release R2, Access audience, domains, and Secrets are distinct.
- Production `workers_dev` exposure is disabled; production uses an explicit custom hostname/route when Board 7 provisions it.
- Deployment tool requires explicit `--environment staging|production` and refuses placeholders, duplicate resource IDs/names, missing required Secret declarations, and environment/profile mismatch.
- Production deployment requires a separate typed confirmation/authorization gate and cannot be inferred from staging success.

### Acceptance criteria

- Running deployment wrapper without environment fails.
- Local/default config cannot deploy to production-named Worker.
- Static preflight detects placeholder/duplicate staging-production resources.
- Staging Launcher profile refuses production API origin and vice versa.
- No production Cloudflare mutation is needed to prove the local guard logic.

### Migration / rollback

First change local config/tooling only. Staging wrapper adoption happens under B6-G4/G5. Production values remain unprovisioned until Board 7. Rollback returns staging deployment tooling only; production remains untouched.

### Independent authorization gate

Local tooling: **B6-G2 or B6-G3** as implementation planning dictates. Staging resource/config mutation: **B6-G4**. Production provisioning/deploy: Board 7 production gate.

---

## D4. Production ingress, domain, and China-delivery boundary

**Severity:** Medium-High

### Current behavior

Staging is exposed through Worker infrastructure. Production custom-domain/Access/China mainland domain and备案 strategy is not finalized. Board 6 roadmap explicitly calls for a formal domain/备案 decision.

### Risk

Security controls can be bypassed if production remains on an unintended public workers.dev route. China mainland accessibility/compliance may later force architecture changes if not separated from core API trust assumptions.

### Options

1. Use workers.dev for production.
2. Use a dedicated global production custom domain with Cloudflare Access protecting admin login/admin ingress; treat mainland hosting/备案 as a separate commercialization track.
3. Require mainland-hosted/备案 infrastructure before any formal release.

### Recommended design

Adopt option 2 for the software architecture. Board 6 defines a production custom-domain contract and disables production workers.dev exposure. Mainland hosting/备案 is documented as an external delivery prerequisite if mainland formal distribution is required, but it is not mixed into the cryptographic/update protocol.

### Acceptance criteria

- Admin login/admin API production policy is tied to the production hostname/Access audience.
- Launcher production profile contains the exact production API origin.
- No security decision depends on DNS names being interchangeable between staging and production.
- A written external prerequisite states when备案/mainland hosting becomes release-blocking.

### Migration / rollback

No domain purchase/DNS/备案 action occurs during local Board 6 implementation. Staging domain/Access changes require B6-G4. Production domain actions remain Board 7/external gate.

### Independent authorization gate

Design/local validation under Board 6. Any domain purchase, DNS mutation, Access production policy, or备案 application requires a separate external/production authorization gate.

---

# 6. Cross-domain security invariants

The recommended design is accepted only if all of the following remain true:

1. **Server is authoritative for release eligibility.** Client config can narrow/expect, never broaden license entitlement.
2. **Every executable trust layer is independent.** Ed25519 manifest signature + package SHA-256 + Windows Authenticode publisher verification are all required for production updates.
3. **Trust-critical Launcher configuration is inside the signed artifact.** Mutable external config cannot replace API origin or trust roots.
4. **Production runtime update distribution carries no GitHub read credential.** GitHub remains provenance; R2 is distribution.
5. **Normal admin use has no long-lived bearer credential.** Short-lived sessions and audited identity are required.
6. **Secrets are purpose-separated and version-rotatable.** No new cross-purpose secret reuse is allowed.
7. **Diagnostics are opt-in, minimized, time-bounded, and deletable.** Upload TTL is not retention TTL.
8. **Staging and production are structurally non-interchangeable.** Names, resources, trust profiles, credentials, and deployment gates are distinct.
9. **Board 5 evidence remains immutable.** Board 6 uses a fresh integration lineage; no historical rewrite.
10. **No implementation gate implies the next gate.** Cloud, signing, credential, release, merge, and production effects each require explicit authorization.

# 7. Board 6 completion definition

Board 6 may be called `accepted complete` only after separately authorized implementation gates have produced evidence for:

- selective source integration baseline accepted on a fresh Board 6 worktree;
- A-domain server-authoritative channel and exact failed-candidate behavior;
- R2 staging distribution accepted while GitHub remains immutable provenance;
- short-lived admin session flow accepted in staging;
- explicit CORS and complete rate-limit coverage accepted;
- versioned key/secret rotation code accepted and at least one staging overlap rotation drill completed;
- diagnostics retention/privacy policy accepted against staging D1/R2;
- pywebview compatibility contract pinned/accepted;
- app + Launcher + installer code-signing pipeline implemented and a real staging-signed artifact accepted under B6-G6;
- embedded deployment trust profile accepted;
- staging/production deployment guard tooling accepted with no production mutation;
- full Python/Worker/Windows packaging/security tests pass;
- final Board 6 acceptance report records what was and was not mutated;
- Board 7 remains separately gated.

# 8. Current authorization boundary

This design and the companion implementation plan are approved, but approval of the documents never authorizes a gate by itself. **B6-G0 and B6-G1 have each been separately authorized and completed locally. B6-G2 is pending approval.**

Current B6-G1 closure/governance update does not authorize:

- any B6-G2 or later implementation code change;
- push or merge to main;
- reset, rebase or amend of the Board 6 lineage;
- Worker deployment or staging behavior change;
- creation/modification of D1/R2/Access/DNS resources;
- rotation/addition/removal of a real Secret;
- removal of `GITHUB_RELEASE_READ_TOKEN`;
- code-signing purchase/application or use of a real signing identity;
- publication of a new GitHub release/tag;
- registration or enablement of a new Worker release;
- production provisioning/mutation;
- Board 7 entry.

The next possible implementation gate is **B6-G2 Admin & Data Security Local Gate**, and it requires a new explicit user authorization after this B6-G1 closure.
