# Web Navigation Simplification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 精简 Web 控制台导航，把聊天总结交互并入聊天记录，并发布 Windows 0.2.8 安装包。

**Architecture:** 后端 CLI 与 API 保持不变，只调整静态 HTML 的信息架构、JavaScript 的目标页面绑定、少量 CSS 和用户文档。已有 summary 响应模式继续服务聊天记录页面，因此不会复制数据处理逻辑。

**Tech Stack:** Python 3.12、静态 HTML/CSS/JavaScript、unittest/pytest、PyInstaller。

---

### Task 1: 锁定精简信息架构

**Files:**
- Modify: `tests/test_web_server.py`
- Modify: `tests/test_main.py`

- [ ] **Step 1: 写导航精简的失败测试**

在 `tests/test_web_server.py` 中断言导航按钮文字严格为八个保留入口，断言被删除页面 ID 不存在，并断言 `history` 页面包含 `data-result-mode="summary"`、会话搜索框、两个日期输入和数据库范围提示。

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_web_server.py -q`

Expected: FAIL，因为旧导航、独立 `chat-summary` 页面和旧按钮文字仍存在。

- [ ] **Step 3: 写版本失败测试**

把 `tests/test_main.py` 的预期版本改为 `0.2.8`。

- [ ] **Step 4: 运行版本测试确认失败**

Run: `python -m pytest tests/test_main.py -q`

Expected: FAIL，实际版本仍为 `0.2.7`。

### Task 2: 实现 Web 精简

**Files:**
- Modify: `wechat_cli/web/static/index.html`
- Modify: `wechat_cli/web/static/app.js`
- Modify: `wechat_cli/web/static/app.css`

- [ ] **Step 1: 收敛 HTML**

保留八个导航按钮；删除 `sessions`、旧 `history`、`export`、`favorites`、`unread` 页面；把 `chat-summary` 页面改为 `history` 和“聊天记录”；删除快捷操作面板；更新三个统计类标题与复制按钮文字。

- [ ] **Step 2: 调整 JavaScript 页面绑定**

把会话懒加载条件从：

```javascript
if (id === "chat-summary" && !summarySessionsLoaded)
```

改为：

```javascript
if (id === "history" && !summarySessionsLoaded)
```

并把按钮反馈文字统一为“复制精简信息”。

- [ ] **Step 3: 调整单列总览样式**

让 `.dashboard-grid` 在只剩状态面板时使用单列布局并占满宽度，不保留快捷操作空白。

- [ ] **Step 4: 运行定向测试**

Run: `python -m pytest tests/test_web_server.py tests/test_main.py -q`

Expected: PASS。

### Task 3: 文档、版本与发布

**Files:**
- Modify: `README_CN.md`
- Modify: `packaging/windows/README-APP.md`
- Modify: `pyproject.toml`
- Modify: `wechat_cli/main.py`

- [ ] **Step 1: 更新 Web 使用说明**

把独立“聊天总结”描述改为“聊天记录”，列出八个保留入口，并说明“复制精简信息”和数据库起始范围。

- [ ] **Step 2: 升级版本**

把 `pyproject.toml` 与 `wechat_cli/main.py` 的版本统一为 `0.2.8`。

- [ ] **Step 3: 完整验证**

Run:

```powershell
node --check wechat_cli/web/static/app.js
python -m pytest -q
git diff --check
```

Expected: 0 failures，JavaScript 和差异格式检查通过。

- [ ] **Step 4: 浏览器验收**

启动源码 Web 服务，验证导航数量、页面标题、聊天记录下拉和真实群聊读取结果；确认页面切换不串结果、远程图片为零、浏览器错误和警告为零。

- [ ] **Step 5: 提交、合并、打包和安装**

提交功能分支，快进合并到 `main`，运行 `python scripts/package_windows_app.py`，执行安装脚本并验证 `http://127.0.0.1:8787/api/health` 与安装 EXE 版本。
