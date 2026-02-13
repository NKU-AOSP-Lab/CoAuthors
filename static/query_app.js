const healthStatusEl = document.getElementById("health-status");
const dataSourceEl = document.getElementById("data-source");
const dataDateEl = document.getElementById("data-date");
const kpiPubsEl = document.getElementById("kpi-pubs");
const kpiAuthorsEl = document.getElementById("kpi-authors");

const pairsMsgEl = document.getElementById("pairs-msg");
const matrixHeadEl = document.getElementById("matrix-head");
const matrixBodyEl = document.getElementById("matrix-body");
const pairSelectorEl = document.getElementById("pair-selector");
const pairPubsBodyEl = document.getElementById("pair-pubs-body");
const pairsFormEl = document.getElementById("pairs-form");
const loadingBoxEl = document.getElementById("pairs-loading");
const loadingTextEl = document.getElementById("pairs-loading-text");
const loadingElapsedEl = document.getElementById("pairs-loading-elapsed");

const styleSelectEl = document.getElementById("style-select");
const languageSelectEl = document.getElementById("language-select");
const isConsolePage = document.body?.dataset.page === "console";

let latestPairPubs = [];
let loadingTimer = null;
let loadingStartedAt = 0;
let healthState = "checking";

const STYLE_STORAGE_KEY = "coauthors_style";
const LANG_STORAGE_KEY = "coauthors_lang";
const SUPPORTED_STYLES = new Set(["hotcrp", "journal", "nordic", "campus", "folio", "slate"]);
const SUPPORTED_LANGS = new Set(["en", "zh"]);
let currentLang = "en";

const I18N = {
  en: {
    page_title_user: "CoAuthors Coauthorship Query",
    page_title_console: "CoAuthors Advanced Console",
    hero_user_title: "CoAuthors Coauthorship Query",
    hero_user_subtitle:
      "Enter two author sets to find coauthored pairs and publication metadata.",
    hero_console_title: "CoAuthors Advanced Console",
    hero_console_subtitle:
      "For experiments and tuning: configure advanced options for batch coauthor queries.",
    nav_user: "User Page",
    nav_console: "Advanced Console",
    nav_bootstrap: "Bootstrap Console",
    control_style: "Style",
    control_language: "Language",
    lang_en: "English",
    lang_zh: "Chinese",
    status_title: "System Status",
    status_service: "Service",
    status_source: "Data Source",
    status_date: "Data Date",
    status_checking: "Checking",
    status_ok: "OK",
    status_error: "ERROR",
    stats_title: "Data Scale",
    stats_publications: "Publications",
    stats_authors: "Authors",
    query_title_user: "Coauthorship Matching",
    query_hint_user:
      "One author per line. If an input contains an organization (e.g., `Yann LeCun (New York University)`), it will be stripped automatically.",
    query_left_user: "Author Set A (one per line)",
    query_right_user: "Author Set B (one per line)",
    query_button_user: "Start Matching",
    query_title_console: "coauthored_pairs Query",
    query_hint_console:
      "If an input contains an organization (e.g., `Yann LeCun (New York University)`), it will be stripped automatically.",
    query_left_console: "Left Authors (one per line)",
    query_right_console: "Right Authors (one per line)",
    query_limit_per_pair: "limit_per_pair (optional, empty = unlimited)",
    query_author_limit: "author_limit (optional, empty = unlimited)",
    query_exact_base: "exact_base_match = true",
    query_button_console: "Run coauthored_pairs",
    matrix_title_user: "Coauthorship Matrix",
    matrix_title_console: "Matrix",
    pubs_title_user: "Coauthored Publications",
    pubs_title_console: "Pair Publications",
    pair_selector_user: "Select Pair",
    pair_selector_console: "Select Pair",
    table_title: "Title",
    table_year: "Year",
    table_venue: "Venue",
    table_type: "Type",
    placeholder_left: "Geoffrey Hinton\nYann LeCun (New York University)",
    placeholder_right: "Andrew Y. Ng\nYoshua Bengio (Universite de Montreal)",
    placeholder_unlimited: "Unlimited",
    loading_default: "Matching...",
    matrix_left_right: "LEFT \\ RIGHT",
    matrix_count_header: "Coauthored Count",
    no_coauthored_pairs: "No coauthored pairs",
    no_publications: "No publications",
    msg_require_both_user: "Please enter at least one author on both sides.",
    msg_require_both_console: "Both left and right author lists are required.",
    msg_matching_user: "Matching {n} author pairs...",
    msg_matching_console: "Matching {n} pairs...",
    msg_completed_user: "Completed: found {n} coauthored pairs.",
    msg_completed_console:
      "Completed {n} coauthored pairs (mode={mode}, limit_per_pair={limit}).",
    msg_query_failed: "Query failed: {err}",
    elapsed: "Elapsed",
    unlimited: "unlimited",
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
    page_title_user: "CoAuthors 共作查询",
    page_title_console: "CoAuthors 高级控制台",
    hero_user_title: "CoAuthors 共作查询系统",
    hero_user_subtitle: "输入两组作者姓名，返回存在共作关系的作者对与论文元数据。",
    hero_console_title: "CoAuthors 高级控制台",
    hero_console_subtitle: "面向实验与调参：可配置高级参数进行批量共作检索。",
    nav_user: "用户页面",
    nav_console: "高级控制台",
    nav_bootstrap: "建库控制台",
    control_style: "页面风格",
    control_language: "语言",
    lang_en: "英文",
    lang_zh: "中文",
    status_title: "系统状态",
    status_service: "服务",
    status_source: "数据来源",
    status_date: "数据日期",
    status_checking: "检测中",
    status_ok: "正常",
    status_error: "异常",
    stats_title: "数据规模",
    stats_publications: "论文数",
    stats_authors: "作者数",
    query_title_user: "作者共作匹配",
    query_hint_user:
      "每行输入一个作者。若包含机构信息（如 `Yann LeCun (New York University)`），系统会自动剔除括号内容。",
    query_left_user: "作者集合 A（每行一个）",
    query_right_user: "作者集合 B（每行一个）",
    query_button_user: "开始匹配",
    query_title_console: "coauthored_pairs 查询",
    query_hint_console:
      "若输入包含机构信息（如 `Yann LeCun (New York University)`），系统会自动剔除括号内容。",
    query_left_console: "左侧作者（每行一个）",
    query_right_console: "右侧作者（每行一个）",
    query_limit_per_pair: "limit_per_pair（可选，留空为不限制）",
    query_author_limit: "author_limit（可选，留空为不限制）",
    query_exact_base: "exact_base_match = true",
    query_button_console: "执行 coauthored_pairs",
    matrix_title_user: "共作矩阵",
    matrix_title_console: "矩阵",
    pubs_title_user: "共作论文列表",
    pubs_title_console: "配对论文列表",
    pair_selector_user: "选择作者对",
    pair_selector_console: "选择作者对",
    table_title: "标题",
    table_year: "年份",
    table_venue: "会议/期刊",
    table_type: "类型",
    placeholder_left: "Geoffrey Hinton\nYann LeCun (New York University)",
    placeholder_right: "Andrew Y. Ng\nYoshua Bengio (Universite de Montreal)",
    placeholder_unlimited: "不限制",
    loading_default: "匹配中...",
    matrix_left_right: "左侧 \\ 右侧",
    matrix_count_header: "共作数量",
    no_coauthored_pairs: "没有共作作者对",
    no_publications: "没有论文",
    msg_require_both_user: "请在两侧都输入至少一个作者姓名。",
    msg_require_both_console: "左右作者列表都不能为空。",
    msg_matching_user: "正在匹配 {n} 个作者对...",
    msg_matching_console: "正在匹配 {n} 个配对...",
    msg_completed_user: "匹配完成：共找到 {n} 个有共作关系的作者对。",
    msg_completed_console: "完成：共找到 {n} 个共作配对（mode={mode}, limit_per_pair={limit}）。",
    msg_query_failed: "查询失败：{err}",
    elapsed: "耗时",
    unlimited: "不限制",
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

function fmtNum(value) {
  if (typeof value !== "number") return "-";
  return new Intl.NumberFormat("en-US").format(value);
}

function parseLines(text) {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
}

function normalizeText(text) {
  return String(text || "")
    .trim()
    .replace(/\s+/g, " ");
}

function parseAuthorEntry(entry) {
  let text = normalizeText(entry);
  for (const sep of ["||", "|", "::", "\t"]) {
    if (text.includes(sep)) {
      text = normalizeText(text.split(sep, 1)[0]);
      break;
    }
  }

  while (text.endsWith(")") && text.includes(" (")) {
    const splitIndex = text.lastIndexOf(" (");
    const suffix = text.slice(splitIndex + 2, -1);
    if (!normalizeText(suffix)) {
      break;
    }
    text = normalizeText(text.slice(0, splitIndex));
  }
  return text;
}

function sanitizeAuthorEntries(entries) {
  const cleaned = [];
  const seen = new Set();
  for (const entry of entries) {
    const normalized = parseAuthorEntry(entry);
    if (!normalized || seen.has(normalized)) continue;
    seen.add(normalized);
    cleaned.push(normalized);
  }
  return cleaned;
}

function showMsg(message, isError = false) {
  if (!pairsMsgEl) return;
  pairsMsgEl.textContent = message;
  pairsMsgEl.classList.toggle("error", isError);
}

function clearNode(node) {
  if (!node) return;
  while (node.firstChild) {
    node.removeChild(node.firstChild);
  }
}

function appendTextCell(row, text, className = "") {
  const cell = document.createElement("td");
  cell.textContent = text ?? "";
  if (className) cell.className = className;
  row.appendChild(cell);
  return cell;
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

  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    const key = el.getAttribute("data-i18n-placeholder");
    if (!key) return;
    el.setAttribute("placeholder", t(key));
  });

  setHealthStatus(healthState);
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
    languageSelectEl.addEventListener("change", (event) => applyLanguage(event.target.value));
  }
}

function formatElapsed(seconds) {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${s}s`;
}

function setHealthStatus(state) {
  healthState = state;
  if (!healthStatusEl) return;

  if (state === "ok") {
    healthStatusEl.textContent = t("status_ok");
    healthStatusEl.className = "chip chip-ok";
  } else if (state === "error") {
    healthStatusEl.textContent = t("status_error");
    healthStatusEl.className = "chip chip-error";
  } else {
    healthStatusEl.textContent = t("status_checking");
    healthStatusEl.className = "chip chip-warn";
  }
}

function setQueryLoading(isLoading, totalPairs = 0) {
  if (!loadingBoxEl || !pairsFormEl || !loadingTextEl || !loadingElapsedEl) return;

  if (isLoading) {
    if (loadingTimer) clearInterval(loadingTimer);

    loadingStartedAt = Date.now();
    loadingBoxEl.classList.add("is-active");
    pairsFormEl.classList.add("is-loading");
    loadingTextEl.textContent = isConsolePage
      ? t("msg_matching_console", { n: fmtNum(totalPairs) })
      : t("msg_matching_user", { n: fmtNum(totalPairs) });
    loadingElapsedEl.textContent = `${t("elapsed")} 0s`;

    pairsFormEl.querySelectorAll("textarea, input, select, button").forEach((el) => {
      el.disabled = true;
    });

    loadingTimer = setInterval(() => {
      const seconds = Math.max(0, Math.floor((Date.now() - loadingStartedAt) / 1000));
      loadingElapsedEl.textContent = `${t("elapsed")} ${formatElapsed(seconds)}`;
    }, 500);
    return;
  }

  if (loadingTimer) {
    clearInterval(loadingTimer);
    loadingTimer = null;
  }

  loadingBoxEl.classList.remove("is-active");
  pairsFormEl.classList.remove("is-loading");
  loadingElapsedEl.textContent = "";
  pairsFormEl.querySelectorAll("textarea, input, select, button").forEach((el) => {
    el.disabled = false;
  });
}

async function fetchJson(url, options = {}) {
  const resp = await fetch(url, options);
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
  return data;
}

function renderMatrix(leftAuthors, rightAuthors, matrix) {
  clearNode(matrixHeadEl);
  clearNode(matrixBodyEl);
  if (!matrixHeadEl || !matrixBodyEl) return;

  const visibleRightAuthors = rightAuthors.filter((right) =>
    leftAuthors.some((left) => ((matrix[left] || {})[right] ?? 0) > 0)
  );
  const visibleLeftAuthors = leftAuthors.filter((left) =>
    visibleRightAuthors.some((right) => ((matrix[left] || {})[right] ?? 0) > 0)
  );

  if (visibleLeftAuthors.length === 0 || visibleRightAuthors.length === 0) {
    const headerRow = document.createElement("tr");
    const h1 = document.createElement("th");
    h1.textContent = t("matrix_left_right");
    const h2 = document.createElement("th");
    h2.textContent = t("matrix_count_header");
    headerRow.appendChild(h1);
    headerRow.appendChild(h2);
    matrixHeadEl.appendChild(headerRow);

    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 2;
    cell.textContent = t("no_coauthored_pairs");
    row.appendChild(cell);
    matrixBodyEl.appendChild(row);
    return;
  }

  const headerRow = document.createElement("tr");
  const leftHeader = document.createElement("th");
  leftHeader.textContent = t("matrix_left_right");
  headerRow.appendChild(leftHeader);

  for (const right of visibleRightAuthors) {
    const th = document.createElement("th");
    th.textContent = right;
    headerRow.appendChild(th);
  }
  matrixHeadEl.appendChild(headerRow);

  for (const left of visibleLeftAuthors) {
    const row = document.createElement("tr");
    appendTextCell(row, left, "name-cell");

    const rowValues = matrix[left] || {};
    for (const right of visibleRightAuthors) {
      const value = rowValues[right] ?? 0;
      appendTextCell(row, value > 0 ? String(value) : "", value > 0 ? "count-hot" : "");
    }
    matrixBodyEl.appendChild(row);
  }
}

function renderPairPubs(items) {
  clearNode(pairPubsBodyEl);
  if (!pairPubsBodyEl) return;

  if (!items || items.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");
    cell.colSpan = 4;
    cell.textContent = t("no_publications");
    row.appendChild(cell);
    pairPubsBodyEl.appendChild(row);
    return;
  }

  for (const item of items) {
    const row = document.createElement("tr");
    appendTextCell(row, item.title ?? "");
    appendTextCell(row, item.year ?? "");
    appendTextCell(row, item.venue ?? "");
    appendTextCell(row, item.pub_type ?? "");
    pairPubsBodyEl.appendChild(row);
  }
}

function renderPairSelector(pairPubs) {
  latestPairPubs = (pairPubs || []).filter((pair) => (pair.count ?? 0) > 0);
  clearNode(pairSelectorEl);
  if (!pairSelectorEl) return;

  if (latestPairPubs.length === 0) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = t("no_coauthored_pairs");
    pairSelectorEl.appendChild(option);
    renderPairPubs([]);
    return;
  }

  latestPairPubs.forEach((pair, idx) => {
    const option = document.createElement("option");
    option.value = String(idx);
    option.textContent = `${pair.left} x ${pair.right} (${pair.count})`;
    pairSelectorEl.appendChild(option);
  });

  pairSelectorEl.value = "0";
  renderPairPubs(latestPairPubs[0].items);
}

if (pairSelectorEl) {
  pairSelectorEl.addEventListener("change", () => {
    const idx = Number(pairSelectorEl.value);
    if (!Number.isFinite(idx) || idx < 0 || idx >= latestPairPubs.length) {
      renderPairPubs([]);
      return;
    }
    renderPairPubs(latestPairPubs[idx].items);
  });
}

async function loadHealth() {
  try {
    await fetchJson("/api/health");
    setHealthStatus("ok");
  } catch (_) {
    setHealthStatus("error");
  }
}

async function loadStats() {
  if (!kpiPubsEl || !kpiAuthorsEl) return;
  try {
    const data = await fetchJson("/api/stats");
    kpiPubsEl.textContent = fmtNum(data.publications);
    kpiAuthorsEl.textContent = fmtNum(data.authors);
    if (dataSourceEl) dataSourceEl.textContent = data.data_source || "DBLP";
    if (dataDateEl) dataDateEl.textContent = data.data_date || "-";
  } catch (_) {
    kpiPubsEl.textContent = "-";
    kpiAuthorsEl.textContent = "-";
    if (dataSourceEl) dataSourceEl.textContent = "DBLP";
    if (dataDateEl) dataDateEl.textContent = "-";
  }
}

if (pairsFormEl) {
  pairsFormEl.addEventListener("submit", async (event) => {
    event.preventDefault();

    const leftRaw = parseLines(document.getElementById("left-authors")?.value || "");
    const rightRaw = parseLines(document.getElementById("right-authors")?.value || "");
    const left = sanitizeAuthorEntries(leftRaw);
    const right = sanitizeAuthorEntries(rightRaw);
    const limitPerPairRaw = (document.getElementById("limit-per-pair")?.value || "").trim();
    const authorLimitRaw = (document.getElementById("author-limit")?.value || "").trim();
    const exactBaseMatchEl = document.getElementById("exact-base-match");
    const exactBaseMatch = exactBaseMatchEl ? Boolean(exactBaseMatchEl.checked) : true;

    if (left.length === 0 || right.length === 0) {
      showMsg(isConsolePage ? t("msg_require_both_console") : t("msg_require_both_user"), true);
      return;
    }

    const totalPairs = left.length * right.length;
    const payload = { left, right, exact_base_match: exactBaseMatch };

    if (limitPerPairRaw) {
      const limitPerPair = Number(limitPerPairRaw);
      if (Number.isFinite(limitPerPair) && limitPerPair > 0) payload.limit_per_pair = limitPerPair;
    }
    if (authorLimitRaw) {
      const authorLimit = Number(authorLimitRaw);
      if (Number.isFinite(authorLimit) && authorLimit > 0) payload.author_limit = authorLimit;
    }

    setQueryLoading(true, totalPairs);
    showMsg(
      isConsolePage
        ? t("msg_matching_console", { n: fmtNum(totalPairs) })
        : t("msg_matching_user", { n: fmtNum(totalPairs) })
    );

    try {
      const data = await fetchJson("/api/coauthors/pairs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      renderMatrix(data.left_authors || [], data.right_authors || [], data.matrix || {});
      renderPairSelector(data.pair_pubs || []);

      const coauthoredPairCount = (data.pair_pubs || []).filter((pair) => (pair.count ?? 0) > 0)
        .length;

      if (isConsolePage) {
        const limitText = data.limit_per_pair == null ? t("unlimited") : String(data.limit_per_pair);
        showMsg(
          t("msg_completed_console", {
            n: coauthoredPairCount,
            mode: data.mode,
            limit: limitText,
          })
        );
      } else {
        showMsg(t("msg_completed_user", { n: fmtNum(coauthoredPairCount) }));
      }
    } catch (err) {
      clearNode(matrixHeadEl);
      clearNode(matrixBodyEl);
      renderPairSelector([]);
      showMsg(t("msg_query_failed", { err: err.message }), true);
    } finally {
      setQueryLoading(false);
    }
  });
}

initStyle();
initLanguage();
loadHealth();
loadStats();
