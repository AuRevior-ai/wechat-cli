# WeChat CLI License & Update Worker

Cloudflare Worker service for permanent licenses, device authorization, signed offline leases, private update distribution, administrator operations, and opt-in diagnostics.

## Security model

- Permanent license keys are stored only as peppered HMAC digests.
- Device and administrator tokens use a public identifier plus a separately hashed secret.
- Contact data is encrypted with versioned AES-256-GCM keys. Search fields use separate peppered lookup digests.
- Offline leases are signed with Ed25519 and never exceed seven days.
- Release packages remain in a private GitHub release repository. Worker download tickets are short lived and are sent in an authorization header, never in a URL.
- Diagnostic uploads require a valid device token, a short-lived upload token, an exact size, and an exact SHA-256 digest.
- Administrator mutations require scopes, rate limits, audit events, and idempotency nonces.
- Plaintext license keys are returned only from creation requests. Idempotency records never contain plaintext keys; retry-safe keys are derived from a secret and the operation nonce.

## Local verification

Use Node.js and npm from a disposable development environment:

```powershell
npm install
npm run typecheck
npm test
npx wrangler d1 migrations apply wechat-cli-license-local --local --env=""
npx wrangler deploy --dry-run --outdir .wrangler-dry-run
```

Generate a disposable local bundle outside the repository:

```powershell
wechat-cli-admin bootstrap demo --output-dir C:\secure\wechat-cli-worker-local
```

Copy the generated `.dev.vars` into the disposable Worker checkout, replace the GitHub-token placeholder, apply `bootstrap-admin.sql` once, and import `admin-token.txt` with `wechat-cli-admin config set`. Delete the plaintext token file after DPAPI storage succeeds. Alternatively, copy `.dev.vars.example` and replace every placeholder manually. Do not reuse local values in staging or production.

Run the self-contained disposable local end-to-end environment:

```powershell
python scripts/run_local_e2e.py
```

The runner copies the Worker into a temporary directory, installs dependencies there, generates disposable secrets and an Ed25519 lease key, applies D1 migrations, seeds a temporary administrator, starts local Wrangler with D1 and R2, and removes the temporary environment afterward. It exercises license creation, the three-device limit, validation and offline leases, rename and immediate unbind/rebind, release registration and enablement, update tickets, pause behavior, failed-version suppression, diagnostic upload/list/delete, suspension, resume, and revocation. It also checks the Worker log for leaked disposable credentials. It never prints the license key, device token, administrator token, or generated secrets.

## Cloudflare resources

Create separate staging and production resources:

- One D1 database per environment.
- One private R2 diagnostics bucket per environment.
- One Worker per environment.
- A custom API hostname after DNS and any required mainland-China compliance work are complete.

Replace the placeholder database IDs in `wrangler.jsonc`. Set Worker secrets with Wrangler rather than writing them into the config file:

```powershell
npx wrangler secret put LICENSE_KEY_PEPPER --env staging
npx wrangler secret put DEVICE_TOKEN_PEPPER --env staging
npx wrangler secret put ADMIN_TOKEN_PEPPER --env staging
npx wrangler secret put CONTACT_LOOKUP_PEPPER --env staging
npx wrangler secret put CONTACT_ENCRYPTION_KEY_V1 --env staging
npx wrangler secret put LEASE_SIGNING_PRIVATE_KEY --env staging
npx wrangler secret put DOWNLOAD_TICKET_SECRET --env staging
npx wrangler secret put GITHUB_RELEASE_READ_TOKEN --env staging
```

Apply migrations before deployment:

```powershell
npx wrangler d1 migrations apply wechat-cli-license-staging --remote --env staging
npx wrangler deploy --env staging
```

Repeat with production only after staging acceptance.

## Initial administrator token

The first administrator token is provisioned out of band:

1. Generate a high-entropy token in the form `wcadmin_adm_<id>.<secret>`.
2. Compute `HMAC-SHA256(ADMIN_TOKEN_PEPPER, secret)`.
3. Insert only the token ID, digest, and scopes into `admin_tokens`.
4. Store the plaintext token with `wechat-cli-admin config set`, which protects it with current-user Windows DPAPI.
5. Delete any temporary plaintext copy.

The Demo may use a long-lived token with `"*"` scope. Formal production should replace this with short-lived administrator sessions and narrower scopes.

## Release registration

`wechat-cli-release publish` performs these steps:

1. Validate the application ZIP and embedded `app-manifest.json`.
2. Build deterministic update-manifest bytes.
3. Sign the exact bytes with a local Ed25519 private key.
4. Create a private draft GitHub Release.
5. Upload the package, manifest, and signature.
6. Register the GitHub asset IDs and signed bytes with the Worker as disabled and paused.
7. Enable the release only when explicitly requested.

The Worker never receives the release signing private key.

## Contact-key rotation

Add the next secret, for example `CONTACT_ENCRYPTION_KEY_V2`, update `CONTACT_ENCRYPTION_KEY_VERSION`, deploy, and then run bounded batches:

```powershell
wechat-cli-admin contacts rotate --limit 50
wechat-cli-admin contacts status
```

Keep old keys configured until the status reports zero records on older versions.

## Scheduled cleanup

The scheduled handler removes expired rate-limit windows, idempotency records, download tickets, and diagnostic objects. Configure the Worker cron before production deployment and verify it in staging.
