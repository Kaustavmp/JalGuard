(() => {
  const app = window.JalGuard;
  const settings = app.getSettings();

  const el = {
    accountName: document.getElementById("accountName"),
    accountEmail: document.getElementById("accountEmail"),
    accountPhoto: document.getElementById("accountPhoto"),
    accountPhotoPreview: document.getElementById("accountPhotoPreview"),
    accountCreatedAt: document.getElementById("accountCreatedAt"),
    assistantExplain: document.getElementById("assistantExplain"),
    assistantDetail: document.getElementById("assistantDetail"),
    assistantAutoSuggest: document.getElementById("assistantAutoSuggest"),
    assistantPersona: document.getElementById("assistantPersona"),
    displayTheme: document.getElementById("displayTheme"),
    displayLogMode: document.getElementById("displayLogMode"),
    displayChartMode: document.getElementById("displayChartMode"),
    displayLanguage: document.getElementById("displayLanguage"),
    saveSettingsBtn: document.getElementById("saveSettingsBtn"),
    historySearch: document.getElementById("historySearch"),
    refreshHistoryBtn: document.getElementById("refreshHistoryBtn"),
    settingsHistoryList: document.getElementById("settingsHistoryList"),
    changePasswordBtn: document.getElementById("changePasswordBtn"),
  };

  function formatDate(raw) {
    if (!raw) return "-";
    const date = new Date(raw);
    if (Number.isNaN(date.getTime())) return "-";
    return date.toLocaleString();
  }

  function readPhoto(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ""));
      reader.onerror = () => reject(new Error("Could not read image"));
      reader.readAsDataURL(file);
    });
  }

  function bindSettingsToForm() {
    el.accountName.value = settings.account.display_name || "";
    el.accountEmail.value = settings.account.email || "";
    el.accountCreatedAt.textContent = formatDate(settings.account.created_at);
    if (settings.account.profile_picture) {
      el.accountPhotoPreview.src = settings.account.profile_picture;
      el.accountPhotoPreview.style.display = "block";
    }

    el.assistantExplain.checked = Boolean(settings.assistant.explain_reasoning);
    el.assistantDetail.value = settings.assistant.response_detail || "balanced";
    el.assistantAutoSuggest.checked = Boolean(settings.assistant.auto_suggest);
    el.assistantPersona.value = settings.assistant.persona_name || "JalGuard Assistant";

    el.displayTheme.value = settings.display.theme || "dark";
    el.displayLogMode.value = settings.display.log_mode || "significant";
    el.displayChartMode.value = settings.display.chart_mode || "realtime";
    el.displayLanguage.value = settings.display.language || "English";
  }

  function collectFormSettings() {
    return {
      account: {
        display_name: el.accountName.value.trim() || "JalGuard Operator",
        email: el.accountEmail.value.trim() || "operator@jalguard.local",
        created_at: settings.account.created_at || new Date().toISOString(),
        profile_picture: settings.account.profile_picture || "",
      },
      assistant: {
        explain_reasoning: el.assistantExplain.checked,
        response_detail: el.assistantDetail.value,
        auto_suggest: el.assistantAutoSuggest.checked,
        persona_name: el.assistantPersona.value.trim() || "JalGuard Assistant",
      },
      display: {
        theme: el.displayTheme.value,
        log_mode: el.displayLogMode.value,
        chart_mode: el.displayChartMode.value,
        language: el.displayLanguage.value.trim() || "English",
      },
    };
  }

  async function saveAllSettings() {
    const next = collectFormSettings();
    app.saveSettings(next);
    Object.assign(settings, next);
    app.toast("Settings saved");
  }

  async function refreshHistory() {
    const query = el.historySearch.value || "";
    const data = await app.api(`/api/scenario-history?q=${encodeURIComponent(query)}`);
    const rows = data.history || [];
    el.settingsHistoryList.innerHTML = "";

    if (!rows.length) {
      el.settingsHistoryList.innerHTML = `<div class="history-item"><strong>No matching scenarios</strong><span>Try another search or create a new scenario.</span></div>`;
      return;
    }

    rows.forEach((entry) => {
      const card = document.createElement("div");
      card.className = "history-item";
      card.innerHTML = `
        <strong>${entry.name}</strong>
        <span>${entry.summary || ""}</span>
        <small>Created: ${formatDate(entry.created_at)} | Task: ${entry.last_task_id || "-"} | Score: ${entry.last_score === null || entry.last_score === undefined ? "-" : Number(entry.last_score).toFixed(3)}</small>
        <div class="history-actions">
          <button class="btn secondary small" data-load="${entry.id}">Load</button>
          <button class="btn ghost small" data-rename="${entry.id}">Rename</button>
          <button class="btn danger small" data-delete="${entry.id}">Delete</button>
        </div>
      `;
      el.settingsHistoryList.appendChild(card);
    });

    el.settingsHistoryList.querySelectorAll("[data-load]").forEach((button) => {
      button.addEventListener("click", async () => {
        const id = button.getAttribute("data-load");
        const response = await app.api(`/api/scenario-history/${encodeURIComponent(id)}/load`, { method: "POST" });
        app.toast(`Loaded ${response.scenario?.name || id}`);
      });
    });

    el.settingsHistoryList.querySelectorAll("[data-rename]").forEach((button) => {
      button.addEventListener("click", async () => {
        const id = button.getAttribute("data-rename");
        const current = rows.find((item) => item.id === id);
        const newName = window.prompt("Enter a new scenario name:", current?.name || "");
        if (!newName || newName.trim().length < 2) return;
        await app.api(`/api/scenario-history/${encodeURIComponent(id)}/rename`, {
          method: "POST",
          body: JSON.stringify({ name: newName.trim() }),
        });
        app.toast("Scenario renamed");
        refreshHistory();
      });
    });

    el.settingsHistoryList.querySelectorAll("[data-delete]").forEach((button) => {
      button.addEventListener("click", async () => {
        const id = button.getAttribute("data-delete");
        const confirmed = window.confirm("Delete this scenario from history?");
        if (!confirmed) return;
        await app.api(`/api/scenario-history/${encodeURIComponent(id)}`, { method: "DELETE" });
        app.toast("Scenario deleted");
        refreshHistory();
      });
    });
  }

  function wireEvents() {
    el.saveSettingsBtn.addEventListener("click", saveAllSettings);
    el.refreshHistoryBtn.addEventListener("click", refreshHistory);
    el.historySearch.addEventListener("input", refreshHistory);
    el.changePasswordBtn.addEventListener("click", () => {
      app.toast("Password update flow will be enabled in the secure auth release.");
    });

    el.accountPhoto.addEventListener("change", async (event) => {
      const file = event.target.files?.[0];
      if (!file) return;
      const dataUrl = await readPhoto(file);
      settings.account.profile_picture = dataUrl;
      el.accountPhotoPreview.src = dataUrl;
      el.accountPhotoPreview.style.display = "block";
      app.saveSettings(settings);
    });
  }

  async function boot() {
    app.boot("settings");
    bindSettingsToForm();
    wireEvents();
    await refreshHistory();
  }

  boot().catch((error) => app.toast(error.message, "err"));
})();
