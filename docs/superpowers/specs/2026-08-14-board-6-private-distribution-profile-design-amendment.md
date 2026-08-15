# Board 6 Private / Controlled Distribution Profile Design Amendment

> **APPROVED DESIGN AMENDMENT**
>
> Date: 2026-08-14
>
> User decision: current launch scope is private / small-scale controlled distribution. Commercial Windows Authenticode signing is deferred and is not a launch or Board 6 closure blocker for this profile.

## 1. Decision

Board 6 now distinguishes two distribution profiles instead of treating commercial Authenticode as universally mandatory.

### Private / Controlled Distribution — current profile

Use this profile when the software is distributed directly to a limited set of known recipients and the product goal is to support controlled remote updates after initial installation.

Required update-trust layers remain:

- server-authoritative license/channel/release eligibility;
- Ed25519-signed release manifest verified by the Launcher;
- exact package SHA-256 and size verification;
- HTTPS/R2 runtime distribution with immutable release provenance retained separately;
- safe extraction/path checks;
- exact failed-candidate identity/suppression;
- health-gated commit and rollback;
- embedded deployment trust profile for API origin and release/lease public keys;
- staging/production isolation and explicit deployment gates.

For this profile, `windows_publisher_policy` is intentionally empty. The Launcher therefore does not require Authenticode publisher verification before starting an otherwise accepted candidate.

Commercial code-signing procurement, identity/KYC, subscription/payment, managed/HSM key provisioning, provider software activation, real certificate use, and real Authenticode staging acceptance are **deferred**.

### Public / Formal Distribution — future profile

Use this profile only when the product moves to broad public download/distribution, formal publisher identity, or when Windows SmartScreen / Unknown Publisher UX becomes an unacceptable product constraint.

This future profile requires:

- a real Windows code-signing identity;
- Authenticode signing of app, Launcher, and installer;
- independent Windows signature/publisher verification;
- non-empty `windows_publisher_policy` bound to the approved publisher identity;
- build -> sign -> verify -> package -> SHA-256 -> Ed25519 manifest signing order;
- a separately authorized provider/account/KYC/payment/key/signing gate.

## 2. Why this scope change is safe for the current goal

Commercial Authenticode and remote-update authenticity solve different problems.

The current remote-update chain already rejects a modified or substituted network-distributed package unless it matches the exact SHA-256/size in a release manifest carrying a valid configured Ed25519 signature and the server has authorized that release for the requesting license/channel/device path.

Authenticode adds an independent Windows-recognized publisher identity and improves initial-install/runtime publisher trust. It is valuable for formal public distribution, but it is not technically required for the current controlled remote-update objective.

## 3. Accepted private-profile tradeoffs

The private profile explicitly accepts all of the following:

- Windows may display Unknown Publisher / SmartScreen warnings during initial installation or execution.
- Windows does not independently attest the publisher identity of unsigned binaries.
- The private profile does not add an Authenticode layer against post-extraction local filesystem tampering by an attacker that already has sufficient local write privileges.
- Initial bootstrap authenticity depends on the controlled direct distribution channel and the operator/user knowing the expected source. Existing cryptographic update protections apply after the Launcher is installed and using the embedded release trust roots.

These are accepted scope tradeoffs for a limited known-recipient launch test, not claims that unsigned binaries are equivalent to publicly code-signed binaries.

## 4. Explicit trust-profile representation

The approved private/public distinction must be represented explicitly in the embedded deployment trust profile; an empty publisher string alone must not silently choose a security mode.

Considered implementation options:

1. infer private distribution whenever `windows_publisher_policy` is empty — rejected because an accidentally missing public publisher would silently weaken policy;
2. add an explicit schema-v2 `distribution_profile` enum — **selected** because intent is embedded, reviewable, and fail-closed;
3. add a production-only boolean exception — rejected because it couples distribution semantics to environment and does not scale cleanly to staging acceptance of the public profile.

Schema-v2 contract:

```text
distribution_profile = private_controlled | public_formal
```

Compatibility/safety rules:

- schema v1 remains accepted with its historical behavior unchanged; in particular, legacy schema-v1 production still requires a non-empty publisher policy;
- schema v2 requires an explicit valid `distribution_profile`;
- production still always requires HTTPS, a non-loopback/non-staging host, and stable channel;
- `public_formal` requires a non-empty `windows_publisher_policy` in every environment;
- `private_controlled` permits an empty publisher policy and therefore permits unsigned binaries while retaining the Ed25519/SHA-256 update chain;
- `distribution_profile` is trust-critical embedded configuration and cannot be supplied/overridden by mutable external launcher config.

This schema change is required before a future private production profile can be built; otherwise the old production validator would remain a hidden commercial-signing blocker.

Implementation evidence: `ebd3378` (`feat: support private distribution trust profiles`) adds the schema-v2 enum, preserves legacy schema-v1 production behavior, exposes the distribution profile through `LauncherConfig`, and prevents mutable external config from overriding it. TDD RED first failed on the missing schema/fields/override guard; GREEN passed the focused Launcher config/CLI suite 30/30. Fresh full Python verification after implementation passed 646 tests with 2 expected skips and 0 failures; Worker typecheck and Vitest 92/92 also passed.

A read-only load of the existing repo-external staging trust profile confirmed it remains untouched at schema v1 / `distribution_profile=legacy` / environment `staging` / channel `stable` / empty `windows_publisher_policy`.

## 5. B6-G6 disposition

B6-G6 Phase A provider-neutral readiness repair/research remains valid completed engineering evidence.

Commit `50e7074` (`feat: add ssl.com esigner signing provider`) is retained as a dormant optional future adapter. It does not configure an SSL.com account, contain credentials, provision a key, change publisher policy, sign an artifact, or create any external side effect.

The remaining B6-G6 real provider procurement/signing work is reclassified as:

> **DEFERRED — optional Public / Formal Distribution hardening; not required for the current Private / Controlled Distribution profile.**

Board 6 must not claim that real B6-G6 signing was completed. Closure evidence must instead record that it was explicitly deferred by approved scope change.

## 6. Board 6 closure consequences

For the current private profile, Board 6 closure no longer requires a real signed staging artifact/public certificate metadata.

Closure must instead prove and record:

- staging `windows_publisher_policy` remains intentionally empty for this profile;
- Ed25519 manifest verification remains required;
- package SHA-256/size verification remains required;
- server-authoritative release eligibility remains accepted;
- safe extraction, health-gated commit, rollback, and failed-candidate suppression remain accepted;
- no commercial signing identity/provider was provisioned or used;
- the public/formal Authenticode profile remains a future optional hardening track.

The next mandatory Board 6 gate is therefore **B6-G7 Staging Key Rotation Drill Gate**, followed by **B6-G8 Board 6 Closure Gate**.

## 7. Authorization boundary

This amendment does not authorize:

- payment or subscription;
- certificate application or KYC;
- signing-tool/provider installation or activation;
- managed/HSM key provisioning;
- real Authenticode signing;
- staging publisher-policy mutation to a real publisher;
- a new release publication/enablement;
- production provisioning/deployment;
- push, merge, tag modification, reset, rebase, or amend;
- B6-G7 or B6-G8 cloud/credential mutations without their own gate approval.
