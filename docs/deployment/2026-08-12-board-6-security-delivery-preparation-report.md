# Board 6 Security & Delivery Preparation Final Acceptance Report

Final closure verification: 2026-08-15

Branch: `board6/security-delivery-preparation`

Board 6 closure basis: **Private / Controlled Distribution**. Commercial Authenticode procurement, identity verification, managed/HSM key provisioning, publisher-policy activation, and real commercial signing are explicitly deferred optional hardening for a future Public / Formal Distribution profile and are not Board 6 closure blockers under the approved scope amendment.

## 1. Final conclusion

**Board 6 is accepted complete.**

B6-G0 through B6-G8 have satisfied the mandatory Board 6 exit conditions for the approved Private / Controlled Distribution profile. The accepted system now has server-authoritative update eligibility, immutable release provenance plus controlled runtime transport, short-lived administrator access, explicit Origin/rate controls, diagnostics privacy/retention behavior, reversible staging key rotation evidence, embedded deployment trust, Windows integrity/signing capability boundaries, and fail-closed staging/production isolation.

No production deployment or production credential provisioning was performed by Board 6. Frozen `main` remains `a579a25cb7f16e6fdf88d618252b4a5cbffef53d`; Board 5 accepted evidence remains `67d3dec0fd1c4a02c87be1ab79c4f78ea63f49d6`.

Board 7 remains unstarted and requires a separate design/production authorization gate.

## 2. Scope and authorization matrix

| Gate | Result | Primary evidence |
|---|---|---|
| B6-G0 Source Integration | complete | `docs/superpowers/governance/2026-08-12-board-6-source-integration-provenance.md`; integration through `c1d0458` |
| B6-G1 Update Trust Local | complete | `a23b6ff`, `988a504`, `bdc98af` |
| B6-G2 Admin & Data Security Local | complete | implementation through `e0c91df` |
| B6-G3 Windows Integrity Local | complete | implementation through `1a07447`; audit `d73cf3f` |
| B6-G4 Staging Infrastructure | complete | `docs/superpowers/governance/2026-08-14-board-6-staging-infrastructure-gate.md` |
| B6-G5 Staging Behavior Acceptance | accepted complete | `docs/superpowers/governance/2026-08-14-board-6-staging-behavior-acceptance.md` |
| B6-G6 Provider-neutral signing readiness | complete for current profile | `9f4ad0f`, `e9cb67b`; dormant optional adapter `50e7074`; Private / Controlled amendment `ebd3378` |
| B6-G7 Staging Key Rotation Drill | accepted complete | `docs/superpowers/governance/2026-08-14-board-6-key-rotation-preflight.md`; closure commit `f2202b5` |
| B6-G8 Final Closure | accepted complete | this report plus fresh 2026-08-15 verification |

## 3. Source integration provenance

Board 6 was created from frozen main `a579a25cb7f16e6fdf88d618252b4a5cbffef53d` and selectively integrated only audited Board 5 candidates. The Board 5 accepted evidence worktree remains at `67d3dec0fd1c4a02c87be1ab79c4f78ea63f49d6`; its two retained untracked Board 6 seed drafts remain present and were not deleted. Main remains at the same frozen commit with the historical untracked `NUL` entry preserved.

The generic packaging/source-boundary cleanup was completed under B6-G0 before later security work. No reset, rebase, amend, history rewrite, push, or merge was performed as part of Board 6.

## 4. A-domain acceptance — update trust boundary

The A-domain acceptance is complete for the current profile:

- update channel authority is server-side and tied to the authenticated license rather than trusting a client-selected channel;
- failed-candidate suppression and release immutability semantics were tightened and accepted in real staging;
- GitHub is retained as immutable provenance while R2 is supported as the controlled runtime distribution backend;
- redirect/runtime transport boundaries were tightened and exercised in staging;
- existing stable release rows remain unchanged and enabled; fault/acceptance release rows remain in their approved disabled/paused terminal states.

Fresh B6-G8 D1 readback on 2026-08-15 showed:

- `rel_staging_050`: stable, GitHub backend, enabled, not paused, rollout 100, package SHA-256 `406b72c14ad186141f373087595f7723e143b9638bf298fde23b6bb0ae057523`;
- `rel_staging_051`: stable, GitHub backend, enabled, not paused, rollout 100, package SHA-256 `0ddbb0b402cc9d98ed001391c1a618527d165e328a1f4f1534d80e6b984956c0`;
- Board 5 fault release remains disabled/paused;
- Board 6 G5 acceptance release remains disabled/paused and uses the R2 backend.

All final reconcile queries were read-only with `rows_written=0`.

## 5. B-domain acceptance — credentials, admin security, rate/origin, diagnostics

Board 6 accepted the Cloudflare Access-backed administrator identity/session boundary, short-lived administrator sessions, exact scope enforcement, recent-auth requirements for high-risk operations, explicit Origin/CORS handling, and purpose-separated rate limits.

B6-G7 then proved real staging credential rotation behavior:

- Admin session pepper final state: current V2, readable V1+V2;
- Download ticket secret final state: current V2, readable V1+V2;
- Contact encryption final state: V2 with lookup pepper retained at V1;
- all V1 materials remain present; no V1 retirement was performed.

The contact-encryption drill discovered a real D1 BLOB runtime-shape incompatibility. The repair accepts only strict byte arrays with integer values `0..255`, preserving fail-closed behavior for malformed values; it was TDD-reproduced, repaired, deployed to staging, and proven through reversible V1→V2→V1→V2 contact migration.

Diagnostics acceptance includes explicit consent metadata, bounded upload size, separate upload and retention deadlines, exact seven-day retention, administrative download/delete behavior, and idempotent retention cleanup based on `retention_expires_at`. The G5 disposable diagnostic object/row was deleted at cleanup.

Fresh B6-G8 D1 readback confirms `admin_board6_g5_primary` is back in its exact pre-G7 terminal state: status `revoked`, original scopes only, `revoked_at='2026-08-14 11:18:29'`; all nine sessions under that principal are revoked.

## 6. C-domain acceptance — Windows delivery integrity and signing boundary

Board 6 completed the provider-neutral Windows integrity path:

- pywebview compatibility is pinned and the pre-load/runtime boundary is explicit;
- Launcher deployment trust is embedded rather than delegated to mutable external configuration;
- Authenticode inspection and public signer/timestamp evidence are deterministic;
- Windows app/Launcher/installer signing-provider abstractions and signed-artifact verification paths exist;
- installer/runtime packaging and trust validation are covered by the full test suite;
- a real Microsoft-signed system binary was successfully inspected during B6-G6 readiness verification.

For the current **Private / Controlled Distribution** profile, `windows_publisher_policy` is intentionally empty. Remote update integrity instead remains mandatory through Ed25519 manifest signatures, exact package SHA-256/size verification, server-authoritative eligibility, safe extraction, health checks, rollback, and failed-candidate suppression.

### Real signing identity status

No commercial signing identity was purchased, applied for, KYC-verified, provisioned, or used. No production publisher identity was configured. The optional SSL.com adapter remains dormant and unconfigured.

This is an intentional accepted limitation of the current private profile, not an assertion that real commercial code signing occurred.

## 7. D-domain acceptance — integration and production boundary

Board 6 closed the source integration and packaging-dependency risks locally, separated staging/production worker/resource identities, and added fail-closed deployment preflight.

Fresh B6-G8 production preflight returned exit code 2 with:

`production D1 binding contains a placeholder`

This is the intended result: production D1 and production route configuration remain deliberately incomplete and therefore cannot be accidentally treated as deployment-ready.

Fresh staging checks showed no pending D1 migrations, the staging D1/R2 bindings remain distinct, and the final live Worker Version is `633945cb-0103-4fb0-9ccf-7a9c797e6de5`.

Both live staging health origins returned HTTP 200 with `environment=staging` on 2026-08-15:

- `wechat-cli-license-update-staging.aurevior-ai.workers.dev`;
- `wechat-cli-admin-staging.aurevior-devspace.com`.

## 8. Staging cloud mutations actually performed by Board 6

Board 6 performed only the separately authorized staging mutations required by its gates, including:

- creation/use of the dedicated staging release R2 bucket;
- application of D1 migrations `0004`–`0007`;
- provisioning of Board 6 staging Secret names and Access/JWT/custom-domain configuration;
- repeated staging Worker deployments required by G4/G5 acceptance repairs and G7 rotation switch/rollback proofs;
- disposable G5/G7 acceptance licenses, devices, administrator principal/sessions, diagnostics and release evidence;
- G7 V2 Secret additions for Admin session HMAC, download tickets, and contact encryption;
- temporary lease signing-key switch to `lease-key-staging-02` followed by exact atomic restoration to `lease-key-staging-01`.

All disposable G7 resources were returned to their approved terminal states. Fresh B6-G8 readback confirmed both G7 licenses revoked, the G7 device unbound, all administrator sessions revoked, and the administrator principal restored exactly.

## 9. Credential rotations actually performed

B6-G7 demonstrated overlap/switch/rollback/re-switch behavior rather than destructive retirement:

- `ADMIN_SESSION_PEPPER_V1` + `V2`: final current V2, readable V1,V2;
- `DOWNLOAD_TICKET_SECRET_V1` + `V2`: final current V2, readable V1,V2;
- `CONTACT_ENCRYPTION_KEY_V1` + `V2`: final encryption version V2; V1 retained;
- `lease-key-staging-01` + temporary `lease-key-staging-02`: old/new leases verified under overlap trust, then exact live rollback to key-01;
- `release-key-staging-01` + local-only `release-key-staging-02`: old/new manifest signatures verified under overlap trust without publication; retained publisher and accepted trust remain key-01.

No V1 Secret/private recovery/public-trust material was retired.

## 10. Fresh B6-G8 verification

Fresh closure verification on 2026-08-15 produced:

- Python: **648 tests run, 2 expected skips, 0 failures**;
- Worker TypeScript: **typecheck PASS**;
- Worker Vitest: **14 files / 93 tests PASS**;
- deployment-preflight suite: **26/26 PASS**;
- staging D1 migrations: **none pending**;
- live staging Worker Version: `633945cb-0103-4fb0-9ccf-7a9c797e6de5`;
- live Admin session selector: current `2`, readable `1,2`;
- live Download ticket selector: current `2`, readable `1,2`;
- live Contact encryption selector: `2`;
- live Lease signer: `lease-key-staging-01`;
- relevant V1 and V2 Secret names are still present;
- two staging health origins: HTTP 200 / `environment=staging`;
- production deployment preflight: fail-closed on placeholder D1 as intended;
- Board 5 evidence worktree: exact HEAD `67d3dec0fd1c4a02c87be1ab79c4f78ea63f49d6`;
- main: exact HEAD `a579a25cb7f16e6fdf88d618252b4a5cbffef53d`;
- tracked non-test source/docs scan: zero complete WCL license-key, device-token, admin-session-token, legacy-admin-token, PAT, or private-key-block shapes;
- the only Secret-assignment scan hit was `.dev.vars.example`, containing explicit `replace-with-...` placeholders only.

## 11. Deferred items

The following remain intentionally deferred and are not Board 6 blockers under the current profile:

- commercial Authenticode provider/publisher selection;
- provider payment/subscription, KYC, certificate or managed/HSM key provisioning;
- production `windows_publisher_policy` activation;
- real commercial signing of app/Launcher/installer artifacts;
- V1 Secret/key/public-trust retirement after real compatibility windows;
- optional cleanup of repo-external G7 probe files and the known failed 27-byte empty rollback-env artifact;
- optional physical cleanup of retained Board 5 evidence worktrees/drafts;
- a dedicated product capability to clean historical G5 device rows whose parent disposable licenses are already revoked.

The last item is a row-level cleanup residual only; the parent licenses are revoked and it is not an active authorization path.

## 12. Explicit actions not performed

Board 6 did **not**:

- provision or deploy production;
- write production Secrets or production D1/R2 data;
- create a production route/domain/cutover;
- purchase/apply for/use a commercial code-signing identity;
- retire V1 credential or signing trust material;
- publish/register/enable a release solely for the G7 release-key proof;
- rewrite Git tags/history;
- push or merge the Board 6 branch;
- reset, rebase, or amend the Board 6 lineage;
- delete the retained Board 5 seed drafts;
- delete or commit the historical main/worktree `NUL` entry.

## 13. Board 7 entry conditions

Board 7 remains a separately gated production program. Before any Board 7 production provision/deploy/cutover action, require a new approved design/implementation gate covering at minimum:

1. production Worker/D1/R2/domain/route topology and exact isolation from staging;
2. production Access/admin identities, scopes, recovery/break-glass policy and Secret provisioning;
3. production deployment trust profile and immutable release/public-key lifecycle;
4. production release publication/registration/rollout/cutover/rollback procedure;
5. production diagnostics/privacy/retention operations;
6. production key-rotation and emergency-revoke runbooks;
7. whether distribution remains Private / Controlled or activates Public / Formal Distribution;
8. if Public / Formal is activated, a separate commercial code-signing provider/publisher/payment/KYC/key-provisioning/signing approval;
9. explicit push/merge/release authorization as applicable.

No Board 7 production action is implied by Board 6 acceptance.

## 14. Final Board 6 state

**Board 6: accepted complete.**

The accepted closure profile is **Private / Controlled Distribution** with commercial Authenticode deferred optional hardening. Staging remains the only live Board 6 environment. Production remains fail-closed and unprovisioned by Board 6. Board 7 is unstarted pending separate authorization.
