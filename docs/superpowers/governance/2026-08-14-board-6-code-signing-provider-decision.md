# Board 6 Code-Signing Provider Decision

> **RETAINED RESEARCH — commercial signing is deferred for the approved Private / Controlled Distribution profile.**
>
> This document records the provider-neutral B6-G6 Phase A local readiness repair and provider research. It is no longer the current next-action decision document: `docs/superpowers/specs/2026-08-14-board-6-private-distribution-profile-design-amendment.md` explicitly defers commercial Authenticode to a future Public / Formal Distribution profile. This document does **not** authorize a purchase, certificate application, identity verification, paid subscription, signing-key provisioning, signer installation/activation, staging publisher-policy mutation, real signing, signed release publication, B6-G7, B6-G8, Board 7, production mutation, push, merge, or tag modification.

Date: 2026-08-14

Branch: `board6/security-delivery-preparation`

Phase A implementation commits:

- `9f4ad0f` — `fix: make windows authenticode inspection deterministic`
- `e9cb67b` — `feat: record complete authenticode public evidence`

## 1. Current Board 6 boundary

Canonical execution state remains:

- Board 5: **accepted complete** at evidence HEAD `67d3dec0fd1c4a02c87be1ab79c4f78ea63f49d6`.
- Board 6: **in progress**.
- B6-G0: complete.
- B6-G1: complete.
- B6-G2: complete.
- B6-G3: complete.
- B6-G4: complete.
- B6-G5: accepted complete.
- B6-G6 real procurement/signing: **not completed; explicitly deferred optional Public / Formal Distribution hardening and not a current Board 6 blocker**.
- B6-G7: not entered.
- B6-G8: not entered.
- Board 7: unstarted.
- Frozen main remains `a579a25cb7f16e6fdf88d618252b4a5cbffef53d` and must not be changed by this phase.
- No push, merge, tag mutation, production mutation, real code signing, certificate application, or payment occurred in Phase A.

The staging `windows_publisher_policy` remains intentionally empty. Under the approved Private / Controlled Distribution profile, that empty publisher policy is now the deliberate current operating mode rather than merely a pre-signing placeholder. Phase A does not insert a fake, Microsoft, temporary production, or arbitrary publisher identity merely to make signing tests run.

## 2. Board 6 worktree `NUL` cleanup status

The Board 6 worktree root `NUL` was reverified before any cleanup attempt:

- worktree: `C:/Users/28276/.devspace/worktrees/wechat-cli-f3860a02`
- branch: `board6/security-delivery-preparation`
- Git state: `?? NUL`
- size: exactly 95 bytes
- content: exactly the historical `rg: docs/deployment/*board-6*: ... (os error 123)` error text

This file is safe to remove, but the current DevSpace contract exposes no dedicated delete primitive. Phase A therefore **did not use shell deletion as a workaround**.

Status: `Board6 NUL cleanup verified safe but blocked by tool contract`.

This does not apply to the unrelated frozen-main `D:/use_as_desktop/Wechat__CLI/wechat-cli/NUL`, which remains strictly protected.

## 3. G5 residual cleanup handoff

Two historical G5 disposable device rows still report `status='active'`, while both parent licenses are `revoked`. The authentication path therefore rejects those credentials through the revoked parent license; the rows are not a live authorization path.

They remain a **non-blocking row-level cleanup residual** and are not a B6-G6 blocker.

Future disposable acceptance cleanup should prefer this order:

```text
unbind disposable devices
-> revoke disposable license
```

Phase A does not implement a revoked-parent safe-cleanup endpoint, does not revive a principal/session, does not reactivate a license, and does not directly UPDATE D1. Whether to add a product capability for safe cleanup under a revoked parent is deferred to a separate design and authorization decision.

## 4. Deterministic Authenticode inspector repair

### 4.1 Frozen root cause

The pre-Phase-A readiness audit had already isolated the local failure:

- the host's inherited `PSModulePath` mixes PowerShell 7 and Windows PowerShell module trees;
- Windows PowerShell 5.1 loading `Microsoft.PowerShell.Security` under that mixed environment encounters TypeData conflicts;
- the old project inspector inherited that environment and failed closed even when inspecting a valid Microsoft-signed system executable;
- a read-only control using only the Windows PowerShell built-in module tree successfully loaded `Microsoft.PowerShell.Security` and returned `Status=Valid` for the same executable.

Phase A did not repeat broad root-cause exploration. It implemented the already-proven child-only isolation model under TDD.

### 4.2 TDD repair

The inspector now:

- resolves Windows PowerShell 5.1 explicitly from `%SystemRoot%/System32/WindowsPowerShell/v1.0/powershell.exe`;
- never relies on a `pwsh` or `powershell.exe` found earlier on `PATH`;
- always uses `-NoProfile` and `-NonInteractive`;
- creates a child-only environment;
- sets child `PSModulePath` to `%SystemRoot%/System32/WindowsPowerShell/v1.0/Modules`;
- explicitly imports `Microsoft.PowerShell.Security -ErrorAction Stop`;
- never changes the process-global, user, or system PowerShell environment;
- never edits PowerShell installation, profile, registry, or module installation;
- passes the target path through child-only `WECHAT_CLI_AUTHENTICODE_TARGET`, not via an unreliable `$args[0]` command-line assumption;
- fails closed on module execution errors, malformed JSON, parser errors, and structurally incomplete evidence.

The second target-path behavior was discovered by a real integration probe after the first unit-level repair: Windows PowerShell `-Command <script> <path>` did not populate `$args[0]` as the old design assumed. A single-variable control using a child-only environment variable returned `Valid`, then a new RED test froze that contract before the minimal implementation change.

### 4.3 Local evidence

Before the first implementation change, the new deterministic-environment test failed because the command still used bare `powershell.exe` and inherited the host environment.

Before the target-transport implementation change, the new target-env test failed because `WECHAT_CLI_AUTHENTICODE_TARGET` did not exist.

After the repairs:

- Authenticode focused suite: 13/13 PASS at the deterministic-inspector commit boundary.
- Launcher process focused regression: 13/13 PASS.
- `git diff --check`: PASS.
- real read-only system-signed probe through the project inspector: `Status=Valid`.

## 5. Expanded public Authenticode evidence contract

`AuthenticodeSignature` now records public verification evidence without storing any signing secret:

- signature status;
- signer subject;
- signer issuer;
- signer certificate validity start;
- signer certificate validity end;
- signer thumbprint/public leaf identity;
- normalized timestamp evidence status;
- timestamper subject when present;
- timestamper issuer when present;
- timestamper certificate validity start/end when present.

### 5.1 Timestamp semantics

The normalized timestamp contract is deliberately conservative:

```text
absent
present
```

`present` means only that Windows `Get-AuthenticodeSignature` exposed a non-null `TimeStamperCertificate` and that the expected public timestamper metadata was structurally available.

It **does not mean** that this Python result independently revalidated the RFC3161 token or proves a separate cryptographic timestamp-validation result. Phase A therefore never labels the state `validated` merely because `TimeStamperCertificate` exists.

If B6-G6 later needs a stronger normalized timestamp state, that must be backed by a Windows/provider API that actually exposes the stronger validation evidence.

### 5.2 Parser fail-closed rules

For `Status=Valid`, incomplete signer subject/issuer/validity/thumbprint evidence is rejected.

If timestamp evidence says present but its public timestamper fields are incomplete, parsing is rejected.

If timestamp evidence says absent while timestamper public fields are populated, parsing is rejected.

No private key, signing token, PIN, account password, OTP, API key, or certificate private material enters this result model.

### 5.3 Windows system-signed read-only probe

Phase A used the existing Windows PowerShell system executable only as an inspector integration probe. The system file was not modified.

Observed public evidence from the project inspector:

- Authenticode status: `Valid`
- signer subject: `CN=Microsoft Windows, O=Microsoft Corporation, L=Redmond, S=Washington, C=US`
- signer issuer: `CN=Microsoft Windows Production PCA 2011, O=Microsoft Corporation, L=Redmond, S=Washington, C=US`
- signer certificate validity: `2026-04-16T19:09:15Z` through `2026-10-17T19:09:15Z`
- public leaf thumbprint: `DC91E564D5BC1E3A8E02D6A8508682ABEA8A2443`
- normalized timestamp status: `present`
- timestamper subject: Microsoft Time-Stamp Service
- timestamper issuer: Microsoft Time-Stamp PCA 2010
- timestamper certificate validity: `2026-02-19T19:40:01Z` through `2027-05-17T19:40:01Z`

This proves only that the repaired inspector can read a real, existing Windows signature and its public metadata. It is **not** WeChat CLI publisher acceptance and does not authorize Microsoft as this project's signing identity.

### 5.4 Focused regression evidence

After the public-evidence contract change:

```text
Authenticode + signing provider protocol + Launcher process/service/CLI + Windows packaging/installer
103 / 103 PASS
```

This is local provider-neutral evidence only. Full Phase A closure verification is recorded separately in canonical state after it is run.

## 6. Provider decision criteria

The approved Board 6 design requires the real provider to support:

1. Windows Authenticode.
2. Public publisher identity appropriate for formal Windows distribution.
3. Non-exportable, hardware-backed, or managed key custody.
4. Timestamping suitable for long-lived signed artifacts.
5. A Windows CLI/API path.
6. Future GitHub Actions automation.
7. Least-privilege credentials/roles.
8. Auditable signing events.
9. A certificate lifecycle compatible with the embedded publisher trust model.
10. A legally and geographically available application path for the actual publisher.

Provider selection must happen before any provider-specific adapter or publisher-policy schema is frozen.

The actual legal publisher identity, entity type, and country/region have not been frozen in Board 6 evidence. Therefore Phase A cannot truthfully mark Microsoft Public Trust eligibility as already satisfied or rejected for this project. The recommendation below is conditional on that explicit user-side identity decision; no identity document or account data was collected during research.

## 7. Current provider comparison

### 7.1 Option A — Microsoft Azure Artifact Signing Public Trust

**Overall fit:** technically strongest option **if the publisher is eligible**.

Official current facts:

- Microsoft recommends Artifact Signing for non-Store Windows application distribution.
- Public Trust supports Win32 Authenticode.
- Basic SKU: USD 9.99/month, 5,000 signatures/month, then USD 0.005/signature.
- Premium SKU: USD 99.99/month, 100,000 signatures/month, then USD 0.005/signature.
- A paid Azure subscription is required; free, trial, or sponsored subscriptions are unsupported.
- Public Trust eligibility is currently limited to organizations in the USA, Canada, European Union, and United Kingdom, and individual developers in the USA and Canada.
- Individual public identity validation uses the Azure billing identity and government-identity verification flow.
- The service keeps the Authenticode certificate/private key; the private certificate/key is not handed to the user.
- SignTool, GitHub Actions, Azure DevOps, PowerShell, and an Artifact Signing SDK are supported integrations.
- `Artifact Signing Certificate Profile Signer` is a purpose-specific signing role and can view signing history; identity validation uses a separate Identity Verifier role.
- Azure diagnostic settings can route signing transaction logs.
- Public Trust certificates are short-lived; Microsoft documents a new certificate being issued daily with roughly three-day validity. Timestamping is therefore critical.
- Microsoft does not allow an arbitrary custom CN/O for the public identity.

**Key custody:** Microsoft-managed signing service; no exportable project PFX.

**Timestamp:** Microsoft timestamp endpoint supported by the SignTool integration.

**CI/GitHub fit:** excellent; first-party documented GitHub Actions and SignTool integration.

**Least privilege/audit:** strongest of the three reviewed options because Azure RBAC separates identity management from signing and supports signing transaction logs.

**Certificate lifecycle implication:** leaf certificates and thumbprints rotate frequently by design. If selected, the runtime trust model must **not pin a single leaf thumbprint as the long-lived publisher identity**. A stable validated publisher subject/provider identity is the natural starting point, with the exact public policy frozen only after a real certificate profile is provisioned and inspected.

**Eligibility risk:** this is a hard pre-purchase gate. An individual outside the USA/Canada cannot use Microsoft Public Trust under the current official eligibility statement. An organization outside USA/Canada/EU/UK is likewise not eligible for Public Trust. Private Trust is not a substitute for publicly distributed Windows binaries.

**Concrete provider adapter if selected:**

```text
ArtifactSigningProvider
-> pinned Windows SDK signtool.exe
-> pinned Azure.CodeSigning.Dlib matching architecture/version
-> explicit metadata file containing only endpoint/account/profile identifiers
-> Azure credential source constrained to Artifact Signing Certificate Profile Signer
-> Microsoft RFC3161 timestamp endpoint
-> project verify_windows_authenticode() after every sign
```

The adapter must not auto-discover a broader Azure identity, print tokens, or provision resources. Credential mode for local staging and future GitHub Actions must be separately frozen after account setup.

### 7.2 Option B — SSL.com IV Code Signing + eSigner for Code

**Overall fit:** strongest practical individual-developer fallback when Microsoft Public Trust eligibility is unavailable, subject to pre-purchase country/identity confirmation.

Official current facts:

- SSL.com explicitly markets IV Code Signing to independent developers, freelancers, open-source maintainers, students, and hobbyists without a business entity.
- IV Code Signing is currently listed at USD 129/year.
- eSigner cloud signing Tier 1 is currently shown at USD 15/month with 240 signings and one credential; new certificates receive 30 days of eSigner cloud signing free before subscription fees apply.
- IV requires government-issued personal identity validation.
- SSL.com documents automated ID + liveness verification and a manual government-document path.
- The May 2026 identity guide lists an Asia-Pacific category including Japan, South Korea, Singapore, the Philippines, "and others"; it does **not explicitly name mainland China in the reviewed text**. Eligibility for the actual applicant country must therefore be confirmed with SSL.com before any purchase.
- eSigner is a cloud-HSM-backed signing service; SSL.com states the private key remains in its cloud HSM and code-signing private keys are not downloadable as PFX.
- eSigner CKA exposes the remote signing certificate to Windows through a KSP/CNG integration so standard `signtool.exe` can sign.
- Official CI examples cover GitHub Actions and other CI platforms.
- Official SignTool examples use SHA-256 and the SSL.com timestamp endpoint.
- Public code-signing certificate issuance is now subject to the CA/B Forum short maximum validity; SSL.com documents a 458-day issuance maximum and reissuance within purchased terms.

**Key custody:** non-exportable cloud HSM through eSigner; no project PFX.

**Timestamp:** official SignTool examples use SSL.com's timestamp service.

**CI/GitHub fit:** good; eSigner CKA is explicitly documented for GitHub Actions/CI.

**Least privilege/audit:** automation is available, but the reviewed public documentation is less explicit than Azure RBAC or DigiCert KeyLocker about a narrow bot-only signer role and detailed per-signature audit authorization. The exact CKA/CSC credential surface and audit retention must be confirmed before provisioning.

**Certificate lifecycle implication:** renewal/reissue creates a new leaf certificate, so a permanent single-leaf thumbprint pin is unsuitable. The verified personal publisher subject is expected to be the more stable public identity if the legal identity is unchanged; that is an inference that must be confirmed against the first real issued/reissued certificate lifecycle before production policy is frozen.

**Concrete provider adapter if selected:**

```text
SslEsignerProvider
-> pinned Windows SDK signtool.exe
-> installed/pinned eSigner CKA provider
-> load exactly the authorized eSigner certificate into the intended Windows user store
-> resolve exactly one certificate under the approved public publisher policy
-> signtool sign /fd sha256 /tr http://ts.ssl.com /td sha256 /sha1 <current public leaf>
-> project verify_windows_authenticode() after every sign
```

The provider adapter must not accept a private key or PFX. Any CKA/CSC username/password/TOTP-secret or automation credential must be treated as a separately authorized secret and never written into source or ordinary `.env` files.

### 7.3 Option C — DigiCert Code Signing + KeyLocker

**Overall fit:** strongest enterprise/organization-oriented fallback, but the current official workflow is organization-based and materially more expensive for this project's expected signing volume.

Official current facts:

- DigiCert's current retail comparison page lists Code Signing + KeyLocker at USD 65/month/certificate on a 12-month auto-renewing subscription and separately displays `subscription $996.00`. Those two displayed values are arithmetically inconsistent; this document records the provider page as-is rather than silently correcting its commercial presentation.
- The same page lists EV Code Signing + KeyLocker at USD 83/month/certificate with displayed `subscription $1,272.00`.
- KeyLocker includes 1,000 signatures per certificate/year and one assigned signer at a time; additional signatures can be purchased in increments of 1,000.
- DigiCert describes KeyLocker as cloud key storage/signing with FIPS-backed controls.
- The KeyLocker Signer role can view assigned certificate/keypair details and sign; DigiCert also exposes signature logs.
- Official GitHub examples support KeyLocker client tools/KSP/PKCS#11 and SignTool-style Windows signing with DigiCert timestamping.
- Current CertCentral code-signing issuance requires an active organization validated for CS or EV CS plus a validated verified contact authorized to approve the order.
- DigiCert's 2026 request documentation states a maximum 459-day public code-signing certificate validity.

**Applicant fit:** no individual code-signing path was found in the current CertCentral code-signing workflow reviewed for this research. Treat this option as organization-dependent unless DigiCert gives a current written alternative.

**Country support:** the reviewed official pages do not provide a simple public country allowlist for code signing. Organization validation, verified contact, sanctions/compliance, and order availability must be confirmed for the actual legal entity before purchase.

**Key custody:** KeyLocker cloud key storage; no project-owned exportable private key is needed.

**Timestamp:** DigiCert timestamp endpoint is documented in its signing examples.

**CI/GitHub fit:** good; KSP/PKCS#11 and GitHub workflow examples are documented.

**Least privilege/audit:** strong; dedicated KeyLocker Signer role plus signature logs, but the CI credential set (API key/client auth certificate/host or equivalent) must be treated as sensitive and narrowed after account setup.

**Certificate lifecycle implication:** renewal/reissue produces a new public leaf; do not design a permanent one-thumbprint trust contract before inspecting the real lifecycle. The organization subject is expected to be more stable than the leaf when organization identity remains unchanged, but the actual policy must be frozen from real provider evidence.

**Concrete provider adapter if selected:**

```text
DigiCertKeyLockerProvider
-> pinned KeyLocker client/KSP version
-> pinned Windows SDK signtool.exe
-> exact assigned KeyLocker certificate/keypair identity
-> least-privilege KeyLocker Signer credentials
-> DigiCert RFC3161 timestamp endpoint
-> project verify_windows_authenticode() after every sign
```

The adapter must never export the KeyLocker private key and must not embed DigiCert API/client-auth credentials in command-line arguments or logs.

## 8. Decision matrix

| Dimension | Microsoft Artifact Signing Basic | SSL.com IV + eSigner | DigiCert Code Signing + KeyLocker |
|---|---|---|---|
| Windows Authenticode | Yes | Yes | Yes |
| Publisher identity model | Microsoft Public Trust validated org/individual | IV personal identity; OV/EV also available | CS/EV CS organization identity |
| Explicit individual path | Yes, USA/Canada only | Yes | Not found in reviewed current CS workflow |
| Public Trust geography | Org: USA/Canada/EU/UK; individual: USA/Canada | Broader IV guide; mainland-China support not explicit and must be confirmed | No simple public country list found; organization validation/order eligibility required |
| Private key custody | Microsoft managed; cert/key not handed to user | eSigner cloud HSM; non-exportable | KeyLocker cloud HSM/key storage |
| RFC3161 timestamp path | Microsoft timestamp service | SSL.com timestamp service | DigiCert timestamp service |
| Windows signer integration | SignTool + Azure dlib / SDK | SignTool + eSigner CKA/KSP | SignTool + KeyLocker KSP/client tools |
| GitHub Actions | First-party documented | Official CI/CKA examples | Official KSP/PKCS#11 examples |
| Least privilege | Strong Azure RBAC signer role | Needs exact automation-credential confirmation | Strong KeyLocker Signer role |
| Audit evidence | Azure signing history/diagnostic logs | Public docs reviewed are less explicit; confirm before purchase | Signature logs documented |
| Leaf lifecycle | New short-lived cert roughly daily | Reissue/renewal changes leaf | Renewal/reissue changes leaf |
| Long-lived leaf thumbprint pin | Unsuitable | Unsuitable | Unsuitable |
| Current headline price | USD 9.99/month Basic; 5,000 signatures/month | IV USD 129/year + eSigner Tier 1 USD 15/month; 240 signings, 1 credential | USD 65/month shown, also `subscription $996` shown by provider; 1,000 signings/year |
| Extra prerequisites | Paid Azure subscription + Entra + eligible identity | SSL.com account + IV + eSigner enrollment | CertCentral + validated organization + verified contact |
| Best fit | Eligible developer/org wanting strongest automation/RBAC and lowest cost | Individual developer when Microsoft geography is unavailable | Organization/enterprise needing CertCentral/KeyLocker controls |

## 9. Recommendation

### 9.1 Preferred provider when eligible: Microsoft Artifact Signing Basic

If the actual publisher satisfies Microsoft Public Trust geography and identity eligibility and can use a paid Azure subscription, **Microsoft Artifact Signing Basic is the preferred technical choice** for this project.

Reasons:

- lowest reviewed base cost;
- fully managed short-lived certificates and private-key custody;
- no exportable PFX workflow;
- first-party SignTool and GitHub Actions paths;
- explicit least-privilege signer RBAC;
- explicit signing-transaction logging;
- high monthly signing quota relative to this project's expected volume;
- certificate lifecycle strongly encourages the correct trust model: stable publisher identity rather than brittle leaf pinning.

The hard downside is eligibility. No purchase should be attempted until the actual legal publisher region/type is confirmed to fall inside Microsoft's current Public Trust allowlist.

### 9.2 Practical individual fallback: SSL.com IV + eSigner entry tier

If Microsoft Public Trust is unavailable to the actual individual publisher because of geography or entity type, **SSL.com IV + eSigner is the practical next choice** among the reviewed options because it has an explicit individual-developer path and managed non-exportable signing.

Before purchase, obtain written/checkout confirmation that the applicant's actual country and government document are accepted for IV Code Signing. The current official Asia-Pacific guide is broader than Microsoft's list but does not explicitly name mainland China in the reviewed text.

### 9.3 DigiCert position

Do not choose DigiCert KeyLocker by default for this project unless an organization-based publisher identity or CertCentral/enterprise governance requirement makes those controls worth the higher commercial cost. Its current code-signing workflow requires organization validation and a verified contact.

## 10. Publisher-policy implications

Phase A intentionally leaves:

```text
windows_publisher_policy = ""
```

unchanged.

No provider-specific schema change is justified before the provider and first real public certificate/profile are chosen.

Current policy direction after provider selection should be:

1. obtain the real public certificate/profile without signing project artifacts yet;
2. inspect provider-documented renewal/reissue behavior;
3. inspect the actual subject/issuer/public leaf fields;
4. decide whether the stable trust anchor is:
   - verified publisher subject only;
   - publisher subject plus a bounded overlap set of current leaf thumbprints;
   - a provider-specific public identity/profile contract;
5. only then modify the embedded staging publisher policy under a separately approved B6-G6 real-signing gate.

For Microsoft Artifact Signing, a permanent leaf-thumbprint requirement is already incompatible with the documented daily short-lived certificate lifecycle.

For SSL.com and DigiCert, leaf changes on reissue/renewal also argue against an indefinite one-leaf pin, but the exact overlap/subject contract must be based on the selected provider's real issuance evidence rather than assumption.

## 11. User action and external side-effect matrix

| Provider | User/external action | Side effect class | Allowed in Phase A? |
|---|---|---|---|
| Microsoft | Confirm actual Public Trust identity/geography eligibility | Read-only decision | Yes |
| Microsoft | Create/upgrade to paid Azure subscription if needed | Account/billing | **No** |
| Microsoft | Register Artifact Signing resource/provider and create account | Cloud account/resource mutation | **No** |
| Microsoft | Perform identity validation in Azure portal | Identity/KYC | **No** |
| Microsoft | Create Public Trust certificate profile | Managed signing-key/certificate provisioning | **No** |
| Microsoft | Assign Artifact Signing signer role | Account permission mutation | **No** |
| Microsoft | Install Windows SDK SignTool/Azure signing dlib | Local software installation | **No** until provider approval |
| Microsoft | Sign app/Launcher/installer | Real signing | **No** |
| SSL.com | Confirm IV country/document eligibility with SSL.com | Read-only/pre-purchase confirmation | Yes |
| SSL.com | Purchase IV certificate | Payment/certificate order | **No** |
| SSL.com | Complete government-ID/liveness/manual validation | Identity/KYC | **No** |
| SSL.com | Purchase/activate eSigner subscription | Payment/service activation | **No** |
| SSL.com | Enroll certificate/key in eSigner cloud HSM | Managed key provisioning | **No** |
| SSL.com | Install Windows SDK SignTool/eSigner CKA | Local software installation | **No** until provider approval |
| SSL.com | Configure CKA/automation credentials | Credential provisioning | **No** |
| SSL.com | Sign app/Launcher/installer | Real signing | **No** |
| DigiCert | Confirm organization/order eligibility | Read-only decision | Yes |
| DigiCert | Create/use CertCentral subscription/order | Account/payment | **No** |
| DigiCert | Submit organization + verified contact validation | Organization/identity validation | **No** |
| DigiCert | Purchase Code Signing + KeyLocker | Payment/certificate order | **No** |
| DigiCert | Provision KeyLocker certificate/keypair | Managed HSM key provisioning | **No** |
| DigiCert | Assign KeyLocker Signer/API/client credentials | Permission/credential mutation | **No** |
| DigiCert | Install Windows SDK/KeyLocker client tools | Local software installation | **No** until provider approval |
| DigiCert | Sign app/Launcher/installer | Real signing | **No** |

## 12. Future Public / Formal Distribution activation work

This section is retained only for a future activation of commercial Authenticode. Commit `50e7074` already provides one dormant SSL.com implementation of `WindowsSigningProvider`; that adapter is not active and does not imply SSL.com remains selected. If public/formal signing is later authorized, implementation must remain narrow and provider-specific:

1. use exactly one approved concrete `WindowsSigningProvider` (reuse the dormant SSL.com adapter only if SSL.com is actually selected; otherwise implement only the selected provider);
2. resolve the selected signer executable/tool from an explicit configured path, not generic PATH discovery;
3. pin/verify the provider client version where practical;
4. keep all credentials out of command-line logs and project files;
5. require a configured public publisher policy derived from the real issued identity before signing;
6. sign app and Launcher;
7. verify each immediately with the repaired provider-neutral inspector;
8. package those exact signed bytes;
9. build/sign/verify the installer;
10. record only public certificate/timestamp evidence;
11. compute package hash after Authenticode signing;
12. create/sign the Ed25519 update manifest only after the signed package bytes are frozen;
13. run exactly one separately authorized signed staging update acceptance.

Do not implement or activate adapters for all three providers. Only the provider selected by a future Public / Formal Distribution authorization may be activated.

## 13. What remains prohibited after this document

While the current Private / Controlled Distribution profile remains active, and until a future Public / Formal Distribution signing gate is separately approved, do not:

- purchase a signing service or certificate;
- submit a certificate application;
- perform identity or organization validation;
- create a paid subscription/payment method;
- provision/import/export a signing key or PFX;
- install provider signing software or Windows SDK solely for real signing;
- create provider credentials or GitHub signing secrets;
- modify staging `windows_publisher_policy` to a real identity;
- perform a real signing operation;
- build/publish a formally signed staging release;
- upload/register/enable a signed staging candidate;
- treat this retained provider research as authorization for B6-G7 or B6-G8; those gates remain independently authorized even though B6-G7 is now the next mandatory Board 6 gate;
- enter Board 7 or mutate production;
- push, merge, or modify tags;
- clean frozen main or Board 5 evidence;
- directly clean the G5 residual device rows in D1.

## 14. Official sources reviewed

Research used provider-owned documentation/product pages only for load-bearing facts.

### Microsoft

- Artifact Signing SKU/pricing: https://learn.microsoft.com/en-us/azure/artifact-signing/how-to-change-sku
- Artifact Signing quickstart / geography / identity validation: https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart
- Artifact Signing FAQ / paid-subscription requirement / certificate custody: https://learn.microsoft.com/en-us/azure/artifact-signing/faq
- Artifact Signing trust models: https://learn.microsoft.com/en-us/azure/artifact-signing/concept-trust-models
- Signing integrations / SignTool / timestamp: https://learn.microsoft.com/en-us/azure/artifact-signing/how-to-signing-integrations
- Artifact Signing roles: https://learn.microsoft.com/en-us/azure/artifact-signing/tutorial-assign-roles
- Signing transaction logs: https://learn.microsoft.com/en-us/azure/trusted-signing/how-to-sign-history
- Windows code-signing options / short-lived certificate behavior: https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options

### SSL.com

- IV Code Signing: https://www.ssl.com/products/software-integrity/code-signing/iv/
- eSigner for Code pricing/integrations: https://www.ssl.com/products/software-integrity/signing-service/
- eSigner CKA CI/CD integration: https://www.ssl.com/how-to/how-to-integrate-esigner-cka-with-ci-cd-tools-for-automated-code-signing/
- eSigner CKA / SignTool automation: https://www.ssl.com/how-to/automate-ev-code-signing-with-signtool-or-certutil-esigner/
- Identity Validation guide: https://www.ssl.com/guide/identity-validation-for-ssl-com-certificates-a-complete-guide/
- Code-signing key export / certificate validity notes: https://www.ssl.com/how-to/getting-started-with-your-code-signing-certificate-installation-configuration-and-your-first-signing-operation/

### DigiCert

- Code Signing + KeyLocker current comparison/pricing: https://www.digicert.com/signing/compare-code-signing-certificates
- KeyLocker licensing: https://docs.digicert.com/en/digicert-keylocker/overview/licensing.html
- Code-signing request/organization validation: https://docs.digicert.com/en/certcentral/order-and-manage-certificates/request-certificates/request-a-code-signing-or-ev-code-signing-certificate/request-code-signing-certificate.html
- KeyLocker Signer role: https://docs.digicert.com/en/digicert-keylocker/overview/users/roles/keylocker-signer.html
- KeyLocker GitHub/KSP examples: https://docs.digicert.com/en/digicert-keylocker/ci-cd-integrations/scripts/github/scripts-for-signing-using-ksp-library-on-github.html
- KeyLocker signature licensing: https://docs.digicert.com/en/digicert-keylocker/overview/licensing.html

## 15. Phase A closure verification

Fresh verification after both provider-neutral implementation commits and provider research:

```text
python -m unittest discover -s tests
=> 630 tests / 2 expected skips / 0 failures

services/license-update-worker: npm run typecheck
=> PASS

services/license-update-worker: npm test -- --run
=> 14 files / 92 tests PASS

Authenticode + WindowsSigningProvider protocol + Launcher process/service/CLI + Windows packaging/installer
=> 103 / 103 PASS

real read-only project inspector against existing Microsoft-signed Windows PowerShell executable
=> Status=Valid with complete public signer evidence and timestamp_status=present
```

The system probe still means only that the provider-neutral verifier works on a real existing Windows signature. It is not project publisher acceptance.

Final diff/sensitive/frozen-boundary checks are part of the local governance commit preflight. The Board 6 `NUL` remains the only allowed worktree residual because its exact safe deletion is blocked by the current DevSpace tool contract.

Phase A is therefore locally complete. Commit `50e7074` later added one dormant optional SSL.com eSigner adapter with no account, credential, key, publisher-policy, or signing side effect; it is retained only as future capability. Scope-amendment implementation `ebd3378` then added the explicit schema-v2 private/public distribution-profile contract while preserving legacy schema-v1 production publisher requirements. Under the approved Private / Controlled Distribution amendment, real commercial signing is deferred and is not a current closure blocker. The next mandatory Board 6 authorization is **B6-G7 Staging Key Rotation Drill Gate**. No commercial or identity side effect is implied by this retained research.
