// ── State ────────────────────────────────────────────────────────────────────
let currentTaskId = 1;
let episodeActive = false;

const ACTION_DESCRIPTIONS = {
  resolve:  "Fully resolve the incident. Best outcome — contributes maximum score.",
  escalate: "Hand off to the on-call team. Partial credit; use when you can't resolve directly.",
  mitigate: "Apply a temporary fix. Resets the incident's age counter — prevents cascade in Task 3.",
  ignore:   "Take no action this step. Advances the clock without changing incident state.",
};

const SERVICE_ICONS = {
  auth:          "🔐",
  payments:      "💳",
  trading:       "📈",
  ui:            "🖥",
  database:      "🗄",
  "api-gateway": "🔀",
};

// ── Task tab selection ────────────────────────────────────────────────────────
document.querySelectorAll(".task-tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".task-tab").forEach(t => t.classList.remove("active"));
    tab.classList.add("active");
    currentTaskId = parseInt(tab.dataset.task);
    resetEnv();
  });
});

// ── Action description hint ───────────────────────────────────────────────────
document.getElementById("action-select").addEventListener("change", updateActionDesc);

function updateActionDesc() {
  const type = document.getElementById("action-select").value;
  document.getElementById("action-desc").textContent = ACTION_DESCRIPTIONS[type] || "";
}
updateActionDesc();

// ── API helpers ───────────────────────────────────────────────────────────────
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

  setStepBtnEnabled(false);
  try {
    const res = await fetch("/step", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type, incident_id }),
    });
    const data = await res.json();
    renderState(data.state);
    addLog(type, data.state, data.info);

    if (data.done) {
      episodeActive = false;
      showDoneModal(data.state.score, data.state, data.info);
    } else {
      setStepBtnEnabled(true);
    }
  } catch (err) {
    console.error("Step failed:", err);
    setStepBtnEnabled(true);
  }
}

// ── Render state ──────────────────────────────────────────────────────────────
function renderState(state) {
  renderStats(state);
  renderCards(state);
  renderDropdown(state);
  renderCascadeBanner(state);
}

function renderStats(state) {
  const taskNames = {
    1: "Single Alert Triage",
    2: "Multi-Service Queue",
    3: "Cascading Failure",
  };
  document.getElementById("stat-task").textContent = taskNames[state.task_id] || `Task ${state.task_id}`;
  document.getElementById("stat-step").textContent = `${state.step} / ${state.max_steps}`;
  document.getElementById("stat-score").textContent = state.score.toFixed(3);

  const resolved = state.incidents.filter(i => i.status === "resolved").length;
  document.getElementById("stat-resolved").textContent = `${resolved} / ${state.incidents.length}`;

  const scoreEl = document.getElementById("stat-score");
  scoreEl.style.color = scoreColor(state.score);
}

function renderCards(state) {
  const container = document.getElementById("incident-cards");
  const selectedId = document.getElementById("incident-select").value;
  document.getElementById("incident-count").textContent =
    `${state.incidents.length} incident${state.incidents.length !== 1 ? "s" : ""}`;

  if (!state.incidents.length) {
    container.innerHTML = '<div class="empty-state">No incidents.</div>';
    return;
  }

  container.innerHTML = state.incidents.map(inc => {
    const ageMax = currentTaskId === 3 ? 2 : 10;
    const agePct = Math.min(100, (inc.age / ageMax) * 100);
    const ageColor = agePct >= 100 ? "#ef4444" : agePct >= 60 ? "#f97316" : "#6c63ff";

    return `
      <div class="incident-card ${inc.status === "resolved" ? "resolved" : ""} ${inc.id === selectedId ? "selected" : ""}"
           data-severity="${inc.severity}"
           onclick="selectIncident('${inc.id}')">
        <div class="card-top">
          <span class="card-id">${inc.id}</span>
          ${inc.is_cascade ? '<span class="cascade-tag">CASCADE</span>' : ""}
        </div>
        <div class="card-service">
          <span class="service-icon">${SERVICE_ICONS[inc.service] || "⚙"}</span>
          ${inc.service}
        </div>
        <div class="card-badges">
          <span class="badge sev-${inc.severity}">${inc.severity}</span>
          <span class="badge status-${inc.status}">${inc.status}</span>
        </div>
        ${currentTaskId === 3 && inc.status === "open" ? `
        <div class="card-age">
          <span>Age ${inc.age}</span>
          <div class="age-bar-wrap">
            <div class="age-bar" style="width:${agePct}%;background:${ageColor}"></div>
          </div>
        </div>` : ""}
      </div>
    `;
  }).join("");
}

function renderDropdown(state) {
  const sel = document.getElementById("incident-select");
  const current = sel.value;
  const actionable = state.incidents.filter(i => i.status !== "resolved");

  sel.innerHTML = actionable.length
    ? actionable.map(inc =>
        `<option value="${inc.id}">${inc.id} — ${inc.service} (${inc.severity})</option>`
      ).join("")
    : '<option value="">No actionable incidents</option>';

  if (actionable.find(i => i.id === current)) sel.value = current;
}

function renderCascadeBanner(state) {
  if (currentTaskId !== 3) {
    document.getElementById("cascade-banner").classList.add("hidden");
    return;
  }
  const risky = state.incidents.filter(
    i => i.status === "open" && ["critical", "high"].includes(i.severity) && i.age >= 1
  );
  const banner = document.getElementById("cascade-banner");
  if (risky.length > 0) {
    banner.classList.remove("hidden");
    document.getElementById("cascade-detail").textContent =
      ` (${risky.map(i => i.id).join(", ")})`;
  } else {
    banner.classList.add("hidden");
  }
}

// ── Card click to select ──────────────────────────────────────────────────────
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
    const cascadeNote = info?.cascades_triggered?.length
      ? `<span class="log-cascade"> · ${info.cascades_triggered.length} cascade(s) triggered!</span>`
      : "";
    entry.innerHTML = `
      <div class="log-entry-top">
        <span class="log-action">${actionType} → ${info?.incident_id || "?"}</span>
        <span class="log-step">Step ${info?.step || "?"}</span>
      </div>
      <div class="log-detail">
        ${info?.incident_service || "?"} (${info?.incident_severity || "?"})
        · <span class="log-score">score ${state.score.toFixed(3)}</span>
        ${cascadeNote}
      </div>`;
  }

  log.insertBefore(entry, log.firstChild);
}

function clearLog() {
  document.getElementById("activity-log").innerHTML = '<div class="log-empty">No actions yet.</div>';
}

// ── Done modal ────────────────────────────────────────────────────────────────
function showDoneModal(score, state, _info) { // eslint-disable-line no-unused-vars
  const resolved = state.incidents.filter(i => i.status === "resolved").length;
  const total = state.incidents.length;
  const pct = Math.round(score * 100);

  const icon = score >= 0.8 ? "🏆" : score >= 0.5 ? "👍" : "📉";
  const msg = score >= 0.8
    ? `Excellent work! Resolved ${resolved}/${total} incidents with a strong score.`
    : score >= 0.5
    ? `Good effort. ${resolved}/${total} incidents handled. Room to improve priority order.`
    : `${resolved}/${total} incidents resolved. Try prioritising critical incidents first.`;

  document.getElementById("modal-icon").textContent = icon;
  document.getElementById("modal-title").textContent = "Episode Complete";
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
function scoreColor(score) {
  if (score >= 0.8) return "#22c55e";
  if (score >= 0.5) return "#eab308";
  return "#ef4444";
}

function setStepBtnEnabled(enabled) {
  document.getElementById("btn-step").disabled = !enabled;
}

// ── Init ──────────────────────────────────────────────────────────────────────
resetEnv();
