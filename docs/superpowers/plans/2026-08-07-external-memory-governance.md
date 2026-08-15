# WeChat CLI External Memory Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a durable project-memory hierarchy, synchronize public documentation with the current 0.5.0 codebase, and clearly separate current state from historical plans and reports without changing business code or cloud resources.

**Architecture:** Add a stable repository entry point (`AGENTS.md`), a current-state summary (`docs/PROJECT_STATE.md`), and a version-oriented `CHANGELOG.md`; keep the seven-board authorized-update roadmap as the specialist source of truth. Update README files and historical documents with explicit status boundaries, preserving the approved board-4 state and all original implementation history.

**Tech Stack:** Markdown, Git, Python 3.10+, Click CLI help, unittest, TypeScript, npm, Vitest, ripgrep, Git Bash.

---

## File Map

- Create: `AGENTS.md` — stable repository entry rules and document-reading order.
- Create: `docs/PROJECT_STATE.md` — concise current-state summary and fact/evidence boundaries.
- Create: `CHANGELOG.md` — version-oriented product and architecture history.
- Modify: `docs/deployment/authorized-update-roadmap.md` — add project-state linkage and evidence wording while preserving board statuses.
- Modify: `docs/superpowers/plans/2026-08-05-board-4-test-license-and-release.md` — add project-state linkage while preserving every current checkbox and authorization gate.
- Modify: `docs/deployment/2026-08-05-local-finalization-report.md` — mark as a dated snapshot and correct the Python test count.
- Modify: nine completed plans under `docs/superpowers/plans/` — add historical-plan notices and verified final-result summaries.
- Modify: `README.md` — synchronize repository, channels, commands, platform support, and development links.
- Modify: `README_CN.md` — mirror the English README facts in Chinese.
- Reference only: `docs/superpowers/specs/2026-08-07-external-memory-governance-design.md`.
- Reference only: `pyproject.toml`, `wechat_cli/version.py`, `npm/wechat-cli/package.json`, `wechat_cli/main.py`, `services/license-update-worker/wrangler.jsonc`.

## Guardrails

- Preserve the two existing untracked documents and edit them in place; do not replace their board-4 facts with assumptions.
- Do not modify Python, TypeScript, JavaScript, PowerShell, package metadata, build output, Cloudflare resources, GitHub Releases, tags, or remote branches.
- Do not display or record tokens, private keys, complete license keys, device tokens, `.env` content, or repository-external secure-directory contents.
- Describe unverified cloud state as “last recorded on 2026-08-05” rather than as a live fact.
- Keep `0.5.1` explicitly unreleased and unbuilt.
- Before every commit, run `git diff --check` and inspect the staged file list.

### Task 1: Establish the repository memory entry point

**Files:**
- Create: `AGENTS.md`
- Create: `docs/PROJECT_STATE.md`
- Reference: `wechat_cli/version.py:12-18`
- Reference: `docs/deployment/authorized-update-roadmap.md:1-250`
- Reference: `docs/superpowers/plans/2026-08-05-board-4-test-license-and-release.md:1-210`

- [ ] **Step 1: Reconfirm the protected baseline**

Run:

```bash
git status --short
git rev-parse --short HEAD
```

Expected:

```text
?? docs/deployment/authorized-update-roadmap.md
?? docs/superpowers/plans/2026-08-05-board-4-test-license-and-release.md
5310630
```

If any implementation file is modified, stop this task and inspect that change before continuing.

- [ ] **Step 2: Create the stable `AGENTS.md` entry rules**

Create `AGENTS.md` with this structure and wording:

```markdown
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
```

- [ ] **Step 3: Create `docs/PROJECT_STATE.md` as a current-state summary**

Create the file with these exact sections:

```markdown
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
```

Do not add a complete license, token, cloud secret, private key, or repository-external path.

- [ ] **Step 4: Verify the entry chain and fixed facts**

Run:

```bash
rg -n 'docs/PROJECT_STATE.md|authorized-update-roadmap.md' AGENTS.md
rg -n 'Application version: `0.5.0`|Launcher version: `0.1.0`|Task 2' docs/PROJECT_STATE.md
rg -n 'APP_VERSION = "0.5.0"|LAUNCHER_VERSION = "0.1.0"' wechat_cli/version.py
```

Expected:

- `AGENTS.md` points to both current-state and specialist-roadmap files.
- `PROJECT_STATE.md` records 0.5.0, 0.1.0, and board 4 Task 2 without claiming completion.
- Runtime version constants match the state document.

- [ ] **Step 5: Check and commit the entry layer**

Run:

```bash
git diff --check
git diff -- AGENTS.md docs/PROJECT_STATE.md
git add AGENTS.md docs/PROJECT_STATE.md
git diff --cached --name-only
git commit -m "docs: add project memory entry points"
```

Expected staged files:

```text
AGENTS.md
docs/PROJECT_STATE.md
```

### Task 2: Bring the authorized-update current state under Git control

**Files:**
- Modify: `docs/deployment/authorized-update-roadmap.md:1-250`
- Modify: `docs/superpowers/plans/2026-08-05-board-4-test-license-and-release.md:1-210`
- Reference: `docs/PROJECT_STATE.md`

- [ ] **Step 1: Preserve the current board status before editing**

Run:

```bash
rg -n '实施状态|板块 4|Task 2|尚未完成|当前执行点|当前唯一允许推进' docs/deployment/authorized-update-roadmap.md
rg -n '计划状态|Task 2|\[ \]|\[x\]|当前执行点' docs/superpowers/plans/2026-08-05-board-4-test-license-and-release.md
```

Expected:

- Board 4 remains in progress.
- Task 1 remains complete.
- Task 2 authorization is recorded, but its file/ACL/scan completion boxes remain unchecked.
- Tasks 3 through 7 remain incomplete.

- [ ] **Step 2: Add the repository-wide state link to the roadmap**

Immediately after the title and before the existing update timestamp, add:

```markdown
> Repository-wide current-state summary: [`docs/PROJECT_STATE.md`](../PROJECT_STATE.md). This roadmap remains authoritative for the fixed seven-board licensing, update, release, and deployment program.
```

In section `## 1. 使用规则`, add a rule after the first item:

```markdown
2. 先读取 `docs/PROJECT_STATE.md` 获取仓库级当前状态；本文件只负责授权更新专项的七板块状态和外部副作用门槛。
```

Renumber the remaining rules without changing their meaning.

At the beginning of `## 6. 板块 4：首次测试许可证与测试发布`, add:

```markdown
> 状态证据说明：仓库内配置、代码、提交和本地产物可直接复验；Worker、D1、Secret、GitHub Release、许可证和设备状态若未重新联网核验，均表示 2026-08-05 路线图记录的最后人工验收状态。
```

Do not change board statuses, fixed IDs, hashes, authorization timestamps, or the stated next task.

- [ ] **Step 3: Link the active board-4 plan to project state**

After the plan title and before the existing plan-status quote, add:

```markdown
> Repository-wide current state: [`docs/PROJECT_STATE.md`](../../PROJECT_STATE.md). This file is the active execution plan for board 4 and its checkboxes remain the detailed progress record for this board.
```

Do not mark any additional checkbox complete.

- [ ] **Step 4: Confirm no accidental progress mutation**

Run:

```bash
rg -n '板块 4.*进行中|Task 2.*授权|创建并安全保存一张 staging 测试许可证|当前不得提前构建或发布 0.5.1' docs/deployment/authorized-update-roadmap.md
rg -n 'Task 1 状态：\*\*已完成\*\*|Task 2 授权时间|目标文件必须位于仓库外安全目录并拒绝覆盖已有文件|构建 0.5.1' docs/superpowers/plans/2026-08-05-board-4-test-license-and-release.md
```

Expected: all original current-state and safety-gate statements remain present.

- [ ] **Step 5: Add both formerly untracked authority files to Git**

Run:

```bash
git diff --check
git diff -- docs/deployment/authorized-update-roadmap.md docs/superpowers/plans/2026-08-05-board-4-test-license-and-release.md
git add docs/deployment/authorized-update-roadmap.md docs/superpowers/plans/2026-08-05-board-4-test-license-and-release.md
git diff --cached --name-only
git commit -m "docs: track authorized update program state"
```

Expected staged files:

```text
docs/deployment/authorized-update-roadmap.md
docs/superpowers/plans/2026-08-05-board-4-test-license-and-release.md
```

### Task 3: Correct and contextualize the 0.5.0 finalization report

**Files:**
- Modify: `docs/deployment/2026-08-05-local-finalization-report.md:1-216`
- Reference: `docs/PROJECT_STATE.md`
- Reference: `docs/deployment/authorized-update-roadmap.md`

- [ ] **Step 1: Add a dated-snapshot notice**

After the report title, insert:

```markdown
> **Historical snapshot:** This report records the local-finalization state on 2026-08-05. For the current repository state, read [`docs/PROJECT_STATE.md`](../PROJECT_STATE.md); for the later licensing and update program state, read [`authorized-update-roadmap.md`](authorized-update-roadmap.md).
```

- [ ] **Step 2: Correct the Python test count**

Replace:

```markdown
- 全量测试：**465 项通过**；
- 平台条件跳过：**2 项**；
```

with:

```markdown
- 共收集并运行：**465 项**；
- 通过：**463 项**；
- 平台条件跳过：**2 项**；
```

- [ ] **Step 3: Preserve historical risks and append later-status notes**

Under `### 5.1 根目录意外文件 NUL`, append:

```markdown
**后续状态：** 当前工作树已不再显示该 `NUL` 文件；本段保留为报告日期当时的历史记录。
```

Under `### 5.3 云端尚未验收`, append:

```markdown
**后续状态：** 后续路线图记录板块 2 和板块 3 已完成，并记录了 0.5.0 私有 Draft Release 和 staging Worker 发布登记。该结论属于后续人工验收记录，不改变本报告在 2026-08-05 本地收尾时点的范围。
```

Under `### 5.4 未提交工作树`, append:

```markdown
**后续状态：** 自动更新实现和邀请统计修复后来已拆分提交；当前状态以项目状态页和 Git 历史为准。
```

- [ ] **Step 4: Verify report wording**

Run:

```bash
rg -n 'Historical snapshot|共收集并运行：\*\*465|通过：\*\*463|平台条件跳过：\*\*2|后续状态' docs/deployment/2026-08-05-local-finalization-report.md
```

Expected: one snapshot notice, corrected counts, and three later-status annotations.

- [ ] **Step 5: Commit the report correction**

Run:

```bash
git diff --check
git diff -- docs/deployment/2026-08-05-local-finalization-report.md
git add docs/deployment/2026-08-05-local-finalization-report.md
git commit -m "docs: clarify 0.5.0 finalization snapshot"
```

### Task 4: Mark completed construction plans as historical records

**Files:**
- Modify: `docs/superpowers/plans/2026-07-28-group-invite-stats.md`
- Modify: `docs/superpowers/plans/2026-07-29-ai-chat-package.md`
- Modify: `docs/superpowers/plans/2026-07-29-author-support.md`
- Modify: `docs/superpowers/plans/2026-07-29-avatar-and-invite-picker.md`
- Modify: `docs/superpowers/plans/2026-07-29-reusable-session-and-date-picker.md`
- Modify: `docs/superpowers/plans/2026-07-29-web-navigation-simplification.md`
- Modify: `docs/superpowers/plans/2026-07-29-web-result-and-chat-summary.md`
- Modify: `docs/superpowers/plans/2026-08-04-invite-stats-xml-fix.md`
- Modify: `docs/superpowers/plans/2026-08-04-wechat-cli-auto-update.md`

- [ ] **Step 1: Add the standard historical-plan notice to every completed plan**

Immediately after each title, add:

```markdown
> **Historical construction plan:** This file records the intended implementation steps at the time. Its unchecked boxes are not the current project progress. Read [`docs/PROJECT_STATE.md`](../../PROJECT_STATE.md) and the relevant specialist roadmap for current status.
```

For Chinese-first plans, use this equivalent wording:

```markdown
> **历史施工计划：** 本文件记录实施当时的预定步骤，未勾选项目不代表当前完成度。当前状态请读取 [`docs/PROJECT_STATE.md`](../../PROJECT_STATE.md) 和对应专项路线图。
```

Use one language consistently with each file’s primary language.

- [ ] **Step 2: Add verified final-result summaries**

After the notice in each file, add a `## Final result` or `## 最终结果` section containing the matching verified facts below.

Use these exact mappings:

```text
2026-07-28-group-invite-stats.md
  Commits: 019eed8 and later compatibility fixes 8431984, 8d46801
  Result: invite-stats CLI, Web view, CSV/text output, identity binding, XML compatibility
  Tests: tests/test_invite_stats.py and Web command tests

2026-07-29-ai-chat-package.md
  Commits: f7dcdca, d2516b8, 691d19d, 325c2be
  Supporting commits: 1f05b8b, 39f9cb9, df0bee7, d789d21, 853867a, b376f86
  Result: recursive merged forwards, image/sticker collection, voice decode/transcription, CLI and Web ZIP flow
  Tests: tests/test_ai_package.py, test_forwarded.py, test_voice.py, test_asr.py, and Web tests

2026-07-29-author-support.md
  Commits: 0722d49, 09b7152, 9af3767, d8e4a2e
  Result: local author assets, About & Support Web page, focused layout, 0.4.1 delivery preparation
  Tests: Web static-resource and page tests

2026-07-29-avatar-and-invite-picker.md
  Commit: 7f57776
  Result: local avatar proxy, real avatars, invite-group picker, date controls
  Tests: Web server and static UI contract tests

2026-07-29-reusable-session-and-date-picker.md
  Commits: 6344502, 9212262, c59f775, 6ba081c
  Result: shared session/date pickers with stale-request and escape-selection fixes
  Tests: reusable-picker Web contract tests

2026-07-29-web-navigation-simplification.md
  Commit: 6583db7
  Result: simplified Web navigation and unified chat-record workflow
  Tests: Web static and server regression tests

2026-07-29-web-result-and-chat-summary.md
  Commits: d4da7d3, 877af46, 4cec836
  Result: per-feature result isolation, Chinese presentation, chat summary workflow, performance/privacy hardening
  Tests: Web server and UI contract tests

2026-08-04-invite-stats-xml-fix.md
  Commits: 8431984, 8d46801, 2bce874, 6b93b9b
  Result: batch/self QR invitation parsing, direct-local-account attribution, release preparation
  Tests: tests/test_invite_stats.py plus full regression

2026-08-04-wechat-cli-auto-update.md
  Commits: 036cec5, 0802e55, 370a9d9, ef9e0e9, e36ab47
  Result: 0.5.0 licensing, launcher, signed update, rollback, Worker, admin/release CLI, Windows packaging, staging configuration
  Acceptance: docs/deployment/2026-08-05-local-finalization-report.md
  Current continuation: docs/deployment/authorized-update-roadmap.md and the board-4 plan
```

For `2026-08-04-wechat-cli-auto-update.md`, explicitly state that later cloud and release progress belongs to the roadmap and that its 135 unchecked implementation boxes are not a current completion measure.

Do not alter the original task steps or checkbox values.

- [ ] **Step 3: Verify that every completed plan has one notice and one result section**

Run:

```bash
for f in \
  docs/superpowers/plans/2026-07-28-group-invite-stats.md \
  docs/superpowers/plans/2026-07-29-ai-chat-package.md \
  docs/superpowers/plans/2026-07-29-author-support.md \
  docs/superpowers/plans/2026-07-29-avatar-and-invite-picker.md \
  docs/superpowers/plans/2026-07-29-reusable-session-and-date-picker.md \
  docs/superpowers/plans/2026-07-29-web-navigation-simplification.md \
  docs/superpowers/plans/2026-07-29-web-result-and-chat-summary.md \
  docs/superpowers/plans/2026-08-04-invite-stats-xml-fix.md \
  docs/superpowers/plans/2026-08-04-wechat-cli-auto-update.md; do
  echo "--- $f"
  rg -n 'Historical construction plan|历史施工计划|^## Final result|^## 最终结果' "$f"
done
```

Expected: every file reports one historical notice and one final-result heading.

- [ ] **Step 4: Confirm no checkbox history was rewritten**

Run before and after editing, comparing against `HEAD^` after staging:

```bash
git diff --word-diff=porcelain -- docs/superpowers/plans | rg '^[-+]\s*- \[[ x]\]' || true
```

Expected: no added or removed checkbox lines in the nine historical plans.

- [ ] **Step 5: Commit the historical-plan annotations**

Run:

```bash
git diff --check
git diff --stat -- docs/superpowers/plans
git add \
  docs/superpowers/plans/2026-07-28-group-invite-stats.md \
  docs/superpowers/plans/2026-07-29-ai-chat-package.md \
  docs/superpowers/plans/2026-07-29-author-support.md \
  docs/superpowers/plans/2026-07-29-avatar-and-invite-picker.md \
  docs/superpowers/plans/2026-07-29-reusable-session-and-date-picker.md \
  docs/superpowers/plans/2026-07-29-web-navigation-simplification.md \
  docs/superpowers/plans/2026-07-29-web-result-and-chat-summary.md \
  docs/superpowers/plans/2026-08-04-invite-stats-xml-fix.md \
  docs/superpowers/plans/2026-08-04-wechat-cli-auto-update.md
git commit -m "docs: archive completed implementation plans"
```

### Task 5: Synchronize the English README with the current product

**Files:**
- Modify: `README.md:1-406`
- Reference: `pyproject.toml:1-42`
- Reference: `npm/wechat-cli/package.json:1-31`
- Reference: `wechat_cli/main.py:1-60`
- Reference: `wechat_cli/version.py:1-18`

- [ ] **Step 1: Update repository links and product positioning**

Replace all `freestylefly/wechat-cli` repository and Star History references with `AuRevior-ai/wechat-cli`.

Change the subtitle to:

```markdown
**Local WeChat data access for people and AI agents, with a productized Windows 0.5.0 line.**
```

Update highlights so they do not claim universal zero-config npm installation. Include these facts:

```markdown
- **AI-first local data access** — structured JSON, text export, search, analytics, and AI-ready media packages.
- **Local Web console** — chat workflows, invite statistics, exports, and local management surfaces.
- **Windows 0.5.0 product line** — WebView2 Launcher, licensed devices, signed updates, health checks, and rollback.
- **Local-first processing** — WeChat database access and chat processing stay on the machine unless the user explicitly submits diagnostics.
```

- [ ] **Step 2: Replace installation claims with a distribution-channel table**

At the beginning of the installation section, add:

```markdown
## Distribution and version lines

| Channel | Current repository version | Availability |
|---|---:|---|
| Python/source and Windows product line | 0.5.0 | Source checkout; Windows licensed builds are distributed through the private release system |
| Existing npm wrapper | 0.2.4 | Existing npm package, currently carrying the macOS arm64 platform package |

These lines are not synchronized. The npm badge reports the npm channel, not the Windows/Python product version.
```

Keep the npm command but label it `Existing npm channel (0.2.4)`. Do not call it universally recommended.

Change source clone commands to:

```bash
git clone https://github.com/AuRevior-ai/wechat-cli.git
cd wechat-cli
pip install -e .
```

Describe `pip install wechat-cli` as an existing package-channel command whose published version may differ from the repository; make source installation the precise route for repository 0.5.0 development.

- [ ] **Step 3: Synchronize AI-agent examples and command coverage**

In the Claude Code command list, add:

```markdown
- `wechat-cli invite-stats "GROUP" --format text` — group invitation statistics
- `wechat-cli ai-package "CHAT" --output chat-ai.zip` — build an AI-ready text and media package
- `wechat-cli media PATH` — process a local media path returned by history
- `wechat-cli web` — start the local Web console
```

Add command-reference sections for the currently missing commands:

```markdown
### `invite-stats` — Group invitation statistics
```

Use the verified behavior already described in `README_CN.md`: exact identity matching, optional `--bind-identity`, text/CSV output, and source-unknown events excluded from ranking.

```markdown
### `media` — Process local media
```

State that it works with local media paths returned by `history --media`; obtain exact options from:

```bash
python -m wechat_cli.main media --help
```

```markdown
### `web` — Start the local Web console
```

State that it starts the loopback Web interface; obtain exact options from:

```bash
python -m wechat_cli.main web --help
```

Do not invent options not displayed by CLI help.

- [ ] **Step 4: Correct platform and privacy wording**

Replace the platform table with capability and distribution distinctions:

```markdown
| Platform | Source capability | Current packaged channel |
|---|---|---|
| Windows x86-64 | Supported; reads `Weixin.exe` process memory | 0.5.0 Windows product and private update flow |
| macOS Apple Silicon | Supported | Existing npm 0.2.4 arm64 platform package |
| macOS Intel | Source support requires an x86-64 binary | No current bundled npm platform package recorded in this repository |
| Linux | Supported through `/proc/<pid>/mem`; usually requires root | Source installation |
```

Replace absolute “nothing is uploaded” language with:

```markdown
Core chat queries and processing are local. The 0.5.0 product line can contact the configured authorization/update service, and diagnostic upload occurs only after explicit user action.
```

Keep the read-only message guarantee.

- [ ] **Step 5: Add development-state links**

Before acknowledgements, add:

```markdown
## Development records

- [Current project state](docs/PROJECT_STATE.md)
- [Changelog](CHANGELOG.md)
- [Authorized update roadmap](docs/deployment/authorized-update-roadmap.md)
- [Approved designs](docs/superpowers/specs/)
- [Implementation plans](docs/superpowers/plans/) — historical plans are not current progress dashboards
```

- [ ] **Step 6: Verify English README facts against the CLI and metadata**

Run:

```bash
python -m wechat_cli.main --help
python -m wechat_cli.main media --help
python -m wechat_cli.main web --help
rg -n 'AuRevior-ai/wechat-cli|0\.5\.0|0\.2\.4|invite-stats|ai-package|media|web|PROJECT_STATE|CHANGELOG' README.md
rg -n 'version = "0.5.0"' pyproject.toml
rg -n '"version": "0.2.4"' npm/wechat-cli/package.json
```

Expected: repository link is current, both version lines are explicit, and all 15 CLI commands are documented or listed.

- [ ] **Step 7: Commit the English README**

Run:

```bash
git diff --check
git diff -- README.md
git add README.md
git commit -m "docs: align English README with 0.5.0"
```

### Task 6: Synchronize the Chinese README with the same facts

**Files:**
- Modify: `README_CN.md:1-411`
- Reference: `README.md`

- [ ] **Step 1: Mirror repository, positioning, and version-channel changes**

Use the Chinese equivalents of the approved English facts:

```markdown
**面向用户与 AI Agent 的本地微信数据访问工具，并包含产品化的 Windows 0.5.0 路线。**
```

Add this channel table:

```markdown
## 分发渠道与版本线

| 渠道 | 当前仓库版本 | 可用方式 |
|---|---:|---|
| Python/源码与 Windows 产品线 | 0.5.0 | 源码安装；Windows 授权版通过私有发布系统分发 |
| 现有 npm 包装层 | 0.2.4 | 已有 npm 包，目前携带 macOS arm64 平台包 |

两条版本线目前不同步。npm 徽章显示的是 npm 渠道版本，不代表 Windows/Python 主工程版本。
```

Update clone URLs and remove the claim that npm is the universal recommended installation.

- [ ] **Step 2: Synchronize command coverage**

Keep the existing detailed `invite-stats` section.

Add a Chinese `ai-package` section matching the verified English behavior and source code.

Add `media` and `web` sections using the exact CLI help output. Add all four commands to the Agent integration list.

Correct the feature-count statement by replacing “12 个命令” with a factual list or “15 个主命令”; verify the count from CLI help before saving.

- [ ] **Step 3: Mirror platform, privacy, and development-record language**

Use the same four-row capability/distribution table as English.

Replace absolute “数据不会上传任何云端” statements with:

```markdown
核心聊天查询和资料处理在本机完成。0.5.0 产品线会连接配置的授权与更新服务；诊断上传只有在用户明确操作后才会发生。
```

Add:

```markdown
## 开发记录

- [当前项目状态](docs/PROJECT_STATE.md)
- [版本变更记录](CHANGELOG.md)
- [授权更新路线图](docs/deployment/authorized-update-roadmap.md)
- [已批准设计](docs/superpowers/specs/)
- [实施计划](docs/superpowers/plans/)——历史计划不是当前进度看板
```

- [ ] **Step 4: Compare English and Chinese core facts**

Run:

```bash
rg -n 'AuRevior-ai/wechat-cli|0\.5\.0|0\.2\.4|15 个主命令|ai-package|invite-stats|media|web|PROJECT_STATE|CHANGELOG' README_CN.md
rg -n 'AuRevior-ai/wechat-cli|0\.5\.0|0\.2\.4|ai-package|invite-stats|media|web|PROJECT_STATE|CHANGELOG' README.md
```

Expected: both files contain the same repository, version-channel, command, platform, privacy, and project-record facts.

- [ ] **Step 5: Commit the Chinese README**

Run:

```bash
git diff --check
git diff -- README_CN.md
git add README_CN.md
git commit -m "docs: align Chinese README with 0.5.0"
```

### Task 7: Add a version-oriented changelog

**Files:**
- Create: `CHANGELOG.md`
- Reference: Git history from `019eed8` through `e36ab47`
- Reference: existing specs and plans

- [ ] **Step 1: Create the changelog header and evidence note**

Start with:

```markdown
# Changelog

This changelog is reconstructed from repository commits, design documents, implementation plans, and local acceptance reports. It records product changes, not the current execution state. Read [docs/PROJECT_STATE.md](docs/PROJECT_STATE.md) for current status.

No `0.5.1` release is recorded because it has not been built or released.
```

- [ ] **Step 2: Add the 0.5.0 entry**

Create:

```markdown
## 0.5.0 — 2026-08-05

### Added
- Permanent licenses with a three-device limit and signed seven-day offline leases.
- Windows WebView2 Launcher, one-time launch sessions, current-user DPAPI storage, and single-instance handling.
- Ed25519-signed update manifests, resumable downloads, safe ZIP extraction, versioned installs, health checks, failed-version suppression, and automatic rollback.
- Administrator and release CLIs.
- Cloudflare Worker, D1 migrations, R2 diagnostic storage, audit, rate limits, idempotency, and cleanup scheduling.
- Windows bootstrap, 0.4.2 migration, repair, uninstall, and separate application-update ZIP.

### Changed
- Centralized product and version metadata at application 0.5.0 and Launcher 0.1.0.
- Added staging Cloudflare resource configuration and private-release workflow documentation.

### Known delivery limits
- Windows binaries are not code-signed.
- The repository’s existing bootstrap archive is Demo-configured, not a staging installer.
- Production resources and automated publishing are not complete.
```

Link the local finalization report and authorized-update roadmap.

- [ ] **Step 3: Add reconstructed 0.4.x and 0.2.x–0.3.x history**

Use grouped entries supported by Git history:

```markdown
## 0.4.x — 2026-07-29 to 2026-08-04
```

Include AI-ready chat archives, merged forwards, voice decoding/offline transcription, image-key handling, Web AI package flow, author-support page, and invitation XML compatibility fixes.

```markdown
## 0.3.x — 2026-07-29
```

Include reusable session/date pickers, real avatars, invitation-group picker, stale request protection, and simplified Web navigation.

```markdown
## 0.2.6–0.2.7 — 2026-07-28 to 2026-07-29
```

Include invitation statistics, result isolation, Chinese fields, chat-summary workflow, privacy/performance hardening, and Web usability release preparation.

```markdown
## 0.2.5 baseline — 2026-07-28
```

State that commit `02404d2` established the verified baseline used for subsequent feature work.

Do not assign undocumented exact patch versions to individual later changes.

- [ ] **Step 4: Verify the changelog against history**

Run:

```bash
rg -n '^## |0\.5\.1|036cec5|02404d2|PROJECT_STATE' CHANGELOG.md
git log --date=short --pretty=format:'%h %ad %s' 02404d2..e36ab47
```

Expected: 0.5.1 appears only in the explicit “not released” statement, and every described feature has supporting commits.

- [ ] **Step 5: Commit the changelog**

Run:

```bash
git diff --check
git diff -- CHANGELOG.md
git add CHANGELOG.md
git commit -m "docs: add reconstructed changelog"
```

### Task 8: Validate document links, command coverage, and sensitive-data boundaries

**Files:**
- Verify: all Markdown files changed by Tasks 1–7
- Modify only when a verification failure proves a documentation defect

- [ ] **Step 1: Check every local Markdown link in changed files**

Run this read-only Python command:

```bash
python -c "import pathlib,re,sys; files=list(map(pathlib.Path,['AGENTS.md','CHANGELOG.md','README.md','README_CN.md','docs/PROJECT_STATE.md','docs/deployment/authorized-update-roadmap.md','docs/deployment/2026-08-05-local-finalization-report.md','docs/superpowers/plans/2026-08-05-board-4-test-license-and-release.md']))+list(pathlib.Path('docs/superpowers/plans').glob('2026-07-*.md'))+list(map(pathlib.Path,['docs/superpowers/plans/2026-08-04-invite-stats-xml-fix.md','docs/superpowers/plans/2026-08-04-wechat-cli-auto-update.md'])); pat=re.compile(r'!?\[[^\]\n]+\]\(([^)\n]+)\)'); fence=chr(96)*3; bad=[]; [(bad.extend((str(f),u) for u in pat.findall(re.sub(re.escape(fence)+r'.*?'+re.escape(fence),'',f.read_text(encoding='utf-8'),flags=re.S)) if u and not u.startswith(('http://','https://','#','mailto:')) and not (f.parent/u.split('#',1)[0]).resolve().exists())) for f in files]; print('\n'.join(f'{f}: {u}' for f,u in bad)); sys.exit(bool(bad))"
```

Expected: no output and exit code 0.

- [ ] **Step 2: Compare actual CLI commands with README coverage**

Run:

```bash
python -m wechat_cli.main --help
for cmd in ai-package contacts export favorites history init invite-stats media members new-messages search sessions stats unread web; do
  rg -q "${cmd}" README.md && rg -q "${cmd}" README_CN.md || { echo "missing: ${cmd}"; exit 1; }
done
```

Expected: CLI help lists 15 commands and the loop prints nothing.

- [ ] **Step 3: Verify version-channel wording**

Run:

```bash
rg -n 'version = "0.5.0"' pyproject.toml
rg -n 'APP_VERSION = "0.5.0"|LAUNCHER_VERSION = "0.1.0"' wechat_cli/version.py
rg -n '"version": "0.2.4"' npm/wechat-cli/package.json
rg -n '0\.5\.0|0\.2\.4|not synchronized|不同步' README.md README_CN.md docs/PROJECT_STATE.md
```

Expected: repository metadata and both README explanations agree.

- [ ] **Step 4: Scan changed documentation for secret-shaped content**

Run:

```bash
git diff 5310630 -- '*.md' | rg -n -i 'ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|cf_[A-Za-z0-9]{20,}|BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY|Bearer [A-Za-z0-9._-]{20,}|license[_ -]?key[" :=]+[A-Za-z0-9_-]{20,}|device[_ -]?token[" :=]+[A-Za-z0-9._-]{20,}' && exit 1 || true
```

Expected: no secret-shaped match. Public IDs, hashes, public key identifiers, and documentation phrases such as “license key” without a complete value are allowed.

- [ ] **Step 5: Ensure no business-code file changed**

Run:

```bash
git diff --name-only 5310630..HEAD
git status --short
```

Expected: only Markdown documentation files appear; no `.py`, `.ts`, `.js`, `.ps1`, package metadata, build, or `dist` files appear.

- [ ] **Step 6: Commit only proven verification fixes**

If Steps 1–5 require documentation corrections, first confirm that every modified path is in the approved documentation set, then stage the full approved set; Git will stage only files that actually changed:

```bash
git diff --check
git diff --name-only
git add \
  AGENTS.md CHANGELOG.md README.md README_CN.md docs/PROJECT_STATE.md \
  docs/deployment/authorized-update-roadmap.md \
  docs/deployment/2026-08-05-local-finalization-report.md \
  docs/superpowers/plans/*.md
git diff --cached --name-only
git commit -m "docs: fix memory governance verification issues"
```

Expected: `git diff --cached --name-only` contains only approved Markdown paths. If no corrections were needed, do not create an empty commit.

### Task 9: Run full regression verification and inspect final history

**Files:**
- Verify only: entire repository

- [ ] **Step 1: Run the full Python suite**

Run:

```bash
python -m unittest discover -s tests -q
```

Expected final summary:

```text
Ran 465 tests
OK (skipped=2)
```

The suite may print a `missing pywebview` build-probe message after successful tests. Record it as a known environment probe, not as a test failure, only when the unittest final status is `OK`.

- [ ] **Step 2: Run Worker type checking and tests**

Run from `services/license-update-worker`:

```bash
npm run typecheck
npm test -- --run
```

Expected:

```text
Test Files  3 passed (3)
Tests       17 passed (17)
```

- [ ] **Step 3: Run final whitespace and repository-scope checks**

Run:

```bash
git diff --check 5310630..HEAD
git status --short
git diff --stat 5310630..HEAD
git diff --name-status 5310630..HEAD
git log --oneline --decorate -12
```

Expected:

- Working tree is clean.
- Every changed path is one of the approved Markdown files.
- The two previously untracked authority files are now tracked.
- No cloud, release, tag, push, installer, or business-code action occurred.

- [ ] **Step 4: Review the complete documentation diff**

Run:

```bash
git diff 5310630..HEAD -- \
  AGENTS.md CHANGELOG.md README.md README_CN.md docs/PROJECT_STATE.md \
  docs/deployment/authorized-update-roadmap.md \
  docs/deployment/2026-08-05-local-finalization-report.md \
  docs/superpowers/plans
```

Read the full result and confirm:

- Current-state statements do not overclaim live cloud state.
- Board 4 remains in progress and Task 2 is not falsely marked complete.
- README files agree on repository, versions, distribution, commands, platform support, and diagnostics behavior.
- Historical plans retain their original checkboxes.
- 0.5.1 is not presented as released.

- [ ] **Step 5: Record the verified result in the final response**

Report:

- the new memory hierarchy;
- the README and Changelog synchronization;
- the formerly untracked documents now under Git;
- exact Python and Worker verification results;
- the known `pywebview` probe if it appeared;
- remaining project risks: board 4 unfinished, Demo bootstrap, unsigned binaries, and no live cloud revalidation;
- the commit range created by this plan.

Do not claim a push, tag, cloud change, release, license mutation, or 0.5.1 build.
