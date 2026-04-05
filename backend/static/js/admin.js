(() => {
  const app = window.JalGuard;
  let validationJobId = null;

  function renderChecklist(rows) {
    const list = document.getElementById("validationChecklist");
    list.innerHTML = "";
    if (!rows || !rows.length) {
      list.innerHTML = `<li class="check-item info"><span>Waiting for validation output...</span></li>`;
      return;
    }

    rows.forEach((row) => {
      const li = document.createElement("li");
      li.className = `check-item ${row.status || "info"}`;
      const mark = row.status === "pass" ? "✓" : row.status === "fail" ? "✗" : "•";
      li.innerHTML = `<strong>${mark} ${row.name || "Check"}</strong><span>${row.detail || ""}</span>`;
      list.appendChild(li);
    });
  }

  async function runPlayground() {
    const action = document.getElementById("playAction").value;
    const rawPayload = document.getElementById("playPayload").value || "{}";
    let payload;
    try {
      payload = JSON.parse(rawPayload);
    } catch {
      app.toast("Please enter valid JSON.", "err");
      return;
    }

    const routeMap = {
      reset: "/reset",
      step: "/step",
      state: "/state",
    };
    const data = await app.api("/api/admin/playground", {
      method: "POST",
      body: JSON.stringify({ route: routeMap[action], payload }),
    });
    document.getElementById("playResponse").textContent = JSON.stringify(data, null, 2);
  }

  async function startValidation() {
    const data = await app.api("/api/admin/run-validation", { method: "POST" });
    validationJobId = data.job_id;
    renderChecklist([]);
    app.toast("Validation started");
    pollValidation();
  }

  async function pollValidation() {
    if (!validationJobId) return;
    const data = await app.api(`/api/admin/validation/${validationJobId}`);
    document.getElementById("validationStatus").textContent = data.status;
    document.getElementById("validationOutput").textContent = data.output || "";
    renderChecklist(data.checklist || []);
    if (data.status === "queued" || data.status === "running") {
      setTimeout(pollValidation, 1200);
    }
  }

  function wireEvents() {
    document.getElementById("playRunBtn").addEventListener("click", runPlayground);
    document.getElementById("runValidationBtn").addEventListener("click", startValidation);
  }

  async function boot() {
    app.boot("admin");
    wireEvents();
  }

  boot().catch((error) => app.toast(error.message, "err"));
})();
