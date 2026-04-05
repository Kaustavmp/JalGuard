const JalGuard = (() => {
  const SETTINGS_KEY = "jalguard-settings-v2";
  const state = {
    status: {},
    autoRunDelayMs: 250,
    settings: null,
  };

  const DEFAULT_SETTINGS = {
    account: {
      display_name: "JalGuard Operator",
      email: "operator@jalguard.local",
      created_at: new Date().toISOString(),
      profile_picture: "",
    },
    assistant: {
      explain_reasoning: true,
      response_detail: "balanced",
      auto_suggest: false,
      persona_name: "JalGuard Assistant",
    },
    display: {
      theme: "dark",
      log_mode: "significant",
      chart_mode: "realtime",
      language: "English",
    },
  };

  function deepMerge(base, patch) {
    const result = { ...base };
    Object.keys(patch || {}).forEach((key) => {
      const baseValue = base[key];
      const patchValue = patch[key];
      if (
        baseValue &&
        patchValue &&
        typeof baseValue === "object" &&
        typeof patchValue === "object" &&
        !Array.isArray(baseValue) &&
        !Array.isArray(patchValue)
      ) {
        result[key] = deepMerge(baseValue, patchValue);
      } else {
        result[key] = patchValue;
      }
    });
    return result;
  }

  function loadSettings() {
    const cloneDefaults = () => JSON.parse(JSON.stringify(DEFAULT_SETTINGS));
    try {
      const raw = localStorage.getItem(SETTINGS_KEY);
      if (!raw) return cloneDefaults();
      const parsed = JSON.parse(raw);
      return deepMerge(DEFAULT_SETTINGS, parsed);
    } catch {
      return cloneDefaults();
    }
  }

  function saveSettings(nextSettings) {
    state.settings = deepMerge(DEFAULT_SETTINGS, nextSettings || {});
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(state.settings));
    applyTheme();
    window.dispatchEvent(new CustomEvent("jalguard:settings-updated", { detail: state.settings }));
  }

  function getSettings() {
    if (!state.settings) {
      state.settings = loadSettings();
    }
    return state.settings;
  }

  function applyTheme() {
    const theme = getSettings().display.theme || "dark";
    document.body.classList.toggle("light", theme === "light");
  }

  function friendlyErrorMessage(raw) {
    const text = String(raw || "").trim();
    if (!text) return "Something went wrong. Try again.";
    if (text.toLowerCase().includes("not found")) return "Requested item was not found.";
    if (text.length > 220) return "Something went wrong. Try resetting the episode.";
    return text.replace(/["{}[\]]/g, "");
  }

  async function api(path, options = {}) {
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    const response = await fetch(path, { ...options, headers });
    if (!response.ok) {
      let payload = "";
      try {
        const body = await response.json();
        payload = body.error || body.detail || JSON.stringify(body);
      } catch {
        payload = await response.text();
      }
      throw new Error(friendlyErrorMessage(payload));
    }
    return response.json();
  }

  function toast(message, type = "ok") {
    const wrap = document.getElementById("toastWrap");
    if (!wrap) return;
    const item = document.createElement("div");
    item.className = `toast ${type}`;
    item.textContent = message;
    wrap.appendChild(item);
    setTimeout(() => item.remove(), 3600);
  }

  function updateStatusPills(status) {
    const map = {
      statusFastAPI: status.fastapi ? "Online" : "Offline",
      statusOpenEnv: status.environment ? "Ready" : "Down",
      statusAssistant: status.assistant_active ? "Active" : "Inactive",
      statusTask: status.task_loaded || "-",
    };
    Object.entries(map).forEach(([id, value]) => {
      const el = document.getElementById(id);
      if (el) el.textContent = value;
    });

    const assistant = document.getElementById("statusAssistant");
    if (assistant) {
      assistant.classList.toggle("ok-text", Boolean(status.assistant_active));
      assistant.classList.toggle("warn-text", !status.assistant_active);
    }
  }

  async function refreshStatus() {
    try {
      const status = await api("/api/admin/status");
      state.status = status;
      updateStatusPills(status);
    } catch (error) {
      toast(`Status check failed: ${error.message}`, "warn");
    }
  }

  function setupQuickActions() {
    document.querySelectorAll("[data-qa]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const action = btn.getAttribute("data-qa");
        window.dispatchEvent(new CustomEvent(`jalguard:${action}`));
      });
    });
  }

  async function defaultQuickAction(action) {
    try {
      if (action === "start" || action === "reset") {
        const task = state.status.task_loaded || "fill_timing";
        await api(`/reset?task_id=${encodeURIComponent(task)}`, { method: "POST" });
        toast(`${action === "start" ? "Started" : "Reset"} task: ${task.replaceAll("_", " ")}`);
      } else if (action === "download") {
        const payload = await api("/api/episodes/current");
        downloadFile("episode_report.json", JSON.stringify(payload, null, 2), "application/json");
        toast("Downloaded episode report");
      } else if (action === "ask-ai") {
        if (document.getElementById("askAiBtn")) {
          window.dispatchEvent(new CustomEvent("jalguard:ask-ai-panel"));
          return;
        }
        const stateResp = await api("/state");
        const obs = stateResp?.state
          ? {
              tank_level: Number(stateResp.state.tank_level || 0),
              is_raining: !!stateResp.state.is_raining,
              municipal_supply_active: !!stateResp.state.supply_on,
              power_active: !!stateResp.state.power_on,
              tds_reading: Number(stateResp.state.tds_actual || 0),
              bacteria_detected: Number(stateResp.state.bacteria_actual || 0) > 0,
              forecasted_demand: Number(stateResp.state.current_demand || 0),
              leak_detected: false,
              chlorine_level: Number(stateResp.state.chlorine_actual || 0),
              time_of_day: Number(stateResp.state.hour || 0),
              day_of_episode: Number(stateResp.state.day || 0),
              step_of_episode: Number(stateResp.step || 0),
              season: String(stateResp.state.season || "summer"),
              cumulative_reward: Number(stateResp.score || 0),
              task_id: String(stateResp.task_id || "fill_timing"),
            }
          : null;
        const response = await api("/api/ai/suggest-action", {
          method: "POST",
          body: JSON.stringify({ task_id: stateResp.task_id || "fill_timing", observation: obs }),
        });
        const line = String(response.reasoning || "Suggestion ready").split(".")[0];
        toast(`AI: ${line}.`);
      }
    } catch (error) {
      toast(`Quick action failed: ${error.message}`, "err");
    }
  }

  function setupShortcuts() {
    document.addEventListener("keydown", (event) => {
      const tag = (event.target?.tagName || "").toLowerCase();
      if (["input", "textarea", "select"].includes(tag)) return;

      if (event.code === "Space") {
        event.preventDefault();
        window.dispatchEvent(new CustomEvent("jalguard:run-step"));
      } else if (event.key.toLowerCase() === "a") {
        window.dispatchEvent(new CustomEvent("jalguard:ask-ai"));
      } else if (event.key.toLowerCase() === "r") {
        window.dispatchEvent(new CustomEvent("jalguard:reset"));
      }
    });
  }

  function setupOnboarding() {
    const modal = document.getElementById("onboardModal");
    if (!modal) return;

    const steps = [
      "Welcome to JalGuard. Move across all 4 primary pages from the top navigation.",
      "Use Quick Actions for Start, Reset, Ask Assistant, and Download Report from any page.",
      "Keyboard shortcuts: Space = Run Step, A = Ask Assistant, R = Reset.",
      "Open the profile icon for user settings and scenario history management.",
    ];

    let idx = 0;
    const body = document.getElementById("onboardBody");
    const next = document.getElementById("onboardNext");

    function render() {
      body.textContent = steps[idx];
      next.textContent = idx >= steps.length - 1 ? "Finish" : "Next";
    }

    next.addEventListener("click", () => {
      if (idx >= steps.length - 1) {
        modal.classList.remove("show");
        localStorage.setItem("jalguard-onboarded", "1");
      } else {
        idx += 1;
        render();
      }
    });

    if (!localStorage.getItem("jalguard-onboarded")) {
      modal.classList.add("show");
      render();
    }
  }

  function initProfileButton() {
    const profile = document.getElementById("profileLink");
    if (!profile) return;
    const name = getSettings().account.display_name || "User";
    const initials = name
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0].toUpperCase())
      .join("");
    profile.textContent = initials || "JG";
    profile.setAttribute("title", "User Settings");
  }

  function downloadFile(filename, content, mime) {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  function boot(pageName) {
    state.settings = loadSettings();
    applyTheme();
    initProfileButton();
    setupQuickActions();
    setupShortcuts();
    setupOnboarding();
    refreshStatus();
    setInterval(refreshStatus, 8000);

    window.addEventListener("jalguard:start", () => defaultQuickAction("start"));
    window.addEventListener("jalguard:reset", () => defaultQuickAction("reset"));
    window.addEventListener("jalguard:ask-ai", () => defaultQuickAction("ask-ai"));
    window.addEventListener("jalguard:download", () => defaultQuickAction("download"));

    document.querySelectorAll(".nav-link").forEach((link) => {
      if (link.dataset.page === pageName) link.classList.add("active");
    });
    const profile = document.getElementById("profileLink");
    if (profile && pageName === "settings") profile.classList.add("active");
  }

  return {
    api,
    toast,
    boot,
    downloadFile,
    state,
    getSettings,
    saveSettings,
  };
})();

window.JalGuard = JalGuard;
