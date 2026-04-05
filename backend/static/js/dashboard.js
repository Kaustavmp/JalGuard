(() => {
  const app = window.JalGuard;
  const settings = app.getSettings();
  const state = {
    taskId: "fill_timing",
    observation: null,
    suggestedAction: null,
    suggestedReasoning: "",
    autoTimer: null,
    autoBusy: false,
    chlorinateCountdown: 0,
    actions: {
      pump_on: false,
      chlorinate: false,
      check_leak: false,
      harvester_on: false,
      release_water: 0,
    },
  };

  const el = {
    taskSelect: document.getElementById("taskSelect"),
    taskDesc: document.getElementById("taskDesc"),
    reward: document.getElementById("mReward"),
    tank: document.getElementById("mTank"),
    chlorine: document.getElementById("mChlorine"),
    demand: document.getElementById("mDemand"),
    day: document.getElementById("mDay"),
    step: document.getElementById("mStep"),
    ph: document.getElementById("mPh"),
    qualityBar: document.getElementById("mQualityBar"),
    qualityVal: document.getElementById("mQualityVal"),
    supply: document.getElementById("mSupply"),
    power: document.getElementById("mPower"),
    season: document.getElementById("mSeason"),
    release: document.getElementById("releaseWater"),
    releaseVal: document.getElementById("releaseVal"),
    releaseLitres: document.getElementById("releaseLitres"),
    logs: document.getElementById("liveLogs"),
    aiReason: document.getElementById("aiReasoning"),
    aiPreview: document.getElementById("aiPreview"),
    aiNote: document.getElementById("aiNote"),
    runMultiSteps: document.getElementById("multiSteps"),
    autoBtn: document.getElementById("autoRunBtn"),
    chlorinateCountdown: document.getElementById("chlorinateCountdown"),
    tiles: {
      pump_on: document.getElementById("pumpOnBtn"),
      chlorinate: document.getElementById("chlorinateBtn"),
      check_leak: document.getElementById("checkLeakBtn"),
      harvester_on: document.getElementById("harvesterOnBtn"),
    },
    tileState: {
      pump_on: document.getElementById("pumpOnState"),
      chlorinate: document.getElementById("chlorinateState"),
      check_leak: document.getElementById("checkLeakState"),
      harvester_on: document.getElementById("harvesterOnState"),
    },
    pumpAnim: document.getElementById("pumpAnim"),
  };

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function computePH(obs) {
    const value = 7.1 + (Number(obs.chlorine_level || 0) - 1.6) * 0.3 + (obs.bacteria_detected ? 0.35 : 0) + (Number(obs.tds_reading || 0) > 1400 ? 0.25 : 0);
    return clamp(value, 5.5, 9.2);
  }

  function computeQuality(obs) {
    const tds = Number(obs.tds_reading || 0);
    const chlorine = Number(obs.chlorine_level || 0);
    let score = 100;
    score -= clamp((tds - 250) / 20, 0, 55);
    if (obs.bacteria_detected) score -= 30;
    if (chlorine < 0.6) score -= 12;
    if (chlorine > 3.2) score -= 18;
    return clamp(score, 0, 100);
  }

  function actionFromUI() {
    return {
      pump_on: state.actions.pump_on,
      release_water: Number(el.release.value),
      chlorinate: state.actions.chlorinate,
      check_leak: state.actions.check_leak,
      harvester_on: state.actions.harvester_on,
    };
  }

  function renderReleaseInfo() {
    const pct = Number(el.release.value || 0);
    state.actions.release_water = pct;
    el.releaseVal.textContent = `${pct}%`;
    const litres = state.observation ? (Number(state.observation.tank_level || 0) * pct) / 100 : 0;
    el.releaseLitres.textContent = `${litres.toFixed(0)}L`;
  }

  function updateActionTiles() {
    Object.keys(el.tiles).forEach((key) => {
      const active = Boolean(state.actions[key]);
      el.tiles[key].classList.toggle("active", active);
      el.tileState[key].textContent = active ? "ON" : "OFF";
    });
    el.pumpAnim.classList.toggle("active", Boolean(state.actions.pump_on));
    if (!state.actions.chlorinate) {
      el.chlorinateCountdown.textContent = "";
    }
  }

  function applyAction(action) {
    if (!action) return;
    state.actions = {
      pump_on: !!action.pump_on,
      release_water: Number(action.release_water || 0),
      chlorinate: !!action.chlorinate,
      check_leak: !!action.check_leak,
      harvester_on: !!action.harvester_on,
    };
    el.release.value = String(state.actions.release_water);
    renderReleaseInfo();
    updateActionTiles();
  }

  function renderObservation(obs, reward = null) {
    if (!obs) return;
    state.observation = obs;
    el.tank.textContent = `${obs.tank_level.toFixed(1)} L`;
    el.chlorine.textContent = `${obs.chlorine_level.toFixed(2)} mg/L`;
    el.demand.textContent = `${obs.forecasted_demand.toFixed(1)} L`;
    el.day.textContent = `${obs.day_of_episode}`;
    el.step.textContent = `${obs.step_of_episode}`;
    el.reward.textContent = `${obs.cumulative_reward.toFixed(2)}${reward === null ? "" : ` (last ${Number(reward).toFixed(2)})`}`;

    const ph = computePH(obs);
    const phSafe = ph >= 6.5 && ph <= 8.5;
    el.ph.textContent = ph.toFixed(2);
    el.ph.classList.toggle("ok-text", phSafe);
    el.ph.classList.toggle("warn-text", !phSafe);

    const quality = computeQuality(obs);
    el.qualityBar.style.width = `${quality}%`;
    el.qualityVal.textContent = `${quality.toFixed(0)}%`;
    el.qualityBar.className = quality >= 70 ? "quality-safe" : quality >= 45 ? "quality-warn" : "quality-danger";

    el.supply.textContent = obs.municipal_supply_active ? "ACTIVE" : "INACTIVE";
    el.supply.className = `pill ${obs.municipal_supply_active ? "active" : "inactive"}`;
    el.power.textContent = obs.power_active ? "ON" : "CUT";
    el.power.className = `pill ${obs.power_active ? "active" : "inactive"}`;
    el.season.textContent = String(obs.season || "").toUpperCase();
    renderReleaseInfo();
  }

  function consumeChlorinationCountdown(action) {
    if (action.chlorinate) {
      state.chlorinateCountdown = 3;
    } else if (state.chlorinateCountdown > 0) {
      state.chlorinateCountdown -= 1;
    }
    if (state.chlorinateCountdown > 0) {
      el.chlorinateCountdown.textContent = `Finishes in ${state.chlorinateCountdown} step${state.chlorinateCountdown === 1 ? "" : "s"}`;
    } else {
      el.chlorinateCountdown.textContent = "";
    }
  }

  async function loadTasks() {
    const data = await app.api("/tasks");
    el.taskSelect.innerHTML = "";
    data.tasks.forEach((task) => {
      const opt = document.createElement("option");
      opt.value = task.id;
      opt.textContent = task.name;
      el.taskSelect.appendChild(opt);
    });
    el.taskSelect.value = state.taskId;
    updateTaskDescription(data.tasks);
  }

  function updateTaskDescription(tasks) {
    const list = tasks || [];
    const current = list.find((t) => t.id === el.taskSelect.value);
    el.taskDesc.textContent = current ? current.description : "";
  }

  async function resetEpisode() {
    state.taskId = el.taskSelect.value;
    const data = await app.api(`/reset?task_id=${encodeURIComponent(state.taskId)}`, { method: "POST" });
    renderObservation(data.observation);
    app.toast(`Episode started: ${state.taskId.replaceAll("_", " ")}`);
  }

  async function runStep(source = "human", reasoning = "", manualAction = null) {
    const action = manualAction || actionFromUI();
    const query = `?source=${encodeURIComponent(source)}&reasoning=${encodeURIComponent(reasoning || "")}`;
    const data = await app.api(`/step${query}`, { method: "POST", body: JSON.stringify(action) });
    renderObservation(data.observation, data.reward);
    consumeChlorinationCountdown(action);
    if (data.done) {
      app.toast("Episode reached terminal step", "warn");
      stopAuto();
    }
    return data;
  }

  async function runMultiple() {
    const count = Math.max(1, Math.min(200, Number(el.runMultiSteps.value || 1)));
    for (let i = 0; i < count; i += 1) {
      await runStep("human");
      if (state.observation?.step_of_episode >= 720) break;
      await new Promise((resolve) => setTimeout(resolve, 30));
    }
  }

  async function autoTick() {
    if (state.autoBusy) return;
    state.autoBusy = true;
    try {
      if (settings.assistant.auto_suggest) {
        await askAI(true);
        await applySuggestion(true);
      } else {
        await runStep("human");
      }
    } catch (error) {
      app.toast(`Auto-run error: ${error.message}`, "err");
      stopAuto();
    } finally {
      state.autoBusy = false;
    }
  }

  function startAuto() {
    if (state.autoTimer) return;
    state.autoTimer = setInterval(autoTick, app.state.autoRunDelayMs || 300);
    el.autoBtn.textContent = "Stop Auto";
  }

  function stopAuto() {
    if (!state.autoTimer) return;
    clearInterval(state.autoTimer);
    state.autoTimer = null;
    el.autoBtn.textContent = "Auto Run";
  }

  async function gradeEpisode() {
    const data = await app.api("/grader", { method: "POST", body: JSON.stringify({ task_id: state.taskId }) });
    app.toast(`Graded ${data.task_id}: ${Number(data.score).toFixed(4)}`);
  }

  function shortenReasoning(text) {
    if (settings.assistant.explain_reasoning) return text;
    const firstSentence = String(text).split(".")[0].trim();
    return firstSentence ? `${firstSentence}.` : "Suggestion ready.";
  }

  async function askAI(silent = false) {
    const payload = {
      task_id: state.taskId,
      observation: state.observation,
      note: el.aiNote.value || "",
    };
    const data = await app.api("/api/ai/suggest-action", { method: "POST", body: JSON.stringify(payload) });
    state.suggestedAction = data.action;
    state.suggestedReasoning = String(data.reasoning || "Recommendation ready.");
    applyAction(data.action);

    const persona = settings.assistant.persona_name || "JalGuard Assistant";
    el.aiReason.textContent = `${persona}: ${shortenReasoning(state.suggestedReasoning)}`;
    el.aiPreview.textContent = shortenReasoning(state.suggestedReasoning);
    if (!silent) app.toast("AI suggestion ready");
    return data;
  }

  async function applySuggestion(silent = false) {
    if (!state.suggestedAction) {
      if (!silent) app.toast("Ask AI first to get a suggestion.", "warn");
      return;
    }
    await runStep("assistant", state.suggestedReasoning, state.suggestedAction);
    if (!silent) app.toast("Assistant suggestion applied");
  }

  async function refreshLogs() {
    const mode = settings.display.log_mode || "significant";
    const data = await app.api(`/api/logs?limit=120&mode=${encodeURIComponent(mode)}`);
    const lines = (data.logs || []).slice().reverse();
    el.logs.textContent = lines.length ? lines.join("\n") : "No events yet. Run a step to begin.";
  }

  async function downloadReport() {
    const data = await app.api("/api/episodes/current");
    app.downloadFile("episode_report.json", JSON.stringify(data, null, 2), "application/json");
    app.toast("Episode report downloaded");
  }

  function wireActionTiles() {
    const map = {
      pumpOnBtn: "pump_on",
      chlorinateBtn: "chlorinate",
      checkLeakBtn: "check_leak",
      harvesterOnBtn: "harvester_on",
    };
    Object.entries(map).forEach(([id, key]) => {
      document.getElementById(id).addEventListener("click", () => {
        state.actions[key] = !state.actions[key];
        updateActionTiles();
      });
    });
  }

  function wireEvents() {
    el.release.addEventListener("input", renderReleaseInfo);
    document.getElementById("startBtn").addEventListener("click", resetEpisode);
    document.getElementById("resetBtn").addEventListener("click", resetEpisode);
    document.getElementById("gradeBtn").addEventListener("click", gradeEpisode);
    document.getElementById("runStepBtn").addEventListener("click", () => runStep("human"));
    document.getElementById("runMultiBtn").addEventListener("click", runMultiple);
    el.autoBtn.addEventListener("click", () => (state.autoTimer ? stopAuto() : startAuto()));
    document.getElementById("askAiBtn").addEventListener("click", () => askAI(false));
    document.getElementById("applyAiBtn").addEventListener("click", () => applySuggestion(false));
    el.taskSelect.addEventListener("change", async () => {
      const data = await app.api("/tasks");
      updateTaskDescription(data.tasks);
    });
    wireActionTiles();

    window.addEventListener("jalguard:run-step", () => runStep("human"));
    window.addEventListener("jalguard:ask-ai-panel", () => askAI(false));
    window.addEventListener("jalguard:reset", resetEpisode);
    window.addEventListener("jalguard:start", resetEpisode);
    window.addEventListener("jalguard:download", downloadReport);
    window.addEventListener("jalguard:settings-updated", (event) => {
      Object.assign(settings, event.detail || {});
    });
  }

  async function boot() {
    app.boot("dashboard");
    wireEvents();
    await loadTasks();
    await resetEpisode();
    applyAction(state.actions);
    await refreshLogs();
    setInterval(refreshLogs, 1200);
  }

  boot().catch((error) => app.toast(error.message, "err"));
})();
