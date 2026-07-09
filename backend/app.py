"""
Flask app entrypoint (PRD Section 18 / backend/app.py).

Wires together the pipeline stages from PRD Section 5:
  1. Upload PDF
  2. Detect text-based vs. scanned per page
  3. OCR scanned pages only
  4. Clean extracted text
  5. Classify document type + Classification Strength
  6. Extract document-specific metadata
  7. Detect business clauses
  8. Generate executive summary (chunked)
  9. Rank and highlight business-critical sentences
  10. Generate searchable highlighted PDF + analysis report
  11. Deliver downloads, then delete all uploaded/intermediate files

Processing runs in a background thread per job so the frontend can poll
live, specific progress (PRD 12.1) instead of a generic spinner. There's
no database (PRD 11): job state lives in an in-memory dict, which is
fine for a single-instance, single-primary-user deployment (PRD 11 time
budget note) but would need to move to Redis/DB before running behind
more than one worker process.

--------------------------------------------------------------------
Interfaces this module expects from not-yet-built pipeline modules
(documented here so those modules can be built independently and drop
straight in; see Section 18 build order):

  pipeline.ingestion.validate_upload(file_storage) -> (page_count: int, save_path: str)
      Raises FileTooLargeError / UnsupportedFileTypeError / TooManyPagesError
      / PasswordProtectedPDFError / CorruptedPDFError (utils.errors).

  pipeline.ocr.run_ocr_on_page(pdf_path: str, page_number: int) -> OcrPageResult
      OcrPageResult has .text: str, .bounding_boxes: list, .confidence: float.
      Raises OCRFailureError(page_number) on failure for that page only
      (other pages continue processing, per PRD 14.4).

  pipeline.metadata_extraction.extract_metadata(full_text: str, profile: dict) -> dict
      Returns {field_name: {"value": str, "confidence": float}} per PRD 9.1.

  pipeline.clause_detection.detect_clauses(full_text: str, profile: dict) -> list[dict]
      Returns [{"category": str, "text": str, "page": int}, ...].

  pipeline.scoring.score_sentences(sentences: list[str], metadata: dict,
                                    profile: dict) -> list[ScoredSentence]
      ScoredSentence has .sentence, .score, .metadata_score, .keyword_score,
      .semantic_score (PRD 8.1-8.4).

  pipeline.diversity_filter.apply_diversity_filter(
      scored_sentences: list[ScoredSentence], top_n: int) -> list[ScoredSentence]
      MMR near-duplicate suppression (PRD 8.5).

  pipeline.summarization.summarize_document(full_text: str) -> str
      Chunked BART summarization (PRD 8.8). Raises nothing fatal; on
      per-chunk failure it should degrade gracefully (PRD 14.4 spirit).

  pipeline.highlighting.highlight_pdf(pdf_path: str, highlights: list[ScoredSentence],
                                       page_map: dict, out_path: str) -> None
      Handles both text-based (10.1) and scanned/OCR (10.2) pages.

  pipeline.report_generator.generate_report(
      doc_type: str, classification, metadata: dict, clauses: list[dict],
      summary: str, highlights: list[ScoredSentence], out_path: str) -> None
      Produces the Analysis Report PDF (PRD Section 9).

  models.model_loader.load_all_models() -> None
      Loads BART / MiniLM / NER / KeyBERT once at Flask startup (PRD 11).
      Raises ModelLoadingError if a model fails to load.

  storage.temp_manager.JobWorkspace(job_id: str)
      .path -> str (temp dir for this job's files)
      .cleanup() -> None (deletes upload + all intermediate + output files,
      PRD Section 13)
--------------------------------------------------------------------
"""
import threading
import traceback
import uuid
from pathlib import Path

from flask import Flask, jsonify, request, send_file

from . import config
from .models import model_loader
from .pipeline import (
    classification,
    clause_detection,
    diversity_filter,
    highlighting,
    ingestion,
    metadata_extraction,
    ocr,
    page_router,
    report_generator,
    scoring,
    sentence_pipeline,
    summarization,
    text_cleaning,
)
from .profiles import get_profile
from .storage.temp_manager import JobWorkspace
from .utils.errors import PipelineError

app = Flask(__name__)

# --- In-memory job state (PRD 11: no database in Version 1) ---
# Guarded by _jobs_lock since Flask's dev/threaded server may access
# concurrently from the upload thread and status-polling requests.
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()

# Stage labels shown to the user (PRD 12.1) instead of a generic spinner.
STAGE_READING = "Reading PDF"
STAGE_OCR = "Performing OCR"
STAGE_ENTITIES = "Extracting Entities"
STAGE_SUMMARY = "Generating Summary"
STAGE_REPORT = "Building Report"
STAGE_DONE = "Done"


def _set_stage(job_id: str, stage: str, **extra):
    with _jobs_lock:
        _jobs[job_id].update(stage=stage, **extra)


def _fail_job(job_id: str, error: PipelineError):
    with _jobs_lock:
        _jobs[job_id].update(
            stage="Error",
            done=True,
            error={"message": error.user_message, "status_code": error.status_code},
        )


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify(status="ok")


@app.route("/api/analyze", methods=["POST"])
def analyze():
    """
    Stage 1 (Upload PDF) + kicks off Stages 2-11 in a background thread.
    Returns immediately with a job_id the frontend polls for status.
    """
    if "file" not in request.files:
        return jsonify(error="No file uploaded under the 'file' field."), 400

    upload = request.files["file"]
    job_id = uuid.uuid4().hex
    workspace = JobWorkspace(job_id)

    try:
        page_count, save_path = ingestion.validate_upload(upload, workspace.path)
    except PipelineError as e:
        workspace.cleanup()
        return jsonify(error=e.user_message), e.status_code

    with _jobs_lock:
        _jobs[job_id] = {
            "stage": STAGE_READING,
            "done": False,
            "error": None,
            "page_count": page_count,
            "result": None,
        }

    thread = threading.Thread(
        target=_run_pipeline, args=(job_id, save_path, workspace), daemon=True
    )
    thread.start()

    return jsonify(job_id=job_id, page_count=page_count), 202


def _run_pipeline(job_id: str, pdf_path: str, workspace: JobWorkspace):
    """
    Stages 2-11 (PRD Section 5), run off the request thread. Any
    PipelineError is caught and recorded on the job instead of crashing
    the worker (PRD 14.4: never fail silently, never crash outright).
    """
    try:
        # --- Stage 2/3: per-page text-vs-scanned routing + OCR ---
        raw_page_texts = ingestion.extract_raw_page_texts(pdf_path)
        routing = page_router.route_document(raw_page_texts)

        page_texts: list[str] = []
        needs_ocr = [r for r in routing if r.page_type.value == "scanned"]
        for i, r in enumerate(routing):
            if r.page_type.value == "scanned":
                _set_stage(job_id, STAGE_OCR, ocr_page=i + 1, ocr_total=len(needs_ocr))
                try:
                    ocr_result = ocr.run_ocr_on_page(pdf_path, r.page_number)
                    page_texts.append(ocr_result.text)
                except PipelineError:
                    # PRD 14.4: OCR failure on one page shouldn't kill the job.
                    page_texts.append("")
            else:
                page_texts.append(r.raw_text)

        # --- Stage 4: clean text ---
        cleaned_pages = [text_cleaning.clean_text(t) for t in page_texts]
        full_text = "\n".join(cleaned_pages)

        # --- Stage 5: classify + Classification Strength ---
        _set_stage(job_id, STAGE_ENTITIES)
        result = classification.classify_document(full_text)
        profile = get_profile(result.predicted_type)

        # --- sentence pipeline feeds both Top-N sizing (8.6) and scoring ---
        sp = sentence_pipeline.run_sentence_pipeline(cleaned_pages)

        # --- Stage 6/7: metadata + clause detection ---
        metadata = metadata_extraction.extract_metadata(full_text, profile)
        clauses = clause_detection.detect_clauses(full_text, profile)

        # --- Stage 8: chunked summary ---
        _set_stage(job_id, STAGE_SUMMARY)
        summary = summarization.summarize_document(full_text)

        # --- Stage 9: score, then diversity-filter down to Top-N ---
        scored = scoring.score_sentences(sp.sentences, metadata, profile)
        highlights = diversity_filter.apply_diversity_filter(scored, sp.top_n)

        # --- Stage 10: highlighted PDF + analysis report ---
        _set_stage(job_id, STAGE_REPORT)
        highlighted_pdf_path = str(Path(workspace.path) / "highlighted.pdf")
        report_pdf_path = str(Path(workspace.path) / "report.pdf")

        highlighting.highlight_pdf(
            pdf_path, highlights, page_map={}, out_path=highlighted_pdf_path
        )
        report_generator.generate_report(
            doc_type=result.predicted_type,
            classification=result,
            metadata=metadata,
            clauses=clauses,
            summary=summary,
            highlights=highlights,
            out_path=report_pdf_path,
        )

        with _jobs_lock:
            _jobs[job_id]["result"] = {
                "document_type": profile["display_name"],
                "classification_strength": result.strength.value,
                "metadata": metadata,
                "clauses": clauses,
                "summary": summary,
                "highlight_count": len(highlights),
                "report_path": report_pdf_path,
                "highlighted_pdf_path": highlighted_pdf_path,
            }
        _set_stage(job_id, STAGE_DONE, done=True)

    except PipelineError as e:
        _fail_job(job_id, e)
    except Exception:
        # Unexpected bug: still surface a meaningful error rather than
        # hanging the frontend on "Building Report" forever (PRD 14.4).
        traceback.print_exc()
        with _jobs_lock:
            _jobs[job_id].update(
                stage="Error",
                done=True,
                error={"message": "An unexpected error occurred while analyzing this document.",
                       "status_code": 500},
            )


@app.route("/api/analyze/<job_id>/status", methods=["GET"])
def analyze_status(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify(error="Unknown job_id."), 404
    return jsonify(
        stage=job["stage"],
        done=job["done"],
        error=job["error"],
        ocr_page=job.get("ocr_page"),
        ocr_total=job.get("ocr_total"),
    )


@app.route("/api/analyze/<job_id>/result", methods=["GET"])
def analyze_result(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify(error="Unknown job_id."), 404
    if job["error"]:
        return jsonify(error=job["error"]["message"]), job["error"]["status_code"]
    if not job["done"]:
        return jsonify(error="Job is still processing."), 409

    result = dict(job["result"])
    # Don't leak server filesystem paths to the client.
    result.pop("report_path", None)
    result.pop("highlighted_pdf_path", None)
    return jsonify(result)


@app.route("/api/analyze/<job_id>/download/<which>", methods=["GET"])
def download(job_id: str, which: str):
    """which is 'report' or 'highlighted' (PRD Section 10)."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None or not job.get("result"):
        return jsonify(error="Result not ready."), 404

    key = "report_path" if which == "report" else "highlighted_pdf_path"
    if which not in ("report", "highlighted"):
        return jsonify(error="Unknown download type."), 400

    path = job["result"][key]
    download_name = "analysis_report.pdf" if which == "report" else "highlighted_document.pdf"
    return send_file(path, as_attachment=True, download_name=download_name)


@app.route("/api/analyze/<job_id>", methods=["DELETE"])
def cleanup_job(job_id: str):
    """
    Explicit cleanup once the user has downloaded both files (PRD 13:
    Upload -> Analyze -> Generate PDFs -> User Downloads -> Delete
    Uploaded PDF -> Delete All Temporary/Intermediate Files).
    """
    with _jobs_lock:
        job = _jobs.pop(job_id, None)
    if job is None:
        return jsonify(error="Unknown job_id."), 404

    JobWorkspace(job_id).cleanup()
    return jsonify(status="cleaned_up")


@app.errorhandler(PipelineError)
def handle_pipeline_error(error: PipelineError):
    return jsonify(error=error.user_message), error.status_code


def create_app() -> Flask:
    """Factory for WSGI servers (e.g. gunicorn on Render, PRD 11)."""
    model_loader.load_all_models()
    return app


if __name__ == "__main__":
    model_loader.load_all_models()
    app.run(host="0.0.0.0", port=5000, debug=False)
