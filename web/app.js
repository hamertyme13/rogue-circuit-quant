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

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();

  if (!response.ok) {
    throw new Error(data.error || "Request failed.");
  }

  return data;
}

async function loadState() {
  setStatus("Refreshing");
  render(await request("/api/state"));
  setStatus("Ready");
}

async function post(path, payload = {}) {
  setStatus("Working");
  const data = await request(path, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  render(data);
  setStatus(data.message || "Ready");
}

function render(state) {
  currentState = state;
  renderMetrics(state.summary);
  renderService(state);
  renderControls(state.controls);
  renderChart(state.snapshots);
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

  const values = snapshots.map((snapshot) => snapshot.total_value);
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

function setStatus(message) {
  document.getElementById("status-line").textContent = message;
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

function bindActions() {
  document.getElementById("refresh-button").addEventListener("click", loadState);
  document.getElementById("deposit-button").addEventListener("click", () => post("/api/deposits", amountPayload("ledger-amount", "ledger-note")));
  document.getElementById("withdraw-button").addEventListener("click", () => post("/api/withdrawals", amountPayload("ledger-amount", "ledger-note")));
  document.getElementById("manual-snapshot-button").addEventListener("click", () => post("/api/snapshots/manual", amountPayload("manual-value")));
  document.getElementById("kraken-snapshot-button").addEventListener("click", () => post("/api/snapshots/kraken"));
  document.getElementById("run-cycle-button").addEventListener("click", () => post("/api/trading/run-once"));
  document.getElementById("start-bot-button").addEventListener("click", () => post("/api/bot/start"));
  document.getElementById("stop-bot-button").addEventListener("click", () => post("/api/bot/stop"));
  document.getElementById("emergency-button").addEventListener("click", () => post("/api/emergency-stop"));
  document.getElementById("resume-button").addEventListener("click", () => post("/api/resume"));
  document.getElementById("save-settings-button").addEventListener("click", () => post("/api/settings", settingsPayload()));
}

window.addEventListener("DOMContentLoaded", () => {
  bindActions();
  loadState().catch((error) => setStatus(error.message));
});
