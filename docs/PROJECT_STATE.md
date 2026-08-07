# WeChat CLI Current Project State

Updated: 2026-08-07 +08:00

## Repository-verifiable baseline

- Product: `wechat-cli-web`
- Application version: `0.5.0`
- Launcher version: `0.1.0`
- Source repository: `AuRevior-ai/wechat-cli`
- Functional-code baseline: `e36ab47`
- External-memory governance design: `5310630`
- Current branch: `main`

## Current program position

The authorized-update program is on board 4, “first test license and test release.” The roadmap last recorded Task 1 as complete and Task 2 as authorized but not yet recorded complete.

The only repository-supported next step is to finish or truthfully update board 4 Task 2 before starting device acceptance, 0.5.1 work, staging bootstrap work, or Windows end-to-end acceptance.

## Evidence boundary

### Verifiable from this repository

- The 0.5.0 license, launcher, update, release, admin, Worker, and Windows packaging implementations exist.
- The local 0.5.0 update ZIP is `14291197` bytes with SHA-256 `406b72c14ad186141f373087595f7723e143b9638bf298fde23b6bb0ae057523`.
- The current bootstrap archive still contains the Demo API URL and Demo signing-key identifiers and is not a staging installer.
- `wrangler.jsonc` contains the recorded staging Worker, D1, R2, and cron configuration.

### Last manually recorded outside the repository

As recorded in the authorized-update roadmap on 2026-08-05, the two private repositories and Cloudflare staging resources had been created, and `rel_staging_050` had been uploaded, registered, and enabled. These are historical acceptance records, not a live cloud check.

## Last local verification

- Python: 465 tests collected and run; 463 passed and 2 skipped.
- Worker: TypeScript typecheck passed; 17 Vitest tests passed.
- Verification date: 2026-08-07.

## Known constraints

- `0.5.1` has not been built or released.
- The existing 0.5.0 bootstrap is Demo-configured and must not be used for staging acceptance.
- Windows executables are not code-signed.
- Production D1 configuration still contains a replacement placeholder.
- npm package metadata remains at `0.2.4`; the Python/Windows main line is `0.5.0`.

## Authoritative links

- [Authorized update roadmap](deployment/authorized-update-roadmap.md)
- [Current board 4 plan](superpowers/plans/2026-08-05-board-4-test-license-and-release.md)
- [External-memory governance design](superpowers/specs/2026-08-07-external-memory-governance-design.md)
- [0.5.0 local finalization report](deployment/2026-08-05-local-finalization-report.md)
- [Changelog](../CHANGELOG.md)
