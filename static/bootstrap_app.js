const styleSelectEl = document.getElementById("style-select");
const languageSelectEl = document.getElementById("language-select");

const STYLE_STORAGE_KEY = "coauthors_style";
const LANG_STORAGE_KEY = "coauthors_lang";
const SUPPORTED_STYLES = new Set(["hotcrp", "journal", "nordic", "campus", "folio", "slate"]);
const SUPPORTED_LANGS = new Set(["en", "zh"]);
let currentLang = "en";

const I18N = {
  en: {
    page_title_bootstrap: "CoAuthors Bootstrap Console",
    nav_user: "User Page",
    nav_console: "Advanced Console",
    nav_bootstrap: "Bootstrap Console",
    control_style: "Style",
    control_language: "Language",
    lang_en: "English",
    lang_zh: "Chinese",
    bootstrap_title: "CoAuthors Bootstrap Console",
    bootstrap_subtitle:
      "Download XML/DTD, decompress XML, and build DBLP SQLite through the web.",
    bootstrap_params_title: "Task Parameters",
    bootstrap_mode: "Build Mode",
    bootstrap_xml_url: "XML.GZ URL",
    bootstrap_dtd_url: "DTD URL",
    bootstrap_batch: "Batch Size",
    bootstrap_progress_every: "Progress Every",
    bootstrap_rebuild: "Rebuild database (remove existing sqlite/wal/shm)",
    bootstrap_start: "Start",
    bootstrap_stop: "Stop",
    bootstrap_reset: "Reset",
    bootstrap_runtime: "Runtime Status",
    bootstrap_progress: "Progress",
    bootstrap_output_files: "Output Files",
    bootstrap_logs: "Live Logs",
    runtime_status: "Status",
    runtime_step: "Step",
    runtime_mode: "Mode",
    runtime_message: "Message",
    runtime_started: "Started",
    runtime_finished: "Finished",
    progress_downloaded: "Downloaded",
    progress_total: "Total",
    progress_xml_written: "XML Written",
    progress_records: "Processed Records",
    progress_rate: "Rate",
    progress_data_dir: "Data Dir",
    table_file: "File",
    table_exists: "Exists",
    table_size: "Size",
    table_path: "Path",
    yes: "yes",
    no: "no",
    msg_refresh_failed: "Refresh failed: {err}",
    msg_start_failed: "Start failed: {err}",
    msg_stop_failed: "Stop failed: {err}",
    msg_reset_failed: "Reset failed: {err}",
    footer_title: "Project Information",
    footer_dev_label: "Developer",
    footer_dev_value: "Nankai University AOSP Laboratory",
    footer_maintainer_label: "Maintainer",
    footer_maintainer_value: "Nankai University AOSP Laboratory",
    footer_version_label: "Version",
    footer_features_label: "Current Features",
    footer_features_value:
      "Coauthor matrix, pair publications, metadata output, bootstrap build pipeline.",
    footer_license_label: "License",
  },
  zh: {
    page_title_bootstrap: "CoAuthors 建库控制台",
    nav_user: "用户页面",
    nav_console: "高级控制台",
    nav_bootstrap: "建库控制台",
    control_style: "页面风格",
    control_language: "语言",
    lang_en: "英文",
    lang_zh: "中文",
    bootstrap_title: "CoAuthors 建库控制台",
    bootstrap_subtitle: "通过 Web 页面完成 XML/DTD 下载、XML 解压与 DBLP SQLite 建库。",
    bootstrap_params_title: "任务参数",
    bootstrap_mode: "构建模式",
    bootstrap_xml_url: "XML.GZ 地址",
    bootstrap_dtd_url: "DTD 地址",
    bootstrap_batch: "批处理大小",
    bootstrap_progress_every: "进度上报间隔",
    bootstrap_rebuild: "重建数据库（删除已有 sqlite/wal/shm）",
    bootstrap_start: "开始",
    bootstrap_stop: "停止",
    bootstrap_reset: "重置",
    bootstrap_runtime: "运行状态",
    bootstrap_progress: "进度",
    bootstrap_output_files: "输出文件",
    bootstrap_logs: "实时日志",
    runtime_status: "状态",
    runtime_step: "步骤",
    runtime_mode: "模式",
    runtime_message: "消息",
    runtime_started: "开始时间",
    runtime_finished: "结束时间",
    progress_downloaded: "已下载",
    progress_total: "总大小",
    progress_xml_written: "XML 写入",
    progress_records: "处理记录数",
    progress_rate: "速率",
    progress_data_dir: "数据目录",
    table_file: "文件",
    table_exists: "是否存在",
    table_size: "大小",
    table_path: "路径",
    yes: "是",
    no: "否",
    msg_refresh_failed: "刷新失败：{err}",
    msg_start_failed: "启动失败：{err}",
    msg_stop_failed: "停止失败：{err}",
    msg_reset_failed: "重置失败：{err}",
    footer_title: "项目信息",
    footer_dev_label: "开发团队",
    footer_dev_value: "南开大学 AOSP 实验室",
    footer_maintainer_label: "维护团队",
    footer_maintainer_value: "南开大学 AOSP 实验室",
    footer_version_label: "版本",
    footer_features_label: "当前特性",
    footer_features_value: "共作矩阵、配对论文列表、元数据输出、建库流水线。",
    footer_license_label: "开源协议",
  },
};

function t(key, vars = {}) {
  const langPack = I18N[currentLang] || I18N.en;
  const template = langPack[key] ?? I18N.en[key] ?? key;
  return template.replace(/\{(\w+)\}/g, (_, name) => String(vars[name] ?? `{${name}}`));
}

function fmtBytes(bytes) {
  if (typeof bytes !== "number" || Number.isNaN(bytes)) return "-";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let idx = 0;
  let val = bytes;
  while (val >= 1024 && idx < units.length - 1) {
    val /= 1024;
    idx += 1;
  }
  return `${val.toFixed(idx === 0 ? 0 : 2)} ${units[idx]}`;
}

function applyStyle(style) {
  const nextStyle = SUPPORTED_STYLES.has(style) ? style : "campus";
  document.body.dataset.style = nextStyle;
  if (styleSelectEl && styleSelectEl.value !== nextStyle) {
    styleSelectEl.value = nextStyle;
  }
  try {
    window.localStorage.setItem(STYLE_STORAGE_KEY, nextStyle);
  } catch (_) {}
}

function initStyle() {
  let initialStyle = "campus";
  try {
    const savedStyle = window.localStorage.getItem(STYLE_STORAGE_KEY);
    if (savedStyle && SUPPORTED_STYLES.has(savedStyle)) {
      initialStyle = savedStyle;
    }
  } catch (_) {}

  applyStyle(initialStyle);
  if (styleSelectEl) {
    styleSelectEl.addEventListener("change", (event) => applyStyle(event.target.value));
  }
}

function applyLanguage(lang) {
  currentLang = SUPPORTED_LANGS.has(lang) ? lang : "en";
  document.documentElement.lang = currentLang === "zh" ? "zh-CN" : "en";
  if (languageSelectEl && languageSelectEl.value !== currentLang) {
    languageSelectEl.value = currentLang;
  }

  try {
    window.localStorage.setItem(LANG_STORAGE_KEY, currentLang);
  } catch (_) {}

  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (!key) return;
    if (el.tagName === "TITLE") {
      document.title = t(key);
      return;
    }
    el.textContent = t(key);
  });
}

function initLanguage() {
  let initialLang = "en";
  try {
    const savedLang = window.localStorage.getItem(LANG_STORAGE_KEY);
    if (savedLang && SUPPORTED_LANGS.has(savedLang)) {
      initialLang = savedLang;
    }
  } catch (_) {}

  applyLanguage(initialLang);
  if (languageSelectEl) {
    languageSelectEl.addEventListener("change", (event) => {
      applyLanguage(event.target.value);
      refreshAll();
    });
  }
}

async function fetchJson(url, options = {}) {
  const resp = await fetch(url, options);
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new Error(data.detail || `HTTP ${resp.status}`);
  }
  return data;
}

function fillText(id, value) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = value ?? "-";
}

function updateState(state) {
  fillText("status", state.status);
  fillText("step", state.step);
  fillText("mode-val", state.mode);
  fillText("message", state.message || "-");
  fillText("started-at", state.started_at || "-");
  fillText("finished-at", state.finished_at || "-");

  const p = state.progress || {};
  fillText("downloaded-bytes", fmtBytes(p.downloaded_bytes));
  fillText("total-bytes", fmtBytes(p.total_bytes));
  fillText("written-bytes", fmtBytes(p.written_bytes));
  fillText("processed-records", p.processed_records ?? "-");
  fillText("records-rate", p.records_per_sec !== undefined ? `${p.records_per_sec} rec/s` : "-");

  const logs = Array.isArray(state.logs) ? state.logs : [];
  const logBox = document.getElementById("logs");
  if (logBox) {
    logBox.textContent = logs.join("\n");
    logBox.scrollTop = logBox.scrollHeight;
  }
}

function updateFiles(data) {
  fillText("data-dir", data.data_dir || "-");
  const tbody = document.getElementById("file-table");
  if (!tbody) return;
  tbody.innerHTML = "";

  const files = data.files || {};
  for (const [name, info] of Object.entries(files)) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${name}</td>
      <td>${info.exists ? t("yes") : t("no")}</td>
      <td>${fmtBytes(info.size_bytes || 0)}</td>
      <td><code>${info.path || "-"}</code></td>
    `;
    tbody.appendChild(tr);
  }
}

async function refreshAll() {
  try {
    const [state, files] = await Promise.all([fetchJson("/api/state"), fetchJson("/api/files")]);
    updateState(state);
    updateFiles(files);
  } catch (err) {
    fillText("message", t("msg_refresh_failed", { err: err.message }));
  }
}

const startFormEl = document.getElementById("start-form");
if (startFormEl) {
  startFormEl.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const payload = {
      mode: document.getElementById("mode")?.value,
      xml_gz_url: document.getElementById("xml-gz-url")?.value?.trim(),
      dtd_url: document.getElementById("dtd-url")?.value?.trim(),
      rebuild: Boolean(document.getElementById("rebuild")?.checked),
      batch_size: Number(document.getElementById("batch-size")?.value || 1000),
      progress_every: Number(document.getElementById("progress-every")?.value || 10000),
    };

    try {
      await fetchJson("/api/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      await refreshAll();
    } catch (err) {
      fillText("message", t("msg_start_failed", { err: err.message }));
    }
  });
}

const stopBtnEl = document.getElementById("stop-btn");
if (stopBtnEl) {
  stopBtnEl.addEventListener("click", async () => {
    try {
      await fetchJson("/api/stop", { method: "POST" });
      await refreshAll();
    } catch (err) {
      fillText("message", t("msg_stop_failed", { err: err.message }));
    }
  });
}

const resetBtnEl = document.getElementById("reset-btn");
if (resetBtnEl) {
  resetBtnEl.addEventListener("click", async () => {
    try {
      await fetchJson("/api/reset", { method: "POST" });
      await refreshAll();
    } catch (err) {
      fillText("message", t("msg_reset_failed", { err: err.message }));
    }
  });
}

initStyle();
initLanguage();
refreshAll();
setInterval(refreshAll, 2000);
