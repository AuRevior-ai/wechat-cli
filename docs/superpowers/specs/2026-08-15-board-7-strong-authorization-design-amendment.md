# Board 7 Strong Authorization Design Amendment

Status: **APPROVED — Strong Authorization Envelope active**
Date: 2026-08-15
Parent design: `docs/superpowers/specs/2026-08-15-board-7-production-automation-controlled-launch-design.md`
Parent implementation plan: `docs/superpowers/plans/2026-08-15-board-7-production-automation-controlled-launch.md`

## 1. Purpose

The approved Board 7 design intentionally used many independent authorization gates for GitHub writes, Cloudflare mutations, production resource creation, credential creation, deployment, release publication, release-state changes, license creation, and final closure.

That model is safe but creates excessive approval chatter after the operator has already reviewed the complete end-to-end production design. This amendment changes **only the authorization mechanics** for the remainder of Board 7. It does not relax the security invariants, test requirements, human/machine separation, clean-room production model, fail-closed behavior, release immutability, Private / Controlled Distribution profile, or deferred Authenticode boundary.

After explicit approval of this amendment, the assistant receives one bounded **Board 7 Strong Authorization Envelope** and may execute all operations enumerated below sequentially without requesting another routine approval at each existing `Mandatory STOP`.

Existing `Mandatory STOP` markers remain **internal verification checkpoints**. They stop execution only when a hard-stop condition in this amendment is met; otherwise the assistant records the evidence and proceeds autonomously.

The authorization expires automatically when either:

1. Board 7 is accepted complete and the Authorized Update Program is accepted complete; or
2. a hard-stop condition below occurs.

It does not authorize any later Public / Formal Distribution program, commercial code-signing work, unrelated repository work, cleanup, or expansion beyond the exact scope below.

---

## 2. Approval-count problem this amendment removes

From the current checkpoint, `B7-G2C.1A Repair Branch Push` is complete. Under the original plan, the remaining work would still generate repeated approvals for at least:

1. repair PR creation;
2. repair merge;
3. this authorization-amendment branch push;
4. amendment PR creation;
5. amendment merge;
6. B7-G3 production infrastructure mutation matrix;
7. B7-G3A non-secret config branch push;
8. B7-G3B config PR creation;
9. B7-G3C config merge;
10. B7-G4 production identity/key bootstrap;
11. B7-G5 production Worker deploy;
12. B7-G6 CI/CD automation acceptance and first production release preparation;
13. B7-G7 production canary gate entry;
14. internal canary license creation;
15. human enable of stable `0.6.0`;
16. publication/registration of `0.6.1-canary.1`;
17. human enable of `0.6.1-canary.1`;
18. canary candidate pause/disable/cleanup decision;
19. B7-G8 recovery/controlled-release gate;
20. first real Private production license issuance;
21. B7-G9 final closure;
22. final closure-doc branch push;
23. final closure-doc PR;
24. final closure-doc merge to canonical `main`.

Some of the original steps also contain conditional sub-approvals for a recovery-drill Worker version or a real credential revoke/rotation. This amendment deliberately resolves those conditions so they do not create additional routine approval prompts.

Therefore, approval of this one amendment replaces roughly **24 future routine approval requests** with a single bounded authorization decision.

---

## 3. Approaches considered

### Approach A — Preserve every existing approval gate

Maximum operator control but highest interaction cost. It preserves the original plan literally and would require repeated approval messages even when each next action is already predetermined by the accepted design.

### Approach B — One authorization per major Board 7 phase

Collapse the process to approximately G2/G3/G4/G5/G6/G7/G8/G9 approvals. This reduces chatter but still requires repeated operator presence and does not materially improve safety over a well-bounded full-program authorization envelope.

### Approach C — Single bounded strong-authorization envelope

**Selected recommendation.** The user reviews one explicit, closed mutation matrix covering all remaining Board 7 operations. Internal gate checks remain mandatory, but successful gates no longer require a new permission message. Unexpected drift, cost, security weakening, scope expansion, or destructive behavior still hard-stops.

This is the best fit for the user’s explicit request to approve the remaining Board 7 program once and let execution proceed autonomously.

---

## 4. Global invariants that remain unchanged

Strong authorization does **not** weaken any of these rules:

```text
Distribution profile = private_controlled
Commercial Authenticode = deferred optional Public/Formal hardening
No staging business-data migration into production
Production workers_dev = false
API/Admin host authority split remains mandatory
Human and machine Access identity models remain separate
Machine identity cannot change release state
Machine registration starts at enabled=false / paused=true / rollout=0
Release-state changes require human wcas session + recent-auth
GitHub provenance remains immutable
R2 release bytes are immutable / never overwrite as rollback mechanism
Production deploy source must be canonical main
No squash/rebase/history rewrite of Board 5/6/7 security lineage
No secret/private key/license key/device token/session value enters tracked source/docs/logs
No production compatibility fallback to staging credentials
No Public/Formal publisher claim while windows_publisher_policy is empty
```

Any operation that would require violating one of these invariants is outside this authorization and must hard-stop.

---

## 5. Exact production inventory frozen by this amendment

Approval of this amendment freezes the production naming matrix below, subject to read-only collision checks before creation.

### Cloudflare Worker

```text
wechat-cli-license-update
```

### D1

```text
wechat-cli-license-production
```

### R2

```text
wechat-cli-releases-production
wechat-cli-diagnostics-production
```

### Exact production hostnames

The symbolic Board 7 `<BASE_DOMAIN>` is resolved for implementation to the existing controlled root domain convention:

```text
API:   wechat-cli-api.aurevior-devspace.com
Admin: wechat-cli-admin.aurevior-devspace.com
```

This amendment intentionally uses product-prefixed hostnames instead of generic root-level `api.*` / `admin.*` names, matching the already accepted staging naming convention and reducing collision risk with unrelated services.

Production source/trust configuration must use these exact origins:

```text
https://wechat-cli-api.aurevior-devspace.com
https://wechat-cli-admin.aurevior-devspace.com
```

If either exact hostname already exists unexpectedly, points at an unrelated resource, or cannot be controlled under the existing account/zone without a paid plan or ownership change, execution hard-stops before mutation.

### Access application identities

```text
human application:      wechat-cli-production-human-admin
automation application: wechat-cli-production-release-automation
service token:           wechat-cli-release-automation-production
```

Path authority remains:

```text
admin hostname /v1/admin/*      -> human Access policy only
admin hostname /v1/automation/* -> Service Auth policy only
```

### GitHub identities

```text
source repository:       AuRevior-ai/wechat-cli
release provenance repo: AuRevior-ai/wechat-cli-releases
GitHub App:              wechat-cli-release-publisher
GitHub Environment:      production
```

The GitHub App may be installed only on the release provenance repository and receives only the permissions actually required by the accepted publisher implementation.

If an object with an exact target name already exists unexpectedly, it is not silently reused, overwritten, deleted, or adopted. The mismatch is a hard stop unless it is independently proven to be the already intended Board 7 object with matching immutable identity.

---

## 6. Human identity resolution rule

The production human administrator must map to the **same exact human Access identity already used and accepted in Board 6 staging acceptance**, but production receives a new principal row/session domain and no staging session/credential is copied.

The exact human identity value is resolved by read-only evidence during B7-G4 from the accepted Access identity source. The assistant may proceed without asking the user again only if exactly one unambiguous previously accepted human identity is recovered.

Hard stop if:

- no accepted identity can be recovered;
- multiple plausible identities exist;
- the recovered identity differs from the Board 6 accepted operator identity;
- creating production Access would require a new external human account or invitation not already controlled by the user.

This bounded derivation avoids recording a personal email unnecessarily in this design document while still preventing arbitrary identity selection.

---

## 7. Production Secret and key authorization

The strong authorization permits generation and provisioning of only the exact runtime inventory derived by the accepted selector/policy source. Initial production selectors remain V1.

Expected representative runtime names are:

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

and separate release signing material:

```text
lease-key-production-01
release-key-production-01
```

Rules:

- all values are freshly generated production material;
- staging values are never copied;
- release private signing key is never placed in Worker runtime;
- lease private key is never placed in the general release-publishing secret domain;
- `GITHUB_RELEASE_READ_TOKEN` is not provisioned for normal production runtime;
- `ADMIN_TOKEN_PEPPER` is not provisioned for normal production operation;
- no legacy admin principal/token is created;
- private values are never printed into chat, logs, tracked files, or governance evidence;
- repo-external recovery evidence contains only what the accepted recovery model permits.

If the available tooling cannot safely create/capture a one-time secret without exposing it, the assistant may require the user to perform a narrow credential-entry/manual-browser step. That is a **tool-capability handoff, not a new authorization request**. The assistant must provide the exact command/UI action, then independently read back only safe metadata.

---

## 8. Authorized Git/GitHub operations through Board 7 closure

Once this amendment is approved, the assistant may perform all remaining ordinary history-preserving hosted Git integration steps without new permission prompts:

1. create the repair PR from `board7/post-merge-whitespace-repair` to `main`;
2. merge it only after exact-head CI is green, using merge-commit/history-preserving semantics;
3. push this strong-authorization amendment branch;
4. create and merge its PR after CI/review preconditions pass;
5. create local implementation/config/governance branches required by the already accepted Board 7 plan;
6. push those reviewed branches;
7. create their exact PRs to canonical `main`;
8. merge only with history-preserving merge commits after checks pass;
9. perform the final Board 7 closure-doc push/PR/merge so remote canonical `main` records the completed program state.

Still forbidden:

```text
force push
history rewrite
rebase merge
squash merge
amend published security lineage
tag creation except release-provenance tags created by the approved release publisher
branch deletion / worktree cleanup unless separately justified after program closure
```

Every hosted write must be preceded and followed by exact SHA readback. Unexpected remote-main drift is a hard stop.

---

## 9. B7-G3 infrastructure mutations authorized

After repair/amendment integration and fresh preflight, the assistant may autonomously:

- create D1 `wechat-cli-license-production`;
- apply migrations only, with no staging import;
- create R2 `wechat-cli-releases-production`;
- create R2 `wechat-cli-diagnostics-production`;
- create/reserve the exact API/Admin production hostnames;
- create the exact human and automation Access applications/policies;
- collect safe issuer/JWKS/audience metadata;
- keep `workers_dev=false`;
- update non-secret source configuration with exact created IDs/hostnames/audiences;
- locally test and commit the config;
- push/PR/merge that config to canonical main.

Clean-room proof must show zero staging/business rows before proceeding.

If Cloudflare requires an application Worker deployment merely to attach a route, do not deploy a placeholder application. Defer route attachment to B7-G5 as already designed.

---

## 10. B7-G4 identity/key/bootstrap mutations authorized

After B7-G3 exact config is canonical and inventory checks pass, the assistant may autonomously:

- generate fresh production V1 runtime secret material;
- generate `lease-key-production-01` Ed25519 material;
- generate `release-key-production-01` Ed25519 material;
- provision runtime-required Worker Secrets only;
- create the production human principal with the exact accepted scope matrix;
- create `release-automation-production` with only:

```text
releases:upload
releases:read
releases:register
```

- create one Cloudflare Access Service Token for automation;
- create/install `wechat-cli-release-publisher` only on the release repo;
- configure the `production` GitHub Environment secrets if the existing GitHub plan provides the required secure boundary;
- build the real repo-external production trust profile;
- record only safe identity/key IDs and public-key evidence.

If secure GitHub Environment handling is unavailable without upgrading a paid plan, do not downgrade to ordinary repository secrets. Use the already designed repo-external/manual signing fallback where possible; if no secure fallback is executable with available tools, hard-stop.

No payment, plan upgrade, KYC, account purchase, or commercial signing action is authorized.

---

## 11. B7-G5 production Worker deployment authorized

After exact canonical-main, secrets, Access, trust-profile, and production preflight all pass, the assistant may dispatch/execute the accepted `deploy-production-worker.yml` for the exact current canonical main SHA.

Authorized effects are limited to the production Worker deployment and the production bindings/routes already named in this design.

The assistant must record:

```text
exact canonical main SHA
Worker Version ID
exact D1/R2 IDs
API/Admin route identity
Access audience identity
safe Secret-name inventory
```

No release/license creation occurs in G5.

---

## 12. B7-G6 CI/CD acceptance and stable 0.6.0 preparation authorized

The assistant may autonomously execute the accepted production release-preparation workflow for exactly:

```text
version: 0.6.0
channel: stable
App: 0.6.0
Launcher: 0.2.0
rollout at registration: 0
initial state: enabled=false, paused=true
release signing key: release-key-production-01
```

Authorized effects include:

- exact-main Windows build;
- update ZIP creation;
- manifest signing;
- production R2 package upload/readiness;
- private GitHub immutable provenance/tag publication with `make_latest=false`;
- automation registration in production D1;
- safe read-only reconciliation;
- denial probes proving machine identity cannot mutate release state.

Machine identity is never authorized to enable/resume/change rollout.

---

## 13. B7-G7 internal canary mutations authorized

After B7-G6 acceptance passes, the assistant may perform the full internal production canary lifecycle without further approval.

### Internal license

Create exactly one production canary license:

```text
channel=beta
maximum_devices=1
purpose=internal-production-canary
```

No second canary license is authorized.

### Stable 0.6.0 human enable

With a fresh human Access session/recent-auth, enable/unpause exactly the already registered stable `0.6.0` release while there are still zero real stable user licenses. Set only the explicitly required stable state; machine identity is not used.

### Canary install/activation

Authorized on the marked controlled Windows canary environment:

- controlled installer delivery;
- 0.6.0 installation;
- single-device activation;
- second-device rejection proof;
- offline lease acceptance using injected/tested time logic, not Windows system clock mutation;
- diagnostics upload/read/delete/retention/log-redaction acceptance.

### Internal beta candidate

Prepare/publish/register exactly one internal beta candidate:

```text
0.6.1-canary.1
channel=beta
initial enabled=false
initial paused=true
initial rollout=0
```

Then, with human Access/recent-auth, enable only this named candidate for the single beta canary license.

Perform real update/fault/transactional rollback/suppression acceptance, then human pause+disable the canary candidate. Preserve its immutable GitHub provenance and R2 bytes.

### Canary cleanup decision

Default terminal policy under this strong authorization:

- preserve the single production canary license/device as the designated long-lived operational canary after successful acceptance;
- do not revoke/unbind it merely for cleanup ceremony;
- do not create additional canary licenses/devices.

This removes the need for a separate cleanup approval.

---

## 14. B7-G8 recovery and first controlled Private issuance authorized

### Human release-state acceptance

The assistant may exercise only named, controlled human-session release-state changes required to prove enable/pause/disable/rollout behavior. Machine denial must remain intact.

### Worker last-known-good recovery drill

Standard recovery primitive remains:

```text
redeploy exact recorded last-known-good canonical main commit
through deploy-production-worker.yml
```

A harmless same-functionality/new-version Worker deployment may be created **only if technically necessary to make the recovery drill meaningful**. It may not include a functional permission/resource/trust change. If no meaningful new version is required, use read-only/workflow evidence instead of creating mutation for ceremony.

### Credential emergency-revoke acceptance

This strong authorization permits **runbook verification only**. It does not authorize actual retirement/rotation/revocation of production V1 secrets or signing keys merely for the drill. A real emergency revoke would be incident response outside normal Board 7 closure and is therefore a hard stop/new incident scope.

### First real Private production license

After canary and recovery acceptance pass, create exactly one first real stable production license:

```text
channel=stable
maximum_devices=1
purpose=first-controlled-private-production-license
```

Rules:

- exactly one license only;
- complete key stored only in the restricted repo-external production evidence location;
- safe metadata/audit evidence may be recorded;
- do not automatically send the key to any third party;
- do not activate/bind a real third-party device under this authorization;
- no bulk license pool is authorized.

This satisfies the first controlled Private issuance checkpoint while keeping actual customer handoff outside autonomous automation.

---

## 15. B7-G9 final closure and canonical integration authorized

After every mandatory Board 7 acceptance condition passes, the assistant may autonomously:

- run fresh full Python/Worker/deployment/workflow verification;
- perform production read-only reconcile;
- reverify Board 5/Board 6 historical boundaries;
- perform sensitive-value scans;
- write the final Board 7 acceptance report;
- update `docs/PROJECT_STATE.md` and the authorized-update roadmap to:

```text
Board 7 accepted complete
Authorized Update Program accepted complete
```

- create the docs-only closure commit;
- push a closure branch;
- create the closure PR;
- merge it with history-preserving merge commit after CI is green;
- read back final canonical `main` SHA.

No branch/worktree/NUL/evidence cleanup is authorized by closure.

---

## 16. Bounded autonomous repair authority

To avoid returning for permission on ordinary CI/environment defects, this strong authorization also permits narrow repairs discovered while executing the approved Board 7 design.

Allowed autonomous repairs must satisfy **all** of the following:

1. directly required to make an already approved Board 7 invariant work as designed;
2. no expansion of permissions, scopes, user population, production resource inventory, release-state authority, or data retention;
3. no new public ingress or compatibility bypass;
4. no change from Private / Controlled to Public / Formal;
5. TDD where code behavior changes;
6. fresh full regression before hosted integration;
7. ordinary history-preserving branch/PR/merge only;
8. repair scope and evidence recorded in governance/closure notes.

Examples allowed:

- hosted CI portability fixes;
- deterministic path normalization;
- safe error handling;
- preflight correctness bugs;
- documentation/canonical-memory consistency repairs;
- read-only reconcile tooling fixes;
- implementation defects that restore the already approved human/machine or fail-closed contract.

Repairs that would change the design boundary are not covered and hard-stop.

---

## 17. Hard-stop conditions that still require the user

Strong authorization is **not** permission to improvise through unexpected high-risk conditions. Execution must stop and report if any of these occur:

### Security / authority drift

- machine identity would need `releases:state` or any license/device/admin-management scope;
- human-only state enforcement cannot be preserved;
- production would require workers.dev fallback;
- API/Admin host/path firewall would need relaxation;
- staging secret/data/credential reuse appears necessary;
- a private key/credential would need to be committed, logged, or placed in an ordinary repository secret;
- GitHub Environment security is unavailable and no already-designed secure fallback is possible;
- an Access identity/audience cannot be uniquely verified.

### Resource/data collision

- any exact production D1/R2/Worker/domain/Access/GitHub App target unexpectedly exists with non-empty or unrelated state;
- production clean-room row counts are non-zero before authorized production data creation;
- a target resource would need deletion/overwrite/adoption without proof.

### Source-control drift

- remote main changes unexpectedly between reviewed preflight and mutation;
- merge would require force/rebase/squash/history rewrite;
- Board 5/6 evidence ancestry is missing or altered;
- an unexpected unrelated user change conflicts with the required source edits.

### Test/acceptance failure requiring design expansion

- a mandatory test/security acceptance fails and the root-cause fix would broaden the approved design;
- rollback/recovery cannot restore the accepted state;
- real canary behavior contradicts a frozen protocol/trust invariant;
- a production fault creates uncontrolled user exposure or persistent data corruption.

### Financial/identity/commercial effects

- any payment, subscription upgrade, billable plan change, commercial certificate purchase, KYC/identity-verification flow, hardware/HSM procurement, or Public/Formal Authenticode action is required;
- any new external human account/invite must be created;
- any third-party customer communication or credential delivery would be required.

### Destructive cleanup

- deletion of GitHub provenance, R2 release bytes, Board 5/6 evidence, branches/worktrees, historical `NUL`, production data, or credentials purely for cleanup.

### User-exposure expansion

- more than one internal beta canary license/device is required;
- more than one first real stable production license is required;
- a real third-party device must be activated;
- public download/website exposure is proposed;
- stable rollout to a population beyond the explicitly created first license is proposed.

A hard stop suspends the strong authorization until the user explicitly resolves that new condition. Routine successful gates do not.

---

## 18. Progress-reporting behavior under strong authorization

After approval, the assistant should not repeatedly ask “approve next gate?”. Instead it should:

1. announce the current internal gate briefly;
2. execute the already authorized actions;
3. report significant findings and blockers as they occur;
4. preserve exact SHA/resource/version evidence;
5. continue automatically when the gate passes;
6. stop only on a hard-stop condition or final Board 7 completion.

Because tooling may require user-controlled browser/session/secret-entry steps, the assistant may still ask the user to perform a **specific mechanical action** when technically unavoidable. Such a request must be phrased as execution handoff, not a new authorization request, and must not expose secret values in chat.

---

## 19. Effect on the existing implementation plan

Upon user approval, this amendment supersedes only the **approval semantics** of the existing Board 7 implementation plan.

Every existing `Mandatory STOP — request ... authorization` becomes:

```text
INTERNAL CHECKPOINT — verify the gate’s preconditions, mutation matrix,
post-write readback and safety invariants. Continue automatically if all
conditions match the Strong Authorization Envelope. Hard-stop only on an
exception listed in the amendment.
```

The technical task order, acceptance criteria, TDD requirements, readbacks, scope matrices, and fail-closed requirements remain in force.

No separate rewrite of the 1,400+ line implementation plan is required before execution; the final closure report must cite this amendment as the authorization source for the consolidated execution.

---

## 20. Explicit exclusions

This amendment does not authorize:

```text
Public / Formal Distribution activation
commercial Authenticode provider selection/procurement
payment or KYC
non-empty production windows_publisher_policy
public download portal
mass/bulk production license creation
customer messaging or credential delivery
more than one real stable production license
real production V1 key/secret retirement solely for drill
unrelated feature development
unrelated repository cleanup
NUL deletion
Board 5/6 evidence cleanup
release provenance deletion
R2 release-object deletion/overwrite
force push / squash / rebase / history rewrite
branch/worktree deletion as routine cleanup
```

---

## 21. Approval semantics

The user can approve this entire amendment with one explicit statement equivalent to:

> **批准 Board 7 Strong Authorization Design Amendment。授权你在本文封闭矩阵、现有 Board 7 design/spec 和 implementation plan 的共同约束下，自主执行从当前 repair integration 到 B7-G9 final closure 的全部列明 GitHub、Cloudflare、production、release、canary、license 与 canonical integration 操作，不再逐 gate 向我申请批准；只有命中本文 hard-stop 条件时才停止并向我报告。**

Once approved, that statement is the sole routine authorization needed for the remainder of Board 7.

The user explicitly approved this amendment on 2026-08-15. The Strong Authorization Envelope is therefore active from this governance-activation commit forward. Per the approval, the first autonomous actions are constrained to governance/source-integration closure: complete the already-pushed `9185f5f` whitespace-repair PR/CI/merge, then integrate this amendment through its own PR/CI/merge, then fresh-read back the exact canonical remote `main`. B7-G3 production provisioning may begin only after those three checks succeed.
