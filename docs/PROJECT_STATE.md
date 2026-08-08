# WeChat CLI Current Project State

Updated: 2026-08-08 +08:00

## Repository-verifiable baseline

- Product: `wechat-cli-web`
- Application version: `0.5.0`
- Launcher version: `0.1.0`
- Source repository: `AuRevior-ai/wechat-cli`
- Functional-code baseline: `cc540dd` (`5d65a9c` license transport User-Agent fix; `cc540dd` staging acceptance tools/tests)
- External-memory governance design: `5310630`
- Current branch: `main`

## Current program position

The authorized-update program is on board 4, “first test license and test release.” Tasks 1, 2, 3, and 4 are complete.

Task 3 real staging license/device acceptance succeeded on 2026-08-08. Task 4 is complete: the fresh real staging lease verified under `lease-key-staging-01` with an exact 604800-second duration; valid/expiring/expired and significant-clock-rollback behavior matched policy; and the authorized single-process status sequence `active → suspended → online LICENSE_SUSPENDED → active → revalidate` succeeded against staging. A fresh 2026-08-08 read-only D1 check reconfirmed the license at `active`, revision 3, `suspended_at=NULL`, `revoked_at=NULL`, with 4 historical devices (3 active, 1 unbound) and device 1 still active after post-restore validation. Revocation remains deliberately deferred so the staging license stays usable for later board work. Task 5 design is now approved and documented in `docs/superpowers/plans/2026-08-08-board-4-task-5-051-update.md`; no Task 5 version/build/packaging implementation is permitted in the main checkout. The next implementation step is to create an isolated DevSpace worktree from the frozen latest `main` HEAD.

## Evidence boundary

### Verifiable from this repository

- The 0.5.0 license, launcher, update, release, admin, Worker, and Windows packaging implementations exist.
- The local 0.5.0 update ZIP is `14291197` bytes with SHA-256 `406b72c14ad186141f373087595f7723e143b9638bf298fde23b6bb0ae057523`.
- The current bootstrap archive still contains the Demo API URL and Demo signing-key identifiers and is not a staging installer.
- `wrangler.jsonc` contains the recorded staging Worker, D1, R2, and cron configuration.

### Last manually recorded outside the repository

As recorded in the authorized-update roadmap, the two private repositories and Cloudflare staging resources had been created, and `rel_staging_050` had been uploaded, registered, and enabled. On 2026-08-08 a live D1 read confirmed one active staging test license: ID `lic_ptrqZVAxh2NI8h5RM6gnGiiL`, hint `JD25`, `stable`, maximum 3 devices, created at `2026-08-08T09:07:57.146Z`. Task 3 then completed against the real staging API: the fourth device was rejected with `DEVICE_LIMIT_REACHED`, rename and unbind/rebind succeeded, and a live D1 read confirmed 4 historical device rows with 3 active and 1 unbound. The complete license key and all device tokens remain outside the repository and are not recorded here. These are historical acceptance records, not a substitute for future live checks.

## Last local verification

- Python full suite: 476 tests run; 474 passed and 2 skipped.
- Worker: `npm run typecheck` passed; Vitest: 3 files passed, 17 tests passed.
- `git diff --check` passed for the Task 3/4 freeze set (line-ending conversion warnings only).
- Sensitive-value scan across the Task 3/4 implementation/tests/docs and Task 5 plan found zero matches for complete license, device-token, admin-token, GitHub-token, or private-key shapes.
- Release repository working tree was clean.
- Fresh read-only D1 verification matched the recorded Task 4 final state and wrote 0 rows.
- Verification date: 2026-08-08.

## Known constraints

- `0.5.1` has not been built or released.
- Task 4 real staging lease, clock-boundary, and suspend/reject/restore behavior are accepted. Revocation remains deferred to avoid destroying the test license before later board work.
- Task 5 design is approved: 0.5.1 is update-link validation only; Launcher stays 0.1.0; use app-only build plus update-only packaging; no staging bootstrap; no 0.5.1 release/upload/registration/enablement in Task 5; build ID default is `staging-051-20260808.1` with explicit environment override retained. Implementation must occur in an isolated worktree from the frozen main baseline.
- The main checkout currently contains an intentionally preserved untracked `NUL` entry; it must not be committed or deleted without separate explicit approval.
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
