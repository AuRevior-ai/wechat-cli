# Board 6 Staging Infrastructure Gate Report

Date: 2026-08-14

Status: **B6-G4 STAGING INFRASTRUCTURE COMPLETE — B6-G5 NOT AUTHORIZED**

## 1. Scope and authorization boundary

B6-G4 was separately authorized for staging-only infrastructure required to make the Board 6 controls testable. The approved scope covered the dedicated staging `RELEASES` R2 bucket/binding, Board 6 D1 migrations `0004`–`0007`, exact new versioned staging Secret names/values, staging Cloudflare Access application/policy/verifier configuration, and the staging Worker deployment required for those controls.

The gate did **not** authorize production mutation, GitHub release publication/enablement, a new acceptance release, real code-signing procurement/use, production provisioning, push/merge, Board 5 evidence cleanup, or B6-G5 behavior acceptance.

Frozen references remained unchanged:

- frozen main: `a579a25cb7f16e6fdf88d618252b4a5cbffef53d`
- Board 5 accepted-complete evidence: `67d3dec0fd1c4a02c87be1ab79c4f78ea63f49d6`
- Board 6 branch: `board6/security-delivery-preparation`
- B6-G3 closure: `b17d007d5959f1074c882130b8a82114a8777dee`

The unrelated Board 6 worktree `?? NUL` entry remained untouched.

## 2. Read-only cloud preflight

Wrangler OAuth was restored by the user before cloud work resumed. The read-only account preflight confirmed:

- staging Worker: `wechat-cli-license-update-staging`
- staging D1: `wechat-cli-license-staging`
- staging D1 UUID: `fa55ac90-8de1-4a69-a8c7-a1997ba02afb`
- existing staging diagnostics R2: `wechat-cli-diagnostics-staging`
- `wechat-cli-releases-staging` did not yet exist before this gate
- the staging Worker initially had exactly the eight Board 4/5 legacy Secret names and no Board 6 `_V1` names
- remote D1 had exactly migrations `0004`–`0007` pending
- Board 5 release rows were read-only frozen before mutation

The pre-mutation release readback had `rows_written=0` and matched the accepted Board 5 state.

## 3. Staging R2 and D1 mutations

### 3.1 Dedicated release R2

Created exactly:

`wechat-cli-releases-staging`

Post-create R2 list contained:

- `wechat-cli-diagnostics-staging`
- `wechat-cli-releases-staging`

No production bucket was created or modified.

### 3.2 Board 6 D1 migrations

Applied remotely to `wechat-cli-license-staging`, in order:

1. `0004_release_distribution.sql`
2. `0005_admin_sessions.sql`
3. `0006_diagnostics_retention.sql`
4. `0007_secret_versions.sql`

Fresh post-migration readback returned `No migrations to apply`.

Compatibility readback confirmed the three existing Board 5 release rows remain `distribution_backend='github'` with no R2 object key, and existing license/device secret-version fields remain version 1.

## 4. Staging Secret migration

Seven new purpose/version-specific staging Secret names were added without deleting, switching away from, or rotating the legacy names:

- `LICENSE_KEY_PEPPER_V1`
- `DEVICE_TOKEN_PEPPER_V1`
- `ADMIN_SESSION_PEPPER_V1`
- `CONTACT_LOOKUP_PEPPER_V1`
- `DOWNLOAD_TICKET_SECRET_V1`
- `DIAGNOSTIC_UPLOAD_SECRET_V1`
- `RATE_LIMIT_PEPPER_V1`

Continuity-sensitive version-1 values were copied from the restricted repo-external legacy source for:

- license-key pepper
- device-token pepper
- contact-lookup pepper
- download-ticket secret

The user performed those four transfers locally without exposing values in chat. The three new purposes — admin-session, diagnostic-upload, and rate-limit — were generated independently with fresh high-entropy values. No Secret value is recorded in this report.

Fresh staging Secret-name readback contains 15 names total: the eight retained legacy/compatibility names plus all seven Board 6 `_V1` names.

## 5. Cloudflare Access staging boundary

The user created the staging self-hosted Access application in the Zero Trust dashboard:

- application name: `WeChat CLI Staging Admin Login`
- protected target: `wechat-cli-admin-staging.aurevior-devspace.com/v1/admin/login/start`
- policy: `WeChat CLI Staging Admin`
- action: Allow
- identity selector: one approved administrator email only
- session duration: 30 minutes

Safe verifier metadata supplied by the user and bound in staging source configuration:

- Access team domain / JWT issuer: `https://floral-glitter-1ede.cloudflareaccess.com`
- JWKS: `https://floral-glitter-1ede.cloudflareaccess.com/cdn-cgi/access/certs`
- Access AUD: `12ce8ebd33213a9c532ba90144d8bf0dc5df851c289071be5484d9cc751eb6fb`
- identity claim: `email`
- exact admin origin: `https://wechat-cli-admin-staging.aurevior-devspace.com`

The team-domain JWKS endpoint returned HTTP 200 with two keys during B6-G4 read-only verification.

The staging Worker source now declares the admin hostname as an exact Workers Custom Domain. Access protects only `/v1/admin/login/start`; the one-time-code exchange route is intentionally not placed behind the Access browser challenge.

## 6. B6-G4 local deployment tooling

Three local Board 6 commits were added before the successful deployment:

- `14db869` — `feat: add staging only worker deploy gate`
- `332c41a` — `feat: bind staging access deployment boundary`
- `86da5a5` — `fix: resolve wrangler executable on windows`

The deploy wrapper now:

- exposes deployment only for `environment=staging`
- runs full preflight before invoking Wrangler
- prints safe target metadata only
- requires D1/R2 declarations, exact required Secret names, staging trust profile/API-origin match, Access issuer/JWKS/audience/identity/origin configuration, and an exact custom-domain route
- rejects workers.dev as the Access admin origin
- keeps production deployment unavailable
- allows staging preflight while production D1/routes intentionally remain unprovisioned, while production preflight itself still rejects those placeholders
- resolves the real `npx` executable on Windows before launching Wrangler

The first real deploy attempt performed no Worker mutation because Windows failed before Wrangler could launch when the wrapper used a bare `npx`. The TDD fix in `86da5a5` closed that defect before retry.

## 7. Repo-external staging trust profile

Created the non-secret Board 6 staging trust profile at:

`D:\use_as_desktop\Wechat__CLI\staging-secrets-20260805\board6\deployment-trust-profile.json`

SHA-256:

`6cb133cdea39688045ce92a0600eccfc173f866c64c03f98a6d44d6aaa7cead5`

It preserves the accepted Board 5 stable staging fingerprint salt and the exact public-key IDs:

- release: `release-key-staging-01`
- lease: `lease-key-staging-01`

Its API authority is the existing staging workers.dev API and expected channel is `stable`. `windows_publisher_policy` remains empty intentionally because real Authenticode identity/signing is deferred to B6-G6.

## 8. Fresh local verification before deployment

Deployment-policy/preflight suite:

- 27 tests
- 27 passed
- 0 failures

Full Python:

- 612 tests run
- 2 expected skips
- 0 failures
- result: `OK`

Worker:

- TypeScript typecheck: PASS
- Vitest: 13 files / 89 tests PASS

Wrangler dry-run:

- PASS
- resolved the exact staging D1 binding
- resolved both staging R2 bindings
- resolved the five Access verifier/origin vars
- resolved all version selectors
- performed no deploy mutation

`git diff --check` passed before each local commit. Targeted sensitive-shape scanning found no real credential/private-key/session-token values in the source diff.

## 9. Staging Worker deployment

The successful deployment was executed only through the staging-only wrapper after its preflight passed.

Deployed Worker:

`wechat-cli-license-update-staging`

Cloudflare Version ID:

`14a19ea3-5a96-408b-a4e3-0a8d8e4ebe2c`

Routes/triggers reported by Wrangler:

- `https://wechat-cli-license-update-staging.aurevior-ai.workers.dev`
- `wechat-cli-admin-staging.aurevior-devspace.com` custom domain
- cron `17 * * * *`

## 10. Post-deploy read-only reconcile

Fresh health:

- workers.dev `/v1/health`: HTTP 200, `environment=staging`
- admin custom-domain `/v1/health`: HTTP 200, `environment=staging`

Ingress isolation:

- unauthenticated custom-domain `/v1/admin/login/start`: HTTP 302 from the Access edge
- workers.dev `/v1/admin/login/start`: HTTP 403, proving the alternate public ingress cannot bypass the exact Access admin origin

Cloud resources:

- R2 list contains exactly the expected staging diagnostics/release buckets
- remote D1: no migrations pending
- staging Secret names: all required Board 6 and retained compatibility names present
- current staging deployment: Version ID `14a19ea3-5a96-408b-a4e3-0a8d8e4ebe2c`

Historical release reconcile remained unchanged and read-only (`rows_written=0`):

- `rel_staging_050`: enabled, unpaused, rollout 100, accepted hashes/size unchanged, legacy GitHub backend
- `rel_staging_051`: enabled, unpaused, rollout 100, accepted hashes/size unchanged, legacy GitHub backend
- `rel_board5_bad_052_01`: disabled, paused, rollout 100, accepted hashes/size unchanged, legacy GitHub backend

No R2 acceptance release object was created and no existing release was registered, published, enabled, disabled, or otherwise mutated under B6-G4.

## 11. Explicit deferred staging acceptance setup

Fresh D1 readback after deployment shows:

- `admin_principals`: 0 rows
- `admin_sessions`: 0 rows

This is deliberate evidence, not an implicit authorization to write a principal. A real Access login cannot mint a short-lived session until one approved Access identity is mapped to an enabled staging `admin_principals` row.

That principal provisioning is therefore an explicit B6-G5 acceptance-setup mutation and must be named in the B6-G5 authorization matrix before execution. B6-G4 does not create it.

## 12. External side-effect statement

B6-G4 performed only the approved staging infrastructure mutations described above. It performed no:

- production Worker/D1/R2/Access/DNS/Secret mutation
- GitHub release publication or tag mutation
- Worker release register/enable mutation
- real code-signing certificate purchase/provision/use
- real signed Windows artifact acceptance
- staging admin-principal/session behavior acceptance
- push or merge
- Board 5 evidence cleanup

## 13. Gate conclusion

B6-G4 Staging Infrastructure Gate is **complete**. The Board 6 staging infrastructure is deployed and fail-closed boundaries are live.

The next possible gate is **B6-G5 Staging Behavior Acceptance Gate**. B6-G5 must be separately authorized and its exact mutation matrix must include any staging admin-principal provisioning, disposable licenses/devices/diagnostic objects, and any acceptance release publication/register/enable operations that are actually required. No B6-G5 action is authorized by this report.
