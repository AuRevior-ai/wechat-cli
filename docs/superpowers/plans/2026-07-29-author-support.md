# Author Support Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an unobtrusive “作者 Au Revior” credit and a local-only “关于与支持” page containing the supplied WeChat contact and payment QR codes, then ship and install Windows version 0.4.1.

**Architecture:** Store the two supplied JPEGs as explicit Web static resources, extend the existing static-resource whitelist to serve only their exact names, and add a new screen using the existing sidebar navigation/state mechanism. Keep QR content out of CLI/JSON output, update project/package metadata, freeze the resources through the existing PyInstaller static-directory inclusion, and verify source, frozen EXE, one-time Web behavior, and installed localhost behavior.

**Tech Stack:** Python 3.12, `http.server`, `importlib.resources`, plain HTML/CSS/JavaScript, Click, PyInstaller, `pytest`, PowerShell packaging scripts.

---

## File map

- Create `wechat_cli/web/static/au-revior-wechat.jpg`: author contact QR source asset.
- Create `wechat_cli/web/static/au-revior-payment.jpg`: author payment QR source asset.
- Modify `wechat_cli/web/server.py`: whitelist and serve the two JPEG filenames through `/static/`.
- Modify `wechat_cli/web/static/index.html`: author credit, bottom navigation entry, and the new support screen.
- Modify `wechat_cli/web/static/app.css`: fixed-bottom sidebar placement, support-page cards, responsive stacking, and QR image presentation.
- Modify `tests/test_web_server.py`: secure resource routing, author credit, navigation, QR semantics, and cache-busting assertions.
- Modify `pyproject.toml`: version 0.4.1 and `Au Revior` project author metadata.
- Modify `wechat_cli/main.py`: CLI version 0.4.1.
- Modify `README.md`: author/support note and 0.4.1 usage language.
- Modify `packaging/windows/README-APP.md`: installed-app author/support instructions.
- Modify `tests/test_main.py`: CLI version assertion.
- Modify `tests/test_windows_packaging.py`: Windows 0.4.1 package/resource expectations.

### Task 1: Add QR assets and a strict static-resource route

**Files:**
- Create: `wechat_cli/web/static/au-revior-wechat.jpg`
- Create: `wechat_cli/web/static/au-revior-payment.jpg`
- Modify: `wechat_cli/web/server.py`
- Test: `tests/test_web_server.py`

- [ ] **Step 1: Write failing static-resource tests**

Add a test that reads the two source files, starts `ThreadingHTTPServer` with `WeChatWebHandler`, sends local-host GET requests, and asserts exact JPEG bytes and content types:

```python
def test_author_qr_assets_are_explicit_local_static_resources(self):
    expected = {
        "au-revior-wechat.jpg": ROOT / "wechat_cli" / "web" / "static" / "au-revior-wechat.jpg",
        "au-revior-payment.jpg": ROOT / "wechat_cli" / "web" / "static" / "au-revior-payment.jpg",
    }
    for filename, source in expected.items():
        self.assertTrue(source.is_file())
        self.assertGreater(source.stat().st_size, 10_000)
        self.assertEqual(source.read_bytes()[:2], b"\xff\xd8")
```

Add whitelist-level assertions so arbitrary sibling files remain inaccessible:

```python
def test_static_asset_whitelist_contains_only_known_web_files(self):
    self.assertEqual(
        web_server.STATIC_ASSET_NAMES,
        {
            "app.css",
            "app.js",
            "au-revior-wechat.jpg",
            "au-revior-payment.jpg",
        },
    )
    self.assertNotIn("README.md", web_server.STATIC_ASSET_NAMES)
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run:

```powershell
python -m pytest -q tests/test_web_server.py -k "author_qr or static_asset_whitelist"
```

Expected: FAIL because the JPEGs and `STATIC_ASSET_NAMES` do not exist.

- [ ] **Step 3: Copy the approved JPEG files into source**

Run:

```powershell
Copy-Item -LiteralPath 'C:\Users\28276\Desktop\个人码.jpg' `
  -Destination 'wechat_cli\web\static\au-revior-wechat.jpg'
Copy-Item -LiteralPath 'C:\Users\28276\Desktop\收款码.jpg' `
  -Destination 'wechat_cli\web\static\au-revior-payment.jpg'
```

Verify:

```powershell
Get-FileHash `
  'C:\Users\28276\Desktop\个人码.jpg', `
  'wechat_cli\web\static\au-revior-wechat.jpg', `
  'C:\Users\28276\Desktop\收款码.jpg', `
  'wechat_cli\web\static\au-revior-payment.jpg' `
  -Algorithm SHA256
```

Expected: each desktop/source pair has identical SHA-256.

- [ ] **Step 4: Implement the explicit static whitelist**

Near the Web server constants, add:

```python
STATIC_ASSET_NAMES = {
    "app.css",
    "app.js",
    "au-revior-wechat.jpg",
    "au-revior-payment.jpg",
}
```

Replace the current two-name route guard with:

```python
if parsed.path.startswith("/static/"):
    name = os.path.basename(parsed.path)
    if name not in STATIC_ASSET_NAMES:
        self.send_error(HTTPStatus.NOT_FOUND)
        return
    content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    if name.endswith(".css"):
        content_type += "; charset=utf-8"
    if name.endswith(".js"):
        content_type = "application/javascript; charset=utf-8"
    self._send_bytes(_static_bytes(name), content_type)
    return
```

This preserves basename normalization, exact filename matching, CSP, `nosniff`, and localhost Host validation.

- [ ] **Step 5: Run focused tests**

Run:

```powershell
python -m pytest -q tests/test_web_server.py -k "author_qr or static_asset_whitelist or local_request_source"
```

Expected: PASS.

- [ ] **Step 6: Commit the secure asset boundary**

```powershell
git add wechat_cli/web/static/au-revior-wechat.jpg `
  wechat_cli/web/static/au-revior-payment.jpg `
  wechat_cli/web/server.py tests/test_web_server.py
git commit -m "feat: serve local author QR assets"
```

### Task 2: Add the author credit and support screen

**Files:**
- Modify: `wechat_cli/web/static/index.html`
- Modify: `wechat_cli/web/static/app.css`
- Test: `tests/test_web_server.py`

- [ ] **Step 1: Write failing UI structure tests**

Add:

```python
def test_web_has_author_credit_and_support_screen(self):
    html = (
        ROOT / "wechat_cli" / "web" / "static" / "index.html"
    ).read_text(encoding="utf-8")
    css = (
        ROOT / "wechat_cli" / "web" / "static" / "app.css"
    ).read_text(encoding="utf-8")

    self.assertIn('class="brand-author">作者 Au Revior</span>', html)
    self.assertIn('data-target="about-support"', html)
    self.assertIn(
        'id="about-support" class="screen" data-title="关于与支持"',
        html,
    )
    self.assertIn('/static/au-revior-wechat.jpg', html)
    self.assertIn('/static/au-revior-payment.jpg', html)
    self.assertIn('alt="Au Revior 的微信二维码"', html)
    self.assertIn('alt="Au Revior 的微信收款码"', html)
    self.assertIn('target="_blank" rel="noopener"', html)
    self.assertIn(".about-support-grid", css)
    self.assertIn(".about-support-card", css)
    self.assertIn(".about-nav", css)
```

Extend the existing navigation-count test to expect nine focused entries and assert the support entry is last:

```python
buttons = re.findall(r'<button[^>]+data-target="([^"]+)"', html)
self.assertEqual(len(buttons), 9)
self.assertEqual(buttons[-1], "about-support")
```

- [ ] **Step 2: Run the UI test and verify failure**

Run:

```powershell
python -m pytest -q tests/test_web_server.py -k "author_credit or navigation_is_reduced"
```

Expected: FAIL because no author screen exists and the navigation still has eight entries.

- [ ] **Step 3: Add the author credit and bottom navigation entry**

In the brand copy, preserve `#profile-name` and add:

```html
<small id="profile-name">正在读取账号…</small>
<span class="brand-author">作者 Au Revior</span>
```

Add the final navigation button:

```html
<button class="about-nav" data-target="about-support">
  <span>关于与支持</span>
  <small>作者 Au Revior</small>
</button>
```

Keep it inside `#nav`, so the existing delegated click handler, `setScreen`, active-button state, title update, and per-screen result-state isolation work without new JavaScript.

- [ ] **Step 4: Add the semantic support page**

Insert before the result area:

```html
<section id="about-support" class="screen" data-title="关于与支持">
  <div class="about-support">
    <header class="about-support-hero">
      <span>AUTHOR &amp; SUPPORT</span>
      <h2>由 Au Revior 制作</h2>
      <p>感谢使用 WeChat CLI Web。二维码仅在本机展示，不会上传网络。</p>
    </header>
    <div class="about-support-grid">
      <article class="about-support-card contact">
        <div>
          <span class="about-card-kicker">CONTACT</span>
          <h3>添加作者微信</h3>
          <p>交流使用体验、问题反馈与功能建议。</p>
        </div>
        <a href="/static/au-revior-wechat.jpg" target="_blank" rel="noopener"
           aria-label="查看 Au Revior 的微信二维码原图">
          <img src="/static/au-revior-wechat.jpg"
               alt="Au Revior 的微信二维码" loading="lazy">
        </a>
      </article>
      <article class="about-support-card payment">
        <div>
          <span class="about-card-kicker">SUPPORT</span>
          <h3>支持作者</h3>
          <p>如果这个工具帮助了你，可以自愿支持后续维护。</p>
        </div>
        <a href="/static/au-revior-payment.jpg" target="_blank" rel="noopener"
           aria-label="查看 Au Revior 的微信收款码原图">
          <img src="/static/au-revior-payment.jpg"
               alt="Au Revior 的微信收款码" loading="lazy">
        </a>
      </article>
    </div>
  </div>
</section>
```

- [ ] **Step 5: Implement desktop and narrow-screen layout**

Change the sidebar and navigation to a vertical flex layout:

```css
.sidebar {
  display: flex;
  flex-direction: column;
}

.nav {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 4px;
}

.about-nav {
  margin-top: auto;
  border-top: 1px solid var(--line) !important;
  border-radius: 0 0 8px 8px !important;
  padding-top: 14px !important;
}
```

Style author/support content with:

```css
.brand-author {
  display: block;
  margin-top: 3px;
  color: var(--green);
  font-size: 11px;
  font-weight: 700;
}

.about-support {
  padding: clamp(20px, 4vw, 46px);
  border: 1px solid var(--line);
  border-radius: 12px;
  background: rgba(255, 253, 248, 0.97);
  box-shadow: var(--shadow);
}

.about-support-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.about-support-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(180px, 260px);
  gap: 20px;
  align-items: center;
  padding: 22px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--panel);
}

.about-support-card img {
  display: block;
  width: 100%;
  max-height: 360px;
  object-fit: contain;
  border-radius: 10px;
  background: #fff;
}
```

Add a media query that stacks the grid and each card below 900px:

```css
@media (max-width: 900px) {
  .about-support-grid {
    grid-template-columns: 1fr;
  }
  .about-support-card {
    grid-template-columns: 1fr;
  }
  .about-support-card img {
    max-height: none;
  }
}
```

Do not crop either QR image; use `object-fit: contain`.

- [ ] **Step 6: Bump static cache URLs**

Change both HTML asset query strings to a unique 0.4.1 marker:

```html
<link rel="stylesheet" href="/static/app.css?v=20260729-author-support">
<script src="/static/app.js?v=20260729-author-support"></script>
```

- [ ] **Step 7: Run UI and JavaScript checks**

Run:

```powershell
python -m pytest -q tests/test_web_server.py -k "author_credit or navigation_is_reduced or cache_busting"
node --check wechat_cli/web/static/app.js
```

Expected: all selected tests PASS and Node reports no syntax error.

- [ ] **Step 8: Commit the Web presentation**

```powershell
git add wechat_cli/web/static/index.html `
  wechat_cli/web/static/app.css tests/test_web_server.py
git commit -m "feat: add author support page"
```

### Task 3: Set author metadata, documentation, and version 0.4.1

**Files:**
- Modify: `pyproject.toml`
- Modify: `wechat_cli/main.py`
- Modify: `README.md`
- Modify: `packaging/windows/README-APP.md`
- Modify: `tests/test_main.py`
- Modify: `tests/test_windows_packaging.py`

- [ ] **Step 1: Write failing version and metadata tests**

Update the main version assertion:

```python
def test_version():
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.4.1" in result.output
```

Add packaging metadata assertions:

```python
def test_release_metadata_names_author_and_version():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    app_readme = (
        ROOT / "packaging" / "windows" / "README-APP.md"
    ).read_text(encoding="utf-8")
    self.assertIn('version = "0.4.1"', pyproject)
    self.assertIn('name = "Au Revior"', pyproject)
    self.assertIn("作者：Au Revior", app_readme)
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest -q tests/test_main.py tests/test_windows_packaging.py
```

Expected: FAIL because current version is 0.4.0 and no author metadata exists.

- [ ] **Step 3: Update Python metadata and CLI version**

In `pyproject.toml`:

```toml
version = "0.4.1"
authors = [
  { name = "Au Revior" },
]
```

In `wechat_cli/main.py`:

```python
_VERSION = "0.4.1"
```

Do not add author data to command JSON payloads.

- [ ] **Step 4: Update user-facing documentation**

Add a short README section:

```markdown
## Author and support

Created by **Au Revior**. In Web mode, open **关于与支持** at the
bottom of the sidebar to add the author on WeChat or voluntarily support
continued maintenance. Both QR codes are bundled locally and are not uploaded.
```

Add to `packaging/windows/README-APP.md`:

```markdown
作者：Au Revior

启动 Web 控制台后，可在左侧底部打开“关于与支持”，查看作者微信二维码和收款码。
二维码随程序保存在本机，不会上传网络。
```

- [ ] **Step 5: Run version and packaging tests**

Run:

```powershell
python -m pytest -q tests/test_main.py tests/test_windows_packaging.py
python -m wechat_cli.main --version
```

Expected: tests PASS and output is `wechat-cli, version 0.4.1`.

- [ ] **Step 6: Commit metadata and documentation**

```powershell
git add pyproject.toml wechat_cli/main.py README.md `
  packaging/windows/README-APP.md tests/test_main.py `
  tests/test_windows_packaging.py
git commit -m "chore: prepare author support release"
```

### Task 4: Full source verification and browser QA

**Files:**
- Modify only if verification exposes a defect in files already listed above.

- [ ] **Step 1: Run the full automated suite**

Run:

```powershell
python -m pytest -q
git diff --check
git status --short
```

Expected: at least 185 tests PASS, no whitespace errors, and no uncommitted tracked files.

- [ ] **Step 2: Start source Web server on a temporary port**

Run the source server on port 8792 using a hidden background process, then request:

```text
GET http://127.0.0.1:8792/
GET http://127.0.0.1:8792/static/au-revior-wechat.jpg
GET http://127.0.0.1:8792/static/au-revior-payment.jpg
GET http://127.0.0.1:8792/static/not-allowed.jpg
```

Expected:

- root: 200 and contains `作者 Au Revior`;
- both known JPEGs: 200, `image/jpeg`, exact source hashes;
- unknown JPEG: 404;
- root and images include `nosniff`;
- malicious `Host: attacker.example:8792` receives 403.

- [ ] **Step 3: Perform visual QA**

Use Playwright against port 8792:

1. Load the root page at desktop viewport 1440×900.
2. Confirm “作者 Au Revior” is visible without scrolling.
3. Click “关于与支持”.
4. Confirm both cards and both QR images are visible.
5. Confirm no image has zero natural width or height.
6. Capture a screenshot for visual inspection.
7. Repeat at 390×844 and confirm cards stack without horizontal overflow.

Expected: both viewports are legible, QR codes are uncropped, and main navigation remains usable.

- [ ] **Step 4: Commit any verification-only correction**

If QA required a correction, run its focused test and commit only the affected files:

```powershell
git add wechat_cli/web/static/index.html `
  wechat_cli/web/static/app.css `
  wechat_cli/web/server.py `
  tests/test_web_server.py
git commit -m "fix: polish author support layout"
```

If no correction was required, do not create an empty commit.

### Task 5: Build, inspect, and install Windows 0.4.1

**Files:**
- Build output: `dist/wechat-cli-web-app-win32-x64-0.4.1.zip`
- Deliverable copy: `C:\Users\28276\Documents\Codex\2026-07-28\gei\outputs\wechat-cli-web-app-win32-x64-0.4.1.zip`

- [ ] **Step 1: Build the frozen executable and Windows ZIP**

Run:

```powershell
python scripts/package_windows_app.py
```

Expected:

- PyInstaller completes;
- frozen executable is created;
- ZIP filename ends with `0.4.1.zip`;
- package contains the app EXE, install scripts, README, license, and third-party notices.

- [ ] **Step 2: Verify frozen CLI and frozen Web resources**

Run:

```powershell
.\dist\wechat-cli-web-app-win32-x64-0.4.1\app\wechat-cli.exe --version
```

Expected: `wechat-cli, version 0.4.1`.

Start the frozen Web server on port 8793 and repeat the root/JPEG/404/security checks from Task 4. The two downloaded JPEG hashes must match the desktop source images.

- [ ] **Step 3: Copy the ZIP to outputs**

Run:

```powershell
Copy-Item -LiteralPath `
  'dist\wechat-cli-web-app-win32-x64-0.4.1.zip' `
  -Destination `
  'C:\Users\28276\Documents\Codex\2026-07-28\gei\outputs\wechat-cli-web-app-win32-x64-0.4.1.zip' `
  -Force
Get-FileHash `
  'C:\Users\28276\Documents\Codex\2026-07-28\gei\outputs\wechat-cli-web-app-win32-x64-0.4.1.zip' `
  -Algorithm SHA256
```

Expected: output ZIP exists and its hash matches the build ZIP.

- [ ] **Step 4: Merge the feature branch locally**

From the main worktree, verify it is clean, then:

```powershell
git merge --ff-only feat/author-support
python -m pytest -q
```

Expected: fast-forward merge and full suite PASS on `main`.

- [ ] **Step 5: Install and start version 0.4.1**

Run the packaged installer:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File 'dist\wechat-cli-web-app-win32-x64-0.4.1\install.ps1'
```

Expected: old 0.4.0 server processes stop, installed files update under `%LOCALAPPDATA%\WeChatCliWeb`, and one logical 0.4.1 Web service starts on port 8787.

- [ ] **Step 6: Verify the installed application**

Verify:

```text
C:\Users\28276\AppData\Local\WeChatCliWeb\app\wechat-cli.exe --version
GET http://127.0.0.1:8787/api/health
GET http://127.0.0.1:8787/static/au-revior-wechat.jpg
GET http://127.0.0.1:8787/static/au-revior-payment.jpg
```

Expected:

- version 0.4.1;
- health `ok: true`;
- exactly one listener on 127.0.0.1:8787;
- two PyInstaller parent/child processes from the installed path only;
- both QR assets return exact source hashes;
- Web UI displays author credit and the support screen.

- [ ] **Step 7: Clean up the feature worktree**

After merge and final checks:

```powershell
git worktree remove '.worktrees\author-support'
git branch -d feat/author-support
git status --short
```

Expected: only `main` remains active, branch is deleted after merge, and the source worktree is clean.
