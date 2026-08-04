# Invite Stats XML Compatibility Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Correct batch self-invite counts and attribute WeChat 4.1 `你分享的二维码` join notices to the local account in CLI and Web.

**Architecture:** Extend the shared XML notice parser in `wechat_cli/core/invite_stats.py`; keep aggregation and Web rendering unchanged because both already consume atomic invite events. Pair batch display names with XML usernames only when their cardinalities match, and mark explicit self-shared QR notices with the existing `inviter_is_self` contract.

**Tech Stack:** Python 3.12, `xml.etree.ElementTree`, `unittest`, Click, vanilla JavaScript Web UI, PyInstaller packaging.

---

### Task 1: Record the real WeChat 4.1 parser regressions

**Files:**
- Modify: `tests/test_invite_stats.py`

- [ ] **Step 1: Add the failing batch XML parser test**

Add a test containing `你邀请"甲、乙"加入了群聊`, two `memberlist/username` elements, and assertions that two direct events are returned with `甲/wxid_a` and `乙/wxid_b`.

- [ ] **Step 2: Run the batch test and verify the old one-event behavior fails**

Run: `python -m unittest tests.test_invite_stats.InviteNoticeParserTests.test_splits_batch_self_invitation_xml_and_pairs_usernames -v`

Expected: FAIL because the parser returns one event named `甲、乙`.

- [ ] **Step 3: Add the failing self-shared QR XML parser test**

Add a `scene=qrcode` XML test whose text is `"闵杰 南昌大学"通过扫描你分享的二维码加入群聊` and whose member list contains `wxid_invitee`; assert method `qr`, inviter `你`, `inviter_is_self=True`, invitee name, and invitee username.

- [ ] **Step 4: Run the QR test and verify it fails as unknown**

Run: `python -m unittest tests.test_invite_stats.InviteNoticeParserTests.test_parses_self_shared_qr_xml_with_invitee_username -v`

Expected: FAIL because the current parser returns `None`.

### Task 2: Normalize XML into atomic invite events

**Files:**
- Modify: `wechat_cli/core/invite_stats.py`
- Test: `tests/test_invite_stats.py`

- [ ] **Step 1: Add conservative batch-name expansion**

Introduce a helper that starts with quoted names, splits a single quoted value on `、` or `，` only when XML exposes multiple usernames, and accepts the split only when name and username counts match.

- [ ] **Step 2: Add the self-shared QR XML branch**

For `scene=qrcode` plus the exact phrase `通过扫描你分享的二维码加入群聊`, return `qr` relations carrying `inviter_name_raw="你"`, `inviter_is_self=True`, and positionally paired invitee usernames.

- [ ] **Step 3: Run the two focused parser tests**

Run: `python -m unittest tests.test_invite_stats.InviteNoticeParserTests.test_splits_batch_self_invitation_xml_and_pairs_usernames tests.test_invite_stats.InviteNoticeParserTests.test_parses_self_shared_qr_xml_with_invitee_username -v`

Expected: both PASS.

- [ ] **Step 4: Add and run an aggregation regression**

Add a temporary message DB containing a two-person direct XML notice and a self-shared QR XML notice. Assert the local account has `unique_invitee_count=3`, `direct_count=2`, `qr_count=1`, and `unparsed_count=0`.

Run: `python -m unittest tests.test_invite_stats.InviteAggregationTests.test_aggregates_batch_and_self_shared_qr_xml_for_local_account -v`

Expected: PASS.

- [ ] **Step 5: Run all invite and Web contract tests**

Run: `python -m unittest tests.test_invite_stats tests.test_invite_stats_command tests.test_web_server`

Expected: all tests PASS.

- [ ] **Step 6: Commit the parser fix**

Run: `git add wechat_cli/core/invite_stats.py tests/test_invite_stats.py docs/superpowers/specs/2026-08-04-invite-stats-xml-fix-design.md docs/superpowers/plans/2026-08-04-invite-stats-xml-fix.md && git commit -m "fix: parse batch and self QR invitations"`

### Task 3: Verify against the real local WeChat database

**Files:**
- No source changes expected.

- [ ] **Step 1: Run source CLI against the affected chatroom**

Run the source entry point with the installed local WeChat configuration for `57757918914@chatroom` and inspect JSON.

Expected: Au Revior has `direct_count=26`, `qr_count=17`, the expanded member list contains 43 atomic identities, and the 17 self-shared QR messages are absent from `unparsed_messages`.

- [ ] **Step 2: Run the full test suite**

Run: `python -m unittest discover -s tests`

Expected: all tests PASS.

### Task 4: Release, package, install, and smoke-test

**Files:**
- Modify: `pyproject.toml`
- Modify: `wechat_cli/main.py`
- Modify any existing release/version assertion tests discovered by `rg -n "0\.4\.1" .`

- [ ] **Step 1: Bump the patch version to 0.4.2 and update version tests**

Change both authoritative version declarations from `0.4.1` to `0.4.2`, preserving existing release conventions.

- [ ] **Step 2: Run version and full regression tests**

Run: `python -m unittest discover -s tests`

Expected: all tests PASS.

- [ ] **Step 3: Commit the release metadata**

Run: `git add pyproject.toml wechat_cli/main.py tests && git commit -m "chore: prepare invite stats fix release"`

- [ ] **Step 4: Build the Windows package**

Run the repository's existing Windows packaging script using the configured workspace dependency runtime.

Expected: a successful 0.4.2 package containing `wechat-cli.exe` and Web assets.

- [ ] **Step 5: Replace the local app through the existing installer/update flow**

Stop only the WeChat CLI Web process bound to port 8787, install/copy the verified 0.4.2 package to `C:\Users\28276\AppData\Local\WeChatCliWeb`, and restart it using the established launcher.

- [ ] **Step 6: Smoke-test installed CLI and Web**

Run installed `wechat-cli.exe --version`, installed `invite-stats 57757918914@chatroom --format json`, and the Web invite-stats action at `127.0.0.1:8787`.

Expected: version 0.4.2, direct 26 / QR 17 for Au Revior, no affected QR message marked unparsed, and the Web response matches CLI JSON.

### Task 5: Integrate and preserve a clean source repository

**Files:**
- No additional source changes expected.

- [ ] **Step 1: Run final verification from the feature worktree**

Run: `git status --short` and `python -m unittest discover -s tests`

Expected: clean worktree and all tests PASS.

- [ ] **Step 2: Integrate the reviewed commits into local main**

Use the repository's existing non-destructive integration convention, preserving all user-owned changes.

- [ ] **Step 3: Verify main and the installed app one final time**

Expected: local main contains the fix commits, remains clean, and both installed CLI and Web report the corrected invite statistics.
