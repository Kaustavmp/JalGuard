(() => {
  const app = window.JalGuard;
  const settings = app.getSettings();
  let tankChart;
  let rewardChart;
  let realtimeTimer = null;

  function extractSeries(steps) {
    const labels = steps.map((step) => step.step);
    const tank = steps.map((step) => Number(step.state.tank_level || 0));
    const chlorine = steps.map((step) => Number(step.state.chlorine_level || 0));
    const reward = steps.map((step) => Number(step.reward || 0));
    const assistant = steps.filter((step) => step.source === "assistant").length;
    const human = steps.filter((step) => step.source !== "assistant").length;
    return { labels, tank, chlorine, reward, assistant, human };
  }

  function ensureChartData(series) {
    if (series.labels.length > 0) return series;
    return {
      labels: ["No Data"],
      tank: [0],
      chlorine: [0],
      reward: [0],
      assistant: 0,
      human: 0,
    };
  }

  function renderCharts(rawSeries) {
    const series = ensureChartData(rawSeries);
    const tankCtx = document.getElementById("tankChart").getContext("2d");
    const rewardCtx = document.getElementById("rewardChart").getContext("2d");

    if (tankChart) tankChart.destroy();
    if (rewardChart) rewardChart.destroy();

    tankChart = new Chart(tankCtx, {
      type: "line",
      data: {
        labels: series.labels,
        datasets: [
          { label: "Tank Level", data: series.tank, borderColor: "#03c7a8", tension: 0.25 },
          { label: "Chlorine", data: series.chlorine, borderColor: "#59a8ff", tension: 0.25 },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });

    rewardChart = new Chart(rewardCtx, {
      type: "bar",
      data: {
        labels: series.labels,
        datasets: [{ label: "Reward", data: series.reward, backgroundColor: "#ffb25a" }],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });
  }

  function renderComparison(series) {
    const table = document.getElementById("comparisonBody");
    table.innerHTML = "";

    const total = Math.max(1, series.assistant + series.human);
    const rows = [
      ["Assistant Decisions", series.assistant],
      ["Manual Decisions", series.human],
      ["Assistant Share", `${((series.assistant / total) * 100).toFixed(1)}%`],
    ];

    rows.forEach((row) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${row[0]}</td><td>${row[1]}</td>`;
      table.appendChild(tr);
    });
  }

  function renderSummary(latest, stepCount) {
    const summary = document.getElementById("episodeSummary");
    if (!latest || !latest.steps) {
      summary.textContent = "Warm-up data loaded. Run an episode and grade it to compare new results.";
      return;
    }
    summary.textContent = `Task: ${latest.task_id} | Steps: ${stepCount} | Final Score: ${latest.final_score ?? "n/a"} | Total Reward: ${latest.total_reward?.toFixed?.(2) ?? latest.total_reward}`;
  }

  async function refresh() {
    const [current, summary] = await Promise.all([app.api("/api/episodes/current"), app.api("/api/episodes/summary")]);
    const steps = current.steps || [];
    const series = extractSeries(steps);
    renderCharts(series);
    renderComparison(series);
    renderSummary(summary.latest || {}, steps.length);
    app.state.latestEpisodeData = { current, summary };
  }

  function exportJson() {
    const payload = app.state.latestEpisodeData || {};
    app.downloadFile("analytics_report.json", JSON.stringify(payload, null, 2), "application/json");
    app.toast("JSON report exported");
  }

  function exportCsv() {
    const steps = app.state.latestEpisodeData?.current?.steps || [];
    const header = ["step", "tank_level", "chlorine", "reward", "source"];
    const rows = steps.map((s) => [s.step, s.state.tank_level, s.state.chlorine_level, s.reward, s.source]);
    const csv = [header.join(","), ...rows.map((row) => row.join(","))].join("\n");
    app.downloadFile("analytics_report.csv", csv, "text/csv");
    app.toast("CSV report exported");
  }

  function applyMode() {
    const mode = settings.display.chart_mode || "realtime";
    document.getElementById("chartModeLabel").textContent = mode === "realtime" ? "Real-time" : "After Episode";
    if (realtimeTimer) clearInterval(realtimeTimer);
    if (mode === "realtime") {
      realtimeTimer = setInterval(() => refresh().catch(() => {}), 5000);
    }
  }

  function wireEvents() {
    document.getElementById("refreshAnalytics").addEventListener("click", refresh);
    document.getElementById("exportJson").addEventListener("click", exportJson);
    document.getElementById("exportCsv").addEventListener("click", exportCsv);
    window.addEventListener("jalguard:download", exportJson);
    window.addEventListener("jalguard:settings-updated", (event) => {
      Object.assign(settings, event.detail || {});
      applyMode();
    });
  }

  async function boot() {
    app.boot("analytics");
    wireEvents();
    applyMode();
    await refresh();
  }

  boot().catch((error) => app.toast(error.message, "err"));
})();
