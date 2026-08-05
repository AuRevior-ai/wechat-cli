(() => {
  "use strict";

  const byId = (id) => document.getElementById(id);
  const title = byId("title");
  const message = byId("message");
  const activationForm = byId("activation-form");
  const licenseKey = byId("license-key");
  const deviceName = byId("device-name");
  const details = byId("details");
  const error = byId("error");
  const progressWrap = byId("progress-wrap");
  const progress = byId("progress");
  const progressLabel = byId("progress-label");
  const retryValidation = byId("retry-validation");
  const retryUpdate = byId("retry-update");
  const startApplication = byId("start-application");
  const openLogs = byId("open-logs");
  const closeLauncher = byId("close-launcher");

  const stateTitles = {
    initializing: "正在初始化",
    activation_required: "激活 WeChat CLI Web",
    validating: "正在验证许可证",
    ready: "准备启动",
    offline_valid: "离线授权可用",
    offline_expiring: "离线授权即将到期",
    blocked: "许可证验证未通过",
    installing: "正在安装更新",
    rollback: "正在恢复上一版本",
    update_failed: "更新失败，已恢复旧版本",
    activated: "激活成功"
  };

  function setHidden(element, hidden) {
    element.hidden = Boolean(hidden);
  }

  function renderDetails(state) {
    details.replaceChildren();
    const rows = [
      ["许可证", state.license_hint ? `••••-${state.license_hint}` : null],
      ["当前设备", state.device_name],
      ["设备数量", Number.isInteger(state.device_count) && Number.isInteger(state.maximum_devices) ? `${state.device_count} / ${state.maximum_devices}` : null],
      ["当前版本", state.current_version],
      ["目标版本", state.target_version],
      ["离线有效期", state.offline_until],
      ["错误编号", state.error_code]
    ];
    rows.forEach(([label, value]) => {
      if (!value) return;
      const dt = document.createElement("dt");
      const dd = document.createElement("dd");
      dt.textContent = label;
      dd.textContent = String(value);
      details.append(dt, dd);
    });
  }

  function render(state) {
    const status = state.status || "initializing";
    title.textContent = state.title || stateTitles[status] || "WeChat CLI Launcher";
    message.textContent = state.message || "";
    setHidden(activationForm, status !== "activation_required");
    if (state.device_name && !deviceName.value) deviceName.value = state.device_name;

    const percentage = Number.isFinite(state.progress) ? Math.max(0, Math.min(100, Number(state.progress))) : null;
    setHidden(progressWrap, percentage === null);
    if (percentage !== null) {
      progress.style.width = `${percentage}%`;
      progress.parentElement.setAttribute("aria-valuenow", String(Math.round(percentage)));
      progressLabel.textContent = `${Math.round(percentage)}%`;
    }

    setHidden(error, !state.error_code && status !== "blocked" && status !== "update_failed");
    error.textContent = state.error_message || state.message || "";
    setHidden(retryValidation, !state.can_retry_validation);
    setHidden(retryUpdate, !state.can_retry_update);
    setHidden(startApplication, !state.can_start);
    renderDetails(state);
  }

  async function call(method, ...args) {
    const api = window.pywebview && window.pywebview.api;
    if (!api || typeof api[method] !== "function") {
      throw new Error("Launcher native bridge is unavailable");
    }
    return api[method](...args);
  }

  async function refresh() {
    try {
      render(await call("get_ui_state"));
    } catch (caught) {
      render({ status: "blocked", error_code: "UI-BRIDGE-UNAVAILABLE", message: String(caught) });
    }
  }

  activationForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const key = licenseKey.value.trim();
    const name = deviceName.value.trim();
    licenseKey.disabled = true;
    deviceName.disabled = true;
    try {
      render({ status: "validating", message: "正在激活许可证，请稍候。" });
      render(await call("activate_license", key, name));
      licenseKey.value = "";
    } catch (caught) {
      render({ status: "activation_required", error_code: "LIC-ACTIVATE-FAILED", error_message: String(caught), message: "许可证激活失败。" });
    } finally {
      licenseKey.value = "";
      licenseKey.disabled = false;
      deviceName.disabled = false;
    }
  });

  retryValidation.addEventListener("click", async () => render(await call("retry_validation")));
  retryUpdate.addEventListener("click", async () => render(await call("retry_update")));
  startApplication.addEventListener("click", async () => render(await call("start_application")));
  openLogs.addEventListener("click", () => call("open_log_folder"));
  closeLauncher.addEventListener("click", () => call("close_launcher"));

  window.addEventListener("pywebviewready", refresh, { once: true });
})();
