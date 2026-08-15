# Board 7 Production Infrastructure Inventory

Date: 2026-08-15
Gate: B7-G3 Production Infrastructure Provision
Status: B7-G3 PARTIALLY PROVISIONED; clean-room D1/R2 complete, Access application creation blocked by current OAuth write permission

## Canonical source boundary

The exact canonical remote source commit entering B7-G3 is:

`fd29a2a7b00ded303c9c6ee8bdab8b1f2bbccc75`

This is the history-preserving merge commit for Strong Authorization PR #3. Canonical-main CI for this exact SHA passed after the earlier whitespace-repair PR #2 had already merged.

Historical boundaries remain distinct:

- historical frozen pre-integration main baseline: `a579a25cb7f16e6fdf88d618252b4a5cbffef53d`;
- retained local main checkout: `D:\use_as_desktop\Wechat__CLI\wechat-cli`, still physically at the historical frozen SHA with its pre-existing untracked `NUL`;
- current canonical remote main: `fd29a2a7b00ded303c9c6ee8bdab8b1f2bbccc75`.

The retained local checkout is not a production source authority and is not modified by this gate.

## Approved production naming matrix

Cloudflare account ID:

`2040a134dbf533fd538deae668556226`

Cloudflare zone:

- zone: `aurevior-devspace.com`
- zone ID: `0ab034c12754086ffdda8d27fc551d65`
- status at preflight: active

Production targets:

- Worker: `wechat-cli-license-update`
- D1: `wechat-cli-license-production`
- R2 releases: `wechat-cli-releases-production`
- R2 diagnostics: `wechat-cli-diagnostics-production`
- API hostname: `wechat-cli-api.aurevior-devspace.com`
- Admin hostname: `wechat-cli-admin.aurevior-devspace.com`
- human Access app: `wechat-cli-production-human-admin`
- automation Access app: `wechat-cli-production-release-automation`
- automation Service Token name reserved for B7-G4: `wechat-cli-release-automation-production`

## Read-only collision evidence

Fresh Wrangler readback before any B7-G3 production creation showed:

- D1 list contains only `wechat-cli-license-staging`; no `wechat-cli-license-production` exists;
- R2 list contains only `wechat-cli-diagnostics-staging` and `wechat-cli-releases-staging`; neither production bucket exists;
- production Worker deployment probe returned Cloudflare error code `10007`, meaning `wechat-cli-license-update` does not exist in this account;
- authoritative HTTPS DNS-over-HTTPS lookup returned NXDOMAIN for both exact production hostnames;
- the existing staging admin hostname resolves normally through Cloudflare, confirming the DNS lookup path itself is valid.

No exact target-name collision was found.

## Clean-room storage provisioning evidence

The Strong Authorization envelope then created only the approved clean-room storage resources:

- production D1 `wechat-cli-license-production` -> ID `011b3c26-bbe6-4bb7-8af7-39f1e6d46932`;
- production R2 releases bucket `wechat-cli-releases-production`;
- production R2 diagnostics bucket `wechat-cli-diagnostics-production`.

Fresh post-create list readback showed the production objects alongside, and distinct from, the retained staging D1/R2 objects. No existing object was adopted, overwritten, or deleted.

Production D1 migrations `0001_initial.sql` through `0008_automation_identity.sql` were applied in repository order. A fresh migration-list readback returned `No migrations to apply`.

Fresh remote scalar-count queries proved all production business, authorization, release, diagnostics, audit, idempotency, and rate-limit tables are empty. Representative counts include `licenses=0`, `devices=0`, `releases=0`, `diagnostic_submissions=0`, `admin_principals=0`, `admin_sessions=0`, `automation_principals=0`, and `audit_events=0`; both count queries reported `rows_written=0`. No staging import/export-to-production operation occurred.

## Cloudflare identity/access evidence

Wrangler is authenticated through its existing OAuth session to the same Cloudflare account above. No Cloudflare token value is recorded here.

Read-only Access API evidence:

- account-scoped Access applications endpoint is readable and currently reports zero account-scoped applications;
- zone-scoped Access applications read through the current OAuth session returns authentication error `10000` and therefore is not treated as authoritative staging-app inventory;
- Board 6 retained governance evidence records the accepted staging human Access boundary and exact issuer/JWKS metadata;
- staging D1 contains exactly one Access-mapped `admin_principals` identity, and that identity matches the currently authenticated Cloudflare operator identity;
- the staging principal is revoked as expected from Board 6 cleanup; only the identity mapping is reused as the production human identity reference. No staging session, principal row, credential, token, or Secret is copied into production.

The exact human identity value is intentionally not repeated in this document.

Fresh public JWKS readback at `https://floral-glitter-1ede.cloudflareaccess.com/cdn-cgi/access/certs` returned HTTP 200 with two keys, so the retained team issuer/JWKS identity is still live. The production source configuration now safely fixes the exact API/Admin origins, this issuer/JWKS pair, and the new production D1 ID. Human/automation Access audience fields intentionally remain fail-closed placeholders until their exact applications exist.

An attempted create of the first production Access application through the existing Wrangler OAuth authority was rejected by Cloudflare with HTTP 403 / Access API code `1010`. No Access application or policy was created by that failed request. Current Wrangler OAuth remains sufficient for Workers/D1/R2 operations but does not provide the required Access application/policy write authority. This is the only unresolved B7-G3 infrastructure authority blocker at this checkpoint.

## G3/G4 automation-identity sequencing clarification

The approved design states that the exact external automation identity stored in `ACCESS_AUTOMATION_IDENTITIES` is the Cloudflare Access Service Token client identity and does not exist until B7-G4 creates that token. Therefore G3 must not invent or predeclare a fake client identity merely to make the full production preflight pass.

The safe sequencing is:

1. B7-G3 creates the human Access application plus its single-email Allow policy.
2. B7-G3 creates the distinct automation Access application and records its distinct audience, but attaches no machine Allow/Service Auth policy yet. Cloudflare Access applications are deny-by-default, so this application remains closed.
3. B7-G3 source configuration may replace the human/automation audience placeholders with the exact created audiences while leaving only `ACCESS_AUTOMATION_IDENTITIES` unresolved.
4. B7-G4 creates the exact `wechat-cli-release-automation-production` Service Token. Its safe `client_id` becomes `ACCESS_AUTOMATION_IDENTITIES`, and the secret is retained only in the approved secret domain.
5. B7-G4 then attaches an exact Service Auth policy referencing only that token and runs the first fully passing production preflight before B7-G5 deployment.

This interpretation preserves the higher-priority design invariant that machine identity is exact and separately provisioned. It does not use Cloudflare's broader `any valid service token` selector and does not weaken fail-closed behavior. The implementation-plan sentence requiring a fully passing production preflight during G3 is therefore interpreted as a staging/config validation checkpoint; full identity-complete production preflight occurs in G4 after the designed client identity exists.

A bounded helper `scripts/board7_access_bootstrap.py` is prepared under TDD for the G3 control-plane write. Its G3 mode can create only the two exact applications and the one human policy; it has no G3 service-token or automation-policy write path and never prints the API token or human email.

## Access application creation readback

The human operator completed the two exact Cloudflare Access application creations through the Zero Trust dashboard after the existing Wrangler OAuth proved read-only for Access writes.

Observed safe state:

- human application `wechat-cli-production-human-admin` exists on `wechat-cli-admin.aurevior-devspace.com/v1/admin/*`;
- human policy `wechat-cli-production-human-admin-allow` is attached;
- human Access audience is `1d08e2b8812cea900d34b49b2468aecd7b7f7b3d5bfb181bd83ea51b5b8f230c`;
- automation application `wechat-cli-production-release-automation` exists on `wechat-cli-admin.aurevior-devspace.com/v1/automation/*`;
- the automation application has no policy in G3 and is therefore intentionally deny-by-default;
- automation Access audience is `d7289641a209be81948f80e4b8a255bc5948b3e90c7318a1e7cd12c279c4e47b`;
- the two audiences are distinct;
- no Service Token exists yet; `ACCESS_AUTOMATION_IDENTITIES` therefore remains an explicit G4 placeholder.

Both safe audience values are now bound into production source configuration. Full production deployment preflight must continue to fail closed until B7-G4 creates the exact automation Service Token identity.

## Isolation requirements for the next mutations

B7-G3 may now create only the approved D1/R2 resources and the exact Access application/policy identities. It must not:

- import staging D1 data;
- create production Worker application code or deploy a placeholder Worker;
- create production runtime Secrets or private keys;
- create human/machine principal rows;
- create the Access Service Token credential;
- create licenses or releases;
- activate Public / Formal Distribution or commercial Authenticode.

If any target resource appears unexpectedly before its creation step, requires paid-plan/ownership changes, or cannot be configured without weakening the approved Access or Host/Path boundaries, execution hard-stops under the Strong Authorization amendment.
