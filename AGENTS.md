# WeChat CLI Repository Instructions

## Required reading order

1. Read `docs/PROJECT_STATE.md` before project work.
2. For licensing, updates, Cloudflare, GitHub Releases, Windows installation, deployment, or production work, read `docs/deployment/authorized-update-roadmap.md` next.
3. Read the current plan named by the roadmap before implementing that work.
4. Treat `docs/superpowers/specs/` as approved design history, `docs/superpowers/plans/` as construction plans, and `docs/deployment/*report.md` as dated acceptance snapshots.

## State and evidence rules

- `docs/PROJECT_STATE.md` is the repository-wide current-state summary.
- The authorized-update roadmap is the source of truth for its fixed seven-board program.
- Do not infer live cloud, license, device, D1, R2, Secret, or GitHub Release state from repository files alone.
- Preserve unrelated and uncommitted user work.
- Never record tokens, private keys, complete license keys, device tokens, cookies, or `.env` content.
- Obtain explicit authorization before cloud mutations, releases, publishing, installation, deletion, Git push, tag creation, or other external side effects.
