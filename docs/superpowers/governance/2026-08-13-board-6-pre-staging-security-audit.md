# Board 6 Pre-Staging Security Audit

Date: 2026-08-13

Status: **LOCAL SECURITY BASELINE VERIFIED — STAGING NOT AUTHORIZED**

## 1. Scope and frozen evidence boundaries

This audit closes the local/read-only verification phase after the separately authorized B6-G0, B6-G1, B6-G2 and B6-G3 local gates. It does not authorize staging, cloud or production mutation.

Frozen references remain:

- frozen main: `a579a25cb7f16e6fdf88d618252b4a5cbffef53d`
- Board 5 accepted-complete evidence: `67d3dec0fd1c4a02c87be1ab79c4f78ea63f49d6`
- Board 6 branch: `board6/security-delivery-preparation`
- B6-G3 implementation base: `6b9e8b774ac1fedc62b7c4c843d8769300af7d39`
- current B6-G3 implementation HEAD before this audit: `1a074472360907be10d336729c3c28e0584b00f3`

The unrelated untracked `NUL` entry in the Board 6 worktree was preserved and was not staged, deleted or modified.

## 2. B6-G3 local implementation lineage

B6-G3 was implemented as five independent local commits:

1. `4b7fbfee3dcc6718cdca35a639a4583eb8449b2d` — `fix: pin launcher webview compatibility boundary`
2. `a1dc6bddc8687b827da84d6dd85278144f606c58` — `feat: embed launcher deployment trust profile`
3. `9b5471057fc08db3d04715eb4bb5c85ff80933dc` — `feat: enforce windows artifact authenticity`
4. `8d7493e423d528f1ff90acfa0f660b57744b8dad` — `feat: add signed windows installer target`
5. `1a074472360907be10d336729c3c28e0584b00f3` — `feat: fail closed worker environment deployment`

No reset, rebase, amend, merge or push was used to produce this lineage.

## 3. Local security controls now implemented

### 3.1 pywebview compatibility boundary

- `pywebview` is source-pinned to the Board 5 accepted version `6.2.1`.
- pre-load URL access is isolated in `wechat_cli/launcher/webview_compat.py`.
- the adapter uses only the accepted backend `window.gui.get_current_url(window.uid)` path during `before_load`.
- missing backend state, missing UID and empty/non-string URLs fail closed as `WebViewUnavailable`.
- `LauncherWindow` consumes an injected preload URL reader and no longer owns the backend-internal call itself.

No dependency installation or upgrade was performed under B6-G3.

### 3.2 embedded Launcher deployment trust profile

`DeploymentTrustProfile` now owns trust-critical deployment state:

- environment
- API authority
- expected release channel
- fingerprint salt
- release public keys
- lease public keys
- Windows publisher policy

The key maps are immutable at runtime. Production profiles fail closed for non-HTTPS API authority, loopback authority, staging-named authority, beta channel or missing Windows publisher policy.

External `launcher-config.json` is reduced to operational schema v2 and may currently contain only non-trust operational fields such as `port`. When an embedded trust profile is present, external trust-critical fields are rejected instead of merged or overridden.

Launcher runtime loads the trust profile from the fixed embedded PyInstaller resource path before loading external operational configuration. Fresh Launcher builds require an explicit, successfully parsed trust-profile file and embed it at the fixed runtime resource path.

### 3.3 Windows artifact authenticity boundary

`wechat_cli/windows/authenticode.py` adds a fail-closed Authenticode policy boundary:

- bounded PowerShell `Get-AuthenticodeSignature` inspection
- no shell-string execution
- explicit signature status validation
- exact publisher-subject policy
- optional normalized certificate-thumbprint allowlist
- malformed inspection data or inspection failure fails closed

`LocalApplicationRuntime` verifies the final executable path before `ApplicationProcessManager.start()` is invoked. Automated evidence proves a rejected signature produces zero process-start calls. This covers the normal current version, update candidate and rollback previous-version process-start boundary through the same runtime abstraction.

`WindowsSigningProvider` is deliberately only an injected signing abstraction. B6-G3 added no certificate discovery, private-key loading, credential environment lookup or real signing provider. The tested package orchestration order is:

`build -> sign app -> verify app -> sign Launcher -> verify Launcher -> package`

A real signing identity remains deferred to B6-G6.

### 3.4 production-capable installer target

A Windows PyInstaller `installer` target now exists with:

- entrypoint `packaging/windows/installer_entry.py`
- explicit embedded bootstrap payload
- no implicit pywebview dependency
- reuse of the existing transaction-aware `install.ps1`
- `shell=False` PowerShell invocation
- user-local installation semantics inherited from the accepted installer script

The historical ZIP bootstrap remains explicitly marked:

- `production_capable=false`
- `distribution_tier=compatibility`

`create_production_installer()` instead prepares a separate embedded payload marked:

- `production_capable=true`
- `distribution_tier=production-installer`

The installer EXE is then separately signed and Authenticode-verified through the injected provider boundary before it becomes the returned deliverable.

No installer was executed and no real certificate was used under B6-G3.

### 3.5 fail-closed Worker deployment preflight

The top-level/default source Worker identity is now `wechat-cli-license-update-local`, distinct from staging and production. Production source explicitly declares:

- `workers_dev=false`
- `routes=[]`

The empty route is intentional: Board 6 local work does not invent or provision a production domain, and the preflight requires a non-empty custom production route before production can ever pass.

`services/license-update-worker/deployment-policy.json` is a non-secret validated policy source for:

- exact local/staging/production Worker identities
- production workers.dev/custom-route requirements
- required D1/R2 binding names
- versioned Secret-purpose prefixes
- non-versioned required Secret names
- local/staging legacy-compatibility Secret names

`scripts/deploy_worker.py` exposes only a `preflight` action. It has no deploy function or deploy subcommand. Preflight fails closed for:

- missing/unknown environment
- Worker identity mismatch
- missing DB/R2 binding
- staging/production D1 or R2 collisions
- placeholder staging/production resource identifiers
- production workers.dev exposure
- missing production custom route
- production route/API-origin mismatch
- deployment trust-profile environment mismatch
- deployment trust-profile API-origin mismatch
- invalid secret-version selector metadata
- missing required Secret names

Secret readiness compares names only. No Secret value is accepted, fetched, printed or persisted by this tool.

The current repository production source is deliberately **not deployment-ready**: the production D1 ID remains a replacement placeholder and the production route list remains empty. Automated tests assert this fail-closed state.

Production required Secret names intentionally do not include `GITHUB_RELEASE_READ_TOKEN`; the production runtime distribution policy is R2-only. Staging/local compatibility may still declare the legacy GitHub read token while Board 5/legacy rows remain relevant.

## 4. Fresh complete local verification

Fresh verification was run after all five B6-G3 implementation commits.

### Python

Command:

`python -m unittest discover -s tests`

Result:

- 607 tests run
- 2 expected platform skips
- 0 failures
- suite result: `OK`

Expected negative-path output from parser/preflight and missing-pywebview tests was observed while the suite still completed successfully.

### Worker

Commands:

- `npm run typecheck`
- `npm test -- --run`

Result:

- TypeScript typecheck: PASS
- Vitest: 13 files passed
- Vitest: 89 tests passed
- 0 failures

### B6-G3 diff integrity

`git diff 6b9e8b7..1a07447 --check` passed with no whitespace errors.

The B6-G3 implementation range contains 26 changed files, 2842 insertions and 60 deletions before this audit document. Worktree status after the implementation commits contained only the separately preserved `?? NUL` entry.

## 5. Static trust-boundary audit

The required static searches produced:

- Board 5 packaging-helper dependency in production code: 0 hits
- wildcard `Access-Control-Allow-Origin: *` in Worker source: 0 hits
- device-token pepper reused for rate-limit identity: 0 hits
- download-ticket secret reused for diagnostic upload: 0 hits
- `GITHUB_RELEASE_READ_TOKEN`: 2 source references remain, both in the legacy GitHub distribution adapter/type contract

The remaining GitHub credential references are explicitly classified as migration/legacy compatibility. `fetchReleasePackage()` rejects the GitHub backend when `ENVIRONMENT === "production"` before constructing the GitHub Authorization header. Production R2 distribution therefore does not depend on the long-lived GitHub runtime read credential.

## 6. Sensitive-value audit

A sensitive-shape scan was run over the changed B6-G3 non-test diff. It found zero matches for targeted real-value shapes including:

- GitHub fine-grained PATs
- private-key PEM blocks
- long-form `wcadmin` credentials
- short-lived `wcas` session credentials
- full license-key-shaped values
- device/download token-shaped values

Synthetic test fixtures remain test-only and are not treated as production credentials.

## 7. Remaining staging-only and production-only unknowns

The local baseline deliberately does not resolve the following external-state questions:

1. Existing staging Secret values have not been copied into the new versioned `_V1` Secret names. Deploying the new Worker before a separately authorized migration would fail closed.
2. No Cloudflare Access application, policy, exact staging issuer/JWKS/audience/origin configuration or production Access policy was created or changed.
3. No B6-G1 R2 migration or B6-G2 D1 migrations were applied to staging under these local gates.
4. No real code-signing certificate was purchased, enrolled, provisioned or used. B6-G3 used only abstractions, fakes and policy tests.
5. No real staging-signed app, Launcher or installer artifact has been accepted. That remains B6-G6.
6. Production D1 remains a replacement placeholder and production custom routes remain unconfigured by design.
7. Production domain/ingress and China-domain/ICP strategy remain unresolved production-boundary work.
8. No production resource was provisioned or mutated.

## 8. External side-effect statement

B6-G0 through B6-G3 local work performed no:

- Worker staging or production deployment
- D1/R2 production provisioning
- staging migration under B6-G3
- Cloudflare Access/DNS mutation
- real Secret add/switch/retire
- credential rotation
- real signing operation
- certificate purchase/application
- GitHub release publication/registration/enablement
- Git push or merge
- Board 5 evidence cleanup

## 9. Gate conclusion

The Board 6 local pre-staging security baseline is verified for the source lineage represented by B6-G0 through B6-G3. This is **not** staging acceptance and is **not** production readiness.

The next possible gate is **B6-G4 Staging Infrastructure Gate**, which requires a new explicit authorization before any external mutation. B6-G4 must begin with read-only preflight and an exact mutation plan for versioned Secret migration, staging bindings/migrations, Access configuration and deployment prerequisites. No B6-G4 action is authorized by this audit.
