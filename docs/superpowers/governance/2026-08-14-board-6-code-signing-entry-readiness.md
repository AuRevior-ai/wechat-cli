# Board 6 B6-G6 Code-Signing Entry Readiness Audit

> **READ-ONLY PRE-GATE READINESS — THIS IS NOT B6-G6 EXECUTION OR APPROVAL.**
>
> Date: 2026-08-14
> Branch: `board6/security-delivery-preparation`
> Baseline: `44bd709` (`docs: close board 6 staging behavior acceptance`)
> B6-G5: accepted complete
> B6-G6: **not entered / not authorized for provider selection, payment/application, identity verification, key provisioning, or real signing**

## 1. Purpose and boundary

This audit was performed after B6-G5 closure because the user authorized the agent to continue as far as possible while they were away. The approved Board 6 plan nevertheless makes B6-G6 a special boundary: the signing vendor/publisher identity, any payment/application, identity verification, key provisioning, and the actual signing operation each require separate explicit approval.

Accordingly, this audit is limited to repository inspection, local read-only capability checks, existing-test execution, and fail-closed dry probes. It did **not** choose a signing vendor, open an account/application, purchase anything, install signing software, provision/import/export a key, create a certificate, sign an artifact, change the staging publisher policy, publish a signed release, mutate production, push, or merge.

## 2. Approved B6-G6 requirements

Task 17 requires the selected signing solution to provide:

- non-exportable, hardware-backed, or managed signing key custody;
- Windows Authenticode support;
- RFC3161-compatible timestamping support;
- a least-privilege automation path;
- auditable signing events;
- a publisher identity suitable for formal Windows distribution.

The required execution order remains:

`build -> Authenticode sign -> Windows trust verify -> package signed bytes -> SHA-256 -> Ed25519 release manifest/signature`

Independent evidence must record only public certificate metadata: subject, issuer, validity, thumbprint/public identity, and timestamp status.

## 3. Repository signing architecture — ready portions

### 3.1 Provider-neutral orchestration exists

`scripts/sign_windows_artifacts.py` exposes only a caller-supplied `WindowsSigningProvider` protocol:

- the core signing orchestration does not discover credentials;
- every requested artifact is signed first and immediately verified;
- the provider receives only an explicit file path;
- no vendor-specific secret/environment convention exists in production source.

This is consistent with C2's provider-neutral requirement.

### 3.2 Build/sign/package order is enforced in code and tests

`scripts/package_windows_app.py` already contains provider-injected signed paths:

- `create_signed_package()` builds app + Launcher, signs/verifies both, then packages their signed bytes;
- `create_production_installer()` first creates the signed app/Launcher package, builds the installer from that payload, then signs/verifies the final installer;
- a non-empty `windows_publisher_policy` is required before either signed path can proceed.

A live dry probe against the current staging trust profile returned fail-closed before build/sign:

`ValueError: signed Windows package requires a publisher policy`

The supplied dummy provider was never reached.

### 3.3 Runtime candidate verification is before process launch

`LocalApplicationRuntime.start()` invokes the configured Authenticode verifier on the candidate executable before `ApplicationProcessManager.start()` / `subprocess.Popen()`.

This gives B6-G6 a correct enforcement point for proving unsigned/wrong-publisher candidates fail before launch.

### 3.4 Focused local tests remain green

Fresh pre-G6 focused verification:

- `tests.test_windows_authenticode`
- `tests.test_windows_signing`
- `tests.test_launcher_process`
- `tests.test_launcher_service`
- `tests.test_launcher_cli`
- `tests.test_windows_packaging`

Result: **93 tests / 0 failures**.

The suite proves the provider contract, sign-then-verify ordering, expected publisher enforcement, optional thumbprint enforcement, runtime verification before process start, signed installer sequencing, and existing Windows packaging/rollback behavior. Test output mentioning `missing pywebview` is the intentional fail-fast test branch; real environment import checks below show pywebview is installed.

## 4. Local build prerequisites — ready portions

Read-only environment inventory:

- Python pywebview: `6.2.1`;
- PyInstaller: `6.20.0`;
- WebView2 Runtime standard install directory exists, with current observed versions `151.0.4129.78` and `151.0.4129.86`;
- Windows PowerShell 5.1 exists;
- `Microsoft.PowerShell.Security` exists in the Windows PowerShell module tree.

No ignored `dist/` artifact was retained after the focused tests.

## 5. B6-G6 blockers / required implementation after explicit gate approval

### 5.1 Signing provider/publisher identity is intentionally absent

No real signing vendor or publisher identity has been selected or provisioned. This is the principal governance blocker and is expected by design.

The current repo-external staging deployment trust profile remains:

- schema 1;
- environment `staging`;
- stable channel;
- existing staging API origin;
- release key ID `release-key-staging-01`;
- lease key ID `lease-key-staging-01`;
- **`windows_publisher_policy` empty**.

Therefore a real signed package cannot be created accidentally before B6-G6 configures the approved public publisher identity.

### 5.2 No concrete real signing-provider adapter exists

Production source contains only the `WindowsSigningProvider` protocol. No concrete `signtool`, managed cloud signing, HSM, or vendor adapter exists.

The normal `package_windows_app.py` CLI also does not expose a signed/provider mode; the signed functions currently require a Python caller to inject a provider object.

After provider selection, B6-G6 must implement a provider-specific adapter/controlled entrypoint that:

- accepts only explicit artifact paths;
- takes no private key material from generic repo `.env` files;
- invokes the selected provider with least privilege;
- requires timestamping;
- emits only safe signing metadata;
- fails closed on provider/timestamp/signature errors.

This adapter should not be implemented before the provider/credential contract is approved, because the command and credential boundary are provider-specific.

### 5.3 No signing executable is currently available

Read-only command inventory found no usable signing executable:

- `signtool.exe`: absent from PATH and absent from the standard Windows SDK 10 `bin` tree checked;
- `AzureSignTool.exe`: absent;
- `trusted-signing-cli.exe`: absent.

No software was installed by this audit.

The exact signing client/tool should be chosen only after the approved provider is known; installing an arbitrary signer now would not close the provider/identity gate.

### 5.4 Real Authenticode inspector currently fails because of PowerShell module-path contamination

The project verifier uses bounded Windows PowerShell `Get-AuthenticodeSignature`. On this machine, the inherited `PSModulePath` contains both Windows PowerShell modules and PowerShell 7 module directories. Under that inherited environment:

- `Get-AuthenticodeSignature` is not available;
- importing `Microsoft.PowerShell.Security` fails with TypeData/member conflicts;
- the project's current `inspect_windows_authenticode()` therefore fails closed even on the genuinely Microsoft-signed system `powershell.exe`.

A read-only control test narrowed `PSModulePath` **inside the child process only** to:

`%WINDIR%\System32\WindowsPowerShell\v1.0\Modules`

Under that isolated child environment:

- `Microsoft.PowerShell.Security` loads;
- `Get-AuthenticodeSignature` is available;
- the same system `powershell.exe` returns `Status=Valid` with the Microsoft Windows publisher identity and an available timestamp certificate.

Conclusion: the host is not missing Authenticode support. The verifier needs a deterministic Windows PowerShell module environment (or a native/other stable verifier) before B6-G6 can rely on real signatures.

This is an engineering readiness blocker, but no verifier code was changed in this pre-gate audit.

### 5.5 Public signature evidence model is incomplete for Task 17 Step 4

Current `AuthenticodeSignature` records:

- status;
- subject;
- thumbprint.

Task 17 Step 4 requires recording public evidence for:

- subject;
- **issuer**;
- **certificate validity**;
- thumbprint/public identity;
- **timestamp status**.

The sanitized native PowerShell control proved the platform exposes issuer, NotBefore/NotAfter, and `TimeStamperCertificate` status, but the current Python model discards them.

B6-G6 should extend the read-only signature inspection result/evidence model before final signed-artifact acceptance. This change should remain metadata-only and must not expose private key material.

### 5.6 Publisher renewal/leaf policy must be resolved after provider choice

`AuthenticodePolicy` can enforce both an expected subject and an accepted thumbprint set. However, `DeploymentTrustProfile` currently carries only one `windows_publisher_policy` string, and Launcher runtime constructs a subject-only policy from it.

The approved design warns against relying only on one leaf thumbprint when managed certificate renewal may change leaf certificates. After provider selection, B6-G6 must explicitly decide whether the provider's stable subject/publisher identity is sufficient or whether a bounded accepted-leaf overlap must become part of the embedded trust-profile schema.

No schema change is justified before the provider certificate lifecycle is known.

## 6. What can start immediately after B6-G6 is explicitly approved

Once the user explicitly approves the exact provider/publisher identity and any required payment/application/identity-verification/key-provisioning steps, the implementation sequence should be:

1. freeze the provider's public identity and credential/custody contract;
2. repair the deterministic Authenticode inspection environment and extend public signature evidence metadata under TDD;
3. implement only the approved provider adapter/controlled signing entrypoint;
4. provision the signing identity without exporting private key material to the repo or generic `.env` files;
5. regenerate the staging deployment trust profile with the approved public publisher policy;
6. build app + Launcher + installer;
7. sign and independently verify all three, including timestamp/public certificate evidence;
8. package only the verified signed bytes, then compute SHA-256 and Ed25519-sign the update manifest;
9. run one separately bounded signed staging update acceptance proving pre-launch Authenticode enforcement;
10. reconcile/retain only public signing evidence and stop before B6-G7.

## 7. Explicitly not performed

This pre-gate audit did not:

- select or recommend a commercial signing vendor;
- search for or purchase a certificate/service;
- start a certificate/application workflow;
- perform identity verification;
- install a signing client/SDK;
- create/import/export/provision any signing key;
- modify the staging publisher policy;
- modify Authenticode/product code;
- build a real signed artifact;
- sign or timestamp any artifact;
- publish/register/enable a signed staging release;
- mutate production;
- push or merge.

## 8. Readiness conclusion

**B6-G6 is not ready for immediate real signing with the current machine/repository state, and it remains intentionally blocked on separate explicit approval.**

The provider-neutral architecture and build/runtime enforcement points are ready and freshly green. The remaining work is sharply bounded:

1. approve/select the real publisher/provider and custody model;
2. obtain the provider-specific signing tool/adapter;
3. make real Windows signature inspection deterministic on this host;
4. capture the full public certificate/timestamp evidence required by Task 17;
5. set the approved staging publisher policy;
6. then perform the separately authorized real signing and staging-signed acceptance.

Until those approvals exist, the correct canonical state remains: **B6-G0 through B6-G5 complete; B6-G6 pending separate approval; no production mutation.**
