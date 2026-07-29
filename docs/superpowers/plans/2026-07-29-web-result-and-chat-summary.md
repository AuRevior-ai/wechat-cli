# Web Result Isolation and Chat Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Web 控制台按功能隔离结果、全面中文化通用字段，并增加可搜索会话与日粒度日期的聊天总结页面。

**Architecture:** 保留现有本地 HTTP API 和原生 HTML/CSS/JavaScript 技术栈。前端按 screen id 保存结果快照，集中处理字段本地化，并在聊天总结页面组合现有 sessions/history 命令，不增加任何外部网络依赖。

**Tech Stack:** Python 3.11、Click CLI、`http.server`、原生 HTML/CSS/JavaScript、`unittest`/pytest、PyInstaller。

---

### Task 1: 固定界面验收行为

**Files:**
- Modify: `tests/test_web_server.py`

- [ ] **Step 1: 编写结果隔离失败测试**

检查静态脚本包含按 screen id 保存/恢复结果的状态容器，并且 `setResult` 接收目标 screen id。

- [ ] **Step 2: 编写中文字段失败测试**

检查脚本包含截图中九个英文属性的中文标签，并在通用键值渲染器中调用字段标签函数。

- [ ] **Step 3: 编写聊天总结失败测试**

检查页面包含 `chat-summary` 导航和表单、搜索式会话选择器、两个 `type="date"` 日期控件，以及脚本中的会话加载和两种复制文本生成函数。

- [ ] **Step 4: 运行测试并确认失败**

Run: `python -m pytest tests/test_web_server.py -q`

Expected: 新增断言失败，原因是对应 UI 和脚本行为尚不存在。

### Task 2: 实现结果隔离和中文展示

**Files:**
- Modify: `wechat_cli/web/static/app.js`

- [ ] **Step 1: 增加每屏结果快照**

增加 `screenResultStates`，快照保存结果 HTML、样式、命令提示、普通复制文本、关键信息文本和下载对象。`setScreen` 恢复目标功能快照，没有快照时显示该功能空状态。

- [ ] **Step 2: 绑定异步结果所属功能**

`runForm` 在请求开始时记录表单所在 screen id；返回后调用 `setResult(payload, screenId, resultMode)`。后台返回时若用户已切换功能，只保存对应快照，不污染当前页面。

- [ ] **Step 3: 增加集中中文标签**

增加 `FIELD_LABELS`、`fieldLabel` 和布尔值中文格式化，在 `renderKeyValue` 与通用数组卡片中使用。

- [ ] **Step 4: 运行目标测试**

Run: `python -m pytest tests/test_web_server.py -q`

Expected: 结果隔离与中文字段测试通过。

### Task 3: 实现聊天总结页面

**Files:**
- Modify: `wechat_cli/web/static/index.html`
- Modify: `wechat_cli/web/static/app.js`
- Modify: `wechat_cli/web/static/app.css`

- [ ] **Step 1: 增加聊天总结表单**

添加左侧入口、搜索式组合框、会话下拉列表、开始/结束日期和提交按钮。技术参数使用隐藏字段固定为 50,000 条。

- [ ] **Step 2: 加载并筛选会话**

通过现有 `/api/run` 请求 500 个 sessions；输入时按名称与账号筛选，选择后将稳定账号写入 `chat_name` 隐藏字段。默认日期使用本机当天。

- [ ] **Step 3: 生成 AI 复制文本**

增加完整文本生成器和关键信息生成器。完整文本包含总结任务、范围、数量和原始消息；关键信息文本仅保留时间、发言人、类型和正文。

- [ ] **Step 4: 渲染总结准备页**

显示选中会话、日期、数量、复制说明和聊天消息，沿用当前消息气泡与复制按钮。

- [ ] **Step 5: 完成视觉细节**

为组合框、下拉菜单、总结范围卡片、加载和空状态增加桌面与窄屏样式，保持现有纸质台账风格与键盘焦点可见性。

- [ ] **Step 6: 运行目标测试**

Run: `python -m pytest tests/test_web_server.py -q`

Expected: 全部 Web 测试通过。

### Task 4: 发布与本机验收

**Files:**
- Modify: `pyproject.toml`
- Modify: `tests/test_main.py`
- Modify: `README_CN.md`
- Modify: `packaging/windows/README-APP.md`

- [ ] **Step 1: 将版本更新至 0.2.7 并更新文档**

记录结果隔离、字段中文化和聊天总结的使用方法。

- [ ] **Step 2: 运行完整测试**

Run: `python -m pytest -q`

Expected: 0 failed。

- [ ] **Step 3: 构建 Windows 交付包**

Run: `python scripts/package_windows_app.py`

Expected: 生成 `dist/wechat-cli-web-app-win32-x64-0.2.7.zip`。

- [ ] **Step 4: 安装本机构建并检查健康状态**

运行包内安装脚本，启动 `127.0.0.1:8787`，访问 `/api/health` 应返回 `{"ok": true}`。

- [ ] **Step 5: 浏览器验收**

实际验证结果切换隔离、最近会话字段中文、聊天总结下拉搜索、日期选择和两种复制按钮。

- [ ] **Step 6: 提交源码**

提交测试、实现、文档和版本变更，确认工作树干净；交付 ZIP 不纳入 Git。

