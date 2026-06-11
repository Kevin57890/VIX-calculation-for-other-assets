const tokenStatus = document.querySelector("#tokenStatus");
const tokenPanel = document.querySelector("#tokenPanel");
const tokenInput = document.querySelector("#tokenInput");
const tokenPreview = document.querySelector("#tokenPreview");
const tokenNote = document.querySelector("#tokenNote");
const switchTokenButton = document.querySelector("#switchTokenButton");
const saveTokenButton = document.querySelector("#saveTokenButton");
const symbolsInput = document.querySelector("#symbolsInput");
const presetChips = document.querySelector("#presetChips");
const modeSelect = document.querySelector("#modeSelect");
const fallbackSelect = document.querySelector("#fallbackSelect");
const strikeLimitInput = document.querySelector("#strikeLimitInput");
const quoteAgeInput = document.querySelector("#quoteAgeInput");
const spreadInput = document.querySelector("#spreadInput");
const delayInput = document.querySelector("#delayInput");
const allowStaleInput = document.querySelector("#allowStaleInput");
const allowExtrapolationInput = document.querySelector("#allowExtrapolationInput");
const queryButton = document.querySelector("#queryButton");
const queryButtonLabel = document.querySelector("#queryButtonLabel");
const resultsBody = document.querySelector("#resultsBody");
const lastRun = document.querySelector("#lastRun");
const historyBody = document.querySelector("#historyBody");
const historyNote = document.querySelector("#historyNote");
const refreshHistoryButton = document.querySelector("#refreshHistoryButton");

const mainValue = document.querySelector("#mainValue");
const mainSymbol = document.querySelector("#mainSymbol");
const mainStatus = document.querySelector("#mainStatus");
const mainExpirations = document.querySelector("#mainExpirations");
const mainAge = document.querySelector("#mainAge");
const mainForward = document.querySelector("#mainForward");
const mainK0 = document.querySelector("#mainK0");
const mainStrikes = document.querySelector("#mainStrikes");
const mainRates = document.querySelector("#mainRates");
let tokenConfigured = false;
let tokenPanelForcedOpen = false;

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
}

async function api(path, payload) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

async function loadStatus() {
  const response = await fetch("/api/status", { cache: "no-store" });
  const data = await response.json();
  setTokenStatus(
    data.tokenConfigured,
    data.tokenSource,
    data.tokenPreview,
    data.tokenFormatOk,
    data.tokenFormatReason
  );
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

function updateMain(row) {
  if (!row) {
    mainValue.textContent = "--";
    mainSymbol.textContent = "Waiting for query";
    mainStatus.textContent = "idle";
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

function renderRows(rows) {
  resultsBody.innerHTML = "";
  if (!rows.length) {
    resultsBody.innerHTML = '<tr><td colspan="6" class="empty">No results</td></tr>';
    updateMain(null);
    return;
  }

  for (const row of rows) {
    const tr = document.createElement("tr");
    const quoteAge =
      row.max_quote_age_minutes === null || row.max_quote_age_minutes === undefined
        ? "--"
        : `${escapeHtml(row.max_quote_age_minutes)} min`;
    tr.innerHTML = `
      <td><strong>${escapeHtml(row.symbol || "")}</strong></td>
      <td><span class="badge ${badgeClass(row.status)}">${escapeHtml(row.status || "")}</span></td>
      <td>${escapeHtml(formatValue(row.asset_vix_30d))}</td>
      <td>${escapeHtml(row.expirations || "--")}</td>
      <td>${quoteAge}</td>
      <td>${escapeHtml(row.reason || "")}</td>
    `;
    tr.addEventListener("click", () => updateMain(row));
    resultsBody.appendChild(tr);
  }

  updateMain(rows.find((row) => row.status === "ok") || rows[0]);
  lastRun.textContent = `Last run: ${new Date().toLocaleString()}`;
}

function renderHistory(rows) {
  historyBody.innerHTML = "";
  if (!rows.length) {
    historyBody.innerHTML = '<tr><td colspan="6" class="empty">No recorded calculations yet</td></tr>';
    historyNote.textContent = "Latest recorded calculations";
    return;
  }

  for (const row of rows.slice().reverse()) {
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
  historyNote.textContent = `${rows.length} latest rows saved locally`;
}

async function loadHistory() {
  try {
    const response = await fetch("/api/history?limit=25", { cache: "no-store" });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      throw new Error(data.error || "History request failed");
    }
    renderHistory(data.rows || []);
  } catch (error) {
    historyBody.innerHTML = `<tr><td colspan="6" class="empty">${escapeHtml(error.message)}</td></tr>`;
    historyNote.textContent = "History unavailable";
  }
}

function buildQueryPayload() {
  return {
    symbols: symbolsInput.value,
    mode: modeSelect.value,
    fallbackMode: fallbackSelect.value,
    maxage: "5min",
    strikeLimit: Number(strikeLimitInput.value || 120),
    maxQuoteAgeMinutes: Number(quoteAgeInput.value || 45),
    maxBidAskSpreadPct: Number(spreadInput.value || 200),
    requestDelaySeconds: Number(delayInput.value || 0.25),
    allowStale: allowStaleInput.checked,
    allowExtrapolation: allowExtrapolationInput.checked,
  };
}

async function runQuery() {
  if (!tokenConfigured) {
    openTokenPanel();
    return;
  }
  queryButton.disabled = true;
  queryButtonLabel.textContent = "Calculating...";
  try {
    const data = await api("/api/query", buildQueryPayload());
    renderRows(data.rows || []);
    await loadHistory();
  } catch (error) {
    resultsBody.innerHTML = `<tr><td colspan="6" class="empty">${escapeHtml(error.message)}</td></tr>`;
    updateMain({
      symbol: "ERROR",
      status: "error",
      asset_vix_30d: null,
      reason: error.message,
    });
  } finally {
    queryButton.disabled = false;
    queryButtonLabel.textContent = "Calculate";
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
  });
});

switchTokenButton.addEventListener("click", toggleTokenPanel);
saveTokenButton.addEventListener("click", saveToken);
refreshHistoryButton.addEventListener("click", loadHistory);
tokenInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") saveToken();
});
queryButton.addEventListener("click", runQuery);

loadStatus();
loadUniverses();
loadHistory();
