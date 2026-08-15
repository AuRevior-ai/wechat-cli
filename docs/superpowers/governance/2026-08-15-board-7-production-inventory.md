# Board 7 Production Infrastructure Inventory

Date: 2026-08-15
Gate: B7-G3 Production Infrastructure Provision
Status: PRE-PROVISION PREFLIGHT PASSED; production resource creation not yet recorded in this document

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

## Cloudflare identity/access evidence

Wrangler is authenticated through its existing OAuth session to the same Cloudflare account above. No Cloudflare token value is recorded here.

Read-only Access API evidence:

- account-scoped Access applications endpoint is readable and currently reports zero account-scoped applications;
- zone-scoped Access applications read through the current OAuth session returns authentication error `10000` and therefore is not treated as authoritative staging-app inventory;
- Board 6 retained governance evidence records the accepted staging human Access boundary and exact issuer/JWKS metadata;
- staging D1 contains exactly one Access-mapped `admin_principals` identity, and that identity matches the currently authenticated Cloudflare operator identity;
- the staging principal is revoked as expected from Board 6 cleanup; only the identity mapping is reused as the production human identity reference. No staging session, principal row, credential, token, or Secret is copied into production.

The exact human identity value is intentionally not repeated in this document.

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
