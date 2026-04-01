const state = {
  tasks: [],
  currentTask: "odisha_survival",
  observation: null,
  suggestedAction: null,
  autoTimer: null,
  done: false,
};

const el = {
  serverStatus: document.getElementById("serverStatus"),
  taskSelect: document.getElementById("taskSelect"),
  taskHint: document.getElementById("taskHint"),
  resetBtn: document.getElementById("resetBtn"),
  gradeBtn: document.getElementById("gradeBtn"),
  stepBtn: document.getElementById("stepBtn"),
  runDayBtn: document.getElementById("runDayBtn"),
  autoBtn: document.getElementById("autoBtn"),
  aiSuggestBtn: document.getElementById("aiSuggestBtn"),
  applyAiBtn: document.getElementById("applyAiBtn"),
  aiNote: document.getElementById("aiNote"),
  aiStatus: document.getElementById("aiStatus"),
  aiActionPreview: document.getElementById("aiActionPreview"),
  releaseWater: document.getElementById("releaseWater"),
  releaseVal: document.getElementById("releaseVal"),
  rewardHint: document.getElementById("rewardHint"),
  mTank: document.getElementById("mTank"),
  mDemand: document.getElementById("mDemand"),
  mChlorine: document.getElementById("mChlorine"),
  mScore: document.getElementById("mScore"),
  mStep: document.getElementById("mStep"),
  mDay: document.getElementById("mDay"),
  mSeason: document.getElementById("mSeason"),
  mSupply: document.getElementById("mSupply"),
  tankBar: document.getElementById("tankBar"),
  tankPercent: document.getElementById("tankPercent"),
  logBox: document.getElementById("logBox"),
  pumpOn: document.getElementById("pumpOn"),
  harvesterOn: document.getElementById("harvesterOn"),
  chlorinate: document.getElementById("chlorinate"),
  checkLeak: document.getElementById("checkLeak"),
};

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json();
}

function log(message, cls = "") {
  const line = document.createElement("div");
  line.className = `log-line ${cls}`.trim();
  const ts = new Date().toLocaleTimeString();
  line.textContent = `[${ts}] ${message}`;
  el.logBox.prepend(line);
}

function setStatus(text, ok = true) {
  el.serverStatus.textContent = text;
  el.serverStatus.style.borderColor = ok ? "rgba(0, 194, 168, 0.55)" : "rgba(255, 91, 122, 0.65)";
  el.serverStatus.style.color = ok ? "#95ffcb" : "#ff9ab1";
}

function updateTaskHint() {
  const current = state.tasks.find((t) => t.id === state.currentTask);
  el.taskHint.textContent = current ? current.description : "";
}

function updateObservation(observation, reward = null) {
  state.observation = observation;
  if (!observation) return;

  const tankPct = Math.max(0, Math.min(100, (observation.tank_level / 2000) * 100));
  el.mTank.textContent = `${observation.tank_level.toFixed(1)} L`;
  el.mDemand.textContent = `${observation.forecasted_demand.toFixed(1)} L`;
  el.mChlorine.textContent = `${observation.chlorine_level.toFixed(2)} mg/L`;
  el.mScore.textContent = observation.cumulative_reward.toFixed(2);
  el.mStep.textContent = String(observation.step_of_episode);
  el.mDay.textContent = String(observation.day_of_episode);
  el.mSeason.textContent = `${observation.season} • ${observation.time_of_day}:00`;
  el.mSupply.textContent = `${observation.municipal_supply_active ? "Supply ON" : "Supply OFF"} | ${observation.power_active ? "Power ON" : "Power OFF"}`;
  el.tankPercent.textContent = `${tankPct.toFixed(1)}%`;
  el.tankBar.style.width = `${tankPct}%`;

  if (reward !== null) {
    el.rewardHint.textContent = `Reward: ${Number(reward).toFixed(3)}`;
  }
}

function getActionFromControls() {
  return {
    pump_on: el.pumpOn.checked,
    release_water: Number(el.releaseWater.value),
    chlorinate: el.chlorinate.checked,
    check_leak: el.checkLeak.checked,
    harvester_on: el.harvesterOn.checked,
  };
}

function setControlsFromAction(action) {
  el.pumpOn.checked = Boolean(action.pump_on);
  el.releaseWater.value = Number(action.release_water || 0);
  el.releaseVal.textContent = String(el.releaseWater.value);
  el.chlorinate.checked = Boolean(action.chlorinate);
  el.checkLeak.checked = Boolean(action.check_leak);
  el.harvesterOn.checked = Boolean(action.harvester_on);
}

async function refreshHealth() {
  try {
    const health = await api("/health");
    setStatus(`Server Ready • Task: ${health.task_id} • Step: ${health.step}`, true);
  } catch {
    setStatus("Server Offline", false);
  }
}

async function loadTasks() {
  const data = await api("/api/tasks");
  state.tasks = data.tasks || [];
  el.taskSelect.innerHTML = "";
  for (const task of state.tasks) {
    const option = document.createElement("option");
    option.value = task.id;
    option.textContent = task.name || task.id;
    el.taskSelect.appendChild(option);
  }
  const hasDefault = state.tasks.some((task) => task.id === state.currentTask);
  if (!hasDefault && state.tasks.length > 0) {
    state.currentTask = state.tasks[0].id;
  }
  el.taskSelect.value = state.currentTask;
  updateTaskHint();
}

async function resetEpisode() {
  state.currentTask = el.taskSelect.value;
  const data = await api(`/reset?task_id=${encodeURIComponent(state.currentTask)}`, { method: "POST" });
  state.done = false;
  updateObservation(data.observation);
  log(`Episode reset for task "${state.currentTask}".`, "success");
}

async function runStep() {
  if (state.done) {
    log("Episode already finished. Reset to continue.", "warn");
    return;
  }
  const payload = getActionFromControls();
  const data = await api("/step", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  updateObservation(data.observation, data.reward);
  state.done = Boolean(data.done);
  if (data.done) {
    log(`Episode completed after ${data.observation.step_of_episode} steps.`, "success");
    stopAuto();
  }
}

async function runDay() {
  for (let i = 0; i < 24; i += 1) {
    if (state.done) break;
    await runStep();
    await new Promise((resolve) => setTimeout(resolve, 45));
  }
}

function startAuto() {
  if (state.autoTimer) return;
  state.autoTimer = setInterval(async () => {
    try {
      await runStep();
    } catch (error) {
      log(`Auto run error: ${error.message}`, "error");
      stopAuto();
    }
  }, 250);
  el.autoBtn.textContent = "Stop Auto";
  log("Auto run started.");
}

function stopAuto() {
  if (state.autoTimer) {
    clearInterval(state.autoTimer);
    state.autoTimer = null;
    el.autoBtn.textContent = "Auto Run";
    log("Auto run stopped.");
  }
}

async function gradeEpisode() {
  const data = await api("/grader", {
    method: "POST",
    body: JSON.stringify({ task_id: state.currentTask }),
  });
  log(`Grader score for ${state.currentTask}: ${Number(data.score).toFixed(4)}`, "success");
}

async function suggestAction() {
  const payload = {
    task_id: state.currentTask,
    note: el.aiNote.value.trim(),
    observation: state.observation,
  };
  const data = await api("/api/ai/suggest-action", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  state.suggestedAction = data.action;
  el.aiStatus.textContent = `Source: ${data.source}${data.reasoning ? ` | ${data.reasoning}` : ""}`;
  el.aiActionPreview.textContent = JSON.stringify(data.action, null, 2);
  log(`AI suggestion received (${data.source}).`, data.source === "fallback" ? "warn" : "success");
}

function bindEvents() {
  el.taskSelect.addEventListener("change", () => {
    state.currentTask = el.taskSelect.value;
    updateTaskHint();
  });
  el.releaseWater.addEventListener("input", () => {
    el.releaseVal.textContent = el.releaseWater.value;
  });
  el.resetBtn.addEventListener("click", async () => {
    try {
      await resetEpisode();
    } catch (error) {
      log(`Reset failed: ${error.message}`, "error");
    }
  });
  el.stepBtn.addEventListener("click", async () => {
    try {
      await runStep();
    } catch (error) {
      log(`Step failed: ${error.message}`, "error");
    }
  });
  el.runDayBtn.addEventListener("click", async () => {
    try {
      await runDay();
    } catch (error) {
      log(`Run day failed: ${error.message}`, "error");
    }
  });
  el.autoBtn.addEventListener("click", () => {
    if (state.autoTimer) {
      stopAuto();
    } else {
      startAuto();
    }
  });
  el.gradeBtn.addEventListener("click", async () => {
    try {
      await gradeEpisode();
    } catch (error) {
      log(`Grader failed: ${error.message}`, "error");
    }
  });
  el.aiSuggestBtn.addEventListener("click", async () => {
    try {
      await suggestAction();
    } catch (error) {
      log(`AI suggestion failed: ${error.message}`, "error");
    }
  });
  el.applyAiBtn.addEventListener("click", () => {
    if (!state.suggestedAction) {
      log("No AI action to apply yet.", "warn");
      return;
    }
    setControlsFromAction(state.suggestedAction);
    log("Applied AI suggestion to controls.");
  });
}

async function bootstrap() {
  bindEvents();
  await refreshHealth();
  setInterval(refreshHealth, 10000);

  try {
    await loadTasks();
    await resetEpisode();
  } catch (error) {
    log(`Startup failed: ${error.message}`, "error");
  }
}

bootstrap();
