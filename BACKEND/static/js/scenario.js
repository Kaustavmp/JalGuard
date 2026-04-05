(() => {
  const app = window.JalGuard;
  const state = {
    sessionId: null,
    latestScenarioId: null,
  };

  const el = {
    chat: document.getElementById("scenarioChat"),
    prompt: document.getElementById("scenarioPrompt"),
    sendBtn: document.getElementById("sendPromptBtn"),
    scenarioName: document.getElementById("scenarioName"),
    historySearch: document.getElementById("historySearch"),
    historyList: document.getElementById("historyList"),
    latestScenarioName: document.getElementById("latestScenarioName"),
    activateLatestBtn: document.getElementById("activateLatestBtn"),
  };

  function appendChat(role, text) {
    const row = document.createElement("div");
    row.className = `chat-bubble ${role}`;
    row.textContent = text;
    el.chat.appendChild(row);
    el.chat.scrollTop = el.chat.scrollHeight;
  }

  function formatDate(raw) {
    if (!raw) return "-";
    const date = new Date(raw);
    if (Number.isNaN(date.getTime())) return "-";
    return date.toLocaleString();
  }

  async function refreshHistory(query = "") {
    const data = await app.api(`/api/scenario-history?q=${encodeURIComponent(query)}`);
    const rows = data.history || [];
    el.historyList.innerHTML = "";

    if (!rows.length) {
      el.historyList.innerHTML = `<div class="history-item"><strong>No scenarios found</strong><span>Use the assistant to create one.</span></div>`;
      return;
    }

    rows.forEach((entry) => {
      const item = document.createElement("div");
      item.className = "history-item";
      item.innerHTML = `
        <strong>${entry.name}</strong>
        <span>${entry.summary || ""}</span>
        <small>${formatDate(entry.created_at)}${entry.last_score === null || entry.last_score === undefined ? "" : ` | Score ${Number(entry.last_score).toFixed(3)}`}</small>
        <button class="btn secondary small" data-load="${entry.id}">Load</button>
      `;
      el.historyList.appendChild(item);
    });

    el.historyList.querySelectorAll("[data-load]").forEach((button) => {
      button.addEventListener("click", async () => {
        const scenarioId = button.getAttribute("data-load");
        const data = await app.api(`/api/scenario-history/${encodeURIComponent(scenarioId)}/load`, { method: "POST" });
        state.latestScenarioId = scenarioId;
        el.latestScenarioName.textContent = data.scenario?.name || scenarioId;
        app.toast(`Loaded ${data.scenario?.name || scenarioId}`);
      });
    });
  }

  async function sendPrompt() {
    const message = el.prompt.value.trim();
    if (!message) {
      app.toast("Write a scenario request first.", "warn");
      return;
    }

    appendChat("user", message);
    el.prompt.value = "";

    const payload = {
      message,
      session_id: state.sessionId,
      scenario_name: el.scenarioName.value.trim() || undefined,
    };
    const data = await app.api("/api/scenario-chat/message", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    state.sessionId = data.session_id;
    state.latestScenarioId = data.scenario?.id || state.latestScenarioId;
    el.latestScenarioName.textContent = data.scenario?.name || "-";
    appendChat("assistant", data.reply || "Scenario updated.");
    await refreshHistory(el.historySearch.value || "");
    app.toast("Scenario saved to history");
  }

  async function activateLatest() {
    if (!state.latestScenarioId) {
      app.toast("No scenario is ready yet.", "warn");
      return;
    }
    await app.api(`/api/scenario-history/${encodeURIComponent(state.latestScenarioId)}/load`, { method: "POST" });
    await app.api("/reset?task_id=custom_user_scenario", { method: "POST" });
    app.toast("Latest scenario loaded and activated");
  }

  function wireEvents() {
    el.sendBtn.addEventListener("click", sendPrompt);
    el.activateLatestBtn.addEventListener("click", activateLatest);
    el.prompt.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendPrompt();
      }
    });
    el.historySearch.addEventListener("input", () => refreshHistory(el.historySearch.value));

    window.addEventListener("jalguard:download", async () => {
      const data = await app.api("/api/scenario-history");
      app.downloadFile("scenario_history.json", JSON.stringify(data, null, 2), "application/json");
      app.toast("Scenario history exported");
    });
  }

  async function boot() {
    app.boot("scenario");
    appendChat("assistant", "Describe the scenario you want to simulate. I will build it, summarize it, and save it to your history automatically.");
    wireEvents();
    await refreshHistory();
  }

  boot().catch((error) => app.toast(error.message, "err"));
})();
