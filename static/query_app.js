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

const languageSelectEl = document.getElementById("language-select");
const sidebarEl = document.getElementById("sidebar");
const sidebarToggleEl = document.getElementById("sidebar-toggle");
const sidebarOverlayEl = document.getElementById("sidebar-overlay");
const yearSliderEl = document.getElementById("year-slider");
const yearSliderLabelEl = document.getElementById("year-slider-label");
const pcConflictToggleEl = document.getElementById("pc-conflict-toggle");
const rightAuthorsEl = document.getElementById("right-authors");
let latestPairPubs = [];
let loadingTimer = null;
let loadingStartedAt = 0;
let healthState = "checking";
let pcMembers = null;
let savedRightAuthors = "";

const LANG_STORAGE_KEY = "coauthors_lang";
const SUPPORTED_LANGS = new Set(["en", "zh"]);
const MAX_AUTHORS_PER_SIDE = 50;
let currentLang = "en";

const I18N = {
  en: {
    page_title_user: "CoAuthors Coauthorship Query",
    hero_user_title: "CoAuthors Coauthorship Query",
    hero_user_subtitle:
      "Enter two author sets to find coauthored pairs and publication metadata.",
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
    matrix_title_user: "Coauthorship Matrix",
    pubs_title_user: "Coauthored Publications",
    pair_selector_user: "Select Pair",
    table_title: "Title",
    table_year: "Year",
    table_venue: "Venue",
    table_type: "Type",
    query_recent_years: "Recent Years",
    query_pc_conflict: "CCS 2026 PC Conflict Check (2026/02/11)",
    year_slider_all: "All",
    year_slider_recent: "Recent {n} years (since {since})",
    placeholder_left: "Geoffrey Hinton\nYann LeCun (New York University)",
    placeholder_right: "Andrew Y. Ng\nYoshua Bengio (Universite de Montreal)",
    loading_default: "Matching...",
    matrix_left_right: "LEFT \\ RIGHT",
    matrix_count_header: "Coauthored Count",
    no_coauthored_pairs: "No coauthored pairs",
    no_publications: "No publications",
    msg_require_both: "Please enter at least one author on both sides.",
    msg_matching: "Matching {n} author pairs...",
    msg_completed: "Completed: found {n} coauthored pairs.",
    msg_query_failed: "Query failed: {err}",
    msg_too_many_authors: "Too many authors. Max {max} per side.",
    elapsed: "Elapsed",
    footer_title: "Project Information",
    footer_dev_label: "Developer",
    footer_dev_value: "Nankai University AOSP Laboratory",
    footer_maintainer_label: "Maintainer",
    footer_maintainer_value: "Nankai University AOSP Laboratory",
    footer_members_label: "Members",
    footer_members_value: "Xiang Li, Zuyao Xu, Yuqi Qiu, Fubin Wu, Fasheng Miao, Lu Sun",
    footer_version_label: "Version",
    footer_features_label: "Current Features",
    footer_features_value:
      "Coauthor matrix; pair publications;",
    footer_license_label: "License",
    footer_visits_label: "Visits",
    footer_copyright_label: "Copyright",
    footer_copyright_value: "© 2026 AOSP Lab of Nankai University. All Rights Reserved.",
    lab_name: "AOSP Laboratory, Nankai University",
    lab_slogan: "All-in-One Security and Privacy Lab",
    lab_description:
      "The lab focuses on diversified security and privacy research, spanning network security, Web security, LLM security, and emerging security risks. It is dedicated to enhancing overall security in scenarios where network technologies converge with large models, and continuously supports the security community through original research contributions.",
    lab_advisor_intro:
      'Advisor: <a href="https://lixiang521.com/" target="_blank" rel="noopener">Xiang Li</a>, Associate Professor at the College of Cryptology and Cyber Science, Nankai University. National Outstanding Talent in Cyberspace. Research areas include network security, protocol security, vulnerability discovery, and LLM security. Published 30+ papers at international conferences, including 10+ as first/corresponding author, achieving a grand slam of first-author papers across all top-4 cybersecurity venues, and has presented at Black Hat for four consecutive years. Led or participated in 9 national-level projects, filed 10+ patents, and received 250+ vulnerability IDs. Awards include ACM SIGSAC China Outstanding Doctoral Dissertation, GeekPwn champion & runner-up, Pwnie Award nomination for Most Innovative Research, and ACSAC Cybersecurity Impact Award.',
    lab_qrcode_caption: "Follow AOSP Lab",
  },
  zh: {
    page_title_user: "CoAuthors 共作查询",
    hero_user_title: "CoAuthors 共作查询系统",
    hero_user_subtitle: "输入两组作者姓名，返回存在共作关系的作者对与论文元数据。",
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
    matrix_title_user: "共作矩阵",
    pubs_title_user: "共作论文列表",
    pair_selector_user: "选择作者对",
    table_title: "标题",
    table_year: "年份",
    table_venue: "会议/期刊",
    table_type: "类型",
    query_recent_years: "近年范围",
    query_pc_conflict: "CCS 2026 New PC Conflict 检查 (2026/02/11)",
    year_slider_all: "全部",
    year_slider_recent: "近 {n} 年（{since} 年起）",
    placeholder_left: "Geoffrey Hinton\nYann LeCun (New York University)",
    placeholder_right: "Andrew Y. Ng\nYoshua Bengio (Universite de Montreal)",
    loading_default: "匹配中...",
    matrix_left_right: "左侧 \\ 右侧",
    matrix_count_header: "共作数量",
    no_coauthored_pairs: "没有共作作者对",
    no_publications: "没有论文",
    msg_require_both: "请在两侧都输入至少一个作者姓名。",
    msg_matching: "正在匹配 {n} 个作者对...",
    msg_completed: "匹配完成：共找到 {n} 个有共作关系的作者对。",
    msg_query_failed: "查询失败：{err}",
    msg_too_many_authors: "作者过多：每侧最多 {max} 个。",
    elapsed: "耗时",
    footer_title: "项目信息",
    footer_dev_label: "开发团队",
    footer_dev_value: "南开大学 AOSP 实验室",
    footer_maintainer_label: "维护团队",
    footer_maintainer_value: "南开大学 AOSP 实验室",
    footer_members_label: "成员",
    footer_members_value: "李想，许祖耀，仇渝淇，吴福彬，苗发生，孙蕗",
    footer_version_label: "版本",
    footer_features_label: "当前特性",
    footer_features_value: "共作矩阵；配对论文列表；",
    footer_license_label: "开源协议",
    footer_visits_label: "访问量",
    footer_copyright_label: "版权",
    footer_copyright_value: "© 2026 AOSP Lab of Nankai University. All Rights Reserved.",
    lab_name: "南开大学 AOSP 实验室",
    lab_slogan: "All-in-One Security and Privacy Lab",
    lab_description:
      "实验室：聚焦多元化安全与隐私研究，涵盖网络安全、Web 安全、大模型安全及新兴安全风险等方向，致力于提升网络技术与大模型融合场景下的整体安全性，并通过原创性研究成果持续服务与支撑安全社区发展。",
    lab_advisor_intro:
      '导师：<a href="https://lixiang521.com/" target="_blank" rel="noopener">李想</a>，南开大学密码与网络空间安全学院副教授，国家网信领域优秀人才，研究领域包括网络安全、协议安全、漏洞挖掘与大模型安全，已发表国际会议论文三十余篇，其中第一作者或通讯作者论文十余篇，实现网络安全顶会论文一作大满贯，并连续四年在 Black Hat 上完成报告，主持或参与国家级等项目九项，申请专利十余项，获批漏洞编号 250+，获得 ACM SIGSAC 中国优博奖、国际安全极客大赛冠亚军、全球黑客奥斯卡最具创新研究提名奖、ACSAC 网络安全技术成果影响力奖等。',
    lab_qrcode_caption: "关注 AOSP 实验室",
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

function toggleSidebar() {
  if (!sidebarEl) return;
  const isOpen = sidebarEl.classList.toggle("is-open");
  if (sidebarOverlayEl) {
    sidebarOverlayEl.classList.toggle("is-active", isOpen);
  }
}

function closeSidebar() {
  if (sidebarEl) sidebarEl.classList.remove("is-open");
  if (sidebarOverlayEl) sidebarOverlayEl.classList.remove("is-active");
}

if (sidebarToggleEl) {
  sidebarToggleEl.addEventListener("click", toggleSidebar);
}
if (sidebarOverlayEl) {
  sidebarOverlayEl.addEventListener("click", closeSidebar);
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

  document.querySelectorAll("[data-i18n-html]").forEach((el) => {
    const key = el.getAttribute("data-i18n-html");
    if (!key) return;
    el.innerHTML = t(key);
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    const key = el.getAttribute("data-i18n-placeholder");
    if (!key) return;
    el.setAttribute("placeholder", t(key));
  });

  setHealthStatus(healthState);
  if (typeof updateYearSliderLabel === "function") updateYearSliderLabel();
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
    loadingTextEl.textContent = t("msg_matching", { n: fmtNum(totalPairs) });
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
  if (pcConflictToggleEl && pcConflictToggleEl.checked && rightAuthorsEl) {
    rightAuthorsEl.disabled = true;
  }
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
      showMsg(t("msg_require_both"), true);
      return;
    }
    if (left.length > MAX_AUTHORS_PER_SIDE || right.length > MAX_AUTHORS_PER_SIDE) {
      showMsg(t("msg_too_many_authors", { max: MAX_AUTHORS_PER_SIDE }), true);
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
    if (yearSliderEl) {
      const years = 29 - Number(yearSliderEl.value);
      if (years > 0) {
        payload.year_min = new Date().getFullYear() - years;
      }
    }

    setQueryLoading(true, totalPairs);
    showMsg(t("msg_matching", { n: fmtNum(totalPairs) }));

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

      showMsg(t("msg_completed", { n: fmtNum(coauthoredPairCount) }));
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

function updateYearSliderLabel() {
  if (!yearSliderEl || !yearSliderLabelEl) return;
  const val = Number(yearSliderEl.value);
  const years = 29 - val;
  if (years === 0) {
    yearSliderLabelEl.textContent = t("year_slider_all");
  } else {
    const since = new Date().getFullYear() - years;
    yearSliderLabelEl.textContent = t("year_slider_recent", { n: years, since });
  }
}

if (yearSliderEl) {
  yearSliderEl.addEventListener("input", updateYearSliderLabel);
}

async function fetchPcMembers() {
  if (pcMembers !== null) return pcMembers;
  try {
    const data = await fetchJson("/api/pc-members");
    pcMembers = (data.members || []).map((m) => m.name);
  } catch (_) {
    pcMembers = [];
  }
  return pcMembers;
}

async function applyPcConflictState() {
  if (!pcConflictToggleEl) return;
  if (pcConflictToggleEl.checked) {
    savedRightAuthors = rightAuthorsEl ? rightAuthorsEl.value : "";
    const members = await fetchPcMembers();
    if (rightAuthorsEl) {
      rightAuthorsEl.value = members.join("\n");
      rightAuthorsEl.disabled = true;
    }
  } else {
    if (rightAuthorsEl) {
      rightAuthorsEl.value = savedRightAuthors;
      rightAuthorsEl.disabled = false;
    }
  }
}

if (pcConflictToggleEl) {
  pcConflictToggleEl.addEventListener("change", applyPcConflictState);
}

initLanguage();
loadHealth();
loadStats();
updateYearSliderLabel();
applyPcConflictState();
