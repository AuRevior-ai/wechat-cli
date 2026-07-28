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

let lastText = "";
let lastKeyText = "";
let lastDownload = null;
let dbDirCandidates = [];

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

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function setScreen(id) {
  screens.forEach((screen) => screen.classList.toggle("active", screen.id === id));
  nav.querySelectorAll("button").forEach((button) => {
    button.classList.toggle("active", button.dataset.target === id);
  });
  const active = document.getElementById(id);
  title.textContent = active?.dataset.title || "WeChat CLI Web";
  if (id === "setup" && dbDirCandidates.length === 0) {
    refreshDbDirs().catch(showTransientError);
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
    params.media = true;
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
  if (payload.command !== "search") return "";
  const params = payload.params || {};
  if (params.keyword) return "";
  if (params.start_time && params.end_time) return "";
  return "关键词为空时，必须同时填写开始时间和结束时间。";
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok && payload.ok !== false) {
    payload.ok = false;
  }
  return payload;
}

async function refreshStatus() {
  const status = await fetchJson("/api/status");
  initPill.textContent = status.initialized ? `已初始化 · ${status.keys_count} keys` : "未初始化";
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

function showTransientError(error) {
  lastKeyText = "";
  copyKeyButton.classList.add("hidden");
  result.className = "result error";
  result.innerHTML = `<pre>${escapeHtml(error.message)}</pre>`;
}

function renderKeyValue(obj, mode = "div") {
  const entries = Object.entries(obj || {});
  if (mode === "dl") {
    return entries.map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(formatScalar(value))}</dd>`).join("");
  }
  return `<div class="kv">${entries.map(([key, value]) => (
    `<div>${escapeHtml(key)}</div><div>${escapeHtml(formatScalar(value))}</div>`
  )).join("")}</div>`;
}

function formatScalar(value) {
  if (value === null || value === undefined) return "";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
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
        "类型分布": Object.entries(data.type_breakdown || {}).map(([k, v]) => `${k}: ${v}`).join(" / "),
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

function mediaUrl(media) {
  if (!media || typeof media !== "object") return "";
  if (media.url && isSafeImageUrl(media.url)) return media.url;
  if (media.path) return `/api/media?path=${encodeURIComponent(media.path)}`;
  return "";
}

function renderAvatar(item, label) {
  const url = item?.sender_avatar_url || item?.avatar_url || item?.chat_avatar_url || "";
  if (url && isSafeImageUrl(url)) {
    return `<img class="avatar-img" src="${escapeHtml(url)}" alt="${escapeHtml(label || "头像")}" loading="lazy" referrerpolicy="no-referrer">`;
  }
  const initial = String(label || "W").trim().slice(0, 1).toUpperCase() || "W";
  return `<span class="avatar-fallback" aria-hidden="true">${escapeHtml(initial)}</span>`;
}

function renderMessageMedia(item) {
  const media = item?.media;
  if (!media || typeof media !== "object") return "";
  const src = mediaUrl(media);
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

function renderChatMessages(items) {
  if (!items.length) return `<div class="empty">没有消息。</div>`;
  return `<div class="chat-list">${items.map((item) => {
    const sender = item.sender || item.chat || "消息";
    const type = TYPE_LABELS[item.type] || item.type_label || item.type || "消息";
    return `<article class="message-row ${item.is_self ? "mine" : ""}">
      ${renderAvatar(item, sender)}
      <div class="message-main">
        <div class="message-meta">
          <strong>${escapeHtml(sender)}</strong>
          <span>${escapeHtml(item.time || "")}</span>
          <em>${escapeHtml(type)}</em>
        </div>
        <div class="message-bubble">
          <p>${escapeHtml(item.text || "")}</p>
          ${renderMessageMedia(item)}
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
    const meta = [item.time, item.type, item.msg_type, item.is_group ? "群聊" : "", item.unread ? `${item.unread} 条未读` : ""]
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

function setResult(payload) {
  const output = payload.stdout || payload.stderr || payload.error || "";
  const text = payload.data ? JSON.stringify(payload.data, null, 2) : output;
  lastText = text || JSON.stringify(payload, null, 2);
  lastKeyText = keyCopyText(payload);
  lastDownload = null;
  copyKeyButton.classList.toggle("hidden", !lastKeyText);
  result.className = `result ${payload.ok ? "" : "error"}`;
  commandPreview.textContent = payload.command ? payload.command.join(" ") : "请求失败";

  if (!payload.ok) {
    result.innerHTML = `<pre>${escapeHtml(output || payload.error || "操作失败")}</pre>`;
    downloadButton.classList.add("hidden");
    return;
  }

  if (payload.data) {
    result.innerHTML = renderData(payload.data);
    if (payload.command?.[1] === "invite-stats") {
      lastDownload = {
        text: inviteCsv(payload.data),
        filename: "wechat-invite-stats.csv",
      };
      downloadButton.classList.remove("hidden");
    } else {
      downloadButton.classList.add("hidden");
    }
    return;
  }

  result.innerHTML = `<pre>${escapeHtml(output)}</pre>`;
  if (payload.command?.[1] === "export" && output) {
    lastDownload = {
      text: output,
      filename: payload.command.includes("txt") ? "wechat-export.txt" : "wechat-export.md",
    };
    downloadButton.classList.remove("hidden");
  } else {
    downloadButton.classList.add("hidden");
  }
}

async function runForm(form) {
  if (!form.reportValidity()) return;
  const payload = readForm(form);
  const validationError = validatePayload(payload);
  if (validationError) {
    result.className = "result error";
    result.innerHTML = `<pre>${escapeHtml(validationError)}</pre>`;
    commandPreview.textContent = "表单校验失败";
    lastKeyText = "";
    copyKeyButton.classList.add("hidden");
    downloadButton.classList.add("hidden");
    return;
  }
  result.className = "result empty";
  result.textContent = "执行中...";
  commandPreview.textContent = `${payload.command} ${JSON.stringify(payload.params)}`;
  lastKeyText = "";
  copyKeyButton.classList.add("hidden");
  downloadButton.classList.add("hidden");
  const response = await fetchJson("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  setResult(response);
  if (payload.command === "init") {
    await refreshStatus();
  }
}

nav.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-target]");
  if (button) setScreen(button.dataset.target);
});

document.querySelectorAll("[data-jump]").forEach((button) => {
  button.addEventListener("click", () => setScreen(button.dataset.jump));
});

document.querySelectorAll(".tool-form").forEach((form) => {
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    runForm(form);
  });
});

document.querySelectorAll("[data-action='refresh-status'], #refresh-status").forEach((button) => {
  button.addEventListener("click", refreshStatus);
});

if (detectDbDirsButton) {
  detectDbDirsButton.addEventListener("click", () => {
    refreshDbDirs().catch(showTransientError);
  });
}

if (dbDirSelect && setupDbDirInput) {
  dbDirSelect.addEventListener("change", () => {
    if (dbDirSelect.value) {
      setupDbDirInput.value = dbDirSelect.value;
    }
  });
}

copyButton.addEventListener("click", async () => {
  if (!lastText) return;
  await navigator.clipboard.writeText(lastText);
  copyButton.textContent = "已复制";
  setTimeout(() => { copyButton.textContent = "复制"; }, 1000);
});

copyKeyButton.addEventListener("click", async () => {
  if (!lastKeyText) return;
  await navigator.clipboard.writeText(lastKeyText);
  copyKeyButton.textContent = "已复制关键信息";
  setTimeout(() => { copyKeyButton.textContent = "复制关键信息"; }, 1000);
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
  result.className = "result error";
  result.innerHTML = `<pre>${escapeHtml(error.message)}</pre>`;
});

refreshDbDirs().catch(() => {});
