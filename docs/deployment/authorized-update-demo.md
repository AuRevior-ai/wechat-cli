# WeChat CLI Web Authorized Update Demo Runbook

This runbook covers the Demo deployment of permanent licenses, three-device authorization, signed seven-day offline leases, private updates, rollback, and opt-in diagnostics.

## 1. Components

The Demo uses five independent trust domains:

1. **Windows Launcher** — validates authorization, installs a pending version, starts the app, checks health, and rolls back.
2. **WeChat CLI Web app** — validates a one-time Launcher session, exposes local management pages, and performs background update downloads.
3. **Cloudflare Worker** — license/device API, update selection, private asset proxy, administrator API, and diagnostic upload sessions.
4. **D1 and R2** — license state and audit metadata in D1; explicitly submitted diagnostic ZIPs in private R2.
5. **Private GitHub release repository** — application ZIP, signed manifest, and signature.

The source repository and release repository remain separate. The release-signing private key remains local for the Demo.

## 2. Local acceptance before cloud work

Run the Python suite:

```powershell
python -m unittest discover -s tests
```

Run Worker checks:

```powershell
cd services/license-update-worker
npm install
npm run typecheck
npm test
npx wrangler d1 migrations apply wechat-cli-license-local --local --env=""
npx wrangler deploy --dry-run --outdir .wrangler-dry-run
```

Run the disposable Worker/D1/R2 E2E in one command:

```powershell
python scripts/run_local_e2e.py
```

The runner generates temporary secrets and keys outside the repository, seeds a disposable administrator, verifies license/device/update/diagnostic/revocation flows, scans the Worker log for leaked credentials, and removes the temporary environment.

Build Windows binaries and packages from an isolated build environment:

```powershell
python npm/scripts/build.py win32-x64
python scripts/package_windows_app.py `
  --skip-build `
  --launcher-config C:\secure\launcher-config.staging.json
```

Expected outputs:

- `npm/platforms/win32-x64/bin/wechat-cli.exe`
- `npm/platforms/win32-x64/bin/wechat-cli-launcher.exe`
- `dist/wechat-cli-web-bootstrap-win32-x64-<version>.zip`
- `dist/wechat-cli-app-<version>-win-x64.zip`

Verify the final bytes, signed-manifest trust chain, safe extraction, legacy migration, repeated installation, and uninstall:

```powershell
python scripts/verify_local_update_artifacts.py
python scripts/verify_windows_bootstrap.py
```

## 3. Create cloud staging

Create a staging D1 database, staging R2 bucket, and staging Worker. Replace the staging IDs in `wrangler.jsonc`; do not reuse production names or secrets.

Apply all D1 migrations:

```powershell
cd services/license-update-worker
npx wrangler d1 migrations apply wechat-cli-license-staging --remote --env staging
```

Set every staging secret with Wrangler. Never put plaintext secrets, GitHub tokens, or private keys into `wrangler.jsonc`, Git, issue trackers, or chat logs.

Deploy staging:

```powershell
npx wrangler deploy --env staging
```

Verify:

- `GET /v1/health` returns the staging environment.
- Missing routes return a stable JSON error and request ID.
- D1 tables and migrations are present.
- The scheduled cleanup trigger appears in the Worker configuration.
- The R2 diagnostics bucket is private.

## 4. Create the private release repository

Create a separate private GitHub repository dedicated to binary releases. The Worker token needs read access only to that release repository. The local publishing token needs the minimum permissions required to create and delete releases and assets.

Configure administrator and release tools on the sole administrator's Windows account:

```powershell
wechat-cli-admin config set --api-url https://staging-api.example.com
wechat-cli-release config set `
  --repository owner/private-release-repo `
  --target-commitish main `
  --signing-key C:\secure\release-signing-key.pem `
  --signing-key-id release-key-staging-01
```

Both tools protect their tokens with current-user DPAPI. The release private key remains a separate local file and is never uploaded to the Worker.

## 5. Build and publish the first staging update

Prepare the signed files without publishing:

```powershell
wechat-cli-release prepare `
  dist\wechat-cli-app-0.5.0-win-x64.zip `
  --release-id rel_staging_050 `
  --published-at 2026-08-05T00:00:00Z `
  --minimum-app-version 0.4.2 `
  --minimum-launcher-version 0.1.0 `
  --summary "Authorized update staging" `
  --output-dir C:\secure\prepared-release
```

Publish as a private GitHub draft and register it disabled/paused:

```powershell
wechat-cli-release publish `
  dist\wechat-cli-app-0.5.0-win-x64.zip `
  --release-id rel_staging_050 `
  --published-at 2026-08-05T00:00:00Z `
  --minimum-app-version 0.4.2 `
  --minimum-launcher-version 0.1.0 `
  --summary "Authorized update staging"
```

Inspect the private draft and Worker record, then explicitly enable it:

```powershell
wechat-cli-admin releases list
wechat-cli-admin releases enable rel_staging_050
```

A failed enable operation preserves the already registered private draft and assets, leaving a recoverable disabled/paused release rather than deleting data referenced by the Worker.

## 6. Create licenses

Create one license:

```powershell
wechat-cli-admin licenses create `
  --maximum-devices 3 `
  --email customer@example.com
```

Create a batch and write plaintext keys once to a new CSV:

```powershell
wechat-cli-admin licenses batch-create `
  --count 20 `
  --maximum-devices 3 `
  --output C:\secure\licenses-2026-08.csv
```

The CSV command refuses to overwrite an existing file. Move the file into the intended secure delivery workflow and delete temporary copies.

## 7. Install the bootstrap

Existing 0.4.2 users perform one manual bootstrap installation. The installer:

- detects or installs the Microsoft Evergreen WebView2 Runtime;
- installs Launcher and version `0.5.0` into versioned directories;
- writes `state/current.json` atomically;
- preserves the old `app` directory;
- preserves `~/.wechat-cli` user data;
- creates shortcuts pointing to the Launcher.

Run `install-and-start.bat`. The first Launcher window requests the permanent license key and stores the license key, device token, lease, and local launch key with current-user DPAPI.

## 8. End-to-end staging acceptance

Use at least two versions, for example 0.5.0 and 0.5.1.

### License and device

- Activate the first device.
- Verify routine startup sends only the device token, not the permanent key.
- Bind two more devices and confirm the fourth is rejected.
- Rename a device from the Web page.
- Unbind a non-current device and immediately reactivate another device.
- Suspend and revoke licenses from the administrator CLI and verify the next online validation blocks immediately.

### Offline lease

- Validate online, disconnect the network, and start successfully within seven days.
- Verify the Web page shows the remaining offline period.
- Verify startup is blocked after expiry.
- Move the system clock significantly behind the last trusted time and verify offline authorization is denied.

### Update

- Publish and enable 0.5.1.
- Start 0.5.0; verify one startup update check.
- Verify download occurs without interrupting the current session.
- Restart; verify Launcher installs 0.5.1 and `/api/health` reports the exact expected version.
- Publish a deliberately unhealthy candidate in staging; verify Launcher restores 0.5.0 and marks the failed version so it is not retried automatically.
- Pause a release and verify new clients no longer receive it.

### Diagnostics

- Generate a local diagnostic ZIP and inspect its `contents.txt`, metadata, and redacted logs.
- Confirm no chat database, full license key, token, email, MachineGuid, SID, or user path appears.
- Explicitly confirm upload in a second UI action.
- List, download, and delete the diagnostic with the administrator CLI.
- Verify expiration cleanup removes old R2 objects and D1 records.

## 9. Production gate

Do not promote staging automatically. Production requires:

- a code-signing certificate for Launcher, app, and installer;
- production-specific D1, R2, Worker, GitHub tokens, peppers, AES keys, and Ed25519 keys;
- tested backup and contact-key rotation procedures;
- a stable custom hostname and completed DNS/compliance work;
- a short-lived administrator authentication design replacing the Demo long-lived token;
- a real private GitHub Release E2E using production-like permissions;
- an independent review of logs, diagnostics, revocation, and rollback behavior.

The Demo implementation reserves forced updates, beta channel, phased rollout, pause, and Launcher-version compatibility fields but does not enable forced updates by default.
