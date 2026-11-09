"use strict";

const button = document.getElementById("analyze");
const status = document.getElementById("status");
button.addEventListener("click", async () => {
  button.disabled = true;
  status.textContent = "Analyzing the synthetic sample. This may take a few seconds.";
  try {
    const response = await fetch("/v1/analyses", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: document.getElementById("synthetic-sample").textContent,
    });
    if (!response.ok) {
      status.textContent = response.status === 429
        ? "Analysis limit reached. Wait one minute before retrying."
        : "Analysis could not be saved. Try again later.";
      return;
    }
    const report = await response.json();
    if (!/^[0-9a-f-]{36}$/.test(report.analysis_id)) throw new Error("Invalid report");
    window.location.assign(`/v1/analyses/${report.analysis_id}/view`);
  } catch {
    status.textContent = "The service could not be reached. Try again later.";
  } finally {
    button.disabled = false;
  }
});
