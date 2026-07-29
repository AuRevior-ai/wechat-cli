const nav = document.querySelector("#nav");
const screens = [...document.querySelectorAll(".screen")];
const title = document.querySelector("#screen-title");
const result = document.querySelector("#result");
const commandPreview = document.querySelector("#command-preview");
const downloadButton = document.querySelector("#download-result");
const copyButton = document.querySelector("#copy-result");
const copyKeyButton = document.querySelector("#copy-key-result");
const initPill = document.querySelector("#init-pill");
const statusList = document.querySelector("#status-list");
const dbDirSelect = document.querySelector("#db-dir-candidates");
const detectDbDirsButton = document.querySelector("#detect-db-dirs");
const setupDbDirInput = document.querySelector("#setup-db-dir");
const summaryChatSearch = document.querySelector("#summary-chat-search");
const summaryChatValue = document.querySelector("#summary-chat-value");
const summaryChatOptions = document.querySelector("#summary-chat-options");
const summaryChatHint = document.querySelector("#summary-chat-hint");
const summaryChatRetry = document.querySelector("#summary-chat-retry");
const summaryDateInputs = [...document.querySelectorAll(".summary-date")];
const inviteGroupSearch = document.querySelector("#invite-group-search");
const inviteGroupValue = document.querySelector("#invite-group-value");
const inviteGroupOptions = document.querySelector("#invite-group-options");
const inviteGroupHint = document.querySelector("#invite-group-hint");
const inviteGroupRetry = document.querySelector("#invite-group-retry");
const profileAvatar = document.querySelector("#profile-avatar");
const profileName = document.querySelector("#profile-name");

let lastText = "";
let lastKeyText = "";
let lastDownload = null;
let lastCopyData = null;
let dbDirCandidates = [];
let summarySessions = [];
let summarySessionsLoaded = false;
let summaryVisibleSessionIndexes = [];
let summaryActiveOption = -1;
let inviteVisibleSessionIndexes = [];
let inviteActiveOption = -1;
let currentScreenId = document.querySelector(".screen.active")?.id || "dashboard";
const screenResultStates = new Map();
const screenRequestVersions = new Map();
const SUMMARY_PREVIEW_LIMIT = 200;

const TYPE_LABELS = {
  text: "文本",
  image: "图片",
  voice: "语音",
  video: "视频",
  sticker: "表情",
  location: "位置",
  link: "链接",
  file: "文件",
  call: "通话",
  system: "系统",
};

const FIELD_LABELS = {
  chat: "聊天名称",
  username: "账号",
  is_group: "是否群聊",
  unread: "未读数量",
  unread_count: "未读数量",
  last_message: "最后一条消息",
  msg_type: "消息类型",
  sender: "发送者",
  sender_name: "发送者",
  timestamp: "时间戳",
  time: "时间",
  count: "数量",
  type: "类型",
  display_name: "显示名称",
  nick_name: "昵称",
  remark: "备注",
  alias: "微信号",
  description: "描述",
  local_type: "联系人类型",
  verify_flag: "认证标记",
  is_subscription: "是否公众号",
  avatar: "头像",
  avatar_url: "头像地址",
  chat_username: "聊天账号",
  chat_avatar_url: "聊天头像",
  sender_username: "发送者账号",
  sender_avatar_url: "发送者头像",
  is_self: "是否本人",
  line: "消息文本",
  text: "消息内容",
  type_label: "消息类型",
  group: "群聊名称",
  member_count: "成员数量",
  members: "群成员",
  owner: "群主",
  summary: "摘要",
  source_chat: "来源会话",
  from: "来源",
  id: "记录编号",
  first_call: "是否首次读取",
  new_count: "新增数量",
  keyword: "关键词",
  scope: "查询范围",
  results: "查询结果",
  start_time: "开始日期",
  end_time: "结束日期",
  limit: "读取上限",
  offset: "偏移数量",
  messages: "聊天记录",
  message_items: "消息详情",
  saved_media: "已保存媒体",
  save_dir: "保存目录",
  failures: "读取失败",
  total: "消息总数",
  type_breakdown: "类型分布",
  top_senders: "发言排行",
  hourly: "时段分布",
  query: "查询内容",
  name: "名称",
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function emptyResultState(screenId) {
  const screen = document.getElementById(screenId);
  const screenTitle = screen?.dataset.title || "当前功能";
  return {
    className: "result empty",
    html: `请在“${escapeHtml(screenTitle)}”中提交操作，结果只会显示在这里。`,
    commandPreview: "等待操作",
    lastText: "",
    lastKeyText: "",
    lastDownload: null,
    copyData: null,
  };
}

function saveResultState(screenId) {
  if (!screenId) return;
  screenResultStates.set(screenId, {
    className: result.className,
    html: result.innerHTML,
    commandPreview: commandPreview.textContent,
    lastText,
    lastKeyText,
    lastDownload,
    copyData: lastCopyData,
  });
}

function applyResultState(state) {
  result.className = state.className;
  result.innerHTML = state.html;
  commandPreview.textContent = state.commandPreview;
  lastText = state.lastText || "";
  lastKeyText = state.lastKeyText || "";
  lastDownload = state.lastDownload || null;
  lastCopyData = state.copyData || null;
  copyKeyButton.classList.toggle("hidden", !lastKeyText && !lastCopyData);
  downloadButton.classList.toggle("hidden", !lastDownload);
}

function restoreResultState(screenId) {
  applyResultState(screenResultStates.get(screenId) || emptyResultState(screenId));
}

function setScreen(id) {
  if (currentScreenId && currentScreenId !== id) {
    saveResultState(currentScreenId);
  }
  currentScreenId = id;
  screens.forEach((screen) => screen.classList.toggle("active", screen.id === id));
  nav.querySelectorAll("button").forEach((button) => {
    button.classList.toggle("active", button.dataset.target === id);
  });
  const active = document.getElementById(id);
  title.textContent = active?.dataset.title || "WeChat CLI Web";
  if (id === "setup" && dbDirCandidates.length === 0) {
    refreshDbDirs().catch((error) => showTransientError(error, "setup"));
  }
  restoreResultState(id);
  if ((id === "history" || id === "invite-stats") && !summarySessionsLoaded) {
    loadSummarySessions().catch(showSummarySessionsError);
  }
}

function compactObject(obj) {
  return Object.fromEntries(Object.entries(obj).filter(([, value]) => {
    if (value === "" || value === null || value === undefined) return false;
    if (Array.isArray(value) && value.length === 0) return false;
    return true;
  }));
}

function readForm(form) {
  const params = {};
  form.querySelectorAll("[data-param]").forEach((field) => {
    const name = field.dataset.param;
    let value;
    if (field.type === "checkbox") {
      value = field.checked;
    } else if (field.dataset.list === "lines") {
      value = field.value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
    } else if (field.type === "number") {
      value = field.value === "" ? "" : Number(field.value);
    } else {
      value = field.value.trim();
    }
    params[name] = value;
  });
  if (form.dataset.command === "history") {
    if (form.dataset.resultMode === "summary") {
      params.media = false;
    } else {
      params.media = true;
    }
  }
  if (form.dataset.command === "invite-stats") {
    params.bind_identity = String(params.bind_identity || "")
      .split(/\r?\n/)
      .map((value) => value.trim())
      .filter(Boolean);
  }
  return { command: form.dataset.command, params: compactObject(params) };
}

function validatePayload(payload) {
  if (payload.command === "init") {
    const params = payload.params || {};
    if (!params.db_dir && dbDirCandidates.length > 1) {
      return "检测到多个微信目录，请先选择一个 db_storage 目录。";
    }
    return "";
  }
  const params = payload.params || {};
  if (payload.command === "invite-stats") {
    if (!params.group_name) return "请先从下拉列表选择一个群聊。";
    if (params.start_time && params.end_time && params.start_time > params.end_time) {
      return "开始日期不能晚于结束日期。";
    }
    return "";
  }
  if (payload.command !== "search") return "";
  if (params.keyword) return "";
  if (params.start_time && params.end_time) return "";
  return "关键词为空时，必须同时填写开始时间和结束时间。";
}

function validateSummaryPayload(params = {}) {
  if (!params.chat_name) return "请先从下拉列表选择一个聊天。";
  if (!params.start_time || !params.end_time) return "请选择完整的开始日期和结束日期。";
  if (params.start_time > params.end_time) return "开始日期不能晚于结束日期。";
  return "";
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok && payload.ok !== false) {
    payload.ok = false;
  }
  return payload;
}

async function refreshStatus(shouldApply = () => true) {
  const status = await fetchJson("/api/status");
  if (!shouldApply()) return status;
  initPill.textContent = status.initialized ? `已初始化 · ${status.keys_count} 个密钥` : "未初始化";
  initPill.className = `pill ${status.initialized ? "ready" : "warn"}`;
  statusList.innerHTML = renderKeyValue({
    "初始化": status.initialized ? "是" : "否",
    "数据目录": status.db_dir || "未设置",
    "目录可访问": status.db_dir_exists ? "是" : "否",
    "密钥数量": status.keys_count,
    "配置文件": status.config_file,
    "状态目录": status.state_dir,
  }, "dl");
  if (setupDbDirInput && status.db_dir && !setupDbDirInput.value) {
    setupDbDirInput.value = status.db_dir;
    if (dbDirCandidates.length) {
      renderDbDirCandidates({ candidates: dbDirCandidates });
    }
  }
}

function renderDbDirCandidates(payload) {
  if (!dbDirSelect) return;
  dbDirCandidates = payload.candidates || [];
  dbDirSelect.innerHTML = "";

  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = dbDirCandidates.length ? "请选择微信目录" : "未检测到目录";
  dbDirSelect.appendChild(placeholder);

  dbDirCandidates.forEach((candidate, index) => {
    const option = document.createElement("option");
    option.value = candidate.path;
    option.textContent = `${index + 1}. ${candidate.account} · ${candidate.path}`;
    dbDirSelect.appendChild(option);
  });

  const currentValue = setupDbDirInput?.value || "";
  const matchingCandidate = dbDirCandidates.find((candidate) => candidate.path === currentValue);
  if (matchingCandidate) {
    dbDirSelect.value = matchingCandidate.path;
    return;
  }

  if (dbDirCandidates.length === 1 && setupDbDirInput && !currentValue) {
    setupDbDirInput.value = dbDirCandidates[0].path;
    dbDirSelect.value = dbDirCandidates[0].path;
  }
}

async function refreshDbDirs() {
  if (!dbDirSelect) return null;
  dbDirSelect.innerHTML = '<option value="">检测中</option>';
  const payload = await fetchJson("/api/db-dirs");
  renderDbDirCandidates(payload);
  return payload;
}

function avatarProxyUrl(url) {
  if (/^https:\/\//i.test(url || "")) {
    return `/api/avatar?url=${encodeURIComponent(url)}`;
  }
  if (/^data:image\//i.test(url || "") || /^\/api\/media\?path=/i.test(url || "")) {
    return url;
  }
  return "";
}

function avatarMarkup(url, label, className = "summary-option-avatar") {
  const initial = String(label || "W").trim().slice(0, 1).toUpperCase() || "W";
  const src = avatarProxyUrl(url);
  return `<span class="${escapeHtml(className)} avatar-shell">
    <span class="avatar-shell-fallback" aria-hidden="true">${escapeHtml(initial)}</span>
    ${src ? `<img src="${escapeHtml(src)}" alt="${escapeHtml(label || "头像")}" loading="lazy" data-avatar-image>` : ""}
  </span>`;
}

async function loadProfile() {
  if (!profileAvatar || !profileName) return;
  const profile = await fetchJson("/api/profile");
  const displayName = profile.display_name || profile.username || "本机微信";
  profileName.textContent = displayName;
  profileName.title = profile.username || displayName;
  profileAvatar.innerHTML = avatarMarkup(
    profile.avatar_url,
    displayName,
    "brand-avatar",
  );
}

function setSummaryOptionsOpen(open) {
  if (!summaryChatOptions || !summaryChatSearch) return;
  summaryChatOptions.hidden = !open;
  summaryChatSearch.setAttribute("aria-expanded", String(open));
}

function renderSummarySessionOptions(query = "") {
  if (!summaryChatOptions) return;
  const normalizedQuery = query.trim().toLocaleLowerCase("zh-CN");
  summaryVisibleSessionIndexes = summarySessions
    .map((session, index) => ({ session, index }))
    .filter(({ session }) => {
      if (!normalizedQuery) return true;
      return [session.chat, session.username, session.sender, session.last_message]
        .some((value) => String(value || "").toLocaleLowerCase("zh-CN").includes(normalizedQuery));
    })
    .slice(0, 80)
    .map(({ index }) => index);
  summaryActiveOption = -1;

  if (!summaryVisibleSessionIndexes.length) {
    summaryChatOptions.innerHTML = '<div class="summary-option-empty">没有匹配的会话</div>';
    return;
  }
  summaryChatOptions.innerHTML = summaryVisibleSessionIndexes.map((sessionIndex) => {
    const session = summarySessions[sessionIndex];
    const meta = [
      session.is_group ? "群聊" : "私聊",
      session.time || "",
      session.unread ? `${session.unread} 条未读` : "",
    ].filter(Boolean).join(" · ");
    return `<button id="summary-session-option-${sessionIndex}" type="button" role="option"
      aria-selected="false" data-session-index="${sessionIndex}">
      ${avatarMarkup(session.avatar_url, session.chat || session.username)}
      <span class="summary-option-main">
        <strong>${escapeHtml(session.chat || session.username)}</strong>
        <small>${escapeHtml(meta)}</small>
      </span>
      <code>${escapeHtml(session.username || "")}</code>
    </button>`;
  }).join("");
}

function selectSummarySession(sessionIndex) {
  const session = summarySessions[sessionIndex];
  if (!session || !summaryChatSearch || !summaryChatValue) return;
  summaryChatSearch.value = session.chat || session.username;
  summaryChatValue.value = session.username || session.chat;
  summaryChatSearch.setAttribute("aria-activedescendant", "");
  if (summaryChatHint) {
    summaryChatHint.textContent = `已选择：${session.chat || session.username} · ${session.is_group ? "群聊" : "私聊"}`;
  }
  setSummaryOptionsOpen(false);
}

function moveSummaryActiveOption(direction) {
  if (!summaryChatOptions || !summaryVisibleSessionIndexes.length) return;
  const optionButtons = [...summaryChatOptions.querySelectorAll("button[data-session-index]")];
  if (!optionButtons.length) return;
  summaryActiveOption = (summaryActiveOption + direction + optionButtons.length) % optionButtons.length;
  optionButtons.forEach((button, index) => {
    const isActive = index === summaryActiveOption;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });
  const activeButton = optionButtons[summaryActiveOption];
  summaryChatSearch.setAttribute("aria-activedescendant", activeButton.id);
  activeButton.scrollIntoView({ block: "nearest" });
}

function setInviteOptionsOpen(open) {
  if (!inviteGroupOptions || !inviteGroupSearch) return;
  inviteGroupOptions.hidden = !open;
  inviteGroupSearch.setAttribute("aria-expanded", String(open));
}

function renderInviteGroupOptions(query = "") {
  if (!inviteGroupOptions) return;
  const normalizedQuery = query.trim().toLocaleLowerCase("zh-CN");
  inviteVisibleSessionIndexes = summarySessions
    .map((session, index) => ({ session, index }))
    .filter(({ session }) => session.is_group)
    .filter(({ session }) => {
      if (!normalizedQuery) return true;
      return [session.chat, session.username]
        .some((value) => String(value || "").toLocaleLowerCase("zh-CN").includes(normalizedQuery));
    })
    .slice(0, 80)
    .map(({ index }) => index);
  inviteActiveOption = -1;

  if (!inviteVisibleSessionIndexes.length) {
    inviteGroupOptions.innerHTML = '<div class="summary-option-empty">没有匹配的群聊</div>';
    return;
  }
  inviteGroupOptions.innerHTML = inviteVisibleSessionIndexes.map((sessionIndex) => {
    const session = summarySessions[sessionIndex];
    return `<button id="invite-group-option-${sessionIndex}" type="button" role="option"
      aria-selected="false" data-session-index="${sessionIndex}">
      ${avatarMarkup(session.avatar_url, session.chat || session.username)}
      <span class="summary-option-main">
        <strong>${escapeHtml(session.chat || session.username)}</strong>
        <small>群聊${session.time ? ` · ${escapeHtml(session.time)}` : ""}</small>
      </span>
      <code>${escapeHtml(session.username || "")}</code>
    </button>`;
  }).join("");
}

function selectInviteGroup(sessionIndex) {
  const session = summarySessions[sessionIndex];
  if (!session?.is_group || !inviteGroupSearch || !inviteGroupValue) return;
  inviteGroupSearch.value = session.chat || session.username;
  inviteGroupValue.value = session.username || session.chat;
  inviteGroupSearch.setAttribute("aria-activedescendant", "");
  if (inviteGroupHint) {
    inviteGroupHint.textContent = `已选择：${session.chat || session.username}`;
  }
  setInviteOptionsOpen(false);
}

function moveInviteActiveOption(direction) {
  if (!inviteGroupOptions || !inviteVisibleSessionIndexes.length) return;
  const optionButtons = [...inviteGroupOptions.querySelectorAll("button[data-session-index]")];
  if (!optionButtons.length) return;
  inviteActiveOption = (inviteActiveOption + direction + optionButtons.length) % optionButtons.length;
  optionButtons.forEach((button, index) => {
    const isActive = index === inviteActiveOption;
    button.classList.toggle("active", isActive);
    button.setAttribute("aria-selected", String(isActive));
  });
  const activeButton = optionButtons[inviteActiveOption];
  inviteGroupSearch.setAttribute("aria-activedescendant", activeButton.id);
  activeButton.scrollIntoView({ block: "nearest" });
}

async function loadSummarySessions() {
  if (!summaryChatSearch || !summaryChatOptions) return [];
  if (summaryChatHint) summaryChatHint.textContent = "正在读取最近会话…";
  if (summaryChatRetry) summaryChatRetry.classList.add("hidden");
  const payload = await fetchJson("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      command: "sessions",
      params: { limit: 5000 },
    }),
  });
  if (!payload.ok || !Array.isArray(payload.data)) {
    throw new Error(payload.stderr || payload.error || "无法读取会话列表");
  }
  summarySessions = payload.data;
  summarySessionsLoaded = true;
  renderSummarySessionOptions(summaryChatSearch.value);
  renderInviteGroupOptions(inviteGroupSearch?.value || "");
  if (summaryChatHint) {
    summaryChatHint.textContent = `已载入 ${summarySessions.length} 个会话，输入名称或账号可快速匹配`;
  }
  if (inviteGroupHint) {
    const groupCount = summarySessions.filter((session) => session.is_group).length;
    inviteGroupHint.textContent = `已载入 ${groupCount} 个群聊，输入群名称或群账号可快速匹配`;
  }
  return summarySessions;
}

function showSummarySessionsError(error) {
  if (summaryChatHint) summaryChatHint.textContent = `会话读取失败：${error.message}`;
  if (summaryChatRetry) summaryChatRetry.classList.remove("hidden");
  if (inviteGroupHint) inviteGroupHint.textContent = `群聊读取失败：${error.message}`;
  if (inviteGroupRetry) inviteGroupRetry.classList.remove("hidden");
}

function showTransientError(error, screenId = currentScreenId) {
  const state = {
    className: "result error",
    html: `<pre>${escapeHtml(error.message)}</pre>`,
    commandPreview: "操作失败",
    lastText: error.message || "",
    lastKeyText: "",
    lastDownload: null,
    copyData: null,
  };
  screenResultStates.set(screenId, state);
  if (currentScreenId === screenId) {
    applyResultState(state);
  }
}

function fieldLabel(key) {
  return FIELD_LABELS[key] || String(key);
}

function renderKeyValue(obj, mode = "div") {
  const entries = Object.entries(obj || {});
  if (mode === "dl") {
    return entries.map(([key, value]) => `<dt>${escapeHtml(fieldLabel(key))}</dt><dd>${escapeHtml(formatScalar(value))}</dd>`).join("");
  }
  return `<div class="kv">${entries.map(([key, value]) => (
    `<div>${escapeHtml(fieldLabel(key))}</div><div>${escapeHtml(formatScalar(value))}</div>`
  )).join("")}</div>`;
}

function formatScalar(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "object") return JSON.stringify(localizeStructuredValue(value), null, 2);
  return String(value);
}

function localizeStructuredValue(value) {
  if (Array.isArray(value)) return value.map(localizeStructuredValue);
  if (value && typeof value === "object") {
    const localized = {};
    Object.entries(value).forEach(([key, nestedValue]) => {
      const label = fieldLabel(key);
      const uniqueLabel = Object.prototype.hasOwnProperty.call(localized, label)
        ? `${label}（${key}）`
        : label;
      localized[uniqueLabel] = localizeStructuredValue(nestedValue);
    });
    return localized;
  }
  if (typeof value === "boolean") return value ? "是" : "否";
  return value;
}

function formatMessagesForKeyCopy(messages) {
  if (!Array.isArray(messages) || messages.length === 0) return "";
  return JSON.stringify(messages, null, 2)
    .split("\n")
    .slice(1, -1)
    .map((line) => `  ${line}`)
    .join("\n");
}

function keyCopyText(payload) {
  if (payload?.data && Array.isArray(payload.data.messages)) {
    return formatMessagesForKeyCopy(payload.data.messages);
  }
  return "";
}

function summarySender(item) {
  const sender = item?.sender || (item?.is_self ? "我" : "");
  return sender === "me" ? "我" : (sender || "未知发送者");
}

function summaryMessageLine(item) {
  const type = TYPE_LABELS[item?.type] || item?.type_label || item?.type || "消息";
  const text = String(item?.text || "").trim() || `[${type}]`;
  return `[${item?.time || "时间未知"}] ${summarySender(item)}（${type}）：${text}`;
}

function formatSummaryCopy(data) {
  const items = Array.isArray(data?.message_items) ? data.message_items : [];
  const lines = items.map(summaryMessageLine);
  return [
    "请总结下面这段微信聊天记录，并使用中文输出：",
    "1. 核心主题与明确结论",
    "2. 已确认的决定、承诺和分工",
    "3. 待办事项（负责人、截止时间、下一步）",
    "4. 重要数字、日期、链接和风险",
    "5. 尚未解决的问题",
    "",
    `会话：${data?.chat || data?.username || "未知会话"}`,
    `日期：${data?.start_time || "最早"} 至 ${data?.end_time || "最新"}`,
    `消息数量：${items.length}`,
    "",
    "—— 聊天记录开始 ——",
    ...(lines.length ? lines : ["（所选日期范围内没有聊天记录）"]),
    "—— 聊天记录结束 ——",
  ].join("\n");
}

function formatSummaryKeyCopy(data) {
  const items = Array.isArray(data?.message_items) ? data.message_items : [];
  return [
    `会话：${data?.chat || data?.username || "未知会话"}`,
    `日期：${data?.start_time || "最早"} 至 ${data?.end_time || "最新"}`,
    `消息数量：${items.length}`,
    "",
    ...(items.length ? items.map(summaryMessageLine) : ["（所选日期范围内没有聊天记录）"]),
  ].join("\n");
}

function renderSummaryResult(data) {
  const items = Array.isArray(data?.message_items) ? data.message_items : [];
  const previewItems = items.slice(0, SUMMARY_PREVIEW_LIMIT);
  const previewNotice = items.length > previewItems.length
    ? `<div class="summary-preview-notice">共 ${items.length} 条，仅在网页预览前 ${previewItems.length} 条；复制仍包含全部记录。</div>`
    : "";
  return `<div class="summary-result">
    <section class="summary-result-hero">
      <div class="summary-chat-identity">
        ${renderAvatar(data, data?.chat || data?.username || "聊天记录", { allowRemote: true })}
        <div>
          <span>已整理，可交给 AI</span>
          <h2>${escapeHtml(data?.chat || data?.username || "聊天记录")}</h2>
          <code>${escapeHtml(data?.username || "")}</code>
        </div>
      </div>
      <div class="summary-range">
        <span>日期范围</span>
        <strong>${escapeHtml(data?.start_time || "最早")} <i>→</i> ${escapeHtml(data?.end_time || "最新")}</strong>
      </div>
      <div class="summary-count">
        <strong>${escapeHtml(items.length)}</strong>
        <span>条消息</span>
      </div>
    </section>
    <section class="summary-copy-guide">
      <div><b>复制</b><span>包含总结要求与完整聊天记录，可直接粘贴给 AI。</span></div>
      <div><b>复制精简信息</b><span>只保留范围、时间、发言人、类型和正文。</span></div>
    </section>
    ${previewNotice}
    ${renderChatMessages(previewItems, {
      allowRemoteAvatars: true,
      allowRemoteMedia: false,
    })}
  </div>`;
}

function firstArray(data) {
  if (Array.isArray(data)) return data;
  if (!data || typeof data !== "object") return null;
  for (const value of Object.values(data)) {
    if (Array.isArray(value)) return value;
  }
  return null;
}

function renderStats(data) {
  const hourly = data.hourly || {};
  const max = Math.max(1, ...Object.values(hourly).map(Number));
  const bars = Object.entries(hourly).map(([hour, count]) => {
    const width = Math.max(2, Number(count) / max * 100);
    return `<div class="bar"><span>${escapeHtml(hour)}:00</span><span><i class="bar-fill" style="display:block;width:${width}%"></i></span><b>${escapeHtml(count)}</b></div>`;
  }).join("");
  return `
    <div class="result-grid">
      <div class="item-row">${renderKeyValue({
        "消息总数": data.total,
        "类型分布": Object.entries(data.type_breakdown || {}).map(([k, v]) => `${TYPE_LABELS[k] || k}: ${v}`).join(" / "),
        "发言排行": (data.top_senders || []).map((item) => `${item.name}: ${item.count}`).join(" / "),
      })}</div>
      <div class="item-row"><strong>24 小时分布</strong><div class="bars">${bars}</div></div>
    </div>`;
}

function inviteCsv(data) {
  const rows = [[
    "邀请者排名", "邀请者", "邀请者账号", "邀请者身份状态",
    "唯一拉人数", "被邀请者", "被邀请者账号",
    "被邀请者身份状态", "入群时间", "邀请方式", "原始提示",
  ]];
  const ranking = new Map(
    (data.ranking || []).map((item) => [item.inviter_key, item])
  );
  const events = [
    ...(data.events || []),
    ...(data.unattributed_events || []),
  ];
  for (const event of events) {
    const inviter = ranking.get(event.inviter_key) || {};
    rows.push([
      inviter.rank || "",
      inviter.inviter_name || event.inviter_name_raw || "",
      inviter.inviter_username || "",
      event.inviter_identity_status || "",
      inviter.unique_invitee_count || 0,
      event.invitee_name_raw || "",
      event.invitee_username || "",
      event.invitee_identity_status || "",
      event.time || "",
      ({
        direct: "直接邀请",
        qr: "二维码",
        unattributed_qr: "来源不明扫码",
      })[event.method] || event.method,
      event.raw_text || "",
    ]);
  }
  const quote = (value) => `"${String(value).replaceAll('"', '""')}"`;
  return "\ufeff" + rows.map((row) => row.map(quote).join(",")).join("\r\n");
}

function renderInviteStats(data) {
  const summary = data.summary || {};
  const scope = data.scope || {};
  const cards = [
    ["邀请事件", summary.invite_event_count || 0],
    ["已归属", summary.attributed_event_count || 0],
    ["唯一成员", summary.unique_invitee_count || 0],
    ["来源不明", summary.unattributed_count || 0],
    ["身份待确认", summary.unresolved_identity_count || 0],
    ["未解析", summary.unparsed_count || 0],
  ];
  const scopeHtml = `
    <div class="invite-scope">
      <div>
        <span>统计群聊</span>
        <strong>${escapeHtml(data.chat || "")}</strong>
        <code>${escapeHtml(data.username || "")}</code>
      </div>
      <div>
        <span>可见系统消息范围</span>
        <strong>${escapeHtml(scope.first_visible_system_time || "无记录")}
          <i>→</i> ${escapeHtml(scope.last_visible_system_time || "无记录")}</strong>
      </div>
    </div>`;
  const cardHtml = `<div class="invite-summary">${
    cards.map(([label, value], index) => `
      <div class="invite-summary-card" style="--card-index:${index}">
        <span>${escapeHtml(label)}</span>
        <strong>${escapeHtml(value)}</strong>
      </div>`).join("")
  }</div>`;
  const rows = (data.ranking || []).map((item) => `
    <details class="invite-rank-row">
      <summary>
        <span class="invite-rank">#${escapeHtml(item.rank)}</span>
        <span class="invite-person">
          <strong>${escapeHtml(item.inviter_name)}</strong>
          <code>${escapeHtml(item.inviter_username || "身份待确认")}</code>
        </span>
        <b>${escapeHtml(item.unique_invitee_count)} 人</b>
        <span class="invite-method-counts">
          直接 ${escapeHtml(item.direct_count)} · 二维码 ${escapeHtml(item.qr_count)}
        </span>
      </summary>
      <div class="invitee-list">${
        (item.invitees || []).map((invitee) => `
          <div>
            <strong>${escapeHtml(invitee.name)}</strong>
            ${invitee.username ? `<code>${escapeHtml(invitee.username)}</code>` : ""}
            <span>${escapeHtml(invitee.time)} ·
              ${invitee.method === "direct" ? "直接邀请" : "二维码"}</span>
          </div>
        `).join("") || "没有明细"
      }</div>
    </details>`).join("");
  const tableHtml = `
    <div class="invite-section-heading">
      <span>LEADERBOARD</span><h3>拉新排行榜</h3>
    </div>
    <div class="invite-ranking-table">${
      rows || '<div class="empty">当前可见范围没有邀请记录。</div>'
    }</div>`;
  const eventRows = (data.events || []).map((event) => `
    <tr>
      <td>${escapeHtml(event.time)}</td>
      <td><strong>${escapeHtml(event.inviter_name_raw)}</strong>
        ${event.inviter_username ? `<code>${escapeHtml(event.inviter_username)}</code>` : ""}</td>
      <td><strong>${escapeHtml(event.invitee_name_raw)}</strong>
        ${event.invitee_username ? `<code>${escapeHtml(event.invitee_username)}</code>` : ""}</td>
      <td><span class="method-badge ${event.method}">${
        event.method === "direct" ? "直接邀请" : "二维码"
      }</span></td>
      <td>${event.inviter_identity_status === "resolved" &&
             event.invitee_identity_status === "resolved"
             ? '<span class="identity-ok">已确认</span>'
             : '<span class="identity-pending">身份待确认</span>'}</td>
    </tr>`).join("");
  const detailsHtml = `
    <div class="invite-section-heading">
      <span>AUDIT TRAIL</span><h3>全部邀请关系</h3>
    </div>
    <div class="invite-detail-scroll">
      <table class="invite-detail-table">
        <thead><tr><th>时间</th><th>邀请者</th><th>被邀请者</th><th>方式</th><th>身份</th></tr></thead>
        <tbody>${eventRows || '<tr><td colspan="5">没有明细</td></tr>'}</tbody>
      </table>
    </div>`;
  const issueItems = [
    ...(data.unattributed_events || []).map((event) => ({
      label: "来源不明",
      time: event.time,
      text: event.raw_text,
    })),
    ...(data.unparsed_messages || []).map((item) => ({
      label: "未解析",
      time: item.time,
      text: item.raw_text,
    })),
  ];
  const issuesHtml = issueItems.length ? `
    <div class="invite-section-heading">
      <span>REVIEW QUEUE</span><h3>待核查记录</h3>
    </div>
    <div class="invite-issues">${issueItems.map((item) => `
      <div><b>${escapeHtml(item.label)}</b>
      <span>${escapeHtml(item.time)}</span>
      <p>${escapeHtml(item.text)}</p></div>
    `).join("")}</div>` : "";
  return `<div class="invite-dashboard">${
    scopeHtml + cardHtml + tableHtml + detailsHtml + issuesHtml
  }</div>`;
}

function isSafeImageUrl(url) {
  return /^https?:\/\//i.test(url) || /^data:image\//i.test(url) || /^\/api\/media\?path=/i.test(url);
}

function mediaUrl(media, { allowRemote = true } = {}) {
  if (!media || typeof media !== "object") return "";
  const isRemote = /^https?:\/\//i.test(media.url || "");
  if (media.url && isSafeImageUrl(media.url) && (allowRemote || !isRemote)) return media.url;
  if (media.path) return `/api/media?path=${encodeURIComponent(media.path)}`;
  return "";
}

function renderAvatar(item, label, { allowRemote = true } = {}) {
  const url = item?.sender_avatar_url || item?.avatar_url || item?.chat_avatar_url || "";
  const isRemote = /^https?:\/\//i.test(url);
  const initial = String(label || "W").trim().slice(0, 1).toUpperCase() || "W";
  const src = url && isSafeImageUrl(url) && (allowRemote || !isRemote)
    ? avatarProxyUrl(url)
    : "";
  return `<span class="message-avatar avatar-shell">
    <span class="avatar-fallback avatar-shell-fallback" aria-hidden="true">${escapeHtml(initial)}</span>
    ${src ? `<img class="avatar-img" src="${escapeHtml(src)}" alt="${escapeHtml(label || "头像")}" loading="lazy" data-avatar-image>` : ""}
  </span>`;
}

function renderMessageMedia(item, { allowRemote = true } = {}) {
  const media = item?.media;
  if (!media || typeof media !== "object") return "";
  const src = mediaUrl(media, { allowRemote });
  const label = media.kind === "sticker" ? "表情" : (TYPE_LABELS[media.kind] || "媒体");
  const meta = [
    media.filename,
    media.md5 ? `md5: ${media.md5}` : "",
    media.exists === false ? "文件不存在" : "",
  ].filter(Boolean).join(" · ");
  if ((media.kind === "image" || media.kind === "sticker") && src) {
    return `<figure class="message-media">
      <img src="${escapeHtml(src)}" alt="${escapeHtml(label)}" loading="lazy" referrerpolicy="no-referrer">
      ${meta ? `<figcaption>${escapeHtml(meta)}</figcaption>` : ""}
    </figure>`;
  }
  return `<div class="media-chip">${escapeHtml(label)}${meta ? ` · ${escapeHtml(meta)}` : ""}</div>`;
}

function renderChatMessages(items, {
  allowRemoteAvatars = true,
  allowRemoteMedia = true,
} = {}) {
  if (!items.length) return `<div class="empty">没有消息。</div>`;
  return `<div class="chat-list">${items.map((item) => {
    const sender = item.sender === "me" ? "我" : (item.sender || item.chat || "消息");
    const type = TYPE_LABELS[item.type] || item.type_label || item.type || "消息";
    return `<article class="message-row ${item.is_self ? "mine" : ""}">
      ${renderAvatar(item, sender, { allowRemote: allowRemoteAvatars })}
      <div class="message-main">
        <div class="message-meta">
          <strong>${escapeHtml(sender)}</strong>
          <span>${escapeHtml(item.time || "")}</span>
          <em>${escapeHtml(type)}</em>
        </div>
        <div class="message-bubble">
          <p>${escapeHtml(item.text || "")}</p>
          ${renderMessageMedia(item, { allowRemote: allowRemoteMedia })}
        </div>
      </div>
    </article>`;
  }).join("")}</div>`;
}

function renderArray(items) {
  if (items.length === 0) return `<div class="empty">没有结果。</div>`;
  return `<div class="result-grid">${items.map((item) => {
    if (typeof item === "string") {
      return `<div class="item-row">${escapeHtml(item)}</div>`;
    }
    if (!item || typeof item !== "object") {
      return `<div class="item-row">${escapeHtml(formatScalar(item))}</div>`;
    }
    const primary = item.chat || item.display_name || item.nick_name || item.summary || item.name || item.username || item.id || "记录";
    const typeMeta = TYPE_LABELS[item.type] || item.msg_type || item.type || "";
    const meta = [item.time, typeMeta, item.is_group ? "群聊" : "", item.unread ? `${item.unread} 条未读` : ""]
      .filter(Boolean).join(" · ");
    return `<article class="item-row">
      <strong>${escapeHtml(primary)}</strong>
      ${meta ? `<p class="meta">${escapeHtml(meta)}</p>` : ""}
      ${renderKeyValue(item)}
    </article>`;
  }).join("")}</div>`;
}

function renderData(data) {
  if (data && typeof data === "object" &&
      Array.isArray(data.ranking) && data.summary &&
      Array.isArray(data.events)) {
    return renderInviteStats(data);
  }
  if (data && typeof data === "object" && "hourly" in data && "total" in data) {
    return renderStats(data);
  }
  if (data && typeof data === "object" && Array.isArray(data.message_items)) {
    const rest = Object.fromEntries(Object.entries(data).filter(([key]) => key !== "messages" && key !== "message_items"));
    return `${Object.keys(rest).length ? `<div class="item-row">${renderKeyValue(rest)}</div>` : ""}${renderChatMessages(data.message_items)}`;
  }
  const array = firstArray(data);
  if (array) {
    const rest = Array.isArray(data) ? null : Object.fromEntries(Object.entries(data).filter(([, value]) => !Array.isArray(value)));
    return `${rest && Object.keys(rest).length ? `<div class="item-row">${renderKeyValue(rest)}</div>` : ""}${renderArray(array)}`;
  }
  if (data && typeof data === "object") {
    return `<div class="item-row">${renderKeyValue(data)}</div>`;
  }
  return `<pre>${escapeHtml(formatScalar(data))}</pre>`;
}

function buildResultState(payload, resultMode = "") {
  const output = payload.stdout || payload.stderr || payload.error || "";
  const isSummaryData = resultMode === "summary" &&
    payload.data && Array.isArray(payload.data.message_items);
  const text = isSummaryData ? "" : (payload.data ? JSON.stringify(payload.data, null, 2) : output);
  const state = {
    className: `result ${payload.ok ? "" : "error"}`.trim(),
    html: "",
    commandPreview: payload.command ? payload.command.join(" ") : "请求失败",
    lastText: isSummaryData ? "" : (text || JSON.stringify(payload, null, 2)),
    lastKeyText: keyCopyText(payload),
    lastDownload: null,
    copyData: null,
  };

  if (!payload.ok) {
    state.html = `<pre>${escapeHtml(output || payload.error || "操作失败")}</pre>`;
    return state;
  }

  if (payload.data) {
    if (isSummaryData) {
      const summaryData = {
        chat: payload.data.chat || "",
        username: payload.data.username || "",
        avatar_url: payload.data.avatar_url || "",
        start_time: payload.data.start_time || null,
        end_time: payload.data.end_time || null,
        message_items: payload.data.message_items,
      };
      state.html = renderSummaryResult(summaryData);
      state.lastText = "";
      state.lastKeyText = "";
      state.copyData = summaryData;
      state.commandPreview = `聊天记录 · ${summaryData.chat || summaryData.username || "会话"} · ${
        summaryData.start_time || "最早"
      } 至 ${summaryData.end_time || "最新"}`;
      return state;
    }
    state.html = renderData(payload.data);
    if (payload.command?.[1] === "invite-stats") {
      state.lastDownload = {
        text: inviteCsv(payload.data),
        filename: "wechat-invite-stats.csv",
      };
    }
    return state;
  }

  state.html = `<pre>${escapeHtml(output)}</pre>`;
  if (payload.command?.[1] === "export" && output) {
    state.lastDownload = {
      text: output,
      filename: payload.command.includes("txt") ? "wechat-export.txt" : "wechat-export.md",
    };
  }
  return state;
}

function setResult(payload, screenId = currentScreenId, resultMode = "") {
  const state = buildResultState(payload, resultMode);
  screenResultStates.set(screenId, state);
  if (currentScreenId === screenId) {
    applyResultState(state);
  }
}

async function runForm(form) {
  if (!form.reportValidity()) return;
  const screenId = form.closest(".screen")?.id || currentScreenId;
  const resultMode = form.dataset.resultMode || "";
  const requestVersion = (screenRequestVersions.get(screenId) || 0) + 1;
  screenRequestVersions.set(screenId, requestVersion);
  const payload = readForm(form);
  const validationError = resultMode === "summary"
    ? validateSummaryPayload(payload.params)
    : validatePayload(payload);
  if (validationError) {
    const errorState = {
      className: "result error",
      html: `<pre>${escapeHtml(validationError)}</pre>`,
      commandPreview: "表单校验失败",
      lastText: validationError,
      lastKeyText: "",
      lastDownload: null,
      copyData: null,
    };
    screenResultStates.set(screenId, errorState);
    if (currentScreenId === screenId) applyResultState(errorState);
    return;
  }
  const loadingState = {
    className: "result empty",
    html: "执行中...",
    commandPreview: `${payload.command} ${JSON.stringify(payload.params)}`,
    lastText: "",
    lastKeyText: "",
    lastDownload: null,
    copyData: null,
  };
  screenResultStates.set(screenId, loadingState);
  if (currentScreenId === screenId) applyResultState(loadingState);
  const requestPayload = resultMode === "summary"
    ? { ...payload, response_mode: "summary" }
    : payload;
  let response;
  try {
    response = await fetchJson("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestPayload),
    });
  } catch (error) {
    if (screenRequestVersions.get(screenId) !== requestVersion) return;
    showTransientError(error, screenId);
    return;
  }
  if (screenRequestVersions.get(screenId) !== requestVersion) return;
  setResult(response, screenId, resultMode);
  if (payload.command === "init") {
    try {
      await refreshStatus(() => screenRequestVersions.get(screenId) === requestVersion);
      if (screenRequestVersions.get(screenId) !== requestVersion) return;
    } catch (error) {
      if (screenRequestVersions.get(screenId) !== requestVersion) return;
      showTransientError(error, screenId);
    }
  }
}

nav.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-target]");
  if (button) setScreen(button.dataset.target);
});

document.querySelectorAll(".tool-form").forEach((form) => {
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    runForm(form);
  });
});

document.querySelectorAll("[data-action='refresh-status'], #refresh-status").forEach((button) => {
  button.addEventListener("click", () => {
    refreshStatus().catch((error) => showTransientError(error, "dashboard"));
  });
});

if (detectDbDirsButton) {
  detectDbDirsButton.addEventListener("click", () => {
    refreshDbDirs().catch((error) => showTransientError(error, "setup"));
  });
}

if (dbDirSelect && setupDbDirInput) {
  dbDirSelect.addEventListener("change", () => {
    if (dbDirSelect.value) {
      setupDbDirInput.value = dbDirSelect.value;
    }
  });
}

if (summaryChatSearch && summaryChatValue && summaryChatOptions) {
  summaryChatSearch.addEventListener("focus", () => {
    renderSummarySessionOptions(summaryChatSearch.value);
    setSummaryOptionsOpen(true);
  });
  summaryChatSearch.addEventListener("input", () => {
    summaryChatValue.value = "";
    if (summaryChatHint) summaryChatHint.textContent = "请从匹配结果中选择一个会话";
    renderSummarySessionOptions(summaryChatSearch.value);
    setSummaryOptionsOpen(true);
  });
  summaryChatSearch.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setSummaryOptionsOpen(true);
      moveSummaryActiveOption(event.key === "ArrowDown" ? 1 : -1);
    } else if (event.key === "Enter" && summaryActiveOption >= 0) {
      event.preventDefault();
      const sessionIndex = summaryVisibleSessionIndexes[summaryActiveOption];
      selectSummarySession(sessionIndex);
    } else if (event.key === "Escape") {
      setSummaryOptionsOpen(false);
    }
  });
  summaryChatOptions.addEventListener("mousedown", (event) => {
    event.preventDefault();
  });
  summaryChatOptions.addEventListener("click", (event) => {
    const option = event.target.closest("button[data-session-index]");
    if (option) selectSummarySession(Number(option.dataset.sessionIndex));
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest("#summary-chat-combobox")) {
      setSummaryOptionsOpen(false);
    }
  });
}

if (summaryChatRetry) {
  summaryChatRetry.addEventListener("click", () => {
    loadSummarySessions().catch(showSummarySessionsError);
  });
}

if (inviteGroupSearch && inviteGroupValue && inviteGroupOptions) {
  inviteGroupSearch.addEventListener("focus", () => {
    renderInviteGroupOptions(inviteGroupSearch.value);
    setInviteOptionsOpen(true);
  });
  inviteGroupSearch.addEventListener("input", () => {
    inviteGroupValue.value = "";
    if (inviteGroupHint) inviteGroupHint.textContent = "请从匹配结果中选择一个群聊";
    renderInviteGroupOptions(inviteGroupSearch.value);
    setInviteOptionsOpen(true);
  });
  inviteGroupSearch.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setInviteOptionsOpen(true);
      moveInviteActiveOption(event.key === "ArrowDown" ? 1 : -1);
    } else if (event.key === "Enter" && inviteActiveOption >= 0) {
      event.preventDefault();
      const sessionIndex = inviteVisibleSessionIndexes[inviteActiveOption];
      selectInviteGroup(sessionIndex);
    } else if (event.key === "Escape") {
      setInviteOptionsOpen(false);
    }
  });
  inviteGroupOptions.addEventListener("mousedown", (event) => {
    event.preventDefault();
  });
  inviteGroupOptions.addEventListener("click", (event) => {
    const option = event.target.closest("button[data-session-index]");
    if (option) selectInviteGroup(Number(option.dataset.sessionIndex));
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest("#invite-group-combobox")) {
      setInviteOptionsOpen(false);
    }
  });
}

if (inviteGroupRetry) {
  inviteGroupRetry.addEventListener("click", () => {
    loadSummarySessions().catch(showSummarySessionsError);
  });
}

const localDate = new Date();
const localToday = [
  localDate.getFullYear(),
  String(localDate.getMonth() + 1).padStart(2, "0"),
  String(localDate.getDate()).padStart(2, "0"),
].join("-");
summaryDateInputs.forEach((input) => {
  if (!input.value) input.value = localToday;
});

document.addEventListener("error", (event) => {
  if (event.target.matches?.("img[data-avatar-image]")) {
    event.target.remove();
  }
}, true);

copyButton.addEventListener("click", async () => {
  const copyText = lastText || (lastCopyData ? formatSummaryCopy(lastCopyData) : "");
  if (!copyText) return;
  await navigator.clipboard.writeText(copyText);
  copyButton.textContent = "已复制";
  setTimeout(() => { copyButton.textContent = "复制"; }, 1000);
});

copyKeyButton.addEventListener("click", async () => {
  const copyText = lastKeyText || (lastCopyData ? formatSummaryKeyCopy(lastCopyData) : "");
  if (!copyText) return;
  await navigator.clipboard.writeText(copyText);
  copyKeyButton.textContent = "已复制精简信息";
  setTimeout(() => { copyKeyButton.textContent = "复制精简信息"; }, 1000);
});

downloadButton.addEventListener("click", () => {
  if (!lastDownload) return;
  const blob = new Blob([lastDownload.text], { type: "text/plain;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = lastDownload.filename;
  link.click();
  URL.revokeObjectURL(link.href);
});

refreshStatus().catch((error) => {
  initPill.textContent = "状态错误";
  initPill.className = "pill warn";
  showTransientError(error, "dashboard");
});

refreshDbDirs().catch(() => {});
loadProfile().catch(() => {
  if (profileName) profileName.textContent = "本机微信";
});
