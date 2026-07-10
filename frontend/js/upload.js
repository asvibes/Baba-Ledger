// Stage 1 (PRD Section 5): upload a PDF and kick off analysis.
// Exposes window.BabasLedger.startAnalysis(file) for progress.js to reuse
// on retry, and hands off the returned job_id to progress.js's poller.

(function () {
  const dropzoneFrame = document.querySelector(".dropzone-frame");
  const fileInput = document.getElementById("file-input");
  const uploadError = document.getElementById("upload-error");

  const MAX_FILE_SIZE_MB = 50; // mirrors backend/config.py MAX_FILE_SIZE_MB —
  // this is a fast client-side check only; the backend is the source of truth.

  function showError(message) {
    uploadError.textContent = message;
    uploadError.hidden = false;
  }

  function clearError() {
    uploadError.hidden = true;
    uploadError.textContent = "";
  }

  async function submitFile(file) {
    clearError();

    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      showError("Unsupported file type. Version 1 supports PDF only.");
      return;
    }
    if (file.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      showError(`This file is larger than the ${MAX_FILE_SIZE_MB} MB limit.`);
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    let response;
    try {
      response = await fetch("/api/analyze", {
        method: "POST",
        body: formData,
      });
    } catch (networkErr) {
      showError("Could not reach the server. Is the backend running?");
      return;
    }

    const data = await response.json().catch(() => ({}));

    if (response.status !== 202) {
      showError(data.error || "This document could not be uploaded.");
      return;
    }

    // Hand off to progress.js
    window.BabasLedger.onUploadStarted(data.job_id, file.name);
  }

  fileInput.addEventListener("change", () => {
    if (fileInput.files.length > 0) submitFile(fileInput.files[0]);
  });

  ["dragenter", "dragover"].forEach((evt) =>
    dropzoneFrame.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzoneFrame.classList.add("is-dragover");
    })
  );

  ["dragleave", "drop"].forEach((evt) =>
    dropzoneFrame.addEventListener(evt, (e) => {
      e.preventDefault();
      dropzoneFrame.classList.remove("is-dragover");
    })
  );

  dropzoneFrame.addEventListener("drop", (e) => {
    const file = e.dataTransfer.files[0];
    if (file) submitFile(file);
  });

  window.BabasLedger = window.BabasLedger || {};
  window.BabasLedger.submitFile = submitFile;
})();