# Changelog

This changelog is reconstructed from repository commits, design documents, implementation plans, and local acceptance reports. It records product changes, not the current execution state. Read [docs/PROJECT_STATE.md](docs/PROJECT_STATE.md) for current status.

## 0.5.1 — 2026-08-08

Local staging update-chain validation only; this version is not recorded as published or hosted.

### Changed

- Bumped the application version to 0.5.1 while keeping Launcher at 0.1.0.
- Added an app-only Windows build target and update-only packaging path so staging can validate a real 0.5.0 → 0.5.1 application update without rebuilding Launcher or producing a bootstrap.
- Fixed the default build identifier at `staging-051-20260808.1` while preserving explicit `WECHAT_CLI_BUILD_ID` overrides.
- No business-facing application feature changed in 0.5.1.

## 0.5.0 — 2026-08-05

Primary implementation commits: `036cec5`, `0802e55`, `370a9d9`, `ef9e0e9`, and `e36ab47`.

### Added

- Permanent licenses with a three-device limit and signed seven-day offline leases.
- Windows WebView2 Launcher, one-time launch sessions, current-user DPAPI storage, and single-instance handling.
- Ed25519-signed update manifests, resumable downloads, safe ZIP extraction, versioned installs, health checks, failed-version suppression, and automatic rollback.
- Administrator and release CLIs.
- Cloudflare Worker, D1 migrations, R2 diagnostic storage, audit, rate limits, idempotency, and cleanup scheduling.
- Windows bootstrap, 0.4.2 migration, repair, uninstall, and a separate application-update ZIP.

### Changed

- Centralized product and version metadata at application 0.5.0 and Launcher 0.1.0.
- Added staging Cloudflare resource configuration and private-release workflow documentation.
- Added a Windows packaging dependency preflight so missing Launcher dependencies fail before existing executables are replaced.

### Known delivery limits

- Windows binaries are not code-signed.
- The repository’s existing bootstrap archive is Demo-configured, not a staging installer.
- Production resources and automated publishing are not complete.

See the [0.5.0 local finalization report](docs/deployment/2026-08-05-local-finalization-report.md) and [authorized update roadmap](docs/deployment/authorized-update-roadmap.md).

## 0.4.x — 2026-07-29 to 2026-08-04

This grouped history is reconstructed from the available commits and documents; later changes are not assigned undocumented exact patch numbers.

### Added

- AI-ready chat archives with recursive merged-forward parsing (`1f05b8b`, `f7dcdca`).
- WeChat 4.1 voice decoding and verified offline transcription (`39f9cb9`, `df0bee7`, `b376f86`).
- Exact same-second image matching and per-session image-key handling (`d789d21`, `853867a`).
- CLI and Web AI material-package flows (`d2516b8`, `691d19d`, `325c2be`).
- Local author assets and an About & Support page (`0722d49`, `09b7152`, `9af3767`).

### Fixed

- Batch and self-QR invitation parsing and local-account attribution (`8431984`, `8d46801`).
- Release preparation and documentation for the invitation-statistics compatibility fixes (`2bce874`, `6b93b9b`).

## 0.3.x — 2026-07-29

### Added

- Reusable session and date pickers across Web tools (`6344502`, `9212262`).
- Real-avatar display through a local proxy and an invitation-group picker (`7f57776`).
- Simplified Web navigation and a unified chat-record workflow (`6583db7`).

### Fixed

- Stale picker-request handling and preservation of the selected session when Escape closes the picker (`c59f775`, `6ba081c`).

## 0.2.6–0.2.7 — 2026-07-28 to 2026-07-29

### Added

- Auditable group invitation statistics in the CLI and Web console, with exact identity resolution and text/CSV output (`019eed8`).
- Per-feature Web result isolation, Chinese field presentation, and a chat-summary workflow (`d4da7d3`).

### Changed

- Hardened chat-summary performance and privacy behavior (`877af46`).
- Prepared the Web usability release documentation (`4cec836`).

## 0.2.5 baseline — 2026-07-28

Commit `02404d2` established the verified baseline used for the invitation-statistics and subsequent feature work.
