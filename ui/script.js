// ── State ────────────────────────────────────────────────────────────────────
let currentTaskId = 1;
let episodeActive = false;

const ACTION_DESCRIPTIONS = {
  resolve:           "Fully resolve the incident. Multi-step incidents need multiple resolves.",
  investigate:       "Identify root cause (fill in hypothesis), or leave blank to check for false alarms.",
  triage:            "Classify severity and assign to the right team. Infer team from logs and metrics.",
  execute_fix:       "Apply fixes in the correct order. Review logs to determine valid fix sequence.",
  write_postmortem:  "Write a post-mortem covering root cause, timeline, prevention steps, and action items.",
  escalate:          "Hand off to on-call team. Partial score credit (50%). Acknowledges the incident.",
  mitigate:          "Temporary fix — resets age, prevents cascade for 2 steps (Task 3).",
  ignore:            "No action. Incident ages, SLA ticks down, severity may escalate.",
};

const SERVICE_ICONS = {
  auth: "🔐", payments: "💳", trading: "📈",
  ui: "🖥", database: "🗄", "api-gateway": "🔀",
};

const SERVICE_IMPACT_LABEL = {
  payments: "1.5×", trading: "1.4×", database: "1.3×",
  auth: "1.2×", "api-gateway": "1.1×", ui: "1.0×",
};

const TASK_NAMES = {
  1: "Single Alert Triage",
  2: "Multi-Service Queue",
  3: "Cascading Failure",
  4: "Full Incident Lifecycle",
};

// Task 4 action payloads — only some actions need extra fields
const PAYLOAD_ACTIONS = ["triage", "investigate", "execute_fix", "write_postmortem"];

// ── Task tab selection ────────────────────────────────────────────────────────
document.querySelectorAll(".task-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".task-tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    currentTaskId = parseInt(tab.dataset.task);
    resetEnv();
  });
});

// ── Action select → update desc + payload fields ──────────────────────────────
document.getElementById("action-select").addEventListener("change", onActionChange);

function onActionChange() {
  const type = document.getElementById("action-select").value;
  document.getElementById("action-desc").textContent = ACTION_DESCRIPTIONS[type] || "";

  // Show/hide payload panels
  PAYLOAD_ACTIONS.forEach(a => {
    const el = document.getElementById(`payload-${a}`);
    if (el) el.classList.toggle("hidden", a !== type);
  });
}
onActionChange();

// ── API ───────────────────────────────────────────────────────────────────────
async function resetEnv() {
  setStepBtnEnabled(false);
  try {
    const res = await fetch("/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: currentTaskId }),
    });
    const state = await res.json();
    episodeActive = true;
    closeModal();
    clearLog();
    document.getElementById("btn-step").textContent = "Execute Action";
    renderState(state);
    addLog(null, state, null);
    setStepBtnEnabled(true);
  } catch (err) {
    console.error("Reset failed:", err);
  }
}

async function stepEnv() {
  if (!episodeActive) return;
  const incident_id = document.getElementById("incident-select").value;
  const type = document.getElementById("action-select").value;
  if (!incident_id) { alert("Select an incident first."); return; }

  const body = { type, incident_id, ...buildPayload(type) };

  setStepBtnEnabled(false);
  try {
    const res = await fetch("/step", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    renderState(data.state);
    addLog(type, data.state, data.info);
    updateActionDropdown(data.state.available_actions);

    if (data.done) {
      episodeActive = false;
      showDoneModal(data.state.score, data.state);
    } else {
      setStepBtnEnabled(true);
    }
  } catch (err) {
    console.error("Step failed:", err);
    setStepBtnEnabled(true);
  }
}

function buildPayload(type) {
  if (type === "triage") {
    return {
      severity: document.getElementById("triage-severity").value,
      team:     document.getElementById("triage-team").value,
    };
  }
  if (type === "investigate") {
    const rc = document.getElementById("investigate-rootcause").value.trim();
    return rc ? { root_cause: rc } : {};
  }
  if (type === "execute_fix") {
    const raw = document.getElementById("fix-list").value;
    const fixes = raw.split(",").map(s => s.trim()).filter(Boolean);
    return { fixes };
  }
  if (type === "write_postmortem") {
    return { postmortem: document.getElementById("postmortem-text").value };
  }
  return {};
}

// ── Render ────────────────────────────────────────────────────────────────────
function renderState(state) {
  renderStats(state);
  renderCards(state);
  renderDropdown(state);
  renderBanners(state);
  updateActionDropdown(state.available_actions || []);
}

function renderStats(state) {
  document.getElementById("stat-task").textContent = TASK_NAMES[state.task_id] || `Task ${state.task_id}`;
  document.getElementById("stat-step").textContent = `${state.step} / ${state.max_steps}`;

  const scoreEl = document.getElementById("stat-score");
  scoreEl.textContent = state.score.toFixed(3);
  scoreEl.style.color = scoreColor(state.score);

  const resolved = state.incidents.filter(i => i.status === "resolved").length;
  document.getElementById("stat-resolved").textContent = `${resolved} / ${state.incidents.length}`;

  const slaEl = document.getElementById("stat-sla");
  slaEl.textContent = state.sla_breaches;
  slaEl.style.color = state.sla_breaches > 0 ? "#ef4444" : "var(--text)";
}

function renderCards(state) {
  const container = document.getElementById("incident-cards");
  const selectedId = document.getElementById("incident-select").value;
  const n = state.incidents.length;
  document.getElementById("incident-count").textContent = `${n} incident${n !== 1 ? "s" : ""}`;

  if (!n) { container.innerHTML = '<div class="empty-state">No incidents.</div>'; return; }
  container.innerHTML = state.incidents.map(inc => cardHTML(inc, state, selectedId)).join("");
}

function cardHTML(inc, state, selectedId) {
  const terminal  = ["resolved", "dismissed"];
  const isTerminal = terminal.includes(inc.status);
  const isSelected = inc.id === selectedId;

  const slaRemaining = inc.sla_deadline - state.step;
  const slaMax = { critical: 4, high: 6, medium: 10, low: 15 }[inc.severity] || 10;
  const slaPct = Math.max(0, Math.min(100, (slaRemaining / slaMax) * 100));
  const slaColor = slaRemaining <= 1 ? "#ef4444" : slaRemaining <= 2 ? "#f97316" : "#22c55e";

  const agePct = Math.min(100, (inc.age / 2) * 100);
  const ageColor = agePct >= 100 ? "#ef4444" : agePct >= 60 ? "#f97316" : "#6c63ff";

  const progressPct = inc.resolution_steps > 1
    ? Math.round((inc.resolution_progress / inc.resolution_steps) * 100) : 0;

  // Tags
  const tags = [];
  if (inc.is_cascade)    tags.push('<span class="inc-tag tag-cascade">CASCADE</span>');
  if (!inc.confirmed)    tags.push('<span class="inc-tag tag-unconfirmed">UNCONFIRMED</span>');
  if (inc.is_root_cause) tags.push('<span class="inc-tag tag-rootcause">ROOT CAUSE</span>');
  if (inc.root_cause_id) tags.push('<span class="inc-tag tag-symptom">SYMPTOM</span>');
  if (inc.sla_breached)  tags.push('<span class="inc-tag tag-sla">SLA BREACHED</span>');
  if (!inc.acknowledged && !isTerminal && ["critical","high"].includes(inc.severity))
                         tags.push('<span class="inc-tag tag-unack">UNACKED</span>');

  // Task 4 lifecycle progress pills
  let lifecyclePills = "";
  if (state.task_id === 4) {
    const stages = [
      { key: "triage_done",      label: "Triage" },
      { key: "root_cause_found", label: "Root Cause" },
      { key: "remediation_done", label: "Remediation" },
      { key: "postmortem_done",  label: "Post-Mortem" },
    ];
    lifecyclePills = `<div class="lifecycle-pills">
      ${stages.map(s =>
        `<span class="lc-pill ${inc[s.key] ? "lc-done" : "lc-pending"}">${s.label}</span>`
      ).join("")}
    </div>`;
  }

  // Metrics snippet (show top 3)
  let metricsHTML = "";
  if (inc.metrics && Object.keys(inc.metrics).length) {
    const entries = Object.entries(inc.metrics).slice(0, 3);
    metricsHTML = `<div class="card-metrics">
      ${entries.map(([k, v]) =>
        `<span class="metric-chip"><span class="metric-key">${k.replace(/_/g," ")}</span> ${v}</span>`
      ).join("")}
    </div>`;
  }

  // Logs (collapsible, show first 2 lines)
  let logsHTML = "";
  if (inc.logs && inc.logs.length) {
    logsHTML = `
      <details class="card-logs">
        <summary>Logs (${inc.logs.length})</summary>
        <pre class="log-pre">${inc.logs.map(l => escapeHTML(l)).join("\n")}</pre>
      </details>`;
  }

  return `
    <div class="incident-card ${isTerminal ? "terminal" : ""} ${isSelected ? "selected" : ""} ${inc.sla_breached ? "sla-breached" : ""}"
         data-severity="${inc.severity}"
         onclick="selectIncident('${inc.id}')">

      <div class="card-top">
        <span class="card-id">${inc.id}</span>
        <div class="card-tags">${tags.join("")}</div>
      </div>

      ${inc.title ? `<div class="card-title">${escapeHTML(inc.title)}</div>` : ""}

      <div class="card-service">
        <span class="service-icon">${SERVICE_ICONS[inc.service] || "⚙"}</span>
        ${inc.service}
        <span class="service-impact">${SERVICE_IMPACT_LABEL[inc.service] || ""}</span>
      </div>

      <div class="card-badges">
        <span class="badge sev-${inc.severity}">${inc.severity}</span>
        <span class="badge status-${inc.status}">${inc.status.replace("_"," ")}</span>
      </div>

      ${lifecyclePills}
      ${metricsHTML}

      ${inc.resolution_steps > 1 ? `
      <div class="progress-row">
        <span class="progress-label">Resolution ${inc.resolution_progress}/${inc.resolution_steps}</span>
        <div class="progress-bar-wrap"><div class="progress-bar" style="width:${progressPct}%"></div></div>
      </div>` : ""}

      ${!isTerminal ? `
      <div class="sla-row ${inc.sla_breached ? "sla-row-breached" : ""}">
        <span class="sla-label">${inc.sla_breached ? "SLA ✗" : `SLA ${slaRemaining}s`}</span>
        <div class="sla-bar-wrap"><div class="sla-bar" style="width:${slaPct}%;background:${slaColor}"></div></div>
      </div>` : ""}

      ${currentTaskId === 3 && inc.status === "open" ? `
      <div class="age-row">
        <span class="age-label">Age ${inc.age}</span>
        <div class="age-bar-wrap"><div class="age-bar" style="width:${agePct}%;background:${ageColor}"></div></div>
      </div>` : ""}

      ${logsHTML}
    </div>`;
}

function renderDropdown(state) {
  const sel = document.getElementById("incident-select");
  const current = sel.value;
  const actionable = state.incidents.filter(i => !["resolved","dismissed"].includes(i.status));

  sel.innerHTML = actionable.length
    ? actionable.map(inc =>
        `<option value="${inc.id}">${inc.id} — ${inc.service} (${inc.severity}${!inc.confirmed ? ", ?" : ""})</option>`
      ).join("")
    : '<option value="">No actionable incidents</option>';

  if (actionable.find(i => i.id === current)) sel.value = current;
}

function renderBanners(state) {
  const banner = document.getElementById("cascade-banner");
  if (currentTaskId === 3) {
    const risky = state.incidents.filter(
      i => i.status === "open" && ["critical","high"].includes(i.severity) && i.age >= 1
    );
    if (risky.length) {
      banner.classList.remove("hidden");
      document.getElementById("cascade-detail").textContent = ` (${risky.map(i => i.id).join(", ")})`;
    } else {
      banner.classList.add("hidden");
    }
  } else {
    banner.classList.add("hidden");
  }
}

function updateActionDropdown(availableActions) {
  const sel = document.getElementById("action-select");
  [...sel.options].forEach(opt => {
    if (!availableActions || availableActions.length === 0) {
      opt.classList.remove("action-suggested");
      return;
    }
    opt.classList.toggle("action-suggested", availableActions.includes(opt.value));
  });
}

// ── Card click ────────────────────────────────────────────────────────────────
function selectIncident(id) {
  const sel = document.getElementById("incident-select");
  if ([...sel.options].find(o => o.value === id)) {
    sel.value = id;
    document.querySelectorAll(".incident-card").forEach(card => {
      card.classList.toggle("selected", card.querySelector(".card-id")?.textContent === id);
    });
  }
}

// ── Activity log ──────────────────────────────────────────────────────────────
function addLog(actionType, state, info) {
  const log = document.getElementById("activity-log");
  const empty = log.querySelector(".log-empty");
  if (empty) empty.remove();

  const entry = document.createElement("div");
  entry.className = "log-entry";

  if (!actionType) {
    entry.innerHTML = `
      <div class="log-entry-top">
        <span class="log-action">Episode started</span>
        <span class="log-step">Task ${state.task_id}</span>
      </div>
      <div class="log-detail">${state.incidents.length} incident(s) generated</div>`;
  } else {
    const notes = [];
    if (info?.grader_feedback)                notes.push(`<span class="log-good">${escapeHTML(info.grader_feedback)}</span>`);
    if (info?.cascades_triggered?.length)     notes.push(`<span class="log-cascade">+${info.cascades_triggered.length} cascade(s)</span>`);
    if (info?.auto_escalated?.length)         notes.push(`<span class="log-warn">sev escalated: ${info.auto_escalated.join(", ")}</span>`);
    if (info?.sla_breached_this_step?.length) notes.push(`<span class="log-breach">SLA breach: ${info.sla_breached_this_step.join(", ")}</span>`);
    if (info?.root_cause_resolved?.length)    notes.push(`<span class="log-good">auto-resolved: ${info.root_cause_resolved.join(", ")}</span>`);
    if (info?.new_arrivals?.length)           notes.push(`<span class="log-warn">new: ${info.new_arrivals.join(", ")}</span>`);
    if (info?.ack_auto_escalated?.length)     notes.push(`<span class="log-breach">unacked escalated: ${info.ack_auto_escalated.join(", ")}</span>`);
    if (info?.false_alarm_revealed)           notes.push(`<span class="log-good">false alarm revealed</span>`);

    entry.innerHTML = `
      <div class="log-entry-top">
        <span class="log-action">${actionType.replace("_"," ")} → ${info?.incident_id || "?"}</span>
        <span class="log-step">Step ${info?.step || "?"}</span>
      </div>
      <div class="log-detail">
        ${info?.incident_service || "?"} (${info?.severity_before || info?.incident_severity || "?"})
        · <span class="log-score">score ${state.score.toFixed(3)}</span>
      </div>
      ${notes.length ? `<div class="log-notes">${notes.join(" · ")}</div>` : ""}`;
  }

  log.insertBefore(entry, log.firstChild);
}

function clearLog() {
  document.getElementById("activity-log").innerHTML = '<div class="log-empty">No actions yet.</div>';
}

// ── Done modal ────────────────────────────────────────────────────────────────
function showDoneModal(score, state) {
  const resolved = state.incidents.filter(i => i.status === "resolved").length;
  const total    = state.incidents.length;
  const pct      = Math.round(score * 100);
  const slaNote  = state.sla_breaches > 0 ? ` ${state.sla_breaches} SLA breach(es).` : "";

  const icon = score >= 0.8 ? "🏆" : score >= 0.5 ? "👍" : "📉";
  const msg = score >= 0.8
    ? `Excellent — ${resolved}/${total} handled cleanly.${slaNote}`
    : score >= 0.5
    ? `${resolved}/${total} handled. Prioritise criticals and watch SLAs.${slaNote}`
    : `${resolved}/${total} resolved. For Task 4: triage → investigate → fix → postmortem → resolve.${slaNote}`;

  document.getElementById("modal-icon").textContent = icon;
  document.getElementById("final-score").textContent = score.toFixed(3);
  document.getElementById("final-score").style.color = scoreColor(score);
  document.getElementById("modal-message").textContent = msg;

  const bar = document.getElementById("final-score-bar");
  bar.style.width = "0%";
  bar.style.background = scoreColor(score);
  setTimeout(() => { bar.style.width = pct + "%"; }, 50);

  document.getElementById("done-overlay").classList.remove("hidden");
}

function closeModal() {
  document.getElementById("done-overlay").classList.add("hidden");
  if (!episodeActive) {
    const btn = document.getElementById("btn-step");
    btn.disabled = true;
    btn.textContent = "Episode Over — Start New Episode";
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function scoreColor(s) {
  return s >= 0.8 ? "#22c55e" : s >= 0.5 ? "#eab308" : "#ef4444";
}

function setStepBtnEnabled(enabled) {
  document.getElementById("btn-step").disabled = !enabled;
}

function escapeHTML(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Init ──────────────────────────────────────────────────────────────────────
resetEnv();
