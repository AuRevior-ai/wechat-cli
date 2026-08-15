# Board 6 Private / Controlled Distribution Profile Plan Amendment

> **APPROVED IMPLEMENTATION PLAN AMENDMENT**
>
> Design source: `docs/superpowers/specs/2026-08-14-board-6-private-distribution-profile-design-amendment.md`
>
> Scope: governance/status/closure criteria only. No production mutation, provider procurement, KYC, payment, real signing, push, merge, tag modification, reset, rebase, or amend.

## Task A — Canonicalize the current private distribution profile

- Update `docs/superpowers/specs/2026-08-12-board-6-security-delivery-preparation-design.md` so Authenticode is mandatory only for the future Public / Formal Distribution profile, not the current Private / Controlled Distribution profile.
- Preserve the original Authenticode engineering work and provider-neutral abstractions as future-capability evidence.
- Record the accepted private-profile tradeoffs explicitly.

## Task B — Reclassify B6-G6

- Keep B6-G6 Phase A readiness/provider research as completed evidence.
- Keep `50e7074` as a dormant optional future SSL.com adapter; do not activate/configure/use it.
- Mark the real procurement/KYC/payment/key/signing portion of B6-G6 as **DEFERRED — non-blocking for current private distribution**.
- Do not mark real B6-G6 signing as completed.

## Task C — Make distribution profile explicit in embedded trust policy

Implement under TDD:

- extend `DeploymentTrustProfile` with schema-v2 `distribution_profile = private_controlled | public_formal`;
- preserve schema-v1 production behavior unchanged for backward compatibility;
- require schema v2 to declare `distribution_profile` explicitly;
- keep production HTTPS/non-loopback/non-staging/stable rules in both profiles;
- require non-empty publisher only for `public_formal`;
- allow empty publisher for `private_controlled`;
- expose `distribution_profile` through `LauncherConfig` and mark it trust-critical so mutable external config cannot override it;
- add a regression proving empty publisher creates `AuthenticodePolicy(required=False)` while non-empty publisher remains required.

Do not mutate the existing staging trust-profile file under this task; the schema change prepares the future private production profile without changing live staging.

## Task D — Update Board 6 execution plan and closure criteria

- Change Task 17 from a mandatory next gate to a deferred optional future gate.
- Make B6-G7 Staging Key Rotation Drill the next mandatory Board 6 gate.
- Replace the B6-G8 requirement for `real signed staging artifact/public certificate metadata` with explicit private-profile evidence:
  - empty `windows_publisher_policy` by design;
  - Ed25519 release-manifest verification;
  - exact package SHA-256/size verification;
  - server-authoritative release eligibility;
  - safe extraction and rollback/failure suppression evidence;
  - explicit record that no real signing identity was provisioned or used.

## Task E — Update canonical status documents

Update:

- `docs/PROJECT_STATE.md`
- `docs/deployment/authorized-update-roadmap.md`
- `docs/superpowers/governance/2026-08-14-board-6-code-signing-provider-decision.md`

The canonical next gate must become **B6-G7 Staging Key Rotation Drill Gate**.

## Task F — Verification

Run fresh checks:

```powershell
python -m unittest tests.test_launcher_cli tests.test_launcher_config tests.test_windows_authenticode tests.test_windows_signing tests.test_ssl_esigner_signing tests.test_ssl_esigner_signing_cli
cd services/license-update-worker
npm run typecheck
npm test -- --run
cd ../..
git diff --check
git status --short
```

Also inspect the current staging trust profile read-only and confirm `windows_publisher_policy` remains empty. Do not mutate staging.

## Verification evidence

- TDD RED: schema-v2/private-profile tests failed on unsupported schema, missing `distribution_profile`, and missing external override guard.
- Implementation commit: `ebd3378` — `feat: support private distribution trust profiles`.
- Focused Launcher config/CLI GREEN: 30/30 PASS.
- Full Python suite: 646 run / 2 expected skips / 0 failures.
- Worker: typecheck PASS; Vitest 14 files / 92 tests PASS.
- Existing staging trust profile read-only: schema v1, `distribution_profile=legacy`, environment `staging`, channel `stable`, `windows_publisher_policy` empty; no staging mutation performed.

## Completion rule

This amendment is complete only when all canonical documents agree on the following state:

```text
Current distribution profile: Private / Controlled Distribution
Commercial Authenticode: deferred optional hardening; not current launch blocker
B6-G6 Phase A: complete
B6-G6 real procurement/signing: deferred, not completed
Next mandatory gate: B6-G7 Staging Key Rotation Drill Gate
B6-G8 closure: may accept the private profile without real signed artifact
Board 7: still separately gated/unstarted
```
