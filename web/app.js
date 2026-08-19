const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

const percent = new Intl.NumberFormat("en-US", {
  style: "percent",
  maximumFractionDigits: 2,
});

const metricLabels = [
  ["Deposited", "deposits", "money"],
  ["Withdrawn", "withdrawals", "money"],
  ["Net Invested", "net_deposits", "money"],
  ["Current Value", "current_value", "money"],
  ["Net Growth", "net_growth", "money"],
  ["Growth", "growth_percent", "percent"],
];

let currentState = null;
let toastTimer = null;

async function request(path, options = {}) {
  const token = localStorage.getItem("rogue_quant_token") || "";
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { "X-Rogue-Token": token } : {}),
    ...(options.headers || {}),
  };
  const response = await fetch(path, {
    ...options,
    headers,
  });
  const data = await response.json();

  if (response.status === 401) {
    const entered = window.prompt("Rogue Quant token");
    if (entered) {
      localStorage.setItem("rogue_quant_token", entered);
      return request(path, options);
    }
  }

  if (!response.ok) {
    throw new Error(data.error || "Request failed.");
  }

  return data;
}

async function loadState() {
  setStatus("Refreshing", "working");
  render(await request("/api/state"));
  setStatus("Ready", "success");
}

async function post(path, payload = {}) {
  setStatus("Working", "working");
  const data = await request(path, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  render(data);
  setStatus(data.message || "Ready", "success");

  return data;
}

function render(state) {
  currentState = state;
  renderMetrics(state.summary);
  renderService(state);
  renderSystem(state);
  document.getElementById("bot-symbols").textContent = state.service.symbols.join(", ");
  renderServiceHealth(state.service);
  renderControls(state.controls);
  renderChart(state.chart_data?.equity_curve || state.snapshots);
  renderRows("transactions-table", state.transactions, [
    ["type"],
    ["amount", money],
    ["note"],
    ["created_at", shortDate],
  ]);
  renderRows("trades-table", state.trades, [
    ["symbol"],
    ["side"],
    ["quantity", number],
    ["price", money],
    ["pnl", money],
  ]);
  renderRows("decisions-table", state.decisions, [
    ["symbol"],
    ["action"],
    ["confidence", decimal],
    ["executed", yesNo],
    ["reason"],
  ]);
  renderRows("strategies-table", state.strategies, [
    ["symbol"],
    ["strategy"],
    ["score", decimal],
    ["net_profit", money],
    ["win_rate", ratio],
    ["drawdown", ratio],
    ["trades"],
  ]);
  renderRows("alerts-table", state.alerts, [
    ["level"],
    ["message"],
    ["source"],
    ["created_at", shortDate],
  ]);
  renderRows("audit-table", state.audit_log, [
    ["action"],
    ["detail"],
    ["source"],
    ["created_at", shortDate],
  ]);
  renderRows("paper-live-table", state.paper_live, [
    ["symbol"],
    ["paper_action"],
    ["live_action"],
    ["paper_price", money],
    ["difference", money],
    ["reason"],
  ]);
  renderRows("opportunities-table", state.market_opportunities || [], [
    ["rank"],
    ["symbol"],
    ["action"],
    ["confidence", ratio],
    ["score", decimal],
    ["net_profit", money],
    ["win_rate", ratio],
    ["drawdown", ratio],
  ]);
}

function renderMetrics(summary) {
  document.getElementById("metrics").innerHTML = metricLabels
    .map(([label, key, kind]) => {
      const value = kind === "percent"
        ? percent.format(summary[key])
        : currency.format(summary[key]);
      return `<article class="metric-card"><span>${label}</span><strong>${value}</strong></article>`;
    })
    .join("");
}

function renderService(state) {
  const status = state.service.emergency_stop
    ? "Emergency stop active"
    : state.service.running
      ? "Bot running"
      : "Bot stopped";
  document.getElementById("service-status").textContent = status;
}

function renderServiceHealth(service) {
  document.getElementById("service-cycles").textContent = service.cycles_completed || 0;
  document.getElementById("service-errors").textContent = service.errors_total || 0;
  const detail = document.getElementById("service-detail");

  if (service.consecutive_errors) {
    detail.textContent = `Retrying after error: ${service.last_error || "Unknown error"}`;
    detail.dataset.tone = "error";
  } else if (service.last_success_at) {
    detail.textContent = `Last successful cycle: ${shortDate(service.last_success_at)}`;
    detail.dataset.tone = "success";
  } else {
    detail.textContent = service.running ? "First cycle is running." : "Waiting to start.";
    detail.dataset.tone = "idle";
  }
}

function renderSystem(state) {
  document.getElementById("deployment-mode").textContent = state.deployment_mode.name;
  document.getElementById("auth-mode").textContent = state.auth.required
    ? "Token required"
    : "Local open";
  document.getElementById("credential-mode").textContent = state.credential_status.kraken_configured
    ? "Kraken vault ready"
    : "Vault empty";
  document.getElementById("notification-mode").textContent = state.notification_channels.length
    ? state.notification_channels.join(", ")
    : "No channels";
  renderTargetAsset(state.target_asset);
  renderLiveReadiness(state.live_readiness);
}

function renderTargetAsset(target) {
  const ready = target.ready_for_live
    ? "Live ready"
    : target.ready_for_paper
      ? "Paper ready"
      : "Locked";

  document.getElementById("target-mode").textContent = `${target.asset} ${ready}`;
  document.getElementById("target-asset-symbol").textContent = target.symbol;
  document.getElementById("target-asset-balance").textContent = number(target.balance);
  document.getElementById("target-asset-value").textContent = money(target.estimated_usd);
  document.getElementById("target-asset-ready").textContent = ready;
}

function renderLiveReadiness(readiness) {
  const validation = readiness.paper_validation || {};
  const label = readiness.ready ? "Ready" : "Locked";
  const reason = readiness.reasons?.[0] || readiness.message;

  document.getElementById("live-gate-mode").textContent = label;
  document.getElementById("paper-cycles").textContent = validation.cycles || 0;
  document.getElementById("paper-closed-trades").textContent = validation.closed_trades || 0;
  document.getElementById("paper-growth").textContent = ratio(validation.growth_percent || 0);
  document.getElementById("paper-drawdown").textContent = ratio(validation.max_drawdown || 0);
  document.getElementById("live-gate-message").textContent = reason;
  document.getElementById("live-gate-message").dataset.ready = readiness.ready ? "true" : "false";
}

function renderControls(controls) {
  document.getElementById("max-order").value = controls.max_order_notional;
  document.getElementById("min-confidence").value = controls.min_signal_confidence;
  document.getElementById("loop-seconds").value = controls.loop_seconds;
}

function renderChart(snapshots) {
  const canvas = document.getElementById("value-chart");
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  const padding = 44;

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = "#101522";
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = "rgba(25, 230, 255, 0.16)";
  ctx.lineWidth = 1;
  for (let x = padding; x < width; x += 56) {
    ctx.beginPath();
    ctx.moveTo(x, padding);
    ctx.lineTo(x, height - padding);
    ctx.stroke();
  }
  for (let y = padding; y < height; y += 44) {
    ctx.beginPath();
    ctx.moveTo(padding, y);
    ctx.lineTo(width - padding, y);
    ctx.stroke();
  }

  if (!snapshots.length) {
    ctx.fillStyle = "#94a3b8";
    ctx.font = "16px Arial";
    ctx.textAlign = "center";
    ctx.fillText("Record a portfolio snapshot to start the chart.", width / 2, height / 2);
    return;
  }

  const values = snapshots.map((snapshot) => snapshot.total_value ?? snapshot.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 1);

  const points = values.map((value, index) => {
    const x = padding + (index / Math.max(values.length - 1, 1)) * (width - padding * 2);
    const y = height - padding - ((value - min) / range) * (height - padding * 2);
    return [x, y];
  });

  ctx.beginPath();
  points.forEach(([x, y], index) => {
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.lineTo(points.at(-1)[0], height - padding);
  ctx.lineTo(points[0][0], height - padding);
  ctx.closePath();
  ctx.fillStyle = "rgba(124, 60, 255, 0.18)";
  ctx.fill();

  ctx.beginPath();
  points.forEach(([x, y], index) => {
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.strokeStyle = "#39ff88";
  ctx.lineWidth = 3;
  ctx.stroke();

  ctx.fillStyle = "#94a3b8";
  ctx.font = "12px Courier New";
  ctx.textAlign = "left";
  ctx.fillText(currency.format(max), padding, 24);
  ctx.fillText(currency.format(min), padding, height - 14);
}

function renderRows(id, rows, columns) {
  const body = document.getElementById(id);
  body.innerHTML = rows.length
    ? rows.map((row) => {
      const cells = columns.map(([key, formatter]) => {
        const value = formatter ? formatter(row[key]) : row[key];
        return `<td>${escapeHtml(value ?? "")}</td>`;
      }).join("");
      return `<tr>${cells}</tr>`;
    }).join("")
    : `<tr><td colspan="${columns.length}">No records yet.</td></tr>`;
}

function money(value) {
  return currency.format(Number(value || 0));
}

function number(value) {
  return Number(value || 0).toFixed(8);
}

function decimal(value) {
  return Number(value || 0).toFixed(2);
}

function ratio(value) {
  return percent.format(Number(value || 0));
}

function yesNo(value) {
  return value ? "yes" : "no";
}

function shortDate(value) {
  return String(value || "").slice(0, 19).replace("T", " ");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function setStatus(message, tone = "info") {
  const line = document.getElementById("status-line");
  line.textContent = message;
  line.dataset.tone = tone;
}

function showToast(message, tone = "info") {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.dataset.tone = tone;
  toast.classList.add("visible");

  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => {
    toast.classList.remove("visible");
  }, 2600);
}

function amountPayload(amountId, noteId = null) {
  return {
    amount: document.getElementById(amountId).value,
    note: noteId ? document.getElementById(noteId).value : "",
  };
}

function settingsPayload() {
  return {
    max_order_notional: document.getElementById("max-order").value,
    min_signal_confidence: document.getElementById("min-confidence").value,
    loop_seconds: document.getElementById("loop-seconds").value,
  };
}

function scanPayload() {
  return {
    scan_limit: document.getElementById("scan-limit").value,
    active_limit: document.getElementById("active-limit").value,
  };
}

function credentialsPayload() {
  return {
    api_key: document.getElementById("kraken-api-key").value,
    api_secret: document.getElementById("kraken-api-secret").value,
  };
}

async function saveCredentials() {
  const data = await post("/api/credentials/kraken", credentialsPayload());
  document.getElementById("kraken-api-key").value = "";
  document.getElementById("kraken-api-secret").value = "";
  return data;
}

async function runAction(button, busyLabel, task) {
  if (button.disabled) return;

  const originalLabel = button.dataset.label || button.textContent;
  button.dataset.label = originalLabel;
  button.disabled = true;
  button.textContent = busyLabel;
  button.classList.add("is-loading");
  button.classList.remove("is-success", "is-error");
  button.setAttribute("aria-busy", "true");

  try {
    const data = await task();
    button.classList.remove("is-loading");
    button.classList.add("is-success");
    showToast(data?.message || "Action completed.", "success");
  } catch (error) {
    button.classList.remove("is-loading");
    button.classList.add("is-error");
    setStatus(error.message, "error");
    showToast(error.message, "error");
  } finally {
    button.removeAttribute("aria-busy");
    window.setTimeout(() => {
      button.disabled = false;
      button.textContent = originalLabel;
      button.classList.remove("is-loading");
    }, 350);
    window.setTimeout(() => {
      button.classList.remove("is-success", "is-error");
    }, 1400);
  }
}

function bindAction(id, busyLabel, task) {
  const button = document.getElementById(id);
  button.addEventListener("click", () => runAction(button, busyLabel, task));
}

function bindPressFeedback() {
  document.querySelectorAll(".button").forEach((button) => {
    button.addEventListener("pointerdown", () => {
      if (!button.disabled) button.classList.add("is-pressed");
    });
    ["pointerup", "pointercancel", "pointerleave", "blur"].forEach((event) => {
      button.addEventListener(event, () => {
        button.classList.remove("is-pressed");
      });
    });
  });
}

function ensureToast() {
  if (document.getElementById("toast")) return;

  const toast = document.createElement("div");
  toast.id = "toast";
  toast.className = "toast";
  toast.setAttribute("role", "status");
  toast.setAttribute("aria-live", "polite");
  document.body.appendChild(toast);
}

function bindActions() {
  bindPressFeedback();
  bindAction("refresh-button", "Refreshing", loadState);
  bindAction("deposit-button", "Adding", () => post("/api/deposits", amountPayload("ledger-amount", "ledger-note")));
  bindAction("withdraw-button", "Withdrawing", () => post("/api/withdrawals", amountPayload("ledger-amount", "ledger-note")));
  bindAction("manual-snapshot-button", "Recording", () => post("/api/snapshots/manual", amountPayload("manual-value")));
  bindAction("kraken-snapshot-button", "Checking", () => post("/api/snapshots/kraken"));
  bindAction("run-cycle-button", "Running", () => post("/api/trading/run-once"));
  bindAction("start-bot-button", "Starting", () => post("/api/bot/start"));
  bindAction("stop-bot-button", "Stopping", () => post("/api/bot/stop"));
  bindAction("emergency-button", "Stopping", () => post("/api/emergency-stop"));
  bindAction("resume-button", "Resuming", () => post("/api/resume"));
  bindAction("save-settings-button", "Saving", () => post("/api/settings", settingsPayload()));
  bindAction("save-credentials-button", "Encrypting", saveCredentials);
  bindAction("check-kraken-button", "Checking", () => post("/api/kraken/check"));
  bindAction("use-target-button", "Switching", () => post("/api/kraken/use-target"));
  bindAction("scan-markets-button", "Analyzing", () => post("/api/markets/scan", scanPayload()));
}

window.addEventListener("DOMContentLoaded", () => {
  ensureToast();
  bindActions();
  loadState().catch((error) => {
    setStatus(error.message, "error");
    showToast(error.message, "error");
  });
});
