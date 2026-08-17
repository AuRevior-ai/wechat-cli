# Board 7 Production Automation & Controlled Launch Final Acceptance Report

Final closure verification: 2026-08-17

Closure branch: `board7/final-production-closure-g9`

G9 base canonical main: `a685fcfa24fd1ae2336a5286642affab87b6a85d` (B7-G8 governance closure PR #24)

Distribution profile: **Private / Controlled Distribution**

## 1. Final conclusion

**Board 7 satisfies the mandatory production, automation, canary, recovery, controlled-issuance, and final-verification conditions for accepted completion under the approved Private / Controlled Distribution profile.**

B7-G0 through B7-G8 were independently accepted before entry to B7-G9. B7-G9 then ran fresh full verification, live production read-only reconciliation, historical-boundary verification, and tracked sensitive-value scanning from exact canonical main `a685fcfa24fd1ae2336a5286642affab87b6a85d` before this final report was authored.

The resulting production system remains deliberately narrow:

- exact custom API/Admin host separation;
- one production Worker deployment with independently provisioned production D1/R2 resources;
- one human administration principal and one least-privilege automation principal;
- machine publication authority without machine release-state authority;
- R2 runtime distribution with private GitHub provenance;
- stable `0.6.0` first-install baseline and internal `0.6.1-canary.1` update acceptance;
- exactly one long-lived internal beta canary license/device;
- exactly one first controlled stable Private license, with zero stable device bindings and no third-party handoff;
- recovery/rollback and credential-emergency runbooks accepted;
- commercial Authenticode still explicitly deferred.

No production mutation was performed merely to satisfy B7-G9 closure.

The final history-preserving merge commit produced by the closure PR is intentionally not hard-coded in this report because it does not exist until after this report is committed and merged. It is read back as the last canonical-integration step before the external completion claim.

## 2. Scope and authorization matrix

Board 7 was executed under the approved design, implementation plan, and Strong Authorization amendment:

- design: `docs/superpowers/specs/2026-08-15-board-7-production-automation-controlled-launch-design.md`;
- plan: `docs/superpowers/plans/2026-08-15-board-7-production-automation-controlled-launch.md`;
- Strong Authorization amendment: `docs/superpowers/specs/2026-08-15-board-7-strong-authorization-design-amendment.md`.

The gate sequence was:

| Gate | Accepted scope |
|---|---|
| B7-G0 | production design, authorization matrix, implementation plan |
| B7-G1 | local production hardening and TDD only |
| B7-G2 | history-preserving source integration |
| B7-G3 | clean-room production infrastructure provision |
| B7-G4 | production human/machine identities, runtime Secrets, signing keys, GitHub publisher identity |
| B7-G5 | exact production Worker deployment and ingress/Access acceptance |
| B7-G6 | CI/CD publication automation acceptance and stable `0.6.0` release preparation |
| B7-G7 | one-device internal beta canary E2E, diagnostics, real update/fault/rollback/suppression |
| B7-G8 | human state controls, recovery/runbooks, first separately authorized stable Private issuance |
| B7-G9 | fresh verification, production read-only reconciliation, historical-boundary verification, final report/state closure |

Strong Authorization did not permit design-boundary expansion. Hard-stop protections remained in force for additional user population, third-party activation/handoff, Public/Formal distribution, real credential retirement, history rewriting, production cleanup, and commercial signing actions.

## 3. Source lineage and canonical-main integration

Board 7 preserved ordinary Git history throughout. Important lineage points include:

- primary Board 7 integration PR #1 -> `f63eb76b596080cb68b2285a8d0b0cc8e413a9a4`;
- whitespace repair PR #2 -> `a47bb21526d1d6e2fc3bc66567807943a488df51`;
- Strong Authorization PR #3 -> `fd29a2a7b00ded303c9c6ee8bdab8b1f2bbccc75`;
- production infrastructure PR #4 -> `8188384ce40f6239d8cebf8471def267faf74cde`;
- production identity/key PR #5 -> `13acc173b47355c0944d4c850b9e81384fd1bbc6`;
- atomic Worker Secret-bundle workflow repair PR #6 -> `4608d8b850d081cf189449161ee30780eaa18c29`;
- Service Token JWT compatibility repair PR #7 -> `f760355779d05f59d1bcc81bd3dec40d38872be2`;
- G6 automation repair lineage through PR #12 -> `c8f404b4d9d627f6530890b2f7a6b2c4f4743645`;
- G7 implementation repairs/candidate integration through PR #22 -> `8afbc7a074a0cc1cbefa7d9f53da82caa38a9e42`;
- G7 governance closure PR #23 -> `c24783ff9150fba465747d4592bc845f1ab2e485`;
- G8 governance closure PR #24 -> `a685fcfa24fd1ae2336a5286642affab87b6a85d`.

Fresh G9 ancestry checks proved every listed Board 7 merge point remains an ancestor of the current closure branch. No squash/rebase/force history rewrite was used.

The Board 5 evidence boundary is intentionally different: the accepted Board 5 evidence commit `67d3dec0fd1c4a02c87be1ab79c4f78ea63f49d6` is not a direct ancestor because Board 6 used selective source integration from historical frozen main. G9 therefore verified the actual required invariant — the frozen Board 5 final report Git blob is byte-identical at the frozen evidence commit and current HEAD (`65eecb6c3c9fda6ee587a3e8cfb1a75f650f5609`).

Board 6 closure ancestry is retained directly. The Board 6 final-report introduction commit `740ddabc5808a6a68c2dd812ae81c039b17d23b4` remains an ancestor and its report blob is unchanged (`059cf684b1c8a168b5d057f5919cb8486a56802e`).

## 4. Production topology

Fresh B7-G9 live readback confirms:

- Worker name: `wechat-cli-license-update`;
- active Worker Version ID: `ceedf5c8-111c-41e8-83f2-72733225352c` at 100%;
- production D1: `wechat-cli-license-production`, ID `011b3c26-bbe6-4bb7-8af7-39f1e6d46932`;
- diagnostics R2: `wechat-cli-diagnostics-production`;
- release R2: `wechat-cli-releases-production`;
- API origin: `https://wechat-cli-api.aurevior-devspace.com`;
- Admin origin: `https://wechat-cli-admin.aurevior-devspace.com`;
- release provenance repository: `AuRevior-ai/wechat-cli-releases`.

Fresh live ingress checks returned:

- API `/v1/health`: HTTP 200, `environment=production`;
- API host `/v1/admin/releases`: HTTP 403 `INGRESS_NOT_ALLOWED`;
- API host `/v1/automation/releases`: HTTP 403 `INGRESS_NOT_ALLOWED`;
- Admin host public `/v1/health` without Access: HTTP 403;
- Admin host public `/v1/licenses/activate` without Access: HTTP 403;
- Admin admin-route without human session: HTTP 401;
- Admin automation-route without Service Token: HTTP 403.

The current Windows network stack could not establish a TLS session to the attempted production `workers.dev` endpoint during G9; this is recorded as fresh unavailability rather than misreported as HTTP 404. More importantly, current production source/deployment policy continues to declare `workers_dev=false`, the accepted active Worker deployment is unchanged, and the focused deployment/preflight tests freshly proved production workers.dev exposure is rejected.

The long-lived internal canary loopback `/api/health` returned HTTP 200 with:

- product `wechat-cli-web`;
- version `0.6.1-canary.1`;
- Build ID `prod-060-8afbc7a074a0`;
- `status=ok`;
- `license_session_valid=true`.

## 5. Clean-room production data evidence

Fresh production D1 reconciliation found exactly:

- releases: 2 (`0.6.0` stable and `0.6.1-canary.1` beta);
- licenses: 2 (one beta canary and one stable controlled Private license);
- devices: 1 (the beta canary device);
- license-contact rows: 0;
- production release rows with `0.5.x`: 0.

The production beta canary license is:

- ID `lic_epPwkKlncMPfpLw5aOfzyEDn`;
- hint `MVQ7`;
- active;
- channel `beta`;
- `max_devices=1`;
- one active device.

Its only device is:

- ID `dev_7Td0DKYrLMbitpDsJ2EnswimLoHzHStE`;
- active;
- latest app `0.6.1-canary.1`;
- latest Launcher `0.2.0`.

The separately authorized first controlled stable Private license is:

- ID `lic_moOphTS-64IW4bvaqNurnuI0`;
- hint `JFEV`;
- active;
- channel `stable`;
- `max_devices=1`;
- zero active/bound stable devices.

No complete license key is present in this report or tracked source.

Production data remains distinct from staging: current Worker bindings point only to production D1/R2 identities, the live-binding forbidden-name scan found no staging binding or staging-only runtime credential name, and D1 contains no `0.5.x` staging release rows.

## 6. Human/machine identity and scope evidence

Fresh D1 readback proves the exact active principals remain:

### Human

`production-primary-admin`

Scopes:

- `licenses:read`;
- `licenses:write`;
- `devices:read`;
- `devices:write`;
- `releases:upload`;
- `releases:read`;
- `releases:register`;
- `releases:state`;
- `diagnostics:read`;
- `diagnostics:delete`;
- `contacts:rotate`.

### Machine

`release-automation-production`

Scopes:

- `releases:upload`;
- `releases:read`;
- `releases:register`.

The machine principal has no wildcard and no `releases:state`.

Fresh audit reconciliation found **zero** automation `release.update` events. Fresh Worker/auth tests also retained the stronger defense: even a synthetic non-session identity accidentally carrying `releases:state` is rejected from normal release-state mutation because state-changing administration requires human session auth mode.

Current Worker metadata still carries distinct human and automation Access audiences/identity-claim fields. No Access audience conflation was introduced.

At G9 readback, exactly one human session remained unexpired: the fresh Task 43 session for `production-primary-admin`, expiring at `2026-08-17T03:34:43.209Z`. Earlier rows remain `status=active` historically but are already expired by time. G9 does not mutate or revoke sessions merely for ceremony; the short-lived session expires naturally.

## 7. Secret/key inventory and independence

Fresh active Worker metadata exposes Secret **names/types only**, not values. Production current/readable selectors remain V1:

- `ADMIN_SESSION_PEPPER_CURRENT_VERSION=1`, readable `1`;
- `CONTACT_LOOKUP_PEPPER_CURRENT_VERSION=1`, readable `1`;
- `DEVICE_TOKEN_PEPPER_CURRENT_VERSION=1`, readable `1`;
- `DIAGNOSTIC_UPLOAD_SECRET_CURRENT_VERSION=1`, readable `1`;
- `DOWNLOAD_TICKET_SECRET_CURRENT_VERSION=1`, readable `1`;
- `LICENSE_KEY_PEPPER_CURRENT_VERSION=1`, readable `1`;
- `RATE_LIMIT_PEPPER_CURRENT_VERSION=1`, readable `1`;
- `CONTACT_ENCRYPTION_KEY_VERSION=1`;
- lease signer key ID `lease-key-production-01`.

Fresh production trust-profile metadata confirms:

- schema version `2`;
- `distribution_profile=private_controlled`;
- environment `production`;
- API origin `https://wechat-cli-api.aurevior-devspace.com`;
- release public trust only `release-key-production-01`;
- lease public trust only `lease-key-production-01`;
- empty `windows_publisher_policy`.

Fresh GitHub `production` Environment secret-name readback contains:

- `CLOUDFLARE_API_TOKEN`;
- `PRODUCTION_ACCESS_CLIENT_ID`;
- `PRODUCTION_ACCESS_CLIENT_SECRET`;
- `PRODUCTION_RELEASE_SIGNING_PRIVATE_KEY`;
- `PRODUCTION_WORKER_SECRETS_JSON`;
- `RELEASE_PUBLISHER_APP_PRIVATE_KEY`.

The active Worker binding scan found no staging value, no `GITHUB_RELEASE_READ_TOKEN`, and no legacy `ADMIN_TOKEN_PEPPER` dependency. Production therefore does not depend on the staging runtime GitHub PAT model or normal legacy-admin Secret path.

No V1 Secret or signing key was retired merely for Board 7 closure.

## 8. CI/CD workflow acceptance

Fresh B7-G9 verification passed the workflow/deployment policy suite and `scripts/verify_workflow_policy.py` for all three privileged workflows:

- `ci.yml`;
- `deploy-production-worker.yml`;
- `publish-production-release.yml`.

The verified properties include:

- privileged workflows are manual/concurrency-controlled where required;
- exact canonical-main identity is enforced for privileged production action;
- external Actions are full-SHA pinned;
- ordinary CI has minimal permissions and no production credential boundary;
- production Worker Secret material is passed atomically from the protected Environment;
- release workflow has no release-state or license mutation;
- release signing private key is scoped to the signing step and is not available to later untrusted Actions;
- publication automation preflights the production machine transport before signing.

The GitHub production Environment still identifies publisher App ID `4608862` and release provenance repository `AuRevior-ai/wechat-cli-releases`. The accepted B7-G4 evidence records that App installation as selected-repository only with `contents:write` plus GitHub-required `metadata:read`. A direct ordinary-user query of private App metadata is not an available read path and was not used to broaden credentials in G9; the same unchanged App ID/Environment boundary successfully published the immutable G7 candidate.

## 9. Production Worker deployment evidence

The active production Worker Version remains:

`ceedf5c8-111c-41e8-83f2-72733225352c`

It was produced by the accepted B7-G5 repair deployment from exact canonical-main source `f760355779d05f59d1bcc81bd3dec40d38872be2`.

Fresh G9 Git comparison proved **zero diff** from `f760355...` through current canonical main for:

- `services/license-update-worker/`;
- `scripts/deploy_worker.py`;
- `.github/workflows/deploy-production-worker.yml`.

B7-G8 therefore correctly did not manufacture a new same-functionality Worker version merely for a recovery ceremony. The accepted last-known-good recovery primitive remains exact canonical-main redeploy through `deploy-production-worker.yml`, and fresh production preflight plus current health/ingress evidence prove the recorded LKG is still the live accepted runtime.

Cloudflare provider-side version rollback is not the standard recovery primitive.

## 10. `0.6.0` / Launcher `0.2.0` installer evidence

Stable production release `rel_prod_0_6_0` remains:

- version `0.6.0`;
- channel `stable`;
- enabled `1`;
- paused `0`;
- rollout `0`;
- manifest SHA-256 `af7c3aad001131f5255a479bb6b94859c7c7772c630b0625b816d0c91900256e`;
- package SHA-256 `7259580fd447028e9ee66827d72f1c481fb41593ba3b12e4e3e5edb52fdfc423`;
- package size `15191871`;
- runtime backend `r2`.

Fresh direct R2 streaming readback reproduced exactly the same package size and SHA-256.

GitHub release `v0.6.0` remains the single explicitly approved G6 native-immutability exception:

- release ID `371243689`;
- `draft=false`;
- `prerelease=false`;
- package asset ID `516494905`;
- exact package digest/size still match D1/R2;
- `isImmutable=false` remains unchanged and is not retroactively rewritten.

The release repository itself now has native Immutable Releases enabled prospectively; every later Board 7 release must be immutable.

The accepted canonical `0.6.0` production installer evidence remains present. Fresh G9 readback:

- size `41520833`;
- SHA-256 `aaa9b0dbde0b850725fc989a9816538544a1ce459cf0ac1cf2629268099a4bf5`;
- Authenticode status `NotSigned`;
- no signer certificate;
- no timestamp certificate.

Launcher version remains `0.2.0`, including on the live canary device.

## 11. `0.6.1-canary.1` update/rollback evidence

Internal candidate `rel_prod_0_6_1_canary_1` remains:

- version `0.6.1-canary.1`;
- channel `beta`;
- enabled `0`;
- paused `1`;
- rollout `100`;
- manifest SHA-256 `6960eb52c02ecaabb07bcfbe18687ae325378bb3f42d76939cfef1d9541a7b9b`;
- package SHA-256 `a356552d1bc3461028806663f93d4af44860e18bd6731da8ae6d328b01dd6d90`;
- package size `15193192`;
- runtime backend `r2`.

Fresh R2 streaming readback reproduced that exact size/hash.

GitHub `v0.6.1-canary.1` remains:

- release ID `371463634`;
- private prerelease;
- `isImmutable=true`;
- package asset ID `517349597`;
- package digest/size exactly matching D1/R2;
- manifest digest exactly matching D1.

B7-G7 already proved the real installed path:

1. same beta canary device selected the candidate;
2. download ticket/R2 transport completed;
3. Ed25519 manifest and exact package SHA/size verified;
4. update committed and health passed on `0.6.1-canary.1`;
5. an isolated same-device controlled fault drove health-version mismatch;
6. Launcher performed transactional rollback;
7. candidate process tree was fully removed;
8. restored `0.6.0` owned the listener;
9. exact failed-candidate suppression prevented reselection;
10. the designated long-lived primary canary was finally restored healthy on `0.6.1-canary.1` before the candidate release itself was paused/disabled.

Fresh G9 loopback health reconfirms that committed healthy version remains running and is not force-downgraded merely because the candidate release is now disabled/paused.

## 12. Release-state human-only evidence

Release state remains a human-session-only capability.

Fresh D1 audit shows:

- stable `0.6.0` enable was performed by `production-primary-admin`;
- beta candidate enable, rollout 100, and final disable/pause were all performed by `production-primary-admin`;
- automation produced only `release.package_ready` and `release.register` for both releases;
- automation `release.update` count is exactly `0`.

The machine principal still lacks `releases:state`; the Worker route/auth-mode implementation and fresh test suite independently prevent a machine identity from turning an accidental scope mistake into a valid state mutation.

The final candidate state remains `enabled=0`, `paused=1`, rollout `100`.

## 13. Controlled user issuance evidence

After B7-G7 canary acceptance and B7-G8 recovery controls passed, the user separately approved exactly one first real Private stable production license.

The issuance used a fresh human Access session and the human Admin batch endpoint with:

- count `1`;
- channel `stable`;
- maximum devices `1`;
- purpose `first-controlled-private-production-license`.

Safe identity:

- license ID `lic_moOphTS-64IW4bvaqNurnuI0`;
- key hint `JFEV`;
- active;
- revision `1`;
- created by `production-primary-admin`;
- zero stable device bindings.

The `license.batch_create` audit contains only safe metadata `count=1`, `maximum_devices=1`, `release_channel=stable`.

The complete key was never printed into chat/governance output and remains only in the repo-external production evidence CSV. That new evidence directory, CSV, and fresh DPAPI admin config were ACL-hardened to the current Windows user plus Administrators and SYSTEM.

No key was sent to a third party and no real third-party device was activated.

## 14. Rollback/recovery evidence

Recovery acceptance consists of both application-release and Worker/control-plane layers.

Application layer:

- G7 controlled candidate fault proved transactional rollback;
- candidate process-tree cleanup proved the failed candidate was no longer serving;
- prior stable health ownership was verified;
- exact failed-release suppression was verified;
- pause+disable semantics stop new candidate propagation without force-downgrading already committed healthy installs;
- forward-fix via a new immutable `0.6.x` release remains the post-commit remediation path.

Worker layer:

- accepted LKG Worker Version ID recorded;
- fresh production preflight passed;
- live Worker/deploy source remains byte-equivalent to current canonical implementation;
- health/ingress/Access boundaries are still accepted;
- canonical-main-only deploy workflow remains the standard redeploy primitive;
- no redundant same-functionality Worker version was created for ceremony.

Credential emergency runbook:

- HMAC/ticket material uses add/overlap/switch/prove/rollback/re-switch/wait/retire sequencing;
- contact encryption material cannot be physically retired while dependent ciphertext remains unless data inaccessibility is explicitly accepted;
- lease/release signer replacement does not revoke embedded client trust by itself; public-trust overlap/client update is required before retirement;
- Service Token/App/API-token consequences are separated by purpose;
- no production V1 credential was actually revoked or rotated merely for the drill.

## 15. Diagnostics/privacy evidence

The single production canary diagnostics submission remains as deleted metadata:

- ID `diag_RadhMmueCIX0mPvH1kEk2cB_`;
- status `deleted`;
- size `806`;
- SHA-256 `0aa78dd28673ce45e1084d5fd9ed95b788dc1cb982f2251ea470f23a1efb88e8`;
- client version `0.6.0`;
- Launcher `0.2.0`;
- seven-day retention deadline preserved in metadata.

G7 proved upload, byte-for-byte admin download, explicit delete, idempotent second delete, and post-delete not-found behavior while retaining relationship/audit metadata.

Fresh G9 diagnostics verification additionally passed:

- Python diagnostics/redaction/upload/retention: 17/17;
- Worker diagnostics retention/admin metadata: 14/14.

The tests prove complete license/device/admin/GitHub token redaction, Authorization/Cookie/query-secret removal, user-path redaction, second-pass sensitive scanning, consent v1, bounded upload TTL, and seven-day retention policy.

No diagnostic content was re-downloaded or recreated in G9.

## 16. Deferred Authenticode

Commercial Authenticode is **not** a Board 7 Private / Controlled closure blocker and is not claimed as complete.

Fresh evidence remains consistent with the approved deferral:

- `distribution_profile=private_controlled`;
- `windows_publisher_policy` is empty;
- accepted production installer is `NotSigned`;
- no signer certificate;
- no timestamp certificate;
- no provider payment/subscription;
- no KYC/identity verification;
- no managed/HSM signing key;
- no production publisher-policy activation.

Any future Public / Formal Distribution activation requires a new design and explicit authorization.

## 17. Explicit actions not performed

B7-G9 did not:

- create another production license or device;
- send the stable Private license key to any third party;
- activate/bind a third-party device;
- enable/resume/pause/disable or change rollout on any release;
- publish or rewrite a GitHub release/tag/asset;
- modify or delete R2 release bytes;
- deploy a new Worker version;
- use Cloudflare provider-side rollback;
- rotate/revoke/retire/delete a production V1 Secret/key;
- change Access identities/audiences/policies;
- perform Public/Formal Authenticode procurement or signing;
- delete branches/worktrees/evidence;
- clean the historical retained `NUL` boundary;
- force-push, rebase, squash, or rewrite history.

The current G9 worktree also contains a local untracked `nul` artifact created during earlier shell diagnostics. It is explicitly excluded from all staging/commits and is not the retained historical `D:\use_as_desktop\Wechat__CLI\wechat-cli\NUL` boundary. Closure authorization does not permit deleting either merely for cleanup.

## 18. B7-G9 fresh verification evidence

Fresh execution from exact G9 base `a685fcfa24fd1ae2336a5286642affab87b6a85d` produced:

- Python full suite: **713 tests, 2 skipped, 0 failed**;
- Worker TypeScript typecheck: PASS;
- Worker Vitest: **18 files, 132/132 tests PASS**;
- production deployment/workflow focused unittest set: **50/50 PASS**;
- workflow source policy: all three required workflows PASS;
- tracked high-confidence sensitive-value verifier: PASS;
- additional final sensitive-shape scan for private-key/license/device/admin-session/GitHub-token patterns: PASS;
- `git diff --check`: PASS.

A separate diagnostics/privacy focused run produced Python 17/17 PASS and Worker 14/14 PASS.

## 19. Final program state

All Board 7 mandatory Safety, Consistency, and Operational acceptance criteria have fresh or frozen-as-required evidence and no unresolved defect requires a design-boundary expansion.

Accordingly, the canonical state represented by this closure branch is:

```text
Board 7 accepted complete
Authorized Update Program accepted complete
```

This acceptance is specifically for **Private / Controlled Distribution**.

The production terminal state is intentionally conservative:

- stable `0.6.0` release enabled/unpaused, rollout 0;
- one active stable Private license, max devices 1, zero device bindings;
- one active beta internal canary license/device;
- internal `0.6.1-canary.1` release disabled/paused, rollout 100, provenance retained immutable;
- long-lived canary healthy on committed `0.6.1-canary.1`;
- automation cannot mutate release state;
- no public distribution or third-party activation occurred.

The seven-board Authorized Update Program therefore closes with its controlled production path accepted. Any expansion beyond this state — additional real-user population, actual customer handoff/activation, public distribution, commercial Authenticode, credential retirement, destructive cleanup, or a new release/recovery design — is outside this program closure and requires a new explicit scope/design authorization.
