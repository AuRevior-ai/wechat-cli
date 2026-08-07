# Avatar and Invite Picker Implementation Plan

> **历史施工计划：** 本文件记录实施当时的预定步骤，未勾选项目不代表当前完成度。当前状态请读取 [`docs/PROJECT_STATE.md`](../../PROJECT_STATE.md) 和对应专项路线图。

## 最终结果

- 主要提交：`7f57776`。
- 已实现安全的本机头像代理、真实头像显示、邀请群聊选择器和日期控件。
- 主要验证位于 Web Server 测试和静态 UI 契约测试。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为邀请统计增加群聊下拉与日历，并通过安全的本机代理显示本人、群聊和消息发送者的真实头像。

**Architecture:** `sessions` 增加头像数据；Web 服务提供受限头像代理和本人资料端点；静态前端共享会话数据，分别渲染聊天记录和邀请统计选择器。头像下载失败始终降级为现有首字占位。

**Tech Stack:** Python 3.12、urllib、ThreadingHTTPServer、静态 HTML/CSS/JavaScript、pytest、PyInstaller。

---

### Task 1: 会话头像与本机头像 API

**Files:**
- Modify: `wechat_cli/commands/sessions.py`
- Modify: `wechat_cli/web/server.py`
- Modify: `tests/test_web_server.py`
- Modify: `tests/test_sessions_command.py`

- [ ] **Step 1: 写失败测试**

断言 sessions 结果含 `avatar_url`；断言 `avatar_remote_payload()` 仅接受允许的 HTTPS 头像域名、拒绝非图片和超限响应；断言 `profile_payload()` 返回当前账号资料。

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_sessions_command.py tests/test_web_server.py -q`

Expected: FAIL，因为头像字段和两个 API 函数尚不存在。

- [ ] **Step 3: 实现最小后端**

在 sessions 中调用 `get_contact_avatars()` 并输出：

```python
"avatar_url": avatars.get(username, ""),
```

在 server 中实现：

```python
def avatar_remote_payload(url: str) -> dict[str, Any]:
    # HTTPS + 微信头像域名 + 最终 URL + image/* + 2 MiB 上限
    ...

def profile_payload() -> dict[str, Any]:
    # 从 db_dir 推导 wxid，调用 contacts --detail
    ...
```

并注册 `/api/avatar` 与 `/api/profile`。

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/test_sessions_command.py tests/test_web_server.py -q`

Expected: PASS。

### Task 2: 邀请统计群聊选择器与头像渲染

**Files:**
- Modify: `wechat_cli/web/static/index.html`
- Modify: `wechat_cli/web/static/app.js`
- Modify: `wechat_cli/web/static/app.css`
- Modify: `tests/test_web_server.py`

- [ ] **Step 1: 写失败测试**

断言邀请统计包含 `invite-group-search`、隐藏 `group_name`、listbox 和两个 `type="date"`；断言 JS 仅筛选群聊、通过 `/api/avatar` 代理远程头像、加载 `/api/profile`，并在聊天结果启用头像。

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_web_server.py -q`

Expected: FAIL，因为邀请统计仍是文本框，头像仍使用首字。

- [ ] **Step 3: 实现前端**

聊天记录与邀请统计共享 `sessionChoices`；邀请选择器只渲染：

```javascript
sessionChoices.filter((session) => session.is_group)
```

远程头像统一转换为：

```javascript
`/api/avatar?url=${encodeURIComponent(url)}`
```

页面启动时读取 `/api/profile`，更新左上角头像和昵称。

- [ ] **Step 4: 运行定向测试**

Run: `node --check wechat_cli/web/static/app.js; python -m pytest tests/test_web_server.py -q`

Expected: PASS。

### Task 3: 版本、文档与发布验证

**Files:**
- Modify: `README_CN.md`
- Modify: `packaging/windows/README-APP.md`
- Modify: `pyproject.toml`
- Modify: `wechat_cli/main.py`
- Modify: `tests/test_main.py`

- [ ] **Step 1: 写 0.2.9 失败测试并确认失败**

Run: `python -m pytest tests/test_main.py -q`

Expected: FAIL，当前版本仍为 0.2.8。

- [ ] **Step 2: 更新版本与说明**

把版本统一改为 0.2.9，并说明邀请统计群聊下拉、日历以及本机头像代理。

- [ ] **Step 3: 完整验证**

Run:

```powershell
node --check wechat_cli/web/static/app.js
python -m pytest -q
git diff --check
```

Expected: 0 failures。

- [ ] **Step 4: 真实数据浏览器验收**

验证本人头像、群聊头像、群友/本人消息头像、邀请群聊下拉和日期控件；确认所有头像 `<img>` 均指向 127.0.0.1、浏览器错误为零。

- [ ] **Step 5: 复审、合并、打包和安装**

独立代码复审后快进合并到 `main`，构建 Windows 0.2.9 包，覆盖安装并验证 8787 健康状态和安装 EXE 版本。
