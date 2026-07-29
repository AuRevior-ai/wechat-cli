# Reusable Session and Date Picker Implementation Plan

> **For Codex:** Execute this plan task-by-task with test-driven development. Keep the shared picker API generic; do not add page-specific JavaScript branches.

**Goal:** Replace every manual chat/group/date field in the Web console with one reusable session picker system and native graphical date controls.

**Architecture:** Mark picker roots declaratively in HTML with `data-session-picker`, `data-filter`, and `data-multiple`. JavaScript creates a controller for each root and applies shared loading, filtering, rendering, keyboard, selection, chip, retry, and reset behavior against one session cache. Existing command payload shapes remain unchanged.

**Tech Stack:** Static HTML/CSS/JavaScript, Python `unittest`/`pytest`, existing `ThreadingHTTPServer`, PyInstaller Windows packaging.

---

### Task 1: Define the shared UI contract with failing tests

**Files:**
- Modify: `tests/test_web_server.py`

**Step 1: Write failing HTML contract tests**

Assert that:

- `history-chat-picker`, `search-chat-picker`, `members-group-picker`, `stats-chat-picker`, and `invite-group-picker` are `data-session-picker` roots.
- The history/search/stats pickers use `data-filter="all"`.
- The members/invite pickers use `data-filter="group"`.
- Only search uses `data-multiple="true"` and a hidden newline-list command parameter.
- All eight range fields use `class="date-input"` and `type="date"`.

**Step 2: Write failing JavaScript contract tests**

Assert that generic functions such as `createSessionPicker`, `renderSessionPickerOptions`, `selectSessionPickerOption`, `loadSessions`, and `resetSessionPickers` exist, while the old summary/invite-specific render and load functions do not.

**Step 3: Run the focused tests to verify RED**

Run: `python -m pytest tests/test_web_server.py -q`

Expected: failures showing the new reusable picker markup and functions are absent.

**Step 4: Commit tests**

```text
test: define reusable session picker contract
```

### Task 2: Replace page-specific markup with reusable controls

**Files:**
- Modify: `wechat_cli/web/static/index.html`
- Modify: `wechat_cli/web/static/app.css`

**Step 1: Implement the five declarative picker roots**

Each root contains a search combobox, command value field, optional chip container, options list, hint, and retry button. Keep unique ARIA IDs but shared CSS classes.

**Step 2: Standardize graphical date fields**

Replace search and stats text dates with `type="date"`. Give every range input `date-input`; add `data-default-today` only to history fields.

**Step 3: Generalize styles**

Replace `summary-*` picker selectors with `session-picker-*`; preserve current colors, focus visibility, avatar layout, responsive behavior, and add removable multi-select chips.

**Step 4: Run focused tests**

Run: `python -m pytest tests/test_web_server.py -q`

Expected: HTML tests pass; JavaScript contract tests remain red.

### Task 3: Implement the reusable picker controller

**Files:**
- Modify: `wechat_cli/web/static/app.js`

**Step 1: Create controllers**

Build `sessionPickers` from all `[data-session-picker]` roots. Each controller owns DOM references, filter/multiple settings, selected usernames, visible indices, and active option.

**Step 2: Implement shared rendering and selection**

- Filter by name and stable username.
- Limit group pickers to `is_group`.
- Render proxy avatars with letter fallback.
- Single-select writes one username and closes.
- Multi-select writes newline-separated usernames and renders removable chips.
- Implement shared arrow/Enter/Escape behavior.

**Step 3: Share loading, retry, and reset**

Rename the cache loader to `loadSessions`. Render every controller from the same cache. On account refresh, invalidate cache, reset values, clear chips, and reload safely under the existing stale-request guard.

**Step 4: Generalize page activation**

When a newly active screen contains a picker, lazily load sessions. Remove all summary/invite-specific event binding blocks.

**Step 5: Initialize dates**

Set only `[data-default-today]` fields to today. Leave all optional date ranges blank.

**Step 6: Run focused tests and JavaScript syntax check**

Run:

```text
python -m pytest tests/test_web_server.py -q
node --check wechat_cli/web/static/app.js
```

Expected: pass.

**Step 7: Commit implementation**

```text
feat: reuse session and date pickers across web tools
```

### Task 4: Bump release version and protect it with tests

**Files:**
- Modify: `tests/test_main.py`
- Modify: `pyproject.toml`
- Modify: `wechat_cli/main.py`

**Step 1: Change the expected version test to `0.3.0`**

Run: `python -m pytest tests/test_main.py -q`

Expected: fail with current `0.2.9`.

**Step 2: Bump package and CLI versions**

Set both `pyproject.toml` and `wechat_cli/main.py` to `0.3.0`.

**Step 3: Run full tests**

Run: `python -m pytest -q`

Expected: all tests pass.

**Step 4: Commit release version**

```text
chore: bump version to 0.3.0
```

### Task 5: Verify behavior in a real browser

**Files:**
- No source changes unless verification reveals a defect

**Step 1: Start the source Web server on port 8788**

Use the existing configured local WeChat data and the worktree source.

**Step 2: Exercise every picker**

- History: all sessions, single select, today defaults.
- Search: add at least two sessions, remove one chip, graphical dates.
- Members: group-only options.
- Stats: all sessions and optional graphical dates.
- Invite stats: group-only options and optional graphical dates.

Check avatar images, name/username search, mouse selection, keyboard selection, outside-click close, and payload/result submission.

**Step 3: Check responsive layout and console**

Verify desktop and narrow viewport, and confirm no browser console errors.

### Task 6: Independent review, merge, package, and install

**Files:**
- Generated: `dist/wechat-cli-web-app-win32-x64-0.3.0.zip`
- Deliverable: `outputs/wechat-cli-web-app-win32-x64-0.3.0.zip`

**Step 1: Request an independent code review**

Provide the reviewer the design, base commit, head commit, test commands, and browser evidence. Address every substantiated finding and rerun affected tests.

**Step 2: Run final verification**

Run full tests, JavaScript syntax check, and `git diff --check`. Confirm the feature worktree is clean.

**Step 3: Fast-forward merge into local `main`**

Verify main is clean and merge `feat/reusable-session-picker` with `--ff-only`.

**Step 4: Build and install `0.3.0`**

Use the repository packaging script, copy the ZIP to the Codex outputs directory, and run the packaged installer to replace the local installation.

**Step 5: Verify the installed application**

Confirm `http://127.0.0.1:8787/api/health`, version `0.3.0`, profile/avatar endpoints, and the five picker screens in the installed Web app.

**Step 6: Record SHA-256 and clean the worktree**

Report the installed version, test count, browser checks, deliverable path, and checksum.
