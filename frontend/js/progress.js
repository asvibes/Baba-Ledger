// Stages 2-11: polls /api/analyze/<job_id>/status, then renders
// /api/analyze/<job_id>/result once done. Matches backend/app.py exactly:
//   status  -> {stage, done, error, ocr_page, ocr_total}
//   result  -> {document_type, classification_strength, metadata, clauses,
//               summary, highlight_count}
//   download-> GET /api/analyze/<job_id>/download/report|highlighted

(function () {
  const POLL_INTERVAL_MS = 1500;

  const stages = {
    upload: document.getElementById("stage-upload"),
    processing: document.getElementById("stage-processing"),
    error: document.getElementById("stage-error"),
    results: document.getElementById("stage-results"),
  };

  const processingFile = document.querySelector(".processing-file");
  const stageListItems = document.querySelectorAll("#stage-list li");
  const ocrProgressEl = document.getElementById("ocr-progress");

  const errorMessageEl = document.getElementById("error-message");
  const errorRetryBtn = document.getElementById("error-retry");
  const startOverBtn = document.getElementById("start-over");

  let currentJobId = null;
  let pollTimer = null;

  function showStage(name) {
    Object.entries(stages).forEach(([key, el]) => {
      el.classList.toggle("is-active", key === name);
    });
  }

  function updateStageList(currentStageLabel) {
    const order = [
      "Reading PDF",
      "Performing OCR",
      "Extracting Entities",
      "Generating Summary",
      "Building Report",
      "Done",
    ];
    const currentIndex = order.indexOf(currentStageLabel);

    stageListItems.forEach((li) => {
      const stageName = li.dataset.stage;
      const idx = order.indexOf(stageName);
      li.classList.remove("is-current", "is-done");
      if (idx < currentIndex) li.classList.add("is-done");
      if (idx === currentIndex) li.classList.add("is-current");
    });
  }

  function stopPolling() {
    if (pollTimer) {
      clearTimeout(pollTimer);
      pollTimer = null;
    }
  }

  async function pollStatus() {
    if (!currentJobId) return;

    let response;
    try {
      response = await fetch(`/api/analyze/${currentJobId}/status`);
    } catch (e) {
      // Transient network hiccup — try again on the next tick rather
      // than failing the whole job over one dropped request.
      pollTimer = setTimeout(pollStatus, POLL_INTERVAL_MS);
      return;
    }

    if (!response.ok) {
      showError("Lost track of this job. Please try uploading again.");
      return;
    }

    const data = await response.json();

    if (data.error) {
      showError(data.error.message);
      return;
    }

    updateStageList(data.stage);

    if (data.stage === "Performing OCR" && data.ocr_page && data.ocr_total) {
      ocrProgressEl.textContent = ` (page ${data.ocr_page} of ${data.ocr_total})`;
    } else {
      ocrProgressEl.textContent = "";
    }

    if (data.done) {
      await loadResult();
      return;
    }

    pollTimer = setTimeout(pollStatus, POLL_INTERVAL_MS);
  }

  function showError(message) {
    stopPolling();
    errorMessageEl.textContent = message;
    showStage("error");
  }

  async function loadResult() {
    let response;
    try {
      response = await fetch(`/api/analyze/${currentJobId}/result`);
    } catch (e) {
      showError("Could not retrieve the results. Please try again.");
      return;
    }

    const data = await response.json();

    if (!response.ok) {
      showError(data.error || "The results could not be retrieved.");
      return;
    }

    renderResult(data);
    showStage("results");
  }

  function renderResult(result) {
    document.getElementById("result-doctype").textContent = result.document_type || "Unknown";

    const strengthEl = document.getElementById("result-strength");
    const strength = (result.classification_strength || "unknown").toLowerCase();
    strengthEl.textContent = strength.toUpperCase();
    strengthEl.className = `stamp ${strength}`;

    document.getElementById("result-summary").textContent =
      result.summary && result.summary.trim()
        ? result.summary
        : "A summary could not be generated for this document.";

    const metadataEl = document.getElementById("result-metadata");
    metadataEl.innerHTML = "";
    const metadata = result.metadata || {};
    const fieldNames = Object.keys(metadata);

    if (fieldNames.length === 0) {
      metadataEl.innerHTML = `<p class="card-body">No metadata fields were extracted.</p>`;
    } else {
      fieldNames.forEach((fieldName) => {
        const field = metadata[fieldName] || {};
        const dt = document.createElement("dt");
        dt.textContent = fieldName;

        const dd = document.createElement("dd");
        if (field.value) {
          const confidencePct = Math.round((field.confidence || 0) * 100);
          dd.textContent = field.value;
          if (confidencePct < 60) {
            const flag = document.createElement("span");
            flag.className = "confidence-flag";
            flag.textContent = `⚠ ${confidencePct}%`;
            dd.appendChild(flag);
          }
        } else {
          dd.textContent = "Not found";
          dd.classList.add("is-missing");
        }

        metadataEl.appendChild(dt);
        metadataEl.appendChild(dd);
      });
    }

    const clausesEl = document.getElementById("result-clauses");
    clausesEl.innerHTML = "";
    const clauses = result.clauses || [];

    if (clauses.length === 0) {
      clausesEl.innerHTML = `<li class="card-body">No business clauses were detected.</li>`;
    } else {
      clauses.forEach((clause) => {
        const li = document.createElement("li");
        const pageLabel = clause.page != null ? ` · page ${clause.page}` : "";
        li.innerHTML = `<span class="clause-category">${clause.category || "Uncategorized"}${pageLabel}</span>${clause.text || ""}`;
        clausesEl.appendChild(li);
      });
    }

    document.getElementById("result-highlight-count").textContent =
      `${result.highlight_count || 0} business-critical sentence(s) highlighted in the downloadable PDF.`;

    document.getElementById("download-report").href = `/api/analyze/${currentJobId}/download/report`;
    document.getElementById("download-highlighted").href = `/api/analyze/${currentJobId}/download/highlighted`;
  }

  function resetToUpload() {
    stopPolling();
    if (currentJobId) {
      // Best-effort cleanup (PRD 13) — don't block the UI on this.
      fetch(`/api/analyze/${currentJobId}`, { method: "DELETE" }).catch(() => {});
    }
    currentJobId = null;
    document.getElementById("file-input").value = "";
    document.getElementById("upload-error").hidden = true;
    showStage("upload");
  }

  errorRetryBtn.addEventListener("click", resetToUpload);
  startOverBtn.addEventListener("click", resetToUpload);

  // Called by upload.js once /api/analyze returns a job_id.
  window.BabasLedger = window.BabasLedger || {};
  window.BabasLedger.onUploadStarted = function (jobId, fileName) {
    currentJobId = jobId;
    processingFile.textContent = fileName;
    updateStageList("Reading PDF");
    ocrProgressEl.textContent = "";
    showStage("processing");
    pollStatus();
  };
})();