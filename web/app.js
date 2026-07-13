const tokenStatus = document.querySelector("#tokenStatus");
const tokenPanel = document.querySelector("#tokenPanel");
const tokenInput = document.querySelector("#tokenInput");
const tokenPreview = document.querySelector("#tokenPreview");
const tokenNote = document.querySelector("#tokenNote");
const switchTokenButton = document.querySelector("#switchTokenButton");
const saveTokenButton = document.querySelector("#saveTokenButton");
const symbolsInput = document.querySelector("#symbolsInput");
const presetChips = document.querySelector("#presetChips");
const listNameInput = document.querySelector("#listNameInput");
const savedListSelect = document.querySelector("#savedListSelect");
const saveListButton = document.querySelector("#saveListButton");
const loadListButton = document.querySelector("#loadListButton");
const deleteListButton = document.querySelector("#deleteListButton");
const modeSelect = document.querySelector("#modeSelect");
const fallbackSelect = document.querySelector("#fallbackSelect");
const strikeLimitInput = document.querySelector("#strikeLimitInput");
const minOpenInterestInput = document.querySelector("#minOpenInterestInput");
const minVolumeInput = document.querySelector("#minVolumeInput");
const riskFreeRateInput = document.querySelector("#riskFreeRateInput");
const minSideStrikesInput = document.querySelector("#minSideStrikesInput");
const quoteAgeInput = document.querySelector("#quoteAgeInput");
const spreadInput = document.querySelector("#spreadInput");
const delayInput = document.querySelector("#delayInput");
const allowStaleInput = document.querySelector("#allowStaleInput");
const allowExtrapolationInput = document.querySelector("#allowExtrapolationInput");
const autoRefreshSelect = document.querySelector("#autoRefreshSelect");
const autoRefreshStatus = document.querySelector("#autoRefreshStatus");
const queryButton = document.querySelector("#queryButton");
const queryButtonLabel = document.querySelector("#queryButtonLabel");
const resultsBody = document.querySelector("#resultsBody");
const lastRun = document.querySelector("#lastRun");
const resultSortSelect = document.querySelector("#resultSortSelect");
const scannerNote = document.querySelector("#scannerNote");
const scannerHigh = document.querySelector("#scannerHigh");
const scannerLow = document.querySelector("#scannerLow");
const scannerSpread = document.querySelector("#scannerSpread");
const scannerList = document.querySelector("#scannerList");
const downloadRunCsvButton = document.querySelector("#downloadRunCsvButton");
const downloadRunJsonButton = document.querySelector("#downloadRunJsonButton");
const summaryOk = document.querySelector("#summaryOk");
const summaryWarn = document.querySelector("#summaryWarn");
const summaryError = document.querySelector("#summaryError");
const summaryAverage = document.querySelector("#summaryAverage");
const historyBody = document.querySelector("#historyBody");
const historyNote = document.querySelector("#historyNote");
const refreshHistoryButton = document.querySelector("#refreshHistoryButton");
const clearHistoryButton = document.querySelector("#clearHistoryButton");
const clearHistoryButtonLabel = document.querySelector("#clearHistoryButtonLabel");
const downloadFilteredHistoryCsvLink = document.querySelector("#downloadFilteredHistoryCsvLink");
const downloadFilteredHistoryJsonLink = document.querySelector("#downloadFilteredHistoryJsonLink");
const historySymbolFilter = document.querySelector("#historySymbolFilter");
const historyStatusFilter = document.querySelector("#historyStatusFilter");
const historyWindowFilter = document.querySelector("#historyWindowFilter");
const historyLatest = document.querySelector("#historyLatest");
const historyChange = document.querySelector("#historyChange");
const historyChangePercent = document.querySelector("#historyChangePercent");
const historyAverage = document.querySelector("#historyAverage");
const historyMedian = document.querySelector("#historyMedian");
const historyRange = document.querySelector("#historyRange");
const historyPercentile = document.querySelector("#historyPercentile");
const historyRegime = document.querySelector("#historyRegime");
const historyNumeric = document.querySelector("#historyNumeric");
const chartSymbolSelect = document.querySelector("#chartSymbolSelect");
const chartNote = document.querySelector("#chartNote");
const chartSummary = document.querySelector("#chartSummary");
const chartCanvas = document.querySelector("#assetVixChart");
const chartEmpty = document.querySelector("#chartEmpty");
const chartLegend = document.querySelector("#chartLegend");

const mainValue = document.querySelector("#mainValue");
const mainSymbol = document.querySelector("#mainSymbol");
const mainStatus = document.querySelector("#mainStatus");
const mainChange = document.querySelector("#mainChange");
const mainExpirations = document.querySelector("#mainExpirations");
const mainAge = document.querySelector("#mainAge");
const mainForward = document.querySelector("#mainForward");
const mainK0 = document.querySelector("#mainK0");
const mainStrikes = document.querySelector("#mainStrikes");
const mainRates = document.querySelector("#mainRates");
let tokenConfigured = false;
let tokenPanelForcedOpen = false;
let historyRows = [];
let historyMeta = { matchedCount: 0, totalCount: 0 };
let latestRows = [];
let appVersion = "";
let autoRefreshTimer = null;
let autoRefreshTicker = null;
let autoRefreshDeadline = null;
let queryInProgress = false;
const HISTORY_FETCH_LIMIT = 500;
const HISTORY_TABLE_LIMIT = 25;
const SCANNER_LIST_LIMIT = 12;
const ALL_SYMBOLS = "__all__";
const SETTINGS_KEY = "assetvix.query-settings.v1";
const CUSTOM_LISTS_KEY = "assetvix.custom-symbol-lists.v1";
const RUN_EXPORT_FIELDS = [
  "recorded_at_utc",
  "run_id",
  "source",
  "ts_utc",
  "symbol",
  "status",
  "asset_vix_30d",
  "previous_asset_vix_30d",
  "change_from_previous",
  "change_from_previous_pct",
  "variance_30d",
  "target_days",
  "rate_source",
  "mode",
  "expirations",
  "days",
  "rates",
  "forwards",
  "k0",
  "strike_counts",
  "put_counts",
  "call_counts",
  "max_quote_age_minutes",
  "reason",
];
const rememberedControls = [
  symbolsInput,
  modeSelect,
  fallbackSelect,
  strikeLimitInput,
  minOpenInterestInput,
  minVolumeInput,
  riskFreeRateInput,
  minSideStrikesInput,
  quoteAgeInput,
  spreadInput,
  delayInput,
  allowStaleInput,
  allowExtrapolationInput,
  autoRefreshSelect,
  resultSortSelect,
];
const chartColors = [
  "#0b8f83",
  "#315f9f",
  "#b7791f",
  "#8a4ab8",
  "#ba2f3a",
  "#177245",
  "#53606f",
  "#c44f24",
];

function setTokenStatus(configured, source, preview, formatOk = true, formatReason = "") {
  const usable = configured && formatOk;
  tokenConfigured = usable;
  tokenStatus.classList.toggle("ok", usable);
  tokenStatus.classList.toggle("missing", !usable);
  tokenStatus.querySelector("span:last-child").textContent = usable
    ? `token ready (${source}${preview ? ` ${preview}` : ""})`
    : configured
      ? "token format error"
    : "token required";
  switchTokenButton.querySelector("span").textContent = configured ? "Change Token" : "Add Token";
  tokenPreview.textContent = configured
    ? `Current ${source}${preview ? ` · ${preview}` : ""}`
    : "Not configured";
  tokenPanel.hidden = usable && !tokenPanelForcedOpen;
  tokenNote.textContent = usable
    ? "A newly saved token becomes active for the next query."
    : configured
      ? `Current token cannot be used: ${formatReason || "format error"}`
    : "Save a MarketData token before running a query.";
  if (!usable) clearAutoRefresh("Auto refresh needs a valid token");
}

function autoRefreshMinutes() {
  const minutes = Number(autoRefreshSelect.value);
  return [5, 15, 30, 60].includes(minutes) ? minutes : 0;
}

function formatCountdown(milliseconds) {
  const seconds = Math.max(0, Math.ceil(milliseconds / 1000));
  const minutes = Math.floor(seconds / 60);
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`;
}

function setAutoRefreshStatus(message, state = "idle") {
  autoRefreshStatus.textContent = message;
  autoRefreshStatus.dataset.state = state;
}

function clearAutoRefresh(message = "") {
  if (autoRefreshTimer !== null) window.clearTimeout(autoRefreshTimer);
  if (autoRefreshTicker !== null) window.clearInterval(autoRefreshTicker);
  autoRefreshTimer = null;
  autoRefreshTicker = null;
  autoRefreshDeadline = null;
  if (message) {
    setAutoRefreshStatus(message, "idle");
  }
}

function updateAutoRefreshCountdown() {
  if (!autoRefreshDeadline) return;
  const remaining = autoRefreshDeadline - Date.now();
  if (remaining <= 0) {
    setAutoRefreshStatus("Refreshing now…", "running");
    return;
  }
  setAutoRefreshStatus(`Next refresh in ${formatCountdown(remaining)}`, "scheduled");
}

function scheduleAutoRefresh() {
  clearAutoRefresh();
  const minutes = autoRefreshMinutes();
  if (!minutes) {
    setAutoRefreshStatus("Manual refresh only", "idle");
    return;
  }
  if (!tokenConfigured) {
    setAutoRefreshStatus("Auto refresh needs a valid token", "idle");
    return;
  }
  if (!latestRows.length) {
    setAutoRefreshStatus("Click Calculate to start monitoring", "idle");
    return;
  }
  autoRefreshDeadline = Date.now() + minutes * 60 * 1000;
  updateAutoRefreshCountdown();
  autoRefreshTicker = window.setInterval(updateAutoRefreshCountdown, 1000);
  autoRefreshTimer = window.setTimeout(() => {
    clearAutoRefresh();
    runQuery({ automatic: true });
  }, minutes * 60 * 1000);
}

function saveSettings() {
  const settings = {};
  for (const control of rememberedControls) {
    settings[control.id] =
      control.type === "checkbox" ? control.checked : control.value;
  }
  try {
    window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch (_error) {
    // The app remains usable when browser storage is unavailable.
  }
}

function loadSettings() {
  try {
    const settings = JSON.parse(window.localStorage.getItem(SETTINGS_KEY) || "{}");
    if (!settings || typeof settings !== "object" || Array.isArray(settings)) return;
    for (const control of rememberedControls) {
      if (!Object.prototype.hasOwnProperty.call(settings, control.id)) continue;
      const value = settings[control.id];
      if (control.type === "checkbox") {
        if (typeof value === "boolean") control.checked = value;
      } else if (typeof value === "string") {
        control.value = value;
      }
    }
  } catch (_error) {
    // Ignore malformed or unavailable browser storage.
  }
}

function normalizeListName(value) {
  return String(value || "").trim().replace(/\s+/g, " ").slice(0, 32);
}

function loadCustomLists() {
  try {
    const lists = JSON.parse(window.localStorage.getItem(CUSTOM_LISTS_KEY) || "{}");
    if (!lists || typeof lists !== "object" || Array.isArray(lists)) return {};
    return Object.fromEntries(
      Object.entries(lists)
        .filter((entry) => typeof entry[0] === "string" && typeof entry[1] === "string")
        .map(([name, symbols]) => [normalizeListName(name), symbols.trim()])
        .filter(([name, symbols]) => name && symbols)
    );
  } catch (_error) {
    return {};
  }
}

function storeCustomLists(lists) {
  try {
    window.localStorage.setItem(CUSTOM_LISTS_KEY, JSON.stringify(lists));
  } catch (_error) {
    // Custom lists are optional; failed storage should not block calculations.
  }
}

function renderSavedLists(selected = "") {
  const lists = loadCustomLists();
  const names = Object.keys(lists).sort((left, right) => left.localeCompare(right));
  savedListSelect.innerHTML = '<option value="">None</option>';
  for (const name of names) {
    const option = document.createElement("option");
    option.value = name;
    option.textContent = name;
    savedListSelect.appendChild(option);
  }
  savedListSelect.value = names.includes(selected) ? selected : "";
  loadListButton.disabled = !savedListSelect.value;
  deleteListButton.disabled = !savedListSelect.value;
}

function saveCurrentList() {
  const name = normalizeListName(listNameInput.value);
  const symbols = symbolsInput.value.trim();
  if (!name) {
    listNameInput.focus();
    return;
  }
  if (!symbols) {
    symbolsInput.focus();
    return;
  }
  const lists = loadCustomLists();
  lists[name] = symbols;
  storeCustomLists(lists);
  listNameInput.value = "";
  renderSavedLists(name);
}

function loadSelectedList() {
  const lists = loadCustomLists();
  const symbols = lists[savedListSelect.value];
  if (!symbols) return;
  symbolsInput.value = symbols;
  saveSettings();
}

function deleteSelectedList() {
  const name = savedListSelect.value;
  if (!name) return;
  const lists = loadCustomLists();
  delete lists[name];
  storeCustomLists(lists);
  renderSavedLists();
}

function setRunExportState() {
  const hasRows = latestRows.length > 0;
  downloadRunCsvButton.disabled = !hasRows;
  downloadRunJsonButton.disabled = !hasRows;
}

function updateResultSummary(rows) {
  const counts = { ok: 0, warn: 0, error: 0 };
  const values = [];
  for (const row of rows) {
    const bucket = badgeClass(String(row.status || ""));
    counts[bucket] += 1;
    const value = parseAssetVix(row.asset_vix_30d);
    if (value !== null && bucket !== "error") values.push(value);
  }
  const average = values.length
    ? values.reduce((total, value) => total + value, 0) / values.length
    : null;
  summaryOk.textContent = String(counts.ok);
  summaryWarn.textContent = String(counts.warn);
  summaryError.textContent = String(counts.error);
  summaryAverage.textContent = average === null ? "--" : formatValue(average);
}

function csvExportValue(value) {
  let text = value === null || value === undefined ? "" : String(value);
  if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return `"${text.replace(/"/g, '""')}"`;
}

function rowsToCsv(rows) {
  const lines = [RUN_EXPORT_FIELDS.join(",")];
  for (const row of rows) {
    lines.push(RUN_EXPORT_FIELDS.map((field) => csvExportValue(row[field])).join(","));
  }
  return `${lines.join("\n")}\n`;
}

function downloadBlob(filename, type, content) {
  const blob = new Blob([content], { type });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

function exportCurrentRun(format) {
  if (!latestRows.length) return;
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  if (format === "json") {
    const payload = {
      version: appVersion || null,
      exported_at_utc: new Date().toISOString(),
      count: latestRows.length,
      rows: latestRows,
    };
    downloadBlob(
      `assetvix-run-${stamp}.json`,
      "application/json;charset=utf-8",
      `${JSON.stringify(payload, null, 2)}\n`
    );
    return;
  }
  downloadBlob(`assetvix-run-${stamp}.csv`, "text/csv;charset=utf-8", rowsToCsv(latestRows));
}

async function api(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const contentType = response.headers.get("content-type") || "";
  let data;
  if (contentType.includes("application/json")) {
    data = await response.json();
  } else {
    data = { error: (await response.text()).trim() || "Request failed" };
  }
  if (!response.ok || !data.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

async function loadStatus() {
  const response = await fetch("/api/status", { cache: "no-store" });
  const data = await response.json();
  appVersion = data.version || appVersion;
  setTokenStatus(
    data.tokenConfigured,
    data.tokenSource,
    data.tokenPreview,
    data.tokenFormatOk,
    data.tokenFormatReason
  );
  scheduleAutoRefresh();
}

async function loadUniverses() {
  try {
    const response = await fetch("/api/universes", { cache: "no-store" });
    const data = await response.json();
    if (!data.ok || !Array.isArray(data.universes)) return;

    const visible = data.universes.filter((item) =>
      ["core", "etfs", "mega_cap", "semis", "liquid50", "liquid100"].includes(item.name)
    );
    if (!visible.length) return;

    presetChips.innerHTML = "";
    for (const item of visible) {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.symbols = (item.symbols || []).join(",");
      button.textContent = `${item.name} (${item.count})`;
      button.addEventListener("click", () => {
        symbolsInput.value = button.dataset.symbols || symbolsInput.value;
        saveSettings();
      });
      presetChips.appendChild(button);
    }
  } catch (_error) {
    // Static fallback buttons remain available.
  }
}

function badgeClass(status) {
  if (status === "ok") return "ok";
  if (status === "error") return "error";
  return "warn";
}

function formatValue(value) {
  if (value === null || value === undefined || value === "") return "--";
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric.toFixed(2) : String(value);
}

function formatSignedValue(value) {
  if (value === null || value === undefined || value === "") return "--";
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return String(value);
  return `${numeric > 0 ? "+" : ""}${numeric.toFixed(2)}`;
}

function formatSignedPercent(value) {
  if (value === null || value === undefined || value === "") return "--";
  const number = Number(value);
  if (!Number.isFinite(number)) return "--";
  return `${number > 0 ? "+" : ""}${number.toFixed(2)}%`;
}

function formatDateTime(value) {
  if (!value) return "--";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString();
}

function shortRunId(value) {
  if (!value) return "--";
  return String(value).slice(0, 8);
}

function parseRecordTime(row) {
  const date = new Date(row.recorded_at_utc || row.ts_utc || "");
  return Number.isNaN(date.getTime()) ? null : date;
}

function parseAssetVix(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function formatAxisTime(value) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "--";
  return date.toLocaleString(undefined, {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function chartColor(symbol, index = 0) {
  let hash = index;
  for (const char of String(symbol || "")) {
    hash = (hash * 31 + char.charCodeAt(0)) % chartColors.length;
  }
  return chartColors[Math.abs(hash) % chartColors.length];
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => {
    const entities = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    };
    return entities[char];
  });
}

function optionalNumber(value) {
  if (value === null || value === undefined || String(value).trim() === "") return null;
  return parseAssetVix(value);
}

function previousRunComparison(row) {
  const previous = optionalNumber(row?.previous_asset_vix_30d);
  const change = optionalNumber(row?.change_from_previous);
  const changePercent = optionalNumber(row?.change_from_previous_pct);
  if (previous === null) {
    return { text: "First recorded run", trend: "flat", hasPrevious: false };
  }
  if (change === null) {
    return { text: `Prior ${formatValue(previous)}`, trend: "flat", hasPrevious: true };
  }
  const percentage = changePercent === null ? "" : ` · ${formatSignedPercent(changePercent)}`;
  const trend = Math.abs(change) < 0.000001 ? "flat" : change > 0 ? "up" : "down";
  return {
    text: `${formatSignedValue(change)}${percentage}`,
    trend,
    hasPrevious: true,
  };
}

function updatePreviousRunIndicator(row) {
  const comparison = previousRunComparison(row);
  mainChange.textContent =
    row && comparison.hasPrevious ? `${comparison.text} vs prior` : comparison.text;
  mainChange.classList.remove("trend-up", "trend-down", "trend-flat");
  mainChange.classList.add(`trend-${row ? comparison.trend : "flat"}`);
}

function updateMain(row) {
  if (!row) {
    mainValue.textContent = "--";
    mainSymbol.textContent = "Waiting for query";
    mainStatus.textContent = "idle";
    updatePreviousRunIndicator(null);
    mainExpirations.textContent = "--";
    mainAge.textContent = "--";
    mainForward.textContent = "--";
    mainK0.textContent = "--";
    mainStrikes.textContent = "--";
    mainRates.textContent = "--";
    return;
  }

  mainValue.textContent = formatValue(row.asset_vix_30d);
  mainSymbol.textContent = row.symbol || "--";
  mainStatus.textContent = row.status || "--";
  updatePreviousRunIndicator(row);
  mainExpirations.textContent = row.expirations || "--";
  mainAge.textContent =
    row.max_quote_age_minutes === null || row.max_quote_age_minutes === undefined
      ? "--"
      : `${row.max_quote_age_minutes} min`;
  mainForward.textContent = row.forwards || "--";
  mainK0.textContent = row.k0 || "--";
  mainStrikes.textContent = row.strike_counts || "--";
  mainRates.textContent = row.rates || "--";
}

function rowAssetVix(row) {
  const value = parseAssetVix(row.asset_vix_30d);
  return badgeClass(String(row.status || "")) === "error" ? null : value;
}

function sortedResultRows(rows) {
  const sort = resultSortSelect.value;
  return rows.slice().sort((left, right) => {
    if (sort === "symbol") {
      return String(left.symbol || "").localeCompare(String(right.symbol || ""));
    }
    const leftValue = rowAssetVix(left);
    const rightValue = rowAssetVix(right);
    if (leftValue === null && rightValue === null) return 0;
    if (leftValue === null) return 1;
    if (rightValue === null) return -1;
    return sort === "low" ? leftValue - rightValue : rightValue - leftValue;
  });
}

function scannerItems(rows) {
  return rows
    .map((row) => ({ row, value: rowAssetVix(row) }))
    .filter((item) => item.value !== null)
    .sort((left, right) => right.value - left.value);
}

function renderScanner(rows) {
  const items = scannerItems(rows);
  scannerList.innerHTML = "";
  if (!items.length) {
    scannerNote.textContent = rows.length
      ? "No usable 30D values in this run"
      : "Calculate a basket to compare cross-asset volatility";
    scannerHigh.textContent = "--";
    scannerLow.textContent = "--";
    scannerSpread.textContent = "--";
    scannerList.innerHTML = '<p class="scanner-empty">No ranked AssetVIX values yet</p>';
    return;
  }

  const highest = items[0];
  const lowest = items[items.length - 1];
  const average = items.reduce((total, item) => total + item.value, 0) / items.length;
  const spread = highest.value - lowest.value;
  const maximum = highest.value || 1;
  scannerNote.textContent = `${items.length} usable values · basket average ${formatValue(average)}`;
  scannerHigh.textContent = `${highest.row.symbol} ${formatValue(highest.value)}`;
  scannerLow.textContent = `${lowest.row.symbol} ${formatValue(lowest.value)}`;
  scannerSpread.textContent = formatValue(spread);

  for (const [index, item] of items.slice(0, SCANNER_LIST_LIMIT).entries()) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "scanner-row";
    button.addEventListener("click", () => updateMain(item.row));

    const rank = document.createElement("span");
    rank.className = "scanner-rank";
    rank.textContent = String(index + 1);
    const symbol = document.createElement("strong");
    symbol.textContent = item.row.symbol || "UNKNOWN";
    const bar = document.createElement("span");
    bar.className = "scanner-bar";
    const fill = document.createElement("i");
    fill.style.width = `${Math.max(5, (item.value / maximum) * 100)}%`;
    bar.appendChild(fill);
    const value = document.createElement("span");
    value.className = "scanner-value";
    value.textContent = formatValue(item.value);
    const delta = document.createElement("span");
    delta.className = item.value >= average ? "scanner-delta above" : "scanner-delta below";
    delta.textContent = `${formatSignedValue(item.value - average)} vs avg`;
    button.append(rank, symbol, bar, value, delta);
    scannerList.appendChild(button);
  }
  if (items.length > SCANNER_LIST_LIMIT) {
    const more = document.createElement("p");
    more.className = "scanner-empty";
    more.textContent = `${items.length - SCANNER_LIST_LIMIT} additional symbols remain in the results table`;
    scannerList.appendChild(more);
  }
}

function renderRows(rows, { markRun = true } = {}) {
  latestRows = rows.slice();
  setRunExportState();
  updateResultSummary(rows);
  renderScanner(rows);
  resultsBody.innerHTML = "";
  if (!rows.length) {
    resultsBody.innerHTML = '<tr><td colspan="7" class="empty">No results</td></tr>';
    updateMain(null);
    return;
  }

  for (const row of sortedResultRows(rows)) {
    const tr = document.createElement("tr");
    const quoteAge =
      row.max_quote_age_minutes === null || row.max_quote_age_minutes === undefined
        ? "--"
        : `${escapeHtml(row.max_quote_age_minutes)} min`;
    const comparison = previousRunComparison(row);
    tr.innerHTML = `
      <td><strong>${escapeHtml(row.symbol || "")}</strong></td>
      <td><span class="badge ${badgeClass(row.status)}">${escapeHtml(row.status || "")}</span></td>
      <td>${escapeHtml(formatValue(row.asset_vix_30d))}</td>
      <td><span class="previous-change trend-${comparison.trend}">${escapeHtml(comparison.text)}</span></td>
      <td>${escapeHtml(row.expirations || "--")}</td>
      <td>${quoteAge}</td>
      <td>${escapeHtml(row.reason || "")}</td>
    `;
    tr.addEventListener("click", () => updateMain(row));
    resultsBody.appendChild(tr);
  }

  updateMain(rows.find((row) => row.status === "ok") || rows[0]);
  if (markRun) lastRun.textContent = `Last run: ${new Date().toLocaleString()}`;
}

function renderHistory(rows) {
  const tableRows = rows.slice(-HISTORY_TABLE_LIMIT);
  historyBody.innerHTML = "";
  if (!tableRows.length) {
    const message = historyMeta.totalCount
      ? "No history matches these filters"
      : "No recorded calculations yet";
    historyBody.innerHTML = `<tr><td colspan="6" class="empty">${message}</td></tr>`;
    historyNote.textContent = historyMeta.totalCount
      ? "0 matching rows"
      : "Latest recorded calculations";
    return;
  }

  for (const row of tableRows.slice().reverse()) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(formatDateTime(row.recorded_at_utc || row.ts_utc))}</td>
      <td><span class="run-id">${escapeHtml(shortRunId(row.run_id))}</span></td>
      <td><strong>${escapeHtml(row.symbol || "")}</strong></td>
      <td><span class="badge ${badgeClass(row.status)}">${escapeHtml(row.status || "")}</span></td>
      <td>${escapeHtml(formatValue(row.asset_vix_30d))}</td>
      <td>${escapeHtml(row.reason || "")}</td>
    `;
    historyBody.appendChild(tr);
  }
  const matchedCount = Number.isFinite(historyMeta.matchedCount)
    ? historyMeta.matchedCount
    : rows.length;
  historyNote.textContent = `${tableRows.length} of ${matchedCount} matching rows shown`;
}

function renderHistorySummary(summary) {
  const latest = summary?.latest;
  const latestSymbol = latest?.symbol ? `${latest.symbol} ` : "";
  historyLatest.textContent = latest ? `${latestSymbol}${formatValue(latest.value)}` : "--";
  historyChange.textContent = formatSignedValue(summary?.change);
  historyChange.classList.remove("trend-up", "trend-down", "trend-flat");
  historyChange.classList.add(`trend-${summary?.trend || "flat"}`);
  historyChangePercent.textContent = formatSignedPercent(summary?.changePercent);
  historyChangePercent.classList.remove("trend-up", "trend-down", "trend-flat");
  historyChangePercent.classList.add(`trend-${summary?.trend || "flat"}`);
  historyAverage.textContent = formatValue(summary?.average);
  historyMedian.textContent = formatValue(summary?.median);
  historyRange.textContent =
    summary?.low === null || summary?.low === undefined
      ? "--"
      : `${formatValue(summary.low)} - ${formatValue(summary.high)}`;
  historyPercentile.textContent =
    summary?.percentile === null || summary?.percentile === undefined
      ? "--"
      : `${Number(summary.percentile).toFixed(1)}th`;
  const regime = String(summary?.regime || "unknown");
  historyRegime.textContent = regime === "unknown" ? "--" : regime;
  historyRegime.className = `regime regime-${regime}`;
  const numericCount = Number(summary?.numericCount ?? 0);
  const matchedCount = Number(summary?.matchedCount ?? 0);
  historyNumeric.textContent = matchedCount ? `${numericCount}/${matchedCount}` : "--";
}

function updateHistorySymbolOptions(symbols) {
  const previous = historySymbolFilter.value || ALL_SYMBOLS;
  const uniqueSymbols = Array.from(
    new Set((symbols || []).map((symbol) => String(symbol || "").toUpperCase()).filter(Boolean))
  ).sort();
  historySymbolFilter.innerHTML = '<option value="__all__">All</option>';
  for (const symbol of uniqueSymbols) {
    const option = document.createElement("option");
    option.value = symbol;
    option.textContent = symbol;
    historySymbolFilter.appendChild(option);
  }
  historySymbolFilter.value = uniqueSymbols.includes(previous) ? previous : ALL_SYMBOLS;
}

function chartPoints(rows) {
  return rows
    .map((row) => {
      const time = parseRecordTime(row);
      const value = parseAssetVix(row.asset_vix_30d);
      const status = String(row.status || "");
      if (!time || value === null || status === "error") return null;
      return {
        symbol: String(row.symbol || "").toUpperCase() || "UNKNOWN",
        time,
        value,
        status,
      };
    })
    .filter(Boolean)
    .sort((left, right) => left.time - right.time);
}

function updateChartSymbolOptions(points) {
  const previous = chartSymbolSelect.value || ALL_SYMBOLS;
  const symbols = Array.from(new Set(points.map((point) => point.symbol))).sort();
  chartSymbolSelect.innerHTML = '<option value="__all__">All</option>';
  for (const symbol of symbols) {
    const option = document.createElement("option");
    option.value = symbol;
    option.textContent = symbol;
    chartSymbolSelect.appendChild(option);
  }
  chartSymbolSelect.value =
    previous === ALL_SYMBOLS || symbols.includes(previous) ? previous : ALL_SYMBOLS;
}

function updateChartSummary(points) {
  const values = points.map((point) => point.value);
  const latest = points[points.length - 1];
  const low = values.length ? Math.min(...values) : null;
  const high = values.length ? Math.max(...values) : null;
  const items = [
    latest ? formatValue(latest.value) : "--",
    low === null ? "--" : formatValue(low),
    high === null ? "--" : formatValue(high),
    String(points.length || "--"),
  ];
  chartSummary.querySelectorAll("strong").forEach((node, index) => {
    node.textContent = items[index] || "--";
  });
}

function groupChartPoints(points) {
  const groups = new Map();
  for (const point of points) {
    if (!groups.has(point.symbol)) groups.set(point.symbol, []);
    groups.get(point.symbol).push(point);
  }
  return Array.from(groups.entries()).map(([symbol, values], index) => ({
    symbol,
    values,
    color: chartColor(symbol, index),
  }));
}

function drawChart(points) {
  const parent = chartCanvas.parentElement;
  const width = Math.max(320, Math.floor(parent.clientWidth));
  const height = 320;
  const dpr = window.devicePixelRatio || 1;
  chartCanvas.style.width = `${width}px`;
  chartCanvas.style.height = `${height}px`;
  chartCanvas.width = Math.floor(width * dpr);
  chartCanvas.height = Math.floor(height * dpr);

  const context = chartCanvas.getContext("2d");
  if (!context) {
    chartEmpty.hidden = false;
    chartEmpty.textContent = "Chart unavailable";
    chartLegend.innerHTML = "";
    return;
  }
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  context.clearRect(0, 0, width, height);
  context.fillStyle = "#fbfcfc";
  context.fillRect(0, 0, width, height);

  if (!points.length) {
    chartEmpty.hidden = false;
    chartLegend.innerHTML = "";
    return;
  }
  chartEmpty.hidden = true;

  const margin = { top: 20, right: 18, bottom: 44, left: 58 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const times = points.map((point) => point.time.getTime());
  const values = points.map((point) => point.value);
  let minTime = Math.min(...times);
  let maxTime = Math.max(...times);
  let minValue = Math.min(...values);
  let maxValue = Math.max(...values);

  if (minTime === maxTime) {
    minTime -= 30 * 60 * 1000;
    maxTime += 30 * 60 * 1000;
  }
  if (minValue === maxValue) {
    minValue -= 1;
    maxValue += 1;
  } else {
    const padding = (maxValue - minValue) * 0.12;
    minValue = Math.max(0, minValue - padding);
    maxValue += padding;
  }

  const xFor = (time) =>
    margin.left + ((time.getTime() - minTime) / (maxTime - minTime)) * plotWidth;
  const yFor = (value) =>
    margin.top + plotHeight - ((value - minValue) / (maxValue - minValue)) * plotHeight;

  context.strokeStyle = "#dbe3e2";
  context.lineWidth = 1;
  context.fillStyle = "#677371";
  context.font = "12px Inter, system-ui, sans-serif";
  context.textBaseline = "middle";

  for (let index = 0; index <= 4; index += 1) {
    const y = margin.top + (plotHeight * index) / 4;
    const value = maxValue - ((maxValue - minValue) * index) / 4;
    context.beginPath();
    context.moveTo(margin.left, y);
    context.lineTo(width - margin.right, y);
    context.stroke();
    context.textAlign = "right";
    context.fillText(value.toFixed(1), margin.left - 10, y);
  }

  context.textBaseline = "top";
  for (let index = 0; index <= 3; index += 1) {
    const x = margin.left + (plotWidth * index) / 3;
    const time = new Date(minTime + ((maxTime - minTime) * index) / 3);
    context.beginPath();
    context.moveTo(x, margin.top);
    context.lineTo(x, margin.top + plotHeight);
    context.stroke();
    context.textAlign = index === 0 ? "left" : index === 3 ? "right" : "center";
    context.fillText(formatAxisTime(time), x, margin.top + plotHeight + 14);
  }

  context.strokeStyle = "#9aa6a4";
  context.beginPath();
  context.moveTo(margin.left, margin.top);
  context.lineTo(margin.left, margin.top + plotHeight);
  context.lineTo(width - margin.right, margin.top + plotHeight);
  context.stroke();

  const groups = groupChartPoints(points);
  for (const group of groups) {
    context.strokeStyle = group.color;
    context.fillStyle = group.color;
    context.lineWidth = 2;
    context.beginPath();
    group.values.forEach((point, index) => {
      const x = xFor(point.time);
      const y = yFor(point.value);
      if (index === 0) context.moveTo(x, y);
      else context.lineTo(x, y);
    });
    context.stroke();

    for (const point of group.values) {
      const x = xFor(point.time);
      const y = yFor(point.value);
      context.beginPath();
      context.arc(x, y, 3.4, 0, Math.PI * 2);
      context.fill();
      context.strokeStyle = "#ffffff";
      context.lineWidth = 1.4;
      context.stroke();
      context.strokeStyle = group.color;
    }
  }

  chartLegend.innerHTML = groups
    .map(
      (group) => `
        <span>
          <i style="background:${escapeHtml(group.color)}"></i>
          ${escapeHtml(group.symbol)}
        </span>
      `
    )
    .join("");
}

function renderChart(rows) {
  const points = chartPoints(rows);
  updateChartSymbolOptions(points);
  const selected = chartSymbolSelect.value || ALL_SYMBOLS;
  const visible =
    selected === ALL_SYMBOLS
      ? points
      : points.filter((point) => point.symbol === selected);

  updateChartSummary(visible);
  drawChart(visible);
  const symbolCount = new Set(points.map((point) => point.symbol)).size;
  chartNote.textContent = points.length
    ? `${points.length} numeric points across ${symbolCount} symbols`
    : "Recorded AssetVIX points";
}

function historyFilterParams() {
  const params = new URLSearchParams({ limit: String(HISTORY_FETCH_LIMIT) });
  const selectedSymbol = historySymbolFilter.value || ALL_SYMBOLS;
  const selectedStatus = historyStatusFilter.value || ALL_SYMBOLS;
  const windowDays = historyWindowFilter.value || "0";
  if (selectedSymbol !== ALL_SYMBOLS) params.set("symbol", selectedSymbol);
  if (selectedStatus !== ALL_SYMBOLS) params.set("status", selectedStatus);
  if (windowDays !== "0") params.set("windowDays", windowDays);
  return params;
}

function updateFilteredHistoryLinks() {
  const query = historyFilterParams().toString();
  downloadFilteredHistoryCsvLink.href = `/api/history.csv?${query}`;
  downloadFilteredHistoryJsonLink.href = `/api/history.json?${query}`;
}

async function loadHistory() {
  try {
    const params = historyFilterParams();
    updateFilteredHistoryLinks();
    const query = params.toString();
    const [response, summaryResponse] = await Promise.all([
      fetch(`/api/history?${query}`, { cache: "no-store" }),
      fetch(`/api/history/summary?${query}`, { cache: "no-store" }),
    ]);
    const [data, summary] = await Promise.all([
      response.json(),
      summaryResponse.json(),
    ]);
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "History request failed");
    }
    if (!summaryResponse.ok || !summary.ok) {
      throw new Error(summary.error || "History summary request failed");
    }
    historyRows = data.rows || [];
    historyMeta = {
      matchedCount: Number(data.matchedCount ?? historyRows.length),
      totalCount: Number(data.totalCount ?? historyRows.length),
    };
    updateHistorySymbolOptions(data.symbols || historyRows.map((row) => row.symbol));
    renderHistory(historyRows);
    renderHistorySummary(summary);
    renderChart(historyRows);
  } catch (error) {
    historyBody.innerHTML = `<tr><td colspan="6" class="empty">${escapeHtml(error.message)}</td></tr>`;
    historyNote.textContent = "History unavailable";
    renderHistorySummary(null);
    chartEmpty.hidden = false;
    chartLegend.innerHTML = "";
  }
}

function buildQueryPayload() {
  const optionalNumber = (input) => {
    const value = input.value.trim();
    return value === "" ? null : Number(value);
  };
  const riskFreeRatePct = optionalNumber(riskFreeRateInput);
  return {
    symbols: symbolsInput.value,
    mode: modeSelect.value,
    fallbackMode: fallbackSelect.value,
    maxage: "5min",
    strikeLimit: Number(strikeLimitInput.value || 120),
    minOpenInterest: optionalNumber(minOpenInterestInput),
    minVolume: optionalNumber(minVolumeInput),
    minSideStrikes: Number(minSideStrikesInput.value || 5),
    riskFreeRate: riskFreeRatePct === null ? null : riskFreeRatePct / 100,
    maxQuoteAgeMinutes: Number(quoteAgeInput.value || 45),
    maxBidAskSpreadPct: Number(spreadInput.value || 200),
    requestDelaySeconds: Number(delayInput.value || 0.25),
    allowStale: allowStaleInput.checked,
    allowExtrapolation: allowExtrapolationInput.checked,
  };
}

async function clearHistory() {
  const confirmed = window.confirm(
    "Delete all local calculation history? This cannot be undone."
  );
  if (!confirmed) return;

  clearHistoryButton.disabled = true;
  clearHistoryButtonLabel.textContent = "Clearing...";
  try {
    const data = await api("/api/history/clear", {});
    historyRows = [];
    historyMeta = { matchedCount: 0, totalCount: 0 };
    updateHistorySymbolOptions([]);
    renderHistory(historyRows);
    renderHistorySummary(null);
    renderChart(historyRows);
    historyNote.textContent = data.cleared
      ? "Local calculation history cleared"
      : "Calculation history is already empty";
  } catch (error) {
    historyNote.textContent = `Could not clear history: ${error.message}`;
  } finally {
    clearHistoryButton.disabled = false;
    clearHistoryButtonLabel.textContent = "Clear History";
  }
}

async function runQuery({ automatic = false } = {}) {
  if (!tokenConfigured) {
    clearAutoRefresh("Auto refresh needs a valid token");
    openTokenPanel();
    return;
  }
  if (queryInProgress) return;
  clearAutoRefresh();
  queryInProgress = true;
  queryButton.disabled = true;
  queryButtonLabel.textContent = "Calculating...";
  setAutoRefreshStatus(
    automatic ? "Automatic refresh is running…" : "Calculation is running…",
    "running"
  );
  saveSettings();
  try {
    const data = await api("/api/query", buildQueryPayload());
    renderRows(data.rows || []);
    await loadHistory();
  } catch (error) {
    latestRows = [];
    setRunExportState();
    resultsBody.innerHTML = `<tr><td colspan="6" class="empty">${escapeHtml(error.message)}</td></tr>`;
    updateMain({
      symbol: "ERROR",
      status: "error",
      asset_vix_30d: null,
      reason: error.message,
    });
  } finally {
    queryInProgress = false;
    queryButton.disabled = false;
    queryButtonLabel.textContent = "Calculate";
    scheduleAutoRefresh();
  }
}

function openTokenPanel() {
  tokenPanelForcedOpen = true;
  tokenPanel.hidden = false;
  tokenInput.value = "";
  tokenInput.focus();
}

function toggleTokenPanel() {
  if (tokenPanel.hidden) {
    openTokenPanel();
    return;
  }
  if (tokenConfigured) {
    tokenPanelForcedOpen = false;
    tokenPanel.hidden = true;
  }
}

async function saveToken() {
  const token = tokenInput.value.trim();
  if (!token) {
    tokenInput.focus();
    return;
  }
  saveTokenButton.disabled = true;
  tokenNote.textContent = "Testing token...";
  try {
    const data = await api("/api/token", { token });
    tokenInput.value = "";
    tokenPanelForcedOpen = false;
    setTokenStatus(data.tokenConfigured, data.tokenSource, data.tokenPreview);
    tokenNote.textContent = "Token tested and saved. The next query will use it.";
  } catch (error) {
    tokenNote.textContent = `Token test failed: ${error.message}`;
    tokenInput.focus();
  } finally {
    saveTokenButton.disabled = false;
  }
}

document.querySelectorAll("[data-symbols]").forEach((button) => {
  button.addEventListener("click", () => {
    symbolsInput.value = button.dataset.symbols || symbolsInput.value;
    saveSettings();
  });
});

for (const control of rememberedControls) {
  control.addEventListener("change", saveSettings);
}

switchTokenButton.addEventListener("click", toggleTokenPanel);
saveTokenButton.addEventListener("click", saveToken);
saveListButton.addEventListener("click", saveCurrentList);
loadListButton.addEventListener("click", loadSelectedList);
deleteListButton.addEventListener("click", deleteSelectedList);
savedListSelect.addEventListener("change", () => renderSavedLists(savedListSelect.value));
downloadRunCsvButton.addEventListener("click", () => exportCurrentRun("csv"));
downloadRunJsonButton.addEventListener("click", () => exportCurrentRun("json"));
refreshHistoryButton.addEventListener("click", loadHistory);
clearHistoryButton.addEventListener("click", clearHistory);
historySymbolFilter.addEventListener("change", loadHistory);
historyStatusFilter.addEventListener("change", loadHistory);
historyWindowFilter.addEventListener("change", loadHistory);
autoRefreshSelect.addEventListener("change", () => {
  saveSettings();
  scheduleAutoRefresh();
});
resultSortSelect.addEventListener("change", () => renderRows(latestRows, { markRun: false }));
chartSymbolSelect.addEventListener("change", () => renderChart(historyRows));
window.addEventListener("resize", () => renderChart(historyRows));
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    clearAutoRefresh("Auto refresh paused while this tab is hidden");
  } else if (autoRefreshMinutes() && latestRows.length) {
    scheduleAutoRefresh();
  }
});
tokenInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") saveToken();
});
queryButton.addEventListener("click", runQuery);

loadSettings();
renderSavedLists();
setRunExportState();
updateResultSummary([]);
renderHistorySummary(null);
updateFilteredHistoryLinks();
scheduleAutoRefresh();
loadStatus();
loadUniverses();
loadHistory();
